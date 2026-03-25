#!/usr/bin/env python3
"""
Nexus Training Data Generator

Builds proper training data by combining:
1. Our curated exploit database (accurate loss amounts)
2. DeFiLlama historical TVL data (FREE)
3. Pre-exploit snapshots for training

This creates the dataset needed for a 9+ model.
"""

import json
import time
import requests
from datetime import datetime, timedelta
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Optional
import numpy as np

# Import our curated exploit database
from exploit_database import EXPLOITS, WARNING_SIGN_DESCRIPTIONS

DATA_DIR = Path(__file__).parent.parent / "data"

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; NexusResearch/1.0)"}
LLAMA_PROTOCOL = "https://api.llama.fi/protocol/{slug}"
DELAY = 0.5  # Rate limiting


@dataclass
class TrainingSample:
    """Single training sample with features and label."""
    protocol: str
    slug: str
    date: str

    # Features
    tvl: float
    tvl_change_1d: float
    tvl_change_7d: float
    tvl_change_30d: float
    tvl_volatility: float  # std dev of TVL changes
    category_risk: float
    chain_count: int

    # Labels
    days_to_exploit: int  # -1 if never exploited
    risk_label: float     # 0-1, higher = riskier
    was_exploited: bool
    exploit_type: Optional[str] = None
    exploit_loss: Optional[float] = None


# Protocol slug mappings for DeFiLlama
SLUG_MAPPING = {
    "terra": "terra-classic",
    "anchor": "anchor-protocol",
    "euler": "euler",
    "ftx": None,  # CEX, no TVL data
    "celsius": None,  # CeFi
    "voyager": None,  # CeFi
    "blockfi": None,  # CeFi
    "ronin-bridge": "ronin",
    "wormhole": "wormhole",
    "curve-dex": "curve-dex",
    "yearn-finance": "yearn-finance",
    "cream-finance": "cream-finance",
    "beanstalk": "beanstalk",
    "badger-dao": "badger-dao",
    "harvest-finance": "harvest-finance",
}

CATEGORY_RISK = {
    "Lending": 0.7,
    "CDP": 0.8,
    "Dexes": 0.4,
    "Liquid Staking": 0.5,
    "Bridge": 0.9,
    "Yield": 0.6,
    "Derivatives": 0.7,
    "Algo-Stables": 0.95,
    "Services": 0.4,
    "Unknown": 0.5,
}


def fetch_protocol_tvl_history(slug: str) -> list[dict]:
    """Fetch TVL history from DeFiLlama."""
    try:
        resp = requests.get(
            LLAMA_PROTOCOL.format(slug=slug),
            headers=HEADERS,
            timeout=30
        )
        resp.raise_for_status()
        data = resp.json()

        tvl_history = data.get("tvl", [])
        category = data.get("category", "Unknown")
        chains = data.get("chains", [])

        history = []
        for h in tvl_history:
            history.append({
                "date": datetime.fromtimestamp(h["date"]).strftime("%Y-%m-%d"),
                "timestamp": h["date"],
                "tvl": h.get("totalLiquidityUSD", 0),
            })

        time.sleep(DELAY)
        return history, category, chains

    except Exception as e:
        print(f"  Error fetching {slug}: {e}")
        return [], "Unknown", []


def calculate_tvl_features(
    history: list[dict],
    target_date: str,
) -> dict:
    """Calculate TVL-based features for a specific date."""

    # Find index for target date
    date_to_idx = {h["date"]: i for i, h in enumerate(history)}

    if target_date not in date_to_idx:
        # Find closest date
        target_dt = datetime.strptime(target_date, "%Y-%m-%d")
        closest_date = min(
            history,
            key=lambda h: abs(
                datetime.strptime(h["date"], "%Y-%m-%d") - target_dt
            )
        )
        idx = date_to_idx[closest_date["date"]]
    else:
        idx = date_to_idx[target_date]

    tvl = history[idx]["tvl"]

    # Calculate changes
    def safe_change(current, previous):
        if previous <= 0:
            return 0
        return (current - previous) / previous * 100

    tvl_1d = history[idx - 1]["tvl"] if idx > 0 else tvl
    tvl_7d = history[idx - 7]["tvl"] if idx >= 7 else tvl
    tvl_30d = history[idx - 30]["tvl"] if idx >= 30 else tvl

    change_1d = safe_change(tvl, tvl_1d)
    change_7d = safe_change(tvl, tvl_7d)
    change_30d = safe_change(tvl, tvl_30d)

    # Volatility (std dev of daily changes over last 14 days)
    if idx >= 14:
        daily_changes = []
        for i in range(idx - 13, idx + 1):
            if i > 0:
                change = safe_change(history[i]["tvl"], history[i-1]["tvl"])
                daily_changes.append(change)
        volatility = np.std(daily_changes) if daily_changes else 0
    else:
        volatility = 0

    return {
        "tvl": tvl,
        "tvl_change_1d": round(change_1d, 2),
        "tvl_change_7d": round(change_7d, 2),
        "tvl_change_30d": round(change_30d, 2),
        "tvl_volatility": round(volatility, 2),
    }


def build_exploit_samples(
    exploit: dict,
    days_before: int = 30,
) -> list[TrainingSample]:
    """Build training samples from days before an exploit."""

    slug = exploit["slug"]
    mapped_slug = SLUG_MAPPING.get(slug, slug)

    if mapped_slug is None:
        return []  # CeFi protocol, no TVL data

    print(f"  Fetching {exploit['protocol']} ({mapped_slug})...")

    history, category, chains = fetch_protocol_tvl_history(mapped_slug)

    if not history:
        return []

    exploit_date = exploit["date"]
    exploit_dt = datetime.strptime(exploit_date, "%Y-%m-%d")

    # Generate samples for days BEFORE exploit
    samples = []

    for days_back in range(1, days_before + 1):
        sample_date = (exploit_dt - timedelta(days=days_back)).strftime("%Y-%m-%d")

        # Get TVL features for this date
        features = calculate_tvl_features(history, sample_date)

        if features["tvl"] <= 0:
            continue

        # Risk label: higher risk as we approach exploit
        # days_back = 1 → exploit tomorrow → label = 1.0
        # days_back = 30 → exploit in 30 days → label = 0.5
        risk_label = max(0.5, 1.0 - (days_back / days_before) * 0.5)

        sample = TrainingSample(
            protocol=exploit["protocol"],
            slug=slug,
            date=sample_date,
            tvl=features["tvl"],
            tvl_change_1d=features["tvl_change_1d"],
            tvl_change_7d=features["tvl_change_7d"],
            tvl_change_30d=features["tvl_change_30d"],
            tvl_volatility=features["tvl_volatility"],
            category_risk=CATEGORY_RISK.get(category, 0.5),
            chain_count=len(chains) if chains else 1,
            days_to_exploit=days_back,
            risk_label=risk_label,
            was_exploited=True,
            exploit_type=exploit["type"],
            exploit_loss=exploit["loss_usd"],
        )

        samples.append(sample)

    print(f"    Generated {len(samples)} pre-exploit samples")
    return samples


def build_safe_samples(
    protocol_slug: str,
    start_date: str = "2022-01-01",
    end_date: str = "2024-12-31",
    sampling_frequency: int = 3,  # Sample every N days
) -> list[TrainingSample]:
    """
    Build samples for protocols that were NOT exploited.

    FIXED: Samples distributed across same time period as exploits (2022-2024)
    instead of just recent data.
    """

    print(f"  Fetching {protocol_slug}...")

    history, category, chains = fetch_protocol_tvl_history(protocol_slug)

    if not history or len(history) < 30:
        return []

    # Filter history to date range matching exploit samples
    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    end_dt = datetime.strptime(end_date, "%Y-%m-%d")

    filtered_history = [
        h for h in history
        if start_dt <= datetime.strptime(h["date"], "%Y-%m-%d") <= end_dt
    ]

    if not filtered_history:
        # Fall back to most recent data
        filtered_history = history[-100:]

    samples = []

    # Sample every N days to avoid too many samples
    for i, h in enumerate(filtered_history):
        if i % sampling_frequency != 0:
            continue

        features = calculate_tvl_features(history, h["date"])

        if features["tvl"] <= 0:
            continue

        # Safe protocols have low risk labels
        # But add some variance based on TVL volatility
        base_risk = 0.1
        volatility_risk = min(0.2, features["tvl_volatility"] / 20)
        change_risk = 0.1 if features["tvl_change_7d"] < -10 else 0

        risk_label = base_risk + volatility_risk + change_risk

        sample = TrainingSample(
            protocol=protocol_slug,
            slug=protocol_slug,
            date=h["date"],
            tvl=features["tvl"],
            tvl_change_1d=features["tvl_change_1d"],
            tvl_change_7d=features["tvl_change_7d"],
            tvl_change_30d=features["tvl_change_30d"],
            tvl_volatility=features["tvl_volatility"],
            category_risk=CATEGORY_RISK.get(category, 0.5),
            chain_count=len(chains) if chains else 1,
            days_to_exploit=-1,
            risk_label=round(risk_label, 2),
            was_exploited=False,
        )

        samples.append(sample)

    print(f"    Generated {len(samples)} safe samples from {start_date} to {end_date}")
    return samples


def build_training_dataset():
    """Build complete training dataset."""

    print("=" * 60)
    print("NEXUS — Training Data Generator")
    print("=" * 60)
    print()

    all_samples = []

    # 1. Build exploit samples
    print("[1/2] Building pre-exploit samples...")

    # Focus on DeFi protocols with TVL data (not CeFi)
    defi_exploits = [
        e for e in EXPLOITS
        if e["slug"] not in ["ftx", "celsius", "voyager", "blockfi", "coinex"]
        and e["loss_usd"] >= 10_000_000  # >$10M
    ]

    print(f"  Processing {len(defi_exploits)} DeFi exploits...")

    for exploit in defi_exploits[:20]:  # Top 20 to avoid rate limits
        samples = build_exploit_samples(exploit)
        all_samples.extend(samples)

    exploit_count = len([s for s in all_samples if s.was_exploited])
    print(f"  Total exploit samples: {exploit_count}")

    # 2. Build safe samples
    print()
    print("[2/2] Building safe protocol samples...")

    # Use battle-tested protocols that survived 2022-2023 without exploits
    safe_protocols = [
        "lido",
        "aave-v3",
        "compound-v3",
        "rocket-pool",
        "uniswap-v3",
        "makerdao",
        "pancakeswap",
        "balancer",
    ]

    # Sample from same time period as exploits (2022-2023)
    for slug in safe_protocols:
        samples = build_safe_samples(
            slug,
            start_date="2022-01-01",
            end_date="2023-12-31",
            sampling_frequency=2,  # Every 2 days
        )
        all_samples.extend(samples)

    safe_count = len([s for s in all_samples if not s.was_exploited])
    print(f"  Total safe samples: {safe_count}")

    # 3. Save dataset
    print()
    print("Saving dataset...")

    DATA_DIR.mkdir(exist_ok=True)

    dataset = {
        "metadata": {
            "created_at": datetime.now().isoformat(),
            "total_samples": len(all_samples),
            "exploit_samples": exploit_count,
            "safe_samples": safe_count,
            "exploits_processed": len(defi_exploits[:20]),
        },
        "samples": [asdict(s) for s in all_samples],
    }

    with open(DATA_DIR / "training_dataset.json", "w") as f:
        json.dump(dataset, f, indent=2)

    print(f"Saved: data/training_dataset.json")

    # 4. Summary statistics
    print()
    print("=" * 60)
    print("DATASET SUMMARY")
    print("=" * 60)
    print(f"Total samples:    {len(all_samples)}")
    print(f"Exploit samples:  {exploit_count}")
    print(f"Safe samples:     {safe_count}")

    if exploit_count > 0:
        high_risk = sum(1 for s in all_samples if s.risk_label >= 0.7)
        print(f"High-risk (>=0.7): {high_risk}")

        # Sample distribution by days before exploit
        days_dist = {}
        for s in all_samples:
            if s.was_exploited:
                bucket = f"{(s.days_to_exploit // 7) * 7}-{(s.days_to_exploit // 7 + 1) * 7} days"
                days_dist[bucket] = days_dist.get(bucket, 0) + 1

        print("\nExploit samples by time to hack:")
        for bucket, count in sorted(days_dist.items()):
            print(f"  {bucket}: {count}")

    return dataset


if __name__ == "__main__":
    build_training_dataset()
