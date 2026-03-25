#!/usr/bin/env python3
"""Quick test of real-time monitoring with v3 security-grade model"""

from realtime_monitor import RiskMonitor
from pathlib import Path

print("Testing Nexus Real-Time Monitor v3...")
print("=" * 60)

# Load v3 model (security-grade) - will auto-fallback to v2 if needed
monitor = RiskMonitor()  # Uses default v3 model

# Fetch and analyze top protocols
print("\nFetching top 10 protocols...")
protocols = monitor.fetch_protocols()[:10]

print(f"Analyzing {len(protocols)} protocols...\n")
results = monitor.predict(protocols)

# Display results
print(f"{'Protocol':<25} {'TVL':>12} {'Risk':>6} {'Level':<10} {'Model'}")
print("-" * 75)

for r in results:
    tvl_str = f"${r['tvl']/1e9:.1f}B" if r['tvl'] > 1e9 else f"${r['tvl']/1e6:.0f}M"
    print(f"{r['alert']} {r['name']:<22} {tvl_str:>12} {r['risk_score']:>5.1f}% {r['risk_level']:<10} v{monitor.model_version}")

print(f"\n✓ Real-time monitoring working with v{monitor.model_version} model!")
print(f"  Performance: F1={monitor.metrics.get('f1', 0):.1%}")
print("=" * 60)
