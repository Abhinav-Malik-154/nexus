# Nexus Model Module

Production-grade DeFi risk prediction models.

## Quick Start

```bash
# Train a model
python risk_model.py train

# Evaluate
python risk_model.py eval

# Single prediction
python risk_model.py predict --protocol aave

# List models
python risk_model.py list

# Export for deployment
python risk_model.py export --format onnx
```

## Architecture

### MLP (Default)
- **ResidualBlock**: Linear → LayerNorm → GELU → Dropout → Linear → LayerNorm
- **Skip connections** for gradient flow
- **Focal Loss** to handle class imbalance
- **Automatic threshold optimization** during evaluation

### Transformer
- Each feature embedded independently
- Self-attention over feature sequence
- Mean pooling over features
- Better for capturing feature interactions

## Files

| File | Purpose |
|------|---------|
| `risk_model.py` | **Main CLI** - train, eval, export |
| `inference.py` | Production inference engine |
| `test_model.py` | Unit tests (29 tests) |
| `checkpoints/` | Saved model weights |

## Usage in Code

```python
from inference import RiskPredictor

predictor = RiskPredictor()

# Single prediction
result = predictor.predict("aave")
print(f"Risk: {result.risk_score}% ({result.risk_level})")

# Batch prediction
results = predictor.predict_batch(["aave", "compound", "lido"])

# Scan top protocols
alerts = predictor.get_alerts(threshold=55.0)
```

## Model Card

The latest model is documented in `checkpoints/*_card.json`:

```json
{
  "name": "nexus_mlp_20260328",
  "arch": "mlp",
  "metrics": {
    "precision": 0.201,
    "recall": 0.708,
    "f1": 0.312,
    "auc_roc": 0.662
  },
  "features": ["tvl_log", "tvl_change_1d", ...]
}
```

## Features (14)

| Feature | Range | Description |
|---------|-------|-------------|
| tvl_log | 0-1 | Normalized log TVL |
| tvl_change_1d | -100,100 | 1-day TVL change % |
| tvl_change_7d | -100,100 | 7-day TVL change % |
| tvl_change_30d | -100,100 | 30-day TVL change % |
| tvl_volatility | 0-50 | TVL volatility |
| price_change_1d | -100,100 | 1-day price change % |
| price_change_7d | -100,100 | 7-day price change % |
| price_volatility | 0-50 | Price volatility |
| price_crash_7d | 0-100 | Max 7-day drawdown |
| category_risk | 0-1 | Protocol category risk |
| chain_count | 1-50 | Number of chains |
| mcap_to_tvl | 0-10 | Market cap / TVL ratio |
| age_days | 0-2000 | Protocol age |
| audit_score | 0-1 | Audit quality |

## Training

```bash
# Train MLP (recommended)
python risk_model.py train --arch mlp --hidden 128 --layers 3

# Train Transformer
python risk_model.py train --arch transformer --hidden 64 --layers 2

# With custom hyperparameters
python risk_model.py train \
  --arch mlp \
  --hidden 256 \
  --layers 4 \
  --dropout 0.3 \
  --lr 0.0005 \
  --epochs 200
```

## Tests

```bash
python test_model.py -v  # 29 tests
```

## Deployment

Export to ONNX for deployment:

```bash
python risk_model.py export --format onnx
# Creates checkpoints/nexus_model.onnx
```

Or TorchScript:

```bash
python risk_model.py export --format torchscript
# Creates checkpoints/nexus_model.ts
```
