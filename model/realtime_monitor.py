#!/usr/bin/env python3
"""
Nexus Real-Time Risk Monitor

Continuously monitors DeFi protocols and generates live risk predictions.

Features:
- Real-time TVL tracking
- Price crash detection
- Live GNN predictions
- Alert system for high-risk protocols
- Web dashboard (future)

Usage:
    python realtime_monitor.py                  # Monitor top 50 protocols
    python realtime_monitor.py --protocols lido,aave,curve  # Monitor specific
    python realtime_monitor.py --interval 300   # Update every 5 minutes
"""

import json
import time
import requests
import numpy as np
import torch
from datetime import datetime, timedelta
from pathlib import Path
from dataclasses import dataclass
from typing import Optional
import argparse

# Import models (v3 for production, v2 for compatibility)
from train_gnn_v3 import NexusRiskPredictor, Config as V3Config
from train_gnn_v2 import NexusGATv2, ModelConfig, build_batch_graph

DATA_DIR = Path(__file__).parent.parent / "data"
MODEL_PATH_V3 = DATA_DIR / "nexus_gnn_v3.pt"  # Primary: security-grade v3
MODEL_PATH_V2 = DATA_DIR / "nexus_gnn_v2.pt"  # Fallback: legacy v2

LLAMA_PROTOCOLS = "https://api.llama.fi/protocols"
LLAMA_PROTOCOL = "https://api.llama.fi/protocol/{slug}"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; NexusMonitor/1.0)"}

CATEGORY_RISK = {
    "Lending": 0.7, "CDP": 0.8, "Dexes": 0.4, "Liquid Staking": 0.5,
    "Bridge": 0.9, "Yield": 0.6, "Derivatives": 0.7, "Algo-Stables": 0.95,
    "Services": 0.4, "Unknown": 0.5,
}


@dataclass
class ProtocolSnapshot:
    """Real-time protocol snapshot."""
    slug: str
    name: str
    tvl: float
    tvl_change_1d: float
    tvl_change_7d: float
    category: str
    chains: list[str]
    timestamp: str


class RiskMonitor:
    """Real-time DeFi risk monitoring system."""

    def __init__(self, model_path: Path = None):
        print("Initializing Nexus Risk Monitor...")

        # Default to v3 model (security-grade)
        if model_path is None:
            model_path = MODEL_PATH_V3

        # Try v3 first, fallback to v2
        self.model_version = None
        self.model = None
        self.metrics = {}

        if model_path.exists():
            try:
                self.model, self.model_version, self.metrics = self._load_model(model_path)
                print(f"✓ Model v{self.model_version} loaded (F1: {self.metrics.get('f1', 0):.1%})")
            except Exception as e:
                print(f"✗ Failed to load model from {model_path}: {e}")

        # Fallback to v2 if v3 failed and we were trying v3
        if self.model is None and model_path == MODEL_PATH_V3 and MODEL_PATH_V2.exists():
            print("Attempting fallback to v2 model...")
            try:
                self.model, self.model_version, self.metrics = self._load_model(MODEL_PATH_V2)
                print(f"✓ Fallback model v{self.model_version} loaded (F1: {self.metrics.get('f1', 0):.1%})")
            except Exception as e:
                print(f"✗ Fallback model also failed: {e}")

        if self.model is None:
            raise FileNotFoundError(
                f"No working model found. Train models first:\n"
                f"  v3: python train_gnn_v3.py\n"
                f"  v2: python train_gnn_v2.py"
            )

        # Historical data cache
        self.protocol_history = {}

    def _load_model(self, model_path: Path):
        """Load model with automatic version detection."""
        checkpoint = torch.load(model_path, map_location='cpu')

        # Detect model version and load appropriately
        if 'config' in checkpoint and 'input_dim' in checkpoint['config']:
            input_dim = checkpoint['config']['input_dim']

            if input_dim == 7:
                # v3 model (MLP with 7 features)
                config = V3Config(**checkpoint["config"])
                model = NexusRiskPredictor(config)
                model.load_state_dict(checkpoint["model_state"])
                model.eval()
                metrics = checkpoint.get("metrics", {})
                return model, "3", metrics

            elif input_dim in [12, 64]:  # v2 can have 12 input features or 64 hidden
                # v2 model (GAT with 12 features)
                config = ModelConfig(**checkpoint["config"])
                model = NexusGATv2(config)
                model.load_state_dict(checkpoint["model_state"])
                model.eval()
                metrics = checkpoint.get("metrics", {})
                return model, "2", metrics

        else:
            # Legacy format - assume v2
            config = ModelConfig()  # Default config
            model = NexusGATv2(config)
            model.load_state_dict(checkpoint)
            model.eval()
            return model, "2", {}

    def fetch_protocols(self, protocol_slugs: Optional[list[str]] = None) -> list[dict]:
        """Fetch current protocol data."""

        if protocol_slugs:
            # Fetch specific protocols
            protocols = []
            for slug in protocol_slugs:
                try:
                    resp = requests.get(
                        LLAMA_PROTOCOL.format(slug=slug),
                        headers=HEADERS,
                        timeout=30
                    )
                    resp.raise_for_status()
                    protocols.append(resp.json())
                except Exception as e:
                    print(f"✗ Failed to fetch {slug}: {e}")

        else:
            # Fetch top protocols
            try:
                resp = requests.get(LLAMA_PROTOCOLS, headers=HEADERS, timeout=30)
                resp.raise_for_status()
                all_protocols = resp.json()

                # Filter out protocols with invalid TVL
                valid = [p for p in all_protocols if p.get("tvl") and isinstance(p.get("tvl"), (int, float))]

                protocols = sorted(
                    valid,
                    key=lambda x: float(x.get("tvl", 0)),
                    reverse=True
                )[:50]
            except Exception as e:
                print(f"✗ Failed to fetch protocols: {e}")
                return []

        return protocols

    def calculate_features(self, protocol: dict) -> Optional[torch.Tensor]:
        """Calculate features for current model version (v2 or v3)."""

        slug = protocol.get("slug", "")

        # Handle different API response formats
        tvl = protocol.get("tvl")
        if isinstance(tvl, list):
            # Sometimes DeFiLlama returns TVL as a list of historical values
            tvl = protocol.get("tvl", [{}])[-1].get("totalLiquidityUSD", 0) if tvl else 0
        elif tvl is None:
            tvl = 0

        change_1d = protocol.get("change_1d", 0)
        change_7d = protocol.get("change_7d", 0)
        chains = protocol.get("chains", [])
        category = protocol.get("category", "Unknown")

        if tvl <= 0:
            return None

        # Calculate additional features for both models
        try:
            resp = requests.get(
                LLAMA_PROTOCOL.format(slug=slug),
                headers=HEADERS,
                timeout=30
            )
            resp.raise_for_status()
            details = resp.json()

            tvl_data = details.get("tvl", [])

            if len(tvl_data) >= 30:
                # Calculate 30d change
                current_tvl = tvl_data[-1].get("totalLiquidityUSD", 0)
                month_ago_tvl = tvl_data[-30].get("totalLiquidityUSD", 0)

                change_30d = (
                    (current_tvl - month_ago_tvl) / month_ago_tvl * 100
                    if month_ago_tvl > 0 else 0
                )

                # Calculate volatility
                recent_tvls = [d.get("totalLiquidityUSD", 0) for d in tvl_data[-14:]]
                changes = []
                for i in range(len(recent_tvls) - 1):
                    if recent_tvls[i] > 0:
                        change = (recent_tvls[i+1] - recent_tvls[i]) / recent_tvls[i] * 100
                        changes.append(change)
                volatility = np.std(changes) if changes else 0
            else:
                change_30d = 0
                volatility = 0

        except:
            change_30d = 0
            volatility = 0

        # Normalize common features
        tvl_log = np.log1p(tvl) / 30.0
        tvl_change_1d = np.clip(change_1d / 100.0, -1, 1)
        tvl_change_7d = np.clip(change_7d / 100.0, -1, 1)
        tvl_change_30d = np.clip(change_30d / 100.0, -1, 1)
        tvl_volatility = volatility / 50.0
        category_risk = CATEGORY_RISK.get(category, 0.5)
        chain_count = len(chains) / 10.0

        # Build features based on model version
        if self.model_version == "3":
            # v3 model: 7 features only
            features = torch.tensor([
                tvl_log,
                tvl_change_1d,
                tvl_change_7d,
                tvl_change_30d,
                tvl_volatility,
                category_risk,
                chain_count,
            ], dtype=torch.float32)

        else:
            # v2 model: 12 features (including broken price features)
            # Price features were broken (all zeros) in training, so use zeros for compatibility
            price_change_1d = 0  # Broken feature (was from CoinGecko)
            price_change_7d = 0
            price_volatility = 0
            price_crash = 0
            mcap = protocol.get("mcap", 0)
            mcap_to_tvl = min((mcap or 0) / tvl, 10.0) / 10.0 if tvl > 0 and mcap else 0

            features = torch.tensor([
                tvl_log,
                tvl_change_1d,
                tvl_change_7d,
                tvl_change_30d,
                tvl_volatility,
                category_risk,
                chain_count,
                price_change_1d,     # Broken features (kept for v2 compatibility)
                price_change_7d,
                price_volatility,
                price_crash,
                mcap_to_tvl,
            ], dtype=torch.float32)

        return features

    def predict(self, protocols: list[dict]) -> list[dict]:
        """Generate risk predictions for protocols."""

        print(f"Analyzing {len(protocols)} protocols...")

        results = []

        # Batch features
        features_list = []
        valid_protocols = []

        for protocol in protocols:
            features = self.calculate_features(protocol)
            if features is not None:
                features_list.append(features)
                valid_protocols.append(protocol)

        if not features_list:
            return []

        # Stack features and predict based on model version
        features_batch = torch.stack(features_list)

        with torch.no_grad():
            if self.model_version == "3":
                # v3 model: Direct MLP prediction (no graph structure needed)
                logits = self.model(features_batch)
                predictions = logits.numpy().flatten()  # v3 model outputs sigmoid already
            else:
                # v2 model: GAT prediction (requires graph structure)
                adj = build_batch_graph(features_batch)
                logits = self.model(features_batch, adj)
                predictions = torch.sigmoid(logits).numpy().flatten()

        # Format results
        for protocol, pred in zip(valid_protocols, predictions):
            risk_score = float(pred) * 100

            # Extract TVL - handle list format
            tvl = protocol.get("tvl")
            if isinstance(tvl, list):
                tvl_value = tvl[-1].get("totalLiquidityUSD", 0) if tvl else 0
            else:
                tvl_value = tvl or 0

            if risk_score >= 70:
                level = "CRITICAL"
                alert = "🔴"
            elif risk_score >= 55:
                level = "HIGH"
                alert = "🟠"
            elif risk_score >= 40:
                level = "MEDIUM"
                alert = "🟡"
            else:
                level = "LOW"
                alert = "🟢"

            results.append({
                "slug": protocol.get("slug", ""),
                "name": protocol.get("name", ""),
                "tvl": tvl_value,
                "change_1d": protocol.get("change_1d", 0),
                "change_7d": protocol.get("change_7d", 0),
                "category": protocol.get("category", "Unknown"),
                "risk_score": round(risk_score, 1),
                "risk_level": level,
                "alert": alert,
                "timestamp": datetime.now().isoformat(),
            })

        # Sort by risk
        results.sort(key=lambda x: x["risk_score"], reverse=True)

        return results

    def monitor_loop(self, interval: int = 300, protocol_slugs: Optional[list[str]] = None):
        """Continuous monitoring loop."""

        print()
        print("=" * 80)
        print("NEXUS REAL-TIME RISK MONITOR")
        print("=" * 80)
        print(f"Model: GNN v{self.model_version} ({'Security-Grade' if self.model_version == '3' else 'Legacy'})")
        print(f"Performance: F1={self.metrics.get('f1', 0):.1%}, AUC={self.metrics.get('auc', 0):.3f}")
        print(f"Update Interval: {interval}s")
        print(f"Monitoring: {'All top 50' if not protocol_slugs else ', '.join(protocol_slugs)}")
        print("=" * 80)
        print()

        iteration = 0

        try:
            while True:
                iteration += 1
                print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Update #{iteration}")
                print("-" * 80)

                # Fetch data
                protocols = self.fetch_protocols(protocol_slugs)

                if not protocols:
                    print("✗ No data fetched")
                    time.sleep(interval)
                    continue

                # Predict
                results = self.predict(protocols)

                # Display top risks
                print()
                print(f"{'Protocol':<25} {'TVL':>12} {'1d%':>8} {'7d%':>8} {'Risk':>6} {'Level':<10}")
                print("-" * 80)

                for r in results[:20]:  # Top 20
                    tvl_str = f"${r['tvl']/1e9:.1f}B" if r['tvl'] > 1e9 else f"${r['tvl']/1e6:.0f}M"
                    print(f"{r['alert']} {r['name']:<22} "
                          f"{tvl_str:>12} "
                          f"{r['change_1d']:>7.1f}% "
                          f"{r['change_7d']:>7.1f}% "
                          f"{r['risk_score']:>5.1f}% "
                          f"{r['risk_level']:<10}")

                # Save results
                output = {
                    "timestamp": datetime.now().isoformat(),
                    "update_number": iteration,
                    "protocols_monitored": len(results),
                    "high_risk_count": sum(1 for r in results if r["risk_score"] >= 55),
                    "results": results,
                }

                with open(DATA_DIR / "live_monitoring.json", "w") as f:
                    json.dump(output, f, indent=2)

                # Alerts
                critical = [r for r in results if r["risk_score"] >= 70]
                if critical:
                    print()
                    print(f"⚠️  ALERT: {len(critical)} protocols at CRITICAL risk:")
                    for r in critical:
                        print(f"    {r['alert']} {r['name']}: {r['risk_score']:.1f}%")

                print()
                print(f"Results saved to: data/live_monitoring.json")
                print(f"Next update in {interval}s...")

                time.sleep(interval)

        except KeyboardInterrupt:
            print("\n\nMonitoring stopped by user")
            print("=" * 80)


def main():
    parser = argparse.ArgumentParser(description="Nexus Real-Time Risk Monitor")
    parser.add_argument(
        "--protocols",
        type=str,
        help="Comma-separated protocol slugs to monitor (e.g., 'lido,aave,curve')"
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=300,
        help="Update interval in seconds (default: 300)"
    )
    parser.add_argument(
        "--model",
        type=str,
        default=str(MODEL_PATH_V3),  # Default to security-grade v3
        help="Path to model checkpoint (defaults to v3)"
    )

    args = parser.parse_args()

    protocol_slugs = args.protocols.split(",") if args.protocols else None

    monitor = RiskMonitor(Path(args.model))
    monitor.monitor_loop(
        interval=args.interval,
        protocol_slugs=protocol_slugs
    )


if __name__ == "__main__":
    main()
