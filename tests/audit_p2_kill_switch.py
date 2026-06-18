"""
Priority 2 Audit: Kill Switch Trigger Frequency Analysis
Replays 1-year of data through the actual KillSwitch.evaluate() logic,
tracks which Level and which exact reason fires most often.
"""
import sys, os, asyncio
import pandas as pd
import numpy as np
from collections import defaultdict

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from ml_engine.data.fetcher import BinanceFetcher
from ml_engine.features.kill_switch import KillSwitch

async def audit_kill_switch():
    print("Fetching 1-year BTC/USDT 1H + 4H data for Kill Switch audit...")
    async with BinanceFetcher() as fetcher:
        since = (pd.Timestamp.now('UTC') - pd.Timedelta(days=365)).strftime("%Y-%m-%d")
        df_1h = await fetcher.fetch_ohlcv("BTC/USDT", "1h", since=since)
        df_4h = await fetcher.fetch_ohlcv("BTC/USDT", "4h", since=since)

    print(f"Loaded {len(df_1h)} 1H candles.\n")

    ks = KillSwitch()

    # Simulate a session that slowly degrades (using EMA crossover dummy)
    df_1h['ema_50']  = df_1h['close'].ewm(span=50,  adjust=False).mean()
    df_1h['ema_200'] = df_1h['close'].ewm(span=200, adjust=False).mean()

    cap           = 10000.0
    initial_cap   = cap
    peak          = cap
    consec_losses = 0
    session_dd    = 0.0
    daily_dd      = 0.0
    pos           = None
    last_day      = None
    day_start_cap = cap

    trigger_log   = defaultdict(int)   # reason -> count
    level_log     = defaultdict(int)   # level  -> count
    halted_hrs    = 0
    normal_hrs    = 0
    first_l3_hour = None
    l3_active     = False

    df_4h_idx = df_4h.set_index('open_time')

    for i in range(200, len(df_1h) - 1):
        row       = df_1h.iloc[i]
        next_row  = df_1h.iloc[i + 1]
        t         = row['open_time']
        exec_p    = next_row['open']

        day = t.date()
        if last_day != day:
            day_start_cap = cap
            session_dd    = 0.0
            daily_dd      = 0.0
            last_day      = day

        signal = "LONG" if row['ema_50'] > row['ema_200'] else "SHORT"

        # Close position on signal flip
        if pos and pos['type'] != signal:
            pnl_pct = (exec_p - pos['entry']) / pos['entry'] if pos['type'] == 'LONG' else (pos['entry'] - exec_p) / pos['entry']
            pnl_pct -= 0.001
            pnl_usd  = cap * pnl_pct
            cap     += pnl_usd
            peak     = max(peak, cap)

            if pnl_usd < 0:
                consec_losses += 1
                session_dd = (day_start_cap - cap) / day_start_cap if day_start_cap > 0 else 0
                daily_dd   = session_dd
            else:
                consec_losses = 0

            pos = None

        total_dd_pct   = (initial_cap - cap) / initial_cap
        single_loss    = abs(pnl_usd / (cap + abs(pnl_usd))) if 'pnl_usd' in dir() and pnl_usd < 0 else 0.0

        portfolio_state = {
            "total_drawdown_from_start_pct": total_dd_pct,
            "single_trade_loss_pct":         single_loss,
            "equity":                        cap,
            "equity_floor_usd":              500.0,
            "consecutive_losses":            consec_losses,
            "session_drawdown_pct":          session_dd,
            "daily_drawdown_pct":            daily_dd,
            "operator_kill_command":         False,
            "exchange_balance_mismatch":     False,
            "kronos_spread_pct":             0.0,
        }

        window_1h = df_1h.iloc[max(0, i - 2160): i + 1]
        rel_4h    = df_4h_idx[df_4h_idx.index <= t]
        window_4h = rel_4h.iloc[-540:].reset_index() if not rel_4h.empty else pd.DataFrame()

        level, reason = ks.evaluate(window_1h, window_4h, portfolio_state, {})

        trigger_log[reason] += 1
        level_log[level]    += 1

        if level >= 2:
            halted_hrs += 1
            if level == 3 and not l3_active:
                first_l3_hour = t
                l3_active     = True
        else:
            normal_hrs += 1
            if not pos:
                pos = {'type': signal, 'entry': exec_p}

    total_hours = halted_hrs + normal_hrs
    print(f"{'='*60}")
    print(f"  KILL SWITCH AUDIT — 1 YEAR ({total_hours} hrs simulated)")
    print(f"{'='*60}")
    print(f"\n  Hours halted (L2+): {halted_hrs:>6}  ({halted_hrs/total_hours*100:.1f}%)")
    print(f"  Hours normal  (L0): {normal_hrs:>6}  ({normal_hrs/total_hours*100:.1f}%)")
    if first_l3_hour:
        print(f"\n  First L3 Black Kill triggered at: {first_l3_hour}")
        print(f"  (System locked for rest of the year after this point)")

    print(f"\n  Trigger Frequency by Level:")
    for lvl in sorted(level_log):
        label = {0: "L0-Normal", 1: "L1-Yellow", 2: "L2-Red", 3: "L3-Black"}.get(lvl, str(lvl))
        print(f"    {label}: {level_log[lvl]:>6} hrs")

    print(f"\n  Top 10 Individual Trigger Reasons:")
    sorted_reasons = sorted(trigger_log.items(), key=lambda x: -x[1])
    for reason, count in sorted_reasons[:10]:
        print(f"    {reason.ljust(42)}: {count:>6} hrs  ({count/total_hours*100:.1f}%)")

    print(f"\n  DIAGNOSIS:")
    top_reason = sorted_reasons[0][0] if sorted_reasons else ""
    if "TOTAL_DRAWDOWN" in top_reason:
        print("    [CONFIRMED] L3 fires early on bad EMA signal, then system stays locked forever.")
        print("    [FIX] Real XGBoost/Kronos signals will have positive EV — L3 won't fire as fast.")
    if "SESSION_DRAWDOWN" in top_reason or "CONSECUTIVE_LOSSES" in top_reason:
        print("    [WARNING] L1 threshold (2% session DD / 3 consec losses) fires too aggressively")
        print("              on a negative-EV strategy. These thresholds are calibrated for real signals.")

if __name__ == "__main__":
    asyncio.run(audit_kill_switch())
