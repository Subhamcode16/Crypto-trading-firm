import sys, os, asyncio
import pandas as pd
import numpy as np

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from ml_engine.data.pipeline import DataPipeline
from ml_engine.features.feature_builder import FeatureBuilder
from ml_engine.models.xgb_model import XGBModel

def run_diagnostics():
    print("Fetching 1-year BTC/USDT 1H data for XGBoost raw baseline...")
    since = "2024-01-01"
    until = "2025-01-01"
    df_1h = DataPipeline().storage.load_ohlcv("BTC/USDT", "1h", since=since, until=until)
    if 'index' in df_1h.columns and 'open_time' not in df_1h.columns:
        df_1h = df_1h.rename(columns={'index': 'open_time'})
        
    df_1h['open_time'] = pd.to_datetime(df_1h['open_time'])
    
    fb = FeatureBuilder()
    df_feat = fb.build_dataset(df_1h)
    
    model_path = os.path.join(os.path.dirname(__file__), '..', 'ml_engine', 'models', 'saved', 'xgb_BTC_USDT_1h.pkl')
    xgb = XGBModel.load(model_path)
    feature_names = xgb._feature_names
    
    df_pred = xgb.predict_df(df_feat, feature_names)
    df_pred = df_pred.dropna(subset=feature_names).reset_index(drop=True)
    
    # Run simulation
    initial_capital = 10000.0
    cap = initial_capital
    pos = None
    trades_log = []
    
    for i in range(len(df_pred) - 1):
        row = df_pred.iloc[i]
        next_row = df_pred.iloc[i + 1]
        t = row['open_time']
        exec_p = next_row['open']
        xgb_sig = row['xgb_signal']
        
        if xgb_sig == "STRONG_LONG":
            direction = "LONG"
        elif xgb_sig == "STRONG_SHORT":
            direction = "SHORT"
        else:
            direction = None
            
        if pos and (direction != pos['type']):
            pnl_pct = (exec_p - pos['entry']) / pos['entry'] if pos['type'] == 'LONG' else (pos['entry'] - exec_p) / pos['entry']
            pnl_pct -= 0.001
            trades_log.append({
                'timestamp': pos['entry_time'],
                'exit_timestamp': t,
                'entry_price': pos['entry'],
                'exit_price': exec_p,
                'type': pos['type'],
                'pnl': pnl_pct
            })
            cap += cap * pnl_pct
            pos = None
            
        if direction and not pos:
            pos = {'type': direction, 'entry': exec_p, 'entry_time': t}
            
    trades = pd.DataFrame(trades_log)
    
    print("\n--- TEMPORAL DISTRIBUTION ---")
    if not trades.empty:
        trades['month'] = trades['timestamp'].dt.to_period('M')
        monthly = trades.groupby('month').agg(
            count=('pnl', 'count'),
            total_pnl=('pnl', 'sum'),
            win_rate=('pnl', lambda x: (x > 0).mean())
        )
        print(monthly)
        print(f"\nTotal trades: {len(trades)}")
        print(f"Trades in first 3 months: {(trades['month'] < '2024-04').sum()}")
        print(f"Trades in last 3 months: {(trades['month'] >= '2024-10').sum()}")
    else:
        print("No trades executed.")

    print("\n--- MANUAL TRADE VERIFICATION ---")
    if len(trades) >= 10:
        sample_trades = trades.sample(10, random_state=42)
        df_1h_indexed = df_1h.set_index('open_time')
        
        for _, trade in sample_trades.iterrows():
            entry_time = trade['timestamp']
            exit_time = trade['exit_timestamp']
            
            try:
                entry_bar = df_1h_indexed.loc[entry_time]
                exit_bar = df_1h_indexed.loc[exit_time]
                
                # Manual PnL (we use next bar open in the loop, so let's verify if that matches exit_bar['open'])
                # The simulation exited at next_row['open'] which corresponds to the open price of the bar *after* exit_time signal flipped.
                # Since the backtest code sets t = row['open_time'] and exit happens at next_row['open'],
                # the exit_bar in our index is exactly the t that triggered the flip.
                # So the price executed is exit_bar's NEXT candle open. 
                
                # Actually, df_pred corresponds to df_1h. 
                # Let's just use the entry_price and exit_price logged to verify the math
                logged_pnl = trade['pnl']
                exec_in = trade['entry_price']
                exec_out = trade['exit_price']
                
                if trade['type'] == 'LONG':
                    manual_pnl = (exec_out - exec_in) / exec_in - 0.001
                else:
                    manual_pnl = (exec_in - exec_out) / exec_in - 0.001
                    
                match = abs(logged_pnl - manual_pnl) < 1e-6
                print(f"Trade {trade['type']} at {entry_time} to {exit_time}")
                print(f"  Logged PnL: {logged_pnl:.6f} | Manual PnL: {manual_pnl:.6f} | Match: {match}")
            except Exception as e:
                print(f"Error checking trade at {entry_time}: {e}")
                
    print("\n--- TRAINING DATA OVERLAP ---")
    df_train = DataPipeline().storage.load_ohlcv("BTC/USDT", "1h", since="2020-01-01", until="2025-01-01")
    n_test = max(50, int(len(df_train) * 0.15))
    train_end = df_train.iloc[-n_test - 1]['open_time']
    test_start = df_train.iloc[-n_test]['open_time']
    print(f"Total bars in 2020-2025 dataset: {len(df_train)}")
    print(f"Train/Test split index: -{n_test}")
    print(f"Last Training Candle: {train_end}")
    print(f"First Test Candle:    {test_start}")
    print(f"Baseline Data (2024): 2024-01-01 to 2025-01-01")
    
    print("\n--- RETURN COMPUTATION MISMATCH ---")
    df_1h['future_close'] = df_1h['close'].shift(-8)
    df_1h['next_open'] = df_1h['open'].shift(-1)
    
    future_return_label = df_1h['future_close'] / df_1h['close'] - 1
    future_return_actual = df_1h['future_close'] / df_1h['next_open'] - 1
    
    corr = future_return_label.corr(future_return_actual)
    print(f"Label vs executable return correlation: {corr:.4f}")

if __name__ == "__main__":
    run_diagnostics()
