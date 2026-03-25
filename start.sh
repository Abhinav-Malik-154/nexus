#!/bin/bash
#
# Nexus Protocol - Service Orchestrator
# Starts frontend and oracle updater services
#
# Usage:
#   ./start.sh              # Start all services
#   ./start.sh frontend     # Start frontend only
#   ./start.sh oracle       # Start oracle updater only
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info()  { echo -e "${BLUE}[INFO]${NC} $1"; }
log_ok()    { echo -e "${GREEN}[OK]${NC} $1"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

MODE="${1:-all}"
PIDS=()

cleanup() {
    echo ""
    log_info "Shutting down services..."
    for pid in "${PIDS[@]}"; do
        kill "$pid" 2>/dev/null || true
    done
    log_ok "All services stopped"
    exit 0
}

trap cleanup SIGINT SIGTERM

echo ""
echo "╔════════════════════════════════════════════════════════════╗"
echo "║            NEXUS PROTOCOL - SERVICES                       ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

start_frontend() {
    log_info "Starting frontend..."
    cd "$SCRIPT_DIR/frontend"

    if [[ ! -d "node_modules" ]]; then
        log_info "Installing frontend dependencies..."
        npm install --silent
    fi

    npm run dev &
    PIDS+=($!)
    log_ok "Frontend starting on http://localhost:3000"
}

start_oracle() {
    log_info "Starting oracle updater..."
    cd "$SCRIPT_DIR/model"

    if [[ ! -f ".env" ]]; then
        log_error "model/.env not found. Run ./deploy.sh first"
        return 1
    fi

    # Check Python dependencies
    python3 -c "import web3, dotenv" 2>/dev/null || {
        log_info "Installing Python dependencies..."
        pip3 install web3 python-dotenv --quiet
    }

    python3 update_oracle.py --watch &
    PIDS+=($!)
    log_ok "Oracle updater running (15 min intervals)"
}

case "$MODE" in
    frontend)
        start_frontend
        ;;
    oracle)
        start_oracle
        ;;
    all)
        start_frontend
        sleep 2
        start_oracle
        ;;
    *)
        echo "Usage: ./start.sh [frontend|oracle|all]"
        exit 1
        ;;
esac

echo ""
log_ok "Services running. Press Ctrl+C to stop."
echo ""
echo "  Frontend:       http://localhost:3000"
echo "  Oracle Updater: Running in watch mode"
echo ""

# Wait for all background processes
wait
