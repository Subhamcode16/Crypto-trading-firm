import os
import pandas as pd
import numpy as np
import sqlite3

from ml_engine.features.feature_builder import FeatureBuilder
from ml_engine.models.xgb_model import XGBModel

def run_baseline_backtest():
    print("--- Phase 5: Raw XGBoost Baseline Backtest ---")
    
    # 1. Load full clean dataset from database
    db_path = "ml_engine/data/store/cryptobot.db"
    conn = sqlite3.connect(db_path)
    df = pd.read_sql("SELECT * FROM ohlcv WHERE symbol='BTC/USDT' AND timeframe='1h' ORDER BY open_time", conn)
    df['open_time'] = pd.to_datetime(df['open_time'], utc=True)
    df.set_index('open_time', inplace=True)
    
    # 2. Build features
    fb = FeatureBuilder()
    df_feat = fb.build_dataset(df.copy())
    
    # 3. Load Model
    model_path = os.path.join(os.path.dirname(__file__), '..', 'ml_engine', 'models', 'saved', 'xgb_BTC_USDT_1h.pkl')
    xgb = XGBModel.load(model_path)
    feature_names = xgb._feature_names
    
    # 4. Predict
    df_pred = xgb.predict_df(df_feat, feature_names)
    df_pred = df_pred.dropna(subset=feature_names)
    
    # 5. Extract Test Set (same as training temporal split: last 8,417 bars)
    # The total number of bars in `df_feat` is 56,113. 
    # 56,113 - 8,417 = 47,696
    test_bars = 8417
    df_test = df_pred.iloc[-test_bars:].copy()
    
    print(f"\nRunning backtest on OUT-OF-SAMPLE data: {df_test.index[0]} to {df_test.index[-1]}")
    print(f"Total test bars: {len(df_test)}")
    
    # 6. Run simulation
    initial_capital = 10000.0
    cap = initial_capital
    pos = None
    trades_log = []
    
    # Track equity curve over time for Sharpe/Drawdown
    equity_curve = []
    
    for i in range(len(df_test) - 1):
        row = df_test.iloc[i]
        next_row = df_test.iloc[i + 1]
        
        # safely extract timestamp
        t = df.index[df_test.index[i]] if isinstance(df_test.index[i], (int, np.integer)) else df_test.index[i]
        exec_p = next_row['open']
        xgb_sig = row['xgb_signal']
        
        # Update held position
        if pos:
            pos['bars_held'] += 1
            
            # Check TP/SL or time stop
            pnl_pct = (exec_p - pos['entry']) / pos['entry'] if pos['type'] == 'LONG' else (pos['entry'] - exec_p) / pos['entry']
            
            exit_reason = None
            if pnl_pct >= pos['target']:
                exit_reason = 'TP'
            elif pnl_pct <= -pos['target']: # 1:1 risk reward for baseline
                exit_reason = 'SL'
            elif pos['bars_held'] >= 8:
                exit_reason = 'TIME_STOP'
                
            if exit_reason:
                pnl_pct -= 0.001  # Fee assumption
                trades_log.append({
                    'entry_time': pos['entry_time'],
                    'exit_time': t,
                    'duration_hours': (t - pos['entry_time']).total_seconds() / 3600,
                    'entry_price': pos['entry'],
                    'exit_price': exec_p,
                    'type': pos['type'],
                    'pnl': pnl_pct,
                    'reason': exit_reason
                })
                cap += cap * pnl_pct
                pos = None

        # Determine new direction
        if xgb_sig == "STRONG_LONG":
            direction = "LONG"
        elif xgb_sig == "STRONG_SHORT":
            direction = "SHORT"
        else:
            direction = None
            
        # Enter new position
        if direction and not pos:
            # Match labeling logic: target is 1.2 * atr_pct, min 0.004
            # Since we don't have true_range pre-calculated here, approximate with a 1% default if missing
            # Better: calculate true range on the fly or just use a fixed 1.5% target for baseline
            target = 0.015
            pos = {'type': direction, 'entry': exec_p, 'entry_time': t, 'bars_held': 0, 'target': target}
            
        equity_curve.append({'time': t, 'equity': cap})
            
    trades = pd.DataFrame(trades_log)
    equity = pd.DataFrame(equity_curve).set_index('time')
    
    print("\n--- RESULTS ---")
    if len(trades) == 0:
        print("No trades executed.")
        return
        
    win_rate = (trades['pnl'] > 0).mean()
    total_pnl = cap / initial_capital - 1.0
    
    # Calculate Sharpe (annualized, assuming risk-free rate = 0)
    # Returns are per trade, but for Sharpe we usually use bar returns or daily returns.
    # Let's compute daily returns of the equity curve
    daily_equity = equity.resample('D').last()
    daily_returns = daily_equity['equity'].pct_change().dropna()
    
    if len(daily_returns) > 0 and daily_returns.std() > 0:
        sharpe = np.sqrt(365) * daily_returns.mean() / daily_returns.std()
    else:
        sharpe = 0.0
        
    # Calculate Max Drawdown
    roll_max = equity['equity'].cummax()
    drawdown = equity['equity'] / roll_max - 1.0
    max_dd = drawdown.min()
    
    avg_duration = trades['duration_hours'].mean()
    
    print(f"Total Trades: {len(trades)}")
    print(f"Win Rate:     {win_rate*100:.2f}%")
    print(f"Total Return: {total_pnl*100:.2f}%")
    print(f"Sharpe Ratio: {sharpe:.2f}")
    print(f"Max Drawdown: {max_dd*100:.2f}%")
    print(f"Avg Duration: {avg_duration:.1f} hours")

if __name__ == "__main__":
    run_baseline_backtest()
