# START HERE: Parallel Backend + Frontend Development

**Status**: ✅ Ready to Build
**Date**: March 3, 2026
**Duration**: 4 weeks to paper trading ready

---

## Quick Summary

### What We Did Today
- ✅ Fixed Agent 2 database logging (48-hour validation running)
- ✅ Built Agent 3 scaffold (Wallet Tracker)
- ✅ Built Agent 4 scaffold (Intel Agent)
- ✅ Extended database with 3 agent analysis tables
- ✅ Documented all data models and APIs for frontend

### What's Ready Now
- **Backend**: All code in place, ready for API integration
- **Frontend**: All specifications defined, ready to build
- **Data**: Agent 2 metrics flowing, Agents 3+4 coming Week 2

---

## For Subham (Frontend Development)

### Read These First (In Order)
1. **`BACKEND_API_CONTRACT.md`** (14 KB)
   - Everything about data structures
   - REST API endpoints
   - Real-time data feeds
   - Sample JSON for each agent

2. **`AGENT_INTEGRATION_MASTER_GUIDE.md`** (15 KB)
   - System architecture diagram
   - Data flow for each token
   - How agents work together
   - What to expect each week

3. **`PARALLEL_DEVELOPMENT_SUMMARY.md`** (11 KB)
   - Week-by-week roadmap
   - Frontend deliverables timeline
   - What data is available when

### Build Sequence
**Week 1**: Design dashboard layout, build Agent 2 panel
- Scan status display
- Filter hit rates (chart)
- Latency metrics
- Risk dashboard

**Week 2**: Build Agent 3 panel when data available
- Smart wallet detection results
- Insider activity tracking
- Copy-trade signals

**Week 3**: Build Agent 4 panel + final integration
- Community metrics
- Sentiment analysis
- Signal generation flow

**Week 4**: Polish, add reporting, go live

### Choose Your Integration Method

**Option A: REST API** (Recommended)
```
GET /api/v1/realtime/current-scan
GET /api/v1/realtime/risk-metrics
GET /api/v1/history/signals?limit=20
```
→ Backend will provide HTTP endpoints
→ Frontend makes AJAX calls
→ Best for web dashboard

**Option B: File Sync** (Simpler)
```
Poll these files every 2-5 seconds:
data/realtime/current_scan.json
data/realtime/active_positions.json
data/realtime/risk_metrics.json
```
→ Simplest to implement
→ Works if frontend has file system access
→ Slightly delayed data

**Option C: WebSocket** (Real-Time)
```
Backend streams events:
event: "signal_discovered" → {signal}
event: "scan_complete" → {stats}
```
→ True real-time updates
→ Best for live monitoring
→ More complex backend code

**Which do you prefer?**

---

## For Alex (Backend Development)

### Build Sequence
**Week 2**: Complete Agent 3
- Build Birdeye API client (`src/apis/birdeye_client.py`)
- Implement smart wallet detection logic
- Implement insider activity tracking
- Implement copy-trade signals
- Test with 10+ known tokens
- Integrate into researcher_bot

**Week 2-3**: Complete Agent 4
- Build Discord API client (`src/apis/discord_client.py`)
- Build Twitter/X API client (`src/apis/twitter_client.py`)
- Implement community metrics
- Implement sentiment analysis
- Implement narrative strength scoring
- Test with 10+ known tokens
- Integrate into researcher_bot

**Week 3-4**: Master Rules Engine
- Implement combined scoring (40/30/30 weighting)
- Implement position sizing
- Implement TP/SL calculation
- Full pipeline end-to-end testing
- Prepare for paper trading

### Scaffolds Ready to Fill In
All agent code is complete with TODO comments showing what to implement:

**Agent 3**: `src/agents/agent_3_wallet_tracker.py`
- `detect_smart_wallets()` - TBD (Birdeye integration)
- `detect_insider_activity()` - TBD (balance tracking)
- `detect_copy_trade_signal()` - TBD (pattern matching)

**Agent 4**: `src/agents/agent_4_intel_agent.py`
- `detect_discord_community()` - TBD (Discord API)
- `detect_telegram_community()` - TBD (Telegram API)
- `detect_twitter_sentiment()` - TBD (Twitter API)
- `detect_narrative_strength()` - TBD (NLP/LLM)
- `detect_coordination_pattern()` - TBD (growth analysis)

### API Keys Needed
```
Week 2:
- Birdeye API (for Agent 3 wallet tracking)
  Status: Check availability (free tier?)
  
Week 2-3:
- Discord Bot Token (for Agent 4 community metrics)
  Status: Easy - create in Discord Developer Portal
  
- Twitter/X API v2 (for sentiment analysis)
  Status: Apply for free tier or use existing access
  
- LLM Access (for narrative analysis)
  Status: Have Haiku access, can use for sentiment
```

### Success Criteria
- Agent 3 latency: <1.5 sec per token
- Agent 4 latency: <2 sec per token
- Combined (2+3+4): <4.5 sec per token
- 6 tokens per scan: <30 sec total
- False positive rate: <5%
- All data flowing to database + frontend

---

## File Structure (New Files)

```
/workspace/
├── src/
│   ├── agents/
│   │   ├── agent_2_on_chain_analyst.py        ✅ WORKING
│   │   ├── agent_3_wallet_tracker.py          ✅ SCAFFOLD (fill in TODO)
│   │   └── agent_4_intel_agent.py             ✅ SCAFFOLD (fill in TODO)
│   ├── monitoring/
│   │   └── agent_2_metrics.py                 ✅ RUNNING
│   ├── apis/
│   │   ├── birdeye_client.py                  🟡 TODO (Week 2)
│   │   ├── discord_client.py                  🟡 TODO (Week 2)
│   │   ├── twitter_client.py                  🟡 TODO (Week 2)
│   │   └── (others exist: solscan, helius, etc)
│   ├── database.py                            ✅ EXTENDED
│   └── researcher_bot.py                      ✅ FIXED
├── docs/
│   ├── BACKEND_API_CONTRACT.md                ✅ READY FOR FRONTEND
│   ├── AGENT_INTEGRATION_MASTER_GUIDE.md      ✅ READY FOR FRONTEND
│   ├── PARALLEL_DEVELOPMENT_SUMMARY.md        ✅ READY
│   └── (other docs)
└── data/
    ├── database.db                            ✅ SCHEMA UPDATED
    └── metrics/
        └── agent_2_metrics.json               ✅ AUTO-POPULATING
```

---

## Weekly Checkin Schedule

**Every Monday at 10:00 UTC**:
- Backend: Show Agent 3 progress
- Frontend: Show dashboard mockups
- Discuss any blockers

**Every Wednesday at 10:00 UTC**:
- Backend: Agent integration testing
- Frontend: Data flow testing
- Alignment on next phase

**Every Friday at 10:00 UTC**:
- Status review
- Plan for next week
- Adjust timeline if needed

---

## Critical Path

```
Agent 2 validation (48h) ────────┐
                                 ├→ Week 2: Agent 3 build
Agent 3 scaffold ────────────────┤
                                 ├→ Week 3: Agent 4 build
Agent 4 scaffold ────────────────┘
                                    ├→ Week 4: Master Rules + Go Live
Database extended ─────────────────→

Frontend design ────────────────→ Week 1: Dashboard design
                                   ├→ Week 2: Agent 2 panel LIVE
Agent 2 data available ────────────→ Week 2: Agent 3 panel
                                   ├→ Week 3: Agent 4 panel + full integration
Agents 3+4 data available ──────────→ Week 4: Reporting features
```

---

## Questions to Answer Before Starting

### For Subham (Frontend)
1. REST API, file sync, or WebSocket?
2. Which 3 metrics are CRITICAL first?
3. Any specific dashboard layout preference?
4. Need for reporting/export features?

### For Alex (Backend)
1. Birdeye API availability - start with free tier?
2. Twitter/X API - use existing keys or apply?
3. Discord - self-host bot or use existing?
4. Any performance constraints we should know about?

---

## Success Looks Like

**Week 1 End**:
- ✅ Agent 2 validation metrics show <5% false positive rate
- ✅ Frontend dashboard design complete
- ✅ Agent 2 panel started (scan status, metrics)

**Week 2 End**:
- ✅ Agent 3 integrated, tested with 10+ tokens
- ✅ Agent 2 panel LIVE in dashboard
- ✅ Agent 3 placeholder panel ready

**Week 3 End**:
- ✅ Agent 4 integrated, tested with 10+ tokens
- ✅ All agent results showing in dashboard
- ✅ Master Rules engine 80% complete

**Week 4 End**:
- ✅ Full system tested end-to-end
- ✅ Dashboard live with all features
- ✅ Paper trading ready to launch
- ✅ Ready for $10 trial deployment

---

## Get Started Now

**Subham** → Read `BACKEND_API_CONTRACT.md` (where to get data from)
**Alex** → Search for "TODO" in agent_3_wallet_tracker.py (where to code)

Both → Confirm your next week's milestones in next sync

🚀 **Let's build this together!**

