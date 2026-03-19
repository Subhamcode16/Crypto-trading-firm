import asyncio
import logging
import httpx
import pandas as pd
from datetime import datetime

logger = logging.getLogger('macro_sentinel')

class MacroSentinel:
    """Agent-6: Macro Sentinel checks macro environment before approving any signal. (Async)"""

    def __init__(self, db, user_id="default_user"):
        self.db = db
        self.user_id = user_id
        self.is_running = False
        self.client = httpx.AsyncClient(timeout=10)
        self.current_state = {
            "SOL_1h": "NORMAL",
            "BTC_1h": "NORMAL",
            "BTC_4h": "NORMAL",
            "overall": "NORMAL",  # NORMAL, CAUTION, or CONFIRMED_DOWNTREND
            "last_updated": None
        }
        self.polling_task = None

    def start(self):
        """Starts the background polling task for macro checks (Async)."""
        if self.is_running:
            return
        self.is_running = True
        self.polling_task = asyncio.create_task(self._poll_loop())
        logger.info(f"Macro Sentinel started for user {self.user_id}.")

    async def stop(self):
        """Stops the background polling task and closes the client."""
        self.is_running = False
        if self.polling_task:
            self.polling_task.cancel()
            try:
                await self.polling_task
            except asyncio.CancelledError:
                pass
        await self.client.aclose()
        logger.info("Macro Sentinel stopped.")

    async def _poll_loop(self):
        """Background loop reading DB for interval and running checks (Async)."""
        while self.is_running:
            try:
                # 1. Fetch current interval from DB
                kill_switch = await self.db.get_kill_switch(self.user_id) if self.db else {}
                interval_seconds = kill_switch.get("macro_check_interval_seconds", 900)
                
                # 2. Run the actual checks
                await self.update_macro_state()
                
                # 3. Sleep for the configured interval
                await asyncio.sleep(interval_seconds)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in Macro Sentinel polling loop: {e}")
                await asyncio.sleep(60)  # Sleep 1 min on error before retrying

    async def update_macro_state(self):
        """Updates internal macro state based on 3-condition logic (Async)."""
        # Run checks in parallel for SOL and BTC
        sol_1h_task = self.check_downtrend("SOLUSDT", "1h")
        btc_1h_task = self.check_downtrend("BTCUSDT", "1h")
        btc_4h_task = self.check_downtrend("BTCUSDT", "4h")
        
        results = await asyncio.gather(sol_1h_task, btc_1h_task, btc_4h_task)
        sol_1h_state, btc_1h_state, btc_4h_state = results

        self.current_state["SOL_1h"] = sol_1h_state
        self.current_state["BTC_1h"] = btc_1h_state
        self.current_state["BTC_4h"] = btc_4h_state
        self.current_state["last_updated"] = datetime.utcnow().isoformat()

        # Aggregate state
        if "CONFIRMED_DOWNTREND" in results:
            self.current_state["overall"] = "CONFIRMED_DOWNTREND"
        elif "CAUTION" in results:
            self.current_state["overall"] = "CAUTION"
        else:
            self.current_state["overall"] = "NORMAL"

        logger.info(f"Macro state updated: {self.current_state['overall']} (SOL 1h: {sol_1h_state}, BTC 1h: {btc_1h_state}, BTC 4h: {btc_4h_state})")

    async def fetch_klines(self, symbol, interval, limit=100) -> Optional[pd.DataFrame]:
        """Fetch klines from Binance, fallback to Bybit (Async)."""
        try:
            return await self._fetch_binance_klines(symbol, interval, limit)
        except Exception as e:
            logger.warning(f"Binance fetch failed for {symbol} {interval}: {e}. Trying Bybit fallback.")
            try:
                return await self._fetch_bybit_klines(symbol, interval, limit)
            except Exception as e2:
                logger.error(f"Bybit fallback fetch failed for {symbol} {interval}: {e2}.")
                return None

    async def _fetch_binance_klines(self, symbol, interval, limit=100) -> pd.DataFrame:
        """Fetch klines from Binance API (Async)."""
        url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit}"
        response = await self.client.get(url)
        response.raise_for_status()
        data = response.json()
        
        # [Open time, Open, High, Low, Close, Volume, ...]
        df = pd.DataFrame(data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume', 'close_time', 'quote_av', 'trades', 'tb_base_av', 'tb_quote_av', 'ignore'])
        df['open'] = df['open'].astype(float)
        df['close'] = df['close'].astype(float)
        
        return df

    async def _fetch_bybit_klines(self, symbol, interval, limit=100) -> pd.DataFrame:
        """Fetch klines from Bybit API V5 (Async)."""
        interval_map = {"1h": "60", "4h": "240"}
        bybit_interval = interval_map.get(interval, "60")
        
        url = f"https://api.bybit.com/v5/market/kline?category=spot&symbol={symbol}&interval={bybit_interval}&limit={limit}"
        response = await self.client.get(url)
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
        """Evaluates logic for confirmed downtrend or caution (Async)."""
        df = await self.fetch_klines(symbol, timeframe, limit=60)
        if df is None or len(df) < 50:
            return "NORMAL"

        df['ema_50'] = df['close'].ewm(span=50, adjust=False).mean()
        curr = df.iloc[-1]
        prev1 = df.iloc[-2]
        prev2 = df.iloc[-3]

        # Conditions
        cond1 = ((curr['open'] - curr['close']) / curr['open']) * 100 > 3.0
        cond2 = (curr['close'] < prev1['close']) and (prev1['close'] < prev2['close'])
        cond3 = curr['close'] < curr['ema_50']

        hits = sum([cond1, cond2, cond3])
        if hits == 3: return "CONFIRMED_DOWNTREND"
        if hits > 0: return "CAUTION"
        return "NORMAL"

    async def evaluate_signal(self, signal: dict) -> dict:
        """Checks a signal against current macro state (Async)."""
        if self.current_state['last_updated'] is None:
            await self.update_macro_state()

        overall = self.current_state["overall"]
        if overall == "CONFIRMED_DOWNTREND":
            signal['status'] = "blocked_macro_downtrend"
            signal['reason'] = "Blocked by Agent-6: Confirmed market-wide sharp downtrend."
            signal['macro_caution'] = True
            logger.warning(f"[Agent-6] Blocked signal for {signal.get('token_symbol')} due to macro.")
        elif overall == "CAUTION":
            signal['macro_caution'] = True
            signal['reason'] = (signal.get('reason') or "") + " [MACRO CAUTION]"

        return signal

    async def analyze(self, agent_5_signal: dict) -> dict:
        """Compatibility method for ResearcherBot (Async)."""
        # ResearcherBot expects a status check or regime info
        if self.current_state['last_updated'] is None:
            await self.update_macro_state()
            
        overall = self.current_state["overall"]
        if overall == "CONFIRMED_DOWNTREND":
            return {
                "status": "MACRO_HOLD",
                "failure_reason": "Confirmed market-wide sharp downtrend",
                "market_regime": "bearish"
            }
            
        return {
            "status": "CLEAR",
            "market_regime": self.current_state.get("overall", "mixed").lower()
        }
