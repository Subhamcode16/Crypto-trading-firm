import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import pandas as pd
import numpy as np
from ml_engine.data.pipeline import DataPipeline
from ml_engine.features.feature_builder import FeatureBuilder

def check_leakage():
    print("Loading data...")
    pipeline = DataPipeline()
    df_1h = pipeline.storage.load_ohlcv("BTC/USDT", "1h", since="2025-01-01", until="2026-01-01")
    fb = FeatureBuilder()
    df_feat = fb.build_dataset(df_1h, dropna=False)

    print(f"Data shape: {df_feat.shape}")
    
    # Calculate past 8h return and future 8h return
    df_feat['past_ret_8'] = df_feat['close'].pct_change(8)
    df_feat['future_ret_8'] = df_feat['close'].shift(-8) / df_feat['close'] - 1

    df_clean = df_feat.replace([np.inf, -np.inf], np.nan).dropna()

    exclude_cols = ['timestamp', 'open_time', 'open', 'high', 'low', 'close', 'volume', 'past_ret_8', 'future_ret_8', 'label']
    features = [c for c in df_clean.columns if c not in exclude_cols]

    print(f"Checking {len(features)} features for leakage...")
    
    leaky_features = []
    for f in features:
        corr_past = abs(df_clean[f].corr(df_clean['past_ret_8']))
        corr_fut = abs(df_clean[f].corr(df_clean['future_ret_8']))
        if pd.isna(corr_past) or pd.isna(corr_fut):
            continue
        if corr_past > 0.0001:
            ratio = corr_fut / corr_past
            if ratio > 1.5 and corr_fut > 0.05: # Add minimum absolute correlation to avoid noise
                leaky_features.append((f, ratio, corr_fut, corr_past))
        elif corr_fut > 0.05:
            # If past correlation is basically 0 but future is high, it's definitely leaky
            leaky_features.append((f, float('inf'), corr_fut, corr_past))

    print("\n=== LEAKAGE CHECK RESULTS ===")
    if not leaky_features:
        print("No features with leakage ratio > 1.5 (and meaningful future correlation > 0.05) found.")
    else:
        leaky_features.sort(key=lambda x: -x[1])
        for f, ratio, cf, cp in leaky_features:
            print(f"Feature: {f:<20} | Ratio: {ratio:>6.2f} | Future Corr: {cf:.4f} | Past Corr: {cp:.4f}")

if __name__ == "__main__":
    check_leakage()
