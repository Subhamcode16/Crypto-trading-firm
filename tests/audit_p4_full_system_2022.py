import sys, os, asyncio, json
import pandas as pd
import numpy as np
from datetime import datetime

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from ml_engine.data.fetcher import BinanceFetcher
from ml_engine.features.feature_builder import FeatureBuilder
from ml_engine.models.xgb_model import XGBModel
from ml_engine.features.regime_detector import RegimeDetector
from ml_engine.models.kronos_wrapper import KronosEngine
from ml_engine.features.kill_switch import KillSwitch

async def run_full_system():
    print("="*60)
    print("  PHASE 4: FULL SYSTEM BACKTEST (1-Year)")
    print("="*60)
    print("Fetching 1-year BTC/USDT 1H data...")
    
    from ml_engine.data.pipeline import DataPipeline
    pipeline = DataPipeline()
    since = "2022-01-01"
    until = "2023-01-01"
    df_1h = pipeline.storage.load_ohlcv("BTC/USDT", "1h", since=since, until=until)
    df_4h = pipeline.storage.load_ohlcv("BTC/USDT", "4h", since=since, until=until)
    
    # fetch_ohlcv returns open_time. Rename it
    if 'open_time' in df_1h.columns:
        df_1h = df_1h.rename(columns={'open_time': 'timestamp'})
    if 'open_time' in df_4h.columns:
        df_4h = df_4h.rename(columns={'open_time': 'timestamp'})

    print(f"Loaded {len(df_1h)} 1H candles and {len(df_4h)} 4H candles.")
    
    print("Building XGBoost Features...")
    fb = FeatureBuilder()
    df_feat = fb.build_dataset(df_1h, dropna=False)
    
    model_path = os.path.join(os.path.dirname(__file__), '..', 'ml_engine', 'models', 'saved', 'xgb_BTC_USDT_1h.pkl')
    xgb = XGBModel.load(model_path)
    feature_names = xgb._feature_names

    available_feats = [f for f in feature_names if f in df_feat.columns]
    for f in set(feature_names) - set(available_feats):
        df_feat[f] = 0.0

    print("Generating XGBoost Signals...")
    df_pred = xgb.predict_df(df_feat, feature_names)
    df_1h['xgb_signal'] = df_pred['xgb_signal'].values
    
    # Merge volatility columns from df_feat into df_1h so Kill Switch
    # compute_thresholds() uses proper 14-bar ATR, not raw single-bar TR.
    for col in ['atr_14', 'atr_normalized']:
        if col in df_feat.columns:
            df_1h[col] = df_feat[col].values
    
    # Pre-compute Regimes (1H base only to check distribution)
    rd = RegimeDetector()
    print("Computing Regimes...")
    regimes = []
    adx_series = rd.compute_adx(df_1h, 14)
    er_series = rd.compute_er(df_1h, 14)
    bb_series = rd.compute_bb_width(df_1h, 20)
    
    for i in range(len(df_1h)):
        if i < 200 or pd.isna(adx_series.iloc[i]):
            regimes.append("AMBIGUOUS")
            continue
        adx = adx_series.iloc[i]
        er = er_series.iloc[i]
        current_bb = bb_series.iloc[i]
        bb_hist = bb_series.iloc[max(0, i-200):i].dropna()
        bb_pct = (bb_hist < current_bb).mean() * 100 if not bb_hist.empty else 50.0
        
        r = rd.classify_1h_regime(adx, er, bb_pct)
        regimes.append(r)
        
    df_1h['base_regime'] = regimes
    dist = df_1h['base_regime'].value_counts()
    
    print("\n[Regime Distribution]")
    for r, c in dist.items():
        print(f"  {r.ljust(20)}: {c:>5} bars ({c/len(df_1h)*100:.1f}%)")

    # Load Kronos
    print("\nLoading Kronos Engine...")
    k_engine = KronosEngine(device="cpu")
    k_engine.load()

    print("\nRunning Full System Simulation...")
    initial_capital = 10000.0
    cap = initial_capital
    peak = initial_capital
    max_dd = 0.0
    
    # We will simulate Raw Kronos performance alongside the Full System
    k_cap = initial_capital
    k_peak = initial_capital
    k_max_dd = 0.0
    k_pos = None
    k_trades = 0
    k_wins = 0

    pos = None
    trades = 0
    wins = 0
    
    kill_switch = KillSwitch()
    ps = {
        "current_capital": initial_capital,
        "peak_capital": initial_capital,
        "consecutive_losses": 0,
        "total_drawdown_from_start_pct": 0.0,
        "session_drawdown_pct": 0.0
    }
    
    # Pre-align data
    df_1h = df_1h.reset_index(drop=False)
    if 'index' in df_1h.columns and 'timestamp' not in df_1h.columns:
        df_1h = df_1h.rename(columns={'index': 'timestamp'})
    df_1h['timestamp'] = pd.to_datetime(df_1h['timestamp'])
        
    daily_caps = []
    trade_log = []
    last_day = None
    daily_start_cap = initial_capital  # Track intraday drawdown correctly
    ks_blocks = 0
    rg_blocks = 0
    df4_blocks = 0
    ks_reasons = {}  # Count what's actually firing

    for i in range(500, len(df_1h) - 1):
        row = df_1h.iloc[i]
        next_row = df_1h.iloc[i + 1]
        
        t = row['timestamp']
        exec_p = next_row['open']
        
        day = pd.to_datetime(t).date()
        if last_day and day != last_day:
            daily_caps.append(cap)
            daily_start_cap = cap  # Reset session baseline at day start
            # Reset session-level counters at each new calendar day.
            # consecutive_losses and session_drawdown are intraday guards,
            # not permanent lockouts. A new day means a fresh start.
            ps["session_drawdown_pct"] = 0.0
            ps["consecutive_losses"] = 0
        last_day = day

        # Update position for Full System
        if pos:
            # Hold until signal flips, 8 hours pass, or TP/SL is hit
            hours_held = (pd.to_datetime(t) - pd.to_datetime(pos['entry_time'])).total_seconds() / 3600.0
            
            tp_hit = False
            sl_hit = False
            exit_price = exec_p
            
            high = row['high']
            low = row['low']
            
            if pos['type'] == 'LONG':
                if high >= pos['tp_price']:
                    tp_hit = True
                    exit_price = pos['tp_price']
                elif low <= pos['sl_price']:
                    sl_hit = True
                    exit_price = pos['sl_price']
            else:
                if low <= pos['tp_price']:
                    tp_hit = True
                    exit_price = pos['tp_price']
                elif high >= pos['sl_price']:
                    sl_hit = True
                    exit_price = pos['sl_price']
            
            if hours_held >= 8 or tp_hit or sl_hit:
                pnl_pct = (exit_price - pos['entry']) / pos['entry'] if pos['type'] == 'LONG' else (pos['entry'] - exit_price) / pos['entry']
                pnl_pct -= 0.001 # Trading fee
                pnl_usd = cap * pnl_pct
                cap += pnl_usd
                peak = max(peak, cap)
                dd = (peak - cap) / peak
                max_dd = max(max_dd, dd)
                
                trade_log.append({
                    'entry_time': pos['entry_time'],
                    'exit_time': t,
                    'type': pos['type'],
                    'hours_held': hours_held,
                    'month': pd.to_datetime(pos['entry_time']).month,
                    'year': pd.to_datetime(pos['entry_time']).year
                })
                trades += 1
                if pnl_usd > 0:
                    wins += 1
                
                # Update kill switch portfolio state
                ps["current_capital"] = cap
                ps["peak_capital"] = peak
                ps["total_drawdown_from_start_pct"] = (initial_capital - cap) / initial_capital if cap < initial_capital else 0.0
                ps["session_drawdown_pct"] = max(0.0, (daily_start_cap - cap) / daily_start_cap) if daily_start_cap > 0 else 0.0
                if pnl_usd < 0:
                    ps["consecutive_losses"] += 1
                else:
                    ps["consecutive_losses"] = 0
                
                pos = None
        
        # Update position for Raw Kronos
        if k_pos:
            k_hours = (pd.to_datetime(t) - pd.to_datetime(k_pos['entry_time'])).total_seconds() / 3600.0
            if k_hours >= 8:
                k_pnl = (exec_p - k_pos['entry']) / k_pos['entry'] if k_pos['type'] == 'LONG' else (k_pos['entry'] - exec_p) / k_pos['entry']
                k_pnl -= 0.001
                k_cap += k_cap * k_pnl
                k_peak = max(k_peak, k_cap)
                k_dd = (k_peak - k_cap) / k_peak
                k_max_dd = max(k_max_dd, k_dd)
                k_trades += 1
                if k_pnl > 0: k_wins += 1
                k_pos = None

        xgb_sig = row['xgb_signal']
        
        if xgb_sig in ("STRONG_LONG", "STRONG_SHORT"):
            # Prevent Look-Ahead Bias:
            # We can only use 4H candles that have CLOSED at or before our 1H decision time.
            # Decision time is t_dt + 1 hour. A 4H candle closes at 4H_open_time + 4 hours.
            # So: 4H_open_time + 4h <= t_dt + 1h  =>  4H_open_time <= t_dt - 3h
            t_dt = pd.to_datetime(t)
            df_4h_slice = df_4h[df_4h['timestamp'] <= (t_dt - pd.Timedelta(hours=3))]
            if df_4h_slice.empty or len(df_4h_slice) < 20:
                df4_blocks += 1
                continue

            # 1. Kill Switch Check
            # CRITICAL: pass a proper 60-day rolling window (1440 1H bars) so
            # percentile thresholds are computed against real history, not 5 bars.
            ks_window = df_1h.iloc[max(0, i - 1440):i + 1]
            ks_level, ks_reason = kill_switch.evaluate(ks_window, df_4h_slice, ps, {})
            if ks_level > 0:
                ks_blocks += 1
                ks_reasons[ks_reason] = ks_reasons.get(ks_reason, 0) + 1
                continue # Blocked
                
            # 2. 4H Anchor / Regime Gate
            base_r = row['base_regime']
            signal_dir = "LONG" if xgb_sig == "STRONG_LONG" else "SHORT"
            final_regime = rd.apply_4h_anchor(base_r, signal_dir, df_4h_slice)
            
            if final_regime in ("AMBIGUOUS", "VOLATILE_CHOP", "DEAD_RANGE", "COUNTER_TREND_REJECTED", "MACRO_TREND_REJECTED"):
                rg_blocks += 1
                continue # Blocked by regime gate
            
            # 3. Consensus / Kronos MC Check
            # RUN REAL KRONOS INFERENCE: 
            # With fewer XGBoost signals, we can afford a few forward passes
            lookback = df_1h.iloc[max(0, i - 128):i + 1]
            pred_df = k_engine.predict(lookback, pred_len=4, sample_count=5)
            
            if not pred_df.empty:
                p50 = pred_df['close'].iloc[-1]
                expected_return = (p50 - exec_p) / exec_p
                
                # Raw Kronos Baseline update: 
                if not k_pos:
                    if expected_return > 0.01:
                        k_pos = {'type': 'LONG', 'entry': exec_p, 'entry_time': t}
                    elif expected_return < -0.01:
                        k_pos = {'type': 'SHORT', 'entry': exec_p, 'entry_time': t}
                
                # Full System Consensus
                aligned = (signal_dir == "LONG" and expected_return > 0) or \
                          (signal_dir == "SHORT" and expected_return < 0)
                          
                if aligned and not pos:
                    # 4. LLM Gatekeeper (Simulated PASS for backtest)
                    atr = row.get('atr_14', exec_p * 0.02)
                    tp_dist = atr * 2.0
                    sl_dist = atr * 1.5
                    
                    tp = exec_p + tp_dist if signal_dir == "LONG" else exec_p - tp_dist
                    sl = exec_p - sl_dist if signal_dir == "LONG" else exec_p + sl_dist
                    
                    pos = {'type': signal_dir, 'entry': exec_p, 'entry_time': t, 'tp_price': tp, 'sl_price': sl}

    # Wrap up stats
    def calc_sharpe(caps):
        if len(caps) < 2: return 0.0
        rets = pd.Series(caps).pct_change().dropna()
        if rets.std() == 0: return 0.0
        return (rets.mean() / rets.std()) * np.sqrt(365)
        
    strong_sig_count = df_1h['xgb_signal'].isin(['STRONG_LONG', 'STRONG_SHORT']).sum()
    print(f"\nDEBUG: Total strong signals: {strong_sig_count}, Total trades: {trades}")
    print(f"DEBUG: df4_blocks: {df4_blocks}, ks_blocks: {ks_blocks}, rg_blocks: {rg_blocks}")
    if ks_reasons:
        print("\n[KS REASON BREAKDOWN (top 10)]")
        for reason, count in sorted(ks_reasons.items(), key=lambda x: -x[1])[:10]:
            print(f"  {reason:<55}: {count:>5}")
        
    f_sharpe = calc_sharpe(daily_caps)
    f_ret = (cap - initial_capital) / initial_capital * 100
    
    trade_df = pd.DataFrame(trade_log)
    if not trade_df.empty:
        trade_df['month_year'] = trade_df['year'].astype(str) + '-' + trade_df['month'].astype(str).str.zfill(2)
        print('\n[TRADE DISTRIBUTION BY MONTH]')
        print(trade_df['month_year'].value_counts().sort_index())
        print(f'\nAverage trade duration: {trade_df["hours_held"].mean():.1f} hours')
    
    k_ret = (k_cap - initial_capital) / initial_capital * 100
    # Approximate Sharpe for Kronos since we didn't track daily (just for table)
    # The baseline EMA was -21.3%, 32.32%, -0.46
    # XGBoost was +27.1%, 25.8%, 1.31
    
    print("\n" + "="*60)
    print("FINAL RESULTS FOR PAPER TRADING APPROVAL")
    print("="*60)
    print(f"Component                    Return    Max DD    Sharpe")
    print("-" * 53)
    print(f"EMA baseline (Phase 1)       -21.3%    32.32%    -0.46")
    print(f"Raw XGBoost (Phase 2)        +27.1%    25.84%     1.31")
    print(f"Raw Kronos (Phase 2)         {k_ret:>+5.1f}%    {k_max_dd*100:>5.2f}%     {k_ret/max(1, k_max_dd*100)/2:.2f}*")
    print(f"Full system (Phase 2 target) {f_ret:>+5.1f}%    {max_dd*100:>5.2f}%     {f_sharpe:.2f}")
    
    if max_dd < 0.10 and f_ret > 15.0 and f_sharpe > 1.0:
        print("\nALL CRITERIA MET. Backtest-validated system is READY for Bybit Testnet paper trading.")
    else:
        print("\nTARGETS NOT FULLY MET. Review component performance.")

if __name__ == "__main__":
    asyncio.run(run_full_system())
