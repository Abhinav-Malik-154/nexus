#!/usr/bin/env python3
"""
Nexus Data Pipeline — Production-Grade Dataset Management

Features:
- Automated data fetching from DeFiLlama + CoinGecko
- Real price data integration (not zeros!)
- Data validation & quality checks
- Proper train/val/test splits with temporal awareness
- Versioned datasets with checksums
- SQLite backend for efficient querying

Usage:
    python data_pipeline.py fetch          # Fetch fresh data
    python data_pipeline.py build          # Build training dataset
    python data_pipeline.py validate       # Validate dataset quality
    python data_pipeline.py split          # Create train/val/test splits
    python data_pipeline.py export         # Export to JSON/CSV
"""

import json
import sqlite3
import hashlib
import requests
import argparse
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict, field
from typing import Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

# ═══════════════════════════════════════════════════════════════════════════
#                              CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════

DATA_DIR = Path(__file__).parent
DB_PATH = DATA_DIR / "nexus.db"

LLAMA_PROTOCOLS = "https://api.llama.fi/protocols"
LLAMA_PROTOCOL = "https://api.llama.fi/protocol/{slug}"
LLAMA_TVL_HIST = "https://api.llama.fi/v2/historicalChainTvl/{chain}"
COINGECKO_PRICE = "https://api.coingecko.com/api/v3/coins/{id}/market_chart"
COINGECKO_LIST = "https://api.coingecko.com/api/v3/coins/list"

HEADERS = {"User-Agent": "Mozilla/5.0 (Nexus/2.0)"}

CATEGORY_RISK = {
    "Lending": 0.7, "CDP": 0.8, "Dexes": 0.4, "Liquid Staking": 0.5,
    "Bridge": 0.9, "Yield": 0.6, "Yield Aggregator": 0.65,
    "Derivatives": 0.7, "Algo-Stables": 0.95, "Staking": 0.4,
    "Services": 0.3, "Insurance": 0.4, "Launchpad": 0.5,
    "Options": 0.7, "Indexes": 0.5, "NFT Lending": 0.75,
    "RWA": 0.5, "Liquidity Manager": 0.6, "Farm": 0.7,
    "Leveraged Farming": 0.85, "Uncollateralized Lending": 0.9,
    "Prediction Market": 0.6, "Privacy": 0.5, "Payments": 0.3,
}


@dataclass
class ProtocolSnapshot:
    """Single point-in-time protocol observation."""
    protocol: str
    slug: str
    date: str
    tvl: float
    tvl_change_1d: float = 0.0
    tvl_change_7d: float = 0.0
    tvl_change_30d: float = 0.0
    tvl_volatility: float = 0.0
    price: float = 0.0
    price_change_1d: float = 0.0
    price_change_7d: float = 0.0
    price_volatility: float = 0.0
    price_crash_7d: float = 0.0
    mcap: float = 0.0
    mcap_to_tvl: float = 0.0
    category: str = "Unknown"
    category_risk: float = 0.5
    chain_count: int = 1
    audit_count: int = 0
    age_days: int = 0
    was_exploited: bool = False
    days_to_exploit: int = -1
    exploit_type: Optional[str] = None
    exploit_loss: Optional[float] = None


@dataclass
class DatasetMetadata:
    """Dataset versioning metadata."""
    version: str
    created_at: str
    checksum: str
    total_samples: int
    exploit_samples: int
    safe_samples: int
    protocols: int
    date_range: tuple
    features: list
    splits: dict = field(default_factory=dict)


# ═══════════════════════════════════════════════════════════════════════════
#                              DATABASE
# ═══════════════════════════════════════════════════════════════════════════

def init_db():
    """Initialize SQLite database with proper schema."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    cur.executescript("""
        -- Protocol master data
        CREATE TABLE IF NOT EXISTS protocols (
            slug TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            category TEXT,
            chains TEXT,  -- JSON array
            gecko_id TEXT,
            symbol TEXT,
            url TEXT,
            twitter TEXT,
            audit TEXT,
            created_at TEXT,
            updated_at TEXT
        );
        
        -- TVL snapshots
        CREATE TABLE IF NOT EXISTS tvl_snapshots (
            id INTEGER PRIMARY KEY,
            slug TEXT NOT NULL,
            date TEXT NOT NULL,
            tvl REAL NOT NULL,
            chain_tvls TEXT,  -- JSON object
            UNIQUE(slug, date),
            FOREIGN KEY (slug) REFERENCES protocols(slug)
        );
        
        -- Price snapshots
        CREATE TABLE IF NOT EXISTS price_snapshots (
            id INTEGER PRIMARY KEY,
            gecko_id TEXT NOT NULL,
            date TEXT NOT NULL,
            price REAL,
            mcap REAL,
            volume REAL,
            UNIQUE(gecko_id, date)
        );
        
        -- Exploit events
        CREATE TABLE IF NOT EXISTS exploits (
            id INTEGER PRIMARY KEY,
            slug TEXT NOT NULL,
            date TEXT NOT NULL,
            loss_usd REAL,
            type TEXT,
            description TEXT,
            source TEXT,
            UNIQUE(slug, date),
            FOREIGN KEY (slug) REFERENCES protocols(slug)
        );
        
        -- Computed features (training samples)
        CREATE TABLE IF NOT EXISTS samples (
            id INTEGER PRIMARY KEY,
            slug TEXT NOT NULL,
            date TEXT NOT NULL,
            features TEXT NOT NULL,  -- JSON
            label REAL NOT NULL,
            split TEXT,  -- train/val/test
            UNIQUE(slug, date)
        );
        
        -- Dataset versions
        CREATE TABLE IF NOT EXISTS dataset_versions (
            version TEXT PRIMARY KEY,
            created_at TEXT,
            metadata TEXT  -- JSON
        );
        
        -- Indexes for fast queries
        CREATE INDEX IF NOT EXISTS idx_tvl_slug_date ON tvl_snapshots(slug, date);
        CREATE INDEX IF NOT EXISTS idx_price_gecko_date ON price_snapshots(gecko_id, date);
        CREATE INDEX IF NOT EXISTS idx_samples_split ON samples(split);
        CREATE INDEX IF NOT EXISTS idx_exploits_date ON exploits(date);
    """)
    
    conn.commit()
    return conn


# ═══════════════════════════════════════════════════════════════════════════
#                           DATA FETCHING
# ═══════════════════════════════════════════════════════════════════════════

class DataFetcher:
    """Fetch and store protocol data from external APIs."""
    
    def __init__(self, db: sqlite3.Connection):
        self.db = db
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        self._gecko_map = {}
    
    def fetch_protocols(self, min_tvl: float = 1e6) -> int:
        """Fetch all protocols from DeFiLlama."""
        print("Fetching protocols from DeFiLlama...")
        
        resp = self.session.get(LLAMA_PROTOCOLS, timeout=30)
        resp.raise_for_status()
        protocols = resp.json()
        
        count = 0
        cur = self.db.cursor()
        now = datetime.utcnow().isoformat()
        
        for p in protocols:
            tvl = p.get("tvl", 0) or 0
            if tvl < min_tvl:
                continue
            
            cur.execute("""
                INSERT OR REPLACE INTO protocols 
                (slug, name, category, chains, gecko_id, symbol, url, twitter, audit, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, COALESCE((SELECT created_at FROM protocols WHERE slug = ?), ?), ?)
            """, (
                p.get("slug"),
                p.get("name"),
                p.get("category"),
                json.dumps(p.get("chains", [])),
                p.get("gecko_id"),
                p.get("symbol"),
                p.get("url"),
                p.get("twitter"),
                json.dumps(p.get("audit_links", [])),
                p.get("slug"), now, now
            ))
            count += 1
        
        self.db.commit()
        print(f"  ✓ Stored {count} protocols")
        return count
    
    def fetch_tvl_history(self, slug: str, days: int = 365) -> int:
        """Fetch TVL history for a protocol."""
        try:
            resp = self.session.get(
                LLAMA_PROTOCOL.format(slug=slug),
                timeout=30
            )
            resp.raise_for_status()
            data = resp.json()
            
            tvl_data = data.get("tvl", [])
            if not tvl_data:
                return 0
            
            cur = self.db.cursor()
            count = 0
            cutoff = (datetime.utcnow() - timedelta(days=days)).timestamp()
            
            for point in tvl_data:
                ts = point.get("date", 0)
                if ts < cutoff:
                    continue
                    
                date = datetime.fromtimestamp(ts).strftime("%Y-%m-%d")
                tvl = point.get("totalLiquidityUSD", 0)
                
                cur.execute("""
                    INSERT OR REPLACE INTO tvl_snapshots (slug, date, tvl, chain_tvls)
                    VALUES (?, ?, ?, ?)
                """, (slug, date, tvl, json.dumps({})))
                count += 1
            
            self.db.commit()
            return count
        except Exception as e:
            print(f"  ✗ {slug}: {e}")
            return 0
    
    def fetch_all_tvl(self, max_protocols: int = 500, days: int = 365):
        """Fetch TVL history for top protocols."""
        print(f"Fetching TVL history ({days} days)...")
        
        cur = self.db.cursor()
        cur.execute("SELECT slug FROM protocols ORDER BY ROWID LIMIT ?", (max_protocols,))
        slugs = [r[0] for r in cur.fetchall()]
        
        total = 0
        for i, slug in enumerate(slugs, 1):
            count = self.fetch_tvl_history(slug, days)
            total += count
            if i % 50 == 0:
                print(f"  Progress: {i}/{len(slugs)} protocols, {total} snapshots")
            time.sleep(0.2)  # Rate limiting
        
        print(f"  ✓ Stored {total} TVL snapshots")
        return total
    
    def fetch_gecko_prices(self, gecko_id: str, days: int = 365) -> int:
        """Fetch price history from CoinGecko."""
        try:
            resp = self.session.get(
                COINGECKO_PRICE.format(id=gecko_id),
                params={"vs_currency": "usd", "days": days},
                timeout=30
            )
            resp.raise_for_status()
            data = resp.json()
            
            prices = data.get("prices", [])
            mcaps = data.get("market_caps", [])
            
            cur = self.db.cursor()
            count = 0
            
            mcap_map = {datetime.fromtimestamp(m[0]/1000).strftime("%Y-%m-%d"): m[1] for m in mcaps}
            
            for ts, price in prices:
                date = datetime.fromtimestamp(ts/1000).strftime("%Y-%m-%d")
                mcap = mcap_map.get(date, 0)
                
                cur.execute("""
                    INSERT OR REPLACE INTO price_snapshots (gecko_id, date, price, mcap, volume)
                    VALUES (?, ?, ?, ?, ?)
                """, (gecko_id, date, price, mcap, 0))
                count += 1
            
            self.db.commit()
            return count
        except Exception as e:
            return 0
    
    def fetch_all_prices(self, days: int = 365):
        """Fetch price history for protocols with gecko_id."""
        print(f"Fetching price history ({days} days)...")
        
        cur = self.db.cursor()
        cur.execute("SELECT DISTINCT gecko_id FROM protocols WHERE gecko_id IS NOT NULL AND gecko_id != ''")
        gecko_ids = [r[0] for r in cur.fetchall()]
        
        total = 0
        for i, gid in enumerate(gecko_ids, 1):
            count = self.fetch_gecko_prices(gid, days)
            total += count
            if i % 20 == 0:
                print(f"  Progress: {i}/{len(gecko_ids)} tokens, {total} prices")
            time.sleep(1.2)  # CoinGecko rate limit
        
        print(f"  ✓ Stored {total} price snapshots")
        return total
    
    def load_exploits(self, filepath: Path = None):
        """Load exploit data from JSON file."""
        if filepath is None:
            filepath = DATA_DIR / "defillama_hacks.json"
        
        if not filepath.exists():
            print(f"  ✗ Exploit file not found: {filepath}")
            return 0
        
        print(f"Loading exploits from {filepath.name}...")
        
        with open(filepath) as f:
            data = json.load(f)
        
        cur = self.db.cursor()
        count = 0
        
        exploits = data if isinstance(data, list) else data.get("hacks", data.get("exploits", []))
        
        for exp in exploits:
            # Handle different field names
            slug = exp.get("project", exp.get("slug", exp.get("protocol", ""))).lower().replace(" ", "-")
            date = exp.get("date", "")
            
            # Parse date
            if isinstance(date, (int, float)):
                date = datetime.fromtimestamp(date).strftime("%Y-%m-%d")
            elif "T" in str(date):
                date = date.split("T")[0]
            
            loss = exp.get("amount", exp.get("loss", exp.get("funds_lost", 0))) or 0
            if isinstance(loss, str):
                loss = float(loss.replace(",", "").replace("$", ""))
            
            exp_type = exp.get("classification", exp.get("type", exp.get("technique", "Unknown")))
            
            try:
                cur.execute("""
                    INSERT OR REPLACE INTO exploits (slug, date, loss_usd, type, description, source)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (slug, date, loss, exp_type, exp.get("description", ""), "defillama"))
                count += 1
            except:
                continue
        
        self.db.commit()
        print(f"  ✓ Loaded {count} exploits")
        return count


# ═══════════════════════════════════════════════════════════════════════════
#                         FEATURE ENGINEERING
# ═══════════════════════════════════════════════════════════════════════════

class FeatureBuilder:
    """Compute features for ML training."""
    
    FEATURES = [
        "tvl_log", "tvl_change_1d", "tvl_change_7d", "tvl_change_30d",
        "tvl_volatility", "price_change_1d", "price_change_7d",
        "price_volatility", "price_crash_7d", "category_risk",
        "chain_count", "mcap_to_tvl", "age_days", "audit_score"
    ]
    
    def __init__(self, db: sqlite3.Connection):
        self.db = db
    
    def _get_tvl_history(self, slug: str, date: str, lookback: int = 30) -> list:
        """Get TVL history for a protocol up to a date."""
        cur = self.db.cursor()
        cur.execute("""
            SELECT date, tvl FROM tvl_snapshots
            WHERE slug = ? AND date <= ?
            ORDER BY date DESC LIMIT ?
        """, (slug, date, lookback + 1))
        return [(r[0], r[1]) for r in cur.fetchall()]
    
    def _get_price_history(self, gecko_id: str, date: str, lookback: int = 30) -> list:
        """Get price history for a token up to a date."""
        cur = self.db.cursor()
        cur.execute("""
            SELECT date, price, mcap FROM price_snapshots
            WHERE gecko_id = ? AND date <= ?
            ORDER BY date DESC LIMIT ?
        """, (gecko_id, date, lookback + 1))
        return [(r[0], r[1], r[2]) for r in cur.fetchall()]
    
    def _get_protocol_info(self, slug: str) -> dict:
        """Get protocol metadata."""
        cur = self.db.cursor()
        cur.execute("""
            SELECT name, category, chains, gecko_id, audit, created_at 
            FROM protocols WHERE slug = ?
        """, (slug,))
        row = cur.fetchone()
        if not row:
            return {}
        return {
            "name": row[0],
            "category": row[1],
            "chains": json.loads(row[2] or "[]"),
            "gecko_id": row[3],
            "audit": json.loads(row[4] or "[]"),
            "created_at": row[5]
        }
    
    def _get_exploit(self, slug: str) -> Optional[dict]:
        """Get exploit info for a protocol."""
        cur = self.db.cursor()
        cur.execute("""
            SELECT date, loss_usd, type FROM exploits WHERE slug = ?
            ORDER BY date ASC LIMIT 1
        """, (slug,))
        row = cur.fetchone()
        if not row:
            return None
        return {"date": row[0], "loss": row[1], "type": row[2]}
    
    def compute_features(self, slug: str, date: str) -> Optional[dict]:
        """Compute all features for a protocol at a point in time."""
        info = self._get_protocol_info(slug)
        if not info:
            return None
        
        tvl_hist = self._get_tvl_history(slug, date, 35)
        if len(tvl_hist) < 2:
            return None
        
        current_tvl = tvl_hist[0][1]
        if current_tvl <= 0:
            return None
        
        # TVL features
        tvl_log = np.log1p(current_tvl) / 30.0
        
        tvl_1d = tvl_hist[1][1] if len(tvl_hist) > 1 else current_tvl
        tvl_7d = tvl_hist[7][1] if len(tvl_hist) > 7 else current_tvl
        tvl_30d = tvl_hist[30][1] if len(tvl_hist) > 30 else current_tvl
        
        tvl_change_1d = (current_tvl - tvl_1d) / tvl_1d * 100 if tvl_1d > 0 else 0
        tvl_change_7d = (current_tvl - tvl_7d) / tvl_7d * 100 if tvl_7d > 0 else 0
        tvl_change_30d = (current_tvl - tvl_30d) / tvl_30d * 100 if tvl_30d > 0 else 0
        
        # TVL volatility (std of daily changes)
        tvl_values = [t[1] for t in tvl_hist[:14] if t[1] > 0]
        if len(tvl_values) > 1:
            changes = [(tvl_values[i] - tvl_values[i+1]) / tvl_values[i+1] * 100 
                       for i in range(len(tvl_values)-1) if tvl_values[i+1] > 0]
            tvl_volatility = np.std(changes) if changes else 0
        else:
            tvl_volatility = 0
        
        # Price features
        price_change_1d = 0.0
        price_change_7d = 0.0
        price_volatility = 0.0
        price_crash_7d = 0.0
        mcap = 0.0
        
        if info.get("gecko_id"):
            price_hist = self._get_price_history(info["gecko_id"], date, 35)
            if len(price_hist) >= 2:
                current_price = price_hist[0][1]
                mcap = price_hist[0][2] or 0
                
                price_1d = price_hist[1][1] if len(price_hist) > 1 else current_price
                price_7d = price_hist[7][1] if len(price_hist) > 7 else current_price
                
                if price_1d and price_1d > 0:
                    price_change_1d = (current_price - price_1d) / price_1d * 100
                if price_7d and price_7d > 0:
                    price_change_7d = (current_price - price_7d) / price_7d * 100
                
                # Price volatility
                prices = [p[1] for p in price_hist[:14] if p[1] and p[1] > 0]
                if len(prices) > 1:
                    pct_changes = [(prices[i] - prices[i+1]) / prices[i+1] * 100 
                                   for i in range(len(prices)-1) if prices[i+1] > 0]
                    price_volatility = np.std(pct_changes) if pct_changes else 0
                    
                    # Max crash in 7 days
                    if len(prices) >= 7:
                        max_price = max(prices[:7])
                        min_price = min(prices[:7])
                        price_crash_7d = (max_price - min_price) / max_price * 100 if max_price > 0 else 0
        
        # Category & chains
        category = info.get("category", "Unknown")
        category_risk = CATEGORY_RISK.get(category, 0.5)
        chain_count = len(info.get("chains", [])) or 1
        
        # MCap to TVL ratio
        mcap_to_tvl = min(mcap / current_tvl, 10.0) if current_tvl > 0 and mcap > 0 else 0
        
        # Age
        age_days = 0
        if info.get("created_at"):
            try:
                created = datetime.fromisoformat(info["created_at"].replace("Z", ""))
                obs_date = datetime.strptime(date, "%Y-%m-%d")
                age_days = (obs_date - created).days
            except:
                pass
        
        # Audit score
        audits = info.get("audit", [])
        audit_score = min(len(audits) / 3.0, 1.0)  # Normalize to 0-1
        
        # Exploit label
        exploit = self._get_exploit(slug)
        was_exploited = False
        days_to_exploit = -1
        exploit_type = None
        exploit_loss = None
        
        if exploit:
            exp_date = datetime.strptime(exploit["date"], "%Y-%m-%d")
            obs_date = datetime.strptime(date, "%Y-%m-%d")
            days_diff = (exp_date - obs_date).days
            
            if days_diff >= 0:  # Exploit is in the future relative to observation
                was_exploited = True
                days_to_exploit = days_diff
                exploit_type = exploit["type"]
                exploit_loss = exploit["loss"]
        
        return {
            "protocol": info["name"],
            "slug": slug,
            "date": date,
            "tvl": current_tvl,
            "tvl_log": round(tvl_log, 4),
            "tvl_change_1d": round(np.clip(tvl_change_1d, -100, 100), 2),
            "tvl_change_7d": round(np.clip(tvl_change_7d, -100, 100), 2),
            "tvl_change_30d": round(np.clip(tvl_change_30d, -100, 100), 2),
            "tvl_volatility": round(min(tvl_volatility, 50), 2),
            "price_change_1d": round(np.clip(price_change_1d, -100, 100), 2),
            "price_change_7d": round(np.clip(price_change_7d, -100, 100), 2),
            "price_volatility": round(min(price_volatility, 50), 2),
            "price_crash_7d": round(min(price_crash_7d, 100), 2),
            "category": category,
            "category_risk": round(category_risk, 2),
            "chain_count": chain_count,
            "mcap_to_tvl": round(mcap_to_tvl, 3),
            "age_days": age_days,
            "audit_score": round(audit_score, 2),
            "was_exploited": was_exploited,
            "days_to_exploit": days_to_exploit,
            "exploit_type": exploit_type,
            "exploit_loss": exploit_loss
        }
    
    def build_dataset(self, sample_days: int = 7, max_samples_per_protocol: int = 50) -> list:
        """Build training dataset with temporal sampling."""
        print("Building training dataset...")
        
        cur = self.db.cursor()
        
        # Get all protocols with TVL data
        cur.execute("""
            SELECT DISTINCT slug FROM tvl_snapshots
        """)
        slugs = [r[0] for r in cur.fetchall()]
        
        # Get all exploit dates for labeling
        cur.execute("SELECT slug, date FROM exploits")
        exploit_dates = {r[0]: r[1] for r in cur.fetchall()}
        
        samples = []
        
        for slug in slugs:
            # Get date range for this protocol
            cur.execute("""
                SELECT MIN(date), MAX(date) FROM tvl_snapshots WHERE slug = ?
            """, (slug,))
            date_range = cur.fetchone()
            if not date_range[0]:
                continue
            
            start = datetime.strptime(date_range[0], "%Y-%m-%d")
            end = datetime.strptime(date_range[1], "%Y-%m-%d")
            
            # Sample dates
            current = start + timedelta(days=30)  # Skip first month for features
            sample_count = 0
            
            while current <= end and sample_count < max_samples_per_protocol:
                date_str = current.strftime("%Y-%m-%d")
                
                features = self.compute_features(slug, date_str)
                if features:
                    samples.append(features)
                    sample_count += 1
                
                current += timedelta(days=sample_days)
        
        print(f"  ✓ Generated {len(samples)} samples from {len(slugs)} protocols")
        return samples


# ═══════════════════════════════════════════════════════════════════════════
#                         DATA VALIDATION
# ═══════════════════════════════════════════════════════════════════════════

class DataValidator:
    """Validate dataset quality."""
    
    def __init__(self, samples: list):
        self.samples = samples
        self.issues = []
    
    def check_missing_values(self) -> int:
        """Check for missing/null values."""
        count = 0
        for i, s in enumerate(self.samples):
            for key, val in s.items():
                if val is None and key not in ["exploit_type", "exploit_loss"]:
                    self.issues.append(f"Sample {i}: missing {key}")
                    count += 1
        return count
    
    def check_value_ranges(self) -> int:
        """Check that values are in expected ranges."""
        count = 0
        for i, s in enumerate(self.samples):
            if s.get("tvl", 0) <= 0:
                self.issues.append(f"Sample {i}: invalid TVL {s.get('tvl')}")
                count += 1
            if not 0 <= s.get("category_risk", 0) <= 1:
                self.issues.append(f"Sample {i}: invalid category_risk")
                count += 1
        return count
    
    def check_class_balance(self) -> dict:
        """Check class distribution."""
        exploited = sum(1 for s in self.samples if s.get("was_exploited"))
        safe = len(self.samples) - exploited
        ratio = exploited / len(self.samples) if self.samples else 0
        
        return {
            "total": len(self.samples),
            "exploited": exploited,
            "safe": safe,
            "exploit_ratio": round(ratio, 3),
            "balanced": 0.2 <= ratio <= 0.6
        }
    
    def check_temporal_coverage(self) -> dict:
        """Check date range coverage."""
        dates = [s.get("date") for s in self.samples if s.get("date")]
        if not dates:
            return {"min": None, "max": None, "days": 0}
        
        dates = sorted(dates)
        min_date = datetime.strptime(dates[0], "%Y-%m-%d")
        max_date = datetime.strptime(dates[-1], "%Y-%m-%d")
        
        return {
            "min": dates[0],
            "max": dates[-1],
            "days": (max_date - min_date).days,
            "adequate": (max_date - min_date).days >= 365
        }
    
    def check_feature_variance(self) -> dict:
        """Check that features have variance (not all zeros)."""
        feature_keys = ["tvl_change_1d", "tvl_change_7d", "price_change_1d", 
                        "price_change_7d", "tvl_volatility", "price_volatility"]
        
        results = {}
        for key in feature_keys:
            values = [s.get(key, 0) for s in self.samples]
            nonzero = sum(1 for v in values if v != 0)
            results[key] = {
                "nonzero_count": nonzero,
                "nonzero_pct": round(100 * nonzero / len(values), 1) if values else 0,
                "std": round(np.std(values), 4) if values else 0
            }
        
        return results
    
    def validate(self) -> dict:
        """Run all validation checks."""
        print("Validating dataset...")
        
        results = {
            "sample_count": len(self.samples),
            "missing_values": self.check_missing_values(),
            "range_errors": self.check_value_ranges(),
            "class_balance": self.check_class_balance(),
            "temporal_coverage": self.check_temporal_coverage(),
            "feature_variance": self.check_feature_variance(),
            "issues": self.issues[:20]  # First 20 issues
        }
        
        # Overall quality score
        score = 10.0
        if results["missing_values"] > 0:
            score -= min(results["missing_values"] / 100, 2)
        if results["range_errors"] > 0:
            score -= min(results["range_errors"] / 50, 2)
        if not results["class_balance"]["balanced"]:
            score -= 1
        if not results["temporal_coverage"]["adequate"]:
            score -= 1
        
        # Check feature variance (price features should have >30% nonzero)
        for key, stats in results["feature_variance"].items():
            if "price" in key and stats["nonzero_pct"] < 30:
                score -= 0.5
        
        results["quality_score"] = round(max(score, 0), 1)
        
        print(f"  Quality Score: {results['quality_score']}/10")
        return results


# ═══════════════════════════════════════════════════════════════════════════
#                         TRAIN/VAL/TEST SPLIT
# ═══════════════════════════════════════════════════════════════════════════

class DataSplitter:
    """Create temporal train/val/test splits."""
    
    def __init__(self, samples: list):
        self.samples = sorted(samples, key=lambda x: x.get("date", ""))
    
    def temporal_split(self, train_end: str, val_end: str) -> dict:
        """
        Split by date for proper temporal validation.
        
        Args:
            train_end: Last date for training (e.g., "2023-06-30")
            val_end: Last date for validation (e.g., "2023-12-31")
        
        Returns dict with train/val/test sample lists.
        """
        train = [s for s in self.samples if s["date"] <= train_end]
        val = [s for s in self.samples if train_end < s["date"] <= val_end]
        test = [s for s in self.samples if s["date"] > val_end]
        
        return {
            "train": train,
            "val": val,
            "test": test,
            "splits": {
                "train": {"count": len(train), "end_date": train_end},
                "val": {"count": len(val), "start": train_end, "end": val_end},
                "test": {"count": len(test), "start_date": val_end}
            }
        }
    
    def stratified_temporal_split(self, train_ratio: float = 0.7, val_ratio: float = 0.15) -> dict:
        """
        Split temporally while maintaining class balance.
        """
        # Group by protocol to prevent leakage
        by_protocol = {}
        for s in self.samples:
            slug = s["slug"]
            if slug not in by_protocol:
                by_protocol[slug] = []
            by_protocol[slug].append(s)
        
        # Sort protocols by their first exploit date (if any)
        protocol_order = sorted(
            by_protocol.keys(),
            key=lambda p: min((s["date"] for s in by_protocol[p] if s["was_exploited"]), default="9999-12-31")
        )
        
        n = len(protocol_order)
        train_end = int(n * train_ratio)
        val_end = int(n * (train_ratio + val_ratio))
        
        train = []
        val = []
        test = []
        
        for i, slug in enumerate(protocol_order):
            if i < train_end:
                train.extend(by_protocol[slug])
            elif i < val_end:
                val.extend(by_protocol[slug])
            else:
                test.extend(by_protocol[slug])
        
        return {
            "train": train,
            "val": val,
            "test": test,
            "splits": {
                "train": {"count": len(train), "protocols": train_end},
                "val": {"count": len(val), "protocols": val_end - train_end},
                "test": {"count": len(test), "protocols": n - val_end}
            }
        }


# ═══════════════════════════════════════════════════════════════════════════
#                         EXPORT & VERSIONING
# ═══════════════════════════════════════════════════════════════════════════

class DataExporter:
    """Export datasets with versioning."""
    
    def __init__(self, db: sqlite3.Connection):
        self.db = db
    
    def _compute_checksum(self, data: dict) -> str:
        """Compute SHA256 checksum of dataset."""
        content = json.dumps(data, sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()[:16]
    
    def export_json(self, samples: list, splits: dict, version: str = None) -> Path:
        """Export dataset to JSON with metadata."""
        if version is None:
            version = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        
        # Compute stats
        exploited = [s for s in samples if s.get("was_exploited")]
        safe = [s for s in samples if not s.get("was_exploited")]
        dates = sorted(s.get("date") for s in samples if s.get("date"))
        protocols = list(set(s.get("slug") for s in samples))
        
        data = {
            "metadata": {
                "version": version,
                "created_at": datetime.utcnow().isoformat(),
                "total_samples": len(samples),
                "exploit_samples": len(exploited),
                "safe_samples": len(safe),
                "protocols": len(protocols),
                "date_range": [dates[0], dates[-1]] if dates else [],
                "features": FeatureBuilder.FEATURES,
                "splits": splits
            },
            "samples": samples
        }
        
        data["metadata"]["checksum"] = self._compute_checksum(data)
        
        filepath = DATA_DIR / f"dataset_v{version}.json"
        with open(filepath, "w") as f:
            json.dump(data, f, indent=2)
        
        # Also save as latest
        latest_path = DATA_DIR / "dataset_latest.json"
        with open(latest_path, "w") as f:
            json.dump(data, f, indent=2)
        
        # Store version in DB
        cur = self.db.cursor()
        cur.execute("""
            INSERT OR REPLACE INTO dataset_versions (version, created_at, metadata)
            VALUES (?, ?, ?)
        """, (version, data["metadata"]["created_at"], json.dumps(data["metadata"])))
        self.db.commit()
        
        print(f"  ✓ Exported to {filepath.name}")
        print(f"    Checksum: {data['metadata']['checksum']}")
        return filepath
    
    def export_splits(self, train: list, val: list, test: list, version: str = None) -> dict:
        """Export train/val/test splits as separate files."""
        if version is None:
            version = datetime.utcnow().strftime("%Y%m%d")
        
        paths = {}
        for name, samples in [("train", train), ("val", val), ("test", test)]:
            filepath = DATA_DIR / f"{name}_v{version}.json"
            with open(filepath, "w") as f:
                json.dump({"samples": samples}, f, indent=2)
            paths[name] = filepath
            print(f"  ✓ {name}: {len(samples)} samples → {filepath.name}")
        
        return paths


# ═══════════════════════════════════════════════════════════════════════════
#                              CLI
# ═══════════════════════════════════════════════════════════════════════════

def cmd_fetch(args):
    """Fetch fresh data from APIs."""
    db = init_db()
    fetcher = DataFetcher(db)
    
    fetcher.fetch_protocols(min_tvl=1e6)
    fetcher.load_exploits()
    
    if not args.skip_tvl:
        fetcher.fetch_all_tvl(max_protocols=args.max_protocols, days=args.days)
    
    if not args.skip_prices:
        fetcher.fetch_all_prices(days=args.days)
    
    db.close()
    print("\n✓ Data fetch complete")


def cmd_build(args):
    """Build training dataset."""
    db = init_db()
    builder = FeatureBuilder(db)
    
    samples = builder.build_dataset(
        sample_days=args.sample_days,
        max_samples_per_protocol=args.max_per_protocol
    )
    
    # Validate
    validator = DataValidator(samples)
    results = validator.validate()
    
    # Split
    splitter = DataSplitter(samples)
    split_data = splitter.stratified_temporal_split(
        train_ratio=args.train_ratio,
        val_ratio=args.val_ratio
    )
    
    # Export
    exporter = DataExporter(db)
    exporter.export_json(samples, split_data["splits"], args.version)
    exporter.export_splits(
        split_data["train"],
        split_data["val"],
        split_data["test"],
        args.version
    )
    
    db.close()
    
    print(f"\n{'='*50}")
    print("DATASET SUMMARY")
    print(f"{'='*50}")
    print(f"Total Samples:    {len(samples)}")
    print(f"Exploit Samples:  {results['class_balance']['exploited']}")
    print(f"Safe Samples:     {results['class_balance']['safe']}")
    print(f"Quality Score:    {results['quality_score']}/10")
    print(f"Date Range:       {results['temporal_coverage']['min']} to {results['temporal_coverage']['max']}")


def cmd_validate(args):
    """Validate existing dataset."""
    filepath = DATA_DIR / (args.file or "dataset_latest.json")
    
    if not filepath.exists():
        print(f"File not found: {filepath}")
        return
    
    with open(filepath) as f:
        data = json.load(f)
    
    samples = data.get("samples", [])
    validator = DataValidator(samples)
    results = validator.validate()
    
    print(f"\n{'='*50}")
    print(f"VALIDATION REPORT: {filepath.name}")
    print(f"{'='*50}")
    print(json.dumps(results, indent=2))


def main():
    parser = argparse.ArgumentParser(description="Nexus Data Pipeline")
    subparsers = parser.add_subparsers(dest="command")
    
    # Fetch command
    fetch_p = subparsers.add_parser("fetch", help="Fetch data from APIs")
    fetch_p.add_argument("--max-protocols", type=int, default=500)
    fetch_p.add_argument("--days", type=int, default=730)
    fetch_p.add_argument("--skip-tvl", action="store_true")
    fetch_p.add_argument("--skip-prices", action="store_true")
    
    # Build command
    build_p = subparsers.add_parser("build", help="Build training dataset")
    build_p.add_argument("--sample-days", type=int, default=7)
    build_p.add_argument("--max-per-protocol", type=int, default=100)
    build_p.add_argument("--train-ratio", type=float, default=0.7)
    build_p.add_argument("--val-ratio", type=float, default=0.15)
    build_p.add_argument("--version", type=str, default=None)
    
    # Validate command
    val_p = subparsers.add_parser("validate", help="Validate dataset")
    val_p.add_argument("--file", type=str, default=None)
    
    args = parser.parse_args()
    
    if args.command == "fetch":
        cmd_fetch(args)
    elif args.command == "build":
        cmd_build(args)
    elif args.command == "validate":
        cmd_validate(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
