#!/usr/bin/env python3
"""
Nexus Anomaly Detector - Real-time DeFi Protocol Anomaly Detection

Detects unusual behavior in DeFi protocols using:
1. Statistical thresholds (TVL drops, price crashes)
2. Isolation Forest (ML-based anomaly detection)
3. Rate-of-change analysis

NOT prediction - just current state anomaly detection.
"""

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
import json
from typing import Dict, List, Tuple
from datetime import datetime, timedelta

class AnomalyDetector:
    """Detect anomalies in DeFi protocol behavior"""
    
    def __init__(self):
        self.scaler = StandardScaler()
        self.isolation_forest = IsolationForest(
            contamination=0.1,  # Expect 10% anomalies
            random_state=42,
            n_estimators=100
        )
        self.is_trained = False
        
        # Rule-based thresholds (simple but effective)
        self.thresholds = {
            'tvl_drop_1h': 0.20,      # 20% drop in 1 hour
            'tvl_drop_24h': 0.40,     # 40% drop in 24 hours
            'price_crash': 0.30,       # 30% price drop
            'volume_spike': 5.0,       # 5x normal volume
            'gas_spike': 3.0,          # 3x normal gas usage
        }
    
    def train(self, historical_data: pd.DataFrame):
        """
        Train on NORMAL protocol behavior (not exploits)
        
        Args:
            historical_data: DataFrame with columns:
                - tvl, tvl_change_1d, tvl_change_7d
                - price_change_1d, price_change_7d
                - volume, gas_used, etc.
        """
        # Use only normal samples (not labeled as exploits)
        if 'is_exploit' in historical_data.columns:
            normal_data = historical_data[historical_data['is_exploit'] == 0]
        else:
            normal_data = historical_data
        
        features = self._extract_features(normal_data)
        
        # Fit scaler on normal data
        features_scaled = self.scaler.fit_transform(features)
        
        # Train Isolation Forest on normal behavior
        self.isolation_forest.fit(features_scaled)
        self.is_trained = True
        
        print(f"✓ Trained on {len(normal_data)} normal samples")
    
    def detect(self, protocol_data: Dict) -> Tuple[bool, float, List[str]]:
        """
        Detect if protocol is currently anomalous
        
        Args:
            protocol_data: Current protocol state
                {
                    'tvl': 1000000000,
                    'tvl_1h_ago': 1200000000,
                    'tvl_24h_ago': 1100000000,
                    'price_change_1h': -0.15,
                    'volume_24h': 50000000,
                    ...
                }
        
        Returns:
            (is_anomaly, anomaly_score, reasons)
        """
        reasons = []
        
        # Rule-based detection (fast, interpretable)
        rule_anomaly, rule_reasons = self._rule_based_detection(protocol_data)
        reasons.extend(rule_reasons)
        
        # ML-based detection (catches subtle patterns)
        if self.is_trained:
            ml_anomaly, ml_score = self._ml_based_detection(protocol_data)
        else:
            ml_anomaly = False
            ml_score = 0.0
        
        # Combine: Anomaly if EITHER rules trigger OR ML detects
        is_anomaly = rule_anomaly or ml_anomaly
        
        # Score: 0 (normal) to 100 (critical anomaly)
        if is_anomaly:
            score = min(100, len(reasons) * 25 + abs(ml_score) * 100)
        else:
            score = 0.0
        
        return is_anomaly, score, reasons
    
    def _rule_based_detection(self, data: Dict) -> Tuple[bool, List[str]]:
        """Simple threshold-based rules"""
        reasons = []
        
        # 1. Sudden TVL drop
        if 'tvl' in data and 'tvl_1h_ago' in data:
            tvl_change = (data['tvl'] - data['tvl_1h_ago']) / data['tvl_1h_ago']
            if tvl_change < -self.thresholds['tvl_drop_1h']:
                reasons.append(f"TVL dropped {abs(tvl_change)*100:.1f}% in 1 hour")
        
        if 'tvl' in data and 'tvl_24h_ago' in data:
            tvl_change_24h = (data['tvl'] - data['tvl_24h_ago']) / data['tvl_24h_ago']
            if tvl_change_24h < -self.thresholds['tvl_drop_24h']:
                reasons.append(f"TVL dropped {abs(tvl_change_24h)*100:.1f}% in 24 hours")
        
        # 2. Price crash
        if 'price_change_1h' in data:
            if data['price_change_1h'] < -self.thresholds['price_crash']:
                reasons.append(f"Price crashed {abs(data['price_change_1h'])*100:.1f}%")
        
        # 3. Volume spike (possible exploit draining)
        if 'volume_24h' in data and 'avg_volume_7d' in data:
            if data['avg_volume_7d'] > 0:
                volume_ratio = data['volume_24h'] / data['avg_volume_7d']
                if volume_ratio > self.thresholds['volume_spike']:
                    reasons.append(f"Volume spiked {volume_ratio:.1f}x normal")
        
        # 4. Unusual transactions
        if 'large_withdrawals' in data:
            if data['large_withdrawals'] > 10:
                reasons.append(f"{data['large_withdrawals']} large withdrawals detected")
        
        return len(reasons) > 0, reasons
    
    def _ml_based_detection(self, data: Dict) -> Tuple[bool, float]:
        """ML-based anomaly detection (Isolation Forest)"""
        features = self._extract_features_single(data)
        features_scaled = self.scaler.transform(features.reshape(1, -1))
        
        # Predict: -1 = anomaly, 1 = normal
        prediction = self.isolation_forest.predict(features_scaled)[0]
        
        # Get anomaly score
        score = self.isolation_forest.score_samples(features_scaled)[0]
        
        return prediction == -1, score
    
    def _extract_features(self, df: pd.DataFrame) -> np.ndarray:
        """Extract features for training"""
        feature_cols = [
            'tvl_change_1d', 'tvl_change_7d', 'tvl_volatility',
            'price_change_1d', 'price_change_7d', 'price_volatility',
            'volume_24h', 'age_days'
        ]
        
        # Use available columns
        available_cols = [col for col in feature_cols if col in df.columns]
        return df[available_cols].fillna(0).values
    
    def _extract_features_single(self, data: Dict) -> np.ndarray:
        """Extract features from single sample"""
        feature_keys = [
            'tvl_change_1d', 'tvl_change_7d', 'tvl_volatility',
            'price_change_1d', 'price_change_7d', 'price_volatility',
            'volume_24h', 'age_days'
        ]
        
        features = [data.get(key, 0) for key in feature_keys]
        return np.array(features)


class RealTimeMonitor:
    """Real-time monitoring for DeFi protocols"""
    
    def __init__(self, detector: AnomalyDetector):
        self.detector = detector
        self.protocol_history = {}
    
    def update(self, protocol_id: str, current_state: Dict):
        """Update protocol state and check for anomalies"""
        
        # Store history
        if protocol_id not in self.protocol_history:
            self.protocol_history[protocol_id] = []
        
        self.protocol_history[protocol_id].append({
            'timestamp': datetime.now(),
            'state': current_state
        })
        
        # Keep only last 7 days
        cutoff = datetime.now() - timedelta(days=7)
        self.protocol_history[protocol_id] = [
            h for h in self.protocol_history[protocol_id]
            if h['timestamp'] > cutoff
        ]
        
        # Compute deltas (1h ago, 24h ago)
        enriched_state = self._compute_deltas(protocol_id, current_state)
        
        # Detect anomaly
        is_anomaly, score, reasons = self.detector.detect(enriched_state)
        
        if is_anomaly:
            self._alert(protocol_id, score, reasons)
        
        return is_anomaly, score, reasons
    
    def _compute_deltas(self, protocol_id: str, current: Dict) -> Dict:
        """Compute time-based deltas"""
        history = self.protocol_history.get(protocol_id, [])
        
        enriched = current.copy()
        
        if len(history) >= 2:
            # Find state 1h ago
            one_hour_ago = datetime.now() - timedelta(hours=1)
            for h in reversed(history):
                if h['timestamp'] <= one_hour_ago:
                    enriched['tvl_1h_ago'] = h['state'].get('tvl', current.get('tvl'))
                    break
            
            # Find state 24h ago
            one_day_ago = datetime.now() - timedelta(days=1)
            for h in reversed(history):
                if h['timestamp'] <= one_day_ago:
                    enriched['tvl_24h_ago'] = h['state'].get('tvl', current.get('tvl'))
                    break
        
        return enriched
    
    def _alert(self, protocol_id: str, score: float, reasons: List[str]):
        """Send alert (print for now, webhook later)"""
        print(f"\n🚨 ANOMALY DETECTED: {protocol_id}")
        print(f"   Score: {score:.1f}/100")
        print(f"   Reasons:")
        for reason in reasons:
            print(f"     - {reason}")
        print()


# Quick test
if __name__ == "__main__":
    # Create detector
    detector = AnomalyDetector()
    
    # Train on normal data
    normal_data = pd.DataFrame({
        'tvl': [1e9, 1.1e9, 1.05e9, 0.95e9],
        'tvl_change_1d': [0.05, 0.02, -0.03, -0.01],
        'tvl_change_7d': [0.1, 0.08, 0.05, 0.03],
        'tvl_volatility': [0.05, 0.06, 0.04, 0.05],
        'price_change_1d': [0.02, -0.01, 0.01, 0.0],
        'price_change_7d': [0.05, 0.03, 0.02, 0.01],
        'price_volatility': [0.1, 0.12, 0.11, 0.1],
        'volume_24h': [1e6, 1.2e6, 0.9e6, 1.1e6],
        'age_days': [365, 365, 365, 365],
        'is_exploit': [0, 0, 0, 0]
    })
    
    detector.train(normal_data)
    
    # Test: Normal protocol
    normal_protocol = {
        'tvl': 1e9,
        'tvl_1h_ago': 1.01e9,
        'tvl_24h_ago': 0.99e9,
        'price_change_1h': 0.01,
        'tvl_change_1d': 0.01,
        'tvl_change_7d': 0.02,
        'tvl_volatility': 0.05,
        'price_change_1d': 0.01,
        'price_change_7d': 0.03,
        'price_volatility': 0.1,
        'volume_24h': 1e6,
        'avg_volume_7d': 1e6,
        'age_days': 365
    }
    
    is_anomaly, score, reasons = detector.detect(normal_protocol)
    print(f"Normal protocol: Anomaly={is_anomaly}, Score={score}")
    
    # Test: Anomalous protocol (TVL crash)
    anomalous_protocol = {
        'tvl': 0.5e9,  # 50% drop!
        'tvl_1h_ago': 1.0e9,
        'tvl_24h_ago': 1.0e9,
        'price_change_1h': -0.35,  # 35% crash
        'tvl_change_1d': -0.5,
        'tvl_change_7d': -0.5,
        'tvl_volatility': 0.4,
        'price_change_1d': -0.35,
        'price_change_7d': -0.35,
        'price_volatility': 0.5,
        'volume_24h': 10e6,  # 10x spike
        'avg_volume_7d': 1e6,
        'age_days': 365,
        'large_withdrawals': 25
    }
    
    is_anomaly, score, reasons = detector.detect(anomalous_protocol)
    print(f"\nAnomalous protocol: Anomaly={is_anomaly}, Score={score}")
    print(f"Reasons: {reasons}")
