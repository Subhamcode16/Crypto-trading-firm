import sqlite3
import pandas as pd

conn = sqlite3.connect('ml_engine/data/store/cryptobot.db')
df = pd.read_sql_query("SELECT open_time FROM ohlcv WHERE open_time LIKE '2024-12-31%'", conn)
print(df['open_time'].value_counts().head(10))
print("\nUnique raw string examples:")
print(df['open_time'].unique()[:20])

# check string duplicates by looking at datetime parsing
df['parsed'] = pd.to_datetime(df['open_time'], utc=True, format="mixed")
print("\nDuplicates after pd.to_datetime():")
print(df['parsed'].value_counts().head(10))
