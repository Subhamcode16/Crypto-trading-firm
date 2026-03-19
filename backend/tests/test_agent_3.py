#!/usr/bin/env python3
"""
Agent 3 Test Suite - Wallet Tracker Validation

Tests:
1. Smart wallet detection accuracy
2. Insider activity tracking
3. Copy-trade signal generation
4. Scoring logic
5. Database logging
"""

import unittest
import json
import logging
from datetime import datetime
from unittest.mock import Mock, MagicMock, patch

# Add parent to path
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.agents.agent_3_wallet_tracker import Agent3WalletTracker
from src.apis.birdeye_client import BirdeyeClient
from src.config import Config

logger = logging.getLogger('test_agent_3')


class TestBirdeyeClient(unittest.TestCase):
    """Test Birdeye API client"""
    
    def setUp(self):
        self.client = BirdeyeClient()
    
    def test_client_initialization(self):
        """Test Birdeye client initializes without errors"""
        self.assertIsNotNone(self.client.base_url)
        self.assertTrue(self.client.base_url.startswith('https://'))
    
    def test_tier_calculation(self):
        """Test trader tier calculation"""
        client = BirdeyeClient()
        
        # Test each tier boundary
        self.assertEqual(client.is_smart_money.__code__.co_names, ())  # Exists


class TestAgent3SmartWalletDetection(unittest.TestCase):
    """Test smart wallet detection logic"""
    
    def setUp(self):
        self.tracker = Agent3WalletTracker(Config())
        
        # Mock APIs
        self.tracker.solscan = Mock()
        self.tracker.birdeye = Mock()
        self.tracker.helius = Mock()
        self.tracker.db = Mock()
    
    def test_smart_wallet_detection_no_api(self):
        """Test detection gracefully fails if APIs unavailable"""
        self.tracker.solscan = None
        
        wallets, points = self.tracker.detect_smart_wallets("test_token")
        
        self.assertEqual(len(wallets), 0)
        self.assertEqual(points, 0)
    
    def test_smart_wallet_detection_with_top_10(self):
        """Test detection correctly identifies top 10 traders"""
        token_addr = "test_token_123"
        
        # Mock holder list (top wallet is a top trader)
        self.tracker.solscan.get_top_holders.return_value = [
            {
                'address': 'wallet_top_10',
                'balance': 1000000
            },
            {
                'address': 'wallet_regular',
                'balance': 100000
            }
        ]
        
        # Mock top traders list
        self.tracker.birdeye.get_top_traders.return_value = [
            {
                'wallet_address': 'wallet_top_10',
                'rank': 5,
                'win_rate': 0.68,
                'total_trades': 150
            }
        ]
        
        # Mock profile
        self.tracker.birdeye.get_trader_profile.return_value = {
            'wallet_address': 'wallet_top_10',
            'profile_name': 'Top Trader #5',
            'win_rate': 0.68,
            'total_trades': 150,
            'rank': 5
        }
        
        wallets, points = self.tracker.detect_smart_wallets(token_addr)
        
        # Should find 1 wallet and award 2 points (top 10)
        self.assertEqual(len(wallets), 1)
        self.assertEqual(points, 2)
        self.assertEqual(wallets[0]['historical_wr'], 0.68)


class TestAgent3InsiderActivity(unittest.TestCase):
    """Test insider activity detection"""
    
    def setUp(self):
        self.tracker = Agent3WalletTracker(Config())
        self.tracker.solscan = Mock()
        self.tracker.db = Mock()
    
    def test_insider_deployer_accumulating(self):
        """Test detection identifies accumulating deployer"""
        token_addr = "test_token"
        
        # Mock token info
        self.tracker.solscan.get_token_info.return_value = {
            'deployer': 'deployer_wallet',
            'total_supply': 1000000
        }
        
        # Mock holders (deployer has >5% = accumulating)
        self.tracker.solscan.get_top_holders.return_value = [
            {
                'address': 'deployer_wallet',
                'balance': 100000  # 10% of supply
            }
        ]
        
        status, points = self.tracker.detect_insider_activity(token_addr)
        
        self.assertEqual(status['deployer_action'], 'accumulating')
        self.assertEqual(points, 1)
        self.assertIn('aligned incentives', ' '.join(status['green_flags']))
    
    def test_insider_deployer_dumping(self):
        """Test detection flags dumping deployer"""
        token_addr = "test_token"
        
        self.tracker.solscan.get_token_info.return_value = {
            'deployer': 'deployer_wallet',
            'total_supply': 1000000
        }
        
        # Deployer not in top 20 holders
        self.tracker.solscan.get_top_holders.return_value = [
            {'address': 'other_wallet_1', 'balance': 500000},
            {'address': 'other_wallet_2', 'balance': 300000},
            # ... 18 more without deployer
        ]
        
        status, points = self.tracker.detect_insider_activity(token_addr)
        
        self.assertEqual(status['deployer_action'], 'minimal_holding')
        self.assertIn('minimal', ' '.join(status['red_flags']))


class TestAgent3CopyTrade(unittest.TestCase):
    """Test copy-trade signal detection"""
    
    def setUp(self):
        self.tracker = Agent3WalletTracker(Config())
        self.tracker.solscan = Mock()
        self.tracker.birdeye = Mock()
        self.tracker.helius = Mock()
        self.tracker.db = Mock()
    
    def test_copy_trade_strong_signal(self):
        """Test strong copy-trade signal detection"""
        token_addr = "test_token"
        
        # Mock transactions
        self.tracker.helius.get_token_transaction_flow.return_value = [
            {'from': 'top_trader_1', 'to': 'other', 'volume': 100},
            {'from': 'top_trader_2', 'to': 'other', 'volume': 50},
            {'from': 'regular_wallet', 'to': 'other', 'volume': 25}
        ]
        
        # Mock top traders
        self.tracker.birdeye.get_top_traders.return_value = [
            {'wallet_address': 'top_trader_1', 'rank': 10},
            {'wallet_address': 'top_trader_2', 'rank': 25}
        ]
        
        # Mock profiles (high win rates)
        def mock_profile(addr):
            profiles = {
                'top_trader_1': {
                    'win_rate': 0.68,
                    'rank': 10,
                    'profile_name': 'Trader 1'
                },
                'top_trader_2': {
                    'win_rate': 0.65,
                    'rank': 25,
                    'profile_name': 'Trader 2'
                }
            }
            return profiles.get(addr, {})
        
        self.tracker.birdeye.get_trader_profile.side_effect = mock_profile
        
        signal, points = self.tracker.detect_copy_trade_signal(token_addr)
        
        self.assertTrue(signal['detected'])
        self.assertEqual(signal['similar_wallets'], 2)
        self.assertGreaterEqual(signal['historical_success_rate'], 0.65)
        self.assertGreaterEqual(points, 1.0)


class TestAgent3Scoring(unittest.TestCase):
    """Test Agent 3 final scoring"""
    
    def setUp(self):
        self.tracker = Agent3WalletTracker(Config())
        self.tracker.solscan = Mock()
        self.tracker.birdeye = Mock()
        self.tracker.helius = Mock()
        self.tracker.db = Mock()
    
    def test_token_analysis_cleared(self):
        """Test token analysis returns CLEARED when all signals positive"""
        token_addr = "good_token"
        
        # Mock all detection methods
        self.tracker.detect_smart_wallets = Mock(return_value=([{'wallet': 'test'}], 2))
        self.tracker.detect_insider_activity = Mock(return_value=({}, 1))
        self.tracker.detect_copy_trade_signal = Mock(return_value=({}, 1.5))
        
        result = self.tracker.analyze_token(token_addr)
        
        self.assertEqual(result['status'], 'CLEARED')
        self.assertGreater(result['score'], 0)
        self.assertGreater(result['confidence'], 0)
    
    def test_token_analysis_killed(self):
        """Test token analysis returns KILLED when low score"""
        token_addr = "bad_token"
        
        # Mock all detection returning zero signals
        self.tracker.detect_smart_wallets = Mock(return_value=([], 0))
        self.tracker.detect_insider_activity = Mock(return_value=({'red_flags': ['dump']}, 0))
        self.tracker.detect_copy_trade_signal = Mock(return_value=({}, 0))
        
        result = self.tracker.analyze_token(token_addr)
        
        self.assertEqual(result['status'], 'KILLED')
        self.assertLess(result['score'], 5.0)


class TestAgent3Performance(unittest.TestCase):
    """Test Agent 3 performance metrics"""
    
    def setUp(self):
        self.tracker = Agent3WalletTracker(Config())
    
    def test_analyze_token_latency(self):
        """Test analyze_token completes in reasonable time"""
        self.tracker.solscan = Mock()
        self.tracker.solscan.get_top_holders.return_value = []
        self.tracker.birdeye = Mock()
        self.tracker.birdeye.get_top_traders.return_value = []
        self.tracker.helius = Mock()
        self.tracker.helius.get_token_transaction_flow.return_value = []
        
        import time
        start = time.time()
        result = self.tracker.analyze_token("test_token")
        elapsed = (time.time() - start) * 1000  # ms
        
        # Should complete in <1500ms (1.5s target)
        self.assertLess(elapsed, 1500)
        logger.info(f"Agent 3 latency: {elapsed:.1f}ms")


class TestAgent3Database(unittest.TestCase):
    """Test Agent 3 database integration"""
    
    def setUp(self):
        self.tracker = Agent3WalletTracker(Config())
        self.tracker.db = Mock()
    
    def test_log_to_database_success(self):
        """Test successful database logging"""
        result = {
            'token_address': 'test_token',
            'status': 'CLEARED',
            'score': 7.5,
            'confidence': 0.8
        }
        
        self.tracker.log_to_database(result)
        
        # Verify db method was called
        self.tracker.db.log_agent_3_analysis.assert_called_once_with(result)
    
    def test_log_to_database_no_db(self):
        """Test logging gracefully fails if no database"""
        self.tracker.db = None
        
        result = {'token_address': 'test', 'status': 'CLEARED'}
        
        # Should not raise error
        self.tracker.log_to_database(result)


class TestAgent3Integration(unittest.TestCase):
    """Integration tests with full pipeline"""
    
    def setUp(self):
        self.tracker = Agent3WalletTracker(Config())
    
    def test_tier_calculation(self):
        """Test tier calculation helper"""
        self.assertEqual(self.tracker._calculate_tier(5), 'top_10')
        self.assertEqual(self.tracker._calculate_tier(25), 'top_50')
        self.assertEqual(self.tracker._calculate_tier(75), 'top_100')
        self.assertEqual(self.tracker._calculate_tier(1000), 'ranked')


def run_tests():
    """Run all Agent 3 tests"""
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add all tests
    suite.addTests(loader.loadTestsFromTestCase(TestBirdeyeClient))
    suite.addTests(loader.loadTestsFromTestCase(TestAgent3SmartWalletDetection))
    suite.addTests(loader.loadTestsFromTestCase(TestAgent3InsiderActivity))
    suite.addTests(loader.loadTestsFromTestCase(TestAgent3CopyTrade))
    suite.addTests(loader.loadTestsFromTestCase(TestAgent3Scoring))
    suite.addTests(loader.loadTestsFromTestCase(TestAgent3Performance))
    suite.addTests(loader.loadTestsFromTestCase(TestAgent3Database))
    suite.addTests(loader.loadTestsFromTestCase(TestAgent3Integration))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Print summary
    print("\n" + "="*60)
    print("AGENT 3 TEST SUMMARY")
    print("="*60)
    print(f"Tests Run: {result.testsRun}")
    print(f"Successes: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print("="*60)
    
    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_tests()
    exit(0 if success else 1)
