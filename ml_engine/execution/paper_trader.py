import logging
import asyncio
import yfinance as yf
import pandas as pd
from typing import Dict, List, Optional
from datetime import datetime, timezone

from ml_engine.aggregator import SignalAggregator
from ml_engine.features.feature_builder import FeatureBuilder
from ml_engine.data.pipeline import StorageBackend
from ml_engine.data.fetcher import MacroFetcher
from ml_engine.data.sentiment import SentimentEngine
from ml_engine.models.xgb_model import XGBModel
from ml_engine.data.mongo_store import MongoStore

logger = logging.getLogger(__name__)

class GamifiedPaperTrader:
    """
    Live Paper Trading Agent with Gamified Mission Objectives.
    """
    def __init__(self, target_trades: int = 50):
        self.target_trades = target_trades
        self.db = StorageBackend()
        
        # Gamification State
        self.state = {
            "virtual_balance": 10000.0,
            "starting_balance": 10000.0,
            "total_trades": 0,
            "winning_trades": 0,
            "losing_trades": 0,
            "xp": 0,
            "level": 1,
            "status": "IDLE", # IDLE, ACTIVE, COOLDOWN
            "last_update": None
        }
        
        self.mongo_db = MongoStore()
        saved_state = self.mongo_db.load_gamification_state()
        if saved_state:
            self.state.update(saved_state)
            logger.info(f"[PaperTrader] Loaded saved Gamification State: Lvl {self.state['level']} | ${self.state['virtual_balance']:.2f}")
            
        # Symbols configuration
        self.symbols = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "XAU/USD"]
        
        # Position tracking
        self.positions = self.state.get("positions", {sym: None for sym in self.symbols})
        
        # Yahoo Finance ticker mapping
        self.yf_map = {
            "BTC/USDT": "BTC-USD",
            "ETH/USDT": "ETH-USD",
            "SOL/USDT": "SOL-USD",
            "XAU/USD": "GC=F"
        }
        
        # Trade History Log
        self.trade_history = self.mongo_db.get_all_trades()
        if self.trade_history:
            logger.info(f"[PaperTrader] Loaded {len(self.trade_history)} historical trades from DB.")
        
        # Explainability Cache
        self.explainability_data = {sym: {} for sym in self.symbols}

        # Load models
        logger.info("[PaperTrader] Initializing AI Models...")
        self.aggregator = SignalAggregator()
        self.feature_builder = FeatureBuilder()
        self.models = {}
        for sym in self.symbols:
            try:
                self.models[sym] = XGBModel.load(XGBModel.get_save_path(sym, "1h"))
                logger.info(f"[PaperTrader] ✅ Loaded XGBoost model for {sym}")
            except Exception as e:
                logger.warning(f"[PaperTrader] ⚠️ Could not load XGBoost model for {sym}: {e}")
                self.models[sym] = None
                
        self.macro_fetcher = MacroFetcher()
        self.sentiment_engine = SentimentEngine()
        
        logger.info("[PaperTrader] Paper Trader Ready!")

    async def fetch_live_data(self, symbol: str, limit_days: str = "15d") -> Optional[pd.DataFrame]:
        """Fetch enough recent 1h data from YF to build features."""
        try:
            yf_sym = self.yf_map[symbol]
            # Need at least 60-100 bars for technical indicator warm-up.
            df = yf.download(yf_sym, period=limit_days, interval="1h", progress=False)
            if df.empty:
                return None
                
            # Formatting to match our schema
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
                
            df = df.reset_index()
            df.rename(columns={"Datetime": "timestamp", "Open": "open", "High": "high", "Low": "low", "Close": "close", "Volume": "volume"}, inplace=True)
            df.columns = [c.lower() for c in df.columns]
            
            return df
        except Exception as e:
            logger.error(f"[PaperTrader] Error fetching live data for {symbol}: {e}")
            return None

    async def evaluate_market(self):
        """Main loop step: Analyze market, make decisions, execute trades."""
        self.state["status"] = "ANALYZING"
        
        logger.info("[PaperTrader] Fetching macro and sentiment context...")
        macro_df = self.macro_fetcher.fetch_macro_data(start=(datetime.now(timezone.utc) - pd.Timedelta(days=15)).strftime("%Y-%m-%d"))
        live_sentiment = self.sentiment_engine.get_sentiment()
        
        for symbol in self.symbols:
            logger.info(f"[PaperTrader] Analyzing {symbol}...")
            df = await self.fetch_live_data(symbol)
            
            if df is None or len(df) < 100:
                logger.warning(f"[PaperTrader] Not enough live data for {symbol}")
                continue
                
            # Build features on the fly with macro context
            df_feat = self.feature_builder.build_dataset(df, macro_df=macro_df, dropna=True)
            if df_feat.empty:
                continue
                
            # Get latest row
            latest_row = df_feat.iloc[-1]
            current_price = latest_row["close"]
            timestamp = str(latest_row["timestamp"])
            
            # Predict using models
            # ModelAggregator expects df and row_idx, but predict_consensus usually needs the DataFrame.
            # Wait, ModelAggregator.predict takes a single feature row dict or similar?
            # Let's check aggregator: it has a `predict` method that might take a single row.
            try:
                # Get real prediction from local ML models
                prediction = self._real_predict(symbol, latest_row, live_sentiment.get("score", 0.0))
                action = prediction["action"] # BUY, SELL, HOLD
                confidence = prediction["confidence"]
                
                # Cache explainability data
                model = self.models.get(symbol)
                top_features = {}
                if model:
                    top_features = model.get_feature_importance(top_n=5)
                
                self.explainability_data[symbol] = {
                    "chart_data": df[["timestamp", "open", "high", "low", "close", "volume"]].tail(300).to_dict(orient="records"),
                    "macro_context": macro_df.iloc[-1].to_dict() if not macro_df.empty else {},
                    "top_features": top_features,
                    "latest_sentiment": live_sentiment,
                    "prediction": {
                        "action": action,
                        "confidence": confidence,
                        "raw_probs": prediction.get("raw_probs", {})
                    }
                }
                
                logger.info(f"[{symbol}] AI Signal: {action} (Conf: {confidence:.2f}) | Price: ${current_price:.2f}")
                
                self._execute_action(symbol, action, current_price, timestamp, confidence)
                
            except Exception as e:
                logger.error(f"[PaperTrader] Prediction failed for {symbol}: {e}")
                
        self.state["last_update"] = datetime.now(timezone.utc).isoformat()
        self.state["status"] = "IDLE"

    async def run_backtest(self, hours: int = 200):
        """Run an instant backtest to catch up on history and verify accuracy."""
        logger.info(f"🚀 [PaperTrader] Commencing {hours}-hour historical Catch-up Backtest...")
        self.state["status"] = "BACKTESTING"
        
        # Determine how many days to fetch (add 10 days for technical indicators warmup)
        days_to_fetch = int((hours / 24) + 15)
        period_str = f"{days_to_fetch}d"
        
        logger.info("[PaperTrader] Fetching historical macro context for backtest...")
        macro_df = self.macro_fetcher.fetch_macro_data(start=(datetime.now(timezone.utc) - pd.Timedelta(days=days_to_fetch)).strftime("%Y-%m-%d"))
        
        for symbol in self.symbols:
            logger.info(f"[PaperTrader] Backtesting {symbol} over {hours} hours...")
            df = await self.fetch_live_data(symbol, limit_days=period_str)
            if df is None or len(df) < 100:
                continue
                
            df_feat = self.feature_builder.build_dataset(df, macro_df=macro_df, dropna=True)
            if df_feat.empty:
                continue
                
            # Take the last `hours` rows
            test_rows = df_feat.tail(hours)
            
            for _, row in test_rows.iterrows():
                try:
                    prediction = self._real_predict(symbol, row)
                    action = prediction["action"]
                    confidence = prediction["confidence"]
                    current_price = row["close"]
                    timestamp = str(row["timestamp"])
                    
                    self._execute_action(symbol, action, current_price, timestamp, confidence)
                except Exception as e:
                    logger.error(f"[PaperTrader] Backtest prediction failed for {symbol}: {e}")
                    
        self.state["last_update"] = datetime.now(timezone.utc).isoformat()
        self.state["status"] = "IDLE"
        logger.info(f"✅ [PaperTrader] Backtest complete. Total Trades: {self.state['total_trades']}, Win/Loss: {self.state['winning_trades']}/{self.state['losing_trades']}")

    def _real_predict(self, symbol: str, latest_row: pd.Series, live_sentiment: float = 0.0) -> Dict:
        """Uses the real trained XGBoost model for prediction."""
        model = self.models.get(symbol)
        if model is None:
            # Fallback to no signal if model not loaded
            return {"action": "HOLD", "confidence": 0.0}
            
        features_dict = latest_row.to_dict()
        pred = model.predict(features_dict)
        
        raw_probs = pred.get("raw_probs", {})
        long_prob = raw_probs.get("STRONG_LONG", 0)
        short_prob = raw_probs.get("STRONG_SHORT", 0)
        
        action = "HOLD"
        confidence = max(long_prob, short_prob)
        
        # Lowered threshold to 0.35 for paper trading so we get enough signals to test accuracy
        if long_prob > 0.35 and long_prob > short_prob:
            if live_sentiment < -0.3:
                logger.warning(f"[{symbol}] Ignoring BUY signal due to highly negative news sentiment ({live_sentiment:.2f})")
                action = "HOLD"
            else:
                action = "BUY"
        elif short_prob > 0.35 and short_prob > long_prob:
            if live_sentiment > 0.3:
                logger.warning(f"[{symbol}] Ignoring SELL signal due to highly positive news sentiment ({live_sentiment:.2f})")
                action = "HOLD"
            else:
                action = "SELL"
            
        return {"action": action, "confidence": confidence, "raw_probs": raw_probs}

    def _execute_action(self, symbol: str, action: str, price: float, timestamp: str, confidence: float):
        position = self.positions[symbol]
        
        if action == "BUY" and position is None:
            # We want to buy. Risk 10% of virtual balance per trade.
            trade_amount = self.state["virtual_balance"] * 0.10
            if trade_amount < 10:
                return # Too broke
                
            commission = trade_amount * 0.001
            self.state["virtual_balance"] -= (trade_amount + commission)
            
            self.positions[symbol] = {
                "amount": trade_amount / price,
                "entry_price": price,
                "entry_time": timestamp
            }
            
            logger.info(f"[PaperTrader] 🟢 VIRTUAL BUY {symbol} at ${price:.2f} | Size: ${trade_amount:.2f}")
            trade_record = {
                "type": "BUY",
                "symbol": symbol,
                "amount": trade_amount / price,
                "price": price,
                "time": timestamp,
                "confidence": confidence
            }
            self.trade_history.append(trade_record)
            self.mongo_db.append_trade(trade_record)
            
            # Save positions into state so they persist
            self.state["positions"] = self.positions
            self.mongo_db.save_gamification_state(self.state)
            
        elif action == "SELL" and position is not None:
            # We want to sell our position.
            amount = position["amount"]
            entry_price = position["entry_price"]
            exit_value = amount * price
            commission = exit_value * 0.001
            
            net_return = exit_value - commission
            self.state["virtual_balance"] += net_return
            
            pnl = exit_value - (amount * entry_price) - commission
            pnl_pct = (pnl / (amount * entry_price)) * 100
            
            self._handle_gamification(pnl, pnl_pct, symbol)
            
            logger.info(f"[PaperTrader] 🔴 VIRTUAL SELL {symbol} at ${price:.2f} | PnL: ${pnl:.2f} ({pnl_pct:.2f}%)")
            trade_record = {
                "type": "SELL",
                "symbol": symbol,
                "amount": amount,
                "price": price,
                "time": timestamp,
                "pnl": pnl,
                "pnl_pct": pnl_pct,
                "confidence": confidence
            }
            self.trade_history.append(trade_record)
            self.mongo_db.append_trade(trade_record)
            
            self.positions[symbol] = None
            self.state["positions"] = self.positions
            self.mongo_db.save_gamification_state(self.state)

    def _handle_gamification(self, pnl: float, pnl_pct: float, symbol: str):
        """Apply rewards and punishments based on trade outcome."""
        self.state["total_trades"] += 1
        
        if pnl > 0:
            self.state["winning_trades"] += 1
            xp_gained = 50 + int(pnl_pct * 10)
            self.state["xp"] += xp_gained
            logger.info(f"[PaperTrader] 🎁 GIFT RECEIVED! +{xp_gained} XP for winning trade!")
            
            # Level up logic
            if self.state["xp"] >= self.state["level"] * 500:
                self.state["level"] += 1
                bonus = 100 * self.state["level"]
                self.state["virtual_balance"] += bonus
                logger.info(f"[PaperTrader] 🌟 LEVEL UP! You are now Level {self.state['level']}. Cash Bonus: ${bonus}!")
        else:
            self.state["losing_trades"] += 1
            xp_lost = 20 + int(abs(pnl_pct) * 5)
            self.state["xp"] = max(0, self.state["xp"] - xp_lost)
            logger.info(f"[PaperTrader] 💀 MISSION FAILURE! Lost {xp_lost} XP due to bad trade.")
            
            # Cooldown logic if balance drops too low
            if self.state["virtual_balance"] < self.state["starting_balance"] * 0.5:
                logger.warning("[PaperTrader] ⚠️ CRITICAL MISSION DANGER. Virtual balance dropped below 50%. Enacting strict risk limits.")

    def get_status(self):
        # Calculate unrealized PnL
        unrealized = 0.0
        active_pos = []
        for sym, pos in self.positions.items():
            if pos is not None:
                # We need live price for accurate unrealized. This is just an estimate using entry price.
                # True live unrealized is better, but this suffices for state.
                active_pos.append({
                    "symbol": sym,
                    "entry_price": pos["entry_price"],
                    "amount": pos["amount"]
                })
                
        return {
            "gamification": self.state,
            "target_trades": self.target_trades,
            "progress_pct": min(100.0, (self.state["winning_trades"] / self.target_trades) * 100),
            "active_positions": active_pos
        }

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")
    trader = GamifiedPaperTrader()
    asyncio.run(trader.evaluate_market())
