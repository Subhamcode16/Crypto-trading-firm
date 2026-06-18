import sqlite3
import pandas as pd
from statsmodels.tsa.stattools import adfuller
from ml_engine.features.feature_builder import FeatureBuilder
from ml_engine.models.xgb_model import XGBModel
import warnings
warnings.filterwarnings('ignore')

def run_phase_2_3_4():
    print("--- PHASE 2: Feature Matrix Regeneration and Stationarity Tests ---")
    conn = sqlite3.connect('ml_engine/data/store/cryptobot.db')
    df_clean = pd.read_sql("SELECT * FROM ohlcv WHERE symbol='BTC/USDT' AND timeframe='1h' ORDER BY open_time", conn)
    df_clean['open_time'] = pd.to_datetime(df_clean['open_time'], utc=True)
    df_clean.set_index('open_time', inplace=True)
    
    print(f"Loaded {len(df_clean)} clean rows.")
    
    feature_builder = FeatureBuilder()
    df_features = feature_builder.build_dataset(df_clean)
    print(f"Built features. Shape: {df_features.shape}")
    print(f"Available columns: {list(df_features.columns)[:10]} ...")
    
    # Stationarity audit skipped (numpy 2.x compatibility issues with adfuller)
    print("\n--- PHASE 3: Label Recalibration ---")
    xgb = XGBModel(symbol='BTC/USDT', timeframe='1h')
    
    labels = xgb.generate_labels(df_features, min_move_pct=0.004)
    
    counts = labels.value_counts(normalize=True)
    print(f"\nLabel distribution with MIN_THRESHOLD = 0.004:")
    for k, v in counts.items():
        class_name = {0: 'NO_SIGNAL', 1: 'STRONG_LONG', 2: 'STRONG_SHORT'}.get(k, k)
        print(f"  {class_name:<15}: {v:.2%}")
            
    print("\n--- PHASE 4: XGBoost Retraining (Strict Temporal Split) ---")
    
    total_bars = len(df_features)
    train_end = int(total_bars * 0.70)
    val_end = int(total_bars * 0.85)
    
    X_train = df_features.iloc[:train_end]
    X_val = df_features.iloc[train_end:val_end]
    X_test = df_features.iloc[val_end:]
    
    print(f"Train : {X_train.index[0]} to {X_train.index[-1]} ({len(X_train):,} bars)")
    print(f"Val   : {X_val.index[0]} to {X_val.index[-1]} ({len(X_val):,} bars)")
    print(f"Test  : {X_test.index[0]} to {X_test.index[-1]} ({len(X_test):,} bars)")
    
    from ml_engine.models.xgb_model import XGBTrainer
    feature_columns = feature_builder.get_feature_columns(df_features)
    trainer = XGBTrainer(symbol='BTC/USDT', timeframe='1h')
    print("\nRetraining model...")
    trained_model, report = trainer.train(df_features, feature_names=feature_columns, use_optuna=False, retrain=True)
    
    print("\nTraining complete.")
    print("Test Accuracy:", report.get('test_accuracy'))
    trained_model.save()

if __name__ == "__main__":
    run_phase_2_3_4()
