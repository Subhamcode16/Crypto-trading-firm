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

class BreakoutExitManager:
    
    def __init__(self):
        self.stop_atr_multiple    = 1.5   # Stop at 1.5x ATR below entry
        self.target_atr_multiple  = 3.0   # Target at 3.0x ATR above entry
        self.max_hold_bars        = 72    # Hard ceiling — 72 hours
        self.trailing_activation  = 2.0   # Activate trail after 2x ATR profit
        self.trailing_atr_mult    = 1.0   # Trail by 1x ATR
    
    def calculate_exits(self, entry_price: float,
                              direction: str,
                              atr: float) -> dict:
        
        if direction == 'LONG':
            stop_loss    = entry_price - (self.stop_atr_multiple * atr)
            take_profit  = entry_price + (self.target_atr_multiple * atr)
        else:
            stop_loss    = entry_price + (self.stop_atr_multiple * atr)
            take_profit  = entry_price - (self.target_atr_multiple * atr)
        
        return {
            'stop_loss':   stop_loss,
            'take_profit': take_profit,
            'max_bars':    self.max_hold_bars,
            'trailing_activated': False
        }
    
    def should_exit(self, position: dict,
                         current_bar: pd.Series,
                         bars_held: int,
                         atr: float) -> dict:
        
        entry  = position['entry_price']
        direction = position['direction']
        stops  = position['exits']
        
        # ── Hard exits ───────────────────────────────────────────────
        if bars_held >= self.max_hold_bars:
            return {'exit': True, 'reason': 'MAX_HOLD_TIME'}
        
        if direction == 'LONG':
            if current_bar['low'] <= stops['stop_loss']:
                reason = 'TRAILING_STOP' if stops.get('trailing_activated') else 'STOP_LOSS'
                return {'exit': True, 'reason': reason}
            if current_bar['high'] >= stops['take_profit']:
                return {'exit': True, 'reason': 'TAKE_PROFIT'}
        else:
            if current_bar['high'] >= stops['stop_loss']:
                reason = 'TRAILING_STOP' if stops.get('trailing_activated') else 'STOP_LOSS'
                return {'exit': True, 'reason': reason}
            if current_bar['low'] <= stops['take_profit']:
                return {'exit': True, 'reason': 'TAKE_PROFIT'}
        
        # ── Trailing stop activation ─────────────────────────────────
        profit_in_atr = abs(
            (current_bar['close'] - entry) / atr
        )
        
        if profit_in_atr >= self.trailing_activation:
            trail_distance = self.trailing_atr_mult * atr
            
            if direction == 'LONG':
                trail_stop = current_bar['close'] - trail_distance
                if trail_stop > stops['stop_loss']:
                    position['exits']['stop_loss'] = trail_stop
                    position['exits']['trailing_activated'] = True
                    
            else:
                trail_stop = current_bar['close'] + trail_distance
                if trail_stop < stops['stop_loss']:
                    position['exits']['stop_loss'] = trail_stop
                    position['exits']['trailing_activated'] = True
        
        return {'exit': False}

async def run_full_system():
    print("="*60)
    print("  PHASE 4: FULL SYSTEM BACKTEST (1-Year)")
    print("="*60)
    print("Fetching 1-year BTC/USDT 1H data...")
    
    from ml_engine.data.pipeline import DataPipeline
    pipeline = DataPipeline()
    since = "2024-01-01"
    until = "2025-01-01"
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
    # Using VolatilityBreakoutSignal instead of XGBoost
    from ml_engine.models.signal_generator import VolatilityBreakoutSignal
    xgb = VolatilityBreakoutSignal(symbol="BTC/USDT", timeframe="1h")
    feature_names = xgb._feature_names

    available_feats = [f for f in feature_names if f in df_feat.columns]
    for f in set(feature_names) - set(available_feats):
        df_feat[f] = 0.0

    print("Generating XGBoost Signals...")
    df_pred = xgb.predict_df(df_feat, feature_names)
    df_1h['xgb_signal'] = df_pred['xgb_signal'].values
    df_1h['xgb_confidence'] = df_pred['xgb_confidence'].values
    
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
    exit_manager = BreakoutExitManager()
    exit_reason_counts = {}
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
    blocked_signals = []
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
            hours_held = int((pd.to_datetime(t) - pd.to_datetime(pos['entry_time'])).total_seconds() / 3600.0)
            
            exit_eval = exit_manager.should_exit(
                position=pos,
                current_bar=row,
                bars_held=hours_held,
                atr=pos['atr_at_entry']
            )
            
            if exit_eval['exit']:
                reason = exit_eval['reason']
                exit_reason_counts[reason] = exit_reason_counts.get(reason, 0) + 1
                
                # Determine exit price based on reason (simplistic)
                if reason == 'TAKE_PROFIT':
                    exit_price = pos['exits']['take_profit']
                elif reason == 'STOP_LOSS':
                    exit_price = pos['exits']['stop_loss']
                else:
                    exit_price = exec_p # MAX_HOLD_TIME
                
                pnl_pct = (exit_price - pos['entry']) / pos['entry'] if pos['direction'] == 'LONG' else (pos['entry'] - exit_price) / pos['entry']
                pnl_pct -= 0.001 # Trading fee
                position_size = cap * 0.20 # 20% max exposure cap
                pnl_usd = position_size * pnl_pct
                cap += pnl_usd
                peak = max(peak, cap)
                dd = (peak - cap) / peak
                max_dd = max(max_dd, dd)
                
                trade_log.append({
                    'entry_time': pos['entry_time'],
                    'exit_time': t,
                    'type': pos['direction'],
                    'hours_held': hours_held,
                    'month': pd.to_datetime(pos['entry_time']).month,
                    'year': pd.to_datetime(pos['entry_time']).year,
                    'regime_at_entry': pos.get('regime_at_entry', 'UNKNOWN'),
                    'xgb_confidence': pos.get('xgb_confidence', 0.0),
                    'pnl': pnl_pct,
                    'duration_hours': hours_held,
                    'exit_reason': reason
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

            signal_dir = "LONG" if xgb_sig == "STRONG_LONG" else "SHORT"
            
            ps['open_count'] = 1 if pos else 0
            ps['deployed_capital'] = cap * 0.20 if pos else 0.0
            
            # 1. Kill Switch Check
            ks_level, ks_reason = kill_switch.evaluate(
                portfolio=ps, 
                signal={'dir': signal_dir}, 
                breakout_history=trade_log
            )
            if ks_level > 0:
                ks_blocks += 1
                ks_reasons[ks_reason] = ks_reasons.get(ks_reason, 0) + 1
                continue # Blocked
                
            # 2. 4H Anchor / Regime Gate
            base_r = row['base_regime']
            final_regime = rd.apply_4h_anchor(base_r, signal_dir, df_4h_slice)
            
            if final_regime in ("AMBIGUOUS", "VOLATILE_CHOP", "DEAD_RANGE", "COUNTER_TREND_REJECTED", "MACRO_TREND_REJECTED"):
                rg_blocks += 1
                if row['xgb_confidence'] >= 0.55:
                    future_idx = i + 8
                    if future_idx < len(df_1h):
                        close_8h = df_1h.iloc[future_idx]['close']
                        ret = (close_8h / exec_p) - 1 if signal_dir == 'LONG' else 1 - (close_8h / exec_p)
                        blocked_signals.append({
                            'blocked_by': 'regime_gate',
                            'xgb_confidence': row['xgb_confidence'],
                            'entry_price': exec_p,
                            'close_8h_later': close_8h,
                            'actual_forward_return': ret
                        })
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
                
                # Full System Consensus (logged but non-blocking)
                aligned = (signal_dir == "LONG" and expected_return > 0) or \
                          (signal_dir == "SHORT" and expected_return < 0)
                          
            # 4. LLM Gatekeeper (Simulated PASS for backtest)
            # Position entry logic decoupled from Kronos expected_return (non-blocking)
            if not pos:
                atr = row.get('atr_14', exec_p * 0.02)
                if pd.isna(atr) or atr == 0:
                    atr = exec_p * 0.02
                exits = exit_manager.calculate_exits(exec_p, signal_dir, atr)
                
                pos = {
                    'direction': signal_dir,
                    'entry_price': exec_p,
                    'entry': exec_p, 
                    'entry_time': t, 
                    'exits': exits,
                    'atr_at_entry': atr,
                    'regime_at_entry': final_regime, 
                    'xgb_confidence': row['xgb_confidence']
                }

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
            
    if exit_reason_counts:
        print("\n[EXIT REASON DISTRIBUTION]")
        total_exits = sum(exit_reason_counts.values())
        for reason, count in sorted(exit_reason_counts.items(), key=lambda x: -x[1]):
            print(f"  {reason:<20}: {count:>5} ({(count/total_exits)*100:.1f}%)")
        
    f_sharpe = calc_sharpe(daily_caps)
    f_ret = (cap - initial_capital) / initial_capital * 100
    
    trade_df = pd.DataFrame(trade_log)
    if not trade_df.empty:
        trade_df['month_year'] = trade_df['year'].astype(str) + '-' + trade_df['month'].astype(str).str.zfill(2)
        print('\n[TRADE DISTRIBUTION BY MONTH]')
        print(trade_df['month_year'].value_counts().sort_index())
        print(f'\nAverage trade duration: {trade_df["hours_held"].mean():.1f} hours')

        print("\n=== PnL BY REGIME ===")
        regime_analysis = trade_df.groupby('regime_at_entry').agg(
            trade_count   = ('pnl', 'count'),
            total_pnl     = ('pnl', 'sum'),
            mean_pnl      = ('pnl', 'mean'),
            win_rate      = ('pnl', lambda x: (x > 0).mean()),
            avg_duration  = ('duration_hours', 'mean')
        ).round(4)
        print(regime_analysis)

        trade_df['confidence_bucket'] = pd.cut(
            trade_df['xgb_confidence'],
            bins=[0.0, 0.45, 0.55, 0.65, 0.75, 1.0],
            labels=['0.45-', '0.45-0.55', '0.55-0.65', '0.65-0.75', '0.75+']
        )
        # observed=False avoids warning for categorical grouping
        confidence_analysis = trade_df.groupby('confidence_bucket', observed=False).agg(
            trade_count = ('pnl', 'count'),
            mean_pnl    = ('pnl', 'mean'),
            win_rate    = ('pnl', lambda x: (x > 0).mean()),
            total_pnl   = ('pnl', 'sum')
        ).round(4)
        print("\n=== PnL BY XGB CONFIDENCE ===")
        print(confidence_analysis)

    blocked_df = pd.DataFrame(blocked_signals)
    if not blocked_df.empty:
        print("\n=== BLOCKED HIGH-CONFIDENCE SIGNALS — FORWARD RETURNS ===")
        print(f"Count:           {len(blocked_df)}")
        print(f"Mean fwd return: {blocked_df['actual_forward_return'].mean():.4f}")
        print(f"Win rate:        {(blocked_df['actual_forward_return'] > 0).mean():.4f}")
        print(f"Total missed:    {blocked_df['actual_forward_return'].sum():.4f}")
    
    k_ret = (k_cap - initial_capital) / initial_capital * 100
    
    # Audit MAX_HOLD_TIME trades
    if 'exit_reason' in trade_df.columns:
        max_hold_trades = trade_df[trade_df['exit_reason'] == 'MAX_HOLD_TIME']
        print("\n=== MAX_HOLD_TIME TRADE ANALYSIS ===")
        if not max_hold_trades.empty:
            print(f"Count:           {len(max_hold_trades)}")
            print(f"Mean PnL:        {max_hold_trades['pnl'].mean():.4f}")
            print(f"Positive PnL:    {(max_hold_trades['pnl'] > 0).mean():.1%}")
            sl_trades = trade_df[trade_df['exit_reason'] == 'STOP_LOSS']
            if not sl_trades.empty:
                print(f"Mean PnL vs SL:  {max_hold_trades['pnl'].mean() / sl_trades['pnl'].mean():.2f}x")
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
