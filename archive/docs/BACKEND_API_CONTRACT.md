# Backend API Contract for Frontend Integration

## Overview
This document defines the data structures and API endpoints that the **frontend dashboard** will consume.

The backend will expose these via:
1. **REST API** (HTTP endpoints for web dashboard)
2. **JSON files** (for real-time file-based sync)
3. **WebSocket** (optional, for real-time streaming)

---

## Core Data Models

### 1. Agent Analysis Result (Universal)

All agents (2, 3, 4) return this structure:

```json
{
  "agent_id": 2,
  "token_address": "DRLNhjM7jusYFPF1z5ZisK5DjdXLiquidxxx",
  "analysis_timestamp": "2026-03-03T14:07:43.678322",
  "status": "KILLED|CLEARED|PENDING",
  "score": 7.5,
  "confidence": 0.85,
  "details": {
    "filter_results": {...},  // agent-specific
    "reasons": ["reason1", "reason2"],
    "flags": ["red_flag", "green_flag"]
  },
  "execution_time_ms": 1200
}
```

### 2. Signal (After All Agents Process)

```json
{
  "signal_id": "SIG_20260303_001",
  "token_address": "DRLNhjM7jusYFPF1z5ZisK5DjdXLiquidxxx",
  "token_symbol": "DRLN",
  "discovered_at": "2026-03-03T14:07:00.000000",
  "analysis_timeline": {
    "agent_2": {
      "status": "CLEARED",
      "score": 8.5,
      "confidence": 0.95,
      "completion_time": "2026-03-03T14:07:43.500000"
    },
    "agent_3": {
      "status": "CLEARED",
      "score": 7.2,
      "confidence": 0.78,
      "completion_time": "2026-03-03T14:07:45.200000"
    },
    "agent_4": {
      "status": "CLEARED",
      "score": 6.8,
      "confidence": 0.72,
      "completion_time": "2026-03-03T14:07:47.100000"
    }
  },
  "combined_score": 7.5,
  "master_rules_verdict": "BUY",
  "confidence_level": 0.82,
  "reason_to_buy": "All agents cleared, smart money detected, positive sentiment",
  "reason_to_skip": null,
  "entry_price": 0.00015,
  "position_size_usd": 50,
  "target_tp1": 0.00025,
  "target_tp2": 0.00040,
  "stop_loss": 0.00012,
  "expected_profit_percent": 150,
  "risk_reward_ratio": 3.5,
  "status": "SENT|SKIPPED|PENDING"
}
```

---

## Agent-Specific Data Models

### Agent 2: On-Chain Safety (Complete)

```json
{
  "agent_2_analysis": {
    "token_address": "...",
    "status": "CLEARED|KILLED",
    "failure_reason": null,  // if KILLED, why?
    "failed_filter": null,   // "liquidity_locked", "holder_concentration", etc
    "safety_score": 8.5,
    "filters": {
      "contract_age": {
        "passed": true,
        "value": 45,
        "unit": "minutes",
        "requirement": ">=15"
      },
      "liquidity_locked": {
        "passed": true,
        "value": 365,
        "unit": "days",
        "requirement": ">=365"
      },
      "deployer_history": {
        "passed": true,
        "deployer": "addr...",
        "previous_rugs": 0,
        "dead_tokens": 2,
        "requirement": "0 rugs, <5 dead"
      },
      "holder_concentration": {
        "passed": true,
        "top_10_percent": 22.5,
        "requirement": "<30%"
      },
      "unique_buyers": {
        "passed": true,
        "count": 125,
        "requirement": ">=50"
      },
      "volume_authenticity": {
        "passed": true,
        "top_5_percent": 42.3,
        "requirement": "<50%"
      },
      "mint_authority": {
        "passed": true,
        "status": "burned",
        "requirement": "burned|renounced"
      },
      "freeze_authority": {
        "passed": true,
        "status": "disabled",
        "requirement": "disabled"
      },
      "minimum_liquidity": {
        "passed": true,
        "value_usd": 15000,
        "requirement": ">=10000"
      }
    }
  }
}
```

### Agent 3: Wallet Tracker (TBD - Your Design)

```json
{
  "agent_3_analysis": {
    "token_address": "...",
    "status": "CLEARED|KILLED",
    "score": 7.2,
    "confidence": 0.78,
    "smart_wallets_detected": [
      {
        "wallet_address": "wallet1...",
        "wallet_name": "Top Trader #5",
        "wallet_tier": "top_10",
        "historical_wr": 0.68,
        "investment_amount": 50000,
        "invested_at": "2026-03-03T14:05:00",
        "points": 2
      },
      {
        "wallet_address": "wallet2...",
        "wallet_name": "Smart Wallet #23",
        "wallet_tier": "top_50",
        "historical_wr": 0.62,
        "investment_amount": 10000,
        "invested_at": "2026-03-03T14:06:30",
        "points": 1
      }
    ],
    "insider_status": {
      "deployer": "addr...",
      "deployer_action": "holding",  // "holding", "accumulating", "selling"
      "deployer_balance_change_24h": "+500",
      "early_holders_action": "holding",
      "red_flags": [],
      "points": 1
    },
    "copy_trade_signal": {
      "detected": true,
      "similar_wallets": 3,
      "historical_success_rate": 0.71,
      "points": 1.5
    },
    "total_points": 7.2,
    "reason_cleared": "Smart wallets detected, insider holding stable, positive copy signal",
    "reason_killed": null
  }
}
```

### Agent 4: Intel Agent (TBD - Your Design)

```json
{
  "agent_4_analysis": {
    "token_address": "...",
    "status": "CLEARED|KILLED",
    "score": 6.8,
    "confidence": 0.72,
    "community": {
      "discord": {
        "server_found": true,
        "member_count": 1250,
        "active_users_1h": 45,
        "activity_level": "moderate",  // "low", "moderate", "high"
        "growth_rate_1h": 12,
        "sentiment": 0.78,  // 0-1 scale, 0.78 = positive
        "top_topics": ["roadmap", "deployment", "listing"],
        "points": 2
      },
      "telegram": {
        "group_found": true,
        "member_count": 2500,
        "active_users_1h": 85,
        "activity_level": "high",
        "growth_rate_1h": 20,
        "sentiment": 0.75,
        "top_topics": ["trading", "price", "community"],
        "points": 2
      }
    },
    "social": {
      "twitter": {
        "mentions_24h": 87,
        "unique_posters": 34,
        "engagement_rate": 0.045,
        "sentiment": 0.72,
        "influencer_mentions": 4,
        "points": 1.5
      }
    },
    "narrative": {
      "clarity": 0.85,
      "uniqueness": 0.72,
      "community_alignment": 0.78,
      "description": "DeFi aggregator with novel yield farming mechanism",
      "points": 2.3
    },
    "coordination": {
      "growth_pattern": "organic",  // "organic", "sus_spike", "coordinated"
      "distribution": 0.68,  // 0-1, higher = more distributed
      "whale_concentration": 0.15,  // % held by top 3 wallets
      "points": 0.8
    },
    "total_points": 6.8,
    "reason_cleared": "Strong community, positive sentiment, organic growth",
    "reason_killed": null
  }
}
```

---

## Real-Time Data Feeds

### 1. Current Scan Status
**File**: `data/realtime/current_scan.json`

```json
{
  "scan_id": "SCAN_20260303_001",
  "scan_started_at": "2026-03-03T14:07:40.850000",
  "stage": "processing",  // "fetching", "agent_2", "agent_3", "agent_4", "complete"
  "tokens_discovered": 6,
  "tokens_in_agent_2": 3,
  "tokens_in_agent_3": 2,
  "tokens_in_agent_4": 1,
  "cleared_so_far": 0,
  "killed_so_far": 5,
  "elapsed_seconds": 5,
  "estimated_completion_seconds": 8
}
```

### 2. Agent Metrics (48-Hour Validation)
**File**: `data/metrics/agent_2_metrics.json`

```json
{
  "validation_started": "2026-03-03T13:52:40.000000",
  "elapsed_hours": 2.5,
  "scans_completed": 10,
  "total_tokens_analyzed": 60,
  "total_killed": 60,
  "total_cleared": 0,
  "avg_tokens_per_scan": 6,
  "kill_rate_percent": 100,
  "filter_hit_rates": {
    "liquidity_locked": 60,
    "holder_concentration": 0,
    "deployer_history": 0,
    "unique_buyers": 0,
    "volume_authenticity": 0,
    "mint_authority": 0,
    "freeze_authority": 0,
    "minimum_liquidity": 0,
    "contract_age": 0
  },
  "latest_scans": [
    {
      "timestamp": "2026-03-03T14:07:43",
      "token_count": 6,
      "killed_count": 6,
      "cleared_count": 0,
      "filters_hit": {
        "liquidity_locked": 6
      }
    }
  ]
}
```

### 3. Active Positions (Trading)
**File**: `data/realtime/active_positions.json`

```json
{
  "positions": [
    {
      "position_id": "POS_20260301_001",
      "token_address": "...",
      "token_symbol": "XYZ",
      "entry_price": 0.00015,
      "entry_time": "2026-03-01T10:30:00",
      "entry_tx": "hash...",
      "position_size_usd": 50,
      "current_price": 0.00023,
      "current_value_usd": 76.67,
      "unrealized_pnl_usd": 26.67,
      "unrealized_pnl_percent": 53.3,
      "tp1_price": 0.00025,
      "tp1_triggered": false,
      "tp2_price": 0.00040,
      "tp2_triggered": false,
      "stop_loss_price": 0.00012,
      "stop_loss_triggered": false,
      "status": "open",
      "hours_held": 27.5
    }
  ],
  "summary": {
    "total_open_positions": 1,
    "total_deployed_usd": 50,
    "total_unrealized_pnl_usd": 26.67,
    "total_unrealized_pnl_percent": 53.3,
    "capital_available_usd": 450
  }
}
```

### 4. Risk Metrics
**File**: `data/realtime/risk_metrics.json`

```json
{
  "timestamp": "2026-03-03T14:15:00",
  "portfolio": {
    "total_capital_usd": 500,
    "deployed_usd": 50,
    "available_usd": 450,
    "utilization_percent": 10
  },
  "daily_metrics": {
    "date": "2026-03-03",
    "starting_capital": 500,
    "current_capital": 526.67,
    "daily_profit_usd": 26.67,
    "daily_profit_percent": 5.3,
    "daily_loss_limit": 5,
    "current_loss": 0,
    "loss_limit_breached": false
  },
  "drawdown": {
    "peak_capital": 500,
    "current_capital": 526.67,
    "max_drawdown_percent": 0,
    "max_drawdown_usd": 0
  },
  "position_risk": {
    "max_position_size_percent": 5,
    "largest_position_percent": 10,
    "positions_over_limit": 1,
    "alert": "⚠️ Largest position is 10%, limit is 5%"
  },
  "sharpe_ratio": 1.23,
  "sortino_ratio": 1.87,
  "win_rate_percent": 62.5
}
```

---

## REST API Endpoints (Backend to Serve)

### Real-Time Data

```
GET /api/v1/realtime/current-scan
  → Returns: current_scan.json

GET /api/v1/realtime/active-positions
  → Returns: active_positions.json

GET /api/v1/realtime/risk-metrics
  → Returns: risk_metrics.json

GET /api/v1/realtime/latest-signals?limit=20
  → Returns: Last 20 signals with full Agent 2/3/4 results
```

### Historical Data

```
GET /api/v1/history/signals?start_date=2026-03-01&end_date=2026-03-03&limit=100
  → Returns: All signals in date range

GET /api/v1/history/trades?status=closed
  → Returns: Completed trades with P&L

GET /api/v1/metrics/agent-2?period=48h
  → Returns: agent_2_metrics.json

GET /api/v1/metrics/daily-summary?date=2026-03-03
  → Returns: Daily performance summary
```

### Control/Action Endpoints

```
POST /api/v1/control/pause-scanning
POST /api/v1/control/resume-scanning
POST /api/v1/control/stop-trading
POST /api/v1/control/close-position/{position_id}
POST /api/v1/control/manual-entry (body: token, size, tp, sl)
```

### Configuration

```
GET /api/v1/config/agents
  → Agent 2/3/4 thresholds and settings

POST /api/v1/config/agents
  → Update agent thresholds on the fly

GET /api/v1/config/rules
  → Master Rules Engine configuration
```

---

## WebSocket Stream (Optional Real-Time)

For live dashboard updates without polling:

```javascript
// Frontend connects
const ws = new WebSocket('ws://localhost:8000/ws/dashboard');

// Backend sends events
{
  "event": "signal_discovered",
  "data": { signal object }
}

{
  "event": "agent_2_result",
  "data": { agent_2_analysis }
}

{
  "event": "agent_3_result",
  "data": { agent_3_analysis }
}

{
  "event": "agent_4_result",
  "data": { agent_4_analysis }
}

{
  "event": "position_update",
  "data": { position with current price }
}

{
  "event": "scan_complete",
  "data": { scan summary }
}
```

---

## File-Based Sync (Simple Alternative)

If you prefer simple file-based updates instead of APIs:

```
data/
├── realtime/
│   ├── current_scan.json (updated every token)
│   ├── active_positions.json (updated every minute)
│   └── risk_metrics.json (updated every minute)
├── signals/
│   ├── 2026-03-03/
│   │   ├── SIG_001.json
│   │   ├── SIG_002.json
│   │   └── ...
├── metrics/
│   └── agent_2_metrics.json (updated every scan)
└── agents/
    ├── agent_2_results.json (latest results)
    ├── agent_3_results.json
    └── agent_4_results.json
```

Frontend can poll these files every 1-5 seconds.

---

## Implementation Roadmap

### Phase 1 (This Week - Agent 2 Validation Continues)
- [x] Agent 2 data model (database + JSON output)
- [ ] Create REST API skeleton
- [ ] Implement file-based sync for Agent 2 data
- [ ] Test frontend can read current_scan.json + active_positions.json

### Phase 2 (Week 2 - Agent 3 Build)
- [ ] Design Agent 3 data model (this doc)
- [ ] Build Agent 3 code
- [ ] Add Agent 3 results to API + files
- [ ] Test Agent 3 integration

### Phase 3 (Week 2 - Agent 4 Build)
- [ ] Design Agent 4 data model (this doc)
- [ ] Build Agent 4 code
- [ ] Add Agent 4 results to API + files
- [ ] Test Agent 4 integration

### Phase 4 (Week 3 - Integration + Dashboard)
- [ ] Full pipeline: Token → Agent 2 → 3 → 4 → Master Rules → Trade
- [ ] All data flowing to frontend
- [ ] Dashboard live with real data

---

## Notes for Frontend Developer (You)

1. **Data is ready**: Agent 2 analysis is already in the database
2. **JSON files will be created** as we build agents
3. **You can build against the schema** in this document
4. **No breaking changes**: We'll maintain backward compatibility
5. **Real-time or file-based**: Choose your preferred sync method
6. **All timestamps in ISO 8601**: Easy to parse in any language

---

## Questions?

- Do you prefer REST API or file-based sync?
- Any additional data you need in the API?
- Should we add WebSocket for true real-time?
- Any data model adjustments needed?

