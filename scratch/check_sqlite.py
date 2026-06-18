import sqlite3
import pandas as pd

conn = sqlite3.connect('ml_engine/data/store/cryptobot.db')
schema = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='ohlcv'").fetchone()[0]
print(f"SCHEMA:\n{schema}\n")

df = pd.read_sql_query("SELECT symbol, timeframe, open_time, COUNT(*) as cnt FROM ohlcv GROUP BY symbol, timeframe, open_time HAVING cnt > 1 LIMIT 5", conn)
print("DUPLICATE ROWS IN SQLITE:")
print(df)
