# Parallel Development: Backend + Frontend (March 3, 2026)

## Strategy
- **Backend (Alex)**: Build Agents 3+4 integration, Master Rules, testing
- **Frontend (Subham)**: Design dashboard, build UI, consume APIs
- **Timeline**: Work in parallel, integrate weekly

---

## Backend Deliverables (This Session)

### ✅ COMPLETED
1. **Agent 2 Monitoring** (Running 48 hours)
   - Metrics collection module created
   - File: `src/monitoring/agent_2_metrics.py`
   - Tracking: scan count, filter hits, latency, kill rates

2. **Agent 3 Implementation** (Wallet Tracker)
   - File: `src/agents/agent_3_wallet_tracker.py` (8.5 KB)
   - Class: `Agent3WalletTracker`
   - Methods: smart wallet detection, insider activity, copy-trade signals
   - Scoring: 0-10 scale with confidence
   - Database table: `agent_3_analysis`
   - Logging method: `log_agent_3_analysis()`

3. **Agent 4 Implementation** (Intel Agent)
   - File: `src/agents/agent_4_intel_agent.py` (13 KB)
   - Class: `Agent4IntelAgent`
   - Methods: Discord/Telegram metrics, Twitter sentiment, narrative strength, coordination patterns
   - Scoring: 0-10 scale with confidence
   - Database table: `agent_4_analysis`
   - Logging method: `log_agent_4_analysis()`

4. **Database Schema**
   - Extended `init_schema()` with 3 agent tables
   - Added `log_agent_3_analysis()` method
   - Added `log_agent_4_analysis()` method
   - All syntax verified ✓

5. **API Contract** (For Frontend)
   - File: `BACKEND_API_CONTRACT.md` (14 KB)
   - Data models for all agents
   - REST API endpoints
   - WebSocket streaming options
   - File-based sync alternative
   - Real-time data feeds defined

6. **Integration Guide**
   - File: `AGENT_INTEGRATION_MASTER_GUIDE.md` (15 KB)
   - Complete system architecture diagram
   - Data flow for each token
   - Step-by-step signal generation
   - Implementation checklist
   - Performance targets
   - Testing strategy

---

## File Structure

```
crypto-trading-system/
├── src/
│   ├── agents/
│   │   ├── agent_2_on_chain_analyst.py       (17 KB) ✓
│   │   ├── agent_3_wallet_tracker.py         (8.5 KB) ✓
│   │   └── agent_4_intel_agent.py            (13 KB) ✓
│   ├── monitoring/
│   │   ├── __init__.py
│   │   └── agent_2_metrics.py                (5 KB) ✓
│   ├── database.py                           (EXTENDED) ✓
│   └── researcher_bot.py                     (FIXED) ✓
├── docs/
│   ├── BACKEND_API_CONTRACT.md               (14 KB) ✓
│   ├── AGENT_INTEGRATION_MASTER_GUIDE.md     (15 KB) ✓
│   ├── PHASE_2B_AGENTS_3_4_FRAMEWORK.md      (6.8 KB) ✓
│   └── HYBRID_EXECUTION_PROTOCOL.md          (existing)
└── data/
    ├── database.db                           (schema updated)
    └── metrics/
        └── agent_2_metrics.json              (auto-created)
```

---

## Backend Status: READY FOR IMPLEMENTATION

### Week 2: Agent 3 Implementation Details

**What Needs to Be Built**:
1. Birdeye API client (`src/apis/birdeye_client.py`)
   - Get top trader wallets
   - Get wallet history
   - Validate win rates

2. Solscan extensions (already exist, may need updates)
   - `get_top_holders(token_address)` - get top N wallets
   - `get_deployer_history(deployer)` - token history
   - Balance change tracking (24h delta)

3. Complete Agent 3 detection logic
   - `detect_smart_wallets()` - fill implementation
   - `detect_insider_activity()` - fill implementation
   - `detect_copy_trade_signal()` - fill implementation

4. Integration into researcher_bot
   - Call `tracker_3.analyze_token()` for CLEARED tokens
   - Pass results through Master Rules

**Estimated Time**: 2-3 days

### Week 2-3: Agent 4 Implementation Details

**What Needs to Be Built**:
1. Discord API client (`src/apis/discord_client.py`)
   - Connect to Discord bot account
   - Get server stats
   - Analyze message sentiment

2. Twitter/X API client (`src/apis/twitter_client.py`)
   - Search tweets by symbol
   - Get engagement metrics
   - Analyze sentiment

3. Sentiment analyzer (`src/analysis/sentiment_analyzer.py`)
   - LLM-based or regex-based
   - Score sentiment 0-1.0
   - Extract topics

4. Complete Agent 4 detection logic
   - `detect_discord_community()` - fill implementation
   - `detect_telegram_community()` - fill implementation
   - `detect_twitter_sentiment()` - fill implementation
   - `detect_narrative_strength()` - fill implementation
   - `detect_coordination_pattern()` - fill implementation

5. Integration into researcher_bot
   - Call `intel_4.analyze_token()` for all candidates
   - Pass results through Master Rules

**Estimated Time**: 3-4 days

### Week 3-4: Master Rules + Integration

**What Needs to Be Done**:
1. Implement combined scoring
   - Agent 2: 40% weight (safety baseline)
   - Agent 3: 30% weight (smart money signals)
   - Agent 4: 30% weight (community strength)
   - Formula: `score = (A2*0.4) + (A3*0.3) + (A4*0.3) + rules_bonus`

2. Position sizing based on scores
   - 7.0-7.5: 25 USD per position
   - 7.5-8.0: 50 USD per position
   - 8.0-8.5: 75 USD per position
   - 8.5+: 100 USD per position

3. Risk management integration
   - Take profit: variable based on score
   - Stop loss: fixed -10% soft / -20% hard
   - Position limits: max 5% of portfolio

4. Full pipeline testing
   - All 3 agents working together
   - Signals flowing through Master Rules
   - Results stored in database
   - Frontend receiving data

**Estimated Time**: 3-4 days

---

## Frontend Deliverables Needed

### From Documentation Provided
All the data models and API contracts are already defined in:
- `BACKEND_API_CONTRACT.md`
- `AGENT_INTEGRATION_MASTER_GUIDE.md`

### Data Available Now
- Agent 2 analyses (in database + JSON)
- Real-time scan status
- Risk metrics
- Performance metrics

### Frontend Can Build
1. **Agent 2 Panel**
   - Display filter results
   - Show latency per token
   - Safety score visualization
   - Hit rate distribution

2. **Metrics Dashboard**
   - 48-hour validation progress
   - Filter hit rates
   - Kill rate trends
   - Scan performance

3. **Control Panel**
   - Start/stop scanning
   - Manual trade entry
   - Position management
   - Alert configuration

4. **Placeholder Panels** (Ready after Week 2-3)
   - Agent 3 results
   - Agent 4 results
   - Final signals
   - Trading P&L

---

## API Endpoints to Implement (Backend)

### Real-Time
```
GET /api/v1/realtime/current-scan
GET /api/v1/realtime/active-positions
GET /api/v1/realtime/risk-metrics
```

### Historical
```
GET /api/v1/history/signals?limit=20&start_date=2026-03-01
GET /api/v1/history/trades?status=closed
GET /api/v1/metrics/agent-2?period=48h
```

### Control
```
POST /api/v1/control/pause-scanning
POST /api/v1/control/close-position/{position_id}
```

---

## Testing Plan

### Phase 1: Unit Tests (Week 2)
```python
# test_agent_3.py
test_smart_wallet_detection()
test_insider_activity_tracking()
test_copy_trade_signals()

# test_agent_4.py
test_discord_metrics()
test_twitter_sentiment()
test_narrative_scoring()
```

### Phase 2: Integration Tests (Week 3)
```python
# test_integration.py
def test_full_pipeline():
    1. Load test token
    2. Run Agent 2 → Assert CLEARED
    3. Run Agent 3 → Assert score > 5.0
    4. Run Agent 4 → Assert score > 5.0
    5. Master Rules → Assert BUY decision
    6. Check database → Assert signal logged
    7. Check API → Assert data returned
```

### Phase 3: Live Validation (Week 4)
```
Run with Agent 2+3+4 for 48 hours
Measure:
- Latency: target <4.5 sec per token
- Hit rate: goal 40%+ pass all filters
- Signal quality: track in paper trading
```

---

## Dependencies & APIs Needed

### Agent 2 (Already Have)
- [x] Solscan API (free tier)
- [x] Helius RPC (free tier)
- [x] DexScreener API (free)
- [x] Rugcheck API (free)

### Agent 3 (Need To Implement)
- [ ] Birdeye API (may require key - research availability)
- [x] Solscan (already have)
- [x] Helius (already have)

### Agent 4 (Need To Implement)
- [ ] Discord Bot Token (easy - self-hosted)
- [ ] Twitter/X API v2 Key (need to apply - free tier available)
- [ ] Telegram Bot Token (easy - create with BotFather)
- [ ] NLP/Sentiment API or LLM access (have Haiku access)

### No Breaking Changes
All new code is additive - Agent 2 continues running without modification.

---

## Communication Protocol

**Weekly Sync Points**:
- **Monday**: Discuss Agent 3 progress, frontend mockups
- **Wednesday**: Agent 3 integration testing, frontend data flow
- **Friday**: Agent 4 review, full system testing

**Shared Documentation**:
- `BACKEND_API_CONTRACT.md` - Source of truth for data models
- `AGENT_INTEGRATION_MASTER_GUIDE.md` - Architecture reference
- Database schema - Always up to date

**Git Workflow** (recommended):
```
main branch: stable, tested code
  ├── backend/agent-3 branch (Alex)
  ├── backend/agent-4 branch (Alex)
  ├── backend/master-rules branch (Alex)
  └── frontend/dashboard branch (Subham)

Weekly merges to main after testing
```

---

## Success Criteria

### Week 2
- [x] Agent 3 code complete (this session)
- [ ] Agent 3 API clients (Birdeye, etc)
- [ ] Agent 3 detection logic filled in
- [ ] Agent 3 tested with 10+ known tokens
- [ ] Frontend can display Agent 2 metrics

### Week 3
- [ ] Agent 4 code complete
- [ ] Agent 4 API clients (Discord, Twitter, etc)
- [ ] Agent 4 detection logic filled in
- [ ] Agent 4 tested with 10+ known tokens
- [ ] Frontend displays Agent 3 results

### Week 4
- [ ] Master Rules integrated
- [ ] All 3 agents working together
- [ ] Full pipeline end-to-end tested
- [ ] Dashboard live with real data
- [ ] Ready for paper trading

---

## Quick Reference: Agent Scaffolds

All agent code is in place with:
- ✓ Class definitions
- ✓ Method signatures
- ✓ Logging infrastructure
- ✓ Database integration
- ✓ Placeholder comments showing what to build

**To Implement**: Fill in the TODO sections in:
- `agent_3_wallet_tracker.py` (search for "TODO")
- `agent_4_intel_agent.py` (search for "TODO")

No refactoring needed - just implement the logic.

---

## Next Steps

### Backend (Alex)
1. **This Week**: 
   - Confirm Birdeye API availability for Agent 3
   - Confirm Twitter/X API access for Agent 4
   - Start Agent 3 implementation (wallet detection)

2. **Next Week**:
   - Complete Agent 3, integrate into researcher_bot
   - Start Agent 4 implementation
   - Prepare test cases

3. **Week 3**:
   - Complete Agent 4, integrate into researcher_bot
   - Start Master Rules implementation
   - Full pipeline testing

### Frontend (Subham)
1. **This Week**:
   - Design dashboard layout
   - Create mockups for all panels
   - Plan API integration

2. **Next Week**:
   - Build Agent 2 metrics panel
   - Build control panel
   - Integrate with Agent 2 API

3. **Week 3**:
   - Add Agent 3 panel
   - Add Agent 4 panel
   - Full dashboard live with real data

---

## Files to Review

**Backend Documentation**:
1. `BACKEND_API_CONTRACT.md` - Data models & REST API
2. `AGENT_INTEGRATION_MASTER_GUIDE.md` - System architecture
3. `PHASE_2B_AGENTS_3_4_FRAMEWORK.md` - Agent design philosophy

**Backend Code**:
1. `src/agents/agent_3_wallet_tracker.py` - Agent 3 scaffold
2. `src/agents/agent_4_intel_agent.py` - Agent 4 scaffold
3. `src/database.py` - Schema extensions

**For Frontend**:
1. `BACKEND_API_CONTRACT.md` - Everything you need
2. Sample data in `data/realtime/` (will be populated by backend)

---

**Status**: ✅ Backend Ready for Parallel Development
**Frontend**: Ready to Design & Build
**Target**: Full system operational Week 4

