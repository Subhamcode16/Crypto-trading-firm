import asyncio
import pandas as pd
import numpy as np
import time

from ml_engine.data.fetcher import BinanceFetcher
from ml_engine.features.regime_detector import RegimeDetector

async def main():
    print("Fetching 1-year BTC/USDT 1H data...")
    async with BinanceFetcher() as fetcher:
        since = (pd.Timestamp.now('UTC') - pd.Timedelta(days=365)).strftime("%Y-%m-%d")
        df = await fetcher.fetch_ohlcv("BTC/USDT", "1h", since=since)
    print(f"Loaded {len(df)} candles.")

    rd = RegimeDetector()
    
    # Needs to process one by one or vectorize?
    # Regime detector currently has `detect` which takes the full dataframe and index.
    print("Running Regime Detector over 1-year data...")
    regimes = []
    
    # Let's vectorize it since `detect` might be slow if called 8000 times
    # We can just compute adx, er, bb_width for the whole df
    df['adx'] = rd.compute_adx(df, 14)
    df['er']  = rd.compute_er(df, 14)
    
    sma20 = df['close'].rolling(20).mean()
    std20 = df['close'].rolling(20).std()
    bb_upper = sma20 + 2 * std20
    bb_lower = sma20 - 2 * std20
    df['bb_width'] = (bb_upper - bb_lower) / (sma20 + 1e-10)
    
    # We need to rank bb_width dynamically. A simple way is to use a rolling percentile or global.
    # The detect method uses the last 100 periods.
    # Let's just use rolling 100 rank
    df['bb_rank'] = df['bb_width'].rolling(100).apply(lambda x: pd.Series(x).rank(pct=True).iloc[-1])
    
    for i in range(len(df)):
        if i < 100 or pd.isna(df['adx'].iloc[i]):
            regimes.append("AMBIGUOUS")
            continue
            
        adx = df['adx'].iloc[i]
        er = df['er'].iloc[i]
        bb_rank = df['bb_rank'].iloc[i]
        
        is_trending = adx > 20 and er > 0.4
        is_volatile = bb_rank > 0.8
        is_squeeze = bb_rank < 0.2
        
        if is_trending and is_volatile:
            regimes.append("TRENDING")
        elif is_volatile and not is_trending:
            regimes.append("VOLATILE_CHOP")
        elif is_squeeze:
            regimes.append("SQUEEZE")
        elif adx < 20 and er < 0.4:
            regimes.append("RANGING")
        else:
            regimes.append("AMBIGUOUS")
            
    df['regime'] = regimes
    counts = df['regime'].value_counts()
    
    print("\nRegime Distribution:")
    for reg, cnt in counts.items():
        print(f"  {reg.ljust(15)}: {cnt:>5} bars  ({cnt/len(df)*100:.1f}%)")

if __name__ == "__main__":
    asyncio.run(main())
