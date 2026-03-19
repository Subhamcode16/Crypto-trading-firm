#!/usr/bin/env python3
"""
API Health Check & Verification Script
=======================================

Tests all configured APIs to verify they're accessible and working.
Helps diagnose connection issues before running the bot.

Usage:
    python3 src/api_health_check.py
"""

import sys
import json
import logging
from pathlib import Path
from datetime import datetime

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger('api_health_check')

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import Config


class APIHealthChecker:
    """Verify all APIs are properly configured and accessible"""
    
    def __init__(self):
        self.config = Config()
        self.results = {}
        self.passed = 0
        self.failed = 0
    
    def check_all(self):
        """Run all API checks"""
        logger.info("=" * 70)
        logger.info("🔍 API HEALTH CHECK")
        logger.info("=" * 70)
        
        self.check_config_files()
        self.check_dexscreener()
        self.check_solscan()
        self.check_helius()
        self.check_birdeye()
        self.check_anthropic()
        self.check_discord()
        self.check_telegram()
        
        self.print_summary()
    
    def check_config_files(self):
        """Verify config files exist and load"""
        logger.info("\n📁 Checking config files...")
        
        files = {
            'config.json': 'config/config.json',
            '.env': '.env',
            'secrets.env': 'secrets.env'
        }
        
        for name, path in files.items():
            if Path(path).exists():
                logger.info(f"  ✅ {name} — Found")
                self.passed += 1
                self.results[f'config:{name}'] = 'PASS'
            else:
                logger.warning(f"  ❌ {name} — NOT FOUND ({path})")
                self.failed += 1
                self.results[f'config:{name}'] = 'FAIL'
    
    def check_dexscreener(self):
        """Test Dexscreener API connection"""
        logger.info("\n🔗 Checking Dexscreener (Token Discovery)...")
        
        try:
            from src.apis.dexscreener_client import DexscreenerClient
            client = DexscreenerClient()
            
            # Try to fetch trending pairs
            pairs = client.get_solana_pairs(limit=1, strategy='trending')
            
            if pairs and len(pairs) > 0:
                logger.info(f"  ✅ Dexscreener — Connected (got {len(pairs)} pair)")
                self.passed += 1
                self.results['dexscreener'] = 'PASS'
            else:
                logger.warning(f"  ⚠️  Dexscreener — Connected but no pairs returned")
                self.passed += 1
                self.results['dexscreener'] = 'PASS (no data)'
        
        except Exception as e:
            logger.error(f"  ❌ Dexscreener — ERROR: {e}")
            self.failed += 1
            self.results['dexscreener'] = f'FAIL: {str(e)[:50]}'
    
    def check_solscan(self):
        """Test Solscan API connection"""
        logger.info("\n🔗 Checking Solscan (On-Chain Analysis)...")
        
        try:
            api_key = self.config.get_optional_secret('SOLSCAN_API_KEY')
            
            if not api_key:
                logger.warning(f"  ⚠️  Solscan — API key not configured")
                self.failed += 1
                self.results['solscan'] = 'FAIL: No API key'
                return
            
            from src.apis.solscan_client import SolscanClient
            client = SolscanClient()
            
            # Try a test query
            result = client.get_token_info('So11111111111111111111111111111111111111112')  # Wrapped SOL
            
            if result:
                logger.info(f"  ✅ Solscan — Connected (verified with wrapped SOL)")
                self.passed += 1
                self.results['solscan'] = 'PASS'
            else:
                logger.warning(f"  ⚠️  Solscan — Connected but returned no data")
                self.failed += 1
                self.results['solscan'] = 'FAIL: No data'
        
        except Exception as e:
            logger.error(f"  ❌ Solscan — ERROR: {e}")
            self.failed += 1
            self.results['solscan'] = f'FAIL: {str(e)[:50]}'
    
    def check_helius(self):
        """Test Helius RPC connection"""
        logger.info("\n🔗 Checking Helius RPC (Blockchain Data)...")
        
        try:
            rpc_url = self.config.get_optional_secret('HELIUS_RPC_URL')
            
            if not rpc_url:
                logger.warning(f"  ⚠️  Helius — RPC URL not configured")
                self.failed += 1
                self.results['helius'] = 'FAIL: No RPC URL'
                return
            
            from src.apis.helius_rpc import HeliusRPCClient
            client = HeliusRPCClient()
            
            # Try getBalance (simple test)
            result = client.get_account_balance('11111111111111111111111111111111')  # System program
            
            if result is not None:
                logger.info(f"  ✅ Helius — RPC Connected")
                self.passed += 1
                self.results['helius'] = 'PASS'
            else:
                logger.warning(f"  ⚠️  Helius — RPC Connected but returned unexpected data")
                self.passed += 1
                self.results['helius'] = 'PASS (unexpected response)'
        
        except Exception as e:
            logger.error(f"  ❌ Helius — ERROR: {e}")
            self.failed += 1
            self.results['helius'] = f'FAIL: {str(e)[:50]}'
    
    def check_birdeye(self):
        """Test Birdeye API connection"""
        logger.info("\n🔗 Checking Birdeye (Smart Wallet Tracking)...")
        
        try:
            api_key = self.config.get_optional_secret('BIRDEYE_API_KEY')
            
            if not api_key:
                logger.warning(f"  ❌ Birdeye — API key NOT CONFIGURED (Agent 3 will use mock data)")
                logger.warning(f"     ACTION: Add BIRDEYE_API_KEY to .env")
                self.failed += 1
                self.results['birdeye'] = 'FAIL: No API key configured'
                return
            
            from src.apis.birdeye_client import BirdeyeClient
            client = BirdeyeClient()
            
            # Try to get token info
            result = client.get_token_metadata('EPjFWdd5Au17hZ9HXzLXmdDdP7UxfxduRp7j9kXcqSa')  # USDC
            
            if result:
                logger.info(f"  ✅ Birdeye — Connected (verified with USDC)")
                self.passed += 1
                self.results['birdeye'] = 'PASS'
            else:
                logger.warning(f"  ⚠️  Birdeye — Connected but returned no data")
                self.failed += 1
                self.results['birdeye'] = 'FAIL: No data'
        
        except Exception as e:
            logger.error(f"  ❌ Birdeye — ERROR: {e}")
            self.failed += 1
            self.results['birdeye'] = f'FAIL: {str(e)[:50]}'
    
    def check_anthropic(self):
        """Test Anthropic Claude API"""
        logger.info("\n🤖 Checking Anthropic Claude (LLM)...")
        
        try:
            api_key = self.config.get_optional_secret('ANTHROPIC_API_KEY')
            
            if not api_key:
                logger.warning(f"  ❌ Anthropic — API key NOT CONFIGURED")
                self.failed += 1
                self.results['anthropic'] = 'FAIL: No API key'
                return
            
            import anthropic
            client = anthropic.Anthropic(api_key=api_key)
            
            # Try a simple message
            response = client.messages.create(
                model='claude-3-5-haiku-20241022',
                max_tokens=10,
                messages=[
                    {'role': 'user', 'content': 'Hi'}
                ]
            )
            
            if response:
                logger.info(f"  ✅ Anthropic — Connected (Claude Haiku working)")
                self.passed += 1
                self.results['anthropic'] = 'PASS'
            else:
                logger.warning(f"  ⚠️  Anthropic — Connected but unexpected response")
                self.failed += 1
                self.results['anthropic'] = 'FAIL: Invalid response'
        
        except Exception as e:
            logger.error(f"  ❌ Anthropic — ERROR: {e}")
            self.failed += 1
            self.results['anthropic'] = f'FAIL: {str(e)[:50]}'
    
    def check_discord(self):
        """Test Discord Bot Token"""
        logger.info("\n🎮 Checking Discord Bot...")
        
        try:
            import json
            
            with open('config/config.json', 'r') as f:
                config = json.load(f)
            
            token = config.get('discord', {}).get('bot_token')
            
            if not token:
                logger.warning(f"  ❌ Discord — Token NOT CONFIGURED")
                self.failed += 1
                self.results['discord'] = 'FAIL: No token'
                return
            
            # Just verify format (detailed validation would require async discord.py)
            if len(token) > 50 and '.' in token:
                logger.info(f"  ✅ Discord — Token configured (format valid)")
                logger.info(f"     Note: Full validation requires async context")
                self.passed += 1
                self.results['discord'] = 'PASS (format valid)'
            else:
                logger.warning(f"  ❌ Discord — Token format invalid")
                self.failed += 1
                self.results['discord'] = 'FAIL: Invalid token format'
        
        except Exception as e:
            logger.error(f"  ❌ Discord — ERROR: {e}")
            self.failed += 1
            self.results['discord'] = f'FAIL: {str(e)[:50]}'
    
    def check_telegram(self):
        """Test Telegram Bot Configuration"""
        logger.info("\n📱 Checking Telegram Bot...")
        
        try:
            bot_token = self.config.get_optional_secret('TELEGRAM_BOT_TOKEN')
            chat_id = self.config.get_optional_secret('TELEGRAM_CHAT_ID')
            
            if not bot_token:
                logger.warning(f"  ⚠️  Telegram — Bot token not configured (optional)")
                self.passed += 1
                self.results['telegram'] = 'SKIP: Not configured'
                return
            
            if not chat_id:
                logger.warning(f"  ⚠️  Telegram — Chat ID not configured")
                self.failed += 1
                self.results['telegram'] = 'FAIL: No chat ID'
                return
            
            # Verify format
            if len(bot_token) > 30 and chat_id.isdigit():
                logger.info(f"  ✅ Telegram — Credentials configured")
                logger.info(f"     Chat ID: {chat_id}")
                self.passed += 1
                self.results['telegram'] = 'PASS'
            else:
                logger.warning(f"  ❌ Telegram — Credentials format invalid")
                self.failed += 1
                self.results['telegram'] = 'FAIL: Invalid format'
        
        except Exception as e:
            logger.error(f"  ❌ Telegram — ERROR: {e}")
            self.failed += 1
            self.results['telegram'] = f'FAIL: {str(e)[:50]}'
    
    def print_summary(self):
        """Print final summary"""
        total = self.passed + self.failed
        pass_pct = (self.passed / total * 100) if total > 0 else 0
        
        logger.info("\n" + "=" * 70)
        logger.info("📊 HEALTH CHECK SUMMARY")
        logger.info("=" * 70)
        logger.info(f"\nPassed: {self.passed}/{total} ({pass_pct:.0f}%)")
        logger.info(f"Failed: {self.failed}/{total}")
        
        logger.info("\nDetailed Results:")
        for api_name, result in sorted(self.results.items()):
            status = "✅" if "PASS" in result else "❌" if "FAIL" in result else "⚠️"
            logger.info(f"  {status} {api_name.upper()}: {result}")
        
        logger.info("\n" + "=" * 70)
        
        if self.failed > 0:
            logger.warning(f"\n⚠️  {self.failed} API(s) need attention before running the bot")
            logger.warning("   See API_VERIFICATION_REPORT.md for details")
        else:
            logger.info(f"\n✅ All critical APIs configured and accessible!")
        
        logger.info("=" * 70)
        
        return self.failed == 0


if __name__ == '__main__':
    checker = APIHealthChecker()
    success = checker.check_all()
    
    sys.exit(0 if success else 1)
