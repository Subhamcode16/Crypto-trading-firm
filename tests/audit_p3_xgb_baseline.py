"""
Priority 3: True Baseline — Raw XGBoost Signals (No Filters)
Establishes the unfiltered XGBoost signal performance on 1-year data.
This is the number Phase 2 will compare the full system against.

Note: Kronos is excluded from this baseline because it requires ~2 min per
inference call (no GPU). XGBoost alone is the vectorized baseline.
"""
import sys, os, asyncio
import pandas as pd
import numpy as np

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from ml_engine.data.fetcher import BinanceFetcher
from ml_engine.models.xgb_model import XGBModel
from ml_engine.features.regime_detector import RegimeDetector

from ml_engine.features.feature_builder import FeatureBuilder
from ml_engine.models.kronos_wrapper import KronosEngine

async def run_xgb_baseline():
    from ml_engine.data.pipeline import DataPipeline
    print("Fetching 1-year BTC/USDT 1H data for XGBoost raw baseline...")
    since = "2024-01-01"  # Approximate 1 year of data from 2020-2024 set
    until = "2025-01-01"
    df_1h = DataPipeline().storage.load_ohlcv("BTC/USDT", "1h", since=since, until=until)
    if 'index' in df_1h.columns and 'timestamp' not in df_1h.columns:
        df_1h = df_1h.rename(columns={'index': 'timestamp'})

    print(f"Loaded {len(df_1h)} candles. Building features via FeatureBuilder...")
    fb = FeatureBuilder()
    df_feat = fb.build_dataset(df_1h)

    model_path = os.path.join(os.path.dirname(__file__), '..', 'ml_engine', 'models', 'saved', 'xgb_BTC_USDT_1h.pkl')
    # Using VolatilityBreakoutSignal instead of XGBoost as per Step 1
    from ml_engine.models.signal_generator import VolatilityBreakoutSignal
    xgb = VolatilityBreakoutSignal(symbol="BTC/USDT", timeframe="1h")
    feature_names = xgb._feature_names

    # Only keep rows where all features are available
    available_feats = [f for f in feature_names if f in df_feat.columns]
    missing = set(feature_names) - set(df_feat.columns)
    if missing:
        print(f"[WARNING] {len(missing)} features missing from builder: {missing}")
        for f in missing:
            df_feat[f] = 0.0

    df_pred = xgb.predict_df(df_feat, feature_names)
    df_pred = df_pred.dropna(subset=feature_names).reset_index(drop=True)

    print(f"Running raw XGBoost signal simulation on {len(df_pred)} bars...\n")

    initial_capital = 10000.0
    cap         = initial_capital
    peak        = initial_capital
    max_dd      = 0.0
    pos         = None
    trades      = 0
    wins        = 0
    gross_p     = 0.0
    gross_l     = 0.0
    durations   = []
    daily_caps  = []
    last_day    = None

    signal_counts = {"STRONG_LONG": 0, "STRONG_SHORT": 0, "WEAK": 0, "NO_SIGNAL": 0}

    for i in range(len(df_pred) - 1):
        row      = df_pred.iloc[i]
        next_row = df_pred.iloc[i + 1]
        t        = row['open_time']
        exec_p   = next_row['open']
        xgb_sig  = row['xgb_signal']
        xgb_conf = row['xgb_confidence']

        signal_counts[xgb_sig] = signal_counts.get(xgb_sig, 0) + 1

        day = t.date()
        if last_day and day != last_day:
            daily_caps.append(cap)
        last_day = day

        # Translate XGBoost signal to direction
        if xgb_sig == "STRONG_LONG":
            direction = "LONG"
        elif xgb_sig == "STRONG_SHORT":
            direction = "SHORT"
        else:
            direction = None  # WEAK / NO_SIGNAL = hold

        # Close existing position if direction flips or we get NO_SIGNAL
        if pos and (direction != pos['type']):
            pnl_pct = (exec_p - pos['entry']) / pos['entry'] if pos['type'] == 'LONG' else (pos['entry'] - exec_p) / pos['entry']
            pnl_pct -= 0.001  # fee
            pnl_usd  = cap * pnl_pct
            cap     += pnl_usd
            peak     = max(peak, cap)
            dd       = (peak - cap) / peak
            max_dd   = max(max_dd, dd)

            dur = (t - pos['entry_time']).total_seconds() / 3600.0
            durations.append(dur)
            trades += 1
            if pnl_usd > 0:
                wins    += 1
                gross_p += pnl_usd
            else:
                gross_l += abs(pnl_usd)
            pos = None

        # Open new position
        if direction and not pos:
            pos = {'type': direction, 'entry': exec_p, 'entry_time': t, 'conf': xgb_conf}

    if daily_caps:
        returns  = pd.Series(daily_caps).pct_change().dropna()
        sharpe   = (returns.mean() / (returns.std() + 1e-10)) * np.sqrt(365)
    else:
        sharpe = 0.0

    win_rate    = wins / max(1, trades) * 100
    pf          = gross_p / gross_l if gross_l > 0 else float('inf')
    avg_dur     = np.mean(durations) if durations else 0.0
    final_pnl   = (cap - initial_capital) / initial_capital * 100

    print("=" * 60)
    print("  PRIORITY 3 — TRUE BASELINE: RAW XGBoost (Full Features, No Filters)")
    print("=" * 60)
    print(f"\n  XGBoost Signal Distribution:")
    total_bars = sum(signal_counts.values())
    for sig, cnt in sorted(signal_counts.items(), key=lambda x: -x[1]):
        print(f"    {sig.ljust(15)}: {cnt:>5} bars  ({cnt/total_bars*100:.1f}%)")

    print(f"\n  Performance Metrics (1-Year XGBoost-Only):")
    print(f"    Final Capital       : ${cap:,.2f}  ({final_pnl:+.2f}%)")
    print(f"    Max Drawdown        : {max_dd*100:.2f}%  (target < 15%)")
    print(f"    Sharpe Ratio        : {sharpe:.2f}     (target > 1.0)")
    print(f"    Win Rate            : {win_rate:.1f}%     ({wins}/{trades} trades)")
    print(f"    Profit Factor       : {pf:.2f}     (target > 1.5)")
    print(f"    Avg Trade Duration  : {avg_dur:.1f} hrs")
    print(f"    Total Trades        : {trades}")
    print(f"\n  This is your 1-Year Phase 2 comparison baseline.")
    
    print("\n" + "=" * 60)
    print("  KRONOS MC SHORT BASELINE (Last 30 Days)")
    print("=" * 60)
    print("Loading Kronos Engine for a 30-day sample backtest...")
    k_engine = KronosEngine(device="cpu")
    k_engine.load()
    if not k_engine.is_loaded:
        print("Failed to load Kronos. Skipping combined baseline.")
        return
        
    df_30d = df_1h.tail(24 * 30).reset_index(drop=False)
    # Ensure it's named timestamp if it was the index
    if 'index' in df_30d.columns and 'timestamp' not in df_30d.columns:
        df_30d = df_30d.rename(columns={'index': 'timestamp'})
    elif 'timestamp' in df_30d.columns:
        pass
    
    df_feat_30d = df_feat.tail(24 * 30).reset_index(drop=True)
    df_pred_30d = xgb.predict_df(df_feat_30d, feature_names).dropna(subset=feature_names).reset_index(drop=True)
    
    k_trades = 0
    k_blocks = 0
    for i in range(len(df_pred_30d) - 1):
        row = df_pred_30d.iloc[i]
        xgb_sig = row['xgb_signal']
        if xgb_sig in ("STRONG_LONG", "STRONG_SHORT"):
            # Only run Kronos when XGBoost fires a signal to save time
            window = df_30d.iloc[max(0, i-512):i+1].copy()
            pred_df = k_engine.predict(window, pred_len=16, sample_count=10)
            if not pred_df.empty:
                last_price = window['close'].iloc[-1]
                p50 = pred_df['close_p50'].iloc[-1]
                expected_return = (p50 - last_price) / last_price
                
                # Check alignment
                aligned = (xgb_sig == "STRONG_LONG" and expected_return > 0.01) or \
                          (xgb_sig == "STRONG_SHORT" and expected_return < -0.01)
                
                if aligned:
                    k_trades += 1
                else:
                    k_blocks += 1
    
    print(f"  In the last 30 days:")
    print(f"  XGBoost emitted {k_trades + k_blocks} strong signals.")
    print(f"  Kronos MC Cone aligned and verified: {k_trades}")
    print(f"  Kronos MC Cone vetoed: {k_blocks}")
    print("\n  Full system (XGBoost + Kronos + Regime Gate + KillSwitch) must BEAT these numbers.")

if __name__ == "__main__":
    asyncio.run(run_xgb_baseline())
