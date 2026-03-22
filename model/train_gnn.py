import torch
import torch.nn as nn
import torch.nn.functional as F
import json
import numpy as np
from datetime import datetime

# ============================================
# NEXUS — Graph Neural Network
# 
# What this model does:
# Takes a protocol dependency graph as input
# Each node = a DeFi protocol
# Each edge = financial dependency
# Output = risk score for each protocol
#
# Why GNN and not regular neural network?
# Regular NN: looks at each protocol alone
# GNN: looks at each protocol AND its neighbors
# 
# Example:
# Regular NN sees Morpho V1 risk = 30
# GNN sees Morpho V1 + Aave dependency = 52.8
# GNN is correct — Morpho dies if Aave dies
# ============================================

class GraphConvLayer(nn.Module):
    """
    Single graph convolution layer.
    
    What it does:
    For each node — collects information
    from all connected neighbor nodes
    and combines it with own features.
    
    Like asking your neighbors how they are
    before deciding how YOU feel.
    """
    
    def __init__(self, in_features, out_features):
        super().__init__()
        self.linear = nn.Linear(in_features, out_features)
        self.neighbor_linear = nn.Linear(in_features, out_features)
    
    def forward(self, x, adj):
        """
        x   = node features [num_nodes, features]
        adj = adjacency matrix [num_nodes, num_nodes]
              adj[i][j] = 1 if protocol i depends on j
        """
        # Own transformation
        own = self.linear(x)
        
        # Neighbor aggregation
        # Sum up features from all neighbors
        neighbor_sum = torch.mm(adj, x)
        neighbor = self.neighbor_linear(neighbor_sum)
        
        # Combine own + neighbor info
        return F.relu(own + neighbor)


class NexusGNN(nn.Module):
    """
    Full GNN for DeFi risk prediction.
    
    Architecture:
    Input: protocol features (TVL change, utilization, etc.)
    Layer 1: Graph conv — learns local neighborhood risk
    Layer 2: Graph conv — learns 2-hop contagion patterns  
    Layer 3: Linear — outputs final risk score 0-1
    """
    
    def __init__(self, num_features, hidden_dim=32, output_dim=1):
        super().__init__()
        
        self.conv1 = GraphConvLayer(num_features, hidden_dim)
        self.conv2 = GraphConvLayer(hidden_dim, hidden_dim)
        self.output = nn.Linear(hidden_dim, output_dim)
        self.dropout = nn.Dropout(0.3)
    
    def forward(self, x, adj):
        # Layer 1 — learn from direct neighbors
        x = self.conv1(x, adj)
        x = self.dropout(x)
        
        # Layer 2 — learn from neighbors of neighbors
        x = self.conv2(x, adj)
        x = self.dropout(x)
        
        # Output — risk score 0 to 1
        x = torch.sigmoid(self.output(x))
        
        return x


def build_training_data():
    """
    Convert our historical exploit data
    into tensors the GNN can train on.
    
    Each training example is a snapshot
    of the protocol graph BEFORE an exploit
    with label = 1 if protocol got hit, 0 if not
    """
    
    # Load our data
    with open("../data/historical_exploits.json") as f:
        exploit_data = json.load(f)
    
    with open("../data/risk_graph.json") as f:
        graph_data = json.load(f)
    
    # Protocol list
    protocols = [p["name"] for p in graph_data]
    num_protocols = len(protocols)
    protocol_idx = {p: i for i, p in enumerate(protocols)}
    
    print(f"Protocols in graph: {num_protocols}")
    print(f"Training exploits: {len(exploit_data['exploits'])}")
    
    # Build adjacency matrix from graph
    # adj[i][j] = 1 means protocol i is affected by j
    adj = torch.zeros(num_protocols, num_protocols)
    
    # Protocol dependencies from our graph
    DEPENDENCIES = {
        "Aave V3": ["Morpho V1", "Sky Lending"],
        "Uniswap": ["Aave V3", "Sky Lending", "Ethena USDe"],
        "Chainlink": ["Aave V3", "Uniswap", "Sky Lending", 
                      "Morpho V1", "Ethena USDe"],
        "Morpho V1": [],
        "Curve": ["Aave V3", "Morpho V1"],
        "Lido": ["EigenCloud"],
        "WBTC": ["Aave V3"],
        "Ethena USDe": [],
    }
    
    for source, targets in DEPENDENCIES.items():
        if source in protocol_idx:
            for target in targets:
                if target in protocol_idx:
                    i = protocol_idx[source]
                    j = protocol_idx[target]
                    adj[i][j] = 1.0
    
    # Build feature matrix
    # Features for each protocol:
    # [tvl_normalized, change_1d, change_7d, 
    #  category_risk, contagion_risk_normalized]
    
    features = []
    for p in graph_data:
        tvl_log = np.log1p(p["tvl"]) / 30.0
        change_1d = max(min(p["change_1d"] / 100.0, 1.0), -1.0)
        change_7d = max(min(p["change_7d"] / 100.0, 1.0), -1.0)
        category_risk = 1.0 if p["category"] in [
            "Lending", "CDP", "Basis Trading"
        ] else 0.5
        contagion_norm = p["contagion_risk"] / 100.0
        
        features.append([
            tvl_log,
            change_1d,
            change_7d,
            category_risk,
            contagion_norm
        ])
    
    X = torch.tensor(features, dtype=torch.float32)
    
    # Build labels from historical exploits
    # Label = 1 if protocol was hit in any exploit
    labels = torch.zeros(num_protocols, 1)
    
    exploits = exploit_data["exploits"]
    for exploit in exploits:
        # Primary protocol — definitely hit
        primary = exploit["primary_protocol"]
        for p_name, idx in protocol_idx.items():
            if p_name.lower() in primary.lower():
                labels[idx] = 1.0
        
        # Contagion protocols — also hit
        for contagion_p in exploit["contagion_protocols"]:
            for p_name, idx in protocol_idx.items():
                if p_name.lower() in contagion_p.lower():
                    labels[idx] = 0.7  # partial risk
    
    # Protocols with high warning signals
    # get elevated labels
    for i, p in enumerate(graph_data):
        if p["change_1d"] < -10:
            labels[i] = max(labels[i].item(), 0.8)
        elif p["change_1d"] < -5:
            labels[i] = max(labels[i].item(), 0.5)
    
    print(f"Feature shape: {X.shape}")
    print(f"Label shape: {labels.shape}")
    print(f"High risk protocols: {(labels > 0.5).sum().item()}")
    
    return X, adj, labels, protocols


def train_model():
    print("=" * 60)
    print("NEXUS — GNN Training")
    print("=" * 60)
    print()
    
    # Build data
    X, adj, labels, protocols = build_training_data()
    
    # Initialize model
    num_features = X.shape[1]
    model = NexusGNN(
        num_features=num_features,
        hidden_dim=32,
        output_dim=1
    )
    
    optimizer = torch.optim.Adam(
        model.parameters(), 
        lr=0.01,
        weight_decay=1e-4
    )
    criterion = nn.BCELoss()
    
    print(f"\nModel architecture:")
    print(f"  Input features:  {num_features}")
    print(f"  Hidden dim:      32")
    print(f"  Output:          risk score per protocol")
    print(f"  Parameters:      {sum(p.numel() for p in model.parameters())}")
    print()
    
    # Training loop
    print("Training...")
    print("-" * 40)
    
    model.train()
    losses = []
    
    for epoch in range(200):
        optimizer.zero_grad()
        
        # Forward pass
        predictions = model(X, adj)
        
        # Calculate loss
        loss = criterion(predictions, labels)
        
        # Backward pass
        loss.backward()
        optimizer.step()
        
        losses.append(loss.item())
        
        # Print progress every 20 epochs
        if (epoch + 1) % 20 == 0:
            print(f"Epoch {epoch+1:3d}/200 | "
                  f"Loss: {loss.item():.4f}")
    
    # Evaluation
    print()
    print("=" * 60)
    print("TRAINING COMPLETE — Risk Predictions:")
    print("=" * 60)
    
    model.eval()
    with torch.no_grad():
        predictions = model(X, adj)
    
    results = []
    for i, (protocol, pred, label) in enumerate(
        zip(protocols, predictions, labels)
    ):
        risk_score = pred.item() * 100
        true_risk = label.item() * 100
        
        if risk_score >= 70:
            level = "🔴 CRITICAL"
        elif risk_score >= 40:
            level = "🟡 WARNING"
        elif risk_score >= 20:
            level = "🟠 ELEVATED"
        else:
            level = "🟢 SAFE"
        
        results.append({
            "protocol": protocol,
            "gnn_risk_score": round(risk_score, 1),
            "level": level
        })
    
    # Sort by risk
    results.sort(
        key=lambda x: x["gnn_risk_score"],
        reverse=True
    )
    
    for r in results:
        print(f"{r['protocol']:<25} "
              f"{r['gnn_risk_score']:>5.1f}/100  "
              f"{r['level']}")
    
    # Save model
    torch.save(model.state_dict(), "../data/nexus_gnn.pt")
    
    # Save predictions
    with open("../data/gnn_predictions.json", "w") as f:
        json.dump({
            "predictions": results,
            "model_info": {
                "type": "Graph Neural Network",
                "layers": 2,
                "hidden_dim": 32,
                "features": [
                    "tvl_log_normalized",
                    "change_24h",
                    "change_7d", 
                    "category_risk",
                    "contagion_risk"
                ],
                "final_loss": round(losses[-1], 4),
                "epochs": 200
            },
            "timestamp": datetime.now().isoformat()
        }, f, indent=2)
    
    print()
    print(f"Model saved: data/nexus_gnn.pt")
    print(f"Predictions saved: data/gnn_predictions.json")
    print(f"Final loss: {losses[-1]:.4f}")
    print("=" * 60)


if __name__ == "__main__":
    train_model()