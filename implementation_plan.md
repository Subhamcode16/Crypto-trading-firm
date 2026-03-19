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

### Agent-6: Macro Sentinel
#### [NEW] `backend/src/agents/macro_sentinel.py`
- **Data Fetching:** Implement `fetch_klines(symbol, timeframe)` using `ccxt` or pure `requests` targeting Binance API, with a fallback `try/except` block targeting Bybit API.
- **Downtrend Logic (Technical Indicator-Based):** 
  - Calculate 50-EMA and 200-SMA on 1h and 4h timeframes for BTC and SOL using `pandas-ta` or `ta-lib`.
  - Define "sharp confirmed downtrend": e.g., price drops below 50-EMA and 50-EMA crosses below 200-SMA.
- **Signal Clearance:** `evaluate_signal(signal)` routine that drops signals if the macro downtrend is active.
- **Continuous Monitoring:** Run an event loop or APScheduler job to update macro state every 15 minutes.

### Agent-7: Risk Manager & Kill Switch
#### [MODIFY/NEW] `backend/src/agents/risk_manager.py` (or existing Risk Manager)
- **Startup Check:** On `__init__`, read the `kill_switch_state` from MongoDB to resume any active tiers.
- **Rule Evaluation Engine:**
  - **Tier 1 (Caution):** If daily loss >= 40% of limit OR a single token drops 8%+. Action: Block new entries for that token, hold existing, scale new globally by 0.7x (30% reduction). Sets a 2h auto-recovery timestamp.
  - **Tier 2 (Defense):** If daily loss >= 70% of limit OR portfolio drawdown high. Action: Block ALL new entries. Hold and monitor existing. Flags Agent-6 to double check frequency (every 7.5m). Sets auto-recovery to next UTC midnight.
  - **Tier 3 (Full Stop):** If daily loss >= 100% of limit OR manually triggered. Action: Reject all signals, emit liquidation command (for Agent-8 to close at market), update DB state to `tier: 3`. Send immediate Telegram alert. No auto-recovery.

### External Interfaces (Telegram & Admin)
#### [MODIFY] [backend/src/telegram_bot.py](file:///c:/Users/User/OneDrive/Desktop/projects/Crypto-trading-bot/backend/src/telegram_bot.py)
- Add command handler for `/resume`.
- Verify user permissions (is owner/admin).
- Directly query MongoDB: if `tier == 3`, update to `tier: 0` and send confirmation message. If not Tier 3, note that bot is already active or in an auto-recovering tier.

#### [MODIFY] [backend/src/main.py](file:///c:/Users/User/OneDrive/Desktop/projects/Crypto-trading-bot/backend/src/main.py) (or API routers)
- **Admin Backend Endpoint:** Add a protected route `POST /admin/resume-killswitch/{user_id}` to allow the SaaS admin to override Tier 3 states for users locked out of Telegram. Requires admin JWT/API Key.

## Verification Plan
### Automated Tests
- Write a script to mock Binance/Bybit API returns (both uptrend and downtrend) and verify Agent-6 drops signals accurately when indicators cross.
- Write a script to mock Agent-7 inputs (incremental losses) and assert that Tier 1, Tier 2, and Tier 3 states are written to MongoDB correctly.
- Test endpoint `/admin/resume-killswitch` using `httpx` in the test suite.

### Manual Verification
- Start the server. Manually write a Tier 3 state to the database for the test user. Verify that submitting a signal via the pipeline results in an immediate rejection.
- Send `/resume` to the Telegram bot and verify the database is updated and signals are allowed again.
