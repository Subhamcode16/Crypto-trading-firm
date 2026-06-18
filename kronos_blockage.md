The Answers To Your Three Questions
Q1 — Regime Gate: None of A, B, or C yet. Run the diagnostic first. If Scenario A, selectively relax AMBIGUOUS. If Scenario B, the gate isn't the problem. If Scenario C, recalibrate from scratch using the regime's actual predictive correlation with forward returns.
Q2 — Kronos: Temporarily disable it (your Option B) but frame it correctly — you're not disabling it because it's inconvenient, you're isolating it because it has demonstrated negative standalone alpha and you need to know what the system looks like without it before deciding whether to fix it or remove it.
Q3 — Next validation priority: Your Option B. Fix the 2025 blocker first. Running 2022 on a broken 2025 configuration produces no useful information — you already know the kill switch works from previous runs.

The Immediate Action
Run this exact sequence:
1. Disable Kronos consensus vote (keep it logging but non-blocking)
2. Run 2025 backtest — XGBoost + Regime Gate + Kill Switch only
3. Report: signal count, trades executed, Sharpe, max drawdown

If Sharpe recovers above 1.0:
   → Kronos was the problem. Decide: remove it or fine-tune it.

If Sharpe remains negative:
   → Run the trade-level diagnostic above.
   → Regime gate is selecting inversely. Recalibrate.
One variable changed. One clean result. That's how you isolate the failure.
Don't touch thresholds. Don't run HPO. Don't pick from the menu. Isolate the variable that's destroying value first. Then fix it with evidence.
What does the 2025 backtest return when Kronos is non-blocking?

Option Real-1: Remove Kronos from the consensus layer entirely.
               Use it only as a volatility/uncertainty signal (spread width)
               not as a directional vote.

Option Real-2: Fine-tune Kronos on BTC-specific data before including it
               as a consensus vote. Zero-shot crypto performance is
               demonstrably negative — you proved this yourself.

Option Real-3: Keep Kronos but invert its role — use it as a contrarian
               signal. If Kronos says DOWN and XGBoost says UP with high
               confidence, that disagreement itself is informative.