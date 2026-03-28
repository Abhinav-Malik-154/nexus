#!/usr/bin/env python3
"""
Bootstrap Nexus Database from Existing Data

Imports existing JSON files into the new SQLite-backed pipeline.

Usage:
    python bootstrap_db.py
"""

import json
import sqlite3
from pathlib import Path
from datetime import datetime

DATA_DIR = Path(__file__).parent
DB_PATH = DATA_DIR / "nexus.db"


def init_db():
    """Initialize database schema."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    cur.executescript("""
        CREATE TABLE IF NOT EXISTS protocols (
            slug TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            category TEXT,
            chains TEXT,
            gecko_id TEXT,
            symbol TEXT,
            url TEXT,
            twitter TEXT,
            audit TEXT,
            created_at TEXT,
            updated_at TEXT
        );
        
        CREATE TABLE IF NOT EXISTS tvl_snapshots (
            id INTEGER PRIMARY KEY,
            slug TEXT NOT NULL,
            date TEXT NOT NULL,
            tvl REAL NOT NULL,
            chain_tvls TEXT,
            UNIQUE(slug, date)
        );
        
        CREATE TABLE IF NOT EXISTS price_snapshots (
            id INTEGER PRIMARY KEY,
            gecko_id TEXT NOT NULL,
            date TEXT NOT NULL,
            price REAL,
            mcap REAL,
            volume REAL,
            UNIQUE(gecko_id, date)
        );
        
        CREATE TABLE IF NOT EXISTS exploits (
            id INTEGER PRIMARY KEY,
            slug TEXT NOT NULL,
            date TEXT NOT NULL,
            loss_usd REAL,
            type TEXT,
            description TEXT,
            source TEXT,
            UNIQUE(slug, date)
        );
        
        CREATE TABLE IF NOT EXISTS samples (
            id INTEGER PRIMARY KEY,
            slug TEXT NOT NULL,
            date TEXT NOT NULL,
            features TEXT NOT NULL,
            label REAL NOT NULL,
            split TEXT,
            UNIQUE(slug, date)
        );
        
        CREATE TABLE IF NOT EXISTS dataset_versions (
            version TEXT PRIMARY KEY,
            created_at TEXT,
            metadata TEXT
        );
        
        CREATE INDEX IF NOT EXISTS idx_tvl_slug_date ON tvl_snapshots(slug, date);
        CREATE INDEX IF NOT EXISTS idx_exploits_date ON exploits(date);
    """)
    
    conn.commit()
    return conn


def import_exploits(conn: sqlite3.Connection):
    """Import exploit data from JSON files."""
    print("Importing exploits...")
    
    cur = conn.cursor()
    count = 0
    
    # Import from defillama_hacks.json
    hacks_file = DATA_DIR / "defillama_hacks.json"
    if hacks_file.exists():
        with open(hacks_file) as f:
            data = json.load(f)
        
        hacks = data if isinstance(data, list) else data.get("hacks", [])
        
        for h in hacks:
            slug = h.get("project", h.get("name", "")).lower().replace(" ", "-")
            date = h.get("date", "")
            
            # Parse date
            if isinstance(date, (int, float)):
                date = datetime.fromtimestamp(date).strftime("%Y-%m-%d")
            elif "T" in str(date):
                date = date.split("T")[0]
            
            if not slug or not date:
                continue
            
            loss = h.get("amount", h.get("funds_lost", 0)) or 0
            if isinstance(loss, str):
                loss = float(loss.replace(",", "").replace("$", "").replace("M", "e6").replace("B", "e9"))
            
            exp_type = h.get("classification", h.get("technique", "Unknown"))
            
            try:
                cur.execute("""
                    INSERT OR REPLACE INTO exploits (slug, date, loss_usd, type, description, source)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (slug, date, loss, exp_type, h.get("description", ""), "defillama"))
                count += 1
            except Exception as e:
                continue
    
    # Import from historical_exploits.json
    hist_file = DATA_DIR / "historical_exploits.json"
    if hist_file.exists():
        with open(hist_file) as f:
            data = json.load(f)
        
        exploits = data if isinstance(data, list) else data.get("exploits", [])
        
        for e in exploits:
            slug = e.get("protocol", e.get("slug", "")).lower().replace(" ", "-")
            date = e.get("date", "")
            
            if not slug or not date:
                continue
            
            try:
                cur.execute("""
                    INSERT OR IGNORE INTO exploits (slug, date, loss_usd, type, description, source)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    slug, date, 
                    e.get("loss", e.get("amount", 0)),
                    e.get("type", "Unknown"),
                    e.get("description", ""),
                    "historical"
                ))
                count += 1
            except:
                continue
    
    # Import from exploit_labels files
    for year in ["2022", "2023", "2024"]:
        labels_file = DATA_DIR / f"exploit_labels_{year}.json"
        if labels_file.exists():
            with open(labels_file) as f:
                data = json.load(f)
            
            labels = data.get("labels", data) if isinstance(data, dict) else data
            
            for slug, info in labels.items():
                if not isinstance(info, dict):
                    continue
                    
                date = info.get("date", f"{year}-06-15")  # Default to mid-year
                
                try:
                    cur.execute("""
                        INSERT OR IGNORE INTO exploits (slug, date, loss_usd, type, description, source)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (
                        slug, date,
                        info.get("loss_usd", info.get("loss", 0)),
                        info.get("type", "Unknown"),
                        "",
                        f"labels_{year}"
                    ))
                    count += 1
                except:
                    continue
    
    conn.commit()
    print(f"  ✓ Imported {count} exploit records")
    return count


def import_protocols(conn: sqlite3.Connection):
    """Import protocol data from real_protocols.json."""
    print("Importing protocols...")
    
    cur = conn.cursor()
    count = 0
    now = datetime.utcnow().isoformat()
    
    # Import from real_protocols.json
    protos_file = DATA_DIR / "real_protocols.json"
    if protos_file.exists():
        with open(protos_file) as f:
            data = json.load(f)
        
        protocols = data if isinstance(data, list) else data.get("protocols", [])
        
        for p in protocols:
            slug = p.get("slug", p.get("id", "")).lower()
            if not slug:
                continue
            
            try:
                cur.execute("""
                    INSERT OR REPLACE INTO protocols 
                    (slug, name, category, chains, gecko_id, symbol, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    slug,
                    p.get("name", slug),
                    p.get("category", "Unknown"),
                    json.dumps(p.get("chains", [])),
                    p.get("gecko_id"),
                    p.get("symbol"),
                    now, now
                ))
                count += 1
            except Exception as e:
                continue
    
    # Also extract from training datasets
    for ds_file in ["training_dataset.json", "training_dataset_10x.json"]:
        filepath = DATA_DIR / ds_file
        if filepath.exists():
            with open(filepath) as f:
                data = json.load(f)
            
            samples = data.get("samples", data) if isinstance(data, dict) else data
            
            for s in samples:
                slug = s.get("slug", "").lower()
                if not slug:
                    continue
                
                try:
                    cur.execute("""
                        INSERT OR IGNORE INTO protocols (slug, name, category, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?)
                    """, (
                        slug,
                        s.get("protocol", slug),
                        s.get("category", "Unknown"),
                        now, now
                    ))
                    count += 1
                except:
                    continue
    
    conn.commit()
    print(f"  ✓ Imported {count} protocol records")
    return count


def import_training_samples(conn: sqlite3.Connection):
    """Import samples from training datasets."""
    print("Importing training samples...")
    
    cur = conn.cursor()
    count = 0
    
    for ds_file in ["training_dataset_10x.json", "training_dataset.json"]:
        filepath = DATA_DIR / ds_file
        if not filepath.exists():
            continue
        
        print(f"  Processing {ds_file}...")
        
        with open(filepath) as f:
            data = json.load(f)
        
        samples = data.get("samples", []) if isinstance(data, dict) else data
        
        for s in samples:
            slug = s.get("slug", "").lower()
            date = s.get("date", "")
            
            if not slug or not date:
                continue
            
            # Store TVL snapshot
            tvl = s.get("tvl", 0)
            if tvl > 0:
                try:
                    cur.execute("""
                        INSERT OR IGNORE INTO tvl_snapshots (slug, date, tvl)
                        VALUES (?, ?, ?)
                    """, (slug, date, tvl))
                except:
                    pass
            
            # Store features
            features = {
                "tvl_log": s.get("tvl_log", 0),
                "tvl_change_1d": s.get("tvl_change_1d", 0),
                "tvl_change_7d": s.get("tvl_change_7d", 0),
                "tvl_change_30d": s.get("tvl_change_30d", 0),
                "tvl_volatility": s.get("tvl_volatility", 0),
                "price_change_1d": s.get("price_change_1d", 0),
                "price_change_7d": s.get("price_change_7d", 0),
                "price_volatility": s.get("price_volatility", 0),
                "price_crash_7d": s.get("price_crash", s.get("price_crash_7d", 0)),
                "category_risk": s.get("category_risk", 0.5),
                "chain_count": s.get("chain_count", 1),
                "mcap_to_tvl": s.get("mcap_to_tvl", 0),
            }
            
            label = 1.0 if s.get("was_exploited", False) else 0.0
            
            try:
                cur.execute("""
                    INSERT OR REPLACE INTO samples (slug, date, features, label, split)
                    VALUES (?, ?, ?, ?, ?)
                """, (slug, date, json.dumps(features), label, None))
                count += 1
            except Exception as e:
                continue
        
        break  # Only process first available file
    
    conn.commit()
    print(f"  ✓ Imported {count} training samples")
    return count


def print_stats(conn: sqlite3.Connection):
    """Print database statistics."""
    cur = conn.cursor()
    
    print("\n" + "="*50)
    print("DATABASE STATISTICS")
    print("="*50)
    
    cur.execute("SELECT COUNT(*) FROM protocols")
    print(f"Protocols:     {cur.fetchone()[0]}")
    
    cur.execute("SELECT COUNT(*) FROM exploits")
    print(f"Exploits:      {cur.fetchone()[0]}")
    
    cur.execute("SELECT COUNT(*) FROM tvl_snapshots")
    print(f"TVL Snapshots: {cur.fetchone()[0]}")
    
    cur.execute("SELECT COUNT(*) FROM samples")
    print(f"Samples:       {cur.fetchone()[0]}")
    
    cur.execute("SELECT COUNT(*) FROM samples WHERE label = 1")
    print(f"  Positive:    {cur.fetchone()[0]}")
    
    cur.execute("SELECT COUNT(*) FROM samples WHERE label = 0")
    print(f"  Negative:    {cur.fetchone()[0]}")
    
    cur.execute("SELECT MIN(date), MAX(date) FROM samples")
    dates = cur.fetchone()
    print(f"Date Range:    {dates[0]} to {dates[1]}")


def main():
    print("Bootstrapping Nexus Database...")
    print(f"Database: {DB_PATH}")
    print()
    
    conn = init_db()
    
    import_protocols(conn)
    import_exploits(conn)
    import_training_samples(conn)
    
    print_stats(conn)
    
    conn.close()
    print("\n✓ Bootstrap complete")


if __name__ == "__main__":
    main()
