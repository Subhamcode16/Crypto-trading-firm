import sys
import os
import asyncio
from collections import Counter
import pandas as pd

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from ml_engine.data.fetcher import BinanceFetcher
from ml_engine.features.regime_detector import RegimeDetector

async def test_regime_distribution():
    print("Fetching 90 days of historical data...")
    async with BinanceFetcher() as fetcher:
        # 90 days ago
        since_date = (pd.Timestamp.utcnow() - pd.Timedelta(days=90)).strftime("%Y-%m-%d")
        
        df_1h = await fetcher.fetch_ohlcv("BTC/USDT", "1h", since=since_date)
        df_4h = await fetcher.fetch_ohlcv("BTC/USDT", "4h", since=since_date)
        
    print(f"Fetched {len(df_1h)} 1H candles and {len(df_4h)} 4H candles.")
    
    detector = RegimeDetector()
    distribution = Counter()
    
    print("Running regime detector over history...")
    # Start from index 200 to have enough history for BB Percentile
    for i in range(200, len(df_1h)):
        current_1h = df_1h.iloc[:i+1]
        current_time = current_1h.iloc[-1]['open_time']
        
        # Get 4H data up to this time
        current_4h = df_4h[df_4h['open_time'] <= current_time]
        
        result = detector.detect(current_1h, current_4h, signal_direction="LONG")
        distribution[result['regime']] += 1
        
        if i % 500 == 0:
            print(f"Processed {i}/{len(df_1h)} candles...")
            
    total = sum(distribution.values())
    print("\nRegime Distribution (90 Days, SIGNAL=LONG):")
    for regime, count in distribution.most_common():
        pct = (count / total) * 100
        print(f"{regime.ljust(25)}: {pct:.1f}% ({count} hours)")
        
    # Also test for NEUTRAL signal to see base regime without trend conflict rejection
    print("\nRegime Distribution (90 Days, SIGNAL=NEUTRAL):")
    distribution_neutral = Counter()
    for i in range(200, len(df_1h)):
        current_1h = df_1h.iloc[:i+1]
        current_time = current_1h.iloc[-1]['open_time']
        current_4h = df_4h[df_4h['open_time'] <= current_time]
        
        result = detector.detect(current_1h, current_4h, signal_direction="NEUTRAL")
        distribution_neutral[result['regime']] += 1
        
    total_neutral = sum(distribution_neutral.values())
    for regime, count in distribution_neutral.most_common():
        pct = (count / total_neutral) * 100
        print(f"{regime.ljust(25)}: {pct:.1f}% ({count} hours)")

if __name__ == "__main__":
    asyncio.run(test_regime_distribution())
