"""
Nexus Backend Service - THE MISSING PIECE
FastAPI service that connects DefiLlama → Anomaly Detection → Oracle Updates

THIS IS WHAT MAKES THE SYSTEM ACTUALLY WORK
"""
from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
import logging
import asyncio
from datetime import datetime
from typing import Dict, List
import schedule
import threading
import time

# Local imports
from config import *
from data_fetcher import DataFetcher
from anomaly_detector import AnomalyDetector
from oracle_updater import OracleUpdater

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize components
app = FastAPI(title="Nexus Backend Service", version="1.0.0")

# CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:4000", "https://*.vercel.app"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global components
data_fetcher = DataFetcher()
anomaly_detector = AnomalyDetector()
oracle_updater = None

# Global state
last_update = datetime.now()
system_health = {
    "status": "starting",
    "last_update": None,
    "protocols_monitored": 0,
    "anomalies_detected": 0,
    "oracle_updates": 0,
    "errors": []
}

# Pydantic models
class ProtocolData(BaseModel):
    protocol: str
    risk_score: float
    anomaly_reasons: List[str]
    current_tvl: float
    tvl_change_1h: float
    tvl_change_1d: float
    timestamp: str

class SystemHealth(BaseModel):
    status: str
    last_update: str
    protocols_monitored: int
    anomalies_detected: int
    oracle_updates: int
    uptime_seconds: int

@app.on_event("startup")
async def startup_event():
    """Initialize system on startup"""
    global oracle_updater, system_health
    
    try:
        # Initialize Oracle updater
        if PRIVATE_KEY and ORACLE_ADDRESS:
            oracle_updater = OracleUpdater(RPC_URL, PRIVATE_KEY, ORACLE_ADDRESS)
            logger.info("Oracle updater initialized")
        else:
            logger.warning("Oracle updater not initialized - missing credentials")
        
        # Start background monitoring
        start_background_monitoring()
        
        system_health["status"] = "running"
        logger.info("🚀 Nexus Backend Service started successfully")
        
    except Exception as e:
        logger.error(f"Startup failed: {e}")
        system_health["status"] = "error"
        system_health["errors"].append(str(e))

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    global system_health, last_update
    
    return SystemHealth(
        status=system_health["status"],
        last_update=system_health.get("last_update", "never"),
        protocols_monitored=system_health.get("protocols_monitored", 0),
        anomalies_detected=system_health.get("anomalies_detected", 0),
        oracle_updates=system_health.get("oracle_updates", 0),
        uptime_seconds=int((datetime.now() - last_update).total_seconds())
    )

@app.get("/protocols")
async def get_protocol_data():
    """Get current protocol data and risk scores"""
    try:
        protocols = []
        
        for protocol_name in MONITORED_PROTOCOLS:
            # Get protocol data
            data = data_fetcher.fetch_protocol_data(protocol_name)
            if not data:
                continue
                
            # Calculate metrics
            metrics = data_fetcher.calculate_metrics(data.get('historical_tvl', []))
            
            # Create feature vector for anomaly detection
            feature_data = {
                **metrics,
                'current_tvl': data['current_tvl'],
                'volume_24h': 0,  # TODO: Add volume data
                'age_days': 365,  # TODO: Add protocol age
                'price_change_1d': 0,  # TODO: Add price data
                'price_change_7d': 0,
                'price_volatility': 0
            }
            
            # Detect anomalies
            is_anomaly, score, reasons = anomaly_detector.detect(feature_data)
            
            protocols.append(ProtocolData(
                protocol=protocol_name,
                risk_score=score,
                anomaly_reasons=reasons,
                current_tvl=data['current_tvl'],
                tvl_change_1h=metrics['tvl_change_1h'],
                tvl_change_1d=metrics['tvl_change_1d'],
                timestamp=datetime.now().isoformat()
            ))
        
        return {"protocols": protocols, "count": len(protocols)}
        
    except Exception as e:
        logger.error(f"Error getting protocol data: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/manual-update")
async def manual_update():
    """Manually trigger system update (for testing)"""
    try:
        success = await run_monitoring_cycle()
        return {"success": success, "timestamp": datetime.now().isoformat()}
    except Exception as e:
        logger.error(f"Manual update failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/oracle-scores")
async def get_oracle_scores():
    """Get current Oracle risk scores"""
    if not oracle_updater:
        raise HTTPException(status_code=503, detail="Oracle updater not available")
    
    try:
        scores = {}
        for protocol in MONITORED_PROTOCOLS:
            score, timestamp = oracle_updater.get_current_score(protocol)
            scores[protocol] = {
                "score": score,
                "timestamp": timestamp,
                "last_updated": datetime.fromtimestamp(timestamp).isoformat() if timestamp > 0 else "never"
            }
        
        return {"scores": scores}
        
    except Exception as e:
        logger.error(f"Error getting Oracle scores: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Background monitoring functions
async def run_monitoring_cycle() -> bool:
    """Run one complete monitoring cycle"""
    global system_health
    
    try:
        logger.info("🔄 Starting monitoring cycle")
        
        # Fetch all protocol data
        protocol_updates = {}
        anomaly_count = 0
        
        for protocol_name in MONITORED_PROTOCOLS:
            try:
                # Get protocol data
                data = data_fetcher.fetch_protocol_data(protocol_name)
                if not data:
                    continue
                
                # Calculate metrics
                metrics = data_fetcher.calculate_metrics(data.get('historical_tvl', []))
                
                # Create feature vector
                feature_data = {
                    **metrics,
                    'current_tvl': data['current_tvl'],
                    'volume_24h': 0,
                    'age_days': 365,
                    'price_change_1d': 0,
                    'price_change_7d': 0,
                    'price_volatility': 0
                }
                
                # Detect anomalies
                is_anomaly, score, reasons = anomaly_detector.detect(feature_data)
                
                # Log anomalies
                if score > ANOMALY_THRESHOLD:
                    logger.warning(f"🚨 ANOMALY DETECTED: {protocol_name} - Score: {score}, Reasons: {reasons}")
                    anomaly_count += 1
                
                protocol_updates[protocol_name] = score
                
            except Exception as e:
                logger.error(f"Error processing {protocol_name}: {e}")
                system_health["errors"].append(f"{protocol_name}: {str(e)}")
        
        # Update Oracle if we have updates and Oracle is available
        if protocol_updates and oracle_updater:
            success = oracle_updater.batch_update_scores(protocol_updates)
            if success:
                system_health["oracle_updates"] += 1
                logger.info(f"✅ Updated Oracle with {len(protocol_updates)} scores")
            else:
                logger.error("❌ Oracle update failed")
        
        # Update system health
        system_health.update({
            "last_update": datetime.now().isoformat(),
            "protocols_monitored": len(protocol_updates),
            "anomalies_detected": system_health.get("anomalies_detected", 0) + anomaly_count,
            "status": "running"
        })
        
        logger.info(f"✅ Monitoring cycle complete: {len(protocol_updates)} protocols, {anomaly_count} anomalies")
        return True
        
    except Exception as e:
        logger.error(f"❌ Monitoring cycle failed: {e}")
        system_health["status"] = "error"
        system_health["errors"].append(str(e))
        return False

def monitoring_worker():
    """Background worker for periodic monitoring"""
    logger.info("📡 Starting monitoring worker")
    
    while True:
        try:
            # Run monitoring cycle
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(run_monitoring_cycle())
            loop.close()
            
        except Exception as e:
            logger.error(f"Monitoring worker error: {e}")
        
        # Wait for next cycle
        time.sleep(UPDATE_INTERVAL_MINUTES * 60)

def start_background_monitoring():
    """Start background monitoring thread"""
    monitoring_thread = threading.Thread(target=monitoring_worker, daemon=True)
    monitoring_thread.start()
    logger.info(f"🔄 Background monitoring started (every {UPDATE_INTERVAL_MINUTES} minutes)")

if __name__ == "__main__":
    logger.info("🚀 Starting Nexus Backend Service")
    uvicorn.run("server:app", host="0.0.0.0", port=PORT, reload=False)