#!/usr/bin/env python3
"""
Nexus Data Manager — Unified CLI for Data Operations

Production-grade data management:
- Fetch fresh data from DeFiLlama/CoinGecko APIs
- Build training datasets with proper feature engineering
- Validate data quality before training
- Export to various formats

Usage:
    python manage_data.py status                # Show current data status
    python manage_data.py build --target 5000   # Build production dataset
    python manage_data.py validate              # Run validation suite
    python manage_data.py export --format csv   # Export for analysis
    python manage_data.py clean                 # Remove intermediate files
"""

import json
import argparse
import shutil
from pathlib import Path
from datetime import datetime

DATA_DIR = Path(__file__).parent


def cmd_status(args):
    """Show current data status."""
    print("\n" + "="*60)
    print("NEXUS DATA STATUS")
    print("="*60)
    
    # Find datasets
    datasets = [
        "dataset_final.json",
        "dataset_enhanced.json", 
        "dataset_fixed.json",
        "dataset_latest.json",
        "training_dataset_10x.json",
    ]
    
    print("\nDATASETS:")
    for name in datasets:
        path = DATA_DIR / name
        if path.exists():
            size = path.stat().st_size / 1024
            with open(path) as f:
                data = json.load(f)
            samples = data.get("samples", data) if isinstance(data, dict) else data
            n = len(samples) if isinstance(samples, list) else 0
            print(f"  ✓ {name}: {n} samples ({size:.1f} KB)")
        else:
            print(f"  ✗ {name}: not found")
    
    # Check splits
    print("\nSPLITS:")
    for split in ["train", "val", "test"]:
        path = DATA_DIR / f"{split}_final.json"
        if path.exists():
            with open(path) as f:
                data = json.load(f)
            samples = data if isinstance(data, list) else data.get("samples", [])
            print(f"  ✓ {split}: {len(samples)} samples")
        else:
            print(f"  ✗ {split}: not found")
    
    # Database status
    db_path = DATA_DIR / "nexus.db"
    if db_path.exists():
        size = db_path.stat().st_size / 1024
        print(f"\nDATABASE: nexus.db ({size:.1f} KB)")
    
    # Quality score
    try:
        from quality_report import generate_report
        for name in ["dataset_final.json", "dataset_enhanced.json"]:
            path = DATA_DIR / name
            if path.exists():
                report = generate_report(path)
                print(f"\nQUALITY SCORE: {report['quality_score']}/10 ({name})")
                break
    except Exception:
        pass
    
    print()


def cmd_build(args):
    """Build production dataset."""
    import subprocess
    
    print("Building production dataset...")
    
    # Step 1: Fix existing data
    print("\n[1/4] Fixing existing data...")
    result = subprocess.run(
        ["python3", "fix_features.py"],
        cwd=DATA_DIR,
        capture_output=True,
        text=True
    )
    if result.returncode != 0:
        print(f"Error: {result.stderr}")
        return
    print(result.stdout)
    
    # Step 2: Expand dataset
    print(f"\n[2/4] Expanding to {args.target} samples...")
    result = subprocess.run(
        ["python3", "data_enhancer.py", "expand", "--target", str(args.target)],
        cwd=DATA_DIR,
        capture_output=True,
        text=True
    )
    if result.returncode != 0:
        print(f"Error: {result.stderr}")
        return
    print(result.stdout)
    
    # Step 3: Finalize splits
    print("\n[3/4] Creating temporal splits...")
    result = subprocess.run(
        ["python3", "data_enhancer.py", "finalize", "--input", "dataset_enhanced.json"],
        cwd=DATA_DIR,
        capture_output=True,
        text=True
    )
    if result.returncode != 0:
        print(f"Error: {result.stderr}")
        return
    print(result.stdout)
    
    # Step 4: Validate
    print("\n[4/4] Validating...")
    result = subprocess.run(
        ["python3", "validate_data.py", "--file", "dataset_final.json"],
        cwd=DATA_DIR,
        capture_output=True,
        text=True
    )
    print(result.stdout)
    
    print("\n✓ Build complete!")


def cmd_validate(args):
    """Run validation suite."""
    import subprocess
    
    file_arg = ["--file", args.file] if args.file else []
    strict_arg = ["--strict"] if args.strict else []
    
    result = subprocess.run(
        ["python3", "validate_data.py"] + file_arg + strict_arg,
        cwd=DATA_DIR
    )
    return result.returncode


def cmd_export(args):
    """Export dataset to various formats."""
    # Find best dataset
    for name in ["dataset_final.json", "dataset_enhanced.json", "dataset_fixed.json"]:
        input_path = DATA_DIR / name
        if input_path.exists():
            break
    else:
        print("No dataset found!")
        return
    
    print(f"Loading {input_path}...")
    with open(input_path) as f:
        data = json.load(f)
    
    samples = data.get("samples", data) if isinstance(data, dict) else data
    
    if args.format == "csv":
        import csv
        output_path = DATA_DIR / "dataset_export.csv"
        
        # Determine fields from first sample
        if samples:
            fields = list(samples[0].keys())
        else:
            print("No samples to export")
            return
        
        with open(output_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            for s in samples:
                writer.writerow(s)
        
        print(f"Exported {len(samples)} samples to {output_path}")
    
    elif args.format == "parquet":
        try:
            import pandas as pd
            df = pd.DataFrame(samples)
            output_path = DATA_DIR / "dataset_export.parquet"
            df.to_parquet(output_path, index=False)
            print(f"Exported {len(samples)} samples to {output_path}")
        except ImportError:
            print("Error: pandas and pyarrow required for parquet export")
            print("Install with: pip install pandas pyarrow")
    
    elif args.format == "splits":
        # Export splits separately
        for split in ["train", "val", "test"]:
            split_path = DATA_DIR / f"{split}_final.json"
            if split_path.exists():
                output_path = DATA_DIR / f"{split}_export.json"
                shutil.copy(split_path, output_path)
                print(f"Exported {split} to {output_path}")


def cmd_clean(args):
    """Remove intermediate files."""
    patterns = [
        "dataset_fixed.json",
        "dataset_enhanced.json",
        "train_fixed.json",
        "val_fixed.json", 
        "test_fixed.json",
        "*.pyc",
        "__pycache__",
    ]
    
    if not args.force:
        print("Files to remove:")
        for pattern in patterns:
            if "*" in pattern:
                for p in DATA_DIR.glob(pattern):
                    print(f"  {p}")
            else:
                p = DATA_DIR / pattern
                if p.exists():
                    print(f"  {p}")
        
        response = input("\nProceed? [y/N] ")
        if response.lower() != "y":
            print("Cancelled")
            return
    
    removed = 0
    for pattern in patterns:
        if "*" in pattern:
            for p in DATA_DIR.glob(pattern):
                if p.is_dir():
                    shutil.rmtree(p)
                else:
                    p.unlink()
                removed += 1
        else:
            p = DATA_DIR / pattern
            if p.exists():
                if p.is_dir():
                    shutil.rmtree(p)
                else:
                    p.unlink()
                removed += 1
    
    print(f"Removed {removed} files/directories")


def cmd_quality(args):
    """Show detailed quality report."""
    import subprocess
    
    file_arg = ["--file", args.file] if args.file else []
    
    result = subprocess.run(
        ["python3", "quality_report.py"] + file_arg,
        cwd=DATA_DIR
    )


def main():
    parser = argparse.ArgumentParser(
        description="Nexus Data Manager",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # Status
    sub = subparsers.add_parser("status", help="Show data status")
    sub.set_defaults(func=cmd_status)
    
    # Build
    sub = subparsers.add_parser("build", help="Build production dataset")
    sub.add_argument("--target", type=int, default=5000, help="Target sample count")
    sub.set_defaults(func=cmd_build)
    
    # Validate
    sub = subparsers.add_parser("validate", help="Validate dataset")
    sub.add_argument("--file", type=str, help="Specific file to validate")
    sub.add_argument("--strict", action="store_true", help="Fail on warnings")
    sub.set_defaults(func=cmd_validate)
    
    # Quality
    sub = subparsers.add_parser("quality", help="Show quality report")
    sub.add_argument("--file", type=str, help="Specific file to analyze")
    sub.set_defaults(func=cmd_quality)
    
    # Export
    sub = subparsers.add_parser("export", help="Export dataset")
    sub.add_argument("--format", choices=["csv", "parquet", "splits"], 
                     default="csv", help="Export format")
    sub.set_defaults(func=cmd_export)
    
    # Clean
    sub = subparsers.add_parser("clean", help="Remove intermediate files")
    sub.add_argument("--force", action="store_true", help="Don't ask for confirmation")
    sub.set_defaults(func=cmd_clean)
    
    args = parser.parse_args()
    
    if args.command is None:
        parser.print_help()
        return
    
    args.func(args)


if __name__ == "__main__":
    main()
