import sqlite3
import pandas as pd

def fix_database():
    print("Loading all OHLCV data from SQLite...")
    conn = sqlite3.connect('ml_engine/data/store/cryptobot.db')
    
    df = pd.read_sql_query("SELECT * FROM ohlcv", conn)
    print(f"Original rows: {len(df)}")
    
    # Parse datetimes to uniform format
    df['open_time'] = pd.to_datetime(df['open_time'], utc=True, format='mixed', errors='coerce').dt.strftime('%Y-%m-%d %H:%M:%S+00:00')
    df['close_time'] = pd.to_datetime(df['close_time'], utc=True, format='mixed', errors='coerce').dt.strftime('%Y-%m-%d %H:%M:%S+00:00')
    df = df.dropna(subset=['open_time'])
    
    # Sort and drop duplicates, keeping the last fetched (or first, doesn't matter if OHLCV are identical)
    df = df.sort_values(['symbol', 'timeframe', 'open_time'])
    df_dedup = df.drop_duplicates(subset=['symbol', 'timeframe', 'open_time'], keep='last')
    
    print(f"Deduplicated rows: {len(df_dedup)}")
    print(f"Dropped {len(df) - len(df_dedup)} duplicate rows.")
    
    # Write back to a temp table
    print("Writing back to database...")
    df_dedup.to_sql('ohlcv_temp', conn, if_exists='replace', index=False)
    
    # Execute table swap
    with conn:
        conn.execute("DROP TABLE ohlcv")
        conn.execute("""
            CREATE TABLE ohlcv (
                symbol    TEXT    NOT NULL,
                timeframe TEXT    NOT NULL,
                open_time TEXT    NOT NULL,
                open      REAL    NOT NULL,
                high      REAL    NOT NULL,
                low       REAL    NOT NULL,
                close     REAL    NOT NULL,
                volume    REAL    NOT NULL,
                close_time TEXT,
                quote_volume REAL DEFAULT 0,
                num_trades   INTEGER DEFAULT 0,
                taker_buy_base  REAL DEFAULT 0,
                taker_buy_quote REAL DEFAULT 0,
                PRIMARY KEY (symbol, timeframe, open_time)
            )
        """)
        conn.execute("""
            INSERT INTO ohlcv 
            SELECT symbol, timeframe, open_time, open, high, low, close, volume, close_time, quote_volume, num_trades, taker_buy_base, taker_buy_quote
            FROM ohlcv_temp
        """)
        conn.execute("DROP TABLE ohlcv_temp")
        
    print("Database deduplication complete.")

if __name__ == "__main__":
    fix_database()
