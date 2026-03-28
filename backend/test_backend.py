#!/usr/bin/env python3
"""
Test backend components before running server
"""
import sys
import os

# Add backend to path
sys.path.append('/home/mutant/nexus/backend')

def test_imports():
    """Test all component imports"""
    print("🧪 Testing imports...")
    
    try:
        from data_fetcher import DataFetcher
        print("✅ DataFetcher import OK")
    except Exception as e:
        print(f"❌ DataFetcher import failed: {e}")
        return False

    try:
        from oracle_updater import OracleUpdater
        print("✅ OracleUpdater import OK")  
    except Exception as e:
        print(f"❌ OracleUpdater import failed: {e}")
        return False

    try:
        from anomaly_detector import AnomalyDetector
        print("✅ AnomalyDetector import OK")
    except Exception as e:
        print(f"❌ AnomalyDetector import failed: {e}")
        return False
    
    return True

def test_data_fetcher():
    """Test data fetching"""
    print("\n🔍 Testing data fetcher...")
    
    try:
        from data_fetcher import DataFetcher
        fetcher = DataFetcher()
        data = fetcher.fetch_protocol_data('aave')
        
        if data and 'current_tvl' in data:
            tvl = data['current_tvl']
            print(f"✅ Fetched Aave data: TVL = ${tvl:,.0f}")
            return True
        else:
            print("❌ No data returned")
            return False
            
    except Exception as e:
        print(f"❌ Data fetch failed: {e}")
        return False

def test_anomaly_detector():
    """Test anomaly detection"""
    print("\n🤖 Testing anomaly detector...")
    
    try:
        from anomaly_detector import AnomalyDetector
        detector = AnomalyDetector()
        
        # Test with sample data
        test_data = {
            'tvl_change_1h': -25.0,  # Should trigger anomaly
            'tvl_change_1d': -10.0,
            'tvl_change_7d': 5.0,
            'tvl_volatility': 15.0,
            'current_tvl': 1000000000,
            'volume_24h': 0,
            'age_days': 365,
            'price_change_1d': 0,
            'price_change_7d': 0,
            'price_volatility': 0
        }
        
        result = detector.detect(test_data)
        is_anomaly, score, reasons = result
        print(f"✅ Anomaly detection result: Score = {score}, Reasons = {reasons}")
        
        return True
        
    except Exception as e:
        print(f"❌ Anomaly detection failed: {e}")
        return False

if __name__ == "__main__":
    print("🚀 BACKEND COMPONENT TESTING")
    print("=" * 40)
    
    success = True
    success &= test_imports()
    success &= test_data_fetcher()  
    success &= test_anomaly_detector()
    
    print("\n" + "=" * 40)
    if success:
        print("✅ ALL TESTS PASSED - Backend ready to start")
    else:
        print("❌ TESTS FAILED - Fix errors before running server")
        sys.exit(1)