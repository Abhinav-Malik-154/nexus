#!/usr/bin/env python3
"""
Nexus Risk Model — Production-Grade DeFi Risk Prediction

A clean, production-ready implementation that:
- Uses the enhanced 14-feature dataset
- Implements proper train/val/test evaluation
- Supports multiple architectures (MLP, Transformer)
- Exports to ONNX for deployment
- Includes comprehensive metrics and model cards

Usage:
    python risk_model.py train                    # Train default model
    python risk_model.py train --arch transformer # Train transformer
    python risk_model.py eval                     # Evaluate saved model
    python risk_model.py export --format onnx    # Export for deployment
    python risk_model.py predict --protocol aave # Single prediction
"""

import json
import argparse
import hashlib
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, asdict, field
from typing import Optional, Dict, List, Tuple, Any

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import DataLoader, WeightedRandomSampler

# Add parent to path for data imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "data"))
from data_loader import NexusDataset, FeatureConfig, load_samples

DATA_DIR = Path(__file__).parent.parent / "data"
MODEL_DIR = Path(__file__).parent / "checkpoints"


# ═══════════════════════════════════════════════════════════════════════════
#                              CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class ModelConfig:
    """Model hyperparameters."""
    # Architecture
    arch: str = "mlp"  # "mlp", "transformer"
    input_dim: int = 14
    hidden_dim: int = 128
    num_layers: int = 3
    num_heads: int = 4  # For transformer
    dropout: float = 0.2
    
    # Training
    batch_size: int = 64
    learning_rate: float = 1e-3
    weight_decay: float = 1e-4
    epochs: int = 100
    patience: int = 15
    
    # Data
    label_window: int = 30  # Days before exploit to label positive
    balanced_sampling: bool = True
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, d: Dict) -> "ModelConfig":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass 
class TrainingMetrics:
    """Training results and metrics."""
    # Performance
    train_loss: float = 0.0
    val_loss: float = 0.0
    test_loss: float = 0.0
    
    # Classification metrics
    precision: float = 0.0
    recall: float = 0.0
    f1: float = 0.0
    auc_roc: float = 0.0
    
    # Calibration
    brier_score: float = 0.0
    
    # Training info
    epochs_trained: int = 0
    best_epoch: int = 0
    training_time_sec: float = 0.0
    
    def to_dict(self) -> Dict:
        return asdict(self)


# ═══════════════════════════════════════════════════════════════════════════
#                              MODELS
# ═══════════════════════════════════════════════════════════════════════════

class ResidualBlock(nn.Module):
    """Residual MLP block with skip connection."""
    
    def __init__(self, dim: int, dropout: float = 0.2):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(dim, dim),
            nn.LayerNorm(dim),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(dim, dim),
            nn.LayerNorm(dim),
        )
        self.dropout = nn.Dropout(dropout)
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return x + self.dropout(self.net(x))


class NexusMLP(nn.Module):
    """
    Production MLP for risk prediction.
    
    Architecture:
        Input → Projection → [ResidualBlock] × N → Output
    
    Uses residual connections, layer norm, and GELU activation
    for stable training and good generalization.
    """
    
    def __init__(self, config: ModelConfig):
        super().__init__()
        self.config = config
        
        # Input projection
        self.input_proj = nn.Sequential(
            nn.Linear(config.input_dim, config.hidden_dim),
            nn.LayerNorm(config.hidden_dim),
            nn.GELU(),
            nn.Dropout(config.dropout),
        )
        
        # Residual blocks
        self.blocks = nn.ModuleList([
            ResidualBlock(config.hidden_dim, config.dropout)
            for _ in range(config.num_layers)
        ])
        
        # Output head
        self.head = nn.Sequential(
            nn.Linear(config.hidden_dim, config.hidden_dim // 2),
            nn.GELU(),
            nn.Linear(config.hidden_dim // 2, 1),
        )
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.input_proj(x)
        for block in self.blocks:
            x = block(x)
        return self.head(x).squeeze(-1)
    
    def predict_proba(self, x: torch.Tensor) -> torch.Tensor:
        """Get probability predictions."""
        with torch.no_grad():
            logits = self.forward(x)
            return torch.sigmoid(logits)


class NexusTransformer(nn.Module):
    """
    Transformer-based risk predictor.
    
    Treats features as a sequence and applies self-attention
    to learn feature interactions.
    """
    
    def __init__(self, config: ModelConfig):
        super().__init__()
        self.config = config
        
        # Feature embedding (each feature gets its own embedding)
        self.feature_embed = nn.Linear(1, config.hidden_dim)
        self.pos_embed = nn.Parameter(torch.randn(1, config.input_dim, config.hidden_dim) * 0.02)
        
        # Transformer encoder
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=config.hidden_dim,
            nhead=config.num_heads,
            dim_feedforward=config.hidden_dim * 4,
            dropout=config.dropout,
            activation='gelu',
            batch_first=True,
        )
        self.encoder = nn.TransformerEncoder(encoder_layer, num_layers=config.num_layers)
        
        # Output head
        self.head = nn.Sequential(
            nn.LayerNorm(config.hidden_dim),
            nn.Linear(config.hidden_dim, 1),
        )
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # x: [B, F] -> [B, F, 1] -> [B, F, H]
        x = x.unsqueeze(-1)
        x = self.feature_embed(x)
        x = x + self.pos_embed
        
        x = self.encoder(x)
        
        # Pool over features
        x = x.mean(dim=1)
        
        return self.head(x).squeeze(-1)
    
    def predict_proba(self, x: torch.Tensor) -> torch.Tensor:
        with torch.no_grad():
            logits = self.forward(x)
            return torch.sigmoid(logits)


def create_model(config: ModelConfig) -> nn.Module:
    """Factory function to create model."""
    if config.arch == "mlp":
        return NexusMLP(config)
    elif config.arch == "transformer":
        return NexusTransformer(config)
    else:
        raise ValueError(f"Unknown architecture: {config.arch}")


# ═══════════════════════════════════════════════════════════════════════════
#                              TRAINING
# ═══════════════════════════════════════════════════════════════════════════

class FocalLoss(nn.Module):
    """Focal loss for handling class imbalance."""
    
    def __init__(self, alpha: float = 0.25, gamma: float = 2.0):
        super().__init__()
        self.alpha = alpha
        self.gamma = gamma
    
    def forward(self, logits: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
        probs = torch.sigmoid(logits)
        ce_loss = F.binary_cross_entropy_with_logits(logits, targets, reduction='none')
        
        p_t = probs * targets + (1 - probs) * (1 - targets)
        alpha_t = self.alpha * targets + (1 - self.alpha) * (1 - targets)
        focal_weight = alpha_t * (1 - p_t) ** self.gamma
        
        return (focal_weight * ce_loss).mean()


class Trainer:
    """Model trainer with early stopping and metrics tracking."""
    
    def __init__(
        self,
        model: nn.Module,
        config: ModelConfig,
        device: str = "cpu"
    ):
        self.model = model.to(device)
        self.config = config
        self.device = device
        
        self.optimizer = torch.optim.AdamW(
            model.parameters(),
            lr=config.learning_rate,
            weight_decay=config.weight_decay,
        )
        self.scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
            self.optimizer, mode='min', factor=0.5, patience=5, min_lr=1e-6
        )
        self.criterion = FocalLoss(alpha=0.75, gamma=2.0)  # Higher alpha for minority class
        
        self.best_val_loss = float('inf')
        self.best_state = None
        self.patience_counter = 0
        self.history = {"train_loss": [], "val_loss": [], "metrics": []}
    
    def train_epoch(self, loader: DataLoader) -> float:
        self.model.train()
        total_loss = 0.0
        
        for X, y, _ in loader:
            X, y = X.to(self.device), y.to(self.device)
            
            self.optimizer.zero_grad()
            logits = self.model(X)
            loss = self.criterion(logits, y)
            loss.backward()
            
            # Gradient clipping
            torch.nn.utils.clip_grad_norm_(self.model.parameters(), 1.0)
            
            self.optimizer.step()
            total_loss += loss.item()
        
        return total_loss / len(loader)
    
    @torch.no_grad()
    def evaluate(self, loader: DataLoader) -> Tuple[float, Dict]:
        self.model.eval()
        total_loss = 0.0
        all_probs, all_labels = [], []
        
        for X, y, _ in loader:
            X, y = X.to(self.device), y.to(self.device)
            
            logits = self.model(X)
            loss = self.criterion(logits, y)
            total_loss += loss.item()
            
            probs = torch.sigmoid(logits)
            all_probs.extend(probs.cpu().numpy())
            all_labels.extend(y.cpu().numpy())
        
        avg_loss = total_loss / len(loader)
        metrics = self._compute_metrics(np.array(all_probs), np.array(all_labels))
        
        return avg_loss, metrics
    
    def _compute_metrics(self, probs: np.ndarray, labels: np.ndarray) -> Dict:
        from sklearn.metrics import precision_score, recall_score, f1_score, roc_auc_score, brier_score_loss
        
        # Find optimal threshold based on F1
        best_f1, best_thresh = 0, 0.5
        for thresh in np.arange(0.1, 0.9, 0.05):
            preds = (probs >= thresh).astype(int)
            f1 = f1_score(labels.astype(int), preds, zero_division=0)
            if f1 > best_f1:
                best_f1 = f1
                best_thresh = thresh
        
        preds = (probs >= best_thresh).astype(int)
        labels_int = labels.astype(int)
        
        metrics = {
            "precision": float(precision_score(labels_int, preds, zero_division=0)),
            "recall": float(recall_score(labels_int, preds, zero_division=0)),
            "f1": float(f1_score(labels_int, preds, zero_division=0)),
            "brier": float(brier_score_loss(labels, probs)),
            "threshold": float(best_thresh),
        }
        
        try:
            metrics["auc_roc"] = float(roc_auc_score(labels, probs))
        except ValueError:
            metrics["auc_roc"] = 0.0
        
        return metrics
    
    def fit(
        self,
        train_loader: DataLoader,
        val_loader: DataLoader,
        verbose: bool = True
    ) -> TrainingMetrics:
        import time
        start_time = time.time()
        
        if verbose:
            print(f"\nTraining {self.config.arch.upper()} model...")
            print(f"  Parameters: {sum(p.numel() for p in self.model.parameters()):,}")
            print(f"  Train samples: {len(train_loader.dataset)}")
            print(f"  Val samples: {len(val_loader.dataset)}")
            print()
        
        for epoch in range(self.config.epochs):
            train_loss = self.train_epoch(train_loader)
            val_loss, val_metrics = self.evaluate(val_loader)
            
            self.history["train_loss"].append(train_loss)
            self.history["val_loss"].append(val_loss)
            self.history["metrics"].append(val_metrics)
            
            self.scheduler.step(val_loss)
            
            # Early stopping
            if val_loss < self.best_val_loss:
                self.best_val_loss = val_loss
                self.best_state = {k: v.cpu().clone() for k, v in self.model.state_dict().items()}
                self.patience_counter = 0
            else:
                self.patience_counter += 1
            
            if verbose and (epoch + 1) % 10 == 0:
                print(f"Epoch {epoch+1:3d} | Train: {train_loss:.4f} | Val: {val_loss:.4f} | "
                      f"F1: {val_metrics['f1']:.3f} | AUC: {val_metrics['auc_roc']:.3f}")
            
            if self.patience_counter >= self.config.patience:
                if verbose:
                    print(f"Early stopping at epoch {epoch + 1}")
                break
        
        # Load best model
        if self.best_state:
            self.model.load_state_dict(self.best_state)
        
        training_time = time.time() - start_time
        
        # Final evaluation
        _, final_metrics = self.evaluate(val_loader)
        
        return TrainingMetrics(
            train_loss=self.history["train_loss"][-1],
            val_loss=self.best_val_loss,
            precision=final_metrics["precision"],
            recall=final_metrics["recall"],
            f1=final_metrics["f1"],
            auc_roc=final_metrics["auc_roc"],
            brier_score=final_metrics["brier"],
            epochs_trained=len(self.history["train_loss"]),
            best_epoch=len(self.history["train_loss"]) - self.patience_counter,
            training_time_sec=training_time,
        )


# ═══════════════════════════════════════════════════════════════════════════
#                              MODEL REGISTRY
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class ModelCard:
    """Model metadata and documentation."""
    name: str
    version: str
    arch: str
    created_at: str
    
    # Performance
    metrics: Dict
    
    # Data
    train_samples: int
    val_samples: int
    test_samples: int
    features: List[str]
    
    # Config
    config: Dict
    
    # Checksum
    checksum: str
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    def save(self, path: Path):
        with open(path, "w") as f:
            json.dump(self.to_dict(), f, indent=2)
    
    @classmethod
    def load(cls, path: Path) -> "ModelCard":
        with open(path) as f:
            return cls(**json.load(f))


class ModelRegistry:
    """Manage model versions and checkpoints."""
    
    def __init__(self, model_dir: Path = MODEL_DIR):
        self.model_dir = model_dir
        self.model_dir.mkdir(parents=True, exist_ok=True)
    
    def save(
        self,
        model: nn.Module,
        config: ModelConfig,
        metrics: TrainingMetrics,
        train_size: int,
        val_size: int,
        test_size: int,
        version: str = None,
    ) -> Path:
        """Save model with metadata."""
        
        if version is None:
            version = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        name = f"nexus_{config.arch}_{version}"
        
        # Save model weights
        model_path = self.model_dir / f"{name}.pt"
        torch.save({
            "model_state": model.state_dict(),
            "config": config.to_dict(),
            "metrics": metrics.to_dict(),
        }, model_path)
        
        # Compute checksum
        with open(model_path, "rb") as f:
            checksum = hashlib.md5(f.read()).hexdigest()[:12]
        
        # Create model card
        card = ModelCard(
            name=name,
            version=version,
            arch=config.arch,
            created_at=datetime.now().isoformat(),
            metrics=metrics.to_dict(),
            train_samples=train_size,
            val_samples=val_size,
            test_samples=test_size,
            features=FeatureConfig.FEATURES,
            config=config.to_dict(),
            checksum=checksum,
        )
        
        card_path = self.model_dir / f"{name}_card.json"
        card.save(card_path)
        
        # Update latest symlink
        latest_path = self.model_dir / "latest.pt"
        if latest_path.exists():
            latest_path.unlink()
        latest_path.symlink_to(model_path.name)
        
        return model_path
    
    def load(self, path: Path = None) -> Tuple[nn.Module, ModelConfig, Dict]:
        """Load model from checkpoint."""
        
        if path is None:
            path = self.model_dir / "latest.pt"
        
        if not path.exists():
            raise FileNotFoundError(f"No model found at {path}")
        
        checkpoint = torch.load(path, map_location="cpu")
        config = ModelConfig.from_dict(checkpoint["config"])
        model = create_model(config)
        model.load_state_dict(checkpoint["model_state"])
        model.eval()
        
        return model, config, checkpoint.get("metrics", {})
    
    def list_models(self) -> List[Dict]:
        """List all saved models."""
        models = []
        for card_path in self.model_dir.glob("*_card.json"):
            card = ModelCard.load(card_path)
            models.append({
                "name": card.name,
                "version": card.version,
                "arch": card.arch,
                "f1": card.metrics.get("f1", 0),
                "auc": card.metrics.get("auc_roc", 0),
                "created": card.created_at,
            })
        return sorted(models, key=lambda x: x["created"], reverse=True)


# ═══════════════════════════════════════════════════════════════════════════
#                              CLI COMMANDS
# ═══════════════════════════════════════════════════════════════════════════

def cmd_train(args):
    """Train a new model."""
    
    config = ModelConfig(
        arch=args.arch,
        hidden_dim=args.hidden,
        num_layers=args.layers,
        dropout=args.dropout,
        epochs=args.epochs,
        batch_size=args.batch_size,
        learning_rate=args.lr,
    )
    
    print("="*60)
    print("NEXUS RISK MODEL — TRAINING")
    print("="*60)
    print(f"Architecture: {config.arch.upper()}")
    print(f"Hidden dim:   {config.hidden_dim}")
    print(f"Layers:       {config.num_layers}")
    print()
    
    # Load data
    print("Loading data...")
    
    train_path = DATA_DIR / "train_final.json"
    val_path = DATA_DIR / "val_final.json"
    test_path = DATA_DIR / "test_final.json"
    
    if not all(p.exists() for p in [train_path, val_path, test_path]):
        print("Error: Dataset splits not found. Run: python manage_data.py build")
        return
    
    train_samples = load_samples(train_path)
    val_samples = load_samples(val_path)
    test_samples = load_samples(test_path)
    
    train_ds = NexusDataset(train_samples, label_window=config.label_window)
    val_ds = NexusDataset(val_samples, label_window=config.label_window)
    test_ds = NexusDataset(test_samples, label_window=config.label_window)
    
    print(f"  Train: {len(train_ds)} samples ({int(train_ds.y.sum())} positive)")
    print(f"  Val:   {len(val_ds)} samples ({int(val_ds.y.sum())} positive)")
    print(f"  Test:  {len(test_ds)} samples ({int(test_ds.y.sum())} positive)")
    
    # Create dataloaders
    if config.balanced_sampling:
        weights = train_ds.get_class_weights()
        sampler = WeightedRandomSampler(weights, len(weights), replacement=True)
        train_loader = DataLoader(train_ds, batch_size=config.batch_size, sampler=sampler)
    else:
        train_loader = DataLoader(train_ds, batch_size=config.batch_size, shuffle=True)
    
    val_loader = DataLoader(val_ds, batch_size=config.batch_size)
    test_loader = DataLoader(test_ds, batch_size=config.batch_size)
    
    # Create and train model
    model = create_model(config)
    trainer = Trainer(model, config)
    metrics = trainer.fit(train_loader, val_loader)
    
    # Evaluate on test set
    test_loss, test_metrics = trainer.evaluate(test_loader)
    metrics.test_loss = test_loss
    
    print()
    print("="*60)
    print("TRAINING COMPLETE")
    print("="*60)
    print(f"Test Loss:   {test_loss:.4f}")
    print(f"Precision:   {test_metrics['precision']:.1%}")
    print(f"Recall:      {test_metrics['recall']:.1%}")
    print(f"F1 Score:    {test_metrics['f1']:.1%}")
    print(f"AUC-ROC:     {test_metrics['auc_roc']:.3f}")
    print(f"Brier Score: {test_metrics['brier']:.4f}")
    print()
    
    # Save model
    registry = ModelRegistry()
    model_path = registry.save(
        model=model,
        config=config,
        metrics=metrics,
        train_size=len(train_ds),
        val_size=len(val_ds),
        test_size=len(test_ds),
    )
    
    print(f"Model saved: {model_path}")
    print("="*60)


def cmd_eval(args):
    """Evaluate a saved model."""
    
    registry = ModelRegistry()
    
    if args.model:
        model_path = Path(args.model)
    else:
        model_path = None
    
    model, config, saved_metrics = registry.load(model_path)
    
    print("="*60)
    print("NEXUS RISK MODEL — EVALUATION")
    print("="*60)
    print(f"Model: {config.arch.upper()}")
    print()
    
    # Load test data
    test_path = DATA_DIR / "test_final.json"
    if not test_path.exists():
        print("Error: Test data not found")
        return
    
    test_samples = load_samples(test_path)
    test_ds = NexusDataset(test_samples, label_window=config.label_window)
    test_loader = DataLoader(test_ds, batch_size=config.batch_size)
    
    # Evaluate
    trainer = Trainer(model, config)
    test_loss, metrics = trainer.evaluate(test_loader)
    
    print("SAVED METRICS:")
    for k, v in saved_metrics.items():
        if isinstance(v, float):
            print(f"  {k}: {v:.4f}")
    
    print()
    print("CURRENT EVALUATION:")
    print(f"  Loss:      {test_loss:.4f}")
    print(f"  Precision: {metrics['precision']:.1%}")
    print(f"  Recall:    {metrics['recall']:.1%}")
    print(f"  F1:        {metrics['f1']:.1%}")
    print(f"  AUC-ROC:   {metrics['auc_roc']:.3f}")
    print("="*60)


def cmd_export(args):
    """Export model for deployment."""
    
    registry = ModelRegistry()
    model, config, _ = registry.load()
    model.eval()
    
    if args.format == "onnx":
        try:
            import onnx
            
            output_path = MODEL_DIR / "nexus_model.onnx"
            dummy_input = torch.randn(1, config.input_dim)
            
            torch.onnx.export(
                model,
                dummy_input,
                output_path,
                input_names=["features"],
                output_names=["risk_score"],
                dynamic_axes={
                    "features": {0: "batch_size"},
                    "risk_score": {0: "batch_size"},
                },
                opset_version=14,
            )
            
            print(f"Exported ONNX model: {output_path}")
            
        except ImportError:
            print("Error: onnx package required. Install with: pip install onnx")
    
    elif args.format == "torchscript":
        output_path = MODEL_DIR / "nexus_model.ts"
        
        traced = torch.jit.trace(model, torch.randn(1, config.input_dim))
        traced.save(str(output_path))
        
        print(f"Exported TorchScript model: {output_path}")
    
    else:
        print(f"Unknown format: {args.format}")


def cmd_predict(args):
    """Single protocol prediction."""
    import requests
    
    registry = ModelRegistry()
    model, config, _ = registry.load()
    model.eval()
    
    # Fetch protocol data
    print(f"Fetching data for {args.protocol}...")
    
    try:
        resp = requests.get(
            f"https://api.llama.fi/protocol/{args.protocol}",
            timeout=30
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f"Error fetching protocol: {e}")
        return
    
    # Extract features
    tvl = data.get("tvl", 0)
    if isinstance(tvl, list):
        tvl_history = tvl
        tvl = tvl_history[-1].get("totalLiquidityUSD", 0) if tvl_history else 0
    
    # This is simplified - in production you'd compute all features
    from data_loader import prepare_single_sample
    
    features = prepare_single_sample(
        tvl=tvl,
        tvl_change_1d=data.get("change_1d", 0),
        tvl_change_7d=data.get("change_7d", 0),
        category=data.get("category", "Unknown"),
        chain_count=len(data.get("chains", [])),
    )
    
    # Predict
    with torch.no_grad():
        logits = model(features)
        prob = torch.sigmoid(logits).item()
    
    risk_pct = prob * 100
    
    if risk_pct >= 70:
        level = "🔴 CRITICAL"
    elif risk_pct >= 55:
        level = "🟠 HIGH"
    elif risk_pct >= 40:
        level = "🟡 MEDIUM"
    else:
        level = "🟢 LOW"
    
    print()
    print("="*60)
    print(f"NEXUS RISK PREDICTION: {data.get('name', args.protocol)}")
    print("="*60)
    print(f"TVL:        ${tvl/1e9:.2f}B" if tvl > 1e9 else f"TVL:        ${tvl/1e6:.0f}M")
    print(f"Category:   {data.get('category', 'Unknown')}")
    print(f"Chains:     {len(data.get('chains', []))}")
    print()
    print(f"Risk Score: {risk_pct:.1f}%")
    print(f"Risk Level: {level}")
    print("="*60)


def cmd_list(args):
    """List saved models."""
    
    registry = ModelRegistry()
    models = registry.list_models()
    
    if not models:
        print("No models found")
        return
    
    print()
    print(f"{'Name':<40} {'Arch':<12} {'F1':<8} {'AUC':<8} {'Created'}")
    print("-"*90)
    
    for m in models:
        print(f"{m['name']:<40} {m['arch']:<12} {m['f1']:.3f}    {m['auc']:.3f}    {m['created'][:19]}")


def main():
    parser = argparse.ArgumentParser(description="Nexus Risk Model")
    subparsers = parser.add_subparsers(dest="command")
    
    # Train
    p = subparsers.add_parser("train", help="Train a new model")
    p.add_argument("--arch", choices=["mlp", "transformer"], default="mlp")
    p.add_argument("--hidden", type=int, default=128)
    p.add_argument("--layers", type=int, default=3)
    p.add_argument("--dropout", type=float, default=0.2)
    p.add_argument("--epochs", type=int, default=100)
    p.add_argument("--batch-size", type=int, default=64)
    p.add_argument("--lr", type=float, default=1e-3)
    p.set_defaults(func=cmd_train)
    
    # Eval
    p = subparsers.add_parser("eval", help="Evaluate model")
    p.add_argument("--model", type=str, help="Model path")
    p.set_defaults(func=cmd_eval)
    
    # Export
    p = subparsers.add_parser("export", help="Export model")
    p.add_argument("--format", choices=["onnx", "torchscript"], default="onnx")
    p.set_defaults(func=cmd_export)
    
    # Predict
    p = subparsers.add_parser("predict", help="Single prediction")
    p.add_argument("--protocol", type=str, required=True)
    p.set_defaults(func=cmd_predict)
    
    # List
    p = subparsers.add_parser("list", help="List models")
    p.set_defaults(func=cmd_list)
    
    args = parser.parse_args()
    
    if args.command is None:
        parser.print_help()
        return
    
    args.func(args)


if __name__ == "__main__":
    main()
