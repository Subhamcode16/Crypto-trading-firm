#!/usr/bin/env python3
"""
Solana Memecoin Autonomous Trading System - Phase 1 Foundation

Main entry point for the trading bot
"""

import sys
from pathlib import Path
import time
import signal
from datetime import datetime
import asyncio
import json

# Add project root to path (so src imports work)
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Add stubs directory FIRST so mock modules are imported before real packages are attempted
stubs_path = project_root / 'stubs'
if stubs_path.exists():
    sys.path.insert(0, str(stubs_path))
    print("[INFO] Using mock modules for testing (stubs directory found)")

from src.config import Config
from src.database import Database
from src.telegram_bot import TelegramBot
from src.scheduler import TaskScheduler
from src.logger import setup_logger
from src.researcher_bot import ResearcherBot
from src.agents.agent_0_commander import Agent0Commander
from src.agents.agent_2_on_chain_analyst import OnChainAnalyst as Agent2OnChainAnalyst
from src.agents.agent_3_wallet_tracker import Agent3WalletTracker
from src.agents.agent_4_intel_agent import Agent4IntelAgent
from src.agents.agent_5_signal_aggregator import Agent5SignalAggregator
from src.agents.agent_6_macro_sentinel import Agent6MacroSentinel
from src.agents.agent_7_risk_manager import Agent7RiskManager
from src.agents.agent_8_trading_bot import TradingBot
from src.agents.agent_9_performance_analyst import PerformanceAnalyst
from src.ml.trainer import MLTrainer
from src.apis.rugcheck_client import RugcheckClient
from src.scoring.safety_score_calculator import SafetyScorer

logger = setup_logger('main')

# Set up loggers for all modules
setup_logger('researcher')
setup_logger('dexscreener')
setup_logger('solscan')
setup_logger('helius')
setup_logger('rug_detector')
setup_logger('ai_scorer')
setup_logger('signal_formatter')
setup_logger('position_sizer')
setup_logger('telegram')
setup_logger('database')
setup_logger('llm_client')
# New agent loggers
setup_logger('src.agents.agent_0_commander')
setup_logger('src.agents.agent_2_on_chain_analyst')
setup_logger('src.agents.agent_3_wallet_tracker')
setup_logger('intel_agent')  # agent_4
setup_logger('src.agents.agent_5_signal_aggregator')
setup_logger('src.agents.agent_6_macro_sentinel')
setup_logger('src.agents.agent_7_risk_manager')
setup_logger('src.agents.agent_8_trading_bot')
setup_logger('src.agents.agent_9_performance_analyst')

class TradingBotApp:
    """Main application class"""
    
    def __init__(self):
        logger.info('='*50)
        logger.info('Initializing Trading Bot...')
        logger.info('='*50)
        
        try:
            # Load configuration
            self.config = Config()
            logger.info('✅ Config loaded')
            
            # Initialize database
            self.db = Database()
            logger.info('✅ Database initialized')
            
            # Get secrets
            telegram_token = self.config.get_secret('TELEGRAM_BOT_TOKEN')
            chat_id = self.config.get_optional_secret('TELEGRAM_CHAT_ID')
            
            if not telegram_token:
                raise ValueError('TELEGRAM_BOT_TOKEN required in secrets.env')
            
            # Initialize Telegram bot
            if chat_id:
                self.telegram = TelegramBot(telegram_token, chat_id, db=self.db)
                logger.info('✅ Telegram bot initialized')
            else:
                self.telegram = TelegramBot(telegram_token, "0", db=self.db)  # Placeholder
                logger.warning('⚠️ Telegram chat ID not set yet - will extract from first message')
            
            # Initialize scheduler
            self.scheduler = TaskScheduler(self.db)
            logger.info('✅ Scheduler initialized')
            
            # Initialize Researcher Bot
            self.researcher_bot = ResearcherBot(self.db, self.telegram)
            logger.info('✅ Researcher Bot initialized')

            # Legacy sync init continues here, but async parts move to start()
            logger.info('✅ Basic app structure initialized')

        except Exception as e:
            logger.error(f'❌ Initialization failed: {e}')
            raise

    async def _initialize_agents(self):
        """Asynchronously initialize agents and division wiring."""
        logger.info('🏛️ Initializing Trading Divisions (Async)...')
        
        # ── Discovery & Intelligence Division ────────────────────────
        self.agent_2_safety    = Agent2OnChainAnalyst(config=self.config.to_dict())
        self.agent_3_tracker   = Agent3WalletTracker(config=self.config.to_dict())
        self.agent_4_intel     = Agent4IntelAgent(config=self.config, db=self.db)
        self.agent_5_aggregator = Agent5SignalAggregator(config=self.config.to_dict())

        # ── Command Division ─────────────────────────────────────────
        starting_capital = float(self.config.get_optional_secret('INITIAL_CAPITAL') or '10.0')
        self.macro_sentinel    = Agent6MacroSentinel()
        self.risk_manager_a7   = Agent7RiskManager(starting_capital=starting_capital)
        self.risk_manager_a7.db = self.db
        
        self.performance_analyst  = PerformanceAnalyst(db_client=self.db, telegram_client=self.telegram)
        self.commander = Agent0Commander(db_client=self.db, telegram_client=self.telegram)
        
        # ── Execution Division ───────────────────────────────────────
        self.trading_bot = TradingBot(db_client=self.db, agent_9=self.performance_analyst)
        await self.trading_bot.start()

        # ── WIRING ──
        # Intel (A4) -> Aggregator (A5) & Tracker (A3)
        # ── WIRING: Shared Clients & Cross-Agent References ──────
        
        # Agent 2: Safety (Injections)
        self.agent_2_safety.solscan = self.researcher_bot.solscan
        self.agent_2_safety.rugcheck = RugcheckClient()
        self.agent_2_safety.helius = self.researcher_bot.helius
        self.agent_2_safety.dexscreener = self.researcher_bot.dexscreener
        self.agent_2_safety.scorer = SafetyScorer()
        self.agent_2_safety.db = self.db
        
        # Agent 3: Wallet Tracker (Injections)
        self.agent_3_tracker.solscan = self.researcher_bot.solscan
        self.agent_3_tracker.birdeye = self.researcher_bot.birdeye
        self.agent_3_tracker.helius = self.researcher_bot.helius
        self.agent_3_tracker.db = self.db
        self.agent_3_tracker.agent_2 = self.agent_2_safety # Priority routing
        
        # Agent 4: Intel (Wiring)
        self.agent_4_intel.agent_3 = self.agent_3_tracker
        self.agent_4_intel.agent_5 = self.agent_5_aggregator
        
        # Agent 5: Aggregator (Injections)
        self.agent_5_aggregator.db = self.db

        # Telegram & Commander
        self.telegram.commander = self.commander
        
        # Inject into Researcher
        self.researcher_bot.agent_2_safety  = self.agent_2_safety
        self.researcher_bot.agent_3_tracker = self.agent_3_tracker
        self.researcher_bot.agent_4_intel   = self.agent_4_intel
        self.researcher_bot.agent_5_aggregator = self.agent_5_aggregator
        self.researcher_bot.macro_sentinel  = self.macro_sentinel
        self.researcher_bot.risk_manager_a7 = self.risk_manager_a7
        self.researcher_bot.trading_bot     = self.trading_bot
        self.researcher_bot.agent_9         = self.performance_analyst
        
        # Inject trading_bot ref into Agent 9 for open positions data
        self.performance_analyst.trading_bot = self.trading_bot
        
        # Wire Risk Manager -> Trading Bot for liquidation
        self.risk_manager_a7.trading_bot = self.trading_bot
        
        # Start real-time discovery (Agent 4)
        asyncio.create_task(self.agent_4_intel.start())
        
        logger.info('='*50)
        logger.info('🏛️ Nine-Agent Trading Firm — ALL DIVISIONS ONLINE')
        logger.info('='*50)
    
    async def researcher_job(self):
        """Called every N minutes - scan for new tokens"""
        logger.info('🔬 Researcher job running...')
        await self.researcher_bot.scan()
    
    async def position_monitor_job(self):
        """Called every N seconds - placeholder for Phase 4"""
        logger.info('📊 Position monitor running...')
        # Phase 4: Will implement position management here
        pass
    
    async def daily_summary_job(self):
        """Called daily - generates summary"""
        logger.info('📈 Daily summary job running...')
        await self.performance_analyst.generate_daily_report()

    async def strategic_review_job(self):
        """Called every 4 hours - Agent 0 strategic oversight"""
        logger.info('Strategic review job running...')
        await self.commander.run_strategic_review()

    async def agent_digest_job(self):
        """Called every 4 hours - comprehensive agent activity digest"""
        logger.info('Agent Digest job running...')
        await self.performance_analyst.generate_agent_digest()
    
    async def telegram_poll_job(self):
        """No longer needed - Application framework handles its own polling."""
        pass
    
    async def midnight_reset_job(self):
        """Called at midnight UTC - reset daily counters"""
        logger.info('🌙 Midnight reset job running...')
        await self.researcher_bot.reset_daily_counters()
    
    async def weekly_ml_retrain_job(self):
        """Called weekly - retrain XGBoost pump prediction model"""
        logger.info('🧠 Weekly ML retraining job running...')
        try:
            trainer = MLTrainer()
            report = trainer.retrain_from_disk()
            logger.info(f"[ML] Retraining report: {report}")
            
            if report.get('status') == 'completed':
                action = report.get('action', 'unknown')
                accuracy = report.get('new_accuracy', 0)
                samples = report.get('training_samples', 0)
                logger.info(f"🧠 [ML] Retraining complete: {action} | accuracy={accuracy:.3f} | samples={samples}")
            else:
                logger.info(f"🧠 [ML] Retraining skipped: {report.get('reason', 'unknown')}")
        except Exception as e:
            logger.error(f'❌ ML retraining failed: {e}')
    
    async def start(self):
        """Start the trading bot"""
        logger.info('='*50)
        logger.info('STARTING TRADING BOT')
        logger.info('='*50)
        
        try:
            # First, perform async initialization of agents
            await self._initialize_agents()

            # Add scheduled jobs
            researcher_interval = self.config.get('scheduler.researcher_interval_minutes', 15)
            position_interval = self.config.get('scheduler.position_monitor_interval_seconds', 60)
            
            self.scheduler.add_researcher_job(self.researcher_job, researcher_interval)
            self.scheduler.add_position_monitor_job(self.position_monitor_job, position_interval)
            self.scheduler.add_daily_summary_job(self.daily_summary_job)
            self.scheduler.add_midnight_reset_job(self.midnight_reset_job)
            
            # Agent 0 Review Cycle (every 4 hours)
            self.scheduler.add_custom_job(
                "Strategic Review", 
                self.strategic_review_job, 
                60 * 4   # minutes → runs every 4h
            )
            
            # Agent Digest (every 4 hours, aligned with Strategic Review)
            self.scheduler.add_custom_job(
                "Agent Digest",
                self.agent_digest_job,
                60 * 4   # minutes → runs every 4h
            )
            
            # ML Retraining (every 7 days)
            self.scheduler.add_custom_job(
                "ML Retrain",
                self.weekly_ml_retrain_job,
                60 * 24 * 7  # minutes → runs every 7 days
            )
            
            # Start Telegram Bot in the background
            asyncio.create_task(self.telegram.run())
            logger.info("✅ Telegram Bot application started")
            
            logger.info(f'📅 Scheduled jobs:')
            for job in self.scheduler.get_jobs():
                logger.info(f'   - {job.name}')
            
            # Start scheduler
            self.scheduler.start()
            
            # Send startup notification
            chat_id = self.config.get_optional_secret('TELEGRAM_CHAT_ID')
            if chat_id and chat_id != "0":
                await self.telegram.send_status_update({
                    'message': '✅ Trading Bot started and monitoring'
                })
            else:
                logger.info('⚠️ Chat ID not set - skipping startup notification')
                logger.info('   To set chat ID: message your bot, then update secrets.env with TELEGRAM_CHAT_ID')
            
            logger.info('='*50)
            logger.info('✅ Bot running. Press Ctrl+C to stop.')
            logger.info('='*50)
            
            # Keep running
            try:
                while True:
                    await asyncio.sleep(1)
            except asyncio.CancelledError:
                logger.info('⌛ Shutdown requested...')
                await self.stop()
        
        except Exception as e:
            logger.error(f'❌ Error during startup: {e}')
            await self.stop()
            raise
    
    async def stop(self):
        """Stop the trading bot gracefully"""
        logger.info('='*50)
        logger.info('STOPPING TRADING BOT')
        logger.info('='*50)
        
        try:
            self.scheduler.stop()
            
            chat_id = self.config.get_optional_secret('TELEGRAM_CHAT_ID')
            if chat_id and chat_id != "0":
                await self.telegram.send_status_update({
                    'message': '❌ Trading Bot stopped'
                })
            
            logger.info('✅ Bot stopped gracefully')
            logger.info('='*50)
        except Exception as e:
            logger.error(f'Error during shutdown: {e}')

async def main():
    """Entry point"""
    import asyncio
    app = None
    try:
        app = TradingBotApp()
        await app.start()
    except KeyboardInterrupt:
        logger.info('Interrupted')
    except Exception as e:
        logger.error(f'Fatal error: {e}')
    finally:
        if app:
            await app.stop()
        sys.exit(0)

if __name__ == '__main__':
    import asyncio
    asyncio.run(main())
