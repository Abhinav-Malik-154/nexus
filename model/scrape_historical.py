#!/usr/bin/env python3
"""
Nexus Historical Data Scraper

Collects historical data from FREE sources to build pre-exploit training samples.

Data Sources:
1. DeFiLlama - Historical TVL (FREE, no API key)
2. CoinGecko - Price history (FREE tier - 30 calls/min)
3. Rekt News - Exploit details (scraping)
4. DefiLlama Hacks - Exploit database (FREE)

Usage:
    python scrape_historical.py                    # Scrape all data
    python scrape_historical.py --exploits-only    # Just exploits
    python scrape_historical.py --protocol lido    # Specific protocol
"""

import json
import time
import argparse
import requests
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, asdict
import re

# ═══════════════════════════════════════════════════════════════════════════
#                              CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════

DATA_DIR = Path(__file__).parent.parent / "data"
CACHE_DIR = DATA_DIR / "cache"

# Rate limiting
DEFILLAMA_DELAY = 0.3   # seconds between requests
COINGECKO_DELAY = 2.5   # 30 calls/min free tier

# DeFiLlama endpoints (FREE, no API key)
LLAMA_PROTOCOLS = "https://api.llama.fi/protocols"
LLAMA_PROTOCOL = "https://api.llama.fi/protocol/{slug}"
LLAMA_TVL_HISTORY = "https://api.llama.fi/v2/historicalChainTvl"
LLAMA_HACKS = "https://api.llama.fi/hacks"

# CoinGecko endpoints (FREE tier)
GECKO_COIN_LIST = "https://api.coingecko.com/api/v3/coins/list"
GECKO_MARKET_CHART = "https://api.coingecko.com/api/v3/coins/{id}/market_chart"

# Headers
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; NexusResearch/1.0)",
    "Accept": "application/json",
}


@dataclass
class ProtocolSnapshot:
    """Snapshot of protocol state at a point in time."""
    slug: str
    name: str
    date: str
    tvl: float
    tvl_change_1d: float
    tvl_change_7d: float
    tvl_change_30d: float
    price: Optional[float]
    price_change_24h: Optional[float]
    price_change_7d: Optional[float]
    category: str
    chains: list[str]

    # Risk indicators
    days_before_exploit: Optional[int] = None
    was_exploited: bool = False
    exploit_type: Optional[str] = None
    exploit_loss: Optional[float] = None


@dataclass
class ExploitRecord:
    """Record of a DeFi exploit."""
    protocol: str
    slug: str
    date: str
    loss_usd: float
    type: str
    chain: str
    description: str
    tx_hash: Optional[str]
    technique: str


# ═══════════════════════════════════════════════════════════════════════════
#                           DEFILLAMA SCRAPER
# ═══════════════════════════════════════════════════════════════════════════


class DefiLlamaScraper:
    """Scraper for DeFiLlama data (100% FREE)."""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        self.protocol_cache = {}

    def fetch_all_protocols(self) -> list[dict]:
        """Fetch list of all protocols."""
        print("Fetching protocol list from DeFiLlama...")

        try:
            resp = self.session.get(LLAMA_PROTOCOLS, timeout=30)
            resp.raise_for_status()
            protocols = resp.json()
            print(f"  Found {len(protocols)} protocols")
            return protocols
        except Exception as e:
            print(f"  Error: {e}")
            return []

    def fetch_protocol_history(self, slug: str, days: int = 365) -> list[dict]:
        """Fetch TVL history for a protocol."""
        try:
            url = LLAMA_PROTOCOL.format(slug=slug)
            resp = self.session.get(url, timeout=30)
            resp.raise_for_status()
            data = resp.json()

            tvl_history = data.get("tvl", [])

            # Filter to last N days
            cutoff = (datetime.now() - timedelta(days=days)).timestamp()
            history = [
                {
                    "date": datetime.fromtimestamp(h["date"]).strftime("%Y-%m-%d"),
                    "timestamp": h["date"],
                    "tvl": h.get("totalLiquidityUSD", 0),
                }
                for h in tvl_history
                if h["date"] > cutoff
            ]

            time.sleep(DEFILLAMA_DELAY)
            return history

        except Exception as e:
            print(f"  Error fetching {slug}: {e}")
            return []

    def fetch_hacks_database(self) -> list[dict]:
        """Fetch DeFiLlama's hacks database (FREE!)."""
        print("Fetching DeFiLlama hacks database...")

        try:
            resp = self.session.get(LLAMA_HACKS, timeout=30)
            resp.raise_for_status()
            hacks = resp.json()
            print(f"  Found {len(hacks)} hacks in database")
            return hacks
        except Exception as e:
            print(f"  Error: {e}")
            return []

    def build_protocol_snapshots(
        self,
        slug: str,
        exploit_date: Optional[str] = None,
        days_before: int = 30,
    ) -> list[ProtocolSnapshot]:
        """
        Build daily snapshots of a protocol.
        If exploit_date provided, labels data with days_before_exploit.
        """
        history = self.fetch_protocol_history(slug, days=365)

        if not history:
            return []

        # Get protocol metadata
        all_protocols = self.fetch_all_protocols()
        protocol_meta = next(
            (p for p in all_protocols if p.get("slug") == slug),
            {"name": slug, "category": "Unknown", "chains": []}
        )

        snapshots = []

        for i, day in enumerate(history):
            tvl = day["tvl"]

            # Calculate changes
            tvl_1d_ago = history[i-1]["tvl"] if i > 0 else tvl
            tvl_7d_ago = history[i-7]["tvl"] if i >= 7 else tvl
            tvl_30d_ago = history[i-30]["tvl"] if i >= 30 else tvl

            change_1d = ((tvl - tvl_1d_ago) / tvl_1d_ago * 100) if tvl_1d_ago > 0 else 0
            change_7d = ((tvl - tvl_7d_ago) / tvl_7d_ago * 100) if tvl_7d_ago > 0 else 0
            change_30d = ((tvl - tvl_30d_ago) / tvl_30d_ago * 100) if tvl_30d_ago > 0 else 0

            # Calculate days before exploit
            days_before_exploit = None
            if exploit_date:
                try:
                    exploit_dt = datetime.strptime(exploit_date, "%Y-%m-%d")
                    snapshot_dt = datetime.strptime(day["date"], "%Y-%m-%d")
                    delta = (exploit_dt - snapshot_dt).days
                    if delta >= 0:
                        days_before_exploit = delta
                except:
                    pass

            snapshot = ProtocolSnapshot(
                slug=slug,
                name=protocol_meta.get("name", slug),
                date=day["date"],
                tvl=tvl,
                tvl_change_1d=round(change_1d, 2),
                tvl_change_7d=round(change_7d, 2),
                tvl_change_30d=round(change_30d, 2),
                price=None,  # Will be filled by CoinGecko
                price_change_24h=None,
                price_change_7d=None,
                category=protocol_meta.get("category", "Unknown"),
                chains=protocol_meta.get("chains", []),
                days_before_exploit=days_before_exploit,
            )

            snapshots.append(snapshot)

        return snapshots


# ═══════════════════════════════════════════════════════════════════════════
#                           COINGECKO SCRAPER
# ═══════════════════════════════════════════════════════════════════════════


class CoinGeckoScraper:
    """Scraper for CoinGecko price data (FREE tier: 30 calls/min)."""

    # Protocol slug to CoinGecko ID mapping
    SLUG_TO_GECKO = {
        "lido": "lido-dao",
        "aave": "aave",
        "aave-v3": "aave",
        "uniswap": "uniswap",
        "maker": "maker",
        "compound": "compound-governance-token",
        "compound-v3": "compound-governance-token",
        "curve-dex": "curve-dao-token",
        "convex-finance": "convex-finance",
        "yearn-finance": "yearn-finance",
        "synthetix": "havven",
        "balancer-v2": "balancer",
        "frax": "frax-share",
        "euler": "euler",
        "terra": "terra-luna",
        "anchor": "anchor-protocol",
        "ftx": "ftx-token",
    }

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(HEADERS)

    def fetch_price_history(
        self,
        slug: str,
        days: int = 365,
    ) -> list[dict]:
        """Fetch price history for a protocol's token."""

        gecko_id = self.SLUG_TO_GECKO.get(slug)
        if not gecko_id:
            return []

        try:
            url = GECKO_MARKET_CHART.format(id=gecko_id)
            params = {"vs_currency": "usd", "days": days, "interval": "daily"}

            resp = self.session.get(url, params=params, timeout=30)
            resp.raise_for_status()
            data = resp.json()

            prices = data.get("prices", [])
            history = []

            for i, (timestamp, price) in enumerate(prices):
                date = datetime.fromtimestamp(timestamp / 1000).strftime("%Y-%m-%d")

                # Calculate changes
                price_1d_ago = prices[i-1][1] if i > 0 else price
                price_7d_ago = prices[i-7][1] if i >= 7 else price

                change_24h = ((price - price_1d_ago) / price_1d_ago * 100) if price_1d_ago > 0 else 0
                change_7d = ((price - price_7d_ago) / price_7d_ago * 100) if price_7d_ago > 0 else 0

                history.append({
                    "date": date,
                    "price": price,
                    "price_change_24h": round(change_24h, 2),
                    "price_change_7d": round(change_7d, 2),
                })

            time.sleep(COINGECKO_DELAY)
            return history

        except Exception as e:
            print(f"  CoinGecko error for {slug}: {e}")
            return []


# ═══════════════════════════════════════════════════════════════════════════
#                        TRAINING DATA BUILDER
# ═══════════════════════════════════════════════════════════════════════════


class TrainingDataBuilder:
    """Builds training dataset from scraped historical data."""

    def __init__(self):
        self.llama = DefiLlamaScraper()
        self.gecko = CoinGeckoScraper()

    def fetch_defillama_hacks(self) -> list[ExploitRecord]:
        """Fetch and parse DeFiLlama hacks database."""
        hacks = self.llama.fetch_hacks_database()

        records = []
        for hack in hacks:
            try:
                # Parse date
                date_str = hack.get("date", "")
                if isinstance(date_str, int):
                    date = datetime.fromtimestamp(date_str).strftime("%Y-%m-%d")
                else:
                    date = date_str[:10] if date_str else "unknown"

                record = ExploitRecord(
                    protocol=hack.get("name", "Unknown"),
                    slug=hack.get("name", "").lower().replace(" ", "-"),
                    date=date,
                    loss_usd=(hack.get("amount") or 0) * 1_000_000,  # Amount in millions
                    type=hack.get("technique", "unknown"),
                    chain=hack.get("chain", "Unknown"),
                    description=hack.get("description", ""),
                    tx_hash=hack.get("tx", None),
                    technique=hack.get("technique", "unknown"),
                )
                records.append(record)
            except Exception as e:
                print(f"  Error parsing hack: {e}")
                continue

        return records

    def build_pre_exploit_samples(
        self,
        exploits: list[ExploitRecord],
        days_before: int = 30,
    ) -> list[dict]:
        """
        Build training samples from days BEFORE each exploit.

        This is the key to a 9+ model:
        - We need data showing what protocols looked like BEFORE they failed
        - Then label: days_before_exploit <= 7 = high risk
        """

        samples = []

        for exploit in exploits:
            print(f"  Building samples for {exploit.protocol} ({exploit.date})...")

            # Get historical snapshots
            snapshots = self.llama.build_protocol_snapshots(
                slug=exploit.slug,
                exploit_date=exploit.date,
                days_before=days_before,
            )

            if not snapshots:
                # Try alternative slug formats
                alt_slugs = [
                    exploit.slug,
                    exploit.protocol.lower().replace(" ", "-"),
                    exploit.protocol.lower().replace(" ", ""),
                ]

                for alt_slug in alt_slugs:
                    snapshots = self.llama.build_protocol_snapshots(
                        slug=alt_slug,
                        exploit_date=exploit.date,
                        days_before=days_before,
                    )
                    if snapshots:
                        break

            if not snapshots:
                print(f"    No historical data found")
                continue

            # Get price history
            price_history = self.gecko.fetch_price_history(exploit.slug)
            price_by_date = {p["date"]: p for p in price_history}

            # Merge price data into snapshots
            for snapshot in snapshots:
                price_data = price_by_date.get(snapshot.date, {})
                snapshot.price = price_data.get("price")
                snapshot.price_change_24h = price_data.get("price_change_24h")
                snapshot.price_change_7d = price_data.get("price_change_7d")
                snapshot.was_exploited = True
                snapshot.exploit_type = exploit.type
                snapshot.exploit_loss = exploit.loss_usd

                samples.append(asdict(snapshot))

            print(f"    Added {len(snapshots)} samples")

        return samples

    def build_safe_protocol_samples(
        self,
        safe_protocols: list[str],
        days: int = 90,
    ) -> list[dict]:
        """Build samples for protocols that were NOT exploited (negative samples)."""

        samples = []

        for slug in safe_protocols:
            print(f"  Building safe samples for {slug}...")

            snapshots = self.llama.build_protocol_snapshots(slug, days_before=days)

            if not snapshots:
                continue

            # Get price history
            price_history = self.gecko.fetch_price_history(slug)
            price_by_date = {p["date"]: p for p in price_history}

            for snapshot in snapshots:
                price_data = price_by_date.get(snapshot.date, {})
                snapshot.price = price_data.get("price")
                snapshot.price_change_24h = price_data.get("price_change_24h")
                snapshot.price_change_7d = price_data.get("price_change_7d")
                snapshot.was_exploited = False

                samples.append(asdict(snapshot))

            print(f"    Added {len(snapshots)} samples")

        return samples

    def build_full_dataset(self) -> dict:
        """Build complete training dataset."""

        print("=" * 60)
        print("NEXUS — Building Historical Training Dataset")
        print("=" * 60)
        print()

        # 1. Fetch exploits from DeFiLlama
        print("[1/4] Fetching exploit database...")
        exploits = self.fetch_defillama_hacks()
        print(f"  Found {len(exploits)} exploits")

        # Filter to significant exploits (>$1M)
        major_exploits = [e for e in exploits if e.loss_usd >= 1_000_000]
        print(f"  Major exploits (>$1M): {len(major_exploits)}")

        # 2. Build pre-exploit samples
        print()
        print("[2/4] Building pre-exploit samples...")
        exploit_samples = self.build_pre_exploit_samples(major_exploits[:50])  # Top 50
        print(f"  Total exploit samples: {len(exploit_samples)}")

        # 3. Build safe protocol samples
        print()
        print("[3/4] Building safe protocol samples...")
        safe_protocols = [
            "lido", "aave-v3", "uniswap-v3", "maker", "compound-v3",
            "rocket-pool", "coinbase-wrapped-staked-eth", "binance-staked-eth",
        ]
        safe_samples = self.build_safe_protocol_samples(safe_protocols)
        print(f"  Total safe samples: {len(safe_samples)}")

        # 4. Combine and save
        print()
        print("[4/4] Saving dataset...")

        all_samples = exploit_samples + safe_samples

        dataset = {
            "metadata": {
                "created_at": datetime.now().isoformat(),
                "total_samples": len(all_samples),
                "exploit_samples": len(exploit_samples),
                "safe_samples": len(safe_samples),
                "exploits_analyzed": len(major_exploits),
            },
            "samples": all_samples,
            "exploits": [asdict(e) for e in major_exploits],
        }

        DATA_DIR.mkdir(exist_ok=True)

        with open(DATA_DIR / "historical_training_data.json", "w") as f:
            json.dump(dataset, f, indent=2, default=str)

        print(f"  Saved: data/historical_training_data.json")
        print()

        # Summary
        print("=" * 60)
        print("DATASET SUMMARY")
        print("=" * 60)
        print(f"Total samples:     {len(all_samples)}")
        print(f"Exploit samples:   {len(exploit_samples)}")
        print(f"Safe samples:      {len(safe_samples)}")
        print(f"Exploits analyzed: {len(major_exploits)}")

        # Sample distribution
        if exploit_samples:
            high_risk = sum(1 for s in exploit_samples
                          if s.get("days_before_exploit") is not None
                          and s["days_before_exploit"] <= 7)
            print(f"High-risk samples (<=7 days before): {high_risk}")

        return dataset


# ═══════════════════════════════════════════════════════════════════════════
#                                  MAIN
# ═══════════════════════════════════════════════════════════════════════════


def main():
    parser = argparse.ArgumentParser(description="Nexus Historical Data Scraper")
    parser.add_argument("--exploits-only", action="store_true",
                       help="Only fetch exploit data")
    parser.add_argument("--protocol", type=str,
                       help="Fetch data for specific protocol")
    args = parser.parse_args()

    builder = TrainingDataBuilder()

    if args.exploits_only:
        exploits = builder.fetch_defillama_hacks()

        DATA_DIR.mkdir(exist_ok=True)
        with open(DATA_DIR / "defillama_hacks.json", "w") as f:
            json.dump([asdict(e) for e in exploits], f, indent=2)

        print(f"Saved {len(exploits)} exploits to data/defillama_hacks.json")

    elif args.protocol:
        llama = DefiLlamaScraper()
        snapshots = llama.build_protocol_snapshots(args.protocol)

        if snapshots:
            DATA_DIR.mkdir(exist_ok=True)
            with open(DATA_DIR / f"{args.protocol}_history.json", "w") as f:
                json.dump([asdict(s) for s in snapshots], f, indent=2)
            print(f"Saved {len(snapshots)} snapshots")
        else:
            print("No data found")

    else:
        builder.build_full_dataset()


if __name__ == "__main__":
    main()
