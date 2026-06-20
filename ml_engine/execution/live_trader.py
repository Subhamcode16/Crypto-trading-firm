import logging
import asyncio
import os
import json
import time
import requests
import ccxt.async_support as ccxt
from dotenv import load_dotenv
import pandas as pd
import numpy as np
from typing import Dict, List, Optional
from datetime import datetime, timezone, timedelta

from ml_engine.data import bybit_public

from ml_engine.aggregator import SignalAggregator
from ml_engine.features.feature_builder import FeatureBuilder
from ml_engine.data.fetcher import MacroFetcher
from ml_engine.data.sentiment import SentimentEngine
from ml_engine.models.xgb_model import XGBModel
from ml_engine.models.kronos_wrapper import KronosEngine
from ml_engine.data.mongo_store import MongoStore
from ml_engine.data.llm_reasoner import GemmaReasoner

logger = logging.getLogger(__name__)

class LiveTrader:
    """
    Live Execution Agent that connects to Bybit (Demo or Real).
    Replaces PaperTrader. Uses confidence scores for position sizing.
    """
    def __init__(self, api_key: str, api_secret: str, testnet: bool = True, engine_type: str = "kronos"):
        load_dotenv()
        self.testnet = testnet
        self.engine_type = engine_type

        api_key = api_key or os.environ.get("BYBIT_API_KEY")
        api_secret = api_secret or os.environ.get("BYBIT_API_SECRET")

        # ── Private API (Demo/Real): ONLY used for authenticated calls ──────────
        # We inject the markets dict so CCXT never calls load_markets(),
        # which would hammer api-demo.bybit.com and trigger Cloudflare bans.
        exchange_config = {
            'apiKey': api_key,
            'secret': api_secret,
            'enableRateLimit': True,
            'verify': False, # Cloudflare WARP breaks Windows SSL Revocation checks
            'options': {
                'defaultType': 'swap',
                'adjustForTimeDifference': True,
                'recvWindow': 20000,
            },
        }
        
        self.exchange = ccxt.bybit(exchange_config)

        # Inject pre-built market info — prevents load_markets() ever being called
        self.exchange.markets = {
            'BTC/USDT:USDT': {'id': 'BTCUSDT', 'symbol': 'BTC/USDT:USDT', 'base': 'BTC', 'quote': 'USDT', 'settle': 'USDT', 'baseId': 'BTC', 'quoteId': 'USDT', 'settleId': 'USDT', 'type': 'swap', 'spot': False, 'swap': True, 'active': True, 'contract': True, 'linear': True, 'inverse': False, 'contractSize': 1.0, 'precision': {'amount': 0.001, 'price': 0.1}},
            'ETH/USDT:USDT': {'id': 'ETHUSDT', 'symbol': 'ETH/USDT:USDT', 'base': 'ETH', 'quote': 'USDT', 'settle': 'USDT', 'baseId': 'ETH', 'quoteId': 'USDT', 'settleId': 'USDT', 'type': 'swap', 'spot': False, 'swap': True, 'active': True, 'contract': True, 'linear': True, 'inverse': False, 'contractSize': 0.01, 'precision': {'amount': 0.01, 'price': 0.01}},
            'SOL/USDT:USDT': {'id': 'SOLUSDT', 'symbol': 'SOL/USDT:USDT', 'base': 'SOL', 'quote': 'USDT', 'settle': 'USDT', 'baseId': 'SOL', 'quoteId': 'USDT', 'settleId': 'USDT', 'type': 'swap', 'spot': False, 'swap': True, 'active': True, 'contract': True, 'linear': True, 'inverse': False, 'contractSize': 1.0, 'precision': {'amount': 0.1, 'price': 0.01}},
        }
        if self.testnet:
            self.exchange.enable_demo_trading(True)
            logger.info("[LiveTrader] 🔌 Private API → BYBIT DEMO TRADING (Ensure your keys are for Bybit, not Binance!)")
        else:
            logger.warning("[LiveTrader] ⚠️ Private API → REAL BYBIT. REAL FUNDS AT RISK. (Ensure your keys are for Bybit!)")

        # ── Public API: market data goes through bybit_public (NO auth, NO bans) ─
        logger.info("[LiveTrader] 📡 Public API → api.bybit.com (unauthenticated mainnet)")

        # ── Connection health tracking ─────────────────────────────────────────
        # We track consecutive private-API failures. After MAX_API_FAILURES in a
        # row we enter "API circuit breaker" mode and skip private calls until
        # the cooldown expires. This prevents ban spirals.
        self._api_failures = 0
        self._api_backoff_until = 0.0
        self.MAX_API_FAILURES = 5
        self.API_BACKOFF_BASE = 30  # seconds — doubles each failure batch

        self.mongo_db = MongoStore()

        self.symbols = ["BTC/USDT", "ETH/USDT", "SOL/USDT"]

        self.trade_history = self.mongo_db.get_all_trades()
        self.explainability_data = {sym: {} for sym in self.symbols}

        # Elite Trader Psychology tracking
        self.circuit_breaker_active = False
        self._reconciled_on_startup = False

        # Response caches (private API)
        self._balance_cache = None
        self._positions_cache = None
        self._last_balance_time = 0.0
        self._last_positions_time = 0.0
        self._BALANCE_TTL = 15   # seconds
        self._POSITIONS_TTL = 15 # seconds

        # Load models
        logger.info(f"[LiveTrader] Initializing {self.engine_type.upper()} Models...")
        self.aggregator = SignalAggregator()
        self.feature_builder = FeatureBuilder()
        self.macro_fetcher = MacroFetcher()
        self.sentiment_engine = SentimentEngine()

        self.models = {}
        if self.engine_type == "kronos":
            self.kronos_engine = KronosEngine()
        else:
            self.kronos_engine = None
            for sym in self.symbols:
                try:
                    self.models[sym] = XGBModel.load(XGBModel.get_save_path(sym, "1h"))
                except Exception as e:
                    logger.warning(f"[LiveTrader] Could not load XGBoost model for {sym}: {e}")
                    self.models[sym] = None

        self.macro_fetcher = MacroFetcher()
        self.sentiment_engine = SentimentEngine()
        self.llm_reasoner = GemmaReasoner()

        self._last_hold_llm_times = {}
        self.scanner_logs = []

        self.status = "IDLE"
        self.is_running = True

    # ──────────────────────────────────────────────────────────────────────────
    # Telegram Alerts
    # ──────────────────────────────────────────────────────────────────────────
    def _send_telegram(self, message: str):
        # Always log to local file as requested
        try:
            with open("live_alerts.log", "a", encoding="utf-8") as f:
                f.write(message + "\n")
        except Exception as e:
            logger.error(f"[LiveTrader] Failed to write to live_alerts.log: {e}")

        bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
        chat_id = os.environ.get("TELEGRAM_CHAT_ID")
        if not bot_token or not chat_id or bot_token == "YOUR_BOT_TOKEN":
            return
        
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        payload = {"chat_id": chat_id, "text": message}
        try:
            requests.post(url, json=payload, timeout=5)
        except Exception as e:
            logger.error(f"[LiveTrader] Telegram failed: {e}")

    async def _async_send_telegram(self, message: str):
        await asyncio.to_thread(self._send_telegram, message)

    # ──────────────────────────────────────────────────────────────────────────
    # Internal helpers: API resilience
    # ──────────────────────────────────────────────────────────────────────────

    def _is_api_healthy(self) -> bool:
        """Returns True if we should attempt a private API call right now."""
        if time.time() < self._api_backoff_until:
            remaining = int(self._api_backoff_until - time.time())
            logger.warning(f"[LiveTrader] ⏳ API circuit breaker active. Resuming in {remaining}s.")
            return False
        return True

    def _record_api_success(self):
        """Reset failure counter on a successful private API call."""
        if self._api_failures > 0:
            logger.info("[LiveTrader] ✅ Private API back online. Resetting failure counter.")
        self._api_failures = 0
        self._api_backoff_until = 0.0

    def _record_api_failure(self, err: Exception):
        """Track failure and set exponential backoff if threshold is hit."""
        self._api_failures += 1
        logger.warning(f"[LiveTrader] ⚠️ Private API failure #{self._api_failures}: {err}")
        if self._api_failures >= self.MAX_API_FAILURES:
            backoff = self.API_BACKOFF_BASE * (2 ** (self._api_failures - self.MAX_API_FAILURES))
            backoff = min(backoff, 1800)  # cap at 30 minutes
            self._api_backoff_until = time.time() + backoff
            logger.error(f"[LiveTrader] 🛑 {self.MAX_API_FAILURES} consecutive failures! Backing off {backoff:.0f}s to avoid IP ban.")

    async def _ensure_time_sync(self):
        if not getattr(self, '_time_synced', False):
            try:
                await self.exchange.load_time_difference()
                self._time_synced = True
                logger.info(f"[LiveTrader] Synced time with Bybit. Difference: {self.exchange.options.get('timeDifference')} ms")
            except Exception as e:
                logger.warning(f"[LiveTrader] Failed to sync time: {e}")

    async def get_balance(self) -> dict:
        """Fetch account balance with cache + exponential backoff circuit breaker."""
        now = time.time()
        if self._balance_cache and now - self._last_balance_time < self._BALANCE_TTL:
            return self._balance_cache

        if not self._is_api_healthy():
            return self._balance_cache or {'free': 0.0, 'used': 0.0, 'total': 0.0, 'USDT': {'free': 0.0, 'used': 0.0, 'total': 0.0}}

        try:
            await self._ensure_time_sync()
            bal = await self.exchange.fetch_balance()
            self._balance_cache = bal
            self._last_balance_time = time.time()
            self._record_api_success()
            return bal
        except ccxt.AuthenticationError as e:
            logger.error("[LiveTrader] ❌ API Key is invalid. Please update your keys in the Dashboard.")
            return self._balance_cache or {'free': 0.0, 'used': 0.0, 'total': 0.0}
        except Exception as e:
            self._record_api_failure(e)
            return self._balance_cache or {'free': 0.0, 'used': 0.0, 'total': 0.0}

    async def get_positions(self) -> list:
        """Fetch open positions with cache + exponential backoff circuit breaker."""
        now = time.time()
        if self._positions_cache is not None and now - self._last_positions_time < self._POSITIONS_TTL:
            return self._positions_cache

        if not self._is_api_healthy():
            return self._positions_cache or []

        try:
            await self._ensure_time_sync()
            # IMPORTANT: Bybit CCXT v5 does NOT accept a list of symbols in fetch_positions.
            # We call with no args to get ALL positions, then filter to our symbols.
            all_positions = await self.exchange.fetch_positions()
            our_symbols = set(s + ':USDT' for s in self.symbols)  # e.g. 'BTC/USDT:USDT'

            active_pos = []
            for p in all_positions:
                pos_symbol = p.get('symbol', '')
                if pos_symbol not in our_symbols:
                    continue
                contracts = float(p.get('contracts', 0) or 0)
                if contracts <= 0:
                    continue

                side = p['side']
                unrealized_pnl = float(p.get('unrealizedPnl', 0) or 0)
                initial_margin = float(p.get('initialMargin', 0) or 0)
                entry_price = float(p.get('entryPrice', 0) or 0)
                current_price = float(p.get('markPrice', 0) or 0)

                pnl_pct = 0.0
                if initial_margin > 0:
                    pnl_pct = unrealized_pnl / initial_margin
                elif entry_price > 0:
                    if side == 'long':
                        pnl_pct = (current_price - entry_price) / entry_price
                    else:
                        pnl_pct = (entry_price - current_price) / entry_price

                active_pos.append({
                    "symbol": pos_symbol.replace(':USDT', ''),
                    "side": side,
                    "amount": contracts,
                    "entry_price": entry_price,
                    "current_price": current_price,
                    "unrealized_pnl": unrealized_pnl,
                    "pnl_pct": pnl_pct,
                    "value_usdt": contracts * current_price,
                })

            self._positions_cache = active_pos
            self._last_positions_time = time.time()
            self._record_api_success()
            return active_pos
        except ccxt.AuthenticationError:
            logger.error("[LiveTrader] ❌ API Key invalid (positions). Check Dashboard.")
            return self._positions_cache or []
        except Exception as e:
            self._record_api_failure(e)
            return self._positions_cache or []

    async def fetch_live_data(self, symbol: str, limit: int = 360, timeframe: str = "1h") -> Optional[pd.DataFrame]:
        """
        Fetch OHLCV candles via the PUBLIC Bybit mainnet API.
        This is completely separated from the Demo private API — no auth,
        no IP ban risk, no rate-limit issues.
        """
        df = await bybit_public.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
        if df is not None and not df.empty:
            return df
        logger.warning(f"[LiveTrader] Public OHLCV {timeframe} unavailable for {symbol}. Skipping cycle.")
        return None

    async def reconcile_on_startup(self):
        """Reconciles DB open positions against active Exchange positions."""
        db_open = self.mongo_db.get_open_positions()
        exchange_positions = await self.get_positions()
        exchange_symbols = {p['symbol']: p for p in exchange_positions if p.get('amount', 0) > 0}
        
        db_symbols = {p['symbol']: p for p in db_open}
        
        for sym, ex_pos in exchange_symbols.items():
            if sym not in db_symbols:
                logger.warning(f"[LiveTrader] ⚠️ ORPHANED POSITION DETECTED: {sym} found on exchange but not in MongoDB.")
                await self.adopt_orphaned_position(sym, ex_pos)
                
        for db_pos in db_open:
            if db_pos['symbol'] not in exchange_symbols:
                logger.error(f"[LiveTrader] 🚨 MISMATCH: {db_pos['symbol']} is OPEN in DB but missing on exchange!")
                self.mongo_db.close_position(db_pos['symbol'])
                self._reconciliation_mismatch = True

    async def calculate_current_atr(self, symbol: str) -> float:
        """Fetches recent data to calculate a 14-period ATR for stop calculations."""
        try:
            df = await self.fetch_live_data(symbol, limit=20, timeframe="1h")
            if df is not None and not df.empty:
                high_low = df['high'] - df['low']
                high_close = (df['high'] - df['close'].shift()).abs()
                low_close = (df['low'] - df['close'].shift()).abs()
                ranges = pd.concat([high_low, high_close, low_close], axis=1)
                true_range = np.max(ranges, axis=1)
                atr = true_range.rolling(14).mean().iloc[-1]
                return float(atr)
        except Exception as e:
            logger.error(f"[LiveTrader] Error calculating ATR for {symbol}: {e}")
        
        # Fallback
        ticker = await bybit_public.fetch_ticker(symbol)
        if ticker:
            return ticker['last'] * 0.015
        return 0.0

    async def adopt_orphaned_position(self, symbol: str, exchange_position: dict):
        """Creates a DB record for an untracked exchange position."""
        current_atr = await self.calculate_current_atr(symbol)
        entry_price = float(exchange_position.get('entry_price', exchange_position.get('current_price', 0.0)))
        side = exchange_position.get('side', 'long')
        amount = float(exchange_position.get('amount', 0.0))
        
        position_doc = {
            "symbol": symbol,
            "side": side,
            "entry_price": entry_price,
            "initial_amount": amount,
            "amount_remaining": amount,
            "highest_price": entry_price,
            "lowest_price": entry_price,
            "1r_taken": False,
            "2r_taken": False,
            "status": "OPEN",
            "entry_time": str(datetime.now(timezone.utc)),
            "adopted": True,
            "adopted_atr": current_atr
        }
        self.mongo_db.insert_position(position_doc)
        logger.info(f"[LiveTrader] ✅ ADOPTED position {symbol} ({side}) into DB with ATR {current_atr:.4f}")

    async def monitor_open_positions(self):
        """High-frequency risk monitor using MongoDB state."""
        if not self.is_running: return
        
        if not getattr(self, '_reconciled_on_startup', False):
            await self.reconcile_on_startup()
            self._reconciled_on_startup = True
            
        open_positions = self.mongo_db.get_open_positions()
        if not open_positions: return
        
        exchange_positions = await self.get_positions()
        exchange_symbols = {p['symbol']: p for p in exchange_positions if p.get('amount', 0) > 0}
        
        for db_pos in open_positions:
            symbol = db_pos['symbol']
            
            if symbol not in exchange_symbols:
                logger.warning(f"[LiveTrader] DB shows {symbol} OPEN, but not found on exchange. Marking CLOSED.")
                self.mongo_db.close_position(symbol)
                continue
                
            ex_pos = exchange_symbols[symbol]
            current_price = ex_pos['current_price']
            avg_entry = db_pos['entry_price']
            side = db_pos['side']
            
            pnl_pct = (current_price - avg_entry) / avg_entry
            if side == "short":
                pnl_pct = -pnl_pct
                
            # Update extremes
            new_high = max(db_pos.get("highest_price", avg_entry), current_price)
            new_low = min(db_pos.get("lowest_price", avg_entry), current_price)
            
            # Save updates if changed
            updates = {}
            if new_high > db_pos.get("highest_price", 0):
                updates["highest_price"] = new_high
            if new_low < db_pos.get("lowest_price", float('inf')):
                updates["lowest_price"] = new_low
                
            # Execute logic
            r1_pct = 0.015
            r2_pct = 0.030
            trail_pct = 0.015
            
            action_taken = False
            close_all = False
            amount_pct_to_sell = 0.0
            
            # 1R Target (40% off)
            if pnl_pct >= r1_pct and not db_pos.get("1r_taken", False):
                logger.info(f"[LiveTrader] 🎯 1R HIT: Taking 40% profit for {symbol} at {pnl_pct*100:.2f}%.")
                updates["1r_taken"] = True
                amount_pct_to_sell = 0.40
                action_taken = True
                
            # 2R Target (50% of remaining 60%)
            elif pnl_pct >= r2_pct and not db_pos.get("2r_taken", False) and db_pos.get("1r_taken", False):
                logger.info(f"[LiveTrader] 🎯 2R HIT: Taking 30% profit for {symbol} at {pnl_pct*100:.2f}%.")
                updates["2r_taken"] = True
                amount_pct_to_sell = 0.50
                action_taken = True
                
            # Stop Losses
            elif not db_pos.get("1r_taken", False) and pnl_pct <= -r1_pct:
                logger.info(f"[LiveTrader] 🛑 HARD STOP HIT: Cutting loss for {symbol} at {pnl_pct*100:.2f}%.")
                amount_pct_to_sell = 1.0
                action_taken = True
                close_all = True
            elif db_pos.get("1r_taken", False) and pnl_pct <= 0:
                logger.info(f"[LiveTrader] 🛡️ BREAKEVEN STOP HIT: Stopping out remaining {symbol}.")
                amount_pct_to_sell = 1.0
                action_taken = True
                close_all = True
            elif db_pos.get("2r_taken", False):
                extreme_price = db_pos.get("lowest_price", avg_entry) if side == "short" else db_pos.get("highest_price", avg_entry)
                drawdown_from_peak = (current_price - extreme_price) / extreme_price
                if side == "short":
                    drawdown_from_peak = -drawdown_from_peak
                    
                if drawdown_from_peak <= -trail_pct:
                    logger.info(f"[LiveTrader] 🏃 TRAILING STOP HIT: Exiting runner for {symbol} at {drawdown_from_peak*100:.2f}% drop from peak.")
                    amount_pct_to_sell = 1.0
                    action_taken = True
                    close_all = True

            if updates:
                self.mongo_db.update_position(symbol, updates)

            if action_taken:
                # Opposite action to close
                action_dir = "BUY" if side == "short" else "SELL"
                await self._execute_action(symbol, action_dir, current_price, str(datetime.now(timezone.utc)), 1.0, amount_pct=amount_pct_to_sell)
                if close_all:
                    self.mongo_db.close_position(symbol)


    def check_circuit_breaker(self):
        """Halt entries if daily loss exceeds 5% of starting balance."""
        try:
            starting_balance = 100000.0
            state = self.mongo_db.load_gamification_state()
            if 'state' in state:
                state_data = state['state']
                if isinstance(state_data, str):
                    import json
                    state_data = json.loads(state_data)
                starting_balance = state_data.get('starting_balance', 100000.0)

            yesterday = datetime.now(timezone.utc) - timedelta(days=1)
            recent_trades = []
            for t in self.trade_history:
                if t.get('type') != 'SELL':
                    continue
                try:
                    trade_time = t.get('time', '')
                    # Handle both timezone-aware and naive ISO strings
                    if trade_time.endswith('Z'):
                        trade_time = trade_time[:-1] + '+00:00'
                    dt = datetime.fromisoformat(trade_time)
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    if dt >= yesterday:
                        recent_trades.append(t)
                except (ValueError, AttributeError):
                    pass

            daily_pnl = sum(t.get('pnl', 0.0) for t in recent_trades)
            max_allowed_loss = starting_balance * -0.05

            if daily_pnl <= max_allowed_loss:
                if not self.circuit_breaker_active:
                    logger.error(f"[LiveTrader] 🛑 CIRCUIT BREAKER TRIPPED! Daily PnL (${daily_pnl:.2f}) exceeded 5% limit (${max_allowed_loss:.2f}). Halting BUYs.")
                self.circuit_breaker_active = True
            else:
                self.circuit_breaker_active = False

        except Exception as e:
            logger.error(f"[LiveTrader] Error checking circuit breaker: {e}")

    async def evaluate_market(self):
        if not self.is_running: return
        self.status = "ANALYZING"
        
        self.check_circuit_breaker()

        
        logger.info("[LiveTrader] Fetching macro and sentiment context...")
        macro_df = await asyncio.to_thread(
            self.macro_fetcher.fetch_macro_data,
            start=(datetime.now(timezone.utc) - pd.Timedelta(days=15)).strftime("%Y-%m-%d")
        )
        live_sentiment = self.sentiment_engine.get_sentiment()
        
        for symbol in self.symbols:
            logger.info(f"[LiveTrader] Analyzing {symbol}...")
            df = await self.fetch_live_data(symbol, timeframe="1h")
            df_4h = await self.fetch_live_data(symbol, timeframe="4h", limit=120)
            if df is None or len(df) < 30 or df_4h is None or len(df_4h) < 20: continue
            # Step 3: Extract Features (dropna=False so we don't lose the only bars we have)
            df_feat = self.feature_builder.build_dataset(df, macro_df=macro_df, dropna=False)
            
            # Backfill indicators (like EMA200) that need warmup, then fill any remaining with 0
            df_feat = df_feat.bfill().fillna(0)
            
            if df_feat.empty:
                logger.error(f"[LiveTrader] Feature building failed for {symbol} - resulting dataframe is empty.")
                continue
                
            latest_row = df_feat.iloc[-1]
            current_price = latest_row["close"]
            timestamp = str(latest_row["timestamp"])
            
            try:
                # Get raw model prediction
                prediction = self._real_predict(symbol, df, latest_row, live_sentiment.get("score", 0.0))
                raw_action = prediction["action"]
                raw_confidence = prediction["confidence"]
                
                # Format for aggregator
                xgb_result = None
                lstm_result = None
                if self.engine_type == "kronos":
                    # Map kronos output to xgb structure for aggregator compatibility
                    xgb_result = {"signal": "STRONG_LONG" if raw_action == "BUY" else "STRONG_SHORT" if raw_action == "SELL" else "NO_SIGNAL", "confidence": raw_confidence}
                else:
                    xgb_result = {"signal": "STRONG_LONG" if raw_action == "BUY" else "STRONG_SHORT" if raw_action == "SELL" else "NO_SIGNAL", "confidence": raw_confidence}
                
                portfolio_state = {
                    "equity": self.get_status_sync().get("balance", {}).get("total", 100000.0) if hasattr(self, "get_status_sync") else 100000.0, # Approximate
                    "operator_kill_command": False,
                    "exchange_balance_mismatch": getattr(self, '_reconciliation_mismatch', False)
                }
                
                agg_result = await self.aggregator.aggregate(
                    symbol=symbol,
                    features=latest_row.to_dict(),
                    xgb_result=xgb_result,
                    macro_context=macro_df.iloc[-1].to_dict() if not macro_df.empty else {},
                    bar_time=timestamp,
                    df_1h=df,
                    df_4h=df_4h,
                    portfolio_state=portfolio_state
                )
                
                action = agg_result["final_action"]
                confidence = agg_result["confidence"]
                regime = agg_result.get("regime", "ranging")
                
                log_entry = {
                    "timestamp": datetime.now(timezone.utc).strftime("%H:%M:%S"),
                    "symbol": symbol,
                    "raw_action": raw_action,
                    "raw_confidence": raw_confidence,
                    "final_action": action,
                    "regime": regime,
                    "message": f"Raw Math Engine: {raw_action} ({(raw_confidence*100):.1f}%). Aggregator Output: {action}."
                }
                if action == "HOLD" and raw_action != "HOLD":
                    log_entry["message"] += " -> System Blocked/Filtered by Risk Manager."
                
                self.scanner_logs.append(log_entry)
                if len(self.scanner_logs) > 50:
                    self.scanner_logs.pop(0)
                
                model = self.models.get(symbol)
                top_features = model.get_feature_importance(top_n=5) if hasattr(model, "get_feature_importance") else {}
                
                self.explainability_data[symbol] = {
                    "chart_data": df[["timestamp", "open", "high", "low", "close", "volume"]].tail(300).to_dict(orient="records"),
                    "macro_context": macro_df.iloc[-1].to_dict() if not macro_df.empty else {},
                    "top_features": top_features,
                    "latest_sentiment": live_sentiment,
                    "prediction": {
                        "action": action,
                        "confidence": confidence,
                        "raw_probs": prediction.get("raw_probs", {})
                    },
                    "llm_rationale": "Generating rationale...",
                    "llm_decision": "PENDING"
                }
                
                # Fetch LLM Rationale and Gatekeeper Decision ONLY if a trade is proposed
                try:
                    if action == "HOLD":
                        last_gen_time = self._last_hold_llm_times.get(symbol, 0)
                        now = time.time()
                        if now - last_gen_time > 3 * 3600:
                            llm_response = await asyncio.to_thread(
                                self.llm_reasoner.evaluate_trade_proposal,
                                symbol, action, confidence, current_price, top_features,
                                self.explainability_data[symbol]["macro_context"],
                                live_sentiment.get("headlines", [])
                            )
                            self.explainability_data[symbol]["llm_rationale"] = f"[Periodic Hold Review] {llm_response['rationale']}"
                            self.explainability_data[symbol]["llm_decision"] = llm_response["decision"]
                            self._last_hold_llm_times[symbol] = now
                        else:
                            current_rationale = self.explainability_data[symbol].get("llm_rationale", "")
                            if not current_rationale or current_rationale == "Generating rationale...":
                                self.explainability_data[symbol]["llm_rationale"] = "Math Engine recommends HOLD; no risk management override required."
                            self.explainability_data[symbol]["llm_decision"] = "N/A"
                    else:
                        llm_response = await asyncio.to_thread(
                            self.llm_reasoner.evaluate_trade_proposal,
                            symbol, action, confidence, current_price, top_features,
                            self.explainability_data[symbol]["macro_context"],
                            live_sentiment.get("headlines", [])
                        )
                        self.explainability_data[symbol]["llm_rationale"] = llm_response["rationale"]
                        self.explainability_data[symbol]["llm_decision"] = llm_response["decision"]
                        
                        # Log AI Decision to DB ONLY for actual proposed trades
                        self.mongo_db.append_ai_log({
                            "symbol": symbol,
                            "action_proposed": action,
                            "llm_decision": llm_response["decision"],
                            "rationale": llm_response["rationale"],
                            "time": timestamp
                        })
                    
                except Exception as e:
                    logger.error(f"[LiveTrader] LLM Generation error for {symbol}: {e}")
                    self.explainability_data[symbol]["llm_rationale"] = "LLM synthesis failed."
                    self.explainability_data[symbol]["llm_decision"] = "ERROR"
                
                logger.info(f"[{symbol}] Math Signal: {action} (Conf: {confidence:.2f}) | Price: ${current_price:.2f} | Gemma Verdict: {self.explainability_data[symbol]['llm_decision']}")
                
                if action != "HOLD" and self.explainability_data[symbol]["llm_decision"] == "APPROVE":
                    time_str = datetime.now(timezone.utc).strftime("%H:%M UTC")
                    msg = (
                        f"[{time_str}] {symbol} Regime: {regime.upper()}\n"
                        f"[{time_str}] Breakout: {action} | Conf: {confidence:.2f}\n"
                        f"[{time_str}] LLM: {self.explainability_data[symbol]['llm_decision']}\n"
                        f"[{time_str}] Kill Switch: {'ACTIVE' if self.circuit_breaker_active else 'GREEN'}\n"
                        f"[{time_str}] ORDER: {action} {symbol} @ ${current_price:.2f} [TESTNET]"
                    )
                    await self._async_send_telegram(msg)
                    await self._execute_action(symbol, action, current_price, timestamp, confidence)
                elif action != "HOLD" and self.explainability_data[symbol]["llm_decision"] == "VETO":
                    time_str = datetime.now(timezone.utc).strftime("%H:%M UTC")
                    msg = f"[{time_str}] [{symbol}] Trade VETOED by Gemma Risk Manager."
                    await self._async_send_telegram(msg)
                    logger.warning(f"[{symbol}] Trade VETOED by Gemma Risk Manager.")
                
            except Exception as e:
                logger.error(f"[LiveTrader] Prediction failed for {symbol}: {e}")
                
        self.status = "IDLE"

    def _real_predict(self, symbol: str, df: pd.DataFrame, latest_row: pd.Series, live_sentiment: float = 0.0) -> Dict:
        if self.engine_type == "kronos" and self.kronos_engine is not None:
            pred_df = self.kronos_engine.predict(df, pred_len=16)
            if pred_df.empty:
                return {"action": "HOLD", "confidence": 0.0, "raw_probs": {}}
                
            current_price = df.iloc[-1]['close']
            final_future_close = pred_df['close'].iloc[-1]
            
            # Simple Swing Trade check on predicted future
            expected_return = (final_future_close - current_price) / current_price
            
            if expected_return >= 0.0075:
                action = "BUY"
                confidence = min(1.0, expected_return / 0.05)
            elif expected_return <= -0.005:
                action = "SELL"
                confidence = min(1.0, abs(expected_return) / 0.05)
            else:
                action = "HOLD"
                confidence = 0.0
                
            return {"action": action, "confidence": confidence, "raw_probs": {"expected_return": expected_return}}
            
        model = self.models.get(symbol)
        if model is None: return {"action": "HOLD", "confidence": 0.0}
            
        pred = model.predict(latest_row.to_dict())
        raw_probs = pred.get("raw_probs", {})
        long_prob = raw_probs.get("STRONG_LONG", 0)
        short_prob = raw_probs.get("STRONG_SHORT", 0)
        
        action = "HOLD"
        confidence = max(long_prob, short_prob)
        
        if long_prob > 0.35 and long_prob > short_prob:
            if not self.circuit_breaker_active:
                action = "HOLD" if live_sentiment < -0.3 else "BUY"
            else:
                action = "HOLD"
                logger.warning(f"[LiveTrader] Skipped BUY for {symbol} due to Circuit Breaker.")
        elif short_prob > 0.35 and short_prob > long_prob:
            action = "HOLD" if live_sentiment > 0.3 else "SELL"
            
        return {"action": action, "confidence": confidence, "raw_probs": raw_probs}

    async def _execute_action(self, symbol: str, action: str, price: float, timestamp: str, confidence: float, amount_pct: float = 1.0):
        balance = await self.get_balance()
        usdt_info = balance.get('USDT') or {}
        free_usdt = float(usdt_info.get('free') or 0.0)
        
        if free_usdt == 0.0 and isinstance(balance.get('free'), dict):
            free_usdt = float(balance.get('free').get('USDT', 0.0))
        
        positions = await self.get_positions()
        pos = next((p for p in positions if p['symbol'] == symbol), None)
        
        risk_pct = 0.10
        trade_amount_usdt = free_usdt * risk_pct
        
        if trade_amount_usdt < 10 and not pos:
            logger.warning(f"[LiveTrader] Insufficient free USDT (${free_usdt:.2f}) to open position for {symbol}")
            return
            
        try:
            await self._ensure_time_sync()
            # Use public API for current price — no auth, no ban risk
            ticker = await bybit_public.fetch_ticker(symbol)
            if not ticker:
                logger.warning(f"[LiveTrader] Could not get ticker for {symbol}. Skipping execution.")
                return
            current_price = ticker['last']
            amount_to_trade = trade_amount_usdt / current_price
            
            ccxt_symbol = f"{symbol}:USDT"
            if action == "BUY":
                if pos and pos['side'] == 'short':
                    amount_to_cover = pos['amount'] * amount_pct
                    logger.info(f"[LiveTrader] 🟢 EXECUTING BUY TO CLOSE SHORT {symbol} | Amount: {amount_to_cover}")
                    order = await self.exchange.create_market_buy_order(ccxt_symbol, amount_to_cover, params={"reduceOnly": True})
                    
                    pnl = pos['unrealized_pnl'] * amount_pct
                    pnl_pct = pos['pnl_pct']
                    trade_record = {"type": "BUY", "symbol": symbol, "amount": amount_to_cover, "price": order.get('average', current_price), "time": timestamp, "confidence": confidence, "pnl": pnl, "pnl_pct": pnl_pct}
                    self.trade_history.append(trade_record)
                    self.mongo_db.append_trade(trade_record)
                    
                elif pos and pos['side'] == 'long':
                    pass # Already long
                else:
                    logger.info(f"[LiveTrader] 🟢 EXECUTING BUY TO OPEN LONG {symbol} | Size: ${trade_amount_usdt:.2f}")
                    order = await self.exchange.create_market_buy_order(ccxt_symbol, amount_to_trade)
                    trade_record = {"type": "BUY", "symbol": symbol, "amount": amount_to_trade, "price": order.get('average', current_price), "time": timestamp, "confidence": confidence, "pnl": 0.0, "pnl_pct": 0.0}
                    self.trade_history.append(trade_record)
                    self.mongo_db.append_trade(trade_record)
                    
                    self.mongo_db.insert_position({
                        "symbol": symbol,
                        "side": "long",
                        "entry_price": trade_record["price"],
                        "initial_amount": amount_to_trade,
                        "amount_remaining": amount_to_trade,
                        "highest_price": trade_record["price"],
                        "lowest_price": trade_record["price"],
                        "1r_taken": False,
                        "2r_taken": False,
                        "status": "OPEN",
                        "entry_time": timestamp
                    })
                    
            elif action == "SELL":
                if pos and pos['side'] == 'long':
                    amount_to_sell = pos['amount'] * amount_pct
                    logger.info(f"[LiveTrader] 🔴 EXECUTING SELL TO CLOSE LONG {symbol} | Amount: {amount_to_sell}")
                    order = await self.exchange.create_market_sell_order(ccxt_symbol, amount_to_sell, params={"reduceOnly": True})
                    
                    pnl = pos['unrealized_pnl'] * amount_pct
                    pnl_pct = pos['pnl_pct']
                    trade_record = {"type": "SELL", "symbol": symbol, "amount": amount_to_sell, "price": order.get('average', current_price), "time": timestamp, "confidence": confidence, "pnl": pnl, "pnl_pct": pnl_pct}
                    self.trade_history.append(trade_record)
                    self.mongo_db.append_trade(trade_record)
                    
                elif pos and pos['side'] == 'short':
                    pass # Already short
                else:
                    logger.info(f"[LiveTrader] 🔴 EXECUTING SELL TO OPEN SHORT {symbol} | Size: ${trade_amount_usdt:.2f}")
                    order = await self.exchange.create_market_sell_order(ccxt_symbol, amount_to_trade)
                    trade_record = {"type": "SELL", "symbol": symbol, "amount": amount_to_trade, "price": order.get('average', current_price), "time": timestamp, "confidence": confidence, "pnl": 0.0, "pnl_pct": 0.0}
                    self.trade_history.append(trade_record)
                    self.mongo_db.append_trade(trade_record)
                    
                    self.mongo_db.insert_position({
                        "symbol": symbol,
                        "side": "long",
                        "entry_price": trade_record["price"],
                        "initial_amount": amount_to_trade,
                        "amount_remaining": amount_to_trade,
                        "highest_price": trade_record["price"],
                        "lowest_price": trade_record["price"],
                        "1r_taken": False,
                        "2r_taken": False,
                        "status": "OPEN",
                        "entry_time": timestamp
                    })
        except Exception as e:
            logger.error(f"[LiveTrader] ❌ EXECUTION FAILED FOR {symbol}: {e}")

    def get_status_sync(self):
        """Synchronous approximation for portfolio_state injection"""
        return {"balance": {"total": 100000.0}} # Placeholder if needed

    async def get_status(self):
        balance = await self.get_balance()
        positions = await self.get_positions()

        # USDT balance: CCXT returns balance dict at top level AND per-currency
        # The USDT sub-dict is the reliable key for Demo/Futures
        usdt_info = balance.get('USDT') or {}
        free_usdt = float(usdt_info.get('free') or balance.get('free') or 0.0)
        total_usdt = float(usdt_info.get('total') or balance.get('total') or 0.0)

        # Calculate Win Rate from history
        wins = sum(1 for t in self.trade_history if (t.get('pnl') or 0) > 0)
        total_sells = sum(1 for t in self.trade_history if t.get('type') == 'SELL')
        win_rate = (wins / total_sells * 100) if total_sells > 0 else 0.0

        target_trades = 100
        progress_pct = min(100, (wins / target_trades) * 100) if target_trades > 0 else 0

        positions_value = sum(pos.get('value_usdt', 0.0) for pos in positions)
        total_portfolio_value = total_usdt + positions_value
        
        return {
            "status": self.status,
            "testnet": self.testnet,
            "balance": {
                "total": total_usdt,
                "free": free_usdt,
            },
            "active_positions": positions,
            "metrics": {
                "total_trades": len(self.trade_history),
                "win_rate": win_rate
            },
            "target_trades": target_trades,
            "progress_pct": progress_pct,
            "gamification": {
                "winning_trades": wins,
                "losing_trades": total_sells - wins,
                "total_trades": len(self.trade_history),
                "virtual_balance": total_portfolio_value,
                "starting_balance": 100000.0,
                "level": 1 + (len(self.trade_history) // 10),
                "xp": len(self.trade_history) * 50,
                "status": self.status
            },
            "telemetry": {
                sym: {
                    "action": data["prediction"]["action"],
                    "confidence": data["prediction"]["confidence"],
                    "llm_rationale": data.get("llm_rationale", "")
                }
                for sym, data in self.explainability_data.items()
                if "prediction" in data
            },
            "scanner_logs": self.scanner_logs
        }
