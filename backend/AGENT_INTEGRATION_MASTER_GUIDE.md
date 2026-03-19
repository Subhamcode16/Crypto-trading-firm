# Agent Integration Master Guide

## System Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│ RESEARCHER BOT (Main Loop - Every 15 minutes)                           │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
                    ┌───────────────────────────┐
                    │  Fetch Tokens from DEX   │
                    │  (Dexscreener: 6 tokens) │
                    └───────────────────────────┘
                                    │
                                    ▼
        ┌──────────────────────────────────────────────────────┐
        │  FOR EACH TOKEN: Run Agent Pipeline                 │
        └──────────────────────────────────────────────────────┘
                                    │
                    ┌───────────────┴────────────────┐
                    ▼                                ▼
        ┌─────────────────────┐        ┌─────────────────────┐
        │   AGENT 2           │        │   AGENT 2           │
        │  Safety Filters     │        │  Safety Filters     │
        │ (9 sequential)      │        │ (9 sequential)      │
        │                     │        │                     │
        │ Input: Token addr   │        │ Input: Token addr   │
        │ Output: KILLED      │        │ Output: CLEARED ✓   │
        │         (liquidity) │        │                     │
        └─────────────────────┘        └──────────┬──────────┘
                    │                             │
                    │ (skip)                      │ (continue)
                    │                             ▼
                    │                  ┌─────────────────────┐
                    │                  │   AGENT 3           │
                    │                  │ Wallet Tracker      │
                    │                  │                     │
                    │                  │ Input: Token addr   │
                    │                  │ Output: Score 0-10  │
                    │                  │        Confidence   │
                    │                  └──────────┬──────────┘
                    │                             │
                    │                             ▼
                    │                  ┌─────────────────────┐
                    │                  │   AGENT 4           │
                    │                  │ Intel Agent         │
                    │                  │                     │
                    │                  │ Input: Token addr   │
                    │                  │        Token symbol │
                    │                  │ Output: Score 0-10  │
                    │                  │        Confidence   │
                    │                  └──────────┬──────────┘
                    │                             │
                    └─────────────────┬───────────┘
                                      ▼
                        ┌──────────────────────────┐
                        │  MASTER RULES ENGINE     │
                        │                          │
                        │ Combines:                │
                        │ - Agent 2 safety score  │
                        │ - Agent 3 wallet score  │
                        │ - Agent 4 community     │
                        │                          │
                        │ Calculates:              │
                        │ - Final signal score     │
                        │ - Position size          │
                        │ - Entry/TP/SL prices    │
                        │ - BUY / SKIP decision    │
                        └──────────────┬───────────┘
                                      │
                        ┌─────────────┴──────────┐
                        ▼                        ▼
                    ┌────────────┐          ┌─────────┐
                    │ BUY SIGNAL │          │  SKIP   │
                    │ → Trade    │          │ Logged  │
                    └────────────┘          └─────────┘
```

---

## Data Flow for Each Token

### Step 1: Token Discovery
```json
{
  "token_address": "DRLNhjM7jusYFPF1z5ZisK5DjdXLiquidxxx",
  "token_name": "Droneland",
  "token_symbol": "DRLN",
  "discovered_at": "2026-03-03T14:07:40",
  "discovery_source": "dexscreener"
}
```

### Step 2: Agent 2 Processing (Safety Check)
**File**: `src/agents/agent_2_on_chain_analyst.py`
**Database**: `agent_2_analysis` table

```python
# Code flow
analyst_2 = OnChainAnalyst(config)
result_2 = analyst_2.analyze_token(token_address)
# result_2 = {
#   "status": "CLEARED" or "KILLED",
#   "score": 8.5,
#   "filters": {...},
#   ...
# }
db.log_agent_2_analysis(result_2)
```

**Output**:
```json
{
  "agent_id": 2,
  "token_address": "...",
  "status": "CLEARED",
  "score": 8.5,
  "confidence": 0.95,
  "filters_passed": [
    "contract_age", "liquidity_locked", "deployer_history", ...
  ],
  "failure_reason": null
}
```

**Decision Gate**:
- If status = "KILLED" → **STOP** (skip to next token)
- If status = "CLEARED" → **CONTINUE to Agent 3**

---

### Step 3: Agent 3 Processing (Wallet Intelligence)
**File**: `src/agents/agent_3_wallet_tracker.py`
**Database**: `agent_3_analysis` table

```python
# Code flow
tracker_3 = Agent3WalletTracker(config)
tracker_3.solscan = solscan_client
tracker_3.birdeye = birdeye_client  # When API available
tracker_3.db = database

result_3 = tracker_3.analyze_token(token_address)
# result_3 = {
#   "status": "CLEARED" or "KILLED",
#   "score": 7.2,
#   "confidence": 0.78,
#   "smart_wallets_detected": [...],
#   "insider_status": {...},
#   ...
# }
db.log_agent_3_analysis(result_3)
```

**Output**:
```json
{
  "agent_id": 3,
  "token_address": "...",
  "status": "CLEARED",
  "score": 7.2,
  "confidence": 0.78,
  "smart_wallets_detected": [
    {
      "wallet": "addr1...",
      "name": "Top Trader #5",
      "historical_wr": 0.68,
      "investment_amount": 50000
    }
  ],
  "insider_status": {
    "deployer": "addr2...",
    "deployer_action": "holding"
  }
}
```

**Decision Gate**:
- If score < 5.0 (optional) → **SKIP**
- Always → **CONTINUE to Agent 4** (both CLEARED and KILLED inputs OK)

---

### Step 4: Agent 4 Processing (Community Intelligence)
**File**: `src/agents/agent_4_intel_agent.py`
**Database**: `agent_4_analysis` table

```python
# Code flow
intel_4 = Agent4IntelAgent(config)
intel_4.discord_client = discord_api  # When ready
intel_4.twitter_client = twitter_api  # When ready
intel_4.db = database

result_4 = intel_4.analyze_token(
    token_address=token_address,
    token_symbol=token_symbol,
    token_description=token_description
)
# result_4 = {
#   "status": "CLEARED" or "KILLED",
#   "score": 6.8,
#   "confidence": 0.72,
#   "community": {...},
#   "social": {...},
#   ...
# }
db.log_agent_4_analysis(result_4)
```

**Output**:
```json
{
  "agent_id": 4,
  "token_address": "...",
  "token_symbol": "DRLN",
  "status": "CLEARED",
  "score": 6.8,
  "confidence": 0.72,
  "community": {
    "discord": {
      "server_found": true,
      "member_count": 1250,
      "sentiment": 0.78
    },
    "telegram": {...}
  },
  "social": {
    "twitter": {
      "mentions_24h": 87,
      "sentiment": 0.72
    }
  }
}
```

---

### Step 5: Master Rules Engine (Final Decision)
**File**: `src/rules/trading_rules_engine.py`
**Database**: `signals` table

```python
# Code flow
rules_engine = TradingRulesEngine()

final_signal = rules_engine.evaluate(
    agent_2_result=result_2,
    agent_3_result=result_3,
    agent_4_result=result_4,
    token_metadata={...}
)

# final_signal = {
#   "decision": "BUY" or "SKIP",
#   "combined_score": 7.5,
#   "confidence": 0.82,
#   "entry_price": 0.00015,
#   "position_size_usd": 50,
#   "tp1": 0.00025,
#   "tp2": 0.00040,
#   "sl": 0.00012,
#   ...
# }

if final_signal['decision'] == 'BUY':
    db.log_signal(final_signal)
    telegram_bot.send_alert(final_signal)  # Notify user
    executor.place_order(final_signal)     # Execute trade (paper/live)
else:
    logger.info(f"Signal skipped: {reason}")
```

**Final Output** (saved to `signals` table):
```json
{
  "signal_id": "SIG_20260303_001",
  "token_address": "...",
  "token_symbol": "DRLN",
  "discovered_at": "2026-03-03T14:07:40",
  "agent_scores": {
    "agent_2": {
      "status": "CLEARED",
      "score": 8.5,
      "completion_time": "2026-03-03T14:07:43.500"
    },
    "agent_3": {
      "status": "CLEARED",
      "score": 7.2,
      "completion_time": "2026-03-03T14:07:45.200"
    },
    "agent_4": {
      "status": "CLEARED",
      "score": 6.8,
      "completion_time": "2026-03-03T14:07:47.100"
    }
  },
  "combined_score": 7.5,
  "master_rules_verdict": "BUY",
  "confidence": 0.82,
  "entry_price": 0.00015,
  "position_size_usd": 50,
  "target_tp1": 0.00025,
  "target_tp2": 0.00040,
  "stop_loss": 0.00012,
  "expected_profit_percent": 150,
  "status": "SENT"
}
```

---

## Implementation Checklist

### Phase 1: Agent 2 (COMPLETE ✓)
- [x] OnChainAnalyst class
- [x] 9 sequential safety filters
- [x] Database table + logging
- [x] Integration into researcher_bot
- [x] 48-hour validation running

### Phase 2: Agent 3 (IN PROGRESS)
- [x] Agent3WalletTracker class (scaffold)
- [x] Database table + logging
- [ ] Birdeye API client
- [ ] Smart wallet detection logic
- [ ] Insider activity tracking
- [ ] Copy-trade signal detection
- [ ] Integration into researcher_bot
- [ ] Testing + validation

### Phase 3: Agent 4 (IN PROGRESS)
- [x] Agent4IntelAgent class (scaffold)
- [x] Database table + logging
- [ ] Discord API client
- [ ] Telegram API client
- [ ] Twitter/X API client
- [ ] Sentiment analysis logic
- [ ] Community metrics calculation
- [ ] Narrative strength scoring
- [ ] Coordination pattern detection
- [ ] Integration into researcher_bot
- [ ] Testing + validation

### Phase 4: Master Rules Engine (READY)
- [x] TradingRulesEngine class (exists)
- [x] Rule consensus logic
- [ ] Agent score weighting (0.4 / 0.3 / 0.3)
- [ ] Combined scoring formula
- [ ] Entry threshold (7.0/10)
- [ ] Position sizing
- [ ] TP/SL calculation

---

## Integration into Researcher Bot

### Current Code (process_with_agent_2)

```python
def process_with_agent_2(self, candidates):
    """Process candidates through Agent 2 only"""
    cleared_tokens = []
    killed_tokens = []
    
    for candidate in candidates:
        token_address = candidate.get('baseToken', {}).get('address')
        result = analyst.analyze_token(token_address)
        
        if result['status'] == 'CLEARED':
            cleared_tokens.append(result)
        else:
            killed_tokens.append(result)
        
        analyst.log_to_database(result)
    
    return {'cleared': cleared_tokens, 'killed': killed_tokens}
```

### Future Code (process_with_all_agents)

```python
def process_with_all_agents(self, candidates):
    """Process candidates through Agent 2 → 3 → 4"""
    signals = []
    
    for candidate in candidates:
        token_address = candidate.get('baseToken', {}).get('address')
        token_symbol = candidate.get('baseToken', {}).get('symbol')
        
        # Agent 2: Safety (must CLEAR to continue)
        result_2 = analyst_2.analyze_token(token_address)
        analyst_2.log_to_database(result_2)
        
        if result_2['status'] == 'KILLED':
            continue  # Skip to next token
        
        # Agent 3: Wallet Intelligence
        result_3 = tracker_3.analyze_token(token_address)
        tracker_3.log_to_database(result_3)
        
        # Agent 4: Community Intelligence
        result_4 = intel_4.analyze_token(
            token_address=token_address,
            token_symbol=token_symbol,
            token_description=candidate.get('description', '')
        )
        intel_4.log_to_database(result_4)
        
        # Master Rules Engine
        final_signal = rules_engine.evaluate(result_2, result_3, result_4, candidate)
        
        if final_signal['decision'] == 'BUY':
            signals.append(final_signal)
            self.db.log_signal(final_signal)
            self.telegram.send_signal(final_signal)
    
    return signals
```

---

## Testing Strategy

### Unit Tests
```
tests/
├── test_agent_2.py          # Agent 2 filters
├── test_agent_3.py          # Wallet detection
├── test_agent_4.py          # Community analysis
├── test_master_rules.py      # Signal combination
└── test_integration.py       # End-to-end
```

### Integration Test Flow
```
1. Load test token address (known safe)
2. Run through Agent 2 → should CLEAR
3. Run through Agent 3 → should score 5.0+
4. Run through Agent 4 → should score 5.0+
5. Check Master Rules → should BUY
6. Verify signal logged to database
7. Check frontend receives data
```

---

## Performance Targets

| Component | Target | Current |
|-----------|--------|---------|
| Agent 2 latency | <1 sec | ~0.5 sec ✓ |
| Agent 3 latency | <1.5 sec | TBD |
| Agent 4 latency | <2 sec | TBD |
| Total per token | <4.5 sec | TBD |
| 6 tokens per scan | <30 sec | TBD |
| Scan cycle (15 min) | <10 min used | TBD |

---

## Database Schema Reference

```sql
-- Agent 2 Results
SELECT token_address, status, safety_score, failed_filter 
FROM agent_2_analysis 
ORDER BY analysis_timestamp DESC LIMIT 10;

-- Agent 3 Results
SELECT token_address, status, wallet_score, confidence 
FROM agent_3_analysis 
ORDER BY analysis_timestamp DESC LIMIT 10;

-- Agent 4 Results
SELECT token_address, token_symbol, status, intel_score 
FROM agent_4_analysis 
ORDER BY analysis_timestamp DESC LIMIT 10;

-- Final Signals
SELECT signal_id, token_symbol, status, combined_score 
FROM signals 
ORDER BY timestamp DESC LIMIT 10;
```

---

## Next Steps

### Week 2: Build Agent 3
1. Create Birdeye API client
2. Implement smart wallet detection
3. Implement insider activity tracking
4. Implement copy-trade signal logic
5. Add Agent 3 to researcher_bot loop
6. Test & validate for 24h

### Week 2-3: Build Agent 4
1. Create Discord API client
2. Create Twitter/X API client (or use existing)
3. Implement community metrics
4. Implement sentiment analysis
5. Add Agent 4 to researcher_bot loop
6. Test & validate for 24h

### Week 3-4: Master Rules + Integration
1. Tune agent weighting (0.4/0.3/0.3)
2. Implement combined scoring
3. Full pipeline testing
4. Paper trading validation
5. Backend API ready for frontend

---

## Notes for Frontend Developer

**Data Available Now**:
- Agent 2 analysis (48-hour validation in progress)
- JSON files for Agent 2 results
- Database schema ready for Agents 3+4

**Data Coming Soon**:
- Agent 3 analysis (Week 2)
- Agent 4 analysis (Week 2-3)
- Final signal objects (Master Rules output)

**Frontend Can Start With**:
- Display Agent 2 results from `agent_2_analysis` table
- Show real-time scan status
- Show filter hit rate metrics
- Build UI scaffolding for Agent 3+4 panels

**API Contract**: See `BACKEND_API_CONTRACT.md`

