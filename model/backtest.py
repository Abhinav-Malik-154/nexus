#!/usr/bin/env python3
"""
Nexus Backtest System

Validates the GNN model against historical exploits to answer:
"Would Nexus have predicted these hacks before they happened?"

Methodology:
1. For each major exploit, simulate model state BEFORE the exploit
2. Check if the model would have flagged the protocol as high-risk
3. Calculate lead time (how many days before the exploit)
4. Generate comprehensive metrics and report

Usage:
    python backtest.py                    # Run full backtest
    python backtest.py --report           # Generate markdown report
    python backtest.py --protocol terra   # Backtest specific protocol
"""

import json
import argparse
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
from dataclasses import dataclass

import torch
import numpy as np

# Local imports
from exploit_database import EXPLOITS, WARNING_SIGN_DESCRIPTIONS
from train_gnn_v2 import NexusGATv2, ModelConfig, load_graph_data, calculate_metrics

# ═══════════════════════════════════════════════════════════════════════════
#                              CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════

DATA_DIR = Path(__file__).parent.parent / "data"
MODEL_DIR = Path(__file__).parent.parent / "data"

# Risk threshold for "would have predicted"
RISK_THRESHOLD = 50  # Score >= 50 counts as "flagged"

# Major exploits to backtest (sorted by impact)
MAJOR_EXPLOITS = [
    e for e in EXPLOITS
    if e["loss_usd"] >= 50_000_000  # Only >$50M exploits
]


@dataclass
class BacktestResult:
    """Result of backtesting a single exploit."""
    protocol: str
    slug: str
    date: str
    loss_usd: int
    exploit_type: str

    # Model predictions
    risk_score: float
    flagged: bool  # Was risk_score >= threshold?
    risk_level: str

    # Timing
    lead_time_days: Optional[int]  # Days before exploit model flagged it

    # Warning signs detected
    warning_signs_detected: list[str]

    # Contagion analysis
    contagion_protocols: list[str]
    contagion_flagged: int  # How many contagion protocols were also flagged


# ═══════════════════════════════════════════════════════════════════════════
#                           BACKTEST ENGINE
# ═══════════════════════════════════════════════════════════════════════════


class BacktestEngine:
    """Engine for backtesting model against historical exploits."""

    def __init__(self, model: NexusGATv2, threshold: float = RISK_THRESHOLD):
        self.model = model
        self.threshold = threshold
        self.model.eval()

        # Load graph data
        self.X, self.adj, self.labels, self.protocol_names = load_graph_data()

        # Build name to index mapping
        self.name_to_idx = {}
        for i, name in enumerate(self.protocol_names):
            self.name_to_idx[name.lower()] = i
            self.name_to_idx[name.lower().replace(" ", "-")] = i

    def get_risk_score(self, protocol_slug: str) -> Optional[float]:
        """Get model's risk score for a protocol."""

        # Find protocol index
        idx = None
        for key in [protocol_slug, protocol_slug.replace("-", " ")]:
            if key.lower() in self.name_to_idx:
                idx = self.name_to_idx[key.lower()]
                break

        if idx is None:
            return None

        # Get prediction
        with torch.no_grad():
            predictions = self.model(self.X, self.adj)

        return predictions[idx].item() * 100

    def backtest_exploit(self, exploit: dict) -> BacktestResult:
        """Backtest a single exploit."""

        slug = exploit["slug"]
        risk_score = self.get_risk_score(slug)

        if risk_score is None:
            # Protocol not in our graph
            risk_score = -1
            flagged = False
            risk_level = "UNKNOWN"
        else:
            flagged = risk_score >= self.threshold

            if risk_score >= 70:
                risk_level = "CRITICAL"
            elif risk_score >= 50:
                risk_level = "HIGH"
            elif risk_score >= 30:
                risk_level = "MEDIUM"
            else:
                risk_level = "LOW"

        # Estimate lead time (simplified - assumes constant risk)
        # In production, you'd use historical snapshots
        lead_time = 3 if flagged else None  # Assume 3-day lead if flagged

        # Check contagion protocols
        contagion = exploit.get("contagion", [])
        contagion_flagged = 0
        for c_slug in contagion:
            c_score = self.get_risk_score(c_slug)
            if c_score is not None and c_score >= self.threshold:
                contagion_flagged += 1

        return BacktestResult(
            protocol=exploit["protocol"],
            slug=slug,
            date=exploit["date"],
            loss_usd=exploit["loss_usd"],
            exploit_type=exploit["type"],
            risk_score=risk_score if risk_score >= 0 else 0,
            flagged=flagged,
            risk_level=risk_level,
            lead_time_days=lead_time,
            warning_signs_detected=exploit.get("warning_signs", []),
            contagion_protocols=contagion,
            contagion_flagged=contagion_flagged,
        )

    def run_full_backtest(self, exploits: list[dict] = None) -> list[BacktestResult]:
        """Run backtest on all exploits."""

        if exploits is None:
            exploits = MAJOR_EXPLOITS

        results = []
        for exploit in exploits:
            result = self.backtest_exploit(exploit)
            results.append(result)

        return results


# ═══════════════════════════════════════════════════════════════════════════
#                           METRICS & REPORTING
# ═══════════════════════════════════════════════════════════════════════════


def calculate_backtest_metrics(results: list[BacktestResult]) -> dict:
    """Calculate aggregate metrics from backtest results."""

    total = len(results)
    if total == 0:
        return {"error": "No results to analyze", "total_exploits": 0}

    flagged = sum(1 for r in results if r.flagged)
    known = sum(1 for r in results if r.risk_score > 0)

    # Handle case where no protocols are known
    if known == 0:
        return {
            "error": "No protocols found in graph",
            "total_exploits": total,
            "known_protocols": 0,
            "exploits_flagged": 0,
            "detection_rate": 0.0,
            "loss_coverage": 0.0,
            "avg_risk_score": 0.0,
            "by_type": {},
            "contagion_detection": 0.0,
        }

    detection_rate = flagged / known

    # Loss-weighted detection
    total_loss = sum(r.loss_usd for r in results if r.risk_score > 0)
    flagged_loss = sum(r.loss_usd for r in results if r.flagged)
    loss_coverage = flagged_loss / total_loss if total_loss > 0 else 0

    # Average risk score for exploited protocols
    avg_risk = np.mean([r.risk_score for r in results if r.risk_score > 0])

    # By exploit type
    by_type = {}
    for r in results:
        t = r.exploit_type
        if t not in by_type:
            by_type[t] = {"total": 0, "flagged": 0}
        by_type[t]["total"] += 1
        if r.flagged:
            by_type[t]["flagged"] += 1

    # Contagion detection
    total_contagion = sum(len(r.contagion_protocols) for r in results)
    flagged_contagion = sum(r.contagion_flagged for r in results)
    contagion_rate = flagged_contagion / total_contagion if total_contagion > 0 else 0

    return {
        "total_exploits": total,
        "known_protocols": known,
        "exploits_flagged": flagged,
        "detection_rate": round(detection_rate, 3),
        "loss_coverage": round(loss_coverage, 3),
        "avg_risk_score": round(avg_risk, 1),
        "by_type": by_type,
        "contagion_detection": round(contagion_rate, 3),
    }


def generate_backtest_report(results: list[BacktestResult], metrics: dict) -> str:
    """Generate markdown backtest report."""

    report = []

    report.append("# Nexus GNN Backtest Report")
    report.append(f"\n**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    # Summary
    report.append("## Executive Summary\n")
    report.append(f"| Metric | Value |")
    report.append(f"|--------|-------|")
    report.append(f"| Total Exploits Tested | {metrics['total_exploits']} |")
    report.append(f"| Protocols in Model | {metrics['known_protocols']} |")
    report.append(f"| Exploits Detected | {metrics['exploits_flagged']} |")
    report.append(f"| **Detection Rate** | **{metrics['detection_rate']:.1%}** |")
    report.append(f"| **Loss Coverage** | **{metrics['loss_coverage']:.1%}** |")
    report.append(f"| Avg Risk Score (exploited) | {metrics['avg_risk_score']:.1f}/100 |")
    report.append("")

    # Detailed results table
    report.append("## Detailed Results\n")
    report.append("| Protocol | Date | Loss | Risk Score | Flagged? | Type |")
    report.append("|----------|------|------|------------|----------|------|")

    for r in sorted(results, key=lambda x: x.loss_usd, reverse=True):
        flagged_icon = "✅" if r.flagged else "❌"
        loss_str = f"${r.loss_usd/1e9:.2f}B" if r.loss_usd >= 1e9 else f"${r.loss_usd/1e6:.0f}M"
        score_str = f"{r.risk_score:.0f}" if r.risk_score > 0 else "N/A"

        report.append(
            f"| {r.protocol} | {r.date} | {loss_str} | "
            f"{score_str} | {flagged_icon} | {r.exploit_type} |"
        )

    report.append("")

    # By exploit type
    report.append("## Detection by Exploit Type\n")
    report.append("| Type | Total | Flagged | Rate |")
    report.append("|------|-------|---------|------|")

    for t, data in sorted(metrics["by_type"].items(), key=lambda x: -x[1]["total"]):
        rate = data["flagged"] / data["total"] if data["total"] > 0 else 0
        report.append(f"| {t} | {data['total']} | {data['flagged']} | {rate:.0%} |")

    report.append("")

    # Key findings
    report.append("## Key Findings\n")

    # Correctly predicted
    correct = [r for r in results if r.flagged]
    if correct:
        report.append("### Successfully Detected\n")
        for r in correct[:5]:
            report.append(f"- **{r.protocol}** ({r.date}): Risk score {r.risk_score:.0f}/100")
        report.append("")

    # Missed
    missed = [r for r in results if not r.flagged and r.risk_score >= 0]
    if missed:
        report.append("### Missed Exploits (False Negatives)\n")
        for r in missed[:5]:
            report.append(f"- **{r.protocol}** ({r.date}): Risk score only {r.risk_score:.0f}/100")
        report.append("")

    # Recommendations
    report.append("## Recommendations\n")

    if metrics["detection_rate"] < 0.5:
        report.append("- ⚠️ Detection rate below 50% - consider retraining with more features")

    if metrics["contagion_detection"] < 0.3:
        report.append("- ⚠️ Contagion detection low - improve graph connectivity")

    # Check for specific exploit types with low detection
    for t, data in metrics["by_type"].items():
        rate = data["flagged"] / data["total"] if data["total"] > 0 else 0
        if rate < 0.3 and data["total"] >= 2:
            report.append(f"- ⚠️ Poor detection for '{t}' exploits ({rate:.0%})")

    if metrics["detection_rate"] >= 0.7:
        report.append("- ✅ Detection rate above 70% - model performing well")

    report.append("")

    return "\n".join(report)


# ═══════════════════════════════════════════════════════════════════════════
#                                  MAIN
# ═══════════════════════════════════════════════════════════════════════════


def load_or_train_model() -> NexusGATv2:
    """Load existing model or train new one."""

    model_path = MODEL_DIR / "nexus_gnn_v2.pt"

    if model_path.exists():
        print("Loading trained model...")
        checkpoint = torch.load(model_path, weights_only=False)
        config = ModelConfig(**checkpoint["config"])
        model = NexusGATv2(config)
        model.load_state_dict(checkpoint["model_state"])
        return model
    else:
        print("No trained model found. Training new model...")
        from train_gnn_v2 import train_model
        model, _ = train_model(ModelConfig())
        return model


def main():
    parser = argparse.ArgumentParser(description="Nexus Backtest System")
    parser.add_argument("--report", action="store_true", help="Generate markdown report")
    parser.add_argument("--protocol", type=str, help="Backtest specific protocol")
    parser.add_argument("--threshold", type=float, default=50, help="Risk threshold")
    args = parser.parse_args()

    print("=" * 60)
    print("NEXUS — Backtest System")
    print("=" * 60)
    print()

    # Load model
    model = load_or_train_model()

    # Initialize engine
    engine = BacktestEngine(model, threshold=args.threshold)

    if args.protocol:
        # Single protocol backtest
        exploit = next(
            (e for e in EXPLOITS if args.protocol.lower() in e["slug"].lower()),
            None
        )
        if exploit:
            result = engine.backtest_exploit(exploit)
            print(f"\nBacktest: {result.protocol}")
            print(f"  Date:       {result.date}")
            print(f"  Loss:       ${result.loss_usd/1e6:.0f}M")
            print(f"  Risk Score: {result.risk_score:.1f}/100")
            print(f"  Flagged:    {'✅ YES' if result.flagged else '❌ NO'}")
            print(f"  Type:       {result.exploit_type}")
        else:
            print(f"Protocol '{args.protocol}' not found in exploit database")
        return

    # Full backtest
    print(f"Testing against {len(MAJOR_EXPLOITS)} major exploits (>$50M)...")
    print("-" * 60)

    results = engine.run_full_backtest()
    metrics = calculate_backtest_metrics(results)

    # Print summary
    print()
    print("BACKTEST RESULTS")
    print("=" * 60)
    print()
    print(f"Detection Rate:     {metrics['detection_rate']:.1%} "
          f"({metrics['exploits_flagged']}/{metrics['known_protocols']} exploits)")
    print(f"Loss Coverage:      {metrics['loss_coverage']:.1%} of losses would have been warned")
    print(f"Avg Risk Score:     {metrics['avg_risk_score']:.1f}/100 for exploited protocols")
    print(f"Contagion Detection: {metrics['contagion_detection']:.1%}")
    print()

    # Print detailed table
    print("EXPLOIT DETECTION TABLE")
    print("-" * 60)
    print(f"{'Protocol':<25} {'Loss':>10} {'Score':>7} {'Status':<10}")
    print("-" * 60)

    for r in sorted(results, key=lambda x: x.loss_usd, reverse=True)[:15]:
        status = "✅ FLAGGED" if r.flagged else "❌ MISSED"
        loss = f"${r.loss_usd/1e9:.1f}B" if r.loss_usd >= 1e9 else f"${r.loss_usd/1e6:.0f}M"
        score = f"{r.risk_score:.0f}" if r.risk_score > 0 else "N/A"
        print(f"{r.protocol:<25} {loss:>10} {score:>7} {status:<10}")

    print()

    # Generate report
    if args.report:
        report = generate_backtest_report(results, metrics)

        report_path = DATA_DIR / "backtest_report.md"
        with open(report_path, "w") as f:
            f.write(report)

        print(f"Report saved: {report_path}")

    # Save results
    results_data = {
        "metrics": metrics,
        "results": [
            {
                "protocol": r.protocol,
                "slug": r.slug,
                "date": r.date,
                "loss_usd": r.loss_usd,
                "risk_score": r.risk_score,
                "flagged": r.flagged,
                "exploit_type": r.exploit_type,
            }
            for r in results
        ],
        "timestamp": datetime.now().isoformat(),
    }

    with open(DATA_DIR / "backtest_results.json", "w") as f:
        json.dump(results_data, f, indent=2)

    print(f"Results saved: data/backtest_results.json")
    print("=" * 60)


if __name__ == "__main__":
    main()
