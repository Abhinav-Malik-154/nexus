"""
DefiLlama Data Fetcher
Fetches real protocol data for anomaly detection
"""
import requests
import pandas as pd
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

class DataFetcher:
    def __init__(self, api_base: str = "https://api.llama.fi"):
        self.api_base = api_base
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Nexus-Backend/1.0'
        })
    
    def fetch_protocol_data(self, protocol_slug: str) -> Optional[Dict]:
        """Fetch current protocol data from DefiLlama"""
        try:
            # Get current TVL
            response = self.session.get(f"{self.api_base}/protocol/{protocol_slug}")
            response.raise_for_status()
            data = response.json()
            
            if not data or 'tvl' not in data:
                logger.warning(f"No TVL data for {protocol_slug}")
                return None
                
            # Get historical TVL for trend analysis
            historical = self._fetch_historical_tvl(protocol_slug)
            
            return {
                'protocol': protocol_slug,
                'current_tvl': data['tvl'][-1]['totalLiquidityUSD'] if data['tvl'] else 0,
                'timestamp': datetime.now().isoformat(),
                'historical_tvl': historical,
                'category': data.get('category', 'unknown'),
                'chain_tvls': data.get('chainTvls', {}),
                'methodology': data.get('methodology', {})
            }
            
        except requests.RequestException as e:
            logger.error(f"Error fetching {protocol_slug}: {e}")
            return None
            
        except Exception as e:
            logger.error(f"Unexpected error fetching {protocol_slug}: {e}")
            return None
    
    def _fetch_historical_tvl(self, protocol_slug: str) -> List[Dict]:
        """Fetch historical TVL data for trend calculation"""
        try:
            response = self.session.get(f"{self.api_base}/protocol/{protocol_slug}")
            response.raise_for_status()
            data = response.json()
            
            if not data.get('tvl'):
                return []
                
            # Return last 7 days of data
            now = datetime.now()
            week_ago = now - timedelta(days=7)
            
            historical = []
            for point in data['tvl'][-168:]:  # Last 168 hours (7 days)
                timestamp = datetime.fromtimestamp(point['date'])
                if timestamp >= week_ago:
                    historical.append({
                        'timestamp': timestamp.isoformat(),
                        'tvl': point['totalLiquidityUSD']
                    })
            
            return historical
            
        except Exception as e:
            logger.error(f"Error fetching historical data for {protocol_slug}: {e}")
            return []
    
    def fetch_all_protocols(self) -> List[Dict]:
        """Fetch data for all monitored protocols"""
        results = []
        
        for protocol in self.monitored_protocols:
            data = self.fetch_protocol_data(protocol)
            if data:
                results.append(data)
        
        return results
    
    def calculate_metrics(self, historical_data: List[Dict]) -> Dict:
        """Calculate metrics needed for anomaly detection"""
        if len(historical_data) < 2:
            return {
                'tvl_change_1h': 0,
                'tvl_change_1d': 0,
                'tvl_change_7d': 0,
                'tvl_volatility': 0,
                'data_points': len(historical_data)
            }
        
        # Sort by timestamp
        sorted_data = sorted(historical_data, key=lambda x: x['timestamp'])
        current_tvl = sorted_data[-1]['tvl']
        
        # Calculate changes
        tvl_change_1h = 0
        tvl_change_1d = 0
        tvl_change_7d = 0
        
        now = datetime.now()
        hour_ago = now - timedelta(hours=1)
        day_ago = now - timedelta(days=1)
        week_ago = now - timedelta(days=7)
        
        for point in sorted_data:
            timestamp = datetime.fromisoformat(point['timestamp'])
            
            if abs((timestamp - hour_ago).total_seconds()) < 3600:  # Within 1 hour
                tvl_change_1h = ((current_tvl - point['tvl']) / point['tvl'] * 100) if point['tvl'] > 0 else 0
            
            if abs((timestamp - day_ago).total_seconds()) < 86400:  # Within 1 day
                tvl_change_1d = ((current_tvl - point['tvl']) / point['tvl'] * 100) if point['tvl'] > 0 else 0
            
            if abs((timestamp - week_ago).total_seconds()) < 604800:  # Within 1 week
                tvl_change_7d = ((current_tvl - point['tvl']) / point['tvl'] * 100) if point['tvl'] > 0 else 0
        
        # Calculate volatility
        tvl_values = [point['tvl'] for point in sorted_data]
        tvl_volatility = pd.Series(tvl_values).std() / pd.Series(tvl_values).mean() * 100 if len(tvl_values) > 1 else 0
        
        return {
            'tvl_change_1h': round(tvl_change_1h, 2),
            'tvl_change_1d': round(tvl_change_1d, 2),
            'tvl_change_7d': round(tvl_change_7d, 2),
            'tvl_volatility': round(tvl_volatility, 2),
            'data_points': len(historical_data)
        }