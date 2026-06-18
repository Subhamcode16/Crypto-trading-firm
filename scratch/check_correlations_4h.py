import sqlite3
import pandas as pd
import numpy as np
import warnings
from ml_engine.features.feature_builder import FeatureBuilder

warnings.filterwarnings('ignore')

DIRECTIONAL_FEATURES = [
    'rsi_slope_10',
    'price_acceleration',
    'body_persistence_10',
    'return_asymmetry_10',
    'macd_hist_slope',
    'price_vs_20h_low',
    'price_vs_20h_high',
    'price_vs_50h_low',
    'price_vs_50h_high',
]

def run_4h_feasibility():
    print("Loading 1H data to resample to 4H...")
    conn = sqlite3.connect('ml_engine/data/store/cryptobot.db')
    df = pd.read_sql("SELECT * FROM ohlcv WHERE symbol='BTC/USDT' AND timeframe='1h' ORDER BY open_time", conn)
    
    # Preprocess
    df['open_time'] = pd.to_datetime(df['open_time'], utc=True)
    df = df.set_index('open_time')
    
    print("Resampling to 4H...")
    df_4h = df.resample('4h').agg({
        'symbol': 'first',
        'open': 'first',
        'high': 'max',
        'low': 'min',
        'close': 'last',
        'volume': 'sum',
        'quote_volume': 'sum',
        'num_trades': 'sum'
    }).dropna()
    df_4h['timeframe'] = '4h'
    print(f"Resampled to {len(df_4h)} 4H bars.")
    
    print("Building features...")
    fb = FeatureBuilder()
    # We can just run the builder natively on the 4H df
    df_4h_feat = fb.build_dataset(df_4h.copy())
    
    # 3-bar forward horizon for 4H data (12 hours)
    horizon = 3
    future_return_4h = df_4h_feat['close'].shift(-horizon) / df_4h_feat['close'] - 1
    
    print("\n--- Feature Correlation with 4H future_return (horizon=3) ---")
    results = {}
    for col in DIRECTIONAL_FEATURES:
        if col in df_4h_feat.columns:
            corr = df_4h_feat[col].corr(future_return_4h)
            results[col] = corr
        else:
            print(f"WARNING: {col} not found in built features!")
            
    # Sort by absolute correlation
    sorted_res = sorted(results.items(), key=lambda x: abs(x[1]) if not np.isnan(x[1]) else 0, reverse=True)
    
    for k, v in sorted_res:
        print(f"{k:<20}: {v:.4f}")

if __name__ == "__main__":
    run_4h_feasibility()
