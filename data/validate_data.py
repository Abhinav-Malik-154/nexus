#!/usr/bin/env python3
"""
Nexus Data Validation — Production Quality Gates

Comprehensive validation to ensure data quality before training.
Can be run as part of CI/CD pipeline.

Exit codes:
    0 - All validations passed
    1 - Critical failures (should block training)
    2 - Warnings (can proceed with caution)

Usage:
    python validate_data.py                     # Validate default dataset
    python validate_data.py --file dataset.json # Validate specific file
    python validate_data.py --strict            # Fail on warnings too
"""

import json
import sys
import argparse
import numpy as np
from pathlib import Path
from datetime import datetime
from collections import Counter
from typing import Dict, List, Tuple

DATA_DIR = Path(__file__).parent

# Validation thresholds
THRESHOLDS = {
    "min_samples": 1000,
    "min_protocols": 30,
    "min_exploited_protocols": 5,
    "class_balance_min": 0.2,
    "class_balance_max": 0.8,
    "max_zero_rate": 0.3,
    "min_temporal_span_days": 365,
    "max_correlation": 0.95,
    "min_feature_variance": 0.001,
}

REQUIRED_FEATURES = [
    "tvl_log", "tvl_change_1d", "tvl_change_7d", "tvl_change_30d",
    "tvl_volatility", "price_change_1d", "price_change_7d",
    "price_volatility", "price_crash_7d", "category_risk",
    "chain_count", "mcap_to_tvl"
]


class ValidationResult:
    """Holds validation results."""
    
    def __init__(self):
        self.critical = []
        self.warnings = []
        self.info = []
    
    def add_critical(self, msg: str):
        self.critical.append(f"[CRITICAL] {msg}")
    
    def add_warning(self, msg: str):
        self.warnings.append(f"[WARNING] {msg}")
    
    def add_info(self, msg: str):
        self.info.append(f"[INFO] {msg}")
    
    @property
    def passed(self) -> bool:
        return len(self.critical) == 0
    
    @property
    def exit_code(self) -> int:
        if self.critical:
            return 1
        if self.warnings:
            return 2
        return 0
    
    def print_report(self):
        print("\n" + "="*60)
        print("NEXUS DATA VALIDATION REPORT")
        print("="*60)
        
        if self.critical:
            print("\nCRITICAL FAILURES:")
            for msg in self.critical:
                print(f"  ❌ {msg}")
        
        if self.warnings:
            print("\nWARNINGS:")
            for msg in self.warnings:
                print(f"  ⚠️  {msg}")
        
        if self.info:
            print("\nINFO:")
            for msg in self.info:
                print(f"  ℹ️  {msg}")
        
        print("\n" + "-"*60)
        if self.passed:
            print("✅ VALIDATION PASSED")
        else:
            print("❌ VALIDATION FAILED")
        print("-"*60)


def load_dataset(filepath: Path) -> Tuple[List[Dict], Dict]:
    """Load dataset and extract samples."""
    with open(filepath) as f:
        data = json.load(f)
    
    if isinstance(data, dict):
        return data.get("samples", []), data.get("metadata", {})
    return data, {}


def validate_structure(samples: List[Dict], result: ValidationResult):
    """Validate basic data structure."""
    if not samples:
        result.add_critical("Empty dataset")
        return
    
    result.add_info(f"Total samples: {len(samples)}")
    
    # Check required features
    sample = samples[0]
    missing = [f for f in REQUIRED_FEATURES if f not in sample]
    if missing:
        result.add_critical(f"Missing required features: {missing}")
    
    # Check for required metadata
    if "date" not in sample:
        result.add_warning("Missing 'date' field")
    if "slug" not in sample and "protocol" not in sample:
        result.add_warning("Missing protocol identifier (slug/protocol)")


def validate_class_balance(samples: List[Dict], result: ValidationResult):
    """Validate class distribution."""
    exploited = sum(1 for s in samples if s.get("was_exploited"))
    ratio = exploited / len(samples) if samples else 0
    
    result.add_info(f"Class balance: {exploited}/{len(samples)} ({ratio:.1%} exploited)")
    
    if ratio < THRESHOLDS["class_balance_min"]:
        result.add_critical(f"Severe class imbalance: only {ratio:.1%} positive samples")
    elif ratio > THRESHOLDS["class_balance_max"]:
        result.add_critical(f"Severe class imbalance: {ratio:.1%} positive samples (too many)")


def validate_sample_count(samples: List[Dict], result: ValidationResult):
    """Validate sufficient sample count."""
    n = len(samples)
    
    if n < THRESHOLDS["min_samples"]:
        result.add_critical(f"Insufficient samples: {n} < {THRESHOLDS['min_samples']}")
    elif n < 5000:
        result.add_warning(f"Small dataset: {n} samples (recommend 5000+)")


def validate_protocol_diversity(samples: List[Dict], result: ValidationResult):
    """Validate protocol coverage."""
    protocols = set(s.get("slug") or s.get("protocol") for s in samples)
    exploited_protos = set(
        s.get("slug") or s.get("protocol") 
        for s in samples if s.get("was_exploited")
    )
    
    result.add_info(f"Protocols: {len(protocols)} ({len(exploited_protos)} exploited)")
    
    if len(protocols) < THRESHOLDS["min_protocols"]:
        result.add_critical(f"Insufficient protocol diversity: {len(protocols)}")
    
    if len(exploited_protos) < THRESHOLDS["min_exploited_protocols"]:
        result.add_warning(f"Few exploited protocols: {len(exploited_protos)}")


def validate_temporal_coverage(samples: List[Dict], result: ValidationResult):
    """Validate temporal span."""
    dates = [s.get("date") for s in samples if s.get("date")]
    
    if not dates:
        result.add_critical("No date information in samples")
        return
    
    dates = sorted(dates)
    min_date = datetime.strptime(dates[0], "%Y-%m-%d")
    max_date = datetime.strptime(dates[-1], "%Y-%m-%d")
    span = (max_date - min_date).days
    
    result.add_info(f"Temporal span: {dates[0]} to {dates[-1]} ({span} days)")
    
    if span < THRESHOLDS["min_temporal_span_days"]:
        result.add_warning(f"Limited temporal coverage: {span} days")


def validate_feature_quality(samples: List[Dict], result: ValidationResult):
    """Validate feature distributions."""
    for feat in REQUIRED_FEATURES:
        vals = [s.get(feat) for s in samples]
        vals = [v for v in vals if isinstance(v, (int, float)) and not np.isnan(v)]
        
        if not vals:
            result.add_critical(f"No valid values for feature: {feat}")
            continue
        
        # Zero rate
        zero_rate = sum(1 for v in vals if v == 0) / len(vals)
        if zero_rate > THRESHOLDS["max_zero_rate"]:
            result.add_warning(f"High zero rate for {feat}: {zero_rate:.1%}")
        
        # Variance check
        variance = np.var(vals)
        if variance < THRESHOLDS["min_feature_variance"]:
            result.add_warning(f"Low variance for {feat}: {variance:.6f}")
        
        # NaN check
        nan_count = sum(1 for s in samples if s.get(feat) is None)
        if nan_count > 0:
            result.add_warning(f"Missing values in {feat}: {nan_count}")


def validate_feature_ranges(samples: List[Dict], result: ValidationResult):
    """Validate feature values are in expected ranges."""
    ranges = {
        "tvl_log": (0, 2),
        "tvl_change_1d": (-100, 100),
        "tvl_change_7d": (-100, 100),
        "tvl_volatility": (0, 100),
        "price_change_1d": (-100, 100),
        "price_change_7d": (-100, 100),
        "price_volatility": (0, 100),
        "price_crash_7d": (0, 100),
        "category_risk": (0, 1),
        "chain_count": (1, 100),
        "mcap_to_tvl": (0, 100),
    }
    
    for feat, (lo, hi) in ranges.items():
        vals = [s.get(feat, 0) for s in samples if isinstance(s.get(feat), (int, float))]
        if not vals:
            continue
        
        out_of_range = sum(1 for v in vals if v < lo or v > hi)
        if out_of_range > len(vals) * 0.05:  # More than 5% out of range
            result.add_warning(f"{feat} has {out_of_range} values out of range [{lo}, {hi}]")


def validate_correlations(samples: List[Dict], result: ValidationResult):
    """Check for problematic feature correlations."""
    features = ["tvl_change_1d", "tvl_change_7d", "price_change_1d", "price_change_7d"]
    
    data = []
    for s in samples:
        row = [s.get(f, 0) or 0 for f in features]
        data.append(row)
    
    data = np.array(data)
    
    # Check for near-perfect correlations (data leakage indicator)
    for i in range(len(features)):
        for j in range(i + 1, len(features)):
            if np.std(data[:, i]) > 0 and np.std(data[:, j]) > 0:
                corr = np.corrcoef(data[:, i], data[:, j])[0, 1]
                if abs(corr) > THRESHOLDS["max_correlation"]:
                    result.add_warning(
                        f"Very high correlation ({corr:.3f}) between {features[i]} and {features[j]}"
                    )


def validate_duplicates(samples: List[Dict], result: ValidationResult):
    """Check for duplicate samples."""
    # Create signature for each sample
    sigs = []
    for s in samples:
        sig = f"{s.get('slug', '')}:{s.get('date', '')}:{s.get('tvl', 0):.0f}"
        sigs.append(sig)
    
    duplicates = len(sigs) - len(set(sigs))
    if duplicates > 0:
        dup_rate = duplicates / len(samples)
        if dup_rate > 0.1:
            result.add_critical(f"High duplicate rate: {duplicates} ({dup_rate:.1%})")
        else:
            result.add_warning(f"Found {duplicates} potential duplicate samples")


def validate_splits(data_dir: Path, result: ValidationResult):
    """Validate train/val/test splits if they exist."""
    splits = ["train", "val", "test"]
    found_splits = []
    
    for split in splits:
        for suffix in ["_final.json", "_fixed.json", ".json"]:
            path = data_dir / f"{split}{suffix}"
            if path.exists():
                found_splits.append((split, path))
                break
    
    if len(found_splits) < 3:
        result.add_info("Not all split files found; using combined dataset")
        return
    
    # Check for temporal leakage
    split_dates = {}
    for split, path in found_splits:
        with open(path) as f:
            data = json.load(f)
        samples = data if isinstance(data, list) else data.get("samples", [])
        dates = sorted(s.get("date", "") for s in samples if s.get("date"))
        if dates:
            split_dates[split] = (dates[0], dates[-1])
    
    if "train" in split_dates and "test" in split_dates:
        train_max = split_dates["train"][1]
        test_min = split_dates["test"][0]
        
        if train_max >= test_min:
            result.add_warning(
                f"Potential temporal leakage: train ends {train_max}, test starts {test_min}"
            )
        else:
            result.add_info(f"Temporal split: train<={train_max}, test>={test_min}")


def run_validation(filepath: Path, data_dir: Path) -> ValidationResult:
    """Run all validations."""
    result = ValidationResult()
    
    try:
        samples, metadata = load_dataset(filepath)
    except Exception as e:
        result.add_critical(f"Failed to load dataset: {e}")
        return result
    
    # Run all validations
    validate_structure(samples, result)
    if not samples:
        return result
    
    validate_sample_count(samples, result)
    validate_class_balance(samples, result)
    validate_protocol_diversity(samples, result)
    validate_temporal_coverage(samples, result)
    validate_feature_quality(samples, result)
    validate_feature_ranges(samples, result)
    validate_correlations(samples, result)
    validate_duplicates(samples, result)
    validate_splits(data_dir, result)
    
    return result


def main():
    parser = argparse.ArgumentParser(description="Nexus Data Validation")
    parser.add_argument("--file", type=str, default=None, help="Dataset file to validate")
    parser.add_argument("--strict", action="store_true", help="Fail on warnings too")
    parser.add_argument("--quiet", action="store_true", help="Only show failures")
    args = parser.parse_args()
    
    # Find dataset file
    if args.file:
        filepath = Path(args.file)
        if not filepath.is_absolute():
            filepath = DATA_DIR / args.file
    else:
        for name in ["dataset_final.json", "dataset_enhanced.json", 
                     "dataset_fixed.json", "dataset_latest.json"]:
            filepath = DATA_DIR / name
            if filepath.exists():
                break
    
    if not filepath.exists():
        print(f"File not found: {filepath}")
        sys.exit(1)
    
    print(f"Validating: {filepath}")
    
    result = run_validation(filepath, DATA_DIR)
    
    if not args.quiet or not result.passed:
        result.print_report()
    
    # Determine exit code
    if args.strict and result.warnings:
        sys.exit(2)
    
    sys.exit(result.exit_code)


if __name__ == "__main__":
    main()
