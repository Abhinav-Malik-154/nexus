#!/usr/bin/env python3
"""
Nexus DataLoader — Production PyTorch Dataset Interface

Features:
- Efficient loading from JSON/SQLite
- On-the-fly normalization
- Class-balanced sampling
- Proper feature scaling
- Caching for speed

Usage:
    from data_loader import NexusDataset, get_dataloaders
    
    train_loader, val_loader, test_loader = get_dataloaders(
        data_dir="data/",
        batch_size=32,
        balanced=True
    )
"""

import json
import sqlite3
import numpy as np
from pathlib import Path
from typing import Optional, Tuple, Dict, List
from dataclasses import dataclass

import torch
from torch.utils.data import Dataset, DataLoader, WeightedRandomSampler

# ═══════════════════════════════════════════════════════════════════════════
#                              CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class FeatureConfig:
    """Feature definitions and normalization params."""
    
    # Core features (order matters for model input)
    FEATURES = [
        "tvl_log",
        "tvl_change_1d",
        "tvl_change_7d", 
        "tvl_change_30d",
        "tvl_volatility",
        "price_change_1d",
        "price_change_7d",
        "price_volatility",
        "price_crash_7d",
        "category_risk",
        "chain_count",
        "mcap_to_tvl",
        "age_days",
        "audit_score"
    ]
    
    # Normalization bounds (min, max) for each feature
    BOUNDS = {
        "tvl_log": (0, 1.5),          # log1p(tvl)/30
        "tvl_change_1d": (-100, 100),  # percent
        "tvl_change_7d": (-100, 100),
        "tvl_change_30d": (-100, 100),
        "tvl_volatility": (0, 50),     # std of daily changes
        "price_change_1d": (-100, 100),
        "price_change_7d": (-100, 100),
        "price_volatility": (0, 50),
        "price_crash_7d": (0, 100),
        "category_risk": (0, 1),
        "chain_count": (1, 50),
        "mcap_to_tvl": (0, 10),
        "age_days": (0, 2000),
        "audit_score": (0, 1),
    }
    
    @classmethod
    def normalize(cls, feature: str, value: float) -> float:
        """Normalize a feature value to [0, 1]."""
        if feature not in cls.BOUNDS:
            return value
        
        lo, hi = cls.BOUNDS[feature]
        value = max(lo, min(hi, value))  # Clip
        return (value - lo) / (hi - lo) if hi > lo else 0.0
    
    @classmethod
    def denormalize(cls, feature: str, value: float) -> float:
        """Denormalize from [0, 1] back to original scale."""
        if feature not in cls.BOUNDS:
            return value
        
        lo, hi = cls.BOUNDS[feature]
        return value * (hi - lo) + lo


# ═══════════════════════════════════════════════════════════════════════════
#                              DATASET
# ═══════════════════════════════════════════════════════════════════════════

class NexusDataset(Dataset):
    """
    PyTorch Dataset for Nexus risk prediction.
    
    Loads samples from JSON files and provides normalized feature tensors.
    """
    
    def __init__(
        self,
        samples: List[Dict],
        features: List[str] = None,
        normalize: bool = True,
        label_window: int = 30,  # Days before exploit to label as positive
    ):
        """
        Args:
            samples: List of sample dicts with features and labels
            features: List of feature names to use (default: all)
            normalize: Whether to normalize features
            label_window: Days before exploit to consider as positive class
        """
        self.samples = samples
        self.features = features or FeatureConfig.FEATURES
        self.normalize = normalize
        self.label_window = label_window
        
        # Pre-compute tensors
        self._cache_tensors()
    
    def _cache_tensors(self):
        """Pre-compute feature and label tensors."""
        self.X = []
        self.y = []
        self.meta = []
        
        for s in self.samples:
            # Extract features
            feat_vec = []
            for f in self.features:
                val = s.get(f, 0.0) or 0.0
                if self.normalize:
                    val = FeatureConfig.normalize(f, val)
                feat_vec.append(val)
            
            # Compute label
            # days_to_exploit: negative = days before exploit, positive = days after
            # For training: label=1 if this sample is within N days BEFORE an exploit
            days_to_exploit = s.get("days_to_exploit")
            was_exploited = s.get("was_exploited", False)
            
            # Label as positive if:
            # 1. Protocol was exploited AND
            # 2. Sample is within label_window days BEFORE the exploit (negative days)
            if was_exploited:
                if days_to_exploit is not None and -self.label_window <= days_to_exploit <= 0:
                    label = 1.0
                elif days_to_exploit is None:
                    # If days_to_exploit not set but was_exploited=True, assume it's a positive
                    label = 1.0
                else:
                    # Too far from exploit
                    label = 0.0
            else:
                label = 0.0
            
            self.X.append(feat_vec)
            self.y.append(label)
            self.meta.append({
                "slug": s.get("slug"),
                "date": s.get("date"),
                "protocol": s.get("protocol"),
            })
        
        self.X = torch.tensor(self.X, dtype=torch.float32)
        self.y = torch.tensor(self.y, dtype=torch.float32)
    
    def __len__(self) -> int:
        return len(self.samples)
    
    def __getitem__(self, idx: int) -> Tuple[torch.Tensor, torch.Tensor, Dict]:
        return self.X[idx], self.y[idx], self.meta[idx]
    
    @property
    def num_features(self) -> int:
        return len(self.features)
    
    @property
    def pos_weight(self) -> float:
        """Compute positive class weight for imbalanced data."""
        pos = self.y.sum().item()
        neg = len(self.y) - pos
        return neg / pos if pos > 0 else 1.0
    
    def get_class_weights(self) -> torch.Tensor:
        """Get sample weights for balanced sampling."""
        weights = torch.zeros(len(self.y))
        pos_count = self.y.sum().item()
        neg_count = len(self.y) - pos_count
        
        if pos_count > 0 and neg_count > 0:
            pos_weight = len(self.y) / (2 * pos_count)
            neg_weight = len(self.y) / (2 * neg_count)
            
            weights[self.y == 1] = pos_weight
            weights[self.y == 0] = neg_weight
        else:
            weights.fill_(1.0)
        
        return weights
    
    def stats(self) -> Dict:
        """Compute dataset statistics."""
        pos = int(self.y.sum().item())
        neg = len(self.y) - pos
        
        return {
            "total": len(self.y),
            "positive": pos,
            "negative": neg,
            "pos_ratio": pos / len(self.y) if len(self.y) > 0 else 0,
            "num_features": self.num_features,
            "features": self.features,
        }


# ═══════════════════════════════════════════════════════════════════════════
#                           DATA LOADING
# ═══════════════════════════════════════════════════════════════════════════

def load_samples(filepath: Path) -> List[Dict]:
    """Load samples from JSON file."""
    with open(filepath) as f:
        data = json.load(f)
    
    # Handle both formats: {"samples": [...]} or [...]
    if isinstance(data, dict):
        return data.get("samples", [])
    return data


def get_dataloaders(
    data_dir: str = "data/",
    batch_size: int = 32,
    balanced: bool = True,
    num_workers: int = 0,
    features: List[str] = None,
    label_window: int = 30,
    version: str = "final",
) -> Tuple[DataLoader, DataLoader, DataLoader]:
    """
    Create train/val/test dataloaders.
    
    Args:
        data_dir: Directory containing dataset files
        batch_size: Batch size for training
        balanced: Whether to use balanced sampling for training
        num_workers: Number of data loading workers
        features: List of features to use
        label_window: Days before exploit to consider positive
        version: Dataset version to load ("final", "fixed", "latest")
    
    Returns:
        Tuple of (train_loader, val_loader, test_loader)
    """
    data_path = Path(data_dir)
    
    # Try to load split files (prefer final > fixed > versioned)
    search_order = [
        (f"train_{version}.json", f"val_{version}.json", f"test_{version}.json"),
        ("train_final.json", "val_final.json", "test_final.json"),
        ("train_fixed.json", "val_fixed.json", "test_fixed.json"),
        (f"train_v{version}.json", f"val_v{version}.json", f"test_v{version}.json"),
    ]
    
    train_samples, val_samples, test_samples = None, None, None
    
    for train_name, val_name, test_name in search_order:
        train_path = data_path / train_name
        val_path = data_path / val_name
        test_path = data_path / test_name
        
        if train_path.exists() and val_path.exists() and test_path.exists():
            train_samples = load_samples(train_path)
            val_samples = load_samples(val_path)
            test_samples = load_samples(test_path)
            print(f"Loaded splits: {train_name}, {val_name}, {test_name}")
            break
    
    if train_samples is None:
        # Fall back to single file
        for name in ["dataset_final.json", "dataset_enhanced.json", 
                     "dataset_fixed.json", "dataset_latest.json", 
                     "training_dataset_10x.json"]:
            dataset_path = data_path / name
            if dataset_path.exists():
                print(f"Loading from single file: {name}")
                all_samples = load_samples(dataset_path)
                
                # Temporal split
                sorted_samples = sorted(all_samples, key=lambda x: x.get("date", "2020-01-01"))
                n = len(sorted_samples)
                train_end = int(n * 0.7)
                val_end = int(n * 0.85)
                
                train_samples = sorted_samples[:train_end]
                val_samples = sorted_samples[train_end:val_end]
                test_samples = sorted_samples[val_end:]
                break
    
    if train_samples is None:
        raise FileNotFoundError(f"No dataset files found in {data_path}")
    
    # Create datasets
    train_ds = NexusDataset(train_samples, features=features, label_window=label_window)
    val_ds = NexusDataset(val_samples, features=features, label_window=label_window)
    test_ds = NexusDataset(test_samples, features=features, label_window=label_window)
    
    # Create samplers
    if balanced:
        weights = train_ds.get_class_weights()
        sampler = WeightedRandomSampler(weights, len(weights), replacement=True)
        train_loader = DataLoader(
            train_ds, batch_size=batch_size, sampler=sampler, num_workers=num_workers
        )
    else:
        train_loader = DataLoader(
            train_ds, batch_size=batch_size, shuffle=True, num_workers=num_workers
        )
    
    val_loader = DataLoader(val_ds, batch_size=batch_size, shuffle=False, num_workers=num_workers)
    test_loader = DataLoader(test_ds, batch_size=batch_size, shuffle=False, num_workers=num_workers)
    
    print(f"Loaded datasets:")
    print(f"  Train: {train_ds.stats()['total']} samples ({train_ds.stats()['positive']} pos)")
    print(f"  Val:   {val_ds.stats()['total']} samples ({val_ds.stats()['positive']} pos)")
    print(f"  Test:  {test_ds.stats()['total']} samples ({test_ds.stats()['positive']} pos)")
    
    return train_loader, val_loader, test_loader


def collate_with_meta(batch):
    """Custom collate that preserves metadata."""
    X = torch.stack([b[0] for b in batch])
    y = torch.stack([b[1] for b in batch])
    meta = [b[2] for b in batch]
    return X, y, meta


# ═══════════════════════════════════════════════════════════════════════════
#                           QUICK UTILITIES
# ═══════════════════════════════════════════════════════════════════════════

def prepare_single_sample(
    tvl: float,
    tvl_change_1d: float = 0,
    tvl_change_7d: float = 0,
    tvl_change_30d: float = 0,
    tvl_volatility: float = 0,
    price_change_1d: float = 0,
    price_change_7d: float = 0,
    price_volatility: float = 0,
    price_crash_7d: float = 0,
    category: str = "Unknown",
    chain_count: int = 1,
    mcap_to_tvl: float = 0,
    age_days: int = 365,
    audit_score: float = 0,
) -> torch.Tensor:
    """
    Prepare a single sample for inference.
    
    Returns normalized feature tensor ready for model input.
    """
    from data_pipeline import CATEGORY_RISK
    
    tvl_log = np.log1p(tvl) / 30.0
    category_risk = CATEGORY_RISK.get(category, 0.5)
    
    raw = {
        "tvl_log": tvl_log,
        "tvl_change_1d": tvl_change_1d,
        "tvl_change_7d": tvl_change_7d,
        "tvl_change_30d": tvl_change_30d,
        "tvl_volatility": tvl_volatility,
        "price_change_1d": price_change_1d,
        "price_change_7d": price_change_7d,
        "price_volatility": price_volatility,
        "price_crash_7d": price_crash_7d,
        "category_risk": category_risk,
        "chain_count": chain_count,
        "mcap_to_tvl": mcap_to_tvl,
        "age_days": age_days,
        "audit_score": audit_score,
    }
    
    features = []
    for f in FeatureConfig.FEATURES:
        val = raw.get(f, 0.0)
        features.append(FeatureConfig.normalize(f, val))
    
    return torch.tensor([features], dtype=torch.float32)


# ═══════════════════════════════════════════════════════════════════════════
#                              DEMO
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", default=".")
    parser.add_argument("--batch-size", type=int, default=32)
    args = parser.parse_args()
    
    train_loader, val_loader, test_loader = get_dataloaders(
        data_dir=args.data_dir,
        batch_size=args.batch_size,
    )
    
    # Show sample batch
    for X, y, meta in train_loader:
        print(f"\nSample batch:")
        print(f"  X shape: {X.shape}")
        print(f"  y shape: {y.shape}")
        print(f"  Labels: {y[:10].tolist()}")
        break
