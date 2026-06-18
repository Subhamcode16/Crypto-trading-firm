import sqlite3
import pandas as pd
from ml_engine.features.feature_builder import FeatureBuilder

conn = sqlite3.connect('ml_engine/data/store/cryptobot.db')
df = pd.read_sql("SELECT * FROM ohlcv WHERE symbol='BTC/USDT' AND timeframe='1h' ORDER BY open_time", conn)
df['open_time'] = pd.to_datetime(df['open_time'], utc=True)
df.set_index('open_time', inplace=True)

fb = FeatureBuilder()
feats = fb.build_dataset(df, dropna=False)

print(f"Total rows: {len(feats)}")
for col in feats.columns:
    nan_count = feats[col].isna().sum()
    if nan_count > 0:
        print(f"{col}: {nan_count} NaNs")
