# Agent-6, Agent-7, and Kill Switch Implementation

This plan outlines the implementation for the Macro Sentinel (Agent-6), the Risk Manager (Agent-7), and the hybrid 3-tier Kill Switch based on your selected options.

## User Review Required
> [!IMPORTANT]
> Please review this plan, particularly the Tier logic and indicator definitions, and provide the **"green signal"** to proceed with execution.

## Proposed Changes

### Database Layer
#### [MODIFY] [backend/src/database.py](file:///c:/Users/User/OneDrive/Desktop/projects/Crypto-trading-bot/backend/src/database.py)
- Add a new collection `kill_switch_state` to store per-user states (`user_id`, `tier`, `active_since`, `trigger_reason`, `affected_tokens`).
- Add a collection/schema for `daily_portfolio_state` to track daily realized loss vs. limit and current exposure.
- Implement functions: `get_kill_switch(user_id)`, `set_kill_switch(user_id, tier, data)`, `clear_kill_switch(user_id)`.
- **[NEW — Fix 4]** Add a collection `kill_switch_audit_log` to record every Tier activation and `/resume` event with fields: `user_id`, `event_type` (`activated` | `resumed`), `tier`, `triggered_by` (`system` | `user` | `admin`), `timestamp`. Write to this log on every state change in `set_kill_switch` and `clear_kill_switch`.
- **[NEW — Fix 1]** Add a `macro_check_interval_seconds` field (default: `900`) to the per-user config collection. Agent-6 reads this value on each cycle to determine its polling frequency. Agent-7 writes `450` to this field when Tier 2 activates, and restores `900` when Tier 2 clears.

### Agent-6: Macro Sentinel
#### [NEW] `backend/src/agents/macro_sentinel.py`
- **Data Fetching:** Implement `fetch_klines(symbol, timeframe)` using `ccxt` or pure `requests` targeting Binance API, with a fallback `try/except` block targeting Bybit API.
- **Downtrend Logic (Composite — Fix 1 Applied):**
  - Fetch the last 60 × 1h candles for SOL and BTC using `fetch_klines`.
  - Calculate the 50-EMA on the 1h timeframe using `pandas-ta` or `ta-lib`.
  - Define **"sharp confirmed downtrend"** as ALL THREE of the following conditions being true simultaneously:
    1. Current 1h candle shows a price drop of **>3%** (current close vs. current open, or rolling 1h window).
    2. The **last 3 consecutive 1h closes are descending**: `close[n] < close[n-1] < close[n-2]`.
    3. **Current price is below the 50-EMA** on the 1h chart.
  - If only 1 or 2 conditions are true, flag the state as **CAUTION** (logged, not blocking). All 3 must fire to issue a market-wide hold.
  - > ⚠️ **Removed from original plan:** The 200-SMA death cross condition has been removed. A 50-EMA crossing below the 200-SMA is too slow and lagging for 1h/4h trade decisions and would cause missed blocks during fast downmoves. The 200-SMA may be calculated and logged as a contextual indicator only — it must never be a required trigger condition.
- **BTC 4h Check:** Mirror the same composite logic on BTC's 4h chart. The 50-EMA on 4h covers ~200 hours of data, providing a solid structural macro read.
- **Polling Interval (Fix 3 Applied — Decoupled from Agent-7):** On each cycle start, read `macro_check_interval_seconds` from the database for the current user/context. Sleep for that duration after each cycle completes. Agent-7 never calls into Agent-6's scheduler directly — it only writes to the database field.
- **Signal Clearance:** `evaluate_signal(signal)` routine that drops signals if the macro downtrend state is CONFIRMED (all 3 conditions). Returns CAUTION signals upstream with a warning flag but does not block them.

### Agent-7: Risk Manager & Kill Switch
#### [MODIFY/NEW] `backend/src/agents/risk_manager.py` (or existing Risk Manager)
- **Startup Check:** On `__init__`, read the `kill_switch_state` from MongoDB to resume any active tiers. If `tier == 3` is found in the database, immediately enter blocking mode — no signals are processed until manual re-enable.
- **Rule Evaluation Engine:**
  - **Tier 1 (Caution):** If daily loss >= 40% of limit OR a single token drops 8%+. Action: Block new entries for that token, hold existing positions. Scale all new position sizes globally by multiplying by **0.70** (i.e., new_size = calculated_size × 0.70). Sets a 2h auto-recovery timestamp.
    - > ⚠️ **Fix 2 clarification:** Position size is multiplied by 0.70 — not reduced by 0.70. A developer must apply: `approved_size = signal_size * 0.70`, not `approved_size = signal_size - 0.70`.
  - **Tier 2 (Defense):** If daily loss >= 70% of limit OR portfolio drawdown exceeds threshold. Action: Block ALL new entries across all tokens. Hold and monitor existing positions. Write `macro_check_interval_seconds = 450` to the database (Agent-6 picks this up on its next cycle — Agent-7 does NOT call Agent-6 directly). Sets auto-recovery to next UTC midnight OR manual re-enable by user.
  - **Tier 3 (Full Stop):** If daily loss >= 100% of limit OR manually triggered. Action: Reject all incoming signals. Emit liquidation command for Agent-8 to close all open positions at market. Write `tier: 3` to `kill_switch_state`. Send immediate Telegram alert. **No auto-recovery under any condition** — manual re-enable via `/resume` or admin endpoint only.
- **Audit Logging (Fix 4 Applied):** Every tier activation and every tier clearance must write a record to `kill_switch_audit_log` with: `user_id`, `event_type`, `tier`, `triggered_by`, `timestamp`. This is mandatory for SaaS support and dispute resolution.

### External Interfaces (Telegram & Admin)
#### [MODIFY] [backend/src/telegram_bot.py](file:///c:/Users/User/OneDrive/Desktop/projects/Crypto-trading-bot/backend/src/telegram_bot.py)
- Add command handler for `/resume`.
- Verify user permissions (is owner/admin).
- Directly query MongoDB: if `tier == 3`, update to `tier: 0`, restore `macro_check_interval_seconds` to `900`, and send confirmation message to user.
- **[Fix 4 Applied]** Write a record to `kill_switch_audit_log`: `{ event_type: "resumed", triggered_by: "user", tier: 3, timestamp: now }` before sending the confirmation message.
- If not Tier 3, respond noting that the bot is already active or in an auto-recovering tier.

#### [MODIFY] [backend/src/main.py](file:///c:/Users/User/OneDrive/Desktop/projects/Crypto-trading-bot/backend/src/main.py) (or API routers)
- **Admin Backend Endpoint:** Add a protected route `POST /admin/resume-killswitch/{user_id}` to allow the SaaS admin to override Tier 3 states for users locked out of Telegram. Requires admin JWT/API Key.
- **[Fix 4 Applied]** This endpoint must also write to `kill_switch_audit_log` with `triggered_by: "admin"` and include the admin's identifier in the log record.

## Verification Plan
### Automated Tests
- Write a script to mock Binance/Bybit API returns (both uptrend and downtrend) and verify Agent-6 correctly identifies CONFIRMED vs. CAUTION downtrend states using the composite 3-condition logic (% drop + consecutive closes + 50-EMA).
- Verify that a signal is only blocked when ALL THREE conditions are true — test each 2-of-3 combination to confirm they produce CAUTION, not a block.
- Write a script to mock Agent-7 inputs (incremental losses) and assert that Tier 1, Tier 2, and Tier 3 states are written to MongoDB correctly, including the `kill_switch_audit_log` entry on each transition.
- Assert that Tier 1 applies a `× 0.70` multiplier to position size (not a subtraction).
- Assert that Tier 2 activation writes `macro_check_interval_seconds = 450` to the database and does NOT make a direct call into Agent-6.
- Test endpoint `/admin/resume-killswitch` using `httpx` in the test suite. Verify audit log entry is written with `triggered_by: "admin"`.
- Simulate server restart with an active Tier 3 state in the database. Verify Agent-7 resumes in blocking mode immediately on boot.

### Manual Verification
- Start the server. Manually write a Tier 3 state to the database for the test user. Verify that submitting a signal via the pipeline results in an immediate rejection.
- Send `/resume` to the Telegram bot and verify: (a) the database is updated, (b) signals are allowed again, and (c) an audit log record exists with the correct timestamp and `triggered_by: "user"`.
