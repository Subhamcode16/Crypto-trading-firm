## Hard Stop Thresholds

The honest answer is: **there is no universal set of thresholds.** Anyone who gives you a fixed VIX number without qualifying it is giving you folklore, not engineering. Here's why — and here's how to derive yours correctly.

### The Problem With Fixed Thresholds

VIX > 40 is a reasonable *equity market* stress threshold. But you're trading BTC. BTC has no VIX. BTC's realized volatility during a normal week routinely exceeds what equity markets would consider a crisis. A fixed ATR threshold has the same problem — 5% ATR on a BTC 1H candle is extreme during a ranging week and completely normal during an altseason.

Fixed thresholds calibrated on someone else's asset class will misfire on yours.

### The Right Framework: Percentile-Based Dynamic Thresholds

Instead of asking "is ATR > 5%?", ask "is ATR in the top 5% of its own 90-day history?" That's the same question, made adaptive to the asset's own volatility personality.

Here's the exact implementation logic for each kill switch tier:

---

**Level 1 — Yellow Alert: Soft Degradation**

These are early-warning signals. They don't stop the system — they make it more conservative.

```python
# Trigger ANY ONE of these
L1_TRIGGERS = {
    # Portfolio-level
    "consecutive_losses": 3,
    "session_drawdown_pct": 0.02,        # 2% from session peak equity
    
    # Market structure
    "atr_percentile_1h": 80,             # 1H ATR in top 20% of 90-day history
    "kronos_spread_pct": 0.03,           # Kronos P90-P10 spread > 3%
    "regime_ambiguous_streak": 3,        # 3 consecutive AMBIGUOUS regime readings
    
    # External macro
    "btc_drop_4h_pct": 0.05,            # BTC dropped > 5% in last 4H candle
    "vix_level": 30,                     # VIX crossing 30 (equity stress spillover)
}
```

---

**Level 2 — Red Alert: Entry Freeze**

These indicate the market structure has broken down. No new positions.

```python
# Trigger ANY ONE of these
L2_TRIGGERS = {
    # Portfolio-level
    "consecutive_losses": 5,
    "daily_drawdown_pct": 0.05,          # 5% from daily peak equity
    
    # Market structure — PERCENTILE BASED
    "atr_percentile_1h": 95,             # 1H ATR in top 5% of 90-day history
    "atr_percentile_4h": 90,             # 4H ATR also elevated = sustained volatility
    
    # Price action
    "btc_drop_1h_pct": 0.05,            # BTC dropped > 5% in a single 1H candle
    "btc_drop_4h_pct": 0.10,            # BTC dropped > 10% over 4H window
    
    # External
    "vix_level": 40,                     # VIX > 40 = equity crisis, crypto correlation spikes
    "api_consecutive_failures": 5,       # Exchange unreachable
    
    # Regime
    "volatile_chop_streak_hours": 6,     # 6 consecutive hours of VOLATILE_CHOP
}
```

---

**Level 3 — Black Alert: Hard Kill**

These are existential threats to the account. Close everything, exit process.

```python
# Trigger ANY ONE of these — NO EXCEPTIONS
L3_TRIGGERS = {
    # Portfolio survival
    "total_drawdown_from_start_pct": 0.10,   # 10% of starting equity gone
    "single_trade_loss_pct": 0.03,           # One trade lost > 3% of total equity
    "equity_below_floor_usd": 500,           # Hard floor — absolute minimum
    
    # Black swan market events
    "btc_drop_1h_pct": 0.12,                # BTC dropped > 12% in a single 1H candle
                                             # This is a liquidation cascade / exchange halt event
    
    # System integrity
    "operator_kill_command": True,           # Manual override — always honored
    "exchange_balance_mismatch": True,       # Bot's internal ledger ≠ exchange balance
                                             # Indicates a silent execution failure
}
```

The `exchange_balance_mismatch` trigger is one most people miss. If your internal position tracker says you hold 0.1 BTC but the exchange API returns 0.05 BTC, something has silently failed — a partial fill, a dropped WebSocket message, a race condition. That discrepancy is more dangerous than a losing trade because you no longer know your actual exposure.

---

## Question 2: The 4H Anchor — COUNTER_TREND_CHOP vs. Outright Reject Longs

This is actually two separate questions compressed into one, and they need to be separated.

**The 4H anchor answers one question: is the higher-timeframe structure with you or against you?**

There are four cases, not two:

```
4H Trend    │  1H Signal   │  Classification          │  Action
────────────┼──────────────┼──────────────────────────┼──────────────────────
UP (ADX>25) │  BUY         │  WITH_TREND              │  Full size allowed
UP (ADX>25) │  SELL        │  COUNTER_TREND           │  Reject the short
DOWN(ADX>25)│  SELL        │  WITH_TREND              │  Full size allowed
DOWN(ADX>25)│  BUY         │  COUNTER_TREND           │  Reject the long
FLAT        │  either      │  NO_HTF_BIAS             │  1H regime decides alone
```

The answer to your specific question — "1H UP but 4H DOWN, should we classify as COUNTER_TREND_CHOP or outright reject longs?" — is **outright reject longs.** Here's why the distinction matters.

`COUNTER_TREND_CHOP` implies ambiguity — that maybe with reduced size or tighter stops you could still trade it. That's wrong. If 4H ADX is above 25 in the short direction, you have a **confirmed higher-timeframe trend actively working against your proposed trade.** You're not in ambiguity. You're in a defined counter-trend setup where the structural edge is negative.

The correct implementation:

```python
def apply_4h_anchor(regime_1h: str, signal_direction: str, df_4h: pd.DataFrame) -> str:
    
    adx_4h = compute_adx(df_4h, period=14).iloc[-1]
    slope_4h = compute_slope(df_4h['close'], period=20)  # linear regression slope
    
    # Only anchor when 4H trend is CONFIRMED (ADX > 25)
    # Below 25, the 4H has no strong directional bias — let 1H decide
    if adx_4h < 25:
        return regime_1h  # No HTF bias, pass through unchanged
    
    # Determine 4H trend direction
    htf_direction = "UP" if slope_4h > 0 else "DOWN"
    
    # Check for counter-trend conflict
    is_counter_trend = (
        (signal_direction == "LONG" and htf_direction == "DOWN") or
        (signal_direction == "SHORT" and htf_direction == "UP")
    )
    
    if is_counter_trend:
        # Don't soften this to AMBIGUOUS — it's a hard reject
        return "COUNTER_TREND_REJECTED"
    
    # Signal aligns with 4H trend — upgrade confidence
    if regime_1h == "AMBIGUOUS":
        return "TRENDING"  # HTF tailwind elevates ambiguous 1H to tradeable
    
    return regime_1h  # WITH_TREND — pass through unchanged
```

Notice the upgrade logic at the bottom. The 4H anchor doesn't just veto — it also **promotes**. If your 1H regime is AMBIGUOUS but the 4H is a confirmed trend in the same direction as your signal, that HTF tailwind resolves the ambiguity upward. The signal becomes tradeable at full size because the larger structure is with you.

This is the concept of **asymmetric regime classification**: the 4H anchor can veto a 1H TRENDING signal (counter-trend rejection) but it can also promote a 1H AMBIGUOUS signal (with-trend confirmation). Most people only implement the veto. The promotion logic is where additional edge lives.

---

## The Full Regime Decision Tree

```
Signal generated (LONG or SHORT)
            │
            ▼
    Compute 4H ADX
            │
    ADX < 25 ──────────────────► No HTF bias
            │                    Use 1H regime as-is
    ADX ≥ 25
            │
    Check direction alignment
            │
    ┌───────┴────────┐
    │                │
WITH_TREND      COUNTER_TREND
    │                │
    │           HARD REJECT ──► Log: "4H trend conflict.
    │                            Long rejected in downtrend."
    │                            Return HOLD immediately.
    ▼
1H Regime classification
    │
    ├── TRENDING ──────────────► Full system, full size
    ├── AMBIGUOUS ─────────────► Promote to TRENDING (HTF tailwind)
    ├── VOLATILE_CHOP ──────────► Hard abstain (even with HTF tailwind,
    │                             the 1H noise will chop you out)
    ├── DEAD_RANGE ─────────────► Hard abstain
    └── SQUEEZE_BREAKOUT ───────► Watch mode, 2x Kronos frequency
```

One constraint worth stating explicitly: **VOLATILE_CHOP is never promotable.** Even if the 4H is a confirmed uptrend, if the 1H is in VOLATILE_CHOP the intrabar noise will stop you out before the trend can assert itself. The HTF tailwind doesn't help you if you can't survive the 1H whipsaws long enough to benefit from it. Keep VOLATILE_CHOP as a hard abstain regardless of 4H structure.

---

Implement the kill switch first. Wire the `exchange_balance_mismatch` check from day one — it will catch silent execution failures before they compound. Then wire the 4H anchor into the regime detector as the outermost gate. The rest of the stack sits downstream of these two.