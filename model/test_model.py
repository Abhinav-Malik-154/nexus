#!/usr/bin/env python3
"""
Nexus Model Tests — Unit and Integration Tests

Run with:
    python test_model.py              # Run all tests
    python test_model.py -v           # Verbose output
    python test_model.py TestMLP      # Run specific test class
"""

import unittest
import tempfile
import json
import numpy as np
from pathlib import Path
from unittest.mock import MagicMock, patch

import torch
import torch.nn as nn

# Import modules under test
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "data"))

from risk_model import (
    ModelConfig, TrainingMetrics, 
    NexusMLP, NexusTransformer, ResidualBlock,
    create_model, FocalLoss, Trainer, ModelRegistry, ModelCard
)
from data_loader import NexusDataset, FeatureConfig


class TestModelConfig(unittest.TestCase):
    """Test ModelConfig dataclass."""
    
    def test_default_config(self):
        config = ModelConfig()
        self.assertEqual(config.arch, "mlp")
        self.assertEqual(config.input_dim, 14)
        self.assertEqual(config.hidden_dim, 128)
    
    def test_to_dict(self):
        config = ModelConfig(arch="transformer", hidden_dim=256)
        d = config.to_dict()
        self.assertEqual(d["arch"], "transformer")
        self.assertEqual(d["hidden_dim"], 256)
    
    def test_from_dict(self):
        d = {"arch": "mlp", "hidden_dim": 64, "extra_field": "ignored"}
        config = ModelConfig.from_dict(d)
        self.assertEqual(config.arch, "mlp")
        self.assertEqual(config.hidden_dim, 64)


class TestResidualBlock(unittest.TestCase):
    """Test ResidualBlock."""
    
    def test_forward(self):
        block = ResidualBlock(dim=64, dropout=0.1)
        x = torch.randn(8, 64)
        out = block(x)
        self.assertEqual(out.shape, x.shape)
    
    def test_residual_connection(self):
        """Output should be input + transformed."""
        block = ResidualBlock(dim=32, dropout=0.0)
        block.eval()
        x = torch.ones(1, 32)
        out = block(x)
        # Output should not be identical to input (transformation applied)
        self.assertFalse(torch.allclose(out, x))


class TestNexusMLP(unittest.TestCase):
    """Test NexusMLP model."""
    
    def setUp(self):
        self.config = ModelConfig(
            arch="mlp",
            input_dim=14,
            hidden_dim=64,
            num_layers=2,
            dropout=0.1
        )
        self.model = NexusMLP(self.config)
    
    def test_forward_shape(self):
        x = torch.randn(8, 14)
        out = self.model(x)
        self.assertEqual(out.shape, (8,))
    
    def test_single_sample(self):
        x = torch.randn(1, 14)
        out = self.model(x)
        self.assertEqual(out.shape, (1,))
    
    def test_predict_proba(self):
        x = torch.randn(4, 14)
        probs = self.model.predict_proba(x)
        self.assertTrue(torch.all(probs >= 0))
        self.assertTrue(torch.all(probs <= 1))
    
    def test_gradient_flow(self):
        """Ensure gradients flow through all layers."""
        x = torch.randn(4, 14, requires_grad=True)
        out = self.model(x)
        loss = out.sum()
        loss.backward()
        
        # Check gradients exist
        for name, param in self.model.named_parameters():
            if param.requires_grad:
                self.assertIsNotNone(param.grad, f"No gradient for {name}")


class TestNexusTransformer(unittest.TestCase):
    """Test NexusTransformer model."""
    
    def setUp(self):
        self.config = ModelConfig(
            arch="transformer",
            input_dim=14,
            hidden_dim=64,
            num_layers=2,
            num_heads=4,
            dropout=0.1
        )
        self.model = NexusTransformer(self.config)
    
    def test_forward_shape(self):
        x = torch.randn(8, 14)
        out = self.model(x)
        self.assertEqual(out.shape, (8,))
    
    def test_predict_proba(self):
        x = torch.randn(4, 14)
        probs = self.model.predict_proba(x)
        self.assertTrue(torch.all(probs >= 0))
        self.assertTrue(torch.all(probs <= 1))


class TestCreateModel(unittest.TestCase):
    """Test model factory function."""
    
    def test_create_mlp(self):
        config = ModelConfig(arch="mlp")
        model = create_model(config)
        self.assertIsInstance(model, NexusMLP)
    
    def test_create_transformer(self):
        config = ModelConfig(arch="transformer")
        model = create_model(config)
        self.assertIsInstance(model, NexusTransformer)
    
    def test_invalid_arch(self):
        config = ModelConfig(arch="invalid")
        with self.assertRaises(ValueError):
            create_model(config)


class TestFocalLoss(unittest.TestCase):
    """Test FocalLoss."""
    
    def test_output_shape(self):
        loss_fn = FocalLoss()
        logits = torch.randn(10)
        targets = torch.randint(0, 2, (10,)).float()
        loss = loss_fn(logits, targets)
        self.assertEqual(loss.shape, ())
    
    def test_perfect_prediction(self):
        """Loss should be low for correct predictions."""
        loss_fn = FocalLoss(gamma=2.0)
        # Confident correct predictions
        logits = torch.tensor([5.0, -5.0, 5.0, -5.0])
        targets = torch.tensor([1.0, 0.0, 1.0, 0.0])
        loss = loss_fn(logits, targets)
        self.assertLess(loss.item(), 0.1)
    
    def test_wrong_prediction(self):
        """Loss should be high for wrong predictions."""
        loss_fn = FocalLoss(gamma=2.0)
        # Confident wrong predictions
        logits = torch.tensor([-5.0, 5.0, -5.0, 5.0])
        targets = torch.tensor([1.0, 0.0, 1.0, 0.0])
        loss = loss_fn(logits, targets)
        self.assertGreater(loss.item(), 1.0)


class TestFeatureConfig(unittest.TestCase):
    """Test FeatureConfig normalization."""
    
    def test_normalize_in_range(self):
        # TVL log should normalize to [0, 1]
        norm = FeatureConfig.normalize("tvl_log", 0.75)
        self.assertGreaterEqual(norm, 0)
        self.assertLessEqual(norm, 1)
    
    def test_normalize_clipping(self):
        # Values outside range should be clipped
        norm = FeatureConfig.normalize("tvl_change_1d", 200)
        self.assertEqual(norm, 1.0)  # Clipped to max
        
        norm = FeatureConfig.normalize("tvl_change_1d", -200)
        self.assertEqual(norm, 0.0)  # Clipped to min
    
    def test_denormalize_roundtrip(self):
        original = 50.0
        normalized = FeatureConfig.normalize("tvl_change_1d", original)
        denormalized = FeatureConfig.denormalize("tvl_change_1d", normalized)
        self.assertAlmostEqual(original, denormalized, places=5)


class TestNexusDataset(unittest.TestCase):
    """Test NexusDataset."""
    
    def setUp(self):
        self.samples = [
            {
                "slug": "proto1",
                "date": "2024-01-01",
                "tvl_log": 0.7,
                "tvl_change_1d": 5.0,
                "tvl_change_7d": -10.0,
                "tvl_change_30d": 2.0,
                "tvl_volatility": 3.0,
                "price_change_1d": 2.0,
                "price_change_7d": -5.0,
                "price_volatility": 8.0,
                "price_crash_7d": 15.0,
                "category_risk": 0.6,
                "chain_count": 5,
                "mcap_to_tvl": 0.5,
                "age_days": 365,
                "audit_score": 0.8,
                "was_exploited": True,
                "days_to_exploit": -10,
            },
            {
                "slug": "proto2",
                "date": "2024-01-02",
                "tvl_log": 0.5,
                "tvl_change_1d": 1.0,
                "tvl_change_7d": 3.0,
                "tvl_change_30d": 10.0,
                "tvl_volatility": 2.0,
                "price_change_1d": 1.0,
                "price_change_7d": 2.0,
                "price_volatility": 5.0,
                "price_crash_7d": 5.0,
                "category_risk": 0.3,
                "chain_count": 2,
                "mcap_to_tvl": 0.2,
                "age_days": 500,
                "audit_score": 0.9,
                "was_exploited": False,
            },
        ]
    
    def test_len(self):
        ds = NexusDataset(self.samples)
        self.assertEqual(len(ds), 2)
    
    def test_getitem(self):
        ds = NexusDataset(self.samples)
        X, y, meta = ds[0]
        self.assertEqual(X.shape, (14,))
        self.assertIsInstance(y.item(), float)
        self.assertEqual(meta["slug"], "proto1")
    
    def test_labels(self):
        ds = NexusDataset(self.samples, label_window=30)
        # First sample: exploited, days_to_exploit=-10 (within window)
        self.assertEqual(ds.y[0].item(), 1.0)
        # Second sample: not exploited
        self.assertEqual(ds.y[1].item(), 0.0)
    
    def test_pos_weight(self):
        ds = NexusDataset(self.samples)
        weight = ds.pos_weight
        self.assertIsInstance(weight, float)
        self.assertGreater(weight, 0)


class TestModelRegistry(unittest.TestCase):
    """Test ModelRegistry."""
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.registry = ModelRegistry(Path(self.temp_dir))
    
    def test_save_and_load(self):
        config = ModelConfig(arch="mlp", hidden_dim=32, num_layers=1)
        model = create_model(config)
        metrics = TrainingMetrics(f1=0.75, auc_roc=0.85)
        
        path = self.registry.save(
            model=model,
            config=config,
            metrics=metrics,
            train_size=100,
            val_size=20,
            test_size=20,
            version="test_v1"
        )
        
        self.assertTrue(path.exists())
        
        # Load it back
        loaded_model, loaded_config, loaded_metrics = self.registry.load(path)
        self.assertEqual(loaded_config.arch, "mlp")
        self.assertEqual(loaded_config.hidden_dim, 32)
    
    def test_list_models(self):
        config = ModelConfig(arch="mlp", hidden_dim=32, num_layers=1)
        model = create_model(config)
        metrics = TrainingMetrics(f1=0.75, auc_roc=0.85)
        
        self.registry.save(model, config, metrics, 100, 20, 20, "v1")
        self.registry.save(model, config, metrics, 100, 20, 20, "v2")
        
        models = self.registry.list_models()
        self.assertEqual(len(models), 2)


class TestTrainer(unittest.TestCase):
    """Test Trainer class."""
    
    def test_train_epoch(self):
        config = ModelConfig(arch="mlp", hidden_dim=32, num_layers=1)
        model = create_model(config)
        trainer = Trainer(model, config)
        
        # Create dummy data
        X = torch.randn(20, 14)
        y = torch.randint(0, 2, (20,)).float()
        
        class DummyDataset(torch.utils.data.Dataset):
            def __len__(self): return len(X)
            def __getitem__(self, i): return X[i], y[i], {}
        
        loader = torch.utils.data.DataLoader(DummyDataset(), batch_size=4)
        loss = trainer.train_epoch(loader)
        
        self.assertIsInstance(loss, float)
        self.assertGreater(loss, 0)
    
    def test_evaluate(self):
        config = ModelConfig(arch="mlp", hidden_dim=32, num_layers=1)
        model = create_model(config)
        trainer = Trainer(model, config)
        
        # Create dummy data with both classes
        X = torch.randn(20, 14)
        y = torch.tensor([1.0]*10 + [0.0]*10)
        
        class DummyDataset(torch.utils.data.Dataset):
            def __len__(self): return len(X)
            def __getitem__(self, i): return X[i], y[i], {}
        
        loader = torch.utils.data.DataLoader(DummyDataset(), batch_size=4)
        loss, metrics = trainer.evaluate(loader)
        
        self.assertIn("f1", metrics)
        self.assertIn("precision", metrics)
        self.assertIn("recall", metrics)
        self.assertIn("auc_roc", metrics)


class TestIntegration(unittest.TestCase):
    """Integration tests."""
    
    def test_end_to_end_training(self):
        """Test complete training pipeline."""
        # Small model for fast test
        config = ModelConfig(
            arch="mlp",
            hidden_dim=16,
            num_layers=1,
            epochs=5,
            patience=3,
            batch_size=4
        )
        
        # Create synthetic data
        samples = []
        for i in range(50):
            samples.append({
                "slug": f"proto{i}",
                "date": "2024-01-01",
                "protocol": f"Protocol {i}",
                "tvl_log": np.random.uniform(0.3, 0.9),
                "tvl_change_1d": np.random.normal(0, 5),
                "tvl_change_7d": np.random.normal(0, 10),
                "tvl_change_30d": np.random.normal(0, 15),
                "tvl_volatility": np.random.uniform(0, 10),
                "price_change_1d": np.random.normal(0, 3),
                "price_change_7d": np.random.normal(0, 8),
                "price_volatility": np.random.uniform(2, 15),
                "price_crash_7d": np.random.uniform(0, 30),
                "category_risk": np.random.uniform(0.2, 0.8),
                "chain_count": np.random.randint(1, 10),
                "mcap_to_tvl": np.random.uniform(0, 2),
                "age_days": np.random.randint(30, 1000),
                "audit_score": np.random.uniform(0.3, 0.9),
                "was_exploited": i < 20,  # 40% exploited
                "days_to_exploit": -np.random.randint(1, 30) if i < 20 else -100,
            })
        
        train_ds = NexusDataset(samples[:35])
        val_ds = NexusDataset(samples[35:])
        
        train_loader = torch.utils.data.DataLoader(train_ds, batch_size=config.batch_size, shuffle=True)
        val_loader = torch.utils.data.DataLoader(val_ds, batch_size=config.batch_size)
        
        model = create_model(config)
        trainer = Trainer(model, config)
        
        metrics = trainer.fit(train_loader, val_loader, verbose=False)
        
        self.assertGreater(metrics.epochs_trained, 0)
        # F1 might be 0 on small random data, just verify it's computed
        self.assertGreaterEqual(metrics.f1, 0)


if __name__ == "__main__":
    unittest.main()
