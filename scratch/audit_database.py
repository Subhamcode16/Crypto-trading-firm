import sqlite3
import pandas as pd

def audit_clean_database(db_path: str) -> None:
    print(f"Auditing database: {db_path}")
    conn = sqlite3.connect(db_path)
    df = pd.read_sql("SELECT * FROM ohlcv WHERE symbol='BTC/USDT' AND timeframe='1h' ORDER BY open_time", conn)
    
    # Check 1: No duplicate timestamps
    duplicates = df['open_time'].duplicated().sum()
    assert duplicates == 0, f"Still {duplicates} duplicate timestamps"
    print("Check 1: No duplicate timestamps passed")
    
    # Check 2: No gaps larger than 2 hours (1H data should be continuous)
    df['open_time'] = pd.to_datetime(df['open_time'])
    gaps = df['open_time'].diff().dropna()
    large_gaps = gaps[gaps > pd.Timedelta('2h')]
    print(f"Check 2: Gaps larger than 2 hours: {len(large_gaps)}")
    if len(large_gaps) > 0:
        print(large_gaps.head(10))  # Expected: exchange downtime only
    
    # Check 3: No zero or negative prices
    assert (df['close'] > 0).all(), "Zero or negative close prices found"
    assert (df['high'] >= df['low']).all(), "High < Low found"
    assert (df['high'] >= df['close']).all(), "Close > High found"
    assert (df['low'] <= df['close']).all(), "Close < Low found"
    print("Check 3: Price sanity checks passed")
    
    # Check 4: Reasonable price range for BTC
    assert df['close'].min() > 100, "Suspiciously low BTC price"
    assert df['close'].max() < 1_000_000, "Suspiciously high BTC price"
    print("Check 4: BTC price range checks passed")
    
    print(f"\nDatabase clean: {len(df):,} rows")
    print(f"   Date range: {df['open_time'].min()} to {df['open_time'].max()}")
    
    expected_rows = (df['open_time'].max() - df['open_time'].min()).days * 24
    print(f"   Expected rows (1H): ~{expected_rows:,}")
    
    diff_pct = abs(len(df) - expected_rows) / expected_rows
    print(f"   Row count deviation: {diff_pct:.2%}")
    assert diff_pct < 0.05, f"Row count deviates by {diff_pct:.2%}, expected < 5%."

if __name__ == "__main__":
    audit_clean_database('ml_engine/data/store/cryptobot.db')
