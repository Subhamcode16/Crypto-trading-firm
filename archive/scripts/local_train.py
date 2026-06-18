"""
local_train.py
─────────────────────────
Local CPU/GPU Training Script — ML Crypto Bot v2.0

Usage:
  python local_train.py
"""
import asyncio
import logging
from ml_engine.data.pipeline import DataPipeline
from ml_engine.features.feature_builder import FeatureBuilder
from ml_engine.models.lstm_trainer import LSTMTrainer
from ml_engine.models.xgb_model import XGBTrainer
from ml_engine.rl.rl_trainer import RLTrainer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("local_train")

async def main():
    print("\n" + "="*50)
    print("🚀 ML Crypto Bot v2.0 - Local CPU Training")
    print("="*50 + "\n")

    # 1. Bootstrap Data
    print("📥 Step 1: Bootstrapping historical data (Bypassing Binance DNS blocks via Yahoo Finance!)...")
    pipeline = DataPipeline()
    SYMBOLS = ["BTC/USDT", "ETH/USDT", "SOL/USDT"]
    TIMEFRAMES = ["1h", "4h"]
    
    # --- YFINANCE HOT-PATCH FOR LOCAL DNS ISSUES ---
    import yfinance as yf
    import pandas as pd
    yf_map = {"BTC/USDT": "BTC-USD", "ETH/USDT": "ETH-USD", "SOL/USDT": "SOL-USD"}
    
    for symbol in SYMBOLS:
        for tf in TIMEFRAMES:
            yf_sym = yf_map.get(symbol)
            df_raw = yf.download(yf_sym, period="730d", interval="1h", progress=False)
            if df_raw.empty: continue
            
            if isinstance(df_raw.columns, pd.MultiIndex):
                df_raw.columns = df_raw.columns.droplevel(1)
                
            df = df_raw.reset_index().rename(columns={
                "Datetime": "open_time", "Open": "open", "High": "high", 
                "Low": "low", "Close": "close", "Volume": "volume"
            })
            df["open_time"] = pd.to_datetime(df["open_time"], utc=True).astype(str)
            df["symbol"] = symbol
            df["timeframe"] = tf
            for c in ["quote_volume", "num_trades", "taker_buy_base", "taker_buy_quote", "close_time"]: df[c] = 0
            
            pipeline.storage.upsert_ohlcv(df)
            print(f"✅ Downloaded {len(df)} rows for {symbol} {tf} via Yahoo Finance.")
    # -----------------------------------------------
    
    fb = FeatureBuilder()
    sym = "BTC/USDT"
    tf = "1h"
    
    # 2. Extract Features
    print(f"\n🧠 Step 2: Extracting Features for {sym} {tf}...")
    df_raw = pipeline.get_training_data(sym, tf)
    if df_raw.empty:
        print("❌ No data found.")
        return
        
    df_feat = fb.build_dataset(df_raw, dropna=True)
    feat_names = fb.get_feature_columns(df_feat)
    print(f"Data shape: {df_feat.shape}")

    # 3. Train LSTM
    print(f"\n🤖 Step 3: Skipping LSTM Model (Colab models will be downloaded)...")
    # lstm = LSTMTrainer(symbol=sym, timeframe=tf)
    # metrics = lstm.train(retrain=True)
    # print(f"LSTM Metrics: {metrics}")

    # 4. Train XGBoost
    print(f"\n🌲 Step 4: Skipping XGBoost Model (Already trained)...")
    # xgb = XGBTrainer(symbol=sym, timeframe=tf)
    # Turn off Optuna to save time on CPU (1 min vs 2 hours)
    # model, report = xgb.train(df_feat, feat_names, use_optuna=False, retrain=True)
    # print(f"XGBoost Metrics: {report}")

    # 5. Train PPO (RL)
    print(f"\n🎮 Step 5: Training RL Model (PPO) ({sym} {tf})...")
    rl = RLTrainer(symbol=sym, timeframe=tf)
    metrics = rl.train(timesteps=250_000, retrain=True)
    print(f"RL Metrics: {metrics}")

    print("\n✅ Local Training Complete!")
    print("Models saved successfully in: ml_engine/models/saved/")

if __name__ == "__main__":
    asyncio.run(main())
