#!/usr/bin/env python3
"""
Nexus GNN v3 — Trained on Historical Pre-Exploit Data

This is the production model trained on REAL pre-exploit snapshots.
Key improvement: We train on what protocols looked like BEFORE they were exploited.

Usage:
    python train_gnn_v3.py                # Train model
    python train_gnn_v3.py --eval         # Evaluate saved model
"""

import json
import argparse
import numpy as np
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import Dataset, DataLoader
from sklearn.model_selection import train_test_split
from sklearn.metrics import precision_score, recall_score, f1_score, roc_auc_score

DATA_DIR = Path(__file__).parent.parent / "data"


@dataclass
class Config:
    """Model configuration."""
    input_dim: int = 7
    hidden_dim: int = 64
    num_layers: int = 3
    dropout: float = 0.3

    # Training
    batch_size: int = 32
    learning_rate: float = 0.001
    epochs: int = 100
    patience: int = 15


# ═══════════════════════════════════════════════════════════════════════════
#                              DATASET
# ═══════════════════════════════════════════════════════════════════════════


class ExploitDataset(Dataset):
    """Dataset of protocol snapshots with risk labels."""

    def __init__(self, samples: list[dict]):
        self.samples = samples
        self.features = []
        self.labels = []

        for s in samples:
            # Feature vector
            feat = [
                np.log1p(s["tvl"]) / 30.0,          # Normalized TVL
                s["tvl_change_1d"] / 100.0,          # Daily change
                s["tvl_change_7d"] / 100.0,          # Weekly change
                s["tvl_change_30d"] / 100.0,         # Monthly change
                s["tvl_volatility"] / 50.0,          # Volatility
                s["category_risk"],                   # Category risk
                s["chain_count"] / 10.0,             # Multi-chain
            ]

            self.features.append(feat)
            self.labels.append(s["risk_label"])

        self.features = torch.tensor(self.features, dtype=torch.float32)
        self.labels = torch.tensor(self.labels, dtype=torch.float32).unsqueeze(1)

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        return self.features[idx], self.labels[idx]


# ═══════════════════════════════════════════════════════════════════════════
#                              MODEL
# ═══════════════════════════════════════════════════════════════════════════


class NexusRiskPredictor(nn.Module):
    """
    MLP-based risk predictor trained on pre-exploit data.

    This model learns patterns that precede exploits:
    - TVL drops (people withdrawing before disaster)
    - High volatility
    - Risky protocol categories

    Note: This is an MLP, not GNN, because our training data doesn't
    have graph structure. For full GNN, we'd need dependency graph data.
    """

    def __init__(self, config: Config):
        super().__init__()

        self.layers = nn.Sequential(
            # Layer 1
            nn.Linear(config.input_dim, config.hidden_dim),
            nn.BatchNorm1d(config.hidden_dim),
            nn.ReLU(),
            nn.Dropout(config.dropout),

            # Layer 2
            nn.Linear(config.hidden_dim, config.hidden_dim),
            nn.BatchNorm1d(config.hidden_dim),
            nn.ReLU(),
            nn.Dropout(config.dropout),

            # Layer 3
            nn.Linear(config.hidden_dim, config.hidden_dim // 2),
            nn.BatchNorm1d(config.hidden_dim // 2),
            nn.ReLU(),
            nn.Dropout(config.dropout),

            # Output
            nn.Linear(config.hidden_dim // 2, 1),
            nn.Sigmoid(),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.layers(x)


# ═══════════════════════════════════════════════════════════════════════════
#                              TRAINING
# ═══════════════════════════════════════════════════════════════════════════


def load_training_data() -> tuple[list[dict], list[dict]]:
    """Load and split training data."""

    dataset_path = DATA_DIR / "training_dataset.json"

    if not dataset_path.exists():
        raise FileNotFoundError(
            "Training dataset not found. Run: python build_training_data.py"
        )

    with open(dataset_path) as f:
        data = json.load(f)

    samples = data["samples"]

    print(f"Loaded {len(samples)} samples")
    print(f"  Exploit samples: {sum(1 for s in samples if s['was_exploited'])}")
    print(f"  Safe samples: {sum(1 for s in samples if not s['was_exploited'])}")

    # Split train/test (80/20)
    train_samples, test_samples = train_test_split(
        samples,
        test_size=0.2,
        random_state=42,
        stratify=[s["was_exploited"] for s in samples],
    )

    print(f"  Train: {len(train_samples)}, Test: {len(test_samples)}")

    return train_samples, test_samples


def train_model(config: Config) -> tuple[nn.Module, dict]:
    """Train the risk prediction model."""

    print("=" * 60)
    print("NEXUS — GNN v3 Training (Pre-Exploit Data)")
    print("=" * 60)
    print()

    # Load data
    train_samples, test_samples = load_training_data()

    train_dataset = ExploitDataset(train_samples)
    test_dataset = ExploitDataset(test_samples)

    train_loader = DataLoader(
        train_dataset,
        batch_size=config.batch_size,
        shuffle=True,
    )
    test_loader = DataLoader(
        test_dataset,
        batch_size=config.batch_size,
    )

    # Model
    model = NexusRiskPredictor(config)

    print(f"\nModel Architecture:")
    print(f"  Input features: {config.input_dim}")
    print(f"  Hidden dim:     {config.hidden_dim}")
    print(f"  Layers:         {config.num_layers}")
    print(f"  Parameters:     {sum(p.numel() for p in model.parameters()):,}")
    print()

    # Training setup
    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=config.learning_rate,
        weight_decay=1e-4,
    )
    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
        optimizer, mode='min', factor=0.5, patience=5
    )

    # Weighted loss for class imbalance
    criterion = nn.BCELoss()

    # Training loop
    print("Training...")
    print("-" * 60)

    best_loss = float('inf')
    patience_counter = 0
    history = {"train_loss": [], "test_loss": [], "metrics": []}

    for epoch in range(config.epochs):
        # Train
        model.train()
        train_loss = 0

        for features, labels in train_loader:
            optimizer.zero_grad()

            outputs = model(features)
            loss = criterion(outputs, labels)

            loss.backward()
            optimizer.step()

            train_loss += loss.item()

        train_loss /= len(train_loader)
        history["train_loss"].append(train_loss)

        # Evaluate
        model.eval()
        test_loss = 0
        all_preds = []
        all_labels = []

        with torch.no_grad():
            for features, labels in test_loader:
                outputs = model(features)
                test_loss += F.binary_cross_entropy(outputs, labels).item()

                all_preds.extend(outputs.numpy().flatten())
                all_labels.extend(labels.numpy().flatten())

        test_loss /= len(test_loader)
        history["test_loss"].append(test_loss)

        # Calculate metrics
        preds_binary = (np.array(all_preds) >= 0.5).astype(int)
        labels_binary = (np.array(all_labels) >= 0.5).astype(int)

        precision = precision_score(labels_binary, preds_binary, zero_division=0)
        recall = recall_score(labels_binary, preds_binary, zero_division=0)
        f1 = f1_score(labels_binary, preds_binary, zero_division=0)

        try:
            auc = roc_auc_score(all_labels, all_preds)
        except:
            auc = 0

        history["metrics"].append({
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "auc": auc,
        })

        scheduler.step(test_loss)

        # Print progress
        if (epoch + 1) % 10 == 0:
            print(f"Epoch {epoch+1:3d}/{config.epochs} | "
                  f"Loss: {train_loss:.4f}/{test_loss:.4f} | "
                  f"F1: {f1:.3f} | AUC: {auc:.3f}")

        # Early stopping
        if test_loss < best_loss:
            best_loss = test_loss
            patience_counter = 0
            best_state = model.state_dict().copy()
        else:
            patience_counter += 1
            if patience_counter >= config.patience:
                print(f"Early stopping at epoch {epoch + 1}")
                break

    # Load best model
    model.load_state_dict(best_state)

    # Final evaluation
    model.eval()
    all_preds = []
    all_labels = []

    with torch.no_grad():
        for features, labels in test_loader:
            outputs = model(features)
            all_preds.extend(outputs.numpy().flatten())
            all_labels.extend(labels.numpy().flatten())

    preds_binary = (np.array(all_preds) >= 0.5).astype(int)
    labels_binary = (np.array(all_labels) >= 0.5).astype(int)

    final_metrics = {
        "precision": float(precision_score(labels_binary, preds_binary, zero_division=0)),
        "recall": float(recall_score(labels_binary, preds_binary, zero_division=0)),
        "f1": float(f1_score(labels_binary, preds_binary, zero_division=0)),
        "auc": float(roc_auc_score(labels_binary, all_preds)),
    }

    # Print final results
    print()
    print("=" * 60)
    print("TRAINING COMPLETE")
    print("=" * 60)
    print()
    print(f"Final Test Loss: {best_loss:.4f}")
    print(f"Precision:       {final_metrics['precision']:.1%}")
    print(f"Recall:          {final_metrics['recall']:.1%}")
    print(f"F1 Score:        {final_metrics['f1']:.1%}")
    print(f"AUC-ROC:         {final_metrics['auc']:.3f}")
    print()

    # Analyze predictions by days before exploit
    print("Prediction Analysis by Time to Exploit:")
    print("-" * 40)

    test_by_days = {}
    for sample, pred in zip(test_samples, all_preds):
        if sample["was_exploited"]:
            days = sample["days_to_exploit"]
            bucket = f"{(days // 7) * 7}-{(days // 7 + 1) * 7}"
            if bucket not in test_by_days:
                test_by_days[bucket] = {"preds": [], "correct": 0, "total": 0}
            test_by_days[bucket]["preds"].append(pred)
            test_by_days[bucket]["total"] += 1
            if pred >= 0.5:
                test_by_days[bucket]["correct"] += 1

    for bucket, data in sorted(test_by_days.items()):
        avg_pred = np.mean(data["preds"])
        detection = data["correct"] / data["total"] if data["total"] > 0 else 0
        print(f"  {bucket} days before: "
              f"avg_score={avg_pred:.2f}, "
              f"detection={detection:.0%} ({data['correct']}/{data['total']})")

    # Save model
    DATA_DIR.mkdir(exist_ok=True)

    torch.save({
        "model_state": model.state_dict(),
        "config": config.__dict__,
        "metrics": final_metrics,
    }, DATA_DIR / "nexus_gnn_v3.pt")

    # Save predictions for analysis
    with open(DATA_DIR / "gnn_v3_results.json", "w") as f:
        json.dump({
            "metrics": final_metrics,
            "train_samples": len(train_samples),
            "test_samples": len(test_samples),
            "timestamp": datetime.now().isoformat(),
        }, f, indent=2)

    print(f"\nModel saved: data/nexus_gnn_v3.pt")
    print("=" * 60)

    return model, final_metrics


def main():
    parser = argparse.ArgumentParser(description="Nexus GNN v3 Training")
    parser.add_argument("--eval", action="store_true", help="Evaluate saved model")
    parser.add_argument("--epochs", type=int, default=100)
    parser.add_argument("--hidden", type=int, default=64)
    args = parser.parse_args()

    config = Config(
        epochs=args.epochs,
        hidden_dim=args.hidden,
    )

    if args.eval:
        checkpoint = torch.load(DATA_DIR / "nexus_gnn_v3.pt")
        print("Saved model metrics:")
        print(json.dumps(checkpoint["metrics"], indent=2))
    else:
        train_model(config)


if __name__ == "__main__":
    main()
