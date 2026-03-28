"""
Oracle Updater - Updates smart contract with risk scores
THE CRITICAL INTEGRATION PIECE
"""
from web3 import Web3
from eth_account import Account
import json
import logging
from typing import Dict, List
import time

logger = logging.getLogger(__name__)

# Oracle ABI (simplified - just the functions we need)
ORACLE_ABI = [
    {
        "inputs": [{"name": "protocolId", "type": "bytes32"}, {"name": "score", "type": "uint64"}],
        "name": "updateRiskScore",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [{"name": "protocolIds", "type": "bytes32[]"}, {"name": "scores", "type": "uint64[]"}],
        "name": "batchUpdate", 
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [{"name": "protocolId", "type": "bytes32"}],
        "name": "getRiskScore",
        "outputs": [{"name": "", "type": "uint64"}, {"name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function"
    }
]

class OracleUpdater:
    def __init__(self, rpc_url: str, private_key: str, oracle_address: str):
        self.w3 = Web3(Web3.HTTPProvider(rpc_url))
        self.account = Account.from_key(private_key)
        self.oracle_address = Web3.to_checksum_address(oracle_address)
        self.contract = self.w3.eth.contract(
            address=self.oracle_address,
            abi=ORACLE_ABI
        )
        
        # Verify connection
        if not self.w3.is_connected():
            raise ConnectionError(f"Cannot connect to RPC: {rpc_url}")
        
        logger.info(f"Oracle updater connected to {oracle_address}")
    
    def protocol_name_to_id(self, name: str) -> bytes:
        """Convert protocol name to bytes32 ID"""
        return self.w3.keccak(text=name.lower())[:32]
    
    def update_single_score(self, protocol_name: str, risk_score: float) -> bool:
        """Update risk score for single protocol"""
        try:
            protocol_id = self.protocol_name_to_id(protocol_name)
            score_uint = min(100, max(0, int(risk_score)))  # Clamp to 0-100
            
            # Build transaction
            function = self.contract.functions.updateRiskScore(protocol_id, score_uint)
            
            # Estimate gas
            gas_estimate = function.estimate_gas({'from': self.account.address})
            
            # Get current gas price
            gas_price = self.w3.eth.gas_price
            
            # Build transaction
            transaction = function.build_transaction({
                'from': self.account.address,
                'gas': int(gas_estimate * 1.2),  # 20% buffer
                'gasPrice': gas_price,
                'nonce': self.w3.eth.get_transaction_count(self.account.address)
            })
            
            # Sign and send
            signed = self.account.sign_transaction(transaction)
            tx_hash = self.w3.eth.send_raw_transaction(signed.rawTransaction)
            
            logger.info(f"Updated {protocol_name} risk score to {score_uint}. TX: {tx_hash.hex()}")
            
            # Wait for confirmation (optional - don't block)
            return True
            
        except Exception as e:
            logger.error(f"Failed to update {protocol_name}: {e}")
            return False
    
    def batch_update_scores(self, protocol_scores: Dict[str, float]) -> bool:
        """Update multiple risk scores in single transaction"""
        try:
            if not protocol_scores:
                return True
                
            protocol_ids = []
            scores = []
            
            for protocol_name, risk_score in protocol_scores.items():
                protocol_ids.append(self.protocol_name_to_id(protocol_name))
                scores.append(min(100, max(0, int(risk_score))))
            
            # Build batch transaction
            function = self.contract.functions.batchUpdate(protocol_ids, scores)
            
            # Estimate gas
            gas_estimate = function.estimate_gas({'from': self.account.address})
            gas_price = self.w3.eth.gas_price
            
            transaction = function.build_transaction({
                'from': self.account.address,
                'gas': int(gas_estimate * 1.2),
                'gasPrice': gas_price,
                'nonce': self.w3.eth.get_transaction_count(self.account.address)
            })
            
            # Sign and send
            signed = self.account.sign_transaction(transaction)
            tx_hash = self.w3.eth.send_raw_transaction(signed.rawTransaction)
            
            logger.info(f"Batch updated {len(protocol_scores)} protocols. TX: {tx_hash.hex()}")
            return True
            
        except Exception as e:
            logger.error(f"Batch update failed: {e}")
            return False
    
    def get_current_score(self, protocol_name: str) -> tuple[int, int]:
        """Get current risk score and timestamp for protocol"""
        try:
            protocol_id = self.protocol_name_to_id(protocol_name)
            score, timestamp = self.contract.functions.getRiskScore(protocol_id).call()
            return score, timestamp
        except Exception as e:
            logger.error(f"Failed to get score for {protocol_name}: {e}")
            return 0, 0
    
    def verify_update(self, protocol_name: str, expected_score: float) -> bool:
        """Verify that score was updated correctly"""
        try:
            actual_score, _ = self.get_current_score(protocol_name)
            expected = int(expected_score)
            return abs(actual_score - expected) <= 1  # Allow small rounding differences
        except Exception as e:
            logger.error(f"Verification failed for {protocol_name}: {e}")
            return False