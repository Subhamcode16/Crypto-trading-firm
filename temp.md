To give you a reference frame: Renaissance Technologies' Medallion Fund — the most successful quantitative trading operation in history, running for 30+ years with hundreds of PhDs — achieves a Sharpe of approximately 2.0 to 2.5 after fees. Citadel, Two Sigma, DE Shaw operate in the 1.5 to 3.0 range.
A raw unfiltered XGBoost model on hourly BTC data achieving 10.47 Sharpe means one of two things. Either you have discovered something that has eluded every quantitative firm on the planet, or there is still a data integrity problem in the pipeline.
The second explanation is overwhelmingly more likely.

The New Suspect: STRONG_LONG Signal Rate Dropped From 21% to 3.1%
This is the number that points directly to the problem.
You went from 21.6% of bars labeled STRONG_LONG to 3.1%. That's a 7x reduction. Combined with 553 trades executed in one year from a pool of 3.1% signals, something doesn't add up.
Run this diagnostic immediately:
python# Check the temporal distribution of your 553 trades
trades = pd.DataFrame(list(db.trade_log.find({
    "environment": "backtest_2025_xgb_baseline"
})))

trades['timestamp'] = pd.to_datetime(trades['timestamp'])
trades['month'] = trades['timestamp'].dt.to_period('M')

monthly = trades.groupby('month').agg(
    count=('pnl', 'count'),
    total_pnl=('pnl', 'sum'),
    win_rate=('pnl', lambda x: (x > 0).mean())
)

print(monthly)
print(f"\nTotal trades: {len(trades)}")
print(f"Date range: {trades['timestamp'].min()} to {trades['timestamp'].max()}")

# Check if trades cluster in a specific period
print(f"\nTrades in first 3 months: {(trades['month'] < '2025-04').sum()}")
print(f"Trades in last 3 months: {(trades['month'] >= '2025-10').sum()}")

The Three Most Likely Remaining Issues
Issue 1 — Training and Test Data Overlap
Your model was trained on 2020-2024 data. Your baseline test is on 2025 data. That should be clean. But verify the exact split boundary:
python# In train_xgb_2020_2024.py — what is the last training candle?
print(f"Last training candle: {X_train.index[-1]}")
print(f"First test candle: {X_test.index[0]}")

# These must not overlap. Even a single candle of overlap
# contaminates the entire test result.
assert X_test.index[0] > X_train.index[-1], "OVERLAP DETECTED"
Issue 2 — The Threshold Floor Created a New Leakage
Your new label generation uses:
pythonstrong_thresh = np.maximum(1.5 * atr_pct, 0.004)
ATR is computed as a rolling calculation over past bars. But verify that atr_pct at bar T uses only data up to bar T-1, not bar T itself. If ATR includes the current bar's range in its calculation, the label for bar T has seen bar T's price action — which the features also describe. This creates a subtle correlation between features and labels that inflates apparent model performance.
python# Correct ATR computation — shift by 1 to exclude current bar
true_range = pd.concat([
    df['high'] - df['low'],
    (df['high'] - df['close'].shift(1)).abs(),
    (df['low'] - df['close'].shift(1)).abs()
], axis=1).max(axis=1)

# ATR must be computed on PAST bars only
atr = true_range.shift(1).rolling(14).mean()  # shift(1) is critical
Issue 3 — Forward Return Computation Still Using Close
Even with correct entry at next candle open, your label computation may still use close-to-close returns for the target variable while the backtest measures open-to-open or open-to-close returns. This mismatch means the model was trained to predict a return it never actually captures.
python# What your labels compute (close-to-close)
future_return_label = df['close'].shift(-horizon) / df['close'] - 1

# What your backtest actually captures (entry at next open, exit at close)
future_return_actual = df['close'].shift(-horizon) / df['open'].shift(-1) - 1

# These are different. If they diverge significantly during your test period,
# your model learned to predict something it cannot trade.
correlation = future_return_label.corr(future_return_actual)
print(f"Label vs executable return correlation: {correlation:.4f}")
# Should be > 0.85. If below 0.7, you have a return computation mismatch.

The Sanity Check That Supersedes Everything
Before running any of the above, do this one thing:
python# Take 10 random trades from your backtest results
# Manually verify each one against the raw price data

sample_trades = trades.sample(10, random_state=42)

for _, trade in sample_trades.iterrows():
    entry_time = trade['timestamp']
    exit_time  = trade['exit_timestamp']
    
    entry_bar  = df.loc[entry_time]
    exit_bar   = df.loc[exit_time]
    
    # Recalculate PnL from raw price data manually
    manual_pnl = (exit_bar['close'] - entry_bar['open']) / entry_bar['open']
    
    print(f"Trade at {entry_time}")
    print(f"  Logged PnL:  {trade['pnl']:.4f}")
    print(f"  Manual PnL:  {manual_pnl:.4f}")
    print(f"  Match: {abs(trade['pnl'] - manual_pnl) < 0.001}")
    print()
If any of the 10 trades fail the manual verification, your backtest engine has a calculation error that is producing phantom profits. A 10.47 Sharpe built on miscalculated PnL is not a trading system — it's an accounting error.

Do Not Proceed Until You Answer This
A legitimate 10.47 Sharpe would mean your 553 trades had an extraordinarily consistent positive return with almost no variance. That is statistically implausible on live market data.
Run the manual trade verification first. Then run the training/test overlap check. Report what you find on both. If the trades verify correctly against raw price data and the overlap is clean, we go deeper into the ATR and return computation issues.
What does the manual spot check return?