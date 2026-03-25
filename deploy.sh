#!/bin/bash
#
# Nexus Protocol - Automated Deployment Script
# Deploys contracts to Polygon Amoy and configures all services
#
# Usage:
#   ./deploy.sh              # Full deployment
#   ./deploy.sh --dry-run    # Preview without deploying
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info()  { echo -e "${BLUE}[INFO]${NC} $1"; }
log_ok()    { echo -e "${GREEN}[OK]${NC} $1"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

DRY_RUN=false
[[ "${1:-}" == "--dry-run" ]] && DRY_RUN=true

echo ""
echo "╔════════════════════════════════════════════════════════════╗"
echo "║            NEXUS PROTOCOL - DEPLOYMENT                     ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

# ─────────────────────────────────────────────────────────────────
# 1. Validate Prerequisites
# ─────────────────────────────────────────────────────────────────
log_info "Checking prerequisites..."

command -v forge >/dev/null 2>&1 || { log_error "Foundry not installed. Run: curl -L https://foundry.paradigm.xyz | bash"; exit 1; }
command -v cast >/dev/null 2>&1 || { log_error "Cast not found (part of Foundry)"; exit 1; }
command -v node >/dev/null 2>&1 || { log_error "Node.js not installed"; exit 1; }
command -v python3 >/dev/null 2>&1 || { log_error "Python 3 not installed"; exit 1; }

log_ok "All prerequisites installed"

# ─────────────────────────────────────────────────────────────────
# 2. Load Environment Variables
# ─────────────────────────────────────────────────────────────────
if [[ ! -f "contracts/.env" ]]; then
    log_error "Missing contracts/.env file. Create it with:"
    echo ""
    echo "  PRIVATE_KEY=0xYOUR_PRIVATE_KEY"
    echo "  POLYGON_AMOY_RPC=https://polygon-amoy.g.alchemy.com/v2/YOUR_KEY"
    echo ""
    exit 1
fi

set -a
source contracts/.env
set +a

# Support both variable names (POLYGON_AMOY_RPC or RPC_URL)
RPC_URL="${POLYGON_AMOY_RPC:-$RPC_URL}"

[[ -z "${PRIVATE_KEY:-}" ]] && { log_error "PRIVATE_KEY not set in contracts/.env"; exit 1; }
[[ -z "${RPC_URL:-}" ]] && { log_error "POLYGON_AMOY_RPC not set in contracts/.env"; exit 1; }

DEPLOYER_ADDRESS=$(cast wallet address "$PRIVATE_KEY" 2>/dev/null)
log_ok "Deployer: $DEPLOYER_ADDRESS"

# Check balance
BALANCE=$(cast balance "$DEPLOYER_ADDRESS" --rpc-url "$RPC_URL" 2>/dev/null || echo "0")
BALANCE_ETH=$(cast from-wei "$BALANCE" 2>/dev/null || echo "0")
log_info "Balance: $BALANCE_ETH POL"

if [[ "$BALANCE" == "0" ]]; then
    log_error "No POL balance. Get testnet tokens from: https://faucet.polygon.technology/"
    exit 1
fi

# ─────────────────────────────────────────────────────────────────
# 3. Build Contracts
# ─────────────────────────────────────────────────────────────────
log_info "Building contracts..."
cd contracts
forge build --silent
log_ok "Contracts compiled"

# ─────────────────────────────────────────────────────────────────
# 4. Deploy Contracts
# ─────────────────────────────────────────────────────────────────
if $DRY_RUN; then
    log_warn "[DRY RUN] Skipping deployment"
    ORACLE_ADDRESS="0xDRY_RUN_ORACLE_ADDRESS"
    VAULT_ADDRESS="0xDRY_RUN_VAULT_ADDRESS"
else
    log_info "Deploying to Polygon Amoy..."

    DEPLOY_OUTPUT=$(forge script script/Deploy.s.sol:DeployNexus \
        --rpc-url "$RPC_URL" \
        --broadcast \
        --private-key "$PRIVATE_KEY" \
        2>&1) || {
        log_error "Deployment failed"
        echo "$DEPLOY_OUTPUT"
        exit 1
    }

    # Extract addresses from deployment output
    ORACLE_ADDRESS=$(echo "$DEPLOY_OUTPUT" | grep -oP 'NexusRiskOracle:\s*\K0x[a-fA-F0-9]{40}' | tail -1)
    VAULT_ADDRESS=$(echo "$DEPLOY_OUTPUT" | grep -oP 'ProtectionVault:\s*\K0x[a-fA-F0-9]{40}' | tail -1)

    if [[ -z "$ORACLE_ADDRESS" ]] || [[ -z "$VAULT_ADDRESS" ]]; then
        log_error "Failed to extract contract addresses from output"
        echo "$DEPLOY_OUTPUT"
        exit 1
    fi

    log_ok "NexusRiskOracle: $ORACLE_ADDRESS"
    log_ok "ProtectionVault: $VAULT_ADDRESS"
fi

cd "$SCRIPT_DIR"

# ─────────────────────────────────────────────────────────────────
# 5. Update Frontend Configuration
# ─────────────────────────────────────────────────────────────────
log_info "Updating frontend configuration..."

CONTRACTS_FILE="frontend/src/lib/contracts.ts"

if [[ -f "$CONTRACTS_FILE" ]]; then
    sed -i "s|NEXUS_ORACLE: '0x[a-fA-F0-9]\{40\}'|NEXUS_ORACLE: '${ORACLE_ADDRESS}'|g" "$CONTRACTS_FILE"
    sed -i "s|PROTECTION_VAULT: '0x[a-fA-F0-9]\{40\}'|PROTECTION_VAULT: '${VAULT_ADDRESS}'|g" "$CONTRACTS_FILE"
    log_ok "Updated $CONTRACTS_FILE"
else
    log_warn "Frontend contracts file not found: $CONTRACTS_FILE"
fi

# ─────────────────────────────────────────────────────────────────
# 6. Configure ML Oracle Updater
# ─────────────────────────────────────────────────────────────────
log_info "Configuring oracle updater..."

cat > model/.env << EOF
# Nexus Oracle Updater Configuration
# Generated by deploy.sh on $(date -Iseconds)

RPC_URL=${RPC_URL}
PRIVATE_KEY=${PRIVATE_KEY}
ORACLE_ADDRESS=${ORACLE_ADDRESS}
EOF

log_ok "Created model/.env"

# ─────────────────────────────────────────────────────────────────
# 7. Add Updater Authorization
# ─────────────────────────────────────────────────────────────────
if $DRY_RUN; then
    log_warn "[DRY RUN] Skipping updater authorization"
else
    log_info "Adding $DEPLOYER_ADDRESS as authorized updater..."

    cd contracts
    ORACLE_ADDRESS="$ORACLE_ADDRESS" UPDATER_ADDRESS="$DEPLOYER_ADDRESS" \
        forge script script/Deploy.s.sol:AddUpdater \
        --rpc-url "$RPC_URL" \
        --broadcast \
        --private-key "$PRIVATE_KEY" \
        >/dev/null 2>&1 || {
            log_warn "Updater may already be authorized (or you are the owner)"
        }
    cd "$SCRIPT_DIR"

    log_ok "Updater authorized"
fi

# ─────────────────────────────────────────────────────────────────
# 8. Install Dependencies
# ─────────────────────────────────────────────────────────────────
log_info "Checking frontend dependencies..."
if [[ ! -d "frontend/node_modules" ]]; then
    cd frontend && npm install --silent && cd "$SCRIPT_DIR"
    log_ok "Frontend dependencies installed"
else
    log_ok "Frontend dependencies already installed"
fi

log_info "Checking Python dependencies..."
pip3 show web3 >/dev/null 2>&1 || pip3 install web3 python-dotenv --quiet
log_ok "Python dependencies ready"

# ─────────────────────────────────────────────────────────────────
# Summary
# ─────────────────────────────────────────────────────────────────
echo ""
echo "╔════════════════════════════════════════════════════════════╗"
echo "║            DEPLOYMENT COMPLETE                             ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""
echo "  NexusRiskOracle:  $ORACLE_ADDRESS"
echo "  ProtectionVault:  $VAULT_ADDRESS"
echo ""
echo "  Explorer: https://amoy.polygonscan.com/address/$ORACLE_ADDRESS"
echo ""
echo "  Next steps:"
echo "    1. Run ./start.sh to start all services"
echo "    2. Open http://localhost:3000 in your browser"
echo ""

# Save deployment info
cat > deployment.json << EOF
{
  "network": "polygon-amoy",
  "chainId": 80002,
  "timestamp": "$(date -Iseconds)",
  "deployer": "$DEPLOYER_ADDRESS",
  "contracts": {
    "NexusRiskOracle": "$ORACLE_ADDRESS",
    "ProtectionVault": "$VAULT_ADDRESS"
  },
  "explorer": "https://amoy.polygonscan.com"
}
EOF

log_ok "Saved deployment info to deployment.json"
