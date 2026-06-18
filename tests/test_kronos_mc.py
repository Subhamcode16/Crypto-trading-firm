import sys
import os
import pandas as pd
import numpy as np

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from ml_engine.models.kronos_wrapper import KronosEngine

def test_kronos_mc():
    print("Loading Kronos Engine...")
    engine = KronosEngine(device="cpu") # Force CPU for simple testing
    engine.load()
    
    if not engine.is_loaded:
        print("Failed to load Kronos. Aborting test.")
        return
        
    print("Creating dummy OHLCV data...")
    # 512 bars of dummy price data
    np.random.seed(42)
    prices = np.linspace(60000, 65000, 512) + np.random.randn(512) * 100
    df = pd.DataFrame({
        'open': prices,
        'high': prices + 50,
        'low': prices - 50,
        'close': prices,
        'volume': np.random.rand(512) * 10,
        'amount': np.random.rand(512) * 600000
    })
    
    # Needs timestamp
    df['timestamp'] = pd.date_range(end=pd.Timestamp.now(), periods=512, freq='h')
    
    print("Running Kronos MC Verification (1 pass with sample_count=50)...")
    pred_df = engine.predict(df, pred_len=16, sample_count=50)
    
    if pred_df.empty:
        print("Prediction failed!")
        return
        
    print("Checking Std progression...")
    std_progression = pred_df['close_std'].values
    print("close_std progression (Step 1 -> 16):")
    print(np.round(std_progression, 2))
    
    assert np.mean(std_progression) > 0, "close_std is zero, MC Dropout is not generating stochastic variance!"
    assert std_progression[-1] > std_progression[0], "Uncertainty (std) should increase further into the future!"
    print("✅ Kronos Monte Carlo Verification Passed!")

if __name__ == "__main__":
    test_kronos_mc()
