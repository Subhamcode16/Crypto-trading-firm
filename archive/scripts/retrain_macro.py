import asyncio
import logging
from ml_engine.data.pipeline import DataPipeline
from ml_engine.data.fetcher import MacroFetcher
from ml_engine.features.feature_builder import FeatureBuilder
from ml_engine.models.xgb_model import XGBTrainer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("retrain_macro")

async def main():
    print("🚀 Retraining XGBoost Models with Macro Data Edge")
    
    pipeline = DataPipeline()
    macro_fetcher = MacroFetcher()
    fb = FeatureBuilder()
    
    print("Fetching historical macro context...")
    macro_df = macro_fetcher.fetch_macro_data(start="2024-01-01")
    print(f"Loaded {len(macro_df)} days of macro context (TNX, DXY, SPY).")
    
    SYMBOLS = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "XAU/USD"]
    
    for sym in SYMBOLS:
        print(f"\n🧠 Retraining {sym}...")
        try:
            df_raw = pipeline.get_training_data(sym, "1h")
            if df_raw.empty:
                print(f"❌ No data for {sym}, skipping.")
                continue
                
            # Build dataset with MACRO context injected!
            df_feat = fb.build_dataset(df_raw, macro_df=macro_df, dropna=True)
            feat_names = fb.get_feature_columns(df_feat)
            
            print(f"Data shape for {sym}: {df_feat.shape} ({len(feat_names)} features including TNX and DXY)")
            
            xgb = XGBTrainer(symbol=sym, timeframe="1h")
            model, report = xgb.train(df_feat, feat_names, use_optuna=False, retrain=True)
            print(f"✅ {sym} Retraining Complete. Baseline Acc: {report.get('acc', 0):.2f}")
            
        except Exception as e:
            print(f"❌ Failed to retrain {sym}: {e}")
            
    print("\n✅ All Macro-Enabled Models saved successfully!")

if __name__ == "__main__":
    asyncio.run(main())
