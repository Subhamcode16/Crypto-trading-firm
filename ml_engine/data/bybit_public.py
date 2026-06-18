"""
BybitPublicFetcher - Dedicated public market data client.

Talks ONLY to https://api.bybit.com (unauthenticated, mainnet).
This is completely separate from the Demo/Testnet private API,
so it NEVER triggers IP bans and NEVER needs API keys.

Key design decisions:
- Uses aiohttp directly (not CCXT) to avoid CCXT's load_markets() calls
- Exponential backoff on transient errors
- In-memory cache to limit requests to 1 per symbol per 30s
- Graceful degradation: returns None on failure, never raises
"""

import asyncio
import logging
import time
from typing import Optional
import aiohttp
import pandas as pd

logger = logging.getLogger(__name__)

# Bybit's PUBLIC mainnet REST API — no auth, no rate-limit bans
BYBIT_PUBLIC_BASE = "https://api.bybit.com"

# Category for linear perpetual futures (USDT-settled)
CATEGORY = "linear"

# Interval map: our internal timeframes → Bybit API interval strings
INTERVAL_MAP = {
    "1m": "1",
    "5m": "5",
    "15m": "15",
    "30m": "30",
    "1h": "60",
    "4h": "240",
    "1d": "D",
}

# Cache: symbol → (timestamp_fetched, DataFrame)
_ohlcv_cache: dict[str, tuple[float, pd.DataFrame]] = {}
_ticker_cache: dict[str, tuple[float, dict]] = {}

OHLCV_CACHE_TTL = 30   # seconds — refresh every 30s max
TICKER_CACHE_TTL = 10  # seconds — price ticks refresh faster


async def _get(session: aiohttp.ClientSession, url: str, params: dict, retries: int = 3) -> Optional[dict]:
    """
    HTTP GET with exponential backoff.
    Returns the parsed JSON body or None on persistent failure.
    """
    delay = 2.0
    for attempt in range(retries):
        try:
            async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data.get("retCode") == 0:
                        return data
                    else:
                        logger.warning(f"[BybitPublic] API error {data.get('retCode')}: {data.get('retMsg')} | URL: {url}")
                        return None
                elif resp.status == 429:
                    logger.warning(f"[BybitPublic] Rate limited (429). Backing off {delay:.0f}s…")
                    await asyncio.sleep(delay)
                    delay *= 2
                else:
                    logger.warning(f"[BybitPublic] HTTP {resp.status} from {url}")
                    return None
        except asyncio.TimeoutError:
            logger.warning(f"[BybitPublic] Timeout on attempt {attempt+1}/{retries} for {url}")
            await asyncio.sleep(delay)
            delay *= 2
        except aiohttp.ClientError as e:
            logger.warning(f"[BybitPublic] Connection error on attempt {attempt+1}/{retries}: {e}")
            await asyncio.sleep(delay)
            delay *= 2
        except Exception as e:
            logger.error(f"[BybitPublic] Unexpected error: {e}")
            return None

    logger.error(f"[BybitPublic] All {retries} attempts failed for {url}")
    return None


async def fetch_ohlcv(symbol: str, timeframe: str = "1h", limit: int = 360) -> Optional[pd.DataFrame]:
    """
    Fetch OHLCV candles for a futures symbol from Bybit's public mainnet.
    
    Args:
        symbol: CCXT-style symbol like "BTC/USDT" or "BTC/USDT:USDT"
        timeframe: e.g. "1h", "15m", "1d"
        limit: number of candles (max 1000 per Bybit docs)
        
    Returns:
        DataFrame with columns [timestamp, open, high, low, close, volume]
        or None if the request fails.
    """
    # Normalise CCXT-style symbols to Bybit API style (BTCUSDT)
    base_symbol = symbol.replace("/USDT:USDT", "USDT").replace("/USDT", "USDT").replace("/", "")

    cache_key = f"{base_symbol}_{timeframe}_{limit}"
    now = time.time()
    if cache_key in _ohlcv_cache:
        ts, df = _ohlcv_cache[cache_key]
        if now - ts < OHLCV_CACHE_TTL:
            return df

    interval = INTERVAL_MAP.get(timeframe, "60")
    url = f"{BYBIT_PUBLIC_BASE}/v5/market/kline"
    params = {
        "category": CATEGORY,
        "symbol": base_symbol,
        "interval": interval,
        "limit": min(limit, 1000),
    }

    async with aiohttp.ClientSession() as session:
        data = await _get(session, url, params)

    if not data:
        # Return cached stale data rather than None if available
        if cache_key in _ohlcv_cache:
            logger.warning(f"[BybitPublic] Returning stale OHLCV cache for {symbol}")
            return _ohlcv_cache[cache_key][1]
        return None

    raw = data.get("result", {}).get("list", [])
    if not raw:
        return None

    # Bybit returns: [startTime, open, high, low, close, volume, turnover] (newest first)
    rows = []
    for r in reversed(raw):
        rows.append({
            "timestamp": pd.to_datetime(int(r[0]), unit="ms", utc=True),
            "open": float(r[1]),
            "high": float(r[2]),
            "low": float(r[3]),
            "close": float(r[4]),
            "volume": float(r[5]),
        })

    df = pd.DataFrame(rows)
    _ohlcv_cache[cache_key] = (now, df)
    return df


async def fetch_ticker(symbol: str) -> Optional[dict]:
    """
    Fetch the latest ticker (last price, bid, ask, volume) from Bybit public mainnet.
    
    Returns:
        dict with keys: symbol, last, bid, ask, volume or None on failure.
    """
    base_symbol = symbol.replace("/USDT:USDT", "USDT").replace("/USDT", "USDT").replace("/", "")

    now = time.time()
    if base_symbol in _ticker_cache:
        ts, ticker = _ticker_cache[base_symbol]
        if now - ts < TICKER_CACHE_TTL:
            return ticker

    url = f"{BYBIT_PUBLIC_BASE}/v5/market/tickers"
    params = {"category": CATEGORY, "symbol": base_symbol}

    async with aiohttp.ClientSession() as session:
        data = await _get(session, url, params)

    if not data:
        if base_symbol in _ticker_cache:
            logger.warning(f"[BybitPublic] Returning stale ticker cache for {symbol}")
            return _ticker_cache[base_symbol][1]
        return None

    items = data.get("result", {}).get("list", [])
    if not items:
        return None

    item = items[0]
    ticker = {
        "symbol": symbol,
        "last": float(item.get("lastPrice", 0)),
        "bid": float(item.get("bid1Price", 0)),
        "ask": float(item.get("ask1Price", 0)),
        "volume": float(item.get("volume24h", 0)),
        "change_pct": float(item.get("price24hPcnt", 0)),
    }
    _ticker_cache[base_symbol] = (now, ticker)
    return ticker


async def fetch_tickers(symbols: list[str]) -> dict[str, Optional[dict]]:
    """
    Fetch tickers for multiple symbols concurrently.
    Returns a dict of {symbol: ticker_dict_or_None}
    """
    tasks = {sym: fetch_ticker(sym) for sym in symbols}
    results = await asyncio.gather(*tasks.values(), return_exceptions=True)
    return {
        sym: (r if not isinstance(r, Exception) else None)
        for sym, r in zip(tasks.keys(), results)
    }
