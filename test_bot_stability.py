#!/usr/bin/env python3
import logging
import sys
import os
from dotenv import load_dotenv

# Add backend directory to sys.path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'backend'))

from src.researcher_bot import ResearcherBot

def test_stability():
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger('test')
    
    # Load env
    load_dotenv('backend/secrets.env')
    
    config = {
        'secrets': {
            'HELIUS_API_KEY': os.getenv('HELIUS_API_KEY'),
            'SOLSCAN_API_KEY': os.getenv('SOLSCAN_API_KEY'),
            'BIRDEYE_API_KEY': os.getenv('BIRDEYE_API_KEY'),
            'TWITTER_BEARER_TOKEN': os.getenv('TWITTER_BEARER_TOKEN')
        }
    }
    
    # Mock database
    class MockDB:
        def log_agent_3_analysis(self, *args, **kwargs): pass
        def log_signal(self, *args, **kwargs): pass
        def get_recent_analysis(self, *args, **kwargs): return None
        def log_agent_event(self, *args, **kwargs): pass
    
    # Mock telegram bot
    class MockTelegram:
        def send_message(self, *args, **kwargs): pass
        def send_photo(self, *args, **kwargs): pass
        def send_signal_alert(self, *args, **kwargs): pass
    
    bot = ResearcherBot(MockDB(), telegram_bot=MockTelegram())
    
    print("\n--- Testing ResearcherBot Discovery Stability ---")
    print("This will run the discovery phase. It should NOT crash even if Birdeye fails.")
    
    try:
        # We only run the scan part
        bot.scan()
        print("\n✅ SUCCESS: Scan completed without NoneType crash!")
    except Exception as e:
        print(f"\n❌ FAILED: Scan crashed with error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    test_stability()
