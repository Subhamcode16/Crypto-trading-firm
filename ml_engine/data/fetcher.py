"""
ml_engine/data/fetcher.py
─────────────────────────
Historical + incremental OHLCV data fetchers.

Sources:
  1. BinanceFetcher  — REST API, no auth needed, BTC/ETH/SOL OHLCV
  2. CoinGeckoFetcher — market cap, dominance, Fear & Greed proxy
  3. MacroFetcher    — VIX, DXY, SPY via yfinance (offline-friendly)
  4. FearGreedFetcher — Alternative.me daily Fear & Greed index

Usage:
  fetcher = BinanceFetcher()
  df = await fetcher.fetch_ohlcv("BTC/USDT", "1h", since="2021-01-01")
"""

import asyncio
import logging
import time
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Optional, Tuple

import aiohttp
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)

# ─── Constants ─────────────────────────────────────────────────────────────
BINANCE_BASE  = "https://api.binance.com/api/v3"
COINGECKO_BASE = "https://api.coingecko.com/api/v3"
FEAR_GREED_URL = "https://api.alternative.me/fng/"

BINANCE_LIMIT  = 1000   # max candles per request
RATE_LIMIT_DELAY = 0.25  # 250ms between requests (safe for public endpoints)

TIMEFRAME_MAP = {
    "1m":  "1m",  "3m":  "3m",  "5m": "5m",
    "15m": "15m", "30m": "30m", "1h": "1h",
    "2h":  "2h",  "4h":  "4h",  "6h": "6h",
    "8h":  "8h",  "12h": "12h", "1d": "1d",
    "3d":  "3d",  "1w":  "1w",
}

TIMEFRAME_MS = {
    "1m": 60_000, "5m": 300_000, "15m": 900_000,
    "1h": 3_600_000, "4h": 14_400_000, "1d": 86_400_000,
}

DEFAULT_SYMBOLS = ["BTC/USDT", "ETH/USDT", "SOL/USDT"]
BINANCE_SYMBOL_MAP = {s: s.replace("/", "") for s in DEFAULT_SYMBOLS}


class BinanceFetcher:
    """
    Fetches OHLCV candlestick data from Binance public REST API.
    No API key required for historical OHLCV.
    Handles pagination automatically for multi-year fetches.
    """

    def __init__(self, session: Optional[aiohttp.ClientSession] = None):
        self._session = session
        self._owns_session = session is None

    async def __aenter__(self):
        if self._owns_session:
            self._session = aiohttp.ClientSession(
                headers={"User-Agent": "ML-CryptoBot/2.0"}
            )
        return self

    async def __aexit__(self, *args):
        if self._owns_session and self._session:
            await self._session.close()

    def _symbol_to_binance(self, symbol: str) -> str:
        """Convert 'BTC/USDT' → 'BTCUSDT'"""
        return symbol.replace("/", "").upper()

    def _parse_timestamp(self, ts: str | datetime) -> int:
        """Convert date string or datetime to millisecond Unix timestamp."""
        if isinstance(ts, str):
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
        elif isinstance(ts, datetime):
            dt = ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)
        else:
            raise ValueError(f"Invalid timestamp: {ts}")
        return int(dt.timestamp() * 1000)

    async def _get(self, endpoint: str, params: dict) -> list | dict:
        """Make a GET request with retry logic and US fallback."""
        base_urls = [BINANCE_BASE, "https://api.binance.us/api/v3"]
        
        for url_base in base_urls:
            url = f"{url_base}{endpoint}"
            for attempt in range(3):
                try:
                    async with self._session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                        if resp.status == 451:
                            logger.warning(f"[Binance] 451 Legal Block on {url_base}, switching to fallback...")
                            break # Break the attempt loop and try the next base_url
                        if resp.status == 429:
                            wait = int(resp.headers.get("Retry-After", 60))
                            logger.warning(f"[Binance] Rate limited, waiting {wait}s")
                            await asyncio.sleep(wait)
                            continue
                        resp.raise_for_status()
                        return await resp.json()
                except aiohttp.ClientError as e:
                    logger.warning(f"[Binance] Request failed (attempt {attempt+1}/3): {e}")
                    await asyncio.sleep(2 ** attempt)
            
            # If we broke out of the attempt loop due to 451, the outer loop will try the next url_base
        
        raise RuntimeError(f"[Binance] All retry attempts and fallbacks failed for {endpoint}")

    def _klines_to_df(self, klines: list, symbol: str, timeframe: str) -> pd.DataFrame:
        """Convert raw Binance klines list to a clean DataFrame."""
        if not klines:
            return pd.DataFrame()
        df = pd.DataFrame(klines, columns=[
            "open_time", "open", "high", "low", "close", "volume",
            "close_time", "quote_volume", "num_trades",
            "taker_buy_base", "taker_buy_quote", "_ignore"
        ])
        df.drop(columns=["_ignore"], inplace=True)
        # Convert types
        df["open_time"]  = pd.to_datetime(df["open_time"],  unit="ms", utc=True)
        df["close_time"] = pd.to_datetime(df["close_time"], unit="ms", utc=True)
        for col in ["open", "high", "low", "close", "volume",
                    "quote_volume", "taker_buy_base", "taker_buy_quote"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        df["num_trades"] = df["num_trades"].astype(int)
        df["symbol"]     = symbol
        df["timeframe"]  = timeframe
        df.sort_values("open_time", inplace=True)
        df.reset_index(drop=True, inplace=True)
        return df

    async def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str = "1h",
        since: Optional[str | datetime] = None,
        until: Optional[str | datetime] = None,
        progress: bool = True,
    ) -> pd.DataFrame:
        """
        Fetch full OHLCV history for a symbol/timeframe.
        Handles Binance's 1000-candle limit by paginating automatically.

        Args:
            symbol:    e.g. "BTC/USDT"
            timeframe: e.g. "1h", "4h", "1d"
            since:     Start datetime (default: 3 years ago)
            until:     End datetime (default: now)
            progress:  Log progress for long fetches

        Returns:
            pd.DataFrame with columns: open_time, open, high, low, close, volume, ...
        """
        if timeframe not in TIMEFRAME_MAP:
            raise ValueError(f"Unknown timeframe: {timeframe}. Valid: {list(TIMEFRAME_MAP)}")

        binance_symbol = self._symbol_to_binance(symbol)
        now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)

        if since is None:
            # Default: 3 years back
            three_years_ago = datetime.now(timezone.utc) - timedelta(days=365 * 3)
            start_ms = int(three_years_ago.timestamp() * 1000)
        else:
            start_ms = self._parse_timestamp(since)

        end_ms = self._parse_timestamp(until) if until else now_ms

        all_dfs = []
        current_ms = start_ms
        tf_ms = TIMEFRAME_MS.get(timeframe, 3_600_000)
        total_expected = (end_ms - start_ms) // tf_ms
        fetched = 0

        logger.info(f"[Binance] Fetching {symbol} {timeframe} | "
                    f"~{total_expected:,} bars expected")

        while current_ms < end_ms:
            params = {
                "symbol":    binance_symbol,
                "interval":  TIMEFRAME_MAP[timeframe],
                "startTime": current_ms,
                "endTime":   min(current_ms + (BINANCE_LIMIT * tf_ms), end_ms),
                "limit":     BINANCE_LIMIT,
            }

            raw = await self._get("/klines", params)
            if not raw:
                break

            df = self._klines_to_df(raw, symbol, timeframe)
            all_dfs.append(df)
            fetched += len(df)

            # Advance pointer past last fetched bar
            last_open_ms = int(df["open_time"].iloc[-1].timestamp() * 1000)
            current_ms = last_open_ms + tf_ms

            if progress:
                pct = min(100, fetched * 100 // max(1, total_expected))
                logger.info(f"[Binance] {symbol} {timeframe} — {fetched:,}/{total_expected:,} bars ({pct}%)")

            await asyncio.sleep(RATE_LIMIT_DELAY)

        if not all_dfs:
            logger.warning(f"[Binance] No data returned for {symbol} {timeframe}")
            return pd.DataFrame()

        result = pd.concat(all_dfs, ignore_index=True)
        result.drop_duplicates(subset=["open_time"], inplace=True)
        result.sort_values("open_time", inplace=True)
        result.reset_index(drop=True, inplace=True)

        logger.info(f"[Binance] ✅ {symbol} {timeframe}: {len(result):,} bars fetched "
                    f"({result['open_time'].iloc[0].date()} → {result['open_time'].iloc[-1].date()})")
        return result

    async def fetch_latest(
        self,
        symbol: str,
        timeframe: str = "1h",
        last_n: int = 500,
    ) -> pd.DataFrame:
        """
        Fetch only the most recent N candles (for live updates).
        Much faster than full fetch.
        """
        binance_symbol = self._symbol_to_binance(symbol)
        params = {
            "symbol":   binance_symbol,
            "interval": TIMEFRAME_MAP[timeframe],
            "limit":    min(last_n, BINANCE_LIMIT),
        }
        raw = await self._get("/klines", params)
        return self._klines_to_df(raw, symbol, timeframe)

    async def get_server_time(self) -> datetime:
        """Get Binance server time (useful for sync checks)."""
        data = await self._get("/time", {})
        return datetime.fromtimestamp(data["serverTime"] / 1000, tz=timezone.utc)


class CoinGeckoFetcher:
    """
    Fetches market metadata from CoinGecko free API.
    No API key required. Rate limit: 50 calls/min.
    """
    COIN_MAP = {
        "BTC/USDT": "bitcoin",
        "ETH/USDT": "ethereum",
        "SOL/USDT": "solana",
    }

    def __init__(self):
        self._session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self):
        self._session = aiohttp.ClientSession(
            headers={"User-Agent": "ML-CryptoBot/2.0"}
        )
        return self

    async def __aexit__(self, *args):
        if self._session:
            await self._session.close()

    async def _get(self, endpoint: str, params: dict = {}) -> dict:
        url = f"{COINGECKO_BASE}{endpoint}"
        for attempt in range(3):
            try:
                async with self._session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=20)) as resp:
                    if resp.status == 429:
                        logger.warning("[CoinGecko] Rate limited, waiting 60s")
                        await asyncio.sleep(60)
                        continue
                    resp.raise_for_status()
                    return await resp.json()
            except Exception as e:
                logger.warning(f"[CoinGecko] Error (attempt {attempt+1}): {e}")
                await asyncio.sleep(2 ** attempt)
        return {}

    async def get_global_metrics(self) -> Dict:
        """
        Fetch global crypto market stats:
        - BTC dominance
        - Total market cap
        - ETH dominance
        """
        data = await self._get("/global")
        gd = data.get("data", {})
        return {
            "btc_dominance":     round(gd.get("market_cap_percentage", {}).get("btc", 0), 3),
            "eth_dominance":     round(gd.get("market_cap_percentage", {}).get("eth", 0), 3),
            "total_market_cap":  gd.get("total_market_cap", {}).get("usd", 0),
            "total_volume_24h":  gd.get("total_volume", {}).get("usd", 0),
            "active_cryptos":    gd.get("active_cryptocurrencies", 0),
            "recorded_at":       datetime.now(timezone.utc).isoformat(),
        }

    async def get_coin_history(
        self,
        symbol: str,
        days: int = 365,
    ) -> pd.DataFrame:
        """
        Fetch daily OHLCV history from CoinGecko (up to 365 days for free tier).
        Returns DataFrame with date, open, high, low, close, volume columns.
        """
        coin_id = self.COIN_MAP.get(symbol)
        if not coin_id:
            raise ValueError(f"Unknown symbol for CoinGecko: {symbol}")

        data = await self._get(
            f"/coins/{coin_id}/ohlc",
            params={"vs_currency": "usd", "days": str(days)}
        )
        if not data:
            return pd.DataFrame()

        df = pd.DataFrame(data, columns=["timestamp", "open", "high", "low", "close"])
        df["open_time"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
        df["symbol"]    = symbol
        df["timeframe"] = "1d"
        df["volume"]    = 0  # CoinGecko OHLC endpoint doesn't include volume
        df.drop(columns=["timestamp"], inplace=True)
        return df


class FearGreedFetcher:
    """
    Fetches the Crypto Fear & Greed Index from alternative.me.
    Free, no API key. Updates daily.
    """

    async def get_current(self) -> Dict:
        """Get today's Fear & Greed value."""
        async with aiohttp.ClientSession() as session:
            async with session.get(
                FEAR_GREED_URL,
                params={"limit": 1},
                timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                data = await resp.json()

        entry = data.get("data", [{}])[0]
        return {
            "value":       int(entry.get("value", 50)),
            "label":       entry.get("value_classification", "Neutral"),
            "timestamp":   datetime.fromtimestamp(int(entry.get("timestamp", 0)), tz=timezone.utc),
            "recorded_at": datetime.now(timezone.utc).isoformat(),
        }

    async def get_history(self, days: int = 365) -> pd.DataFrame:
        """Get Fear & Greed history as DataFrame."""
        async with aiohttp.ClientSession() as session:
            async with session.get(
                FEAR_GREED_URL,
                params={"limit": days, "format": "json"},
                timeout=aiohttp.ClientTimeout(total=30)
            ) as resp:
                data = await resp.json()

        rows = [
            {
                "date":  datetime.fromtimestamp(int(d["timestamp"]), tz=timezone.utc),
                "value": int(d["value"]),
                "label": d["value_classification"],
            }
            for d in data.get("data", [])
        ]
        df = pd.DataFrame(rows)
        if not df.empty:
            df.sort_values("date", inplace=True)
            df.reset_index(drop=True, inplace=True)
        return df


class MacroFetcher:
    """
    Fetches macro indicators using yfinance (no API key needed).
    Downloads: VIX (^VIX), DXY (DX-Y.NYB), SPY
    """

    VIX_TICKER = "^VIX"
    DXY_TICKER = "DX-Y.NYB"
    SPY_TICKER = "SPY"
    TNX_TICKER = "^TNX"

    def __init__(self):
        self._cache = None
        self._last_fetch = None

    def fetch_macro_data(
        self,
        start: str = "2020-01-01",
        end: Optional[str] = None,
    ) -> pd.DataFrame:
        """
        Fetch VIX, DXY, SPY daily close prices.
        Runs synchronously (yfinance is sync-only).

        Returns:
            DataFrame with columns: date, vix, dxy, spy_close
        """
        try:
            import yfinance as yf
        except ImportError:
            logger.error("[Macro] yfinance not installed. Run: pip install yfinance")
            return pd.DataFrame()

        now = datetime.now()
        if self._cache is not None and self._last_fetch is not None:
            if (now - self._last_fetch).total_seconds() < 3600:
                return self._cache.copy()

        if end is None:
            end = now.strftime("%Y-%m-%d")

        tickers = {
            "vix":       self.VIX_TICKER,
            "dxy":       self.DXY_TICKER,
            "spy_close": self.SPY_TICKER,
            "tnx":       self.TNX_TICKER,
        }

        # yfinance handles Cloudflare on its own natively.
        session = None
            
        result_df = None
        for col_name, ticker in tickers.items():
            try:
                data = yf.download(ticker, period="730d", progress=False, session=session)
                # Handle yfinance returning MultiIndex columns
                if isinstance(data.columns, pd.MultiIndex):
                    series = data["Close"][ticker].rename(col_name)
                else:
                    series = data["Close"].rename(col_name)
                    
                if result_df is None:
                    result_df = series.to_frame()
                else:
                    result_df = result_df.join(series, how="outer")
                logger.info(f"[Macro] ✅ {ticker}: {len(series)} days fetched")
            except Exception as e:
                import traceback
                logger.warning(f"[Macro] Failed to fetch {ticker}: {e}")
                logger.warning(traceback.format_exc())

        if result_df is None:
            return pd.DataFrame()

        result_df.index.name = "date"
        result_df.reset_index(inplace=True)
        result_df["date"] = pd.to_datetime(result_df["date"], utc=True)
        result_df.ffill(inplace=True)
        
        self._cache = result_df.copy()
        self._last_fetch = datetime.now()
        
        return result_df


# ─── Convenience async runner ───────────────────────────────────────────────
async def fetch_all_symbols_ohlcv(
    symbols: List[str] = DEFAULT_SYMBOLS,
    timeframes: List[str] = ["1h", "4h", "1d"],
    since: str = "2021-01-01",
) -> Dict[str, Dict[str, pd.DataFrame]]:
    """
    Convenience: fetch OHLCV for all symbols and timeframes in parallel.

    Returns:
        {symbol: {timeframe: DataFrame}}
    """
    results = {}
    async with BinanceFetcher() as fetcher:
        for symbol in symbols:
            results[symbol] = {}
            for tf in timeframes:
                logger.info(f"[Pipeline] Fetching {symbol} {tf}...")
                df = await fetcher.fetch_ohlcv(symbol, tf, since=since)
                results[symbol][tf] = df
                await asyncio.sleep(0.5)  # polite gap between timeframes
    return results


if __name__ == "__main__":
    import sys
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        stream=sys.stdout
    )

    async def _smoke_test():
        print("=" * 60)
        print("FETCHER SMOKE TEST")
        print("=" * 60)

        # Test Binance
        async with BinanceFetcher() as f:
            df = await f.fetch_ohlcv("BTC/USDT", "1d", since="2024-01-01")
            print(f"\n[Binance] BTC/USDT 1d: {len(df)} bars")
            print(df.tail(3).to_string())

        # Test Fear & Greed
        fg = FearGreedFetcher()
        fgi = await fg.get_current()
        print(f"\n[F&G] Current: {fgi['value']} ({fgi['label']})")

        # Test CoinGecko
        async with CoinGeckoFetcher() as cg:
            gm = await cg.get_global_metrics()
            print(f"\n[CoinGecko] BTC Dominance: {gm['btc_dominance']}%")

    asyncio.run(_smoke_test())
