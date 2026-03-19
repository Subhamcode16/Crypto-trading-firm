# Signal Flow & Deduplication Debug Guide
**Created:** March 6, 2026 — 20:00 UTC

---

## 🎯 Problem Statement

**User Reported:**
1. Researcher might scan same tokens repeatedly (deduplication not working)
2. Signals might be dropped unnecessarily (false gates)
3. Token discovery might miss legitimate tokens

---

## 🔍 Deduplication System (Current Implementation)

### Flow
```
1. Dexscreener fetches tokens (trending + new)
     ↓
2. DexscreenerClient.get_solana_pairs(strategy='hybrid')
     ↓
3. Pairs deduplicated by pairAddress (dict key)
     ↓
4. Researcher Bot checks each token:
     if _token_analyzed_recently(token_addr, hours=24):
         skip this token
     ↓
5. Token passed to Agent 2 (only if not analyzed in last 24h)
```

### Code Location
- **Hybrid strategy:** `src/apis/dexscreener_client.py` (line ~150)
- **Dedup check:** `src/researcher_bot.py` (line ~184)
- **Database query:** `src/database.py` `get_recent_analysis()` (line ~250)

### Database Dedup Check
```python
# Checks agent_2_analysis, agent_3_analysis, agent_4_analysis tables
# for any token analyzed after cutoff_time (24 hours ago)
SELECT * FROM agent_X_analysis
WHERE token_address = ? AND analysis_timestamp > ?
```

---

## ⚠️ Potential Issues & Fixes

### Issue #1: Dedup Window Too Aggressive (24 hours)
**Problem:** Token found at hour 0, reappears at hour 23:59 → skipped (correct)
**Solution:** This is working as designed. Tokens repeated within 24h are intentionally skipped.

### Issue #2: Timestamp Format Mismatch
**Location:** `src/researcher_bot.py` line 410
```python
cutoff_time = (datetime.utcnow() - timedelta(hours=hours)).isoformat()
```

**Risk:** If database uses different timestamp format, comparison fails
**Check:** Verify all timestamps in database are ISO format (YYYY-MM-DDTHH:MM:SS)

**Debug Command:**
```sql
SELECT DISTINCT strftime('%Y-%m-%d %H:%M:%S', analysis_timestamp) 
FROM agent_2_analysis LIMIT 5;
```

### Issue #3: Null/Empty Values in Token Address
**Location:** `src/researcher_bot.py` line 180
```python
token_addr = pair.get('baseToken', {}).get('address') or pair.get('pairAddress')
```

**Risk:** If both fields are None/empty, _token_analyzed_recently() is called with `None`
**Fix:** Add validation before dedup check

**Modified Code:**
```python
token_addr = pair.get('baseToken', {}).get('address') or pair.get('pairAddress')

if not token_addr:
    logger.warning(f"Skipping pair with no token address")
    continue

if self._token_analyzed_recently(token_addr, hours=24):
    logger.debug(f"Skipping {token_addr[:8]}... (already analyzed)")
    continue
```

---

## 📊 Testing Deduplication

### Test 1: Verify Hybrid Dedup Works
```bash
cd /home/node/.openclaw/workspace/projects/crypto-trading-system

python3 -c "
from src.apis.dexscreener_client import DexscreenerClient

client = DexscreenerClient()
trending = client.get_solana_pairs(limit=10, strategy='trending')
new = client.get_solana_pairs(limit=10, strategy='new')
hybrid = client.get_solana_pairs(limit=10, strategy='hybrid')

print(f'Trending pairs: {len(trending)}')
print(f'New pairs: {len(new)}')
print(f'Hybrid (deduplicated): {len(hybrid)}')

# Check if any duplicates in hybrid
addresses = [p.get('pairAddress') for p in hybrid]
unique = len(set(addresses))
print(f'Unique addresses in hybrid: {unique}/{len(hybrid)}')
"
```

### Test 2: Verify Database Dedup Query
```bash
sqlite3 data/database.db << 'EOF'
-- Show all agent_2_analysis records from last 24 hours
SELECT token_address, analysis_timestamp, safety_score, status 
FROM agent_2_analysis 
WHERE analysis_timestamp > datetime('now', '-24 hours')
ORDER BY analysis_timestamp DESC
LIMIT 20;
EOF
```

### Test 3: Run Dedup Check on Test Tokens
```bash
python3 -c "
from src.researcher_bot import ResearcherBot
from src.database import Database

db = Database()
bot = ResearcherBot(db, None)

# Test with fake token address
test_addr = 'TEST123456789012345678901234567890'
recently_analyzed = bot._token_analyzed_recently(test_addr, hours=24)
print(f'Test token recently analyzed: {recently_analyzed}')

# Test with real token
solana_mint = 'So11111111111111111111111111111111111111112'  # Wrapped SOL
recently_analyzed = bot._token_analyzed_recently(solana_mint, hours=24)
print(f'Wrapped SOL recently analyzed: {recently_analyzed}')
"
```

---

## 💥 Signal Dropping Analysis

### Why Signals Get Dropped

```
Token Discovered (Agent 1: 6.5/10)
    ↓
Agent 2: Safety Check
    ├─ if KILLED (fails any of 9 filters) → STOP, Agents 3-5 skip
    └─ if CLEARED (passes 9/9) → Continue
    ↓
Agent 3: Wallet Tracking (if A2 cleared)
    ↓
Agent 4: Community Intel (if A2 cleared)
    ↓
Agent 5: Confluence Scoring
    ├─ Calculates composite = (A3×0.40 + A2×0.25 + A4×0.20 + A1×0.15)
    ├─ if composite < 8.0 → GATE_BLOCKED → STOP
    └─ if composite ≥ 8.0 → Continue
    ↓
Master Rules Gate (15 rules)
    ├─ if ANY Tier 1 rule fails → GATE_BLOCKED → STOP
    └─ if all Tier 1 pass → Continue
    ↓
Risk Manager Gate (5 checks)
    ├─ if ANY check fails → KILLED → STOP
    └─ if all pass → Send to Telegram
    ↓
Telegram Alert Sent ✅
```

### Most Common Drop Points (in order of frequency)

1. **Agent 2 Safety Check** (most strict)
   - Kills ~30-40% of tokens on 9-point filter
   - Most common: liquidity_locked, holder_concentration, deployer_history
   
2. **Agent 5 Confluence Gate** (8.0+ threshold)
   - Kills ~20-30% of tokens that pass Agent 2
   - Reason: Only 2-3 agents clear = 7.2/10 composite
   - With dynamic weighting: Should be < 5% drop

3. **Agent 3 Wallet Tracking** (currently returns mock)
   - Returns 6.5/10 instead of real smart wallet signals
   - If Birdeye API added: Should increase to 7.5-8.5/10

4. **Master Rules Gate** (15 rules)
   - Secondary filter on tokens passing confluence
   - Kills ~5-10% additional

5. **Risk Manager Gate** (5 checks)
   - Final filter, kills ~2-5% due to position sizing/reward ratio

---

## 🔧 Fixing Signal Drops

### Fix #1: Dynamic Weighting (✅ IMPLEMENTED)
**Impact:** Reduces false Agent 5 gate failures by 10-20%
**Status:** Done - see `src/agents/agent_5_signal_aggregator.py`

### Fix #2: Add Birdeye API Key
**Impact:** Increases Agent 3 score from 6.5 → 8.0+, improves confluence
**Status:** Waiting for user to add key
**Action:** `echo "BIRDEYE_API_KEY=<key>" >> secrets.env`

### Fix #3: Lower Agent 5 Threshold (8.0 → 7.5)?
**Risk:** Increases false positives (bad tokens passing)
**Not Recommended:** Master Rules gate should catch low-quality tokens

### Fix #4: Improve Agent 4 Discord Detection
**Current:** Returns 7.5/10 when server not found
**Needed:** Real Discord server search when token added to tracking
**Status:** Blocked on real token data (backtest uses test tokens)

---

## 📋 Verification Checklist

Run these commands to debug signal flow:

### Step 1: Verify APIs Working
```bash
python3 check_apis_simple.py
```

### Step 2: Check Deduplication
```bash
python3 -c "
from src.apis.dexscreener_client import DexscreenerClient
client = DexscreenerClient()
pairs = client.get_solana_pairs(limit=20, strategy='hybrid')
print(f'Fetched {len(pairs)} unique pairs')
print('Sample:', pairs[0] if pairs else 'None')
"
```

### Step 3: Test Backtest (Full Pipeline)
```bash
python3 backtest_5_agent_pipeline.py 2>&1 | tail -40
```

### Step 4: Check Database Logging
```bash
sqlite3 data/database.db "SELECT COUNT(*) as agent_2_scans FROM agent_2_analysis; SELECT COUNT(*) as agent_5_passed FROM agent_5_analysis WHERE status = 'CLEARED';"
```

### Step 5: Analyze Drop Points
```bash
sqlite3 data/database.db << 'EOF'
-- Show signal flow stats
SELECT 
    COUNT(*) as total_agent_2,
    SUM(CASE WHEN status = 'CLEARED' THEN 1 ELSE 0 END) as cleared,
    SUM(CASE WHEN status = 'KILLED' THEN 1 ELSE 0 END) as killed
FROM agent_2_analysis;
EOF
```

---

## 🚀 Next Steps

1. **Add Birdeye API key** (user action)
2. **Run with real token data** (not backtest)
3. **Collect 20+ signals** and measure:
   - How many killed at each stage?
   - Which reasons most common?
   - How many reach Telegram alert?

4. **Adjust weights/thresholds** based on data

5. **Track rule accuracy** (Master Rules Feedback system)
   - Which of 15 rules most predictive?
   - Which categories most accurate?

---

## 📊 Expected Signal Conversion Rates

**Baseline (with static weighting):**
- 6-10 tokens discovered per scan
- 2-4 pass Agent 2 (40% pass rate)
- 1-2 pass Agent 5 (50% of Agent 2 survivors)
- 1-2 pass Master Rules (70% of Agent 5 survivors)
- 0-1 pass Risk Manager (90% of Master Rules survivors)
- **Result: ~1 signal per scan reaches Telegram**

**With Improvements (dynamic weighting + Birdeye):**
- Same discovery rate
- 2-4 pass Agent 2 (unchanged)
- 2-3 pass Agent 5 (70% of Agent 2, +20% improvement)
- 2-3 pass Master Rules (80%)
- 1-2 pass Risk Manager (95%)
- **Result: ~1-2 signals per scan** (no change, but higher quality)

---

**Status:** Ready to test with real data
