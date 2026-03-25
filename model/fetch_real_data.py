#!/usr/bin/env python3
"""
Nexus Real Data Pipeline

Fetches live protocol data from DeFiLlama API.
This replaces synthetic data with real TVL, changes, and protocol relationships.

Usage:
    python fetch_real_data.py              # Fetch current data
    python fetch_real_data.py --historical # Fetch with 30-day history
"""

import json
import time
import argparse
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
import requests

# ═══════════════════════════════════════════════════════════════════════════
#                              CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════

DATA_DIR = Path(__file__).parent.parent / "data"
DEFILLAMA_BASE = "https://api.llama.fi"

# Top protocols to track (by TVL and risk relevance)
TRACKED_PROTOCOLS = [
    "lido", "aave-v3", "eigenlayer", "ether.fi-stake", "ethena",
    "uniswap", "maker", "pendle", "compound-v3", "morpho",
    "rocket-pool", "justlend", "venus", "spark", "instadapp",
    "curve-dex", "convex-finance", "yearn-finance", "balancer-v2",
    "gmx", "dydx", "synthetix", "frax", "liquity", "benqi-lending",
    "maple", "goldfinch", "truefi", "clearpool", "centrifuge",
    "euler", "radiant-v2", "silo-finance", "gearbox", "notional",
    "iron-bank", "cream-finance", "inverse-finance", "anchor",
    "terra", "celsius", "voyager", "blockfi", "ftx"
]

# Protocol categories for risk assessment
CATEGORY_RISK = {
    "Lending": 0.7,
    "CDP": 0.8,
    "Dexes": 0.4,
    "Liquid Staking": 0.5,
    "Bridge": 0.9,
    "Yield": 0.6,
    "Derivatives": 0.7,
    "Yield Aggregator": 0.6,
    "RWA": 0.5,
    "Algo-Stables": 0.95,
    "CEX": 0.6,
}

# Known protocol dependencies (from on-chain analysis)
PROTOCOL_DEPENDENCIES = {
    "aave-v3": ["chainlink", "lido", "maker"],
    "morpho": ["aave-v3", "compound-v3"],
    "compound-v3": ["chainlink"],
    "maker": ["chainlink", "uniswap"],
    "ethena": ["lido", "aave-v3", "maker"],
    "eigenlayer": ["lido", "rocket-pool"],
    "ether.fi-stake": ["eigenlayer", "lido"],
    "pendle": ["lido", "aave-v3", "ethena"],
    "curve-dex": ["maker", "frax", "lido"],
    "convex-finance": ["curve-dex"],
    "yearn-finance": ["curve-dex", "aave-v3", "compound-v3"],
    "frax": ["curve-dex", "aave-v3"],
    "euler": ["chainlink", "uniswap"],
    "radiant-v2": ["chainlink", "layerzero"],
    "gearbox": ["aave-v3", "curve-dex", "uniswap"],
    "anchor": ["terra"],
    "terra": [],
}


# ═══════════════════════════════════════════════════════════════════════════
#                              API FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════


def fetch_all_protocols() -> list[dict]:
    """Fetch all protocols from DeFiLlama."""
    print("Fetching protocol list from DeFiLlama...")

    try:
        response = requests.get(f"{DEFILLAMA_BASE}/protocols", timeout=30)
        response.raise_for_status()
        protocols = response.json()
        print(f"  Found {len(protocols)} total protocols")
        return protocols
    except requests.RequestException as e:
        print(f"  Error fetching protocols: {e}")
        return []


def fetch_protocol_tvl_history(slug: str, days: int = 30) -> list[dict]:
    """Fetch TVL history for a specific protocol."""
    try:
        response = requests.get(f"{DEFILLAMA_BASE}/protocol/{slug}", timeout=30)
        response.raise_for_status()
        data = response.json()

        # Extract TVL history
        tvl_history = data.get("tvl", [])

        # Filter to last N days
        cutoff = datetime.now() - timedelta(days=days)
        cutoff_ts = cutoff.timestamp()

        recent = [
            {"date": h["date"], "tvl": h["totalLiquidityUSD"]}
            for h in tvl_history
            if h["date"] > cutoff_ts
        ]

        return recent
    except requests.RequestException:
        return []


def calculate_tvl_changes(tvl_history: list[dict]) -> dict:
    """Calculate TVL changes from history."""
    if len(tvl_history) < 2:
        return {"change_1d": 0, "change_7d": 0, "change_30d": 0}

    current_tvl = tvl_history[-1]["tvl"]

    # 1-day change
    if len(tvl_history) >= 2:
        day_ago_tvl = tvl_history[-2]["tvl"]
        change_1d = ((current_tvl - day_ago_tvl) / day_ago_tvl * 100) if day_ago_tvl > 0 else 0
    else:
        change_1d = 0

    # 7-day change
    if len(tvl_history) >= 7:
        week_ago_tvl = tvl_history[-7]["tvl"]
        change_7d = ((current_tvl - week_ago_tvl) / week_ago_tvl * 100) if week_ago_tvl > 0 else 0
    else:
        change_7d = 0

    # 30-day change
    if len(tvl_history) >= 30:
        month_ago_tvl = tvl_history[0]["tvl"]
        change_30d = ((current_tvl - month_ago_tvl) / month_ago_tvl * 100) if month_ago_tvl > 0 else 0
    else:
        change_30d = 0

    return {
        "change_1d": round(change_1d, 2),
        "change_7d": round(change_7d, 2),
        "change_30d": round(change_30d, 2),
    }


def fetch_tracked_protocols(with_history: bool = False) -> list[dict]:
    """Fetch data for tracked protocols."""
    all_protocols = fetch_all_protocols()

    if not all_protocols:
        print("Failed to fetch protocols, using cached data if available")
        return []

    # Build slug -> protocol mapping
    slug_map = {p["slug"]: p for p in all_protocols}

    tracked_data = []

    print(f"\nFetching data for {len(TRACKED_PROTOCOLS)} tracked protocols...")

    for i, slug in enumerate(TRACKED_PROTOCOLS):
        if slug not in slug_map:
            print(f"  [{i+1}/{len(TRACKED_PROTOCOLS)}] {slug}: NOT FOUND (may be defunct)")
            # Still add defunct protocols for historical analysis
            tracked_data.append({
                "slug": slug,
                "name": slug.replace("-", " ").title(),
                "tvl": 0,
                "category": "Unknown",
                "change_1d": 0,
                "change_7d": 0,
                "change_30d": 0,
                "chain": "Unknown",
                "status": "defunct",
            })
            continue

        protocol = slug_map[slug]

        # Fetch TVL history if requested
        if with_history:
            print(f"  [{i+1}/{len(TRACKED_PROTOCOLS)}] {slug}: fetching history...")
            tvl_history = fetch_protocol_tvl_history(slug)
            changes = calculate_tvl_changes(tvl_history)
            time.sleep(0.2)  # Rate limiting
        else:
            changes = {
                "change_1d": protocol.get("change_1d", 0) or 0,
                "change_7d": protocol.get("change_7d", 0) or 0,
                "change_30d": 0,
            }
            print(f"  [{i+1}/{len(TRACKED_PROTOCOLS)}] {slug}: ${protocol.get('tvl', 0)/1e9:.2f}B")

        tracked_data.append({
            "slug": slug,
            "name": protocol.get("name", slug),
            "tvl": protocol.get("tvl", 0),
            "category": protocol.get("category", "Unknown"),
            "change_1d": changes["change_1d"],
            "change_7d": changes["change_7d"],
            "change_30d": changes.get("change_30d", 0),
            "chain": protocol.get("chain", "Multi-chain"),
            "status": "active",
        })

    return tracked_data


# ═══════════════════════════════════════════════════════════════════════════
#                           GRAPH CONSTRUCTION
# ═══════════════════════════════════════════════════════════════════════════


def build_risk_graph(protocols: list[dict]) -> dict:
    """Build risk graph with nodes and edges."""

    # Create node list
    nodes = []
    slug_to_idx = {}

    for i, p in enumerate(protocols):
        slug_to_idx[p["slug"]] = i

        # Calculate base risk score
        category_risk = CATEGORY_RISK.get(p["category"], 0.5)

        # TVL risk (smaller = riskier)
        tvl = p["tvl"]
        if tvl > 10_000_000_000:  # >$10B
            tvl_risk = 0.2
        elif tvl > 1_000_000_000:  # >$1B
            tvl_risk = 0.3
        elif tvl > 100_000_000:  # >$100M
            tvl_risk = 0.5
        elif tvl > 10_000_000:  # >$10M
            tvl_risk = 0.7
        else:
            tvl_risk = 0.9

        # Volatility risk (large TVL drops = risky)
        change_1d = p["change_1d"]
        change_7d = p["change_7d"]

        if change_1d < -20 or change_7d < -30:
            volatility_risk = 0.95
        elif change_1d < -10 or change_7d < -20:
            volatility_risk = 0.8
        elif change_1d < -5 or change_7d < -10:
            volatility_risk = 0.6
        elif change_1d < 0:
            volatility_risk = 0.4
        else:
            volatility_risk = 0.2

        # Defunct protocols are maximum risk
        if p["status"] == "defunct":
            base_risk = 1.0
        else:
            base_risk = (category_risk * 0.3 + tvl_risk * 0.3 + volatility_risk * 0.4)

        nodes.append({
            "id": i,
            "slug": p["slug"],
            "name": p["name"],
            "tvl": tvl,
            "category": p["category"],
            "change_1d": change_1d,
            "change_7d": change_7d,
            "base_risk": round(base_risk, 3),
            "status": p["status"],
        })

    # Create edge list from dependencies
    edges = []
    for source_slug, targets in PROTOCOL_DEPENDENCIES.items():
        if source_slug not in slug_to_idx:
            continue
        source_idx = slug_to_idx[source_slug]

        for target_slug in targets:
            if target_slug not in slug_to_idx:
                continue
            target_idx = slug_to_idx[target_slug]

            # Edge weight based on dependency strength
            edges.append({
                "source": source_idx,
                "target": target_idx,
                "weight": 1.0,
            })

    return {
        "nodes": nodes,
        "edges": edges,
        "metadata": {
            "num_nodes": len(nodes),
            "num_edges": len(edges),
            "timestamp": datetime.now().isoformat(),
        }
    }


# ═══════════════════════════════════════════════════════════════════════════
#                                  MAIN
# ═══════════════════════════════════════════════════════════════════════════


def main():
    parser = argparse.ArgumentParser(description="Fetch real DeFi protocol data")
    parser.add_argument("--historical", action="store_true", help="Fetch 30-day history")
    args = parser.parse_args()

    print("=" * 60)
    print("NEXUS — Real Data Pipeline")
    print("=" * 60)
    print()

    # Fetch protocol data
    protocols = fetch_tracked_protocols(with_history=args.historical)

    if not protocols:
        print("No data fetched!")
        return

    # Build risk graph
    print("\nBuilding risk graph...")
    graph = build_risk_graph(protocols)

    # Save raw protocol data
    DATA_DIR.mkdir(exist_ok=True)

    with open(DATA_DIR / "real_protocols.json", "w") as f:
        json.dump(protocols, f, indent=2)
    print(f"Saved: data/real_protocols.json ({len(protocols)} protocols)")

    # Save risk graph
    with open(DATA_DIR / "real_risk_graph.json", "w") as f:
        json.dump(graph, f, indent=2)
    print(f"Saved: data/real_risk_graph.json ({graph['metadata']['num_nodes']} nodes, {graph['metadata']['num_edges']} edges)")

    # Summary
    print()
    print("=" * 60)
    print("DATA SUMMARY")
    print("=" * 60)

    active = [p for p in protocols if p["status"] == "active"]
    defunct = [p for p in protocols if p["status"] == "defunct"]

    print(f"Active protocols:  {len(active)}")
    print(f"Defunct protocols: {len(defunct)}")
    print(f"Total TVL tracked: ${sum(p['tvl'] for p in active) / 1e9:.2f}B")

    # Top risky protocols
    risky = sorted(graph["nodes"], key=lambda x: x["base_risk"], reverse=True)[:5]
    print("\nHighest Base Risk:")
    for p in risky:
        print(f"  {p['name']:<25} {p['base_risk']*100:.0f}% ({p['category']})")

    print()


if __name__ == "__main__":
    main()
