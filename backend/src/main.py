"""
backend/src/main.py
────────────────────
ML Engine Main Orchestrator

Replaces the legacy 9-agent system. This entrypoint orchestrates:
1. Live Data Fetching (Binance, CoinGecko)
2. Feature Engineering (120-dim)
3. Signal Aggregation (LSTM, XGBoost, RL, LLM Agents)
4. Risk Management (ATR Sizing)
5. Order Execution (Paper/Live)
6. Feedback Loop (Continuous Learning)
"""

import sys
import time
import asyncio
import logging
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from ml_engine.data.pipeline import DataPipeline
from ml_engine.aggregator import SignalAggregator
from ml_engine.execution.risk_manager import RiskManager
from ml_engine.execution.order_manager import OrderManager
from ml_engine.feedback.feedback_loop import FeedbackLoop

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("ml_main")

SYMBOLS = ["BTC/USDT", "ETH/USDT", "SOL/USDT"]
TIMEFRAME = "1h"
CHECK_INTERVAL_SEC = 60 * 5  # Check every 5 minutes

class MLEngineBot:
    def __init__(self):
        logger.info("=" * 60)
        logger.info("🚀 INITIALIZING ML TRADING ENGINE (Phase 8)")
        logger.info("=" * 60)
        
        self.pipeline = DataPipeline()
        self.aggregator = SignalAggregator()
        self.risk_manager = RiskManager(initial_capital=1000.0)
        self.order_manager = OrderManager(paper_trade=True, risk_manager=self.risk_manager)
        self.feedback_loop = FeedbackLoop(self.pipeline.storage.engine_or_conn)

    async def run_cycle(self):
        """Single loop cycle over all symbols."""
        logger.info(f"\n[MLEngine] Starting cycle for {len(SYMBOLS)} symbols ({TIMEFRAME})")
        
        for symbol in SYMBOLS:
            try:
                # 1. Update data pipeline (fetches latest OHLCV)
                logger.info(f"[MLEngine] Updating data for {symbol}...")
                await self.pipeline.update(symbols=[symbol], timeframes=[TIMEFRAME])
                df = self.pipeline.get_training_data(symbol, TIMEFRAME)
                
                if df is None or df.empty:
                    logger.warning(f"[MLEngine] No data available for {symbol}, skipping.")
                    continue
                    
                # The aggregator handles feature building internally when given raw data
                # wait, let's check aggregator implementation. It expects features.
                # Actually, our pipeline returns raw data. We need to build features.
                from ml_engine.features.feature_builder import FeatureBuilder
                fb = FeatureBuilder()
                df_feat = fb.build_dataset(df, dropna=True)
                
                if df_feat.empty:
                    logger.warning(f"[MLEngine] Insufficient data after feature building for {symbol}.")
                    continue
                    
                # 2. Get Signal from Aggregator
                logger.info(f"[MLEngine] Getting signal for {symbol}...")
                signal = await self.aggregator.get_signal(symbol, df_feat)
                
                # Enhance signal with latest close price and ATR for risk manager
                latest_bar = df_feat.iloc[-1]
                signal["close_price"] = latest_bar.get("close", 0.0)
                signal["atr"] = latest_bar.get("atr_14", 0.0)
                signal["timestamp"] = latest_bar.get("open_time", "")
                
                # 3. Execute Trade via OrderManager
                logger.info(f"[MLEngine] Processing signal: {signal.get('final_action')} (Strength: {signal.get('signal_strength'):.2f})")
                trade_result = await self.order_manager.execute_signal(signal)
                
                if trade_result:
                    logger.info(f"[MLEngine] 🟢 Trade Executed: {trade_result}")
                    # 4. Record for Feedback Loop
                    self.feedback_loop.log_trade({
                        "symbol": symbol,
                        "action": trade_result["action"],
                        "size": trade_result["size"],
                        "entry_price": trade_result["price"],
                        "signal_strength": signal["signal_strength"],
                        "timestamp": trade_result["timestamp"]
                    })
                    
            except Exception as e:
                logger.error(f"[MLEngine] Error processing {symbol}: {e}", exc_info=True)

        logger.info(f"[MLEngine] Cycle complete. Processed {len(SYMBOLS)} symbols.")

    async def start(self):
        """Main bot loop."""
        logger.info("=" * 60)
        logger.info("🟢 ML ENGINE ONLINE & MONITORING")
        logger.info("=" * 60)
        
        while True:
            start_time = time.time()
            
            try:
                await self.run_cycle()
            except Exception as e:
                logger.error(f"Critical error in main loop: {e}", exc_info=True)
                
            elapsed = time.time() - start_time
            sleep_time = max(0, CHECK_INTERVAL_SEC - elapsed)
            
            logger.info(f"Sleeping for {sleep_time:.0f} seconds until next cycle...")
            await asyncio.sleep(sleep_time)

async def main():
    bot = MLEngineBot()
    await bot.start()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Shutting down ML Engine.")
