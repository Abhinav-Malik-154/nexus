#!/usr/bin/env python3
"""
Nexus Oracle Updater

Production-grade script to push GNN risk predictions to the on-chain NexusRiskOracle.
Designed for reliability, gas efficiency, and operational monitoring.

Usage:
    python update_oracle.py                    # Single update
    python update_oracle.py --watch            # Continuous mode (15 min intervals)
    python update_oracle.py --dry-run          # Preview without sending tx

Requirements:
    pip install web3 python-dotenv

Environment Variables (in .env):
    RPC_URL=https://rpc-amoy.polygon.technology
    PRIVATE_KEY=your_private_key_here
    ORACLE_ADDRESS=0x...
"""

import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import TypedDict

from dotenv import load_dotenv
from web3 import Web3
from web3.middleware import ExtraDataToPOAMiddleware

# ═══════════════════════════════════════════════════════════════════════════
#                              CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("nexus-oracle")

# Path to GNN predictions (in project root /data folder)
PREDICTIONS_PATH = Path(__file__).parent.parent / "data" / "gnn_predictions.json"

# Update interval for watch mode (seconds)
UPDATE_INTERVAL = 15 * 60  # 15 minutes

# Gas configuration
MAX_GAS_PRICE_GWEI = 100
GAS_LIMIT_PER_PROTOCOL = 50_000
BASE_GAS_LIMIT = 100_000


# ═══════════════════════════════════════════════════════════════════════════
#                                  TYPES
# ═══════════════════════════════════════════════════════════════════════════


class Prediction(TypedDict):
    protocol: str
    gnn_risk_score: float
    level: str


class GNNPredictions(TypedDict):
    predictions: list[Prediction]
    model_info: dict
    timestamp: str


# ═══════════════════════════════════════════════════════════════════════════
#                             CONTRACT ABI
# ═══════════════════════════════════════════════════════════════════════════

# Minimal ABI for NexusRiskOracle (gas-optimized version)
ORACLE_ABI = [
    {
        "name": "batchUpdateRiskScoresByName",
        "type": "function",
        "stateMutability": "nonpayable",
        "inputs": [
            {"name": "_protocolNames", "type": "string[]"},
            {"name": "scores", "type": "uint64[]"},
        ],
        "outputs": [],
    },
    {
        "name": "updateRiskScoreByName",
        "type": "function",
        "stateMutability": "nonpayable",
        "inputs": [
            {"name": "protocolName", "type": "string"},
            {"name": "score", "type": "uint64"},
        ],
        "outputs": [],
    },
    {
        "name": "getRiskScoreByName",
        "type": "function",
        "stateMutability": "view",
        "inputs": [{"name": "protocolName", "type": "string"}],
        "outputs": [
            {"name": "score", "type": "uint64"},
            {"name": "lastUpdated", "type": "uint64"},
            {"name": "isStale", "type": "bool"},
        ],
    },
    {
        "name": "getProtocolCount",
        "type": "function",
        "stateMutability": "view",
        "inputs": [],
        "outputs": [{"name": "", "type": "uint256"}],
    },
    {
        "name": "alertThreshold",
        "type": "function",
        "stateMutability": "view",
        "inputs": [],
        "outputs": [{"name": "", "type": "uint64"}],
    },
    {
        "name": "authorizedUpdaters",
        "type": "function",
        "stateMutability": "view",
        "inputs": [{"name": "", "type": "address"}],
        "outputs": [{"name": "", "type": "bool"}],
    },
]


# ═══════════════════════════════════════════════════════════════════════════
#                            ORACLE UPDATER
# ═══════════════════════════════════════════════════════════════════════════


class OracleUpdater:
    """Production-grade oracle updater with gas optimization and monitoring."""

    def __init__(self, rpc_url: str, private_key: str, oracle_address: str):
        self.w3 = Web3(Web3.HTTPProvider(rpc_url))

        # Polygon/POA middleware
        self.w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)

        if not self.w3.is_connected():
            raise ConnectionError(f"Failed to connect to RPC: {rpc_url}")

        self.account = self.w3.eth.account.from_key(private_key)
        self.oracle = self.w3.eth.contract(
            address=Web3.to_checksum_address(oracle_address), abi=ORACLE_ABI
        )

        logger.info(f"Connected to chain ID: {self.w3.eth.chain_id}")
        logger.info(f"Updater address: {self.account.address}")
        logger.info(f"Oracle address: {oracle_address}")

    def verify_authorization(self) -> bool:
        """Check if updater is authorized on the oracle contract."""
        try:
            is_authorized = self.oracle.functions.authorizedUpdaters(
                self.account.address
            ).call()
            if not is_authorized:
                logger.warning(f"Address {self.account.address} is NOT authorized!")
                logger.warning("Add via: oracle.addAuthorizedUpdater(address)")
            return is_authorized
        except Exception as e:
            logger.error(f"Failed to check authorization: {e}")
            return False

    def load_predictions(self) -> GNNPredictions | None:
        """Load GNN predictions from JSON file."""
        if not PREDICTIONS_PATH.exists():
            logger.error(f"Predictions file not found: {PREDICTIONS_PATH}")
            return None

        try:
            with open(PREDICTIONS_PATH) as f:
                data = json.load(f)

            logger.info(f"Loaded {len(data['predictions'])} predictions")
            logger.info(f"Model timestamp: {data['timestamp']}")
            return data
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in predictions file: {e}")
            return None

    def prepare_batch(
        self, predictions: list[Prediction]
    ) -> tuple[list[str], list[int]]:
        """
        Convert predictions to contract-compatible format.

        - Protocol names: string[]
        - Scores: uint64[] (0-100, rounded from float)
        """
        names: list[str] = []
        scores: list[int] = []

        for pred in predictions:
            protocol = pred["protocol"]
            score = min(100, max(0, round(pred["gnn_risk_score"])))

            names.append(protocol)
            scores.append(score)

            level = pred.get("level", "UNKNOWN")
            logger.debug(f"  {protocol}: {score} ({level})")

        return names, scores

    def estimate_gas(self, names: list[str], scores: list[int]) -> int:
        """Estimate gas for batch update."""
        try:
            gas_estimate = self.oracle.functions.batchUpdateRiskScoresByName(
                names, scores
            ).estimate_gas({"from": self.account.address})

            # Add 20% buffer
            return int(gas_estimate * 1.2)
        except Exception as e:
            logger.warning(f"Gas estimation failed: {e}")
            return BASE_GAS_LIMIT + (GAS_LIMIT_PER_PROTOCOL * len(names))

    def get_gas_price(self) -> int:
        """Get current gas price with cap."""
        gas_price = self.w3.eth.gas_price
        max_gas = Web3.to_wei(MAX_GAS_PRICE_GWEI, "gwei")

        if gas_price > max_gas:
            logger.warning(
                f"Gas price {Web3.from_wei(gas_price, 'gwei'):.2f} gwei > max ({MAX_GAS_PRICE_GWEI})"
            )
            return max_gas

        return gas_price

    def update(self, dry_run: bool = False) -> bool:
        """
        Execute oracle update.

        Args:
            dry_run: If True, simulate without sending transaction

        Returns:
            True if update successful
        """
        logger.info("=" * 60)
        logger.info("Starting oracle update")
        logger.info("=" * 60)

        # Load predictions
        data = self.load_predictions()
        if not data:
            return False

        predictions = data["predictions"]
        if not predictions:
            logger.warning("No predictions to update")
            return False

        # Prepare batch
        names, scores = self.prepare_batch(predictions)

        # Log high-risk protocols
        threshold = self.oracle.functions.alertThreshold().call()
        high_risk = [n for n, s in zip(names, scores) if s >= threshold]
        if high_risk:
            logger.warning(f"HIGH RISK PROTOCOLS: {high_risk}")

        # Gas estimation
        gas_limit = self.estimate_gas(names, scores)
        gas_price = self.get_gas_price()

        estimated_cost = Web3.from_wei(gas_limit * gas_price, "ether")
        logger.info(f"Estimated gas: {gas_limit:,}")
        logger.info(f"Gas price: {Web3.from_wei(gas_price, 'gwei'):.2f} gwei")
        logger.info(f"Estimated cost: {estimated_cost:.6f} ETH/POL")

        if dry_run:
            logger.info("[DRY RUN] Would update:")
            for name, score in zip(names, scores):
                logger.info(f"  {name}: {score}")
            return True

        # Build transaction
        nonce = self.w3.eth.get_transaction_count(self.account.address)

        tx = self.oracle.functions.batchUpdateRiskScoresByName(names, scores).build_transaction(
            {
                "from": self.account.address,
                "nonce": nonce,
                "gas": gas_limit,
                "gasPrice": gas_price,
            }
        )

        # Sign and send
        signed_tx = self.account.sign_transaction(tx)
        tx_hash = self.w3.eth.send_raw_transaction(signed_tx.raw_transaction)

        logger.info(f"Transaction sent: {tx_hash.hex()}")

        # Wait for confirmation
        logger.info("Waiting for confirmation...")
        receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)

        if receipt["status"] == 1:
            logger.info(f"SUCCESS! Block: {receipt['blockNumber']}")
            logger.info(f"Gas used: {receipt['gasUsed']:,}")
            actual_cost = Web3.from_wei(
                receipt["gasUsed"] * receipt["effectiveGasPrice"], "ether"
            )
            logger.info(f"Actual cost: {actual_cost:.6f} ETH/POL")
            return True
        else:
            logger.error("Transaction FAILED!")
            return False

    def watch(self, interval: int = UPDATE_INTERVAL):
        """Continuous update mode."""
        logger.info(f"Starting watch mode (interval: {interval}s)")

        while True:
            try:
                self.update()
            except Exception as e:
                logger.error(f"Update failed: {e}")

            next_update = datetime.now().timestamp() + interval
            next_time = datetime.fromtimestamp(next_update).strftime("%H:%M:%S")
            logger.info(f"Next update at {next_time}")

            time.sleep(interval)


# ═══════════════════════════════════════════════════════════════════════════
#                                  MAIN
# ═══════════════════════════════════════════════════════════════════════════


def main():
    parser = argparse.ArgumentParser(
        description="Nexus Oracle Updater - Push GNN predictions on-chain"
    )
    parser.add_argument(
        "--watch", action="store_true", help="Run continuously (15 min intervals)"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Preview without sending transaction"
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=UPDATE_INTERVAL,
        help="Update interval in seconds (watch mode)",
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="Debug logging")
    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Load environment
    load_dotenv()

    rpc_url = os.getenv("RPC_URL")
    private_key = os.getenv("PRIVATE_KEY")
    oracle_address = os.getenv("ORACLE_ADDRESS")

    if not all([rpc_url, private_key, oracle_address]):
        logger.error("Missing environment variables. Create .env file:")
        logger.error("  RPC_URL=https://...")
        logger.error("  PRIVATE_KEY=0x...")
        logger.error("  ORACLE_ADDRESS=0x...")
        sys.exit(1)

    try:
        updater = OracleUpdater(rpc_url, private_key, oracle_address)

        # Verify authorization
        if not args.dry_run and not updater.verify_authorization():
            logger.error("Updater not authorized. Exiting.")
            sys.exit(1)

        if args.watch:
            updater.watch(args.interval)
        else:
            success = updater.update(dry_run=args.dry_run)
            sys.exit(0 if success else 1)

    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
