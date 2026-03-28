#!/usr/bin/env python3
"""
Nexus Data Quality Report

Generates comprehensive quality metrics for the dataset.

Usage:
    python quality_report.py [--file dataset.json] [--output report.json]
"""

import json
import argparse
import numpy as np
from pathlib import Path
from datetime import datetime
from collections import Counter
from typing import Dict, List, Any

DATA_DIR = Path(__file__).parent


def load_dataset(filepath: Path) -> Dict:
    """Load dataset from JSON."""
    with open(filepath) as f:
        data = json.load(f)
    return data


def compute_feature_stats(samples: List[Dict], feature: str) -> Dict:
    """Compute statistics for a single feature."""
    values = [s.get(feature, 0) or 0 for s in samples]
    values = [v for v in values if isinstance(v, (int, float))]
    
    if not values:
        return {"error": "no values"}
    
    return {
        "count": len(values),
        "mean": round(np.mean(values), 4),
        "std": round(np.std(values), 4),
        "min": round(min(values), 4),
        "max": round(max(values), 4),
        "median": round(np.median(values), 4),
        "q25": round(np.percentile(values, 25), 4),
        "q75": round(np.percentile(values, 75), 4),
        "zeros": sum(1 for v in values if v == 0),
        "zero_pct": round(100 * sum(1 for v in values if v == 0) / len(values), 2),
        "nulls": len(samples) - len(values),
    }


def compute_class_metrics(samples: List[Dict]) -> Dict:
    """Compute class distribution metrics."""
    exploited = [s for s in samples if s.get("was_exploited")]
    safe = [s for s in samples if not s.get("was_exploited")]
    
    return {
        "total": len(samples),
        "exploited": len(exploited),
        "safe": len(safe),
        "ratio": round(len(exploited) / len(samples), 4) if samples else 0,
        "balanced": 0.3 <= len(exploited) / len(samples) <= 0.7 if samples else False,
    }


def compute_temporal_metrics(samples: List[Dict]) -> Dict:
    """Compute temporal coverage metrics."""
    dates = [s.get("date") for s in samples if s.get("date")]
    
    if not dates:
        return {"error": "no dates"}
    
    dates = sorted(dates)
    date_counts = Counter(d[:7] for d in dates)  # Monthly counts
    
    min_date = datetime.strptime(dates[0], "%Y-%m-%d")
    max_date = datetime.strptime(dates[-1], "%Y-%m-%d")
    span_days = (max_date - min_date).days
    
    return {
        "min_date": dates[0],
        "max_date": dates[-1],
        "span_days": span_days,
        "span_years": round(span_days / 365, 2),
        "unique_dates": len(set(dates)),
        "months_covered": len(date_counts),
        "samples_per_month": round(len(samples) / max(len(date_counts), 1), 1),
    }


def compute_protocol_metrics(samples: List[Dict]) -> Dict:
    """Compute protocol distribution metrics."""
    protocols = [s.get("slug") or s.get("protocol") for s in samples]
    protocol_counts = Counter(protocols)
    
    # Samples per protocol
    counts = list(protocol_counts.values())
    
    # Exploited protocols
    exploited_protos = set(
        s.get("slug") or s.get("protocol") 
        for s in samples if s.get("was_exploited")
    )
    
    return {
        "unique_protocols": len(protocol_counts),
        "exploited_protocols": len(exploited_protos),
        "avg_samples_per_protocol": round(np.mean(counts), 2) if counts else 0,
        "max_samples_per_protocol": max(counts) if counts else 0,
        "min_samples_per_protocol": min(counts) if counts else 0,
        "top_protocols": dict(protocol_counts.most_common(10)),
    }


def compute_category_metrics(samples: List[Dict]) -> Dict:
    """Compute category distribution."""
    categories = [s.get("category", "Unknown") for s in samples]
    cat_counts = Counter(categories)
    
    # Exploit rate by category
    cat_exploits = {}
    for cat in cat_counts:
        cat_samples = [s for s in samples if s.get("category") == cat]
        exploited = sum(1 for s in cat_samples if s.get("was_exploited"))
        cat_exploits[cat] = {
            "count": len(cat_samples),
            "exploited": exploited,
            "exploit_rate": round(exploited / len(cat_samples), 4) if cat_samples else 0,
        }
    
    return {
        "categories": len(cat_counts),
        "distribution": dict(cat_counts.most_common()),
        "by_category": cat_exploits,
    }


def compute_correlation_matrix(samples: List[Dict], features: List[str]) -> Dict:
    """Compute feature correlation matrix."""
    data = []
    for s in samples:
        row = [s.get(f, 0) or 0 for f in features]
        data.append(row)
    
    data = np.array(data)
    
    # Only numeric features
    valid_cols = [i for i in range(data.shape[1]) if np.std(data[:, i]) > 0]
    
    if len(valid_cols) < 2:
        return {"error": "insufficient variance"}
    
    corr = np.corrcoef(data[:, valid_cols].T)
    
    # Find highly correlated pairs
    high_corr = []
    for i in range(len(valid_cols)):
        for j in range(i + 1, len(valid_cols)):
            c = abs(corr[i, j])
            if c > 0.7:
                high_corr.append({
                    "feature1": features[valid_cols[i]],
                    "feature2": features[valid_cols[j]],
                    "correlation": round(c, 4),
                })
    
    return {
        "high_correlations": sorted(high_corr, key=lambda x: -x["correlation"]),
    }


def compute_quality_score(metrics: Dict) -> float:
    """Compute overall quality score (0-10)."""
    score = 10.0
    
    # Class balance (0.3-0.7 is ideal)
    ratio = metrics["class"]["ratio"]
    if ratio < 0.2 or ratio > 0.8:
        score -= 2.0
    elif ratio < 0.3 or ratio > 0.7:
        score -= 1.0
    
    # Sample count
    total = metrics["class"]["total"]
    if total < 500:
        score -= 2.0
    elif total < 1000:
        score -= 1.0
    
    # Protocol diversity
    protocols = metrics["protocols"]["unique_protocols"]
    if protocols < 20:
        score -= 2.0
    elif protocols < 50:
        score -= 1.0
    
    # Temporal coverage
    span_years = metrics["temporal"]["span_years"]
    if span_years < 1:
        score -= 2.0
    elif span_years < 2:
        score -= 1.0
    
    # Feature variance (check price features)
    for feat in ["price_change_1d", "price_change_7d"]:
        if feat in metrics["features"]:
            zero_pct = metrics["features"][feat].get("zero_pct", 100)
            if zero_pct > 80:
                score -= 1.0
            elif zero_pct > 50:
                score -= 0.5
    
    return max(round(score, 1), 0)


def generate_report(filepath: Path) -> Dict:
    """Generate comprehensive quality report."""
    data = load_dataset(filepath)
    
    if isinstance(data, dict):
        samples = data.get("samples", [])
        metadata = data.get("metadata", {})
    else:
        samples = data
        metadata = {}
    
    # Feature list
    features = [
        "tvl_log", "tvl_change_1d", "tvl_change_7d", "tvl_change_30d",
        "tvl_volatility", "price_change_1d", "price_change_7d",
        "price_volatility", "price_crash_7d", "category_risk",
        "chain_count", "mcap_to_tvl"
    ]
    
    report = {
        "generated_at": datetime.utcnow().isoformat(),
        "source_file": str(filepath),
        "metadata": metadata,
        "class": compute_class_metrics(samples),
        "temporal": compute_temporal_metrics(samples),
        "protocols": compute_protocol_metrics(samples),
        "categories": compute_category_metrics(samples),
        "features": {f: compute_feature_stats(samples, f) for f in features},
        "correlations": compute_correlation_matrix(samples, features),
    }
    
    report["quality_score"] = compute_quality_score(report)
    
    # Issues summary
    issues = []
    
    if report["class"]["ratio"] < 0.2:
        issues.append("CRITICAL: Very few positive samples (< 20%)")
    elif report["class"]["ratio"] > 0.8:
        issues.append("CRITICAL: Very few negative samples (< 20%)")
    
    if report["class"]["total"] < 500:
        issues.append("WARNING: Small dataset (< 500 samples)")
    
    if report["protocols"]["unique_protocols"] < 30:
        issues.append("WARNING: Low protocol diversity (< 30)")
    
    for feat in ["price_change_1d", "price_change_7d"]:
        if feat in report["features"]:
            if report["features"][feat].get("zero_pct", 0) > 50:
                issues.append(f"WARNING: {feat} has >50% zeros")
    
    if report["temporal"]["span_years"] < 1:
        issues.append("WARNING: Limited temporal coverage (< 1 year)")
    
    report["issues"] = issues
    
    return report


def print_report(report: Dict):
    """Print report to console."""
    print("\n" + "="*60)
    print("NEXUS DATA QUALITY REPORT")
    print("="*60)
    print(f"Generated: {report['generated_at']}")
    print(f"Source: {report['source_file']}")
    print()
    
    print(f"QUALITY SCORE: {report['quality_score']}/10")
    print()
    
    if report["issues"]:
        print("ISSUES:")
        for issue in report["issues"]:
            print(f"  • {issue}")
        print()
    
    print("CLASS DISTRIBUTION:")
    print(f"  Total:     {report['class']['total']}")
    print(f"  Exploited: {report['class']['exploited']} ({report['class']['ratio']*100:.1f}%)")
    print(f"  Safe:      {report['class']['safe']}")
    print(f"  Balanced:  {'✓' if report['class']['balanced'] else '✗'}")
    print()
    
    print("TEMPORAL COVERAGE:")
    print(f"  Range:     {report['temporal']['min_date']} to {report['temporal']['max_date']}")
    print(f"  Span:      {report['temporal']['span_years']} years ({report['temporal']['span_days']} days)")
    print(f"  Months:    {report['temporal']['months_covered']}")
    print()
    
    print("PROTOCOL DIVERSITY:")
    print(f"  Protocols: {report['protocols']['unique_protocols']}")
    print(f"  Exploited: {report['protocols']['exploited_protocols']}")
    print(f"  Avg/proto: {report['protocols']['avg_samples_per_protocol']} samples")
    print()
    
    print("FEATURE SUMMARY:")
    print(f"  {'Feature':<20} {'Mean':>10} {'Std':>10} {'Zero%':>8}")
    print("  " + "-"*50)
    for feat, stats in report["features"].items():
        if "error" not in stats:
            print(f"  {feat:<20} {stats['mean']:>10.3f} {stats['std']:>10.3f} {stats['zero_pct']:>7.1f}%")
    print()
    
    if report["correlations"].get("high_correlations"):
        print("HIGH CORRELATIONS (>0.7):")
        for c in report["correlations"]["high_correlations"][:5]:
            print(f"  {c['feature1']} <-> {c['feature2']}: {c['correlation']:.3f}")
    print()


def main():
    parser = argparse.ArgumentParser(description="Nexus Data Quality Report")
    parser.add_argument("--file", type=str, default=None, help="Dataset file to analyze")
    parser.add_argument("--output", type=str, default=None, help="Output JSON file")
    args = parser.parse_args()
    
    # Find dataset file
    if args.file:
        filepath = Path(args.file)
    else:
        for name in ["dataset_latest.json", "training_dataset_10x.json", "training_dataset.json"]:
            filepath = DATA_DIR / name
            if filepath.exists():
                break
    
    if not filepath.exists():
        print(f"File not found: {filepath}")
        return
    
    report = generate_report(filepath)
    print_report(report)
    
    if args.output:
        output_path = Path(args.output)
        with open(output_path, "w") as f:
            json.dump(report, f, indent=2)
        print(f"Report saved to: {output_path}")


if __name__ == "__main__":
    main()
