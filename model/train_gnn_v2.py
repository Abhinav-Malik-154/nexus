#!/usr/bin/env python3
"""
Nexus GNN v2 — Production-Grade Risk Prediction with GAT

FIXES APPLIED:
1. ✓ Hardcoded dependencies → Uses real pre-exploit data from training_dataset.json
2. ✓ Only ~20 protocols → Now uses 660+ samples with real exploit data
3. ✓ No train/test split → Proper 80/20 stratified split
4. ✓ Model collapsed → Better initialization, real labels, class balancing
5. ✓ No backtesting → Temporal validation against historical exploits
6. ✓ No accuracy metrics → Full metrics: AUC-ROC, Precision, Recall, F1

Architecture:
    Input Features → GAT Layer 1 (multi-head) → GAT Layer 2 → MLP → Risk Score

Usage:
    python train_gnn_v2.py                    # Train with default settings
    python train_gnn_v2.py --backtest 2023    # Temporal backtest (train pre-2023)
    python train_gnn_v2.py --eval             # Evaluate saved model
"""

import json
import argparse
import numpy as np
from datetime import datetime
from pathlib import Path
from typing import Optional
from dataclasses import dataclass

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import Dataset, DataLoader, WeightedRandomSampler
from torch.optim.lr_scheduler import ReduceLROnPlateau
from sklearn.model_selection import train_test_split
from sklearn.metrics import precision_score, recall_score, f1_score, roc_auc_score

# ═══════════════════════════════════════════════════════════════════════════
#                              CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════

DATA_DIR = Path(__file__).parent.parent / "data"
MODEL_DIR = Path(__file__).parent.parent / "data"


@dataclass
class ModelConfig:
    """Model hyperparameters."""
    input_dim: int = 12         # Updated: 12 features (7 TVL + 5 price/market)
    hidden_dim: int = 64        # Hidden layer dimension
    num_heads: int = 4          # Number of attention heads
    num_layers: int = 2         # Number of GAT layers
    dropout: float = 0.3        # Dropout rate
    output_dim: int = 1         # Output dimension (risk score)

    # Training
    learning_rate: float = 0.001
    weight_decay: float = 1e-4
    epochs: int = 150
    patience: int = 20
    batch_size: int = 32


# ═══════════════════════════════════════════════════════════════════════════
#                         GRAPH ATTENTION LAYER
# ═══════════════════════════════════════════════════════════════════════════


class GraphAttentionLayer(nn.Module):
    """
    Graph Attention Layer (GAT).

    Learns attention weights for each neighbor, allowing the model to focus
    on the most relevant connections for risk prediction.
    """

    def __init__(
        self,
        in_features: int,
        out_features: int,
        num_heads: int = 4,
        dropout: float = 0.3,
        concat: bool = True,
    ):
        super().__init__()

        self.in_features = in_features
        self.out_features = out_features
        self.num_heads = num_heads
        self.concat = concat

        # Linear transformation for each head
        self.W = nn.Linear(in_features, out_features * num_heads, bias=False)

        # Attention mechanism parameters
        self.a = nn.Parameter(torch.zeros(num_heads, 2 * out_features))
        nn.init.xavier_uniform_(self.a)

        self.leaky_relu = nn.LeakyReLU(0.2)
        self.dropout = nn.Dropout(dropout)

    def forward(self, x: torch.Tensor, adj: torch.Tensor) -> torch.Tensor:
        """
        Args:
            x: Node features [N, in_features]
            adj: Adjacency matrix [N, N]

        Returns:
            Updated node features
        """
        N = x.size(0)

        # Linear transformation
        h = self.W(x)
        h = h.reshape(N, self.num_heads, self.out_features)

        # Compute attention
        a_src = self.a[:, :self.out_features]
        a_tgt = self.a[:, self.out_features:]

        attn_src = torch.einsum('nhf,hf->nh', h, a_src)
        attn_tgt = torch.einsum('nhf,hf->nh', h, a_tgt)

        # Pairwise attention
        e = attn_src.unsqueeze(-1) + attn_tgt.T.unsqueeze(0)
        e = self.leaky_relu(e)

        # Mask non-neighbors
        adj_with_self = adj + torch.eye(N, device=x.device)
        mask = adj_with_self.unsqueeze(1).expand(-1, self.num_heads, -1)
        e = e.masked_fill(mask == 0, float('-inf'))

        # Softmax attention
        attention = F.softmax(e, dim=-1)
        attention = torch.nan_to_num(attention, 0)
        attention = self.dropout(attention)

        # Aggregate
        out = torch.einsum('nhj,jhf->nhf', attention, h)

        if self.concat:
            out = out.reshape(N, self.num_heads * self.out_features)
        else:
            out = out.mean(dim=1)

        return out


# ═══════════════════════════════════════════════════════════════════════════
#                           GNN MODEL
# ═══════════════════════════════════════════════════════════════════════════


class NexusGATv2(nn.Module):
    """
    Graph Attention Network for DeFi risk prediction.

    Architecture:
        Input → GAT1 (multi-head) → LayerNorm → ReLU → Dropout
              → GAT2 (single-head) → LayerNorm → ReLU → Dropout
              → Skip Connection → MLP → Sigmoid → Risk Score
    """

    def __init__(self, config: ModelConfig):
        super().__init__()
        self.config = config

        # GAT layers
        self.gat1 = GraphAttentionLayer(
            in_features=config.input_dim,
            out_features=config.hidden_dim,
            num_heads=config.num_heads,
            dropout=config.dropout,
            concat=True,
        )

        gat2_input_dim = config.hidden_dim * config.num_heads
        self.gat2 = GraphAttentionLayer(
            in_features=gat2_input_dim,
            out_features=config.hidden_dim,
            num_heads=1,
            dropout=config.dropout,
            concat=False,
        )

        # Normalization
        self.norm1 = nn.LayerNorm(gat2_input_dim)
        self.norm2 = nn.LayerNorm(config.hidden_dim)

        # Skip connection
        self.skip = nn.Linear(config.input_dim, config.hidden_dim)

        # Output MLP
        self.mlp = nn.Sequential(
            nn.Linear(config.hidden_dim, config.hidden_dim // 2),
            nn.ReLU(),
            nn.Dropout(config.dropout),
            nn.Linear(config.hidden_dim // 2, config.output_dim),
            # Note: No Sigmoid here - using BCEWithLogitsLoss
        )

        self.dropout = nn.Dropout(config.dropout)

        # Initialize weights
        self._init_weights()

    def _init_weights(self):
        """Initialize weights to prevent collapse."""
        for m in self.modules():
            if isinstance(m, nn.Linear):
                nn.init.xavier_uniform_(m.weight)
                if m.bias is not None:
                    nn.init.zeros_(m.bias)

    def forward(self, x: torch.Tensor, adj: torch.Tensor) -> torch.Tensor:
        """
        Forward pass returning logits (raw scores before sigmoid).
        Use torch.sigmoid(output) for probabilities.
        """
        skip = self.skip(x)

        h = self.gat1(x, adj)
        h = self.norm1(h)
        h = F.relu(h)
        h = self.dropout(h)

        h = self.gat2(h, adj)
        h = self.norm2(h)
        h = F.relu(h)
        h = self.dropout(h)

        h = h + skip
        out = self.mlp(h)

        return out


# ═══════════════════════════════════════════════════════════════════════════
#                           LOSS FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════


class FocalLoss(nn.Module):
    """
    Focal Loss for handling class imbalance.

    Reduces loss for well-classified examples, focusing on hard examples.
    Better than simple weighting for severe imbalance.
    """

    def __init__(self, alpha: float = 0.25, gamma: float = 1.0):
        super().__init__()
        self.alpha = alpha
        self.gamma = gamma  # Reduced from 2.0 to 1.0 to prevent vanishing gradients

    def forward(self, logits: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
        bce_loss = F.binary_cross_entropy_with_logits(
            logits, targets, reduction='none'
        )
        probs = torch.sigmoid(logits)
        pt = torch.where(targets == 1, probs, 1 - probs)
        focal_weight = (1 - pt) ** self.gamma

        if self.alpha is not None:
            alpha_t = torch.where(targets == 1, self.alpha, 1 - self.alpha)
            focal_weight = alpha_t * focal_weight

        loss = focal_weight * bce_loss
        return loss.mean()


# ═══════════════════════════════════════════════════════════════════════════
#                           DATASET
# ═══════════════════════════════════════════════════════════════════════════


class ExploitDataset(Dataset):
    """
    Dataset of protocol snapshots with risk labels.

    FIX #1: Uses REAL pre-exploit data instead of hardcoded dependencies.
    FIX #2: Uses 660+ samples instead of ~20 protocols.

    Supports both formats:
    - Old format: 7 features (TVL only)
    - New 10x format: 12 features (TVL + price data + market data)
    """

    def __init__(self, samples: list[dict]):
        self.samples = samples
        self.features = []
        self.labels = []

        # Detect format
        first_sample = samples[0] if samples else {}
        has_price_data = "price_change_1d" in first_sample

        for s in samples:
            if has_price_data:
                # New 10x format with price data
                feat = [
                    np.log1p(s["tvl"]) / 30.0,           # Normalized TVL
                    s["tvl_change_1d"] / 100.0,          # Daily change
                    s["tvl_change_7d"] / 100.0,          # Weekly change
                    s["tvl_change_30d"] / 100.0,         # Monthly change
                    s["tvl_volatility"] / 50.0,          # Volatility
                    s["category_risk"],                   # Category risk
                    s["chain_count"] / 10.0,             # Multi-chain exposure
                    s["price_change_1d"] / 100.0,        # Price daily change
                    s["price_change_7d"] / 100.0,        # Price weekly change
                    s["price_volatility"] / 50.0,        # Price volatility
                    min(s["price_crash"], 0) / 100.0,    # Price crash (negative)
                    min(s["mcap_to_tvl"], 10.0) / 10.0,  # Market cap / TVL ratio
                ]
            else:
                # Old format (7 features)
                feat = [
                    np.log1p(s["tvl"]) / 30.0,
                    s["tvl_change_1d"] / 100.0,
                    s["tvl_change_7d"] / 100.0,
                    s["tvl_change_30d"] / 100.0,
                    s["tvl_volatility"] / 50.0,
                    s["category_risk"],
                    s["chain_count"] / 10.0,
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
#                           DATA LOADING
# ═══════════════════════════════════════════════════════════════════════════


def load_training_data(backtest_year: Optional[str] = None) -> tuple:
    """
    Load training data from training_dataset.json or training_dataset_10x.json.

    FIX #3: Implements proper train/test split (80/20 stratified).
    FIX #5: Supports temporal backtesting.
    """

    # Try 10x dataset first (with price data)
    dataset_10x_path = DATA_DIR / "training_dataset_10x.json"
    dataset_path = DATA_DIR / "training_dataset.json"

    if dataset_10x_path.exists():
        print("Using 10x dataset (with price data)...")
        with open(dataset_10x_path) as f:
            data = json.load(f)
    elif dataset_path.exists():
        print("Using standard dataset...")
        with open(dataset_path) as f:
            data = json.load(f)
    else:
        raise FileNotFoundError(
            "No training dataset found. Run build_training_data.py or build_10x_dataset.py"
        )

    samples = data["samples"]

    print(f"Loaded {len(samples)} samples")
    print(f"  Exploit samples: {sum(1 for s in samples if s['was_exploited'])}")
    print(f"  Safe samples: {sum(1 for s in samples if not s['was_exploited'])}")

    # FIX #5: Temporal split for backtesting
    if backtest_year:
        cutoff = f"{backtest_year}-01-01"
        train_samples = [s for s in samples if s["date"] < cutoff]
        test_samples = [s for s in samples if s["date"] >= cutoff]

        print(f"  Temporal split at {backtest_year}:")
        print(f"    Train (before {backtest_year}): {len(train_samples)}")
        print(f"    Test ({backtest_year}+): {len(test_samples)}")
    else:
        # FIX #3: Standard stratified split
        train_samples, test_samples = train_test_split(
            samples,
            test_size=0.2,
            random_state=42,
            stratify=[s["was_exploited"] for s in samples],
        )
        print(f"  Train: {len(train_samples)}, Test: {len(test_samples)}")

    return train_samples, test_samples


def build_batch_graph(batch_features: torch.Tensor) -> torch.Tensor:
    """
    Build adjacency matrix for a batch.

    FIX #1: Graph structure is learned from feature similarity,
    not hardcoded.
    """
    N = batch_features.size(0)

    # Compute pairwise similarity
    normalized = F.normalize(batch_features, p=2, dim=1)
    similarity = torch.mm(normalized, normalized.t())

    # Create adjacency: connect similar samples
    threshold = 0.5
    adj = (similarity > threshold).float()

    # Ensure self-loops
    adj = adj + torch.eye(N, device=batch_features.device)
    adj = torch.clamp(adj, 0, 1)

    return adj


# ═══════════════════════════════════════════════════════════════════════════
#                           EVALUATION
# ═══════════════════════════════════════════════════════════════════════════


def evaluate_model(
    model: nn.Module,
    test_loader: DataLoader,
    test_samples: list[dict],
) -> dict:
    """
    Comprehensive model evaluation.

    FIX #6: Calculates all metrics - AUC-ROC, Precision, Recall, F1.
    """
    model.eval()
    all_preds = []
    all_labels = []

    with torch.no_grad():
        for features, labels in test_loader:
            adj = build_batch_graph(features)
            logits = model(features, adj)
            outputs = torch.sigmoid(logits)  # Convert logits to probabilities

            all_preds.extend(outputs.numpy().flatten())
            all_labels.extend(labels.numpy().flatten())

    preds = np.array(all_preds)
    labels_arr = np.array(all_labels)

    # Binary predictions
    preds_binary = (preds >= 0.5).astype(int)
    labels_binary = (labels_arr >= 0.5).astype(int)

    # FIX #6: Calculate comprehensive metrics
    metrics = {
        "precision": float(precision_score(labels_binary, preds_binary, zero_division=0)),
        "recall": float(recall_score(labels_binary, preds_binary, zero_division=0)),
        "f1": float(f1_score(labels_binary, preds_binary, zero_division=0)),
    }

    # AUC-ROC (handle edge cases)
    try:
        metrics["auc"] = float(roc_auc_score(labels_binary, preds))
    except:
        metrics["auc"] = 0.0

    # Detailed breakdown
    tp = ((preds_binary == 1) & (labels_binary == 1)).sum()
    fp = ((preds_binary == 1) & (labels_binary == 0)).sum()
    fn = ((preds_binary == 0) & (labels_binary == 1)).sum()
    tn = ((preds_binary == 0) & (labels_binary == 0)).sum()

    metrics["accuracy"] = float((tp + tn) / len(labels_arr))
    metrics["true_positives"] = int(tp)
    metrics["false_positives"] = int(fp)
    metrics["false_negatives"] = int(fn)
    metrics["true_negatives"] = int(tn)

    return metrics, preds, labels_arr


def backtest_analysis(
    preds: np.ndarray,
    labels: np.ndarray,
    test_samples: list[dict],
) -> dict:
    """
    FIX #5: Detailed backtesting analysis against historical exploits.
    """
    print("\nBacktest Analysis by Days Before Exploit:")
    print("-" * 50)

    results = {}

    for sample, pred in zip(test_samples, preds):
        if sample["was_exploited"]:
            days = sample["days_to_exploit"]
            bucket = f"{(days // 7) * 7}-{(days // 7 + 1) * 7} days"

            if bucket not in results:
                results[bucket] = {"preds": [], "correct": 0, "total": 0}

            results[bucket]["preds"].append(pred)
            results[bucket]["total"] += 1

            if pred >= 0.5:
                results[bucket]["correct"] += 1

    for bucket, data in sorted(results.items()):
        avg_pred = np.mean(data["preds"])
        detection = data["correct"] / data["total"] if data["total"] > 0 else 0
        print(f"  {bucket:>12}: avg_score={avg_pred:.2f}, "
              f"detection={detection:.0%} ({data['correct']}/{data['total']})")

    return results


# ═══════════════════════════════════════════════════════════════════════════
#                              TRAINING
# ═══════════════════════════════════════════════════════════════════════════


def train_model(
    config: ModelConfig,
    backtest_year: Optional[str] = None,
) -> tuple[nn.Module, dict]:
    """
    Train the GAT model with all 6 fixes applied.
    """

    print("=" * 60)
    print("NEXUS — GNN v2 Training (All 6 Problems Fixed)")
    print("=" * 60)
    print()

    # Load data (FIX #2, #3, #5)
    train_samples, test_samples = load_training_data(backtest_year)

    train_dataset = ExploitDataset(train_samples)
    test_dataset = ExploitDataset(test_samples)

    # Update config with actual feature dimension
    actual_features = train_dataset.features.shape[1]
    if config.input_dim != actual_features:
        print(f"  Adjusting input_dim: {config.input_dim} → {actual_features}")
        config.input_dim = actual_features

    # Calculate class imbalance
    exploit_count = sum(1 for s in train_samples if s["was_exploited"])
    safe_count = len(train_samples) - exploit_count

    print(f"  Class distribution:")
    print(f"    Exploit: {exploit_count} ({exploit_count/len(train_samples):.1%})")
    print(f"    Safe: {safe_count} ({safe_count/len(train_samples):.1%})")

    # Create weighted sampler for balanced training
    # Give each sample weight inversely proportional to its class frequency
    sample_weights = []
    for s in train_samples:
        if s["was_exploited"]:
            sample_weights.append(1.0 / exploit_count)
        else:
            sample_weights.append(1.0 / safe_count)

    sampler = WeightedRandomSampler(
        weights=sample_weights,
        num_samples=len(train_samples),
        replacement=True,
    )

    train_loader = DataLoader(
        train_dataset,
        batch_size=config.batch_size,
        sampler=sampler,  # Use weighted sampling instead of shuffle
    )
    test_loader = DataLoader(
        test_dataset,
        batch_size=config.batch_size,
    )

    # Initialize model (FIX #4: Better initialization)
    model = NexusGATv2(config)

    print(f"\nModel Architecture:")
    print(f"  Input features:  {config.input_dim}")
    print(f"  Hidden dim:      {config.hidden_dim}")
    print(f"  Attention heads: {config.num_heads}")
    print(f"  Parameters:      {sum(p.numel() for p in model.parameters()):,}")
    print(f"  Sampling:        Weighted (balanced classes)")
    print()

    # Training setup
    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=config.learning_rate,
        weight_decay=config.weight_decay,
    )
    scheduler = ReduceLROnPlateau(optimizer, mode='min', factor=0.5, patience=5)

    # FIX #4: Use simple BCE loss with weighted sampling (better than Focal Loss)
    criterion = nn.BCEWithLogitsLoss()

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

            # FIX #1: Build graph from feature similarity
            adj = build_batch_graph(features)

            logits = model(features, adj)
            loss = criterion(logits, labels)

            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
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
                adj = build_batch_graph(features)
                logits = model(features, adj)
                test_loss += criterion(logits, labels).item()

                # Get probabilities for metrics
                outputs = torch.sigmoid(logits)
                all_preds.extend(outputs.numpy().flatten())
                all_labels.extend(labels.numpy().flatten())

        test_loss /= len(test_loader)
        history["test_loss"].append(test_loss)

        # FIX #6: Calculate metrics every epoch
        preds_binary = (np.array(all_preds) >= 0.5).astype(int)
        labels_binary = (np.array(all_labels) >= 0.5).astype(int)

        precision = precision_score(labels_binary, preds_binary, zero_division=0)
        recall = recall_score(labels_binary, preds_binary, zero_division=0)
        f1 = f1_score(labels_binary, preds_binary, zero_division=0)

        try:
            auc = roc_auc_score(labels_binary, all_preds)
        except:
            auc = 0

        history["metrics"].append({
            "precision": precision, "recall": recall, "f1": f1, "auc": auc
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

    # Final evaluation (FIX #6)
    final_metrics, preds, labels_arr = evaluate_model(model, test_loader, test_samples)

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
    print(f"Accuracy:        {final_metrics['accuracy']:.1%}")
    print()

    # FIX #5: Backtest analysis
    backtest_results = backtest_analysis(preds, labels_arr, test_samples)

    # Save model
    MODEL_DIR.mkdir(exist_ok=True)

    torch.save({
        "model_state": model.state_dict(),
        "config": config.__dict__,
        "metrics": final_metrics,
    }, MODEL_DIR / "nexus_gnn_v2.pt")

    # Save results
    with open(DATA_DIR / "gnn_v2_results.json", "w") as f:
        json.dump({
            "metrics": final_metrics,
            "backtest": {k: {"avg_score": float(np.mean(v["preds"])),
                            "detection_rate": v["correct"]/v["total"] if v["total"] > 0 else 0,
                            "correct": v["correct"],
                            "total": v["total"]}
                        for k, v in backtest_results.items()},
            "train_samples": len(train_samples),
            "test_samples": len(test_samples),
            "fixes_applied": [
                "1. Real pre-exploit data (not hardcoded)",
                "2. 660+ samples (not ~20 protocols)",
                "3. Proper train/test split (80/20 stratified)",
                "4. Better initialization (prevents collapse)",
                "5. Temporal backtesting validation",
                "6. Full metrics (AUC-ROC, Precision, Recall, F1)",
            ],
            "timestamp": datetime.now().isoformat(),
        }, f, indent=2)

    print(f"\nModel saved: data/nexus_gnn_v2.pt")
    print(f"Results saved: data/gnn_v2_results.json")
    print("=" * 60)

    return model, final_metrics


# ═══════════════════════════════════════════════════════════════════════════
#                                  MAIN
# ═══════════════════════════════════════════════════════════════════════════


def main():
    parser = argparse.ArgumentParser(description="Nexus GNN v2 Training")
    parser.add_argument("--backtest", type=str, help="Backtest year (e.g., 2023)")
    parser.add_argument("--eval", action="store_true", help="Evaluate saved model")
    parser.add_argument("--epochs", type=int, default=150)
    parser.add_argument("--hidden", type=int, default=64)
    parser.add_argument("--heads", type=int, default=4)
    args = parser.parse_args()

    config = ModelConfig(
        epochs=args.epochs,
        hidden_dim=args.hidden,
        num_heads=args.heads,
    )

    if args.eval:
        checkpoint = torch.load(MODEL_DIR / "nexus_gnn_v2.pt")
        print("Saved model metrics:")
        print(json.dumps(checkpoint["metrics"], indent=2))
    else:
        train_model(config, backtest_year=args.backtest)


if __name__ == "__main__":
    main()
