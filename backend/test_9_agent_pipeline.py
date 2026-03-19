import sys
import os
import logging
import asyncio
from datetime import datetime
from unittest.mock import MagicMock, AsyncMock

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(name)s] %(levelname)s: %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger('backtest')

# Add project root to path
sys.path.insert(0, os.path.dirname(__file__))

# ══════════════════════════════════════════════════════════════════
# MOCKS
# ══════════════════════════════════════════════════════════════════

class MockLLM:
    async def create_message(self, *args, **kwargs):
        return {"text": '{"market_regime": "bullish", "score": 8.0, "reason": "test"}', "metrics": {}}
    async def create_message_async(self, *args, **kwargs):
        return await self.create_message(*args, **kwargs)

class MockDB:
    async def log_agent_analysis(self, *args, **kwargs): pass
    async def log_agent_2_analysis(self, *args, **kwargs): pass
    async def log_agent_3_analysis(self, *args, **kwargs): pass
    async def get_system_state(self, *args, **kwargs): return None
    async def get_all_positions(self, *args, **kwargs): return {"closed": [], "open": []}
    async def log_agent_9_report(self, *args, **kwargs): pass
    async def log_event(self, *args, **kwargs): pass
    async def log_trade(self, *args, **kwargs): pass

class MockTelegram:
    async def send_status_update(self, *args, **kwargs): return True

# Globally patch LLMClient before importing agents
import src.utils.llm_client
src.utils.llm_client.LLMClient = MagicMock(return_value=MockLLM())

async def run_backtest():
    logger.info("=" * 60)
    logger.info("🧪 NINE-AGENT PIPELINE BACKTEST (ASYNC/MOCKED)")
    logger.info("=" * 60)

    passed = []
    failed = []
    
    mock_db = MockDB()
    mock_tg = MockTelegram()

    # ══════════════════════════════════════════════════════════════════
    # TEST 1: Agent 5 — Signal Aggregator
    # ══════════════════════════════════════════════════════════════════
    logger.info("\n[TEST 1] Agent 5 — Signal Aggregator")
    try:
        from src.agents.agent_5_signal_aggregator import Agent5SignalAggregator
        agg = Agent5SignalAggregator()
        agg.db = mock_db

        signals_triple = {
            'agent_1': {'cleared': True, 'score': 6.5, 'analysis_timestamp': datetime.utcnow().isoformat()},
            'agent_2': {'cleared': True, 'score': 7.5, 'analysis_timestamp': datetime.utcnow().isoformat(), 'discovery_source': 'onchain'},
            'agent_3': {'cleared': True, 'score': 8.0, 'analysis_timestamp': datetime.utcnow().isoformat()},
            'agent_4': {'cleared': True, 'score': 6.0, 'analysis_timestamp': datetime.utcnow().isoformat(), 'community': {}},
        }
        result = await agg.aggregate_signal(
            'TestAddr123', 'TEST', signals_triple,
            datetime.utcnow().isoformat(), 'mixed'
        )
        if result:
            logger.info(f"  ✅ Triple-source: score={result['composite_score']:.2f}, status={result['status']}")
            passed.append("Agent 5: Triple-source aggregation")
        else:
            failed.append("Agent 5: Signal dropped unexpectedly")

    except Exception as e:
        logger.error(f"  ❌ Agent 5 test failed: {e}")
        failed.append(f"Agent 5: {e}")

    # ══════════════════════════════════════════════════════════════════
    # TEST 2: Agent 6 — Macro Sentinel
    # ══════════════════════════════════════════════════════════════════
    logger.info("\n[TEST 2] Agent 6 — Macro Sentinel")
    try:
        from src.agents.agent_6_macro_sentinel import Agent6MacroSentinel
        sentinel = Agent6MacroSentinel(db=mock_db)

        mock_signal = {'token_address': 'TestAddr', 'token_symbol': 'MACROTEST', 'composite_score': 8.5}

        # Override cache with mock market data
        sentinel._market_cache = {
            'btc_price': 70000, 'btc_1h_change': 0.5, 'btc_24h_change': 2.1,
            'sol_price': 140,   'sol_1h_change': 1.2, 'sol_24h_change': 4.0,
            'fetched_at': datetime.utcnow().isoformat()
        }
        sentinel._cache_ts = datetime.utcnow()

        result = await sentinel.analyze(mock_signal)
        logger.info(f"  ✅ Analysis: status={result['status']}, regime={result['market_regime']}")
        passed.append("Agent 6: Macro Sentinel analysis")

    except Exception as e:
        logger.error(f"  ❌ Agent 6 test failed: {e}")
        failed.append(f"Agent 6: {e}")

    # ══════════════════════════════════════════════════════════════════
    # TEST 3: Agent 7 — Risk Manager
    # ══════════════════════════════════════════════════════════════════
    logger.info("\n[TEST 3] Agent 7 — Risk Manager")
    try:
        from src.agents.agent_7_risk_manager import Agent7RiskManager
        rm = Agent7RiskManager(starting_capital=10.0, db=mock_db)
        # Mock daily loss to ensure we pass
        rm.daily_loss_usd = 0.0

        mock_5 = {'token_address': 'Addr', 'token_symbol': 'RISK_TEST', 'composite_score': 8.7}
        mock_6 = {'market_regime': 'mixed'}

        approved, instr, reason = await rm.validate_and_size(mock_5, mock_6, entry_price=0.000042)
        if approved:
            logger.info(f"  ✅ Approved: ${instr.position_size_usd:.2f} | SL=${instr.stop_loss_price:.8f}")
            passed.append("Agent 7: Risk validation and sizing")
        else:
            failed.append(f"Agent 7: Validation failed: {reason}")

    except Exception as e:
        logger.error(f"  ❌ Agent 7 test failed: {e}")
        failed.append(f"Agent 7: {e}")

    # ══════════════════════════════════════════════════════════════════
    # TEST 4: Agent 8 — Trading Bot
    # ══════════════════════════════════════════════════════════════════
    logger.info("\n[TEST 4] Agent 8 — Trading Bot")
    try:
        from src.agents.agent_8_trading_bot import TradingBot, TradeInstruction
        bot = TradingBot(db_client=mock_db)
        bot.paper_trading = True

        instruction = TradeInstruction(
            user_id="test",
            token='SOLUSDT',
            action='BUY',
            entry_price=0.000100,
            position_size_usd=1.00,
            sl_price=0.000080,
            tp1_price=0.000200,
            tp1_exit_pct=0.50,
            tp2_price=0.000400,
            trailing_stop_pct=0.03,
            signal_id="test_id",
            timestamp=datetime.utcnow()
        )

        # Real call to execute_trade
        result = await bot.execute_trade(instruction)
        if result and result.get('status') == 'FILLED':
            logger.info(f"  ✅ Trade Executed: {instruction.token} | fill=${result['fill_price']:.4f}")
            passed.append("Agent 8: Trade execution")
        else:
            failed.append(f"Agent 8: Execution failed or returned unexpected status: {result.get('status') if result else 'None'}")

    except Exception as e:
        logger.error(f"  ❌ Agent 8 test failed: {e}")
        failed.append(f"Agent 8: {e}")

    # ══════════════════════════════════════════════════════════════════
    # TEST 5: Agent 9 — Performance Analyst
    # ══════════════════════════════════════════════════════════════════
    logger.info("\n[TEST 5] Agent 9 — Performance Analyst")
    try:
        from src.agents.agent_9_performance_analyst import PerformanceAnalyst
        analyst = PerformanceAnalyst(db_client=mock_db, telegram_client=mock_tg)
        
        logger.info(f"  ✅ Agent 9 initialized with Mock dependencies")
        passed.append("Agent 9: Performance Analyst initialization")

    except Exception as e:
        logger.error(f"  ❌ Agent 9 test failed: {e}")
        failed.append(f"Agent 9: {e}")

    # ══════════════════════════════════════════════════════════════════
    # SUMMARY
    # ══════════════════════════════════════════════════════════════════
    logger.info("\n" + "=" * 60)
    logger.info("BACKTEST RESULTS")
    logger.info("=" * 60)
    logger.info(f"  PASSED: {len(passed)}")
    logger.info(f"  FAILED: {len(failed)}")

    for f in failed:
        logger.error(f"    [ERR] {f}")

    return len(failed) == 0

if __name__ == '__main__':
    asyncio.run(run_backtest())
