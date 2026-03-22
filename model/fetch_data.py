import requests
import json
import os
from datetime import datetime

DEFILLAMA_BASE = "https://api.llama.fi"

def fetch_all_protocols():
    print("Fetching protocols from DefiLlama...")
    response = requests.get(f"{DEFILLAMA_BASE}/protocols")
    if response.status_code != 200:
        print(f"Error: {response.status_code}")
        return []
    protocols = response.json()
    print(f"Total protocols found: {len(protocols)}")
    return protocols

def calculate_risk_score(protocol):
    change_1d = protocol.get("change_1d", 0) or 0
    change_7d = protocol.get("change_7d", 0) or 0
    category = protocol.get("category", "")
    risk = 0
    if change_1d < -10:
        risk += 40
    elif change_1d < -5:
        risk += 20
    if change_7d < -20:
        risk += 30
    elif change_7d < -10:
        risk += 15
    if category in ["Lending", "CDP"]:
        risk += 10
    return min(round(risk, 2), 100)

def get_risk_level(score):
    if score >= 70:
        return "HIGH RISK"
    elif score >= 40:
        return "MEDIUM RISK"
    elif score >= 20:
        return "LOW-MEDIUM"
    else:
        return "LOW RISK"

if __name__ == "__main__":
    print("=" * 60)
    print("NEXUS — DeFi Risk Intelligence System")
    print("=" * 60)

    all_protocols = fetch_all_protocols()
    if not all_protocols:
        print("Failed to fetch protocols")
        exit(1)

    sorted_protocols = sorted(
        [p for p in all_protocols if (p.get("tvl") or 0) > 100_000_000],
        key=lambda x: x.get("tvl", 0),
        reverse=True
    )[:20]

    print(f"\nTop 20 DeFi Protocols by TVL:")
    print("-" * 60)

    results = []
    for protocol in sorted_protocols:
        name = protocol.get("name", "Unknown")
        tvl = protocol.get("tvl", 0)
        change_1d = protocol.get("change_1d", 0) or 0
        change_7d = protocol.get("change_7d", 0) or 0
        category = protocol.get("category", "Unknown")
        risk_score = calculate_risk_score(protocol)
        risk_level = get_risk_level(risk_score)

        print(f"\n{name} [{category}]")
        print(f"  TVL:    ${tvl:>15,.0f}")
        print(f"  24h:    {change_1d:>+.2f}%")
        print(f"  7d:     {change_7d:>+.2f}%")
        print(f"  Risk:   {risk_score}/100 — {risk_level}")

        results.append({
            "name": name,
            "tvl": tvl,
            "change_1d": change_1d,
            "change_7d": change_7d,
            "category": category,
            "risk_score": risk_score,
            "risk_level": risk_level,
            "timestamp": datetime.now().isoformat()
        })

    os.makedirs("../data", exist_ok=True)
    with open("../data/protocol_risk.json", "w") as f:
        json.dump(results, f, indent=2)

    high_risk = [p for p in results if p["risk_score"] >= 70]
    medium_risk = [p for p in results if 40 <= p["risk_score"] < 70]

    print("\n" + "=" * 60)
    print(f"Saved to data/protocol_risk.json")
    print(f"Protocols analyzed: {len(results)}")
    print(f"\nRISK SUMMARY:")
    print(f"  High Risk:   {len(high_risk)}")
    print(f"  Medium Risk: {len(medium_risk)}")
    print(f"  Low Risk:    {len(results) - len(high_risk) - len(medium_risk)}")
    print("=" * 60)