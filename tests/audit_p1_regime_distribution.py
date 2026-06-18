"""
Priority 1 Audit: Regime Distribution Analysis
Pulls 1-year of BTC/USDT 1H data and reports the regime classification breakdown.
Also tests the effect of lowering ADX threshold from 25 → 20.
"""
import sys, os, asyncio
import pandas as pd
import numpy as np

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from ml_engine.data.fetcher import BinanceFetcher
from ml_engine.features.regime_detector import RegimeDetector

async def audit_regime_distribution():
    print("Fetching 1-year BTC/USDT 1H data for regime audit...")
    async with BinanceFetcher() as fetcher:
        since = (pd.Timestamp.now('UTC') - pd.Timedelta(days=365)).strftime("%Y-%m-%d")
        df_1h = await fetcher.fetch_ohlcv("BTC/USDT", "1h", since=since)
        df_4h = await fetcher.fetch_ohlcv("BTC/USDT", "4h", since=since)

    print(f"Loaded {len(df_1h)} 1H candles.\n")

    rd = RegimeDetector()

    df_1h['adx']  = rd.compute_adx(df_1h, 14)
    df_1h['er']   = rd.compute_er(df_1h, 14)
    bb_w = rd.compute_bb_width(df_1h, 20)
    df_1h['bb_pct'] = bb_w.rolling(200).apply(
        lambda x: (x < x.iloc[-1]).mean() * 100 if len(x.dropna()) > 0 else 50.0
    ).fillna(50.0)

    df_4h['adx_4h']   = rd.compute_adx(df_4h, 14)
    df_4h['slope_4h'] = df_4h['close'].rolling(20).apply(
        lambda x: np.polyfit(np.arange(20), x, 1)[0] if len(x) == 20 else 0.0
    ).fillna(0.0)
    df_4h_idx = df_4h.set_index('open_time')

    def classify(adx_thresh, row, t):
        adx, er, bbp = row['adx'], row['er'], row['bb_pct']
        if pd.isna(adx) or pd.isna(er): return "INSUFFICIENT_DATA"

        # ── 1H Base classification ──────────────────────────────────────────
        if adx > adx_thresh:
            if er < 0.3:
                base = "VOLATILE_CHOP"
            elif er > 0.5 and bbp > 50:
                base = "TRENDING"
            else:
                base = "AMBIGUOUS"
        elif adx < (adx_thresh - 5) and er < 0.3:
            base = "DEAD_RANGE" if bbp < 30 else ("SQUEEZE_BREAKOUT" if bbp > 70 else "AMBIGUOUS")
        else:
            base = "AMBIGUOUS"

        if base == "VOLATILE_CHOP":
            return base

        # ── 4H anchor ──────────────────────────────────────────────────────
        rel = df_4h_idx[df_4h_idx.index <= t]
        if rel.empty:
            return base
        last4 = rel.iloc[-1]
        if last4['adx_4h'] >= 25:
            htf = "UP" if last4['slope_4h'] > 0 else "DOWN"
            if base == "AMBIGUOUS":
                # If 4H is trending, elevate ambiguous (no signal direction here, count both)
                return "TRENDING"  # conservative: assume potential with-trend
        return base

    df_clean = df_1h.iloc[200:].copy()

    for adx_thresh, label in [(25, "Current (ADX>25)"), (20, "Proposed (ADX>20)")]:
        print(f"\n{'='*55}")
        print(f"  REGIME DISTRIBUTION — {label}")
        print(f"{'='*55}")
        regimes = df_clean.apply(lambda r: classify(adx_thresh, r, r['open_time']), axis=1)
        counts = regimes.value_counts()
        pcts   = (counts / len(regimes) * 100).round(2)
        for r, pct in pcts.items():
            flag = " <-- TARGET 25-35%" if r == "TRENDING" else ""
            flag += " [ACTIONABLE]" if r in ("TRENDING",) else " [BLOCKED]" if r in ("VOLATILE_CHOP","DEAD_RANGE","COUNTER_TREND_REJECTED") else ""
            print(f"  {r.ljust(28)}: {pct:6.2f}%  ({counts[r]:>5} hrs){flag}")

        trending_pct = pcts.get("TRENDING", 0.0)
        if trending_pct < 15:
            print(f"\n  [WARNING] TRENDING is only {trending_pct:.1f}% — BELOW 15% minimum target.")
            print(f"           ADX threshold should be LOWERED.")
        elif trending_pct > 35:
            print(f"\n  [WARNING] TRENDING is {trending_pct:.1f}% — ABOVE 35% maximum target.")
            print(f"           ADX threshold may be too permissive.")
        else:
            print(f"\n  [OK] TRENDING at {trending_pct:.1f}% — within 15-35% target range.")

if __name__ == "__main__":
    asyncio.run(audit_regime_distribution())
