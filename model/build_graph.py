import json
import os
from datetime import datetime

# Protocol dependency graph
# This represents real financial connections
# between DeFi protocols
# 
# Each connection means:
# "If Protocol A has problems,
#  Protocol B will likely be affected"
#
# Based on real research from:
# Euler hack 2023, Terra collapse 2022,
# Curve exploit 2023

PROTOCOL_GRAPH = {
    "Aave V3": {
        "depends_on": ["Chainlink", "Uniswap", "WBTC"],
        "depended_by": ["Morpho V1", "Spark"],
        "connection_type": "oracle+liquidity",
        "risk_multiplier": 1.5  # lending = higher contagion
    },
    "Uniswap": {
        "depends_on": ["Chainlink"],
        "depended_by": ["Aave V3", "Curve", "Balancer"],
        "connection_type": "liquidity",
        "risk_multiplier": 1.2
    },
    "Curve": {
        "depends_on": ["Chainlink", "Uniswap"],
        "depended_by": ["Aave V3", "Morpho V1", "Convex"],
        "connection_type": "liquidity+collateral",
        "risk_multiplier": 1.8  # stablecoin core = very high
    },
    "Morpho V1": {
        "depends_on": ["Aave V3", "Chainlink"],
        "depended_by": [],
        "connection_type": "lending_layer",
        "risk_multiplier": 1.6
    },
    "Lido": {
        "depends_on": ["Ethereum"],
        "depended_by": ["Aave V3", "Curve", "Uniswap"],
        "connection_type": "collateral",
        "risk_multiplier": 1.4
    },
    "Chainlink": {
        "depends_on": [],
        "depended_by": ["Aave V3", "Uniswap", "Curve", 
                        "Morpho V1", "Sky Lending"],
        "connection_type": "oracle",
        "risk_multiplier": 2.0  # oracle = catastrophic if fails
    },
    "Sky Lending": {
        "depends_on": ["Chainlink", "Uniswap"],
        "depended_by": ["Aave V3"],
        "connection_type": "stablecoin+cdp",
        "risk_multiplier": 1.7
    },
    "WBTC": {
        "depends_on": ["Bitcoin"],
        "depended_by": ["Aave V3", "Curve", "Uniswap"],
        "connection_type": "wrapped_asset",
        "risk_multiplier": 1.3
    },
    "Ethena USDe": {
        "depends_on": ["Chainlink", "Uniswap"],
        "depended_by": ["Aave V3", "Morpho V1"],
        "connection_type": "synthetic_stablecoin",
        "risk_multiplier": 1.9  # new mechanism = untested
    },
    "EigenCloud": {
        "depends_on": ["Lido", "Ethereum"],
        "depended_by": ["Aave V3"],
        "connection_type": "restaking",
        "risk_multiplier": 1.6
    }
}


def calculate_contagion_risk(protocol_name, base_risk, graph, all_risks):
    """
    Calculate how much a protocol's risk
    spreads to connected protocols.
    
    This is the CORE of Nexus.
    
    If Chainlink (oracle) fails:
    → Aave cannot get prices → emergency
    → Uniswap cannot price assets → emergency
    → Curve pools break → emergency
    
    Contagion score = base_risk * connections * multiplier
    """
    
    if protocol_name not in graph:
        return base_risk
    
    node = graph[protocol_name]
    contagion_score = base_risk
    
    # Add risk from dependencies
    # If something you depend on is risky
    # you are also at risk
    for dependency in node["depends_on"]:
        if dependency in all_risks:
            dep_risk = all_risks[dependency]
            # 30% of dependency risk flows to you
            contagion_score += dep_risk * 0.3
    
    # Apply protocol-specific multiplier
    contagion_score *= node["risk_multiplier"]
    
    return min(round(contagion_score, 2), 100)


def build_risk_graph():
    """
    Combines live market data with
    protocol dependency graph to produce
    contagion-aware risk scores.
    
    This is what makes Nexus different
    from simple TVL monitoring.
    """
    
    # Load base risk scores from fetch_data.py
    data_path = "../data/protocol_risk.json"
    
    if not os.path.exists(data_path):
        print("Run fetch_data.py first")
        exit(1)
    
    with open(data_path) as f:
        protocols = json.load(f)
    
    # Build base risk lookup
    base_risks = {
        p["name"]: p["risk_score"] 
        for p in protocols
    }
    
    print("=" * 60)
    print("NEXUS — Contagion Risk Graph")
    print("=" * 60)
    print()
    
    graph_results = []
    
    for protocol in protocols:
        name = protocol["name"]
        base_risk = protocol["risk_score"]
        
        # Calculate contagion-aware risk
        contagion_risk = calculate_contagion_risk(
            name, base_risk, PROTOCOL_GRAPH, base_risks
        )
        
        # Find which protocols this one is connected to
        connections = []
        if name in PROTOCOL_GRAPH:
            node = PROTOCOL_GRAPH[name]
            connections = (
                node["depends_on"] + 
                node["depended_by"]
            )
        
        # Risk delta — how much contagion added
        risk_delta = contagion_risk - base_risk
        
        graph_results.append({
            "name": name,
            "base_risk": base_risk,
            "contagion_risk": contagion_risk,
            "risk_delta": round(risk_delta, 2),
            "connections": connections,
            "connection_count": len(connections),
            "tvl": protocol["tvl"],
            "change_1d": protocol["change_1d"],
            "change_7d": protocol["change_7d"],
            "category": protocol["category"],
            "timestamp": datetime.now().isoformat()
        })
        
        # Display
        delta_str = f"+{risk_delta:.1f}" if risk_delta > 0 else f"{risk_delta:.1f}"
        
        if contagion_risk >= 70:
            level = "🔴 CRITICAL"
        elif contagion_risk >= 40:
            level = "🟡 WARNING"
        elif contagion_risk >= 20:
            level = "🟠 ELEVATED"
        else:
            level = "🟢 SAFE"
        
        print(f"{name}")
        print(f"  Base Risk:      {base_risk}/100")
        print(f"  Contagion Risk: {contagion_risk}/100 ({delta_str} from connections)")
        print(f"  Status:         {level}")
        
        if connections:
            print(f"  Connected to:   {', '.join(connections[:3])}")
        print()
    
    # Sort by contagion risk
    graph_results.sort(
        key=lambda x: x["contagion_risk"], 
        reverse=True
    )
    
    # Save graph data
    os.makedirs("../data", exist_ok=True)
    with open("../data/risk_graph.json", "w") as f:
        json.dump(graph_results, f, indent=2)
    
    print("=" * 60)
    print("CONTAGION ALERT — Top 5 Highest Risk:")
    print("=" * 60)
    for p in graph_results[:5]:
        print(f"  {p['name']:<20} {p['contagion_risk']}/100")
    
    print()
    print(f"Graph saved to data/risk_graph.json")
    print(f"Nodes: {len(graph_results)}")
    
    # Count edges
    total_edges = sum(
        len(PROTOCOL_GRAPH.get(p["name"], {})
            .get("depends_on", [])) 
        for p in graph_results
    )
    print(f"Edges: {total_edges}")
    print("=" * 60)


if __name__ == "__main__":
    build_risk_graph()