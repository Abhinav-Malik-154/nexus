# Nexus Data Module

Production-grade data infrastructure for DeFi risk prediction.

## Quick Start

```bash
# Check current data status
python manage_data.py status

# Build production dataset (5000 samples)
python manage_data.py build --target 5000

# Validate data quality
python manage_data.py validate

# Show quality report
python manage_data.py quality
```

## Files

| File | Purpose |
|------|---------|
| `manage_data.py` | **Main CLI** - unified data operations |
| `data_loader.py` | PyTorch DataLoader interface |
| `data_pipeline.py` | Full ETL pipeline (fetch/build/validate) |
| `data_enhancer.py` | Dataset expansion with synthetic samples |
| `validate_data.py` | Quality gates for CI/CD |
| `quality_report.py` | Data quality metrics |
| `fix_features.py` | Fix broken features in existing data |
| `bootstrap_db.py` | Import JSON to SQLite |

## Datasets

| File | Samples | Quality | Purpose |
|------|---------|---------|---------|
| `dataset_final.json` | 5000 | 10.0/10 | Production training |
| `train_final.json` | 3500 | - | Training split |
| `val_final.json` | 750 | - | Validation split |
| `test_final.json` | 750 | - | Test split |

## Usage in Training

```python
from data_loader import get_dataloaders

train_loader, val_loader, test_loader = get_dataloaders(
    data_dir="data/",
    batch_size=32,
    balanced=True,
)

for X, y, meta in train_loader:
    # X: [batch, 14] features
    # y: [batch] labels (0=safe, 1=exploit)
    # meta: list of dicts with slug/date/protocol
    ...
```

## Features (14 total)

| Feature | Range | Description |
|---------|-------|-------------|
| tvl_log | 0-1 | log1p(TVL)/30, normalized TVL |
| tvl_change_1d | -100,100 | 1-day TVL % change |
| tvl_change_7d | -100,100 | 7-day TVL % change |
| tvl_change_30d | -100,100 | 30-day TVL % change |
| tvl_volatility | 0-50 | TVL volatility (std) |
| price_change_1d | -100,100 | 1-day price % change |
| price_change_7d | -100,100 | 7-day price % change |
| price_volatility | 0-50 | Price volatility |
| price_crash_7d | 0-100 | Max 7-day drawdown |
| category_risk | 0-1 | Protocol category risk |
| chain_count | 1-50 | Number of chains |
| mcap_to_tvl | 0-10 | Market cap / TVL ratio |
| age_days | 0-2000 | Protocol age in days |
| audit_score | 0-1 | Audit quality score |

## Quality Gates

The validation suite checks:
- Class balance (30-70% exploited)
- Sample count (1000+ required)
- Protocol diversity (30+ protocols)
- Temporal coverage (1+ year span)
- Feature distributions (no >30% zeros)
- Data leakage (temporal split validation)

Run in CI/CD:
```bash
python validate_data.py --strict && echo "Ready for training"
```
