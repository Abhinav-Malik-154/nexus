# NEXUS

**DeFi Contagion Intelligence System** — AI-powered risk prediction with autonomous on-chain protection.

```
███╗   ██╗███████╗██╗  ██╗██╗   ██╗███████╗
████╗  ██║██╔════╝╚██╗██╔╝██║   ██║██╔════╝
██╔██╗ ██║█████╗   ╚███╔╝ ██║   ██║███████╗
██║╚██╗██║██╔══╝   ██╔██╗ ██║   ██║╚════██║
██║ ╚████║███████╗██╔╝ ██╗╚██████╔╝███████║
╚═╝  ╚═══╝╚══════╝╚═╝  ╚═╝ ╚═════╝ ╚══════╝
```

> Predict. Protect. Survive DeFi.

---

## Overview

Nexus is an autonomous DeFi protection system that uses a **Graph Neural Network (GNN)** to predict risk contagion across interconnected DeFi protocols and **automatically protects user funds** when AI-detected risk exceeds user-defined thresholds.

### The Problem

When one DeFi protocol fails (hack, exploit, bank run), the damage **cascades** through dependencies:

- Chainlink fails → Aave, Compound, Curve all break (they depend on price feeds)
- Terra/Luna collapsed → $40B lost → contagion spread to 3AC, Celsius, Voyager
- FTX collapse → cascading liquidations across the entire market

**Nexus monitors these interdependencies and moves your funds to safety BEFORE you even know there's a problem.**

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           OFF-CHAIN (Python)                            │
│                                                                         │
│   DefiLlama API → fetch_data.py → build_graph.py → train_gnn.py        │
│                                          ↓                              │
│                                   GNN Risk Scores                       │
│                                          ↓                              │
│                                  update_oracle.py                       │
└──────────────────────────────────────┬──────────────────────────────────┘
                                       │
                                       │ batchUpdateRiskScores()
                                       ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                          ON-CHAIN (Solidity)                            │
│                                                                         │
│   ┌─────────────────┐         ┌─────────────────┐                       │
│   │ NexusRiskOracle │────────▶│ ProtectionVault │◀── Chainlink         │
│   │                 │         │                 │    Automation         │
│   │ Stores AI       │         │ User deposits   │                       │
│   │ risk scores     │         │ + rules         │                       │
│   └─────────────────┘         └────────┬────────┘                       │
│                                        │                                │
│                                        ▼                                │
│                              User's Safe Address                        │
└─────────────────────────────────────────────────────────────────────────┘
                                       │
                                       │ Events
                                       ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                          FRONTEND (Next.js)                             │
│                                                                         │
│   Dashboard  │  Risk Map (D3)  │  Protection Vault  │  Alerts          │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Tech Stack

| Layer | Technology | Purpose |
|-------|------------|---------|
| **ML/AI** | Python, PyTorch | Graph Neural Network for contagion prediction |
| **Data** | DefiLlama API | Real-time TVL and protocol metrics |
| **Contracts** | Solidity 0.8.24, Foundry | Gas-optimized oracle and vault |
| **Automation** | Chainlink Keepers | Trustless protection triggers |
| **Frontend** | Next.js 14, TypeScript | React-based dashboard |
| **Web3** | wagmi, viem | Contract interaction hooks |
| **Visualization** | D3.js | Interactive contagion graph |
| **Styling** | CSS-in-JS | Terminal/hacker aesthetic |
| **Network** | Polygon Amoy | Testnet deployment |

---

## Project Structure

```
nexus/
├── contracts/                    # Solidity smart contracts
│   ├── src/
│   │   ├── NexusRiskOracle.sol   # AI risk score storage
│   │   └── ProtectionVault.sol   # Autonomous fund protection
│   ├── test/
│   │   ├── Nexus.t.sol           # Unit tests (33 tests)
│   │   └── NexusFuzz.t.sol       # Fuzz + invariant tests (16 tests)
│   └── script/
│       └── Deploy.s.sol          # Production deployment
│
├── frontend/                     # Next.js application
│   └── src/
│       ├── app/
│       │   ├── page.tsx          # Dashboard
│       │   ├── risk-map/         # D3 contagion graph
│       │   ├── protection/       # Vault management
│       │   └── alerts/           # Real-time notifications
│       ├── components/           # UI components
│       ├── hooks/
│       │   └── useNexus.ts       # Contract interaction hooks
│       └── lib/
│           ├── contracts.ts      # ABIs and addresses
│           └── wagmi.ts          # Web3 configuration
│
└── model/                        # Python ML pipeline
    ├── fetch_data.py             # DefiLlama data collection
    ├── build_graph.py            # Dependency graph construction
    ├── historical_exploits.py    # Training data (8 exploits, $49B+)
    ├── train_gnn.py              # GNN model training
    └── update_oracle.py          # On-chain oracle updater
```

---

## What's Been Done

### Smart Contracts (100% Complete)

- [x] **NexusRiskOracle.sol** — Gas-optimized risk score storage
  - bytes32 protocol IDs (vs strings) — saves ~2-5k gas/op
  - Packed RiskData struct — single storage slot
  - Custom errors — saves ~200 gas vs require strings
  - Unchecked increments — saves ~60 gas/iteration
  - 1-hour staleness check
  - Batch updates for efficiency

- [x] **ProtectionVault.sol** — Autonomous protection vault
  - Chainlink Automation compatible (checkUpkeep/performUpkeep)
  - ReentrancyGuard on all state-changing functions
  - SafeERC20 for token transfers
  - CEI pattern (Checks-Effects-Interactions)
  - Permissionless protection triggers

- [x] **Deploy.s.sol** — Production deployment script
  - Deploys Oracle + Vault
  - Seeds 10 top DeFi protocols
  - Helper scripts for adding updaters

- [x] **Tests** — 49 tests passing
  - 33 unit tests (Oracle + Vault)
  - 11 fuzz tests (property-based)
  - 5 invariant tests (system-wide guarantees)

### Frontend (100% Complete)

- [x] **Dashboard (`/`)** — System status and stats
- [x] **Risk Map (`/risk-map`)** — D3 contagion graph visualization
- [x] **Protection (`/protection`)** — Deposit/withdraw/rules management
- [x] **Alerts (`/alerts`)** — Real-time event feed
- [x] **Components** — Navbar, WalletButton, ChainSelector
- [x] **Hooks** — Complete wagmi hooks for all contract functions
- [x] **Styling** — Terminal/hacker aesthetic

### ML Pipeline (100% Complete)

- [x] **fetch_data.py** — DefiLlama API integration
- [x] **build_graph.py** — Protocol dependency graph
- [x] **historical_exploits.py** — 8 real exploits dataset
- [x] **train_gnn.py** — 2-layer GNN model
- [x] **update_oracle.py** — Oracle updater with watch mode

---

## What Remains

### Deployment & Integration

- [ ] Deploy contracts to Polygon Amoy testnet
- [ ] Update frontend with deployed contract addresses
- [ ] Register vault with Chainlink Automation
- [ ] Set up backend wallet as authorized updater
- [ ] Configure environment variables

### Production Hardening

- [ ] Add more protocols to tracking (currently 10)
- [ ] Expand training dataset (more historical exploits)
- [ ] Add real-time price feed integration
- [ ] Implement model validation (train/test split)
- [ ] Add monitoring and alerting for backend

### Optional Enhancements

- [ ] Multi-chain support (Arbitrum, Optimism, Base)
- [ ] EIP-712 signatures for gasless rule additions
- [ ] Emergency pause functionality
- [ ] Protocol governance for threshold changes
- [ ] Mobile-responsive frontend
- [ ] Email/Telegram notifications

---

## Complete Workflow

### 1. ML Pipeline Generates Risk Scores

```bash
# Fetch latest protocol data
cd model
python fetch_data.py

# Build dependency graph and calculate contagion
python build_graph.py

# Train GNN model
python train_gnn.py
# Outputs: nexus_gnn.pt, gnn_predictions.json

# Push to blockchain (single update)
python update_oracle.py

# Or run in watch mode (updates every 15 min)
python update_oracle.py --watch
```

### 2. User Deposits and Creates Protection Rule

```
User                          ProtectionVault
  │                                 │
  │ deposit(USDC, 1000)             │
  │────────────────────────────────▶│
  │                                 │ Creates vault
  │                                 │ Stores balance
  │                                 │
  │ addProtectionRule(              │
  │   protocol: "Ethena",           │
  │   threshold: 60,                │
  │   token: USDC,                  │
  │   safeAddress: myHardwareWallet │
  │ )                               │
  │────────────────────────────────▶│
  │                                 │ Stores rule
  │                                 │
```

### 3. Risk Score Triggers Protection

```
GNN Model                    Oracle                     Vault                    User
    │                          │                          │                        │
    │ Detects Ethena anomaly   │                          │                        │
    │ Risk score: 78           │                          │                        │
    │                          │                          │                        │
    │ updateRiskScore(78)      │                          │                        │
    │─────────────────────────▶│                          │                        │
    │                          │ Emits HighRiskAlert      │                        │
    │                          │                          │                        │
    │                          │                          │                        │
    │                          │      Chainlink           │                        │
    │                          │      Automation          │                        │
    │                          │         │                │                        │
    │                          │         │ checkUpkeep()  │                        │
    │                          │         │───────────────▶│                        │
    │                          │         │                │ Check all users        │
    │                          │         │                │ User threshold: 60     │
    │                          │         │◀───────────────│ Risk: 78 ≥ 60         │
    │                          │         │ (true, [user]) │ Returns: needs protect│
    │                          │         │                │                        │
    │                          │         │ performUpkeep()│                        │
    │                          │         │───────────────▶│                        │
    │                          │         │                │ Transfer 1000 USDC     │
    │                          │         │                │───────────────────────▶│
    │                          │         │                │      to safe wallet    │
    │                          │         │                │                        │
    │                          │         │                │ Emits                  │
    │                          │         │                │ ProtectionTriggered    │
    │                          │         │                │                        │
```

### 4. Frontend Shows Real-Time Updates

```
/alerts page:
  useProtectionTriggeredEvents() fires
  → "Your 1000 USDC was moved to 0xHardware..."

/protection page:
  useVaultBalance() returns 0
  → Rule shows as deactivated
  → Balance shows 0
```

---

## Quick Start

### Prerequisites

- Node.js 18+
- Foundry
- Python 3.10+
- Git

### Installation

```bash
# Clone repository
git clone https://github.com/abhinav-malik-154/nexus.git
cd nexus

# Install contract dependencies
cd contracts
forge install

# Install frontend dependencies
cd ../frontend
npm install

# Install Python dependencies
cd ../model
pip install -r requirements.txt
```

### Run Tests

```bash
cd contracts
forge test
```

### Run Frontend

```bash
cd frontend
npm run dev
# Open http://localhost:3000
```

### Deploy Contracts

```bash
cd contracts

# Set environment variables
export PRIVATE_KEY=your_private_key
export RPC_URL=https://rpc-amoy.polygon.technology

# Deploy
forge script script/Deploy.s.sol:DeployNexus --rpc-url $RPC_URL --broadcast
```

---

## Contract Addresses

| Contract | Address | Network |
|----------|---------|---------|
| NexusRiskOracle | `TBD` | Polygon Amoy |
| ProtectionVault | `TBD` | Polygon Amoy |
| MockUSDC | `TBD` | Polygon Amoy |

---

## API Reference

### Oracle Functions

```solidity
// Update single protocol
function updateRiskScore(bytes32 id, uint64 score) external

// Batch update
function batchUpdateRiskScores(bytes32[] ids, uint64[] scores) external

// Get risk score
function getRiskScore(bytes32 id) external view returns (uint64 score, uint64 lastUpdated, bool isStale)

// Get high risk protocols
function getHighRiskProtocols() external view returns (bytes32[] memory)
```

### Vault Functions

```solidity
// Deposit tokens
function deposit(address token, uint256 amount) external

// Withdraw tokens
function withdraw(address token, uint256 amount) external

// Add protection rule
function addProtectionRule(bytes32 protocolId, uint64 threshold, address token, address safeAddress) external

// Chainlink automation
function checkUpkeep(bytes calldata) external view returns (bool, bytes memory)
function performUpkeep(bytes calldata) external
```

---

## Security Considerations

- **Oracle Trust**: Authorized updaters can set any risk score. Protect private keys.
- **Staleness**: Data older than 1 hour is ignored to prevent stale triggers.
- **Permissionless Protection**: Anyone can call `checkAndProtect` — this is a feature, not a bug.
- **Reentrancy**: All external state-changing functions use `nonReentrant`.
- **Token Safety**: `SafeERC20` handles non-standard tokens.

---

## License

MIT

---

## Contributing

Contributions welcome! Please read the contributing guidelines first.

---

## Acknowledgments

- DefiLlama for protocol data
- Chainlink for automation infrastructure
- OpenZeppelin for secure contract primitives
