"""
Backtesting framework for signal quality validation

To use:
1. Fetch historical tokens from Dexscreener
2. Run them through the signal pipeline
3. Calculate hit rate and performance metrics
"""

import logging
import sys
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from secrets.env
env_path = Path(__file__).parent.parent / 'secrets.env'
if env_path.exists():
    load_dotenv(env_path)

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.apis.dexscreener_client import DexscreenerClient
from src.apis.solscan_client import SolscanClient
from src.apis.helius_rpc import HeliusRPCClient
from src.analysis.rug_detector import RugDetector
from src.analysis.ai_scorer import AIScorer
from src.signals.signal_formatter import SignalFormatter
from src.database import Database

logger = logging.getLogger('backtest')

class SignalBacktester:
    """Backtest signal quality on historical data"""
    
    def __init__(self):
        self.dexscreener = DexscreenerClient()
        self.solscan = SolscanClient()
        self.helius = HeliusRPCClient()
        self.rug_detector = RugDetector(self.solscan, self.helius)
        self.ai_scorer = AIScorer()
        self.db = Database(':memory:')  # In-memory database for testing
        
        # Metrics
        self.total_tokens_analyzed = 0
        self.signals_generated = 0
        self.signals_dropped = 0
        self.high_confidence = 0  # 8-10
        self.mid_confidence = 0   # 6-7
    
    def backtest_recent_tokens(self, limit: int = 100):
        """Backtest on recent Dexscreener tokens"""
        logger.info(f'🚀 Starting backtest on {limit} recent tokens')
        logger.info('='*60)
        
        # Fetch tokens
        logger.info(f'📡 Fetching {limit} tokens from Dexscreener...')
        pairs = self.dexscreener.get_solana_pairs(limit=limit)
        
        if not pairs:
            logger.error('No pairs fetched')
            return
        
        logger.info(f'✅ Fetched {len(pairs)} pairs')
        
        # Process each token
        for i, pair in enumerate(pairs, 1):
            try:
                parsed = self.dexscreener.parse_pair(pair)
                
                if not parsed or not parsed.get('token_address'):
                    continue
                
                token_symbol = parsed.get('token_symbol', 'UNKNOWN')
                logger.info(f'\n[{i}/{len(pairs)}] Analyzing: {token_symbol}')
                
                # Run rug detection
                passed, rug_analysis = self.rug_detector.analyze(parsed)
                
                if not passed:
                    logger.info(f'   🛑 Dropped by rug filter')
                    self.signals_dropped += 1
                    self.total_tokens_analyzed += 1
                    continue
                
                # Score with AI
                ai_score = self.ai_scorer.score_token(parsed, rug_analysis)
                logger.info(f'   💬 AI Score: {ai_score["score"]}/10')
                
                # Check confidence threshold
                if ai_score['score'] < 6:
                    logger.info(f'   Dropped: Low confidence')
                    self.signals_dropped += 1
                    self.total_tokens_analyzed += 1
                    continue
                
                # Format signal
                signal = SignalFormatter.format(parsed, rug_analysis, ai_score)
                
                if signal:
                    logger.info(f'   ✅ SIGNAL GENERATED')
                    self.signals_generated += 1
                    
                    if ai_score['score'] >= 8:
                        self.high_confidence += 1
                    else:
                        self.mid_confidence += 1
                else:
                    self.signals_dropped += 1
                
                self.total_tokens_analyzed += 1
                
            except Exception as e:
                logger.error(f'Error processing token: {e}')
                self.total_tokens_analyzed += 1
        
        # Print summary
        self._print_summary()
    
    def _print_summary(self):
        """Print backtest summary"""
        logger.info('\n' + '='*60)
        logger.info('📊 BACKTEST SUMMARY')
        logger.info('='*60)
        
        logger.info(f'Total tokens analyzed: {self.total_tokens_analyzed}')
        logger.info(f'Signals generated: {self.signals_generated}')
        logger.info(f'Signals dropped: {self.signals_dropped}')
        
        if self.signals_generated > 0:
            logger.info(f'\nSignal confidence breakdown:')
            logger.info(f'  High (8-10): {self.high_confidence}')
            logger.info(f'  Mid (6-7): {self.mid_confidence}')
            
            hit_rate = (self.signals_generated / self.total_tokens_analyzed) * 100
            logger.info(f'\nSignal generation rate: {hit_rate:.1f}%')
        else:
            logger.warning('No signals generated in this backtest')
        
        logger.info('='*60)

def main():
    """Run backtesting"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
    )
    
    backtester = SignalBacktester()
    backtester.backtest_recent_tokens(limit=50)

if __name__ == '__main__':
    main()
