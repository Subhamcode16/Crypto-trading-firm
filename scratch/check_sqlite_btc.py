import sqlite3
import pandas as pd

conn = sqlite3.connect('ml_engine/data/store/cryptobot.db')
df = pd.read_sql_query("SELECT symbol, timeframe, open_time FROM ohlcv WHERE symbol='BTC/USDT' AND timeframe='1h' AND open_time LIKE '2024-12-31%'", conn)
print("String value counts:")
print(df['open_time'].value_counts().head(5))

df['parsed'] = pd.to_datetime(df['open_time'], utc=True, format='mixed')
print("\nParsed value counts:")
print(df['parsed'].value_counts().head(5))

# check entire 2024 for BTC/USDT 1h
df_all = pd.read_sql_query("SELECT symbol, timeframe, open_time FROM ohlcv WHERE symbol='BTC/USDT' AND timeframe='1h' AND open_time >= '2024-01-01'", conn)
print(f"\nTotal rows in 2024+: {len(df_all)}")
df_all['parsed'] = pd.to_datetime(df_all['open_time'], utc=True, format='mixed')
print(f"Total unique parsed in 2024+: {df_all['parsed'].nunique()}")
print("Parsed value counts all 2024+:")
print(df_all['parsed'].value_counts().head(5))

