# CRYPTO AUTONOMOUS TRADING SYSTEM - SYSTEM LOGIC

**Project:** Solana Memecoin Autonomous Trading System  
**Author:** Subham Rath  
**Status:** Phase 1 Rebuild + Phase 2 Build  
**Last Updated:** 2026-02-26

---

## 1. SYSTEM OVERVIEW

### Vision
A fully autonomous trading system that discovers high-confidence Solana memecoin signals through rigorous on-chain analysis, executes trades with strict risk controls, and self-improves based on performance data.

### Core Philosophy
**Signal Quality > Quantity**
- Researcher produces 3-5 signals/day maximum (not 50)
- Each signal passes 6-point on-chain filter before AI even runs
- Trader executes what it's told, nothing more
- Risk Manager overrides everything, always

### Three-Layer Architecture

```
RESEARCHER BOT (Signal Discovery)
    ↓ (structured signal JSON)
RISK MANAGER (Constraint Enforcement)
    ↓ (position size check, daily loss check, exposure check)
TRADING BOT (Execution)
    ↓ (Jupiter DEX)
SOLANA MEMECOIN MARKET
```

---

## 2. DATA FLOW ARCHITECTURE

### Complete Signal Pipeline

```
LAYER 1: ON-CHAIN DATA COLLECTION
├─ Dexscreener: Monitor new token pairs real-time
├─ Solscan: Wallet activity, contract info, holder concentration
└─ Helius RPC: Token creation events, transaction history

LAYER 2: MANDATORY FILTERS (If ANY fail → Signal dies)
├─ ✅ Contract age > 15 minutes old
├─ ✅ Liquidity locked (verified via Solscan/contract audit)
├─ ✅ Top 10 wallets < 30% of supply
├─ ✅ Volume from >50 unique wallets (organic, not bot-traded)
├─ ✅ Deployer wallet: No rug history
└─ ✅ Clean on-chain data (no anomalies)

IF ALL PASS → Continue to Layer 3
IF ANY FAIL → Signal dropped, never reaches Telegram

LAYER 3: AI SCORING (Claude Haiku)
├─ Narrative strength (meme potential, community viability)
├─ Social velocity (Twitter mentions, Reddit posts)
├─ Technical indicators (volume pattern, price momentum)
└─ Confidence score: 0-10

LAYER 4: POSITION SIZING (Deterministic)
├─ Confidence 8-10 → Position size: $2 (20% of $10 capital)
├─ Confidence 6-7 → Position size: $1 (10% of $10 capital)
└─ Confidence <6 → DROPPED (no position, no signal sent)

LAYER 5: RISK MANAGER CHECKS
├─ Daily loss check: Is today's loss < $3?
├─ Portfolio exposure: Are open positions < 30% of capital?
└─ Position size valid: Does this fit within hard caps?

LAYER 6: TELEGRAM ALERT (Purely Informational)
├─ Token name, symbol, contract address
├─ Recommended entry price
├─ Confidence score
├─ Position size ($1 or $2)
├─ Stop loss price (20% below entry)
├─ Take profit tiers (2x, 4x, trailing)
├─ Risk/reward: 1:2 minimum
└─ Primary reason for signal

LAYER 7: AUTOMATIC EXECUTION (No Approval Required)
├─ Wait 5 seconds (allow Telegram delivery)
├─ If kill switch active → Cancel trade, don't execute
├─ Otherwise → Execute immediately via Jupiter
├─ Set stop loss and take profit orders on-chain
└─ Log execution to database

LAYER 8: POSITION MANAGEMENT
├─ Monitor price in real-time
├─ Execute take profit tiers (40% @ 2x, 40% @ 4x)
├─ Trailing stop for remaining 20% at 50% below high
├─ Track P&L against daily loss limit

LAYER 9: DAILY REVIEW & LOGGING
├─ Track signals sent (quality)
├─ Track trades executed (execution quality)
├─ Calculate hit rate (profitable / total)
└─ Update kill switch status based on daily P&L
```

---

## 3. RISK MANAGEMENT - KILL SWITCH TIERS

### Tier 1: Soft Pause (Early Warning)
**Trigger:** Daily loss reaches $3 (30% of starting capital)

**Actions:**
- Pause new signal generation immediately
- Do NOT execute any new trades
- Allow existing open positions to close on their own
- Send Telegram: "⚠️ SOFT PAUSE: Daily loss limit hit ($3). No new trades. Existing positions closing."
- Resume at UTC midnight (daily reset)

**Purpose:** Prevent compounding losses mid-day; give system time to cool off

---

### Tier 2: Hard Stop (Catastrophic Loss)
**Trigger:** Total capital drops below $5 (50% drawdown from starting $10)

**Actions:**
- Close ALL open positions immediately at market price
- HALT ALL OPERATIONS
- Send Telegram: "🛑 HARD STOP: Capital dropped to $X. All positions closed. System halted."
- System does NOT auto-resume
- Requires manual action:
  1. You review what went wrong
  2. Adjust parameters if needed
  3. Add capital or reset
  4. Manually restart system

**Purpose:** Prevent total account blowup; force human intervention

---

### Tier 3: Emergency Kill (Technical Anomaly)
**Trigger:** Any of these conditions:
- 3 consecutive transaction failures in a row
- API returns corrupted/invalid data (bad JSON, missing fields, etc.)
- Position size somehow exceeds configured maximum (system bug)
- Trade execution doesn't match signal parameters (entry price off by >5%, size mismatch, etc.)
- Slippage exceeds 50% (sign of manipulation or liquidity issue)

**Actions:**
1. Close ALL positions immediately
2. Halt completely (like Tier 2, no auto-resume)
3. Send urgent Telegram alert with:
   - What triggered it (specific error)
   - Full diagnostic data (failed API call, position details, etc.)
   - Timestamp and transaction hash if trade failed
4. System requires manual investigation before restart

**Purpose:** Detect and stop system bugs before they drain account; force code review

---

## 4. POSITION SIZING LOGIC

### Entry Position Size (Deterministic)

```
IF confidence_score >= 8:
    position_size = $2
ELIF confidence_score >= 6:
    position_size = $1
ELSE:
    signal_dropped()  # No position, no trade
    return
```

**At $10 capital scale:**
- $2 position = 20% of capital per trade
- $1 position = 10% of capital per trade
- Max exposure = 30% (so max 2 positions open at once)

**Example:**
- Signal 1: Confidence 9 → $2 position (20% exposure)
- Signal 2: Confidence 8 → $2 position (would be 40% total exposure)
  - **REJECTED by Risk Manager** (exceeds 30% max)
  - Trade doesn't execute
  - Telegram alert: "Position rejected: Would exceed 30% portfolio exposure"

---

## 5. STOP LOSS & TAKE PROFIT LOGIC

### Entry-Level Hard Rule: Stop Loss

```
STOP_LOSS_PERCENT = 20%

stop_loss_price = entry_price * (1 - STOP_LOSS_PERCENT)

Example:
- Entry price: $1.00
- Stop loss: $1.00 * 0.80 = $0.80
- Max loss per position: position_size * 20%
  - $2 position → Max loss $0.40
  - $1 position → Max loss $0.20
```

**Why 20%, not tighter?**
- Solana memecoins have violent 10-15% retracements mid-run
- 10% stop loss = constantly stopped out of winning trades
- 20% = catches real breakdowns, survives normal volatility

**No exceptions, no overrides.**

---

### Tier-Based Take Profit

```
Position: 100 units (example: 100 tokens)

TIER 1: Sell 40% @ 2x entry price
  - Sell 40 units at 2x entry
  - Profit: 40 units * (2x - 1x) = 40 units of profit
  - Lock in gain, reduce exposure

TIER 2: Sell 40% @ 4x entry price
  - Sell 40 units at 4x entry
  - Additional profit: 40 units * (4x - 1x) = 120 units of profit
  - Further reduce exposure

TIER 3: Trailing Stop on remaining 20%
  - 20 units remain (20% of position)
  - Trailing stop: 50% below the current high reached
  
  Example:
  - Entry: $1.00, position = 20 tokens
  - Price runs to $10.00 (10x)
  - Trailing stop at: $10 * 0.50 = $5.00
  - If price retraces to $5.00 → SELL (lock in 5x on remaining)
  - If price continues to $20.00 → Trailing stop moves to $10.00
  - Keeps riding upside with downside protection
```

**Why this structure?**
- Lock in majority profit at 2x and 4x (realistic gains)
- Keep 20% exposure for a potential 10x (tail-end upside)
- Trailing stop prevents being greedy, catches pullbacks
- Avoids "watched it go 10x and never sold" scenario

---

## 6. DAILY LOSS LIMIT & SOFT PAUSE

### Daily Loss Calculation

```
STARTING_CAPITAL = $10
DAILY_LOSS_LIMIT = $3 (30%)

Each trade P&L tracked:
- Trade 1: +$0.50 (profitable)
- Trade 2: -$1.20 (loss)
- Trade 3: -$0.80 (loss)
Daily P&L = +$0.50 - $1.20 - $0.80 = -$1.50

SOFT PAUSE triggers at: Daily P&L <= -$3.00
```

### Soft Pause Behavior

```
SOFT PAUSE = No new trades, but existing positions close naturally

Timeline:
09:00 UTC - Daily loss hits $3 → Soft Pause triggers
  - Telegram: "⚠️ SOFT PAUSE: Daily loss limit ($3) reached"
  - Researcher: STOPS sending signals
  - Trading Bot: Does NOT execute new trades
  - Existing positions: Continue running, close on their own

15:00 UTC - First position hits take profit 2x → Closes (normal flow)
16:30 UTC - Second position hits stop loss → Closes (normal flow)
17:00 UTC - All positions closed, capital reduced due to losses

00:00 UTC - Day resets, daily loss counter resets to $0
  - Soft Pause automatically lifts
  - Researcher resumes sending signals
  - Trading Bot ready to trade again
```

---

## 7. RESEARCHER BOT SIGNAL OUTPUT FORMAT

Every signal sent to Telegram must follow this JSON structure. No exceptions, no incomplete signals.

```json
{
  "timestamp": "2026-02-26T14:23:45Z",
  "signal_id": "SIG_20260226_001",
  "token": {
    "address": "So11111111111111111111111111111111111111112",
    "name": "MEMETOKEN",
    "symbol": "MEME",
    "decimals": 6
  },
  "entry": {
    "price": 0.0025,
    "price_usd": 0.0025,
    "position_size_usd": 2.0,
    "position_size_tokens": 800000,
    "reason": "New token, strong community narrative, organic volume"
  },
  "risk": {
    "stop_loss_price": 0.002,
    "stop_loss_percent": 20,
    "max_loss_usd": 0.40
  },
  "profit_targets": [
    {
      "tier": 1,
      "price": 0.005,
      "multiplier": "2x",
      "sell_percent": 40,
      "tokens_to_sell": 320000,
      "profit_usd": 0.80
    },
    {
      "tier": 2,
      "price": 0.010,
      "multiplier": "4x",
      "sell_percent": 40,
      "tokens_to_sell": 320000,
      "profit_usd": 1.60
    },
    {
      "tier": 3,
      "type": "trailing_stop",
      "trailing_percent": 50,
      "tokens_remaining": 160000
    }
  ],
  "confidence": {
    "score": 8,
    "on_chain_filters": {
      "contract_age_minutes": 28,
      "liquidity_locked": true,
      "top_10_wallet_percent": 22,
      "unique_buyer_wallets": 187,
      "deployer_rug_history": false
    },
    "ai_analysis": {
      "narrative_strength": "High - Dog-themed memecoin with gaming angle",
      "social_velocity": "Growing - Twitter mentions up 45% in 2 hours",
      "technical": "Volume organic, price momentum positive"
    }
  },
  "risk_reward": {
    "ratio": "1:2",
    "best_case": "+$1.60",
    "worst_case": "-$0.40"
  },
  "sources": [
    "dexscreener_new_pair",
    "solscan_holder_analysis",
    "twitter_velocity"
  ]
}
```

### Telegram Display Format

```
🚀 SIGNAL #001 (Confidence: 8/10)

Token: MEME (So11111...11112)
Entry Price: $0.0025
Position: $2.00 (20% of capital)

📊 Risk/Reward: 1:2
Stop Loss: $0.002 (20% below entry) → Max loss: $0.40
Take Profit Targets:
  TP1 (40%): $0.005 (2x) → Lock in $0.80
  TP2 (40%): $0.010 (4x) → Lock in $1.60
  TP3 (20%): Trailing stop at $5.00 (50% below high)

🔍 Why This Signal:
- Strong community narrative (gaming angle)
- Organic volume from 187 unique wallets
- No whale concentration risk (top 10: 22%)
- Deployer has clean history

🎯 Execution: AUTOMATIC (no approval needed)
```

---

## 8. FULL TRADING FLOW TIMELINE

### Complete Example: Signal to Close

```
TIME: 14:23 UTC

STEP 1: RESEARCHER DETECTS SIGNAL
- Dexscreener: New token pair created on Raydium
- Contract age: 28 minutes ✓
- Solscan checks: Liquidity locked, clean holders ✓
- Deployer history: No rugs ✓
- Volume: 187 unique wallets ✓
- AI scoring: Confidence 8/10 ✓
- Position size: $2 (20% of $10)

STEP 2: RISK MANAGER PRE-FLIGHT CHECK
- Daily loss so far: -$1.20
- Daily loss limit: $3.00
- Can we trade? YES ✓
- Portfolio exposure: 10% (from other open position)
- Adding $2 position: 30% total
- Within limit? YES ✓

STEP 3: TELEGRAM ALERT (Purely informational)
- Sends structured signal JSON to Telegram
- Shows all TP levels, stop loss, reason
- No approval needed

STEP 4: EXECUTE IMMEDIATELY
- 5 seconds later (allow Telegram delivery)
- Jupiter API: Buy order
  - Token: MEME
  - Entry: $0.0025
  - Size: 800,000 tokens
  - Slippage: 2% protection
- Order succeeds
- Position OPEN ✓

STEP 5: SET STOP LOSS (HARD RULE)
- Solana blockchain: Place limit order
  - Trigger: $0.002 (20% below entry)
  - Auto-sell entire position if hit
- Confirms on-chain ✓

STEP 6: SET TAKE PROFIT TIERS
- Tier 1: 40% at $0.005 (2x)
- Tier 2: 40% at $0.010 (4x)
- Tier 3: 20% with trailing stop at $5.00 (50% below high)
- All orders set on-chain ✓

---

TIME: 14:31 UTC (8 minutes later)

PRICE MOVEMENT: $0.0025 → $0.0050 (2x entry)

STEP 7: TIER 1 TAKE PROFIT TRIGGERS
- 40% of position (320,000 tokens) sells at $0.0050
- Profit: 320,000 tokens * ($0.0050 - $0.0025) = $0.80
- Remaining position: 480,000 tokens (40% + 20%)
- Daily P&L update: -$1.20 + $0.80 = -$0.40

---

TIME: 14:47 UTC (24 minutes after entry)

PRICE MOVEMENT: $0.0050 → $0.0100 (4x entry)

STEP 8: TIER 2 TAKE PROFIT TRIGGERS
- Another 40% of position (320,000 tokens) sells at $0.0100
- Profit: 320,000 tokens * ($0.0100 - $0.0025) = $2.40
- Remaining position: 160,000 tokens (20%)
- Daily P&L update: -$0.40 + $2.40 = +$2.00

---

TIME: 15:15 UTC (1 hour after entry)

PRICE MOVEMENT: $0.0100 → $0.0150 (6x entry)

STEP 9: TRAILING STOP UPDATES
- Price high reaches $0.0150
- Trailing stop set at: $0.0150 * 0.50 = $0.0075
- Position still open, following the trend

TIME: 15:22 UTC

PRICE MOVEMENT: $0.0150 → $0.0090 (retracement)

STEP 10: TRAILING STOP TRIGGERS
- Price hits trailing stop at $0.0075
- Final 20% (160,000 tokens) sells at $0.0090
- Profit: 160,000 tokens * ($0.0090 - $0.0025) = $1.04
- Position CLOSED ✓

FINAL SUMMARY:
- TP1 profit: +$0.80
- TP2 profit: +$2.40
- TP3 profit: +$1.04
- Total position profit: +$4.24
- Total daily P&L: -$0.40 + $4.24 = +$3.84
- Capital after trade: $10 + $3.84 = $13.84

---

TIME: End of day (23:59 UTC)

DAILY STATISTICS:
- Signals sent: 5
- Trades executed: 5
- Wins: 4
- Losses: 1
- Hit rate: 80%
- Daily profit: +$3.84
- Capital: $13.84 (38% gain)
- Daily loss limit: Not triggered (no soft pause)

DATABASE LOGGED:
- Every signal (sent / dropped, why)
- Every trade (entry, exit, P&L)
- Every error or anomaly
```

---

## 9. ERROR HANDLING & RESILIENCE

### Network/API Failures

```
Failure: Dexscreener API timeout
Response: Log error, skip that scan cycle, retry in 30 seconds

Failure: Jupiter transaction fails (insufficient liquidity)
Response: 
- Return position_size to Risk Manager
- Log: "Trade rejected: insufficient liquidity"
- Telegram: "⚠️ Signal executed but trade failed: [reason]"
- Do NOT retry automatically (avoid cascade failures)

Failure: Solana RPC returns invalid data
Response: Emergency Kill Tier 3 (see above)
```

### Invalid Signal Data

```
Missing field: confidence_score undefined
Response: Signal dropped entirely, never sent to Telegram

Invalid data: confidence_score = -5 (impossible value)
Response: Emergency Kill Tier 3, diagnostics logged
```

### Portfolio Exposure Overrun

```
Check: "Can we add this $2 position?"

Current exposure: 25% (from 2 other positions)
New position: $2 (20% of $10)
Total would be: 45%

Risk Manager: REJECTED
Telegram: "Signal dropped: Would exceed 30% portfolio exposure"
Position not sent, not executed
```

---

## 10. DEPLOYMENT & MONITORING

### Running the System

```
AWS EC2 instance (t3.micro, $6/month)
├─ Researcher Bot: Runs every 15 minutes
│  └─ Checks Dexscreener, Solscan, AI scoring
│  └─ Sends signal if confidence >= 6
├─ Position Monitor: Runs every minute
│  └─ Tracks open positions
│  └─ Closes positions on TP/SL triggers
├─ Risk Manager: Always active
│  └─ Blocks trades if limits hit
│  └─ Monitors kill switch conditions
└─ Database: SQLite (local) for now, PostgreSQL at scale
```

### Daily Review Automation

```
Each day at 23:55 UTC:
- Generate daily report (signals, trades, P&L)
- Calculate hit rate, ROI, win/loss ratio
- Send summary to Telegram
- Log to database for backtest analysis
```

---

## 11. SUCCESS CRITERIA FOR PHASE 2 COMPLETION

✅ All 6-point on-chain filters working (contract age, liquidity, holders, volume, deployer, data integrity)
✅ Confidence scoring producing reasonable scores (6-10 range)
✅ Position sizing logic deterministic (8-10 = $2, 6-7 = $1, <6 = dropped)
✅ Risk Manager enforcing daily loss limit and portfolio exposure
✅ Kill switch Tier 1, 2, 3 all triggering correctly
✅ Stop loss and take profit logic working on-chain
✅ Telegram alerts sending with correct format
✅ Database logging every signal, trade, error
✅ 10 backtest runs showing hit rate >= 60%
✅ Zero false signals (signal drops under bad conditions)

---

## 12. NEXT STEPS

**Phase 1:** Rebuild from scratch with this logic embedded
**Phase 2:** Implement all on-chain data sources
**Phase 3:** Add smart wallet tracking
**Phase 4:** Add Trading Bot with Jupiter execution
**Phase 5:** Add social layer
**Phase 6:** Self-improvement loop

---

**Document Status:** Ready for Phase 1 rebuild
**Questions:** None - system locked and ready to build
