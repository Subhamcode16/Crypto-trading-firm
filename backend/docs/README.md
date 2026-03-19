# Backend API & WebSocket Documentation
**Complete Reference for Frontend Integration**

---

## 🎯 Quick Start

### New to the API?
1. **Read this first:** `API_CONTRACT_COMPLETE_v4.0.md` (30 min)
2. **Then:** `WEBSOCKET_SCHEMA_v4.0.md` (20 min)
3. **Then implement:** Use the REST endpoints and WebSocket events

### Want the complete pipeline?
- **API:** `API_CONTRACT_COMPLETE_v4.0.md` → Agents 1-5 + Gates 1-2 + REST endpoints
- **WebSocket:** `WEBSOCKET_SCHEMA_v4.0.md` → 26 real-time events
- **Summary:** `DOCUMENTATION_UPDATE_SUMMARY.md` → Overview + integration checklist

---

## 📁 Files in This Directory

### **CURRENT (v4.0 - Use These)**

#### `API_CONTRACT_COMPLETE_v4.0.md` (18.4 KB) ⭐ START HERE
Complete API specification including:
- ✅ Agent 1: Discovery (6.5/10)
- ✅ Agent 2: Safety (9 filters)
- ✅ Agent 3: Wallets (smart money)
- ✅ Agent 4: Community (Discord/Telegram/sentiment)
- ✅ **Agent 5: Signal Aggregation with DYNAMIC WEIGHTING**
  - Market regime detection (bullish/mixed/choppy/flat)
  - Confluence scoring & multipliers
  - 8.0/10 gate threshold
- ✅ **Gate 1: Master Trading Rules** (position multiplier)
- ✅ **Gate 2: Risk Manager** (5-point validation + kill switches)
- ✅ 25+ REST API endpoints
- ✅ Complete signal data model

#### `WEBSOCKET_SCHEMA_v4.0.md` (14.8 KB) ⭐ USE TOGETHER
Real-time event streaming specification:
- 26 events covering complete pipeline
- Agent 5 events (9 total)
- Master Rules events (6 total)
- Risk Manager events (6 total)
- Final signal events (5 total)
- Event latency & frequency table
- Client-side handler code example
- End-to-end latency: 500-800ms

#### `DOCUMENTATION_UPDATE_SUMMARY.md` (9.4 KB)
Overview of what's new in v4.0:
- What was updated vs old docs
- Dynamic weighting system explained
- Position multiplier examples
- Risk validation checklist
- Integration checklist for frontend
- Latency breakdown
- File structure & migration guide

---

### **LEGACY (Reference Only)**

#### `BACKEND_API_CONTRACT.md`
⚠️ Old version (Agents 1-4 only)  
→ **Use v4.0 instead** (adds Agent 5 + both gates)

#### `API_CONTRACT_AGENTS_3_4.md`
⚠️ Old version (Agents 3-4 basic, Agent 5 incomplete)  
→ **Use v4.0 instead** (complete Agent 5 + dynamic weighting)

#### `WEBSOCKET_SCHEMA.md`
⚠️ Old version (basic events, incomplete gates)  
→ **Use v4.0 instead** (all 26 events, complete coverage)

#### `AGENT_4_API_ANALYSIS.md`
✅ Keep for Agent 4-specific details if needed

---

## 🚀 Integration Paths

### For Frontend Developer
```
1. Read: API_CONTRACT_COMPLETE_v4.0.md (overview)
2. Read: WEBSOCKET_SCHEMA_v4.0.md (real-time events)
3. Implement: REST API clients (GET/POST endpoints)
4. Implement: WebSocket event handlers (26 events)
5. Build: Dashboard components:
   - Market regime display
   - Confluence visualization
   - Weighting breakdown (pie chart)
   - Risk checklist (5 items)
   - Kill switch indicators
   - Signal approval dialog
6. Test: End-to-end with live backend
```

### For Backend Developer
```
1. Review: API_CONTRACT_COMPLETE_v4.0.md (verify implementation)
2. Verify: All REST endpoints match spec
3. Monitor: WebSocket event latency (<500ms per event)
4. Test: Agent 5 aggregation speed (<100ms)
5. Validate: Master Rules multiplier calculation
6. Verify: Risk Manager 5-point validation
7. Test: End-to-end signal delivery
```

### For QA/Testing
```
1. Read: All v4.0 docs (understand full pipeline)
2. Plan: Test cases for each component
3. Execute: Latency tests (target <4.5s per token)
4. Validate: All 5 risk checks + kill switches
5. Regression: Backward compatibility
6. Load: Test 100+ events/second (WebSocket)
```

---

## 📊 Key Numbers

| Metric | Target | Actual |
|--------|--------|--------|
| Agent 1 latency | <100ms | ~10ms ✅ |
| Agent 2 latency | <1s | ~500ms ✅ |
| Agent 3 latency | <1.5s | ~300ms ✅ |
| Agent 4 latency | <2s | ~200ms ✅ |
| Agent 5 latency | <1s | ~100ms ✅ |
| Gate 1 latency | <1s | ~600ms ✅ |
| Gate 2 latency | <1s | ~600ms ✅ |
| **Total per token** | **<4.5s** | **~2.3s** ✅ |
| **Per batch (6-10)** | **<4.5s** | **2.3s parallel** ✅ |
| WebSocket events | N/A | **26 total** |
| REST endpoints | N/A | **25 total** |

---

## ✨ What's New in v4.0

### Agent 5 Enhancements
- **Dynamic Weighting** by market regime (bullish/mixed/choppy/flat)
- **Confidence Tracking** through confluence detection
- **Independence Validation** to prevent false multi-source signals

### Gate 1: Master Trading Rules
- **15 rules** across 10 categories (market cap, holders, community, fees, etc.)
- **Tier system** (1=critical, 2=recommended, 3=complementary)
- **Position Multiplier** (0.5x-2.0x) applied based on rule score
- **Feedback System** for continuous optimization

### Gate 2: Risk Manager
- **5-point validation:**
  1. Equity risk per trade (≤2%)
  2. Position size (≤25% of capital)
  3. Reward ratio (≥2:1)
  4. Daily loss limit (<$3)
  5. Trade frequency (regime-based)
- **Kill Switches** (soft pause at $3, hard stop at $5)
- **Market Regime Integration** for dynamic limits

---

## 🔄 Migration from Old Docs

If you were using the old docs:

| Old Doc | New Location | Addition |
|---------|--------------|----------|
| `BACKEND_API_CONTRACT.md` | v4.0 | +Agent 5 + Gates 1-2 |
| `API_CONTRACT_AGENTS_3_4.md` | v4.0 | +Dynamic weighting + Gate details |
| `WEBSOCKET_SCHEMA.md` | v4.0 | +Full event coverage (26 events) |

**Action:** Use v4.0 for all new development

---

## 📞 Questions?

- **Agent 5 scoring?** → See `API_CONTRACT_COMPLETE_v4.0.md` (Weighting section)
- **Real-time events?** → See `WEBSOCKET_SCHEMA_v4.0.md` (26 events)
- **Position multiplier?** → See `API_CONTRACT_COMPLETE_v4.0.md` (Gate 1 section)
- **Risk validation?** → See `API_CONTRACT_COMPLETE_v4.0.md` (Gate 2 section)
- **What changed?** → See `DOCUMENTATION_UPDATE_SUMMARY.md` (migration guide)

---

**Version:** 4.0  
**Updated:** March 6, 2026  
**Status:** Production Ready ✅
