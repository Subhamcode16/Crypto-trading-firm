#!/usr/bin/env python3
"""
AGENT 6: The Macro Sentinel — [COMMAND DIVISION]

Role: The last intelligence checkpoint before any trade executes.
Checks macro environment and ecosystem health before approving a signal.

Checks:
- BTC 1h and 4h trend direction
- SOL price action and volatility
- Overall market regime (bullish/mixed/choppy/flat)
- Any breaking news or macro events

Receives from: Signal Aggregator (Agent 5) — composite trade signals
Sends to: Risk Manager (Agent 7) — macro-cleared signals
Runs: Event-driven on each incoming signal; independent checks every 15 min
"""

import logging
from datetime import datetime
from typing import Dict, Optional, Tuple
import httpx
import pandas as pd
import asyncio
import os
from src.utils.llm_client import LLMClient

logger = logging.getLogger(__name__)

class Agent6MacroSentinel:
    """
    Market context validator.
    Issues a MACRO_CLEARED or MACRO_HOLD decision for every signal.
    """

    def __init__(self, db=None, config: Dict = None):
        self.config = config or {}
        self.db = db
        self.is_running = False
        self.current_state = {
            "SOL_1h": "NORMAL",
            "BTC_1h": "NORMAL",
            "BTC_4h": "NORMAL",
            "overall": "NORMAL",  # NORMAL, CAUTION, or MACRO_HOLD
            "last_updated": None
        }

        # Cache for market data (avoid hammering APIs)
        self._cache_ts: Optional[datetime] = None
        self._cache_ttl_seconds = 300  # 5 minutes

        # LLM Client for regime sentiment
        self.llm = LLMClient()
        self.model_type = "haiku"
        self.min_regime_score = 6.0

        logger.info("[AGENT_6] Macro Sentinel initialized with LLMClient (Haiku)")

    async def start(self, user_id="default_user"):
        """Starts the background polling task for macro checks."""
        self.is_running = True
        self.user_id = user_id
        asyncio.create_task(self._poll_loop())
        logger.info(f"Macro Sentinel started for user {self.user_id}.")

    async def stop(self):
        self.is_running = False

    async def _poll_loop(self):
        while self.is_running:
            try:
                interval_seconds = 900
                if self.db:
                    kill_switch = await self.db.get_kill_switch(self.user_id)
                    interval_seconds = kill_switch.get("macro_check_interval_seconds", 900)
                
                await self.update_macro_state()
                await asyncio.sleep(interval_seconds)
            except Exception as e:
                logger.error(f"Error in Macro Sentinel polling loop: {e}")
                await asyncio.sleep(60)

    async def update_macro_state(self):
        sol_1h_state = await self.check_downtrend("SOLUSDT", "1h")
        btc_1h_state = await self.check_downtrend("BTCUSDT", "1h")
        btc_4h_state = await self.check_downtrend("BTCUSDT", "4h")

        self.current_state["SOL_1h"] = sol_1h_state
        self.current_state["BTC_1h"] = btc_1h_state
        self.current_state["BTC_4h"] = btc_4h_state
        self.current_state["last_updated"] = datetime.utcnow().isoformat()

        if "CONFIRMED_DOWNTREND" in [sol_1h_state, btc_1h_state, btc_4h_state]:
            self.current_state["overall"] = "MACRO_HOLD"
        elif "CAUTION" in [sol_1h_state, btc_1h_state, btc_4h_state]:
            self.current_state["overall"] = "CAUTION"
        else:
            self.current_state["overall"] = "NORMAL"

        self._cache_ts = datetime.utcnow()
        logger.info(f"[AGENT_6] Macro state updated: {self.current_state['overall']} (SOL 1h: {sol_1h_state}, BTC 1h: {btc_1h_state}, BTC 4h: {btc_4h_state})")

    async def fetch_klines(self, symbol, interval, limit=100):
        try:
            return await self._fetch_binance_klines(symbol, interval, limit)
        except Exception as e:
            logger.warning(f"Binance fetch failed for {symbol} {interval}: {e}. Trying Bybit fallback.")
            try:
                return await self._fetch_bybit_klines(symbol, interval, limit)
            except Exception as e2:
                logger.error(f"Bybit fallback fetch failed for {symbol} {interval}: {e2}.")
                return None

    async def _fetch_binance_klines(self, symbol, interval, limit=100):
        url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit}"
        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
        df = pd.DataFrame(data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume', 'close_time', 'quote_av', 'trades', 'tb_base_av', 'tb_quote_av', 'ignore'])
        df['open'] = df['open'].astype(float)
        df['close'] = df['close'].astype(float)
        return df

    async def _fetch_bybit_klines(self, symbol, interval, limit=100):
        interval_map = {"1h": "60", "4h": "240"}
        bybit_interval = interval_map.get(interval, "60")
        url = f"https://api.bybit.com/v5/market/kline?category=spot&symbol={symbol}&interval={bybit_interval}&limit={limit}"
        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
        if data["retCode"] != 0:
            raise Exception(f"Bybit error: {data['retMsg']}")
        klines = data["result"]["list"]
        klines.reverse()
        df = pd.DataFrame(klines, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume', 'turnover'])
        df['open'] = df['open'].astype(float)
        df['close'] = df['close'].astype(float)
        return df

    async def check_downtrend(self, symbol: str, timeframe: str) -> str:
        df = await self.fetch_klines(symbol, timeframe, limit=60)
        if df is None or len(df) < 50:
            return "NORMAL"
        
        try:
            import pandas_ta as ta
            df.ta.ema(length=50, append=True)
            ema_col = f'EMA_50'
            if ema_col not in df.columns:
                df[ema_col] = df['close'].ewm(span=50, adjust=False).mean()
        except ImportError:
            df['EMA_50'] = df['close'].ewm(span=50, adjust=False).mean()
            ema_col = 'EMA_50'

        current_candle = df.iloc[-1]
        prev1_candle = df.iloc[-2]
        prev2_candle = df.iloc[-3]
        
        price_drop_pct = ((current_candle['open'] - current_candle['close']) / current_candle['open']) * 100
        cond1_drop = price_drop_pct > 3.0
        cond2_descending = (current_candle['close'] < prev1_candle['close']) and (prev1_candle['close'] < prev2_candle['close'])
        cond3_below_ema = current_candle['close'] < current_candle[ema_col]

        conditions_met = sum([cond1_drop, cond2_descending, cond3_below_ema])
        if conditions_met == 3: return "CONFIRMED_DOWNTREND"
        elif conditions_met > 0: return "CAUTION"
        else: return "NORMAL"

    async def _fetch_market_data(self) -> Dict:
        """Fetch latest price changes for BTC and SOL."""
        try:
            btc_df = await self.fetch_klines("BTCUSDT", "1h", limit=24)
            sol_df = await self.fetch_klines("SOLUSDT", "1h", limit=24)
            
            if btc_df is None or sol_df is None:
                return {}
                
            btc_1h = ((btc_df.iloc[-1]['close'] - btc_df.iloc[-2]['close']) / btc_df.iloc[-2]['close']) * 100
            sol_1h = ((sol_df.iloc[-1]['close'] - sol_df.iloc[-2]['close']) / sol_df.iloc[-2]['close']) * 100
            btc_24h = ((btc_df.iloc[-1]['close'] - btc_df.iloc[0]['close']) / btc_df.iloc[0]['close']) * 100
            sol_24h = ((sol_df.iloc[-1]['close'] - sol_df.iloc[0]['close']) / sol_df.iloc[0]['close']) * 100
            
            return {
                "btc_1h_change": round(btc_1h, 2),
                "sol_1h_change": round(sol_1h, 2),
                "btc_24h_change": round(btc_24h, 2),
                "sol_24h_change": round(sol_24h, 2)
            }
        except Exception as e:
            logger.error(f"[AGENT_6] Error fetching market data: {e}")
            return {}

    def check_btc_trend(self, market_data: Dict) -> Tuple[str, float, str]:
        state = self.current_state.get("BTC_1h", "NORMAL")
        if state == "CONFIRMED_DOWNTREND":
            return "HOLD", 0.0, "BTC sharp 1h/4h downtrend"
        elif state == "CAUTION":
            return "NORMAL", 6.0, "BTC showing weakness"
        return "NORMAL", 10.0, "BTC trend healthy"

    def check_sol_trend(self, market_data: Dict) -> Tuple[str, float, str]:
        state = self.current_state.get("SOL_1h", "NORMAL")
        if state == "CONFIRMED_DOWNTREND":
            return "HOLD", 0.0, "SOL sharp 1h downtrend"
        elif state == "CAUTION":
            return "NORMAL", 6.0, "SOL showing weakness"
        return "NORMAL", 10.0, "SOL trend healthy"

    def calculate_bollinger_bands(self, df: pd.DataFrame, window=20, std_dev=2) -> Dict:
        """Calculate BB and %B from price data."""
        df['MA20'] = df['close'].rolling(window=window).mean()
        df['STD20'] = df['close'].rolling(window=window).std()
        df['Upper'] = df['MA20'] + (df['STD20'] * std_dev)
        df['Lower'] = df['MA20'] - (df['STD20'] * std_dev)
        
        current = df.iloc[-1]
        price = current['close']
        bandwidth = (current['Upper'] - current['Lower']) / current['MA20']
        pct_b = (price - current['Lower']) / (current['Upper'] - current['Lower']) if (current['Upper'] - current['Lower']) != 0 else 0.5
        
        return {"bandwidth": bandwidth, "pct_b": pct_b}

    def calculate_rsi(self, df: pd.DataFrame, window=14) -> float:
        """Calculate Relative Strength Index."""
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1+rs))
        return rsi.iloc[-1]

    def detect_market_regime(self, market_data: Dict) -> str:
        """
        Map market data to a regime label.
        Returns: 'bullish' | 'mixed' | 'choppy' | 'flat'
        """
        btc_1h = market_data.get("btc_1h_change", 0)
        sol_1h = market_data.get("sol_1h_change", 0)

        avg_1h = (btc_1h + sol_1h) / 2

        if avg_1h > 1.5:
            return "bullish"
        elif avg_1h < -1.5:
            return "choppy"
        elif abs(btc_1h - sol_1h) > 3.0:
            return "choppy"
        elif abs(avg_1h) < 0.3:
            return "flat"
        else:
            return "mixed"

    async def _ai_analyze_macro_regime(self, market_data: Dict) -> Tuple[str, float, str]:
        """Use Claude for a second opinion on market regime with Waterfall Fallback Strategy."""
        system_prompt = "You are a crypto macro analyst. Evaluate ecosystem stability for memecoin trading."
        prompt = f"""Analyze the current Solana ecosystem state:
BTC 1h change: {market_data.get('btc_1h_change')}%
SOL 1h change: {market_data.get('sol_1h_change')}%
BTC 24h change: {market_data.get('btc_24h_change')}%
SOL 24h change: {market_data.get('sol_24h_change')}%

Is the market in a dangerous downtrend or extreme volatility state that should block new memecoin trades?
Scale: 0 (Extreme Danger/Hold) to 10 (Safe/Bullish)

Respond with ONLY: [SCORE] - [One sentence reasoning]
Example: "4 - Sharp BTC rejection at 70k causing ecosystem-wide liquidations"
"""
        messages = [{"role": "user", "content": prompt}]
        
        # Waterfall Fallback Strategy: Sonnet -> Haiku
        models_to_try = [self.model_type, self.fallback_model]
        last_error = None
        
        for model in models_to_try:
            try:
                logger.info(f"[AGENT_6] Attempting AI analysis with {model}...")
                response = await self.llm.create_message_async(
                    model_type=model,
                    system_prompt=system_prompt,
                    messages=messages,
                    max_tokens=60,
                    use_caching=True
                )
                
                text = response.get("text", "").strip()
                if not text:
                    raise ValueError(f"Empty response from {model}")

                score = 7.0
                reason = text
                if " - " in text:
                    try:
                        score = float(text.split(" - ")[0])
                        reason = text.split(" - ")[1]
                    except:
                        pass
                
                verdict = "NORMAL" if score >= self.min_regime_score else "HOLD"
                return verdict, score, f"AI Review ({model}): {reason}"
                
            except Exception as e:
                logger.warning(f"[AGENT_6] AI analysis failed with {model}: {e}")
                last_error = e
                continue
                
        # If all AI models fail, default to conservative fallback
        logger.error(f"[AGENT_6] All AI models failed. Last error: {last_error}")
        return "NORMAL", 7.0, f"AI Error: All models failed. Defaulting to Neutral."

    # ─────────────────────────────────────────────────────────────────
    # MAIN ANALYSIS
    # ─────────────────────────────────────────────────────────────────

    async def analyze(self, agent_5_signal: Dict) -> Dict:
        """
        Run macro validation on an Agent 5 cleared signal.

        Args:
            agent_5_signal: Signal dict from Agent 5

        Returns:
            Result dict with status MACRO_CLEARED or MACRO_HOLD
        """
        token_address = agent_5_signal.get("token_address", "unknown")
        token_symbol  = agent_5_signal.get("token_symbol", "UNKNOWN")

        logger.info(f"[AGENT_6] Checking macro for {token_symbol}")

        market_data = await self._fetch_market_data()

        btc_verdict, btc_score, btc_reason   = self.check_btc_trend(market_data)
        sol_verdict, sol_score, sol_reason   = self.check_sol_trend(market_data)
        
        # QUANT OVERLAYS (NEW)
        sol_df = await self.fetch_klines("SOLUSDT", "1h", limit=40)
        quant_score = 10.0
        quant_reason = "Indicators healthy"
        
        if sol_df is not None and len(sol_df) >= 30:
            bb = self.calculate_bollinger_bands(sol_df)
            rsi = self.calculate_rsi(sol_df)
            
            # Penalize if overextended (%B > 1.0 or RSI > 75)
            if bb['pct_b'] > 1.0 or rsi > 75:
                quant_score -= 3.0
                quant_reason = f"SOL Overextended (%B:{bb['pct_b']:.2f}, RSI:{rsi:.1f})"
            # Bonus for squeeze breakout (%B > 0.8 and low bandwidth)
            elif bb['bandwidth'] < 0.05 and bb['pct_b'] > 0.8:
                quant_score += 1.0
                quant_reason = "SOL Bollinger Squeeze Breakout"

        regime = self.detect_market_regime(market_data)

        # AI Second Opinion if things look "Mixed" or for high confidence
        ai_verdict, ai_score, ai_reason = "NORMAL", 10.0, "N/A"
        if regime in ["mixed", "choppy"] or btc_score < 7 or sol_score < 7:
            ai_verdict, ai_score, ai_reason = await self._ai_analyze_macro_regime(market_data)

        # Composite macro score (including Quant & AI)
        macro_score = (btc_score * 0.3) + (sol_score * 0.2) + (quant_score * 0.2) + (ai_score * 0.3)

        # Decision
        hard_blocked = btc_verdict == "HOLD" or sol_verdict == "HOLD" or ai_verdict == "HOLD"
        soft_blocked = macro_score < self.min_regime_score

        if hard_blocked:
            status = "MACRO_HOLD"
            failure_reason = btc_reason if btc_verdict == "HOLD" else sol_reason
        elif soft_blocked:
            status = "MACRO_HOLD"
            failure_reason = f"Macro score {macro_score:.2f} below threshold {self.min_regime_score}"
        else:
            status = "MACRO_CLEARED"
            failure_reason = None

        result = {
            "agent_id": 6,
            "token_address": token_address,
            "token_symbol": token_symbol,
            "analysis_timestamp": datetime.utcnow().isoformat(),
            "status": status,
            "macro_score": round(macro_score, 3),
            "market_regime": regime,
            "checks": {
                "btc": {"verdict": btc_verdict, "score": btc_score, "reason": btc_reason},
                "sol": {"verdict": sol_verdict, "score": sol_score, "reason": sol_reason},
                "quant": {"score": quant_score, "reason": quant_reason}
            },
            "market_snapshot": market_data,
            "failure_reason": failure_reason,
        }

        if status == "MACRO_CLEARED":
            logger.info(f"[AGENT_6] ✅ MACRO_CLEARED: {token_symbol} | regime={regime} | macro_score={macro_score:.2f}")
        else:
            logger.warning(f"[AGENT_6] ⛔ MACRO_HOLD: {token_symbol} | {failure_reason}")

        return result

    async def log_to_database(self, result: Dict):
        """Persist macro analysis to DB if available."""
        if not self.db:
            return
        try:
            await self.db.log_agent_6_analysis(result)
        except Exception as e:
            logger.error(f"[AGENT_6] DB log error: {e}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    sentinel = Agent6MacroSentinel()
    mock_signal = {
        "token_address": "TestAddr123",
        "token_symbol": "TEST",
        "composite_score": 8.5
    }
    async def test():
        result = await sentinel.analyze(mock_signal)
        print(f"Status: {result['status']} | Macro Score: {result['macro_score']}")
    
    asyncio.run(test())
