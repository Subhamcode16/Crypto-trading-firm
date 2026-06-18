import sys
import os
import asyncio
import pandas as pd
import numpy as np

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from ml_engine.data.fetcher import BinanceFetcher
from ml_engine.features.kill_switch import KillSwitch
from ml_engine.features.regime_detector import RegimeDetector

async def run_backtest():
    print("Fetching 5-year historical data for walk-forward backtest...")
    async with BinanceFetcher() as fetcher:
        since_date = (pd.Timestamp.utcnow() - pd.Timedelta(days=1825)).strftime("%Y-%m-%d")
        df_1h = await fetcher.fetch_ohlcv("BTC/USDT", "1h", since=since_date)
        df_4h = await fetcher.fetch_ohlcv("BTC/USDT", "4h", since=since_date)
        
    print(f"Loaded {len(df_1h)} 1H candles and {len(df_4h)} 4H candles.")
    
    # Pre-calculate ALL indicators vectorized to avoid O(N^2) loop
    df_1h['ema_50'] = df_1h['close'].ewm(span=50, adjust=False).mean()
    df_1h['ema_200'] = df_1h['close'].ewm(span=200, adjust=False).mean()
    
    regime_detector = RegimeDetector()
    kill_switch = KillSwitch()
    
    # Pre-compute regime features on full dataset
    df_1h['adx'] = regime_detector.compute_adx(df_1h, 14)
    df_1h['er'] = regime_detector.compute_er(df_1h, 14)
    bb_width = regime_detector.compute_bb_width(df_1h, 20)
    
    df_1h['bb_width_pctile'] = bb_width.rolling(200).apply(
        lambda x: (x < x.iloc[-1]).mean() * 100 if len(x.dropna()) > 0 else 50.0
    ).fillna(50.0)
    
    # 4H features
    df_4h['adx_4h'] = regime_detector.compute_adx(df_4h, 14)
    df_4h['slope_4h'] = df_4h['close'].rolling(20).apply(lambda x: np.polyfit(np.arange(20), x, 1)[0] if len(x) == 20 else 0.0).fillna(0.0)
    
    # Portfolio State
    initial_capital = 10000.0
    
    system_capital = initial_capital
    baseline_capital = initial_capital
    
    system_positions = []
    baseline_positions = []
    
    metrics = {
        'total_trades': 0,
        'winning_trades': 0,
        'abstained_trades': 0,
        'kill_switch_blocks': 0,
        'regime_stats': {r: {'wins': 0, 'losses': 0} for r in ['TRENDING', 'AMBIGUOUS', 'VOLATILE_CHOP', 'DEAD_RANGE', 'SQUEEZE_BREAKOUT', 'COUNTER_TREND_REJECTED']},
        'max_drawdown': 0.0,
        'peak_capital': initial_capital,
    }
    
    # Map 4H data to 1H index for fast lookup
    df_4h_indexed = df_4h.set_index('open_time')
    
    print("Running Backtest Loop...")
    for i in range(200, len(df_1h) - 1):
        if i % 1000 == 0:
            print(f"Processed {i}/{len(df_1h)} steps")
            
        current_1h = df_1h.iloc[i]
        next_candle = df_1h.iloc[i+1]
        
        # 1. Baseline Strategy
        baseline_signal = "LONG" if current_1h['ema_50'] > current_1h['ema_200'] else "SHORT"
        
        exec_price = next_candle['open']
        if not baseline_positions:
            baseline_positions.append({'type': baseline_signal, 'entry': exec_price})
        else:
            if baseline_positions[0]['type'] != baseline_signal:
                entry = baseline_positions[0]['entry']
                pnl = (exec_price - entry) / entry if baseline_positions[0]['type'] == 'LONG' else (entry - exec_price) / entry
                baseline_capital *= (1 + pnl)
                baseline_positions[0] = {'type': baseline_signal, 'entry': exec_price}
                
        # 2. System Architecture Logic
        proposed_signal = baseline_signal 
        
        # Fast Kill Switch 
        # (Mocking simple evaluation so it's fast)
        portfolio_state = {"total_drawdown_from_start_pct": (initial_capital - system_capital) / initial_capital, "consecutive_losses": 0}
        
        # Check Level 3
        ks_level = 0
        if portfolio_state['total_drawdown_from_start_pct'] >= 0.10:
            ks_level = 3
        
        # Fast Regime Detection
        base_regime = regime_detector.classify_1h_regime(current_1h['adx'], current_1h['er'], current_1h['bb_width_pctile'])
        
        # 4H anchor
        # Find latest 4H candle
        t = current_1h['open_time']
        relevant_4h = df_4h_indexed[df_4h_indexed.index <= t]
        regime = base_regime
        
        if not relevant_4h.empty and base_regime != "VOLATILE_CHOP":
            last_4h = relevant_4h.iloc[-1]
            adx_4h = last_4h['adx_4h']
            slope_4h = last_4h['slope_4h']
            
            if adx_4h >= 25:
                htf_direction = "UP" if slope_4h > 0 else "DOWN"
                is_counter_trend = (
                    (proposed_signal == "LONG" and htf_direction == "DOWN") or
                    (proposed_signal == "SHORT" and htf_direction == "UP")
                )
                
                if is_counter_trend:
                    regime = "COUNTER_TREND_REJECTED"
                elif base_regime == "AMBIGUOUS" and proposed_signal in ["LONG", "SHORT"]:
                    is_with_trend = (
                        (proposed_signal == "LONG" and htf_direction == "UP") or
                        (proposed_signal == "SHORT" and htf_direction == "DOWN")
                    )
                    if is_with_trend:
                        regime = "TRENDING"
        
        # System Decision Gate
        final_decision = proposed_signal
        
        if ks_level >= 2:
            final_decision = "HOLD"
            metrics['kill_switch_blocks'] += 1
        elif regime in ["VOLATILE_CHOP", "DEAD_RANGE", "COUNTER_TREND_REJECTED"]:
            final_decision = "HOLD"
            metrics['abstained_trades'] += 1
            
        # Execute System PnL
        if final_decision != "HOLD":
            if not system_positions:
                system_positions.append({'type': final_decision, 'entry': exec_price, 'regime': regime})
            else:
                if system_positions[0]['type'] != final_decision:
                    entry = system_positions[0]['entry']
                    trade_regime = system_positions[0]['regime']
                    
                    pnl = (exec_price - entry) / entry if system_positions[0]['type'] == 'LONG' else (entry - exec_price) / entry
                    # Simulate simple fees
                    pnl -= 0.001 
                    system_capital *= (1 + pnl)
                    
                    metrics['total_trades'] += 1
                    if pnl > 0:
                        metrics['winning_trades'] += 1
                        if trade_regime in metrics['regime_stats']:
                            metrics['regime_stats'][trade_regime]['wins'] += 1
                    else:
                        if trade_regime in metrics['regime_stats']:
                            metrics['regime_stats'][trade_regime]['losses'] += 1
                            
                    metrics['peak_capital'] = max(metrics['peak_capital'], system_capital)
                    dd = (metrics['peak_capital'] - system_capital) / metrics['peak_capital']
                    metrics['max_drawdown'] = max(metrics['max_drawdown'], dd)
                    
                    system_positions[0] = {'type': final_decision, 'entry': exec_price, 'regime': regime}
        else:
            if system_positions:
                entry = system_positions[0]['entry']
                trade_regime = system_positions[0]['regime']
                pnl = (exec_price - entry) / entry if system_positions[0]['type'] == 'LONG' else (entry - exec_price) / entry
                pnl -= 0.001
                system_capital *= (1 + pnl)
                metrics['total_trades'] += 1
                if pnl > 0:
                    metrics['winning_trades'] += 1
                    if trade_regime in metrics['regime_stats']:
                        metrics['regime_stats'][trade_regime]['wins'] += 1
                else:
                    if trade_regime in metrics['regime_stats']:
                        metrics['regime_stats'][trade_regime]['losses'] += 1
                system_positions = []
                
    print("\n================ WALK-FORWARD BACKTEST RESULTS (1 YEAR) ================")
    print(f"Baseline (EMA 50/200) Final Capital : ${baseline_capital:.2f} ({((baseline_capital-initial_capital)/initial_capital)*100:.2f}%)")
    print(f"New System Final Capital            : ${system_capital:.2f} ({((system_capital-initial_capital)/initial_capital)*100:.2f}%)")
    
    print(f"\nSystem Max Drawdown: {metrics['max_drawdown']*100:.2f}%")
    print(f"Total Trades Executed: {metrics['total_trades']}")
    print(f"Win Rate: {(metrics['winning_trades'] / max(1, metrics['total_trades']))*100:.2f}%")
    print(f"Abstained/Blocked Setups: {metrics['abstained_trades']} (Kill Switch Blocks: {metrics['kill_switch_blocks']})")
    
    print("\nWin Rate by Regime:")
    for r, stats in metrics['regime_stats'].items():
        t = stats['wins'] + stats['losses']
        if t > 0:
            print(f"  {r.ljust(25)}: {stats['wins']/t*100:.1f}% ({stats['wins']}/{t})")

if __name__ == "__main__":
    asyncio.run(run_backtest())
