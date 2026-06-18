import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import pandas as pd
import numpy as np
from ml_engine.data.pipeline import DataPipeline
from ml_engine.features.feature_builder import FeatureBuilder

def check_step3_and_4():
    print("Loading data for Step 3...")
    pipeline = DataPipeline()
    df_1h = pipeline.storage.load_ohlcv("BTC/USDT", "1h", since="2025-01-01", until="2026-01-01")
    fb = FeatureBuilder()
    df_feat = fb.build_dataset(df_1h, dropna=False)
    
    # Simulate generate_labels logic
    df = df_feat.copy()
    horizon = 8
    df["future_close"] = df["close"].shift(-horizon)
    df["future_return"] = (df["future_close"] - df["close"]) / df["close"]
    
    # Recreate ATR threshold logic
    # In XGBModel:
    # tr = np.maximum(df['high'] - df['low'], np.abs(df['high'] - df['close'].shift()), np.abs(df['low'] - df['close'].shift()))
    # atr = tr.rolling(14).mean()
    # atr_pct = atr / df['close']
    # strong_thresh = 1.5 * atr_pct
    
    tr = pd.concat([
        df['high'] - df['low'],
        (df['high'] - df['close'].shift()).abs(),
        (df['low'] - df['close'].shift()).abs()
    ], axis=1).max(axis=1)
    atr = tr.rolling(14).mean()
    atr_pct = atr / df['close']
    strong_thresh = 1.5 * atr_pct
    
    df["strong_thresh"] = strong_thresh
    
    # Recreate label mapping
    df['label'] = 0
    df.loc[df["future_return"] > strong_thresh, "label"] = 1   # LONG
    df.loc[df["future_return"] < -strong_thresh, "label"] = -1 # SHORT
    
    # For STRONG_LONG
    long_rows = df[df["label"] == 1]
    if len(long_rows) > 0:
        low_thresh_long = long_rows[long_rows["strong_thresh"] < 0.002]
        pct_long = len(low_thresh_long) / len(long_rows) * 100
        print(f"Step 3: {pct_long:.2f}% of STRONG_LONG labels have threshold < 0.2% ({len(low_thresh_long)} / {len(long_rows)})")
    else:
        print("Step 3: No STRONG_LONG labels found.")
        
    short_rows = df[df["label"] == -1]
    if len(short_rows) > 0:
        low_thresh_short = short_rows[short_rows["strong_thresh"] < 0.002]
        pct_short = len(low_thresh_short) / len(short_rows) * 100
        print(f"Step 3: {pct_short:.2f}% of STRONG_SHORT labels have threshold < 0.2% ({len(low_thresh_short)} / {len(short_rows)})")
        
    print("\nStep 4: Checking scaler logic...")
    print("Scanning xgb_model.py and feature_builder.py for 'scaler' or 'MinMaxScaler' or 'StandardScaler'...")
    xgb_model_path = os.path.join(os.path.dirname(__file__), '..', 'ml_engine', 'models', 'xgb_model.py')
    with open(xgb_model_path, 'r') as f:
        xgb_content = f.read()
    if 'scaler' in xgb_content.lower():
        print("Found scaler in xgb_model.py!")
    else:
        print("No scaler found in xgb_model.py. XGBoost does not use feature scaling natively.")

if __name__ == "__main__":
    check_step3_and_4()
