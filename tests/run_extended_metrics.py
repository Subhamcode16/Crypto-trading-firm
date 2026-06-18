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
    print("Fetching 1-year historical data for extended metrics...")
    async with BinanceFetcher() as fetcher:
        since_date = (pd.Timestamp.now('UTC') - pd.Timedelta(days=365)).strftime("%Y-%m-%d")
        df_1h = await fetcher.fetch_ohlcv("BTC/USDT", "1h", since=since_date)
        df_4h = await fetcher.fetch_ohlcv("BTC/USDT", "4h", since=since_date)
        
    df_1h['ema_50'] = df_1h['close'].ewm(span=50, adjust=False).mean()
    df_1h['ema_200'] = df_1h['close'].ewm(span=200, adjust=False).mean()
    
    regime_detector = RegimeDetector()
    df_1h['adx'] = regime_detector.compute_adx(df_1h, 14)
    df_1h['er'] = regime_detector.compute_er(df_1h, 14)
    bb_width = regime_detector.compute_bb_width(df_1h, 20)
    df_1h['bb_width_pctile'] = bb_width.rolling(200).apply(
        lambda x: (x < x.iloc[-1]).mean() * 100 if len(x.dropna()) > 0 else 50.0
    ).fillna(50.0)
    
    df_4h['adx_4h'] = regime_detector.compute_adx(df_4h, 14)
    df_4h['slope_4h'] = df_4h['close'].rolling(20).apply(lambda x: np.polyfit(np.arange(20), x, 1)[0] if len(x) == 20 else 0.0).fillna(0.0)
    
    df_4h_indexed = df_4h.set_index('open_time')
    
    initial_capital = 10000.0
    
    class Tracker:
        def __init__(self):
            self.cap = initial_capital
            self.pos = None
            self.trades = 0
            self.wins = 0
            self.gross_profit = 0.0
            self.gross_loss = 0.0
            self.durations = []
            self.equity_curve = []
            self.peak = initial_capital
            self.max_dd = 0.0
            
        def close_pos(self, exec_price, exec_time, is_system=False):
            if not self.pos: return
            pnl_pct = (exec_price - self.pos['entry_price']) / self.pos['entry_price'] if self.pos['type'] == 'LONG' else (self.pos['entry_price'] - exec_price) / self.pos['entry_price']
            pnl_pct -= 0.001 # fee
            pnl_usd = self.cap * pnl_pct
            self.cap += pnl_usd
            
            if pnl_usd > 0:
                self.wins += 1
                self.gross_profit += pnl_usd
            else:
                self.gross_loss += abs(pnl_usd)
                
            self.trades += 1
            duration = (exec_time - self.pos['entry_time']).total_seconds() / 3600.0
            self.durations.append(duration)
            
            self.peak = max(self.peak, self.cap)
            dd = (self.peak - self.cap) / self.peak
            self.max_dd = max(self.max_dd, dd)
            self.pos = None

    base = Tracker()
    sys_tracker = Tracker()
    
    blocks = 0
    abstains = 0
    regime_wins = {}
    regime_losses = {}
    
    last_day = None
    base_daily = []
    sys_daily = []
    
    print("Simulating...")
    for i in range(200, len(df_1h) - 1):
        current_1h = df_1h.iloc[i]
        next_candle = df_1h.iloc[i+1]
        t = current_1h['open_time']
        exec_price = next_candle['open']
        exec_time = next_candle['open_time']
        
        day = t.date()
        if last_day and day != last_day:
            base_daily.append(base.cap)
            sys_daily.append(sys_tracker.cap)
        last_day = day
        
        baseline_signal = "LONG" if current_1h['ema_50'] > current_1h['ema_200'] else "SHORT"
        
        if base.pos is None:
            base.pos = {'type': baseline_signal, 'entry_price': exec_price, 'entry_time': exec_time}
        elif base.pos['type'] != baseline_signal:
            base.close_pos(exec_price, exec_time)
            base.pos = {'type': baseline_signal, 'entry_price': exec_price, 'entry_time': exec_time}
            
        base_regime = regime_detector.classify_1h_regime(current_1h['adx'], current_1h['er'], current_1h['bb_width_pctile'])
        relevant_4h = df_4h_indexed[df_4h_indexed.index <= t]
        regime = base_regime
        
        if not relevant_4h.empty and base_regime != "VOLATILE_CHOP":
            last_4h = relevant_4h.iloc[-1]
            if last_4h['adx_4h'] >= 25:
                htf_direction = "UP" if last_4h['slope_4h'] > 0 else "DOWN"
                is_counter = (baseline_signal == "LONG" and htf_direction == "DOWN") or (baseline_signal == "SHORT" and htf_direction == "UP")
                if is_counter:
                    regime = "COUNTER_TREND_REJECTED"
                elif base_regime == "AMBIGUOUS":
                    is_with = (baseline_signal == "LONG" and htf_direction == "UP") or (baseline_signal == "SHORT" and htf_direction == "DOWN")
                    if is_with: regime = "TRENDING"
                    
        dd_pct = (initial_capital - sys_tracker.cap) / initial_capital
        ks_level = 3 if dd_pct >= 0.10 else 0
        
        final_decision = baseline_signal
        if ks_level >= 2:
            final_decision = "HOLD"
            blocks += 1
        elif regime in ["VOLATILE_CHOP", "DEAD_RANGE", "COUNTER_TREND_REJECTED"]:
            final_decision = "HOLD"
            abstains += 1
            
        if final_decision != "HOLD":
            if sys_tracker.pos is None:
                sys_tracker.pos = {'type': final_decision, 'entry_price': exec_price, 'entry_time': exec_time, 'regime': regime}
            elif sys_tracker.pos['type'] != final_decision:
                trade_regime = sys_tracker.pos['regime']
                pnl_before = sys_tracker.cap
                sys_tracker.close_pos(exec_price, exec_time, True)
                pnl_after = sys_tracker.cap
                
                if pnl_after > pnl_before:
                    regime_wins[trade_regime] = regime_wins.get(trade_regime, 0) + 1
                else:
                    regime_losses[trade_regime] = regime_losses.get(trade_regime, 0) + 1
                    
                sys_tracker.pos = {'type': final_decision, 'entry_price': exec_price, 'entry_time': exec_time, 'regime': regime}
        else:
            if sys_tracker.pos is not None:
                trade_regime = sys_tracker.pos['regime']
                pnl_before = sys_tracker.cap
                sys_tracker.close_pos(exec_price, exec_time, True)
                pnl_after = sys_tracker.cap
                if pnl_after > pnl_before:
                    regime_wins[trade_regime] = regime_wins.get(trade_regime, 0) + 1
                else:
                    regime_losses[trade_regime] = regime_losses.get(trade_regime, 0) + 1

    def calc_sharpe(daily_eq):
        if not daily_eq or len(daily_eq) < 2: return 0.0
        returns = pd.Series(daily_eq).pct_change().dropna()
        if returns.std() == 0: return 0.0
        return (returns.mean() / returns.std()) * np.sqrt(365)
        
    base_sharpe = calc_sharpe(base_daily)
    sys_sharpe = calc_sharpe(sys_daily)
    
    print("\n" + "="*50)
    print("1-YEAR COMPREHENSIVE METRICS COMPARISON")
    print("="*50)
    
    def print_metrics(name, t, sharpe):
        pf = (t.gross_profit / t.gross_loss) if t.gross_loss > 0 else float('inf')
        avg_dur = np.mean(t.durations) if t.durations else 0.0
        win_rate = (t.wins / max(1, t.trades)) * 100
        print(f"--- {name} ---")
        print(f"Max Drawdown:          {t.max_dd*100:.2f}%")
        print(f"Sharpe Ratio:          {sharpe:.2f}")
        print(f"Win Rate:              {win_rate:.2f}% ({t.wins}/{t.trades})")
        print(f"Average Duration:      {avg_dur:.1f} hours")
        print(f"Profit Factor:         {pf:.2f}")
        print(f"Final Capital:         ${t.cap:.2f}\n")
        
    print_metrics("BASELINE (Unfiltered 50/200 EMA)", base, base_sharpe)
    print_metrics("NEW SYSTEM (EMA + Regimes + Kill Switch)", sys_tracker, sys_sharpe)
    
    total_hours = len(df_1h) - 200
    abs_rate = (abstains / total_hours) * 100
    print(f"Abstention Rate:       {abs_rate:.2f}% ({abstains} hours blocked by Regime Gate)")
    print(f"Kill Switch Blocks:    {blocks} hours halted due to DD limits")
    
    print("\nWin Rate per Regime:")
    for r in set(list(regime_wins.keys()) + list(regime_losses.keys())):
        w = regime_wins.get(r, 0)
        l = regime_losses.get(r, 0)
        t = w + l
        if t > 0:
            print(f"  {r.ljust(25)}: {w/t*100:.1f}% ({w}/{t})")

if __name__ == "__main__":
    asyncio.run(run_backtest())
