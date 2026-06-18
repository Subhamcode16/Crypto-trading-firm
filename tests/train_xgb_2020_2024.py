import sys, os, asyncio
import pandas as pd

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from ml_engine.data.fetcher import BinanceFetcher
from ml_engine.features.feature_builder import FeatureBuilder
from ml_engine.models.xgb_model import XGBTrainer

async def run_training():
    print("="*60)
    print("  XGBOOST RETRAINING (2020-2024 Multi-Regime Data)")
    print("="*60)
    print("Fetching 5-year BTC/USDT 1H data (2020-2024)...")
    
    from ml_engine.data.pipeline import DataPipeline
    since = "2020-01-01"
    until = "2025-01-01"
    df_1h = DataPipeline().storage.load_ohlcv("BTC/USDT", "1h", since=since, until=until)
    
    if 'index' in df_1h.columns and 'timestamp' not in df_1h.columns:
        df_1h = df_1h.rename(columns={'index': 'timestamp'})
        
    print(f"Loaded {len(df_1h)} 1H candles.")
    
    print("Building XGBoost Features...")
    fb = FeatureBuilder()
    df_feat = fb.build_dataset(df_1h, dropna=False)
    
    print("Training model with class_weight='balanced'...")
    trainer = XGBTrainer(symbol="BTC/USDT", timeframe="1h")
    import numpy as np
    numeric_cols = df_feat.select_dtypes(include=[np.number]).columns.tolist()
    feature_names = [c for c in numeric_cols if c not in ["timestamp", "open_time", "open", "high", "low", "close", "volume", "label"]]
    model, report = trainer.train(df_feat, feature_names, use_optuna=False, retrain=True)
    
    print("\nTraining Complete.")
    print("Report:", report)

if __name__ == "__main__":
    asyncio.run(run_training())
