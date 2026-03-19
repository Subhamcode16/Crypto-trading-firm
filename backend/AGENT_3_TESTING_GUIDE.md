# Agent 3 Testing Guide

## Quick Start

### Unit Tests
```bash
cd /home/node/.openclaw/workspace/projects/crypto-trading-system
python3 -m unittest tests.test_agent_3 -v
```

**Expected Result**: All tests pass ✅

### Live Testing (Week 2)
Enable the new pipeline in `researcher_bot.py`:
```python
# Change from this:
agent_2_results = self.process_with_agent_2(pairs)

# To this:
agent_2_3_results = self.process_with_agents_2_3(pairs)
```

Then monitor logs:
```bash
tail -f /path/to/logs/2026-03-*.log | grep "AGENT_3"
```

---

## Test Coverage

### Unit Tests (8 test classes)

**TestBirdeyeClient** (1 test)
- Client initialization

**TestAgent3SmartWalletDetection** (2 tests)
- No API fallback
- Top 10 trader detection

**TestAgent3InsiderActivity** (2 tests)
- Accumulating deployer detection
- Dumping deployer detection

**TestAgent3CopyTrade** (1 test)
- Strong copy-trade signal detection

**TestAgent3Scoring** (2 tests)
- Token analysis CLEARED status
- Token analysis KILLED status

**TestAgent3Performance** (1 test)
- Latency measurement (<1500ms target)

**TestAgent3Database** (2 tests)
- Successful logging
- Graceful failure if no DB

**TestAgent3Integration** (1 test)
- Tier calculation helper

---

## What Each Test Validates

### Smart Wallet Detection Tests
✅ Detects when top traders are token holders
✅ Correctly assigns tier (top_10, top_50, etc)
✅ Awards correct points (0-2)
✅ Handles missing APIs gracefully

### Insider Activity Tests
✅ Correctly identifies deployer holdings
✅ Distinguishes accumulating vs selling vs minimal
✅ Flags red/green signals appropriately
✅ Analyzes early holder behavior

### Copy-Trade Tests
✅ Finds top traders in recent buyers
✅ Calculates success rates correctly
✅ Awards points based on tier and performance
✅ Handles no matching traders gracefully

### Performance Tests
✅ Single token analysis <1500ms
✅ Suitable for 6 tokens per 30-second scan

### Integration Tests
✅ Tier calculation works across all ranges
✅ Scoring formula produces 0-10 range
✅ Confidence score 0-1 range

---

## Expected Metrics (Live Testing)

### Latency
```
Single Agent 3 analysis: 800-1200ms
- Smart wallet detection: 300-400ms
- Insider activity check: 200-300ms
- Copy-trade analysis: 300-500ms

Agent 2 + 3 combined: 1.5-2.2s per token
Target: <2.5s per token ✅
```

### Hit Rates
```
Tokens with smart wallets: 20-40%
Tokens with accumulating deployer: 10-20%
Tokens with copy-trade signals: 15-30%
```

### Database Logging
```
Agent 3 analyses per day: ~1000+ (6 tokens × 4 scans/hour × 24h)
DB size growth: ~100KB per 1000 analyses
```

---

## Running Live Test (What to Do)

### Step 1: Enable Agent 3 in Researcher Bot
Edit `src/researcher_bot.py`:
```python
# In scan() method, change:
agent_2_results = self.process_with_agent_2(pairs)
# To:
agent_2_3_results = self.process_with_agents_2_3(pairs)
```

### Step 2: Restart the Service
```bash
sudo systemctl restart researcher-bot
```

### Step 3: Monitor the Logs
```bash
journalctl -u researcher-bot -f | grep AGENT_3
```

### Step 4: Check Results
After 1 hour:
```bash
sqlite3 /path/to/database.db \
  "SELECT COUNT(*) as agent_3_analyses FROM agent_3_analysis;"
```

Expected: ~4 analyses (6 tokens per scan - those that pass Agent 2)

### Step 5: Validate Quality
```bash
sqlite3 /path/to/database.db \
  "SELECT token_address, status, wallet_score 
   FROM agent_3_analysis 
   ORDER BY analysis_timestamp DESC 
   LIMIT 10;"
```

Look for:
- Mix of CLEARED and KILLED results
- Scores spread across 0-10 range
- Reasonable confidence levels

---

## Troubleshooting

### Issue: Agent 3 analyses not appearing in database

**Check 1**: Is Agent 3 being called?
```bash
tail -f logs/2026-03-*.log | grep "AGENT_3"
```
If nothing: Agent 3 not enabled yet

**Check 2**: Is Birdeye API responding?
```python
from src.apis.birdeye_client import BirdeyeClient
client = BirdeyeClient()
traders = client.get_top_traders(limit=5)
print(traders)  # Should show trader data
```

If empty: Birdeye may have rate limit or API issue
→ Solution: Check API status, may need API key

**Check 3**: Are results being logged?
```bash
tail -f logs/2026-03-*.log | grep "logged:"
```
If yes but DB empty: Database permission issue

### Issue: Latency >2 seconds per token

**Likely cause**: Birdeye API responses slow
**Solutions**:
1. Add caching for top traders (refresh hourly)
2. Batch requests where possible
3. Increase timeout limits
4. Use API key if available (better rate limits)

### Issue: Most tokens getting KILLED by Agent 3

**Diagnosis**: Check which detection is failing most
```bash
grep "AGENT_3.*KILLED" logs/2026-03-*.log | head -20
```

**Solution**: May need to adjust thresholds:
- Smart wallet: Currently needs top 500 trader
- Insider: Currently looks for >5% holding
- Copy-trade: Currently needs top 100 trader

These are intentionally strict for safety. Adjust as needed based on results.

---

## Success Checklist (After 24h Live Test)

- [ ] Agent 3 is being called for every CLEARED token from Agent 2
- [ ] Results are being logged to database
- [ ] Latency is consistently <2s per token
- [ ] Smart wallet detection works (finds some positive cases)
- [ ] Insider activity tracking is accurate
- [ ] Copy-trade signals are identifying correct wallets
- [ ] Database has 100+ Agent 3 analyses
- [ ] No critical errors in logs
- [ ] Memory usage is stable
- [ ] CPU usage from Agent 3 is <5%

---

## Next Steps (After Validation)

### If Results Are Good ✅
→ Continue to Agent 4 implementation
→ Prepare for full pipeline (Agent 2+3+4)

### If Issues Found 🟡
→ Check `TROUBLESHOOTING` section
→ Adjust thresholds and re-test
→ Document findings

### If Major Issues 🔴
→ Stop Agent 3, revert to Agent 2 only
→ Debug API integration
→ Check with Birdeye documentation

---

## Files Related to Testing

**Test Suite**: `tests/test_agent_3.py` (12 KB)
**Agent 3 Code**: `src/agents/agent_3_wallet_tracker.py`
**Birdeye Client**: `src/apis/birdeye_client.py`
**Researcher Bot Integration**: `src/researcher_bot.py`

---

## Support / Questions

**Monday 10:00 UTC**: Report on live test results
**Wednesday 10:00 UTC**: Debug session if issues
**Friday 10:00 UTC**: Final validation before Agent 4

---

**Testing Framework**: unittest (Python standard)
**Mocking**: unittest.mock
**Code Coverage**: Not measured (can add if needed)
**Performance Profiling**: Can add cProfile if needed

