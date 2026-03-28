import os
from dotenv import load_dotenv

load_dotenv()

# Blockchain Configuration
PRIVATE_KEY = os.getenv("PRIVATE_KEY", "")
RPC_URL = os.getenv("RPC_URL", "https://polygon-amoy.g.alchemy.com/v2/R7-SBXX61zcZPfPAZd7BC")
ORACLE_ADDRESS = os.getenv("ORACLE_ADDRESS", "0x30BB8531e998A3c6574C8985e9c360d621493595")
VAULT_ADDRESS = os.getenv("VAULT_ADDRESS", "0x7E86F2eF483a5B43d8f6d41a88EeeFE7ED745CdC")

# API Configuration  
DEFILLAMA_API = "https://api.llama.fi"
PORT = int(os.getenv("PORT", "8000"))

# Monitoring Configuration
UPDATE_INTERVAL_MINUTES = int(os.getenv("UPDATE_INTERVAL", "10"))
ANOMALY_THRESHOLD = float(os.getenv("ANOMALY_THRESHOLD", "70.0"))

# Protocol Configuration
MONITORED_PROTOCOLS = [
    "aave",
    "compound", 
    "makerdao",
    "lido",
    "curve",
    "uniswap",
    "convex-finance",
    "rocket-pool",
    "yearn-finance", 
    "balancer"
]

# Validation
if not PRIVATE_KEY:
    raise ValueError("PRIVATE_KEY environment variable is required")
if not ORACLE_ADDRESS.startswith("0x"):
    raise ValueError("Invalid ORACLE_ADDRESS format")