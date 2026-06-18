# Regime Detection Layer — Architectural Proposal

> **Context:** Before the consensus layer makes any decision at all, the system must detect whether the market is currently in a trending regime vs. a mean-reverting / choppy regime — and gate the entire pipeline based on that answer.

---

## The Metrics: A Three-Signal Regime Classifier

No single indicator reliably classifies regimes. You need orthogonal signals that measure different properties of the market structure:

### Signal 1: ADX (Average Directional Index) — Trend Strength

ADX measures the *magnitude* of directional movement, regardless of direction. It doesn't tell you up or down — it tells you "is the market moving with conviction?"

- **ADX > 25** → Trending regime
- **ADX < 20** → Choppy / mean-reverting regime
- **20–25** → Ambiguous transition zone

### Signal 2: Efficiency Ratio (Kaufman) — Path Quality

This is the ratio of net price displacement over a window to the total distance traveled. It measures whether price is moving in a straight line or zig-zagging.

```
ER = abs(close - close[N]) / sum(abs(close[i] - close[i-1]) for i in range(N))
```

- **ER > 0.6** → Clean trend (price traveled efficiently in one direction)
- **ER < 0.3** → Chop (price traveled a lot but went nowhere)

This catches what ADX misses: a market can have high volatility (high ATR) and moderate ADX but still be choppy if the net displacement is near zero.

### Signal 3: Bollinger Band Width Percentile — Volatility Regime

Compute Bollinger Band width `(upper - lower) / middle`, then rank the current value against its own 200-bar rolling history as a percentile.

- **Width percentile > 70th** → Expanded volatility (breakout or trend continuation likely)
- **Width percentile < 30th** → Compressed volatility (squeeze / range-bound, but a breakout may be imminent)
- **30th–70th** → Normal volatility

> [!IMPORTANT]
> Compressed bands don't mean "chop forever." They mean "chop *now*, but energy is building." The system should abstain during compression but prepare for a breakout signal.

---

## The Composite Regime Score

| ADX | Efficiency Ratio | BB Width %ile | Regime Classification |
|---|---|---|---|
| > 25 | > 0.5 | > 50th | **TRENDING** — High conviction. Full system online. |
| > 25 | < 0.3 | any | **VOLATILE CHOP** — High energy, no direction. Dangerous false signals. Abstain. |
| < 20 | < 0.3 | < 30th | **DEAD RANGE** — Low energy, no direction. Market is asleep. Hard abstain. |
| < 20 | < 0.3 | > 70th | **SQUEEZE BREAKOUT PENDING** — Compression about to release. Watch-only mode. |
| 20–25 | 0.3–0.5 | 30th–70th | **AMBIGUOUS** — Transition zone. Reduced sizing only. |

---

## Where It Sits in the Pipeline

**Before everything.** The regime detector is the first gate in the entire evaluation cycle, upstream of both Kronos and XGBoost.

```
Hourly Tick
    │
    ▼
┌──────────────────────┐
│   REGIME DETECTOR    │  ◄── Runs FIRST, on raw OHLCV only
│  ADX + ER + BB%ile   │
└──────────┬───────────┘
           │
     ┌─────┴─────┐
     │           │
  TRENDING    CHOPPY / AMBIGUOUS
     │           │
     ▼           ▼
┌─────────┐   LOG & SKIP
│ Kronos  │   "Regime: CHOPPY. Skipping
│ XGBoost │    evaluation cycle."
│ run in  │   No models run.
│ parallel│   No LLM call.
└────┬────┘   No latency cost.
     │
     ▼
┌──────────────────────┐
│  CONSENSUS LAYER     │
│  Agreement Matrix    │
└──────────┬───────────┘
     ┌─────┴─────┐
     │           │
  CONSENSUS    CONFLICT
     │           │
     ▼           ▼
┌──────────┐   ABSTAIN
│ LLM RISK │
│ MANAGER  │
└──────────┘
```

### Why Before, Not After?

1. **Compute savings.** Kronos inference on CPU takes 3–8 seconds. XGBoost takes ~50ms. The LLM takes 1–3 seconds. If the regime is choppy, you save 5–12 seconds of wasted computation per symbol per cycle. Over 3 symbols × 24 cycles/day, that's significant.
2. **Signal quality.** Both Kronos and XGBoost were designed (or at least, should be designed) to detect directional setups. Feeding them data from a ranging market will produce noisy, low-confidence signals that then need to be filtered downstream anyway. It's better to not generate garbage than to generate garbage and then try to filter it.
3. **LLM cost.** Every Gemini API call costs tokens and latency. If the regime gate blocks 40–60% of evaluation cycles (which is realistic — crypto ranges most of the time), you cut your API bill and latency budget in half.

---

## What the System Does in Each Regime

### TRENDING Regime

Full system activation. Kronos and XGBoost both run. Consensus layer adjudicates. LLM risk manager reviews. Standard position sizing (10% equity). **This is where the bot is designed to make money.**

### VOLATILE CHOP Regime

Hard abstain on all new entries. The danger here is that high ATR + low ER produces signals that *look* strong (big candles, high volume) but have no follow-through. This is the regime where most retail algos get chopped to death.

The bot logs:
```
"Regime: VOLATILE_CHOP. High energy, no direction. Skipping."
```
It only monitors existing positions for stop management.

### DEAD RANGE Regime

Full shutdown of signal generation. Even position monitoring is relaxed to every 2 hours instead of every 1 hour. There is genuinely nothing to do.

The bot logs:
```
"Regime: DEAD_RANGE. Market asleep."
```
It conserves resources.

### SQUEEZE BREAKOUT PENDING

> [!TIP]
> This is the most interesting state — and where the highest-EV trades live.

The bot does *not* trade, but it switches to a **watch mode** where it runs Kronos at 2x sampling frequency (every 30 minutes instead of every hour) without executing. It's pre-loading the forecast pipeline so that the moment ADX crosses above 25 and the Efficiency Ratio jumps above 0.5 (confirming the breakout), the system already has a warm, recent Kronos forecast ready to act on.

The first signal after a confirmed breakout gets priority execution.

### AMBIGUOUS Regime

The system is allowed to trade, but with two constraints:

1. Position sizing drops to **50% of normal** (5% equity instead of 10%)
2. The consensus layer requires **STRONG CONSENSUS** (both models must agree) — no partial-agreement trades allowed

---

## The Key Principle

> [!CAUTION]
> The regime detector exists to enforce the oldest rule in trading: **the best trade is often no trade.**

A system that is always hunting for signals will find them even in noise. The regime gate's job is to make the bot comfortable sitting on its hands 40–60% of the time, preserving capital for the 2–3 high-conviction trending windows per week where the edge actually exists.
