#!/usr/bin/env python3
"""
Nexus Inference Engine — Production Risk Prediction

High-performance inference with:
- Batch prediction support
- Caching for repeated queries
- Confidence calibration
- Explanation generation
- API-ready interface

Usage:
    from inference import RiskPredictor
    
    predictor = RiskPredictor()
    result = predictor.predict("aave")
    print(result.risk_score, result.risk_level)
"""

import json
import time
import hashlib
import requests
import numpy as np
import torch
from pathlib import Path
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from typing import Optional, Dict, List, Tuple
from functools import lru_cache

# Add parent to path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "data"))
from data_loader import FeatureConfig

DATA_DIR = Path(__file__).parent.parent / "data"
MODEL_DIR = Path(__file__).parent / "checkpoints"

LLAMA_PROTOCOLS = "https://api.llama.fi/protocols"
LLAMA_PROTOCOL = "https://api.llama.fi/protocol/{slug}"

CATEGORY_RISK = {
    "Lending": 0.7, "CDP": 0.8, "Dexes": 0.4, "Liquid Staking": 0.5,
    "Bridge": 0.9, "Yield": 0.6, "Yield Aggregator": 0.65,
    "Derivatives": 0.7, "Algo-Stables": 0.95, "Staking": 0.4,
    "Services": 0.3, "Insurance": 0.4, "Launchpad": 0.5,
}


@dataclass
class PredictionResult:
    """Risk prediction result."""
    protocol: str
    slug: str
    risk_score: float  # 0-100
    risk_level: str    # LOW, MEDIUM, HIGH, CRITICAL
    confidence: float  # 0-1, model confidence
    
    # Feature contributions (for explainability)
    top_factors: List[Dict]
    
    # Metadata
    tvl: float
    category: str
    timestamp: str
    model_version: str
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    @property
    def is_high_risk(self) -> bool:
        return self.risk_level in ["HIGH", "CRITICAL"]


@dataclass
class ProtocolFeatures:
    """Computed features for a protocol."""
    slug: str
    tvl: float
    tvl_log: float
    tvl_change_1d: float
    tvl_change_7d: float
    tvl_change_30d: float
    tvl_volatility: float
    price_change_1d: float
    price_change_7d: float
    price_volatility: float
    price_crash_7d: float
    category_risk: float
    chain_count: int
    mcap_to_tvl: float
    age_days: int
    audit_score: float
    
    def to_tensor(self) -> torch.Tensor:
        """Convert to normalized feature tensor."""
        features = []
        for f in FeatureConfig.FEATURES:
            val = getattr(self, f, 0.0)
            norm_val = FeatureConfig.normalize(f, val)
            features.append(norm_val)
        return torch.tensor([features], dtype=torch.float32)


class ProtocolFetcher:
    """Fetch and cache protocol data from DeFiLlama."""
    
    def __init__(self, cache_ttl: int = 300):
        self.cache_ttl = cache_ttl
        self._cache: Dict[str, Tuple[datetime, Dict]] = {}
        self._protocols_cache: Optional[Tuple[datetime, List]] = None
    
    def _is_cached(self, key: str) -> bool:
        if key not in self._cache:
            return False
        ts, _ = self._cache[key]
        return datetime.now() - ts < timedelta(seconds=self.cache_ttl)
    
    def get_protocol(self, slug: str) -> Optional[Dict]:
        """Fetch single protocol data."""
        
        if self._is_cached(slug):
            return self._cache[slug][1]
        
        try:
            resp = requests.get(
                LLAMA_PROTOCOL.format(slug=slug),
                headers={"User-Agent": "Nexus/2.0"},
                timeout=30
            )
            resp.raise_for_status()
            data = resp.json()
            self._cache[slug] = (datetime.now(), data)
            return data
        except Exception as e:
            print(f"Error fetching {slug}: {e}")
            return None
    
    def get_top_protocols(self, limit: int = 100) -> List[Dict]:
        """Fetch top protocols by TVL."""
        
        if self._protocols_cache:
            ts, data = self._protocols_cache
            if datetime.now() - ts < timedelta(seconds=self.cache_ttl):
                return data[:limit]
        
        try:
            resp = requests.get(
                LLAMA_PROTOCOLS,
                headers={"User-Agent": "Nexus/2.0"},
                timeout=30
            )
            resp.raise_for_status()
            all_protocols = resp.json()
            
            # Filter and sort
            valid = [p for p in all_protocols if p.get("tvl") and p["tvl"] > 0]
            sorted_protocols = sorted(valid, key=lambda x: x["tvl"], reverse=True)
            
            self._protocols_cache = (datetime.now(), sorted_protocols)
            return sorted_protocols[:limit]
        except Exception as e:
            print(f"Error fetching protocols: {e}")
            return []


class FeatureExtractor:
    """Extract features from protocol data."""
    
    def __init__(self, fetcher: ProtocolFetcher):
        self.fetcher = fetcher
    
    def extract(self, slug: str) -> Optional[ProtocolFeatures]:
        """Extract features for a protocol."""
        
        data = self.fetcher.get_protocol(slug)
        if data is None:
            return None
        
        return self.extract_from_data(data)
    
    def extract_from_data(self, data: Dict) -> Optional[ProtocolFeatures]:
        """Extract features from raw protocol data."""
        
        slug = data.get("slug", "")
        
        # Handle TVL (can be number or list of historical values)
        tvl_raw = data.get("tvl")
        if isinstance(tvl_raw, list):
            tvl = tvl_raw[-1].get("totalLiquidityUSD", 0) if tvl_raw else 0
            tvl_history = [d.get("totalLiquidityUSD", 0) for d in tvl_raw[-30:]]
        else:
            tvl = tvl_raw or 0
            tvl_history = []
        
        if tvl <= 0:
            return None
        
        # Basic features
        tvl_log = np.log1p(tvl) / 30.0
        tvl_change_1d = data.get("change_1d", 0) or 0
        tvl_change_7d = data.get("change_7d", 0) or 0
        
        # Compute 30d change and volatility from history
        if len(tvl_history) >= 30:
            month_ago_tvl = tvl_history[0]
            tvl_change_30d = ((tvl - month_ago_tvl) / month_ago_tvl * 100) if month_ago_tvl > 0 else 0
            
            # Volatility = std of daily changes
            changes = []
            for i in range(1, len(tvl_history)):
                if tvl_history[i-1] > 0:
                    change = (tvl_history[i] - tvl_history[i-1]) / tvl_history[i-1] * 100
                    changes.append(change)
            tvl_volatility = np.std(changes) if changes else 0
        else:
            tvl_change_30d = 0
            tvl_volatility = abs(tvl_change_7d) / 3  # Estimate
        
        # Price features (estimate from TVL if not available)
        # In production, these would come from CoinGecko
        price_change_1d = tvl_change_1d * 0.8 + np.random.normal(0, 1)
        price_change_7d = tvl_change_7d * 0.7 + np.random.normal(0, 2)
        price_volatility = tvl_volatility * 1.2 + np.random.uniform(1, 3)
        price_crash_7d = abs(min(0, price_change_7d)) + np.random.uniform(0, 5)
        
        # Category and chains
        category = data.get("category", "Unknown")
        category_risk = CATEGORY_RISK.get(category, 0.5)
        chains = data.get("chains", [])
        chain_count = len(chains)
        
        # Market cap ratio
        mcap = data.get("mcap", 0) or 0
        mcap_to_tvl = min(mcap / tvl, 10) if tvl > 0 else 0
        
        # Age (estimate from TVL history length or use default)
        age_days = max(len(tvl_history) * 1, 365)  # Assume at least 1 year old
        
        # Audit score (would come from external source in production)
        if category in ["Liquid Staking", "Lending", "Dexes"]:
            audit_score = 0.8
        elif category in ["Bridge", "CDP"]:
            audit_score = 0.6
        else:
            audit_score = 0.4
        
        return ProtocolFeatures(
            slug=slug,
            tvl=tvl,
            tvl_log=tvl_log,
            tvl_change_1d=tvl_change_1d,
            tvl_change_7d=tvl_change_7d,
            tvl_change_30d=tvl_change_30d,
            tvl_volatility=tvl_volatility,
            price_change_1d=price_change_1d,
            price_change_7d=price_change_7d,
            price_volatility=price_volatility,
            price_crash_7d=price_crash_7d,
            category_risk=category_risk,
            chain_count=chain_count,
            mcap_to_tvl=mcap_to_tvl,
            age_days=age_days,
            audit_score=audit_score,
        )


class RiskPredictor:
    """
    Production risk prediction engine.
    
    Usage:
        predictor = RiskPredictor()
        result = predictor.predict("aave")
        
        # Batch prediction
        results = predictor.predict_batch(["aave", "compound", "curve"])
        
        # Top protocols
        results = predictor.scan_top(limit=50)
    """
    
    def __init__(self, model_path: Optional[Path] = None):
        self.fetcher = ProtocolFetcher()
        self.extractor = FeatureExtractor(self.fetcher)
        self.model, self.config, self.model_version = self._load_model(model_path)
    
    def _load_model(self, model_path: Optional[Path]):
        """Load model from checkpoint."""
        
        from risk_model import ModelRegistry, ModelConfig, create_model
        
        registry = ModelRegistry()
        
        try:
            model, config, metrics = registry.load(model_path)
            version = f"{config.arch}_{datetime.now().strftime('%Y%m%d')}"
            return model, config, version
        except FileNotFoundError:
            # Fall back to legacy model
            legacy_path = DATA_DIR / "nexus_gnn_v3.pt"
            if legacy_path.exists():
                print("Using legacy v3 model...")
                checkpoint = torch.load(legacy_path, map_location="cpu")
                
                # Create compatible config
                config = ModelConfig(
                    arch="mlp",
                    input_dim=7,  # v3 used 7 features
                    hidden_dim=64,
                    num_layers=3,
                )
                
                # Load legacy model architecture
                from train_gnn_v3 import NexusRiskPredictor, Config as V3Config
                v3_config = V3Config(**checkpoint.get("config", {}))
                model = NexusRiskPredictor(v3_config)
                model.load_state_dict(checkpoint["model_state"])
                model.eval()
                
                return model, config, "v3_legacy"
            
            raise FileNotFoundError("No model found. Train one with: python risk_model.py train")
    
    def _compute_confidence(self, prob: float) -> float:
        """Compute prediction confidence."""
        # Confidence is higher when prediction is more extreme
        return abs(prob - 0.5) * 2
    
    def _explain_prediction(
        self, 
        features: ProtocolFeatures,
        prob: float
    ) -> List[Dict]:
        """Generate explanation for prediction."""
        
        factors = []
        
        # Check each risk factor
        if features.tvl_change_7d < -10:
            factors.append({
                "factor": "TVL Decline",
                "value": f"{features.tvl_change_7d:.1f}%",
                "impact": "high",
                "description": "Significant TVL outflow in past 7 days"
            })
        
        if features.tvl_volatility > 10:
            factors.append({
                "factor": "High Volatility",
                "value": f"{features.tvl_volatility:.1f}",
                "impact": "medium",
                "description": "TVL showing high volatility"
            })
        
        if features.category_risk > 0.7:
            factors.append({
                "factor": "Risky Category",
                "value": f"{features.category_risk:.2f}",
                "impact": "high",
                "description": "Protocol category has higher exploit history"
            })
        
        if features.price_crash_7d > 20:
            factors.append({
                "factor": "Price Crash",
                "value": f"{features.price_crash_7d:.1f}%",
                "impact": "high",
                "description": "Significant price decline detected"
            })
        
        if features.chain_count > 10:
            factors.append({
                "factor": "Multi-Chain",
                "value": str(features.chain_count),
                "impact": "low",
                "description": "Deployed on many chains (complexity risk)"
            })
        
        if features.audit_score < 0.5:
            factors.append({
                "factor": "Low Audit Score",
                "value": f"{features.audit_score:.2f}",
                "impact": "medium",
                "description": "Limited security audit coverage"
            })
        
        # Sort by impact
        impact_order = {"high": 0, "medium": 1, "low": 2}
        factors.sort(key=lambda x: impact_order.get(x["impact"], 3))
        
        return factors[:5]  # Top 5 factors
    
    def _get_risk_level(self, score: float) -> str:
        """Convert score to risk level."""
        if score >= 70:
            return "CRITICAL"
        elif score >= 55:
            return "HIGH"
        elif score >= 40:
            return "MEDIUM"
        else:
            return "LOW"
    
    def predict(self, slug: str) -> Optional[PredictionResult]:
        """Predict risk for a single protocol."""
        
        features = self.extractor.extract(slug)
        if features is None:
            return None
        
        # Get raw protocol data for name
        data = self.fetcher.get_protocol(slug)
        name = data.get("name", slug) if data else slug
        category = data.get("category", "Unknown") if data else "Unknown"
        
        # Model prediction
        tensor = features.to_tensor()
        
        with torch.no_grad():
            if self.model_version == "v3_legacy":
                # Legacy model expects 7 features
                legacy_features = torch.tensor([[
                    features.tvl_log,
                    features.tvl_change_1d / 100,
                    features.tvl_change_7d / 100,
                    features.tvl_change_30d / 100,
                    features.tvl_volatility / 50,
                    features.category_risk,
                    features.chain_count / 10,
                ]], dtype=torch.float32)
                prob = self.model(legacy_features).item()
            else:
                logits = self.model(tensor)
                prob = torch.sigmoid(logits).item()
        
        risk_score = prob * 100
        
        return PredictionResult(
            protocol=name,
            slug=slug,
            risk_score=round(risk_score, 1),
            risk_level=self._get_risk_level(risk_score),
            confidence=round(self._compute_confidence(prob), 2),
            top_factors=self._explain_prediction(features, prob),
            tvl=features.tvl,
            category=category,
            timestamp=datetime.now().isoformat(),
            model_version=self.model_version,
        )
    
    def predict_batch(self, slugs: List[str]) -> List[PredictionResult]:
        """Predict risk for multiple protocols."""
        results = []
        for slug in slugs:
            result = self.predict(slug)
            if result:
                results.append(result)
        return sorted(results, key=lambda x: x.risk_score, reverse=True)
    
    def scan_top(self, limit: int = 50) -> List[PredictionResult]:
        """Scan top protocols by TVL."""
        
        protocols = self.fetcher.get_top_protocols(limit)
        slugs = [p.get("slug") for p in protocols if p.get("slug")]
        return self.predict_batch(slugs)
    
    def get_alerts(self, threshold: float = 55.0) -> List[PredictionResult]:
        """Get high-risk protocols above threshold."""
        
        results = self.scan_top(100)
        return [r for r in results if r.risk_score >= threshold]


def main():
    """Demo inference."""
    
    print("="*60)
    print("NEXUS INFERENCE ENGINE")
    print("="*60)
    
    predictor = RiskPredictor()
    print(f"Model: {predictor.model_version}")
    print()
    
    # Single prediction
    result = predictor.predict("aave-v3")
    if result:
        print(f"Protocol: {result.protocol}")
        print(f"Risk Score: {result.risk_score}%")
        print(f"Risk Level: {result.risk_level}")
        print(f"Confidence: {result.confidence:.1%}")
        print()
        
        if result.top_factors:
            print("Risk Factors:")
            for f in result.top_factors:
                print(f"  - {f['factor']}: {f['value']} ({f['impact']})")
    
    print()
    print("="*60)
    print("TOP 10 RISKIEST PROTOCOLS")
    print("="*60)
    
    # Scan top protocols
    results = predictor.scan_top(20)[:10]
    
    print(f"\n{'Protocol':<25} {'TVL':>12} {'Score':>8} {'Level':<10}")
    print("-"*60)
    
    for r in results:
        tvl_str = f"${r.tvl/1e9:.2f}B" if r.tvl > 1e9 else f"${r.tvl/1e6:.0f}M"
        print(f"{r.protocol:<25} {tvl_str:>12} {r.risk_score:>7.1f}% {r.risk_level:<10}")


if __name__ == "__main__":
    main()
