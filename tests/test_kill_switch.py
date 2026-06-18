import sys
import os
import pandas as pd

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from ml_engine.features.kill_switch import KillSwitch

def test_kill_switch_levels():
    ks = KillSwitch()
    
    # Mock DataFrames
    df_1h = pd.DataFrame({'open': [100, 100], 'close': [100, 100], 'atr_14': [10, 10]})
    df_4h = pd.DataFrame({'open': [100, 100], 'close': [100, 100], 'atr_14': [10, 10]})
    
    # NORMAL
    portfolio_state = {}
    macro_context = {"vix": 20}
    level, reason = ks.evaluate(df_1h, df_4h, portfolio_state, macro_context)
    assert level == 0, f"Expected 0, got {level}: {reason}"
    print(f"Normal Check Passed: {reason}")
    
    # YELLOW ALERT (L1)
    portfolio_state = {"consecutive_losses": 3}
    level, reason = ks.evaluate(df_1h, df_4h, portfolio_state, macro_context)
    assert level == 1, f"Expected 1, got {level}: {reason}"
    print(f"L1 Check Passed: {reason}")
    
    # RED ALERT (L2)
    portfolio_state = {"consecutive_losses": 5}
    level, reason = ks.evaluate(df_1h, df_4h, portfolio_state, macro_context)
    assert level == 2, f"Expected 2, got {level}: {reason}"
    print(f"L2 Check Passed: {reason}")
    
    # BLACK ALERT (L3)
    portfolio_state = {"total_drawdown_from_start_pct": 0.15}
    level, reason = ks.evaluate(df_1h, df_4h, portfolio_state, macro_context)
    assert level == 3, f"Expected 3, got {level}: {reason}"
    print(f"L3 Check Passed: {reason}")

if __name__ == "__main__":
    test_kill_switch_levels()
    print("All Kill Switch tests passed successfully!")
