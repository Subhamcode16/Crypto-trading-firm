"""
notebooks/colab_train.py
─────────────────────────
Google Colab Training Script — ML Crypto Bot v2.0
(This is a .py version; the .ipynb is the Colab notebook)

Usage in Colab:
  1. Upload this file + ml_engine/ to Google Drive
  2. Open Google Colab, connect to GPU runtime (T4 or better)
  3. Run cells in order

This script handles:
  - Environment setup on Colab
  - Data bootstrapping from Binance
  - LSTM training with GPU acceleration
  - RL (PPO) training with GPU
  - Model download link generation
"""

# ════════════════════════════════════════════════════════════════════
# CELL 1: Setup — Install Dependencies
# ════════════════════════════════════════════════════════════════════

SETUP_CODE = '''
# Install TA-Lib (Ubuntu/Colab-compatible build)
!apt-get install -y libta-lib0-dev 2>/dev/null | tail -1
!pip install TA-Lib --quiet
!pip install tensorflow>=2.15.0 xgboost scikit-learn optuna --quiet
!pip install "stable-baselines3>=2.3.0" "gymnasium>=0.29.0" shimmy --quiet
!pip install ccxt yfinance aiohttp google-generativeai --quiet

# Mount Google Drive
from google.colab import drive
drive.mount("/content/drive")

# Clone or copy ml_engine (if using Drive)
import sys, os
sys.path.insert(0, "/content/drive/MyDrive/crypto-trading-bot")

print("✅ Setup complete!")
'''

# ════════════════════════════════════════════════════════════════════
# CELL 2: Environment Variables
# ════════════════════════════════════════════════════════════════════

ENV_CODE = '''
import os
from google.colab import userdata

# Set your Binance API keys in Colab Secrets (left sidebar → key icon)
try:
    os.environ["BINANCE_API_KEY"]    = userdata.get("BINANCE_API_KEY")
    os.environ["BINANCE_API_SECRET"] = userdata.get("BINANCE_API_SECRET")
    os.environ["GEMINI_API_KEY"]     = userdata.get("GEMINI_API_KEY")
    print("✅ API keys loaded from Colab Secrets")
except Exception:
    print("⚠️ Set API keys in Colab Secrets (left sidebar → key icon)")
    # For data fetching only (no trading), API keys are optional
    os.environ["BINANCE_API_KEY"]    = ""
    os.environ["BINANCE_API_SECRET"] = ""
'''

# ════════════════════════════════════════════════════════════════════
# CELL 3: Bootstrap Historical Data (runs once, ~10-15 min)
# ════════════════════════════════════════════════════════════════════

BOOTSTRAP_CODE = '''
import asyncio
import logging
logging.basicConfig(level=logging.INFO)

from ml_engine.data.pipeline import DataPipeline

pipeline = DataPipeline()

# Bootstrap 3 years of data for BTC, ETH, SOL on 1h and 4h
SYMBOLS    = ["BTC/USDT", "ETH/USDT", "SOL/USDT"]
TIMEFRAMES = ["1h", "4h"]

print("\\n📥 Bootstrapping all symbols and timeframes...")
# Note: Jupyter automatically supports top-level await
rows_fetched = await pipeline.bootstrap(symbols=SYMBOLS, timeframes=TIMEFRAMES)

print(f"\\n✅ Historical data bootstrap complete! Total rows fetched: {rows_fetched:,}")
'''

# ════════════════════════════════════════════════════════════════════
# CELL 4: Feature Engineering Test
# ════════════════════════════════════════════════════════════════════

FEATURE_CODE = '''
from ml_engine.data.pipeline import DataPipeline
from ml_engine.features.feature_builder import FeatureBuilder

pipeline = DataPipeline()
fb       = FeatureBuilder()

# Load BTC 1h data
df_raw  = pipeline.get_training_data("BTC/USDT", "1h")
df_feat = fb.build_dataset(df_raw, dropna=True)
feature_names = fb.get_feature_columns(df_feat)

print(f"✅ Features built: {len(df_feat):,} bars × {len(feature_names)} features")
print(f"First 10 features: {feature_names[:10]}")
print(f"Date range: {df_feat['open_time'].min()} → {df_feat['open_time'].max()}")
print(f"\\nSample feature values (last bar):")
for feat in feature_names[:20]:
    print(f"  {feat}: {df_feat[feat].iloc[-1]:.4f}")
'''

# ════════════════════════════════════════════════════════════════════
# CELL 5: LSTM Training (GPU-accelerated, ~20-30 min with T4)
# ════════════════════════════════════════════════════════════════════

LSTM_CODE = '''
import tensorflow as tf
print(f"GPU available: {len(tf.config.list_physical_devices('GPU'))} device(s)")

from ml_engine.models.lstm_trainer import LSTMTrainer

# Train LSTM for each symbol and timeframe
CONFIGS = [
    ("BTC/USDT", "1h"),
    ("ETH/USDT", "1h"),
    ("SOL/USDT", "1h"),
    ("BTC/USDT", "4h"),
]

reports = []
for sym, tf in CONFIGS:
    print(f"\\n🧠 Training LSTM: {sym} {tf}...")
    trainer = LSTMTrainer(symbol=sym, timeframe=tf)
    report  = trainer.train(retrain=True)
    reports.append(report)
    print(f"   → Status: {report['status']} | Accuracy: {report.get('test_accuracy', 0):.4f}")

print("\\n✅ LSTM training complete!")
print("\\nSummary:")
for r in reports:
    print(f"  {r['symbol']} {r['timeframe']}: acc={r.get('test_accuracy',0):.4f} | saved={r['model_saved']}")
'''

# ════════════════════════════════════════════════════════════════════
# CELL 6: XGBoost Training (~5-10 min, CPU but fast)
# ════════════════════════════════════════════════════════════════════

XGB_CODE = '''
from ml_engine.data.pipeline import DataPipeline
from ml_engine.features.feature_builder import FeatureBuilder
from ml_engine.models.xgb_model import XGBTrainer

pipeline = DataPipeline()
fb       = FeatureBuilder()

for sym in ["BTC/USDT", "ETH/USDT", "SOL/USDT"]:
    print(f"\\n🌲 Training XGBoost: {sym} 1h...")
    df_raw  = pipeline.get_training_data(sym, "1h")
    df_feat = fb.build_dataset(df_raw, dropna=True)
    feat_names = fb.get_feature_columns(df_feat)

    trainer = XGBTrainer(symbol=sym, timeframe="1h")
    model, report = trainer.train(df_feat, feat_names, use_optuna=True, retrain=True)
    print(f"   → Accuracy: {report['test_accuracy']:.4f} | Saved: {report['model_saved']}")

print("\\n✅ XGBoost training complete!")
'''

# ════════════════════════════════════════════════════════════════════
# CELL 7: RL Training (GPU helps here for neural policy, ~45-90 min)
# ════════════════════════════════════════════════════════════════════

RL_CODE = '''
from ml_engine.rl.rl_trainer import RLTrainer

# Train PPO for BTC first (then extend to ETH/SOL)
for sym in ["BTC/USDT", "ETH/USDT", "SOL/USDT"]:
    print(f"\\n🤖 Training RL (PPO): {sym} 1h...")
    trainer = RLTrainer(symbol=sym, timeframe="1h")
    report  = trainer.train(
        timesteps=1_000_000,   # More timesteps on GPU = better policy
        retrain=True,
    )
    print(f"   → Sharpe: {report.get('val_sharpe', 0):.4f}")
    print(f"   → Win Rate: {report.get('val_win_rate', 0):.1%}")
    print(f"   → Return: {report.get('val_total_return', 0):.2f}%")

print("\\n✅ RL training complete!")
'''

# ════════════════════════════════════════════════════════════════════
# CELL 8: Download Trained Models
# ════════════════════════════════════════════════════════════════════

DOWNLOAD_CODE = '''
import shutil
import os
from google.colab import files

# Package all models into a zip
models_dir = "ml_engine/models/saved"
rl_dir     = "ml_engine/rl/policies"

shutil.make_archive("trained_models", "zip", "ml_engine", "models")
shutil.make_archive("rl_policies",    "zip", "ml_engine", "rl/policies")

print("✅ Download these files and place in your local ml_engine/ directory:")
files.download("trained_models.zip")
files.download("rl_policies.zip")

print("\\nAfter download, extract to:")
print("  ml_engine/models/saved/     ← trained_models.zip contents")
print("  ml_engine/rl/policies/      ← rl_policies.zip contents")
'''

if __name__ == "__main__":
    print("This is a Colab notebook script.")
    print("Open notebooks/train_colab.ipynb in Google Colab to run training.")
    print()
    print("Cells:")
    print("  Cell 1: Setup dependencies")
    print("  Cell 2: Configure API keys")
    print("  Cell 3: Bootstrap 3 years of data")
    print("  Cell 4: Test feature engineering")
    print("  Cell 5: Train LSTM (GPU, ~20-30 min)")
    print("  Cell 6: Train XGBoost (~10 min)")
    print("  Cell 7: Train RL agent (GPU, ~45-90 min)")
    print("  Cell 8: Download trained models")
