# API Contract: Agents 3 & 4 (Updated March 3, 2026)

**CRITICAL**: This document defines the **live API contract** for frontend integration. 
Update this immediately after any backend changes.

---

## Agent 3: Wallet Tracker Output

### Data Model

```json
{
  "agent_id": 3,
  "token_address": "DRLNhjM7jusYFPF1z5ZisK5DjdXLiquidxxx",
  "analysis_timestamp": "2026-03-03T14:07:45.200000",
  "status": "CLEARED",
  "score": 7.2,
  "confidence": 0.78,
  "execution_time_ms": 1200,
  
  "smart_wallets_detected": [
    {
      "wallet_address": "wallet1_address",
      "wallet_name": "Top Trader #5",
      "wallet_tier": "top_10",
      "historical_win_rate": 0.68,
      "investment_amount_usd": 50000,
      "invested_at": "2026-03-03T14:05:00",
      "points_awarded": 2
    },
    {
      "wallet_address": "wallet2_address",
      "wallet_name": "Smart Wallet #23",
      "wallet_tier": "top_50",
      "historical_win_rate": 0.62,
      "investment_amount_usd": 10000,
      "invested_at": "2026-03-03T14:06:30",
      "points_awarded": 1
    }
  ],
  
  "insider_status": {
    "deployer_address": "0xdeployer...",
    "deployer_action": "holding",
    "deployer_balance_change_24h": "+500",
    "early_holders_action": "holding",
    "red_flags": [],
    "green_flags": ["Deployer not dumping"],
    "points_awarded": 1
  },
  
  "copy_trade_signal": {
    "detected": true,
    "similar_wallets_found": 3,
    "historical_success_rate": 0.71,
    "profile_type": "profitable_followers",
    "points_awarded": 1.5
  },
  
  "failure_reason": null,
  
  "summary": {
    "smart_wallets_points": 2.0,
    "insider_points": 1.0,
    "copy_trade_points": 1.5,
    "total_points": 4.5,
    "final_score": 4.5,
    "verdict": "POSITIVE_WALLET_SIGNALS"
  }
}
```

### REST Endpoints

```
GET /api/v1/agents/3/latest
  Returns: Latest Agent 3 analysis result

GET /api/v1/agents/3/token/{token_address}
  Returns: Agent 3 analysis for specific token

GET /api/v1/agents/3/history?limit=20&offset=0
  Returns: Last N Agent 3 analyses
  
POST /api/v1/agents/3/analyze
  Body: { "token_address": "...", "token_symbol": "..." }
  Returns: New Agent 3 analysis (async job)
```

### WebSocket Events

```javascript
// Agent 3 analysis started
{
  "event": "agent_3_started",
  "token_address": "...",
  "timestamp": "2026-03-03T14:07:45.000000"
}

// Agent 3 analysis complete
{
  "event": "agent_3_complete",
  "data": { /* full Agent 3 analysis object */ },
  "timestamp": "2026-03-03T14:07:45.200000"
}

// Agent 3 error
{
  "event": "agent_3_error",
  "token_address": "...",
  "error": "Birdeye API unavailable",
  "timestamp": "2026-03-03T14:07:45.300000"
}
```

---

## Agent 4: Intel Agent Output

### Data Model

```json
{
  "agent_id": 4,
  "token_address": "DRLNhjM7jusYFPF1z5ZisK5DjdXLiquidxxx",
  "token_symbol": "DRLN",
  "analysis_timestamp": "2026-03-03T14:07:47.100000",
  "status": "CLEARED",
  "score": 6.8,
  "confidence": 0.72,
  "execution_time_ms": 2100,
  
  "community": {
    "discord": {
      "server_found": true,
      "server_name": "Droneland Official",
      "server_id": 123456789,
      "member_count": 1250,
      "online_count": 45,
      "online_ratio": 0.036,
      "messages_1h": 120,
      "activity_level": "moderate",
      "growth_pattern": "organic",
      "sentiment": {
        "positive": 0.72,
        "neutral": 0.15,
        "negative": 0.13
      },
      "top_topics": ["roadmap", "deployment", "trading"],
      "red_flags": [],
      "green_flags": ["Active community", "Positive sentiment"],
      "health_score": 7.5,
      "verdict": "HEALTHY_COMMUNITY",
      "points_awarded": 2.0
    },
    "telegram": {
      "group_found": false,
      "points_awarded": 0.0
    }
  },
  
  "social": {
    "twitter": null,
    "points_awarded": 0.0
  },
  
  "narrative": {
    "clarity": 0.85,
    "uniqueness": 0.72,
    "community_alignment": 0.78,
    "description": "Decentralized drone logistics network...",
    "red_flags": [],
    "green_flags": ["Clear purpose", "Unique positioning"],
    "points_awarded": 2.3
  },
  
  "coordination": {
    "growth_pattern": "organic",
    "distribution": 0.68,
    "whale_concentration": 0.15,
    "red_flags": [],
    "green_flags": ["Distributed participation"],
    "points_awarded": 0.8
  },
  
  "failure_reason": null,
  
  "summary": {
    "discord_points": 2.0,
    "telegram_points": 0.0,
    "twitter_points": 0.0,
    "narrative_points": 2.3,
    "coordination_points": 0.8,
    "total_points": 7.1,
    "final_score": 6.8,
    "verdict": "STRONG_COMMUNITY"
  }
}
```

### REST Endpoints

```
GET /api/v1/agents/4/latest
  Returns: Latest Agent 4 analysis result

GET /api/v1/agents/4/token/{token_address}
  Returns: Agent 4 analysis for specific token

GET /api/v1/agents/4/history?limit=20&offset=0
  Returns: Last N Agent 4 analyses

GET /api/v1/agents/4/discord/{token_symbol}
  Returns: Discord community metrics for token

POST /api/v1/agents/4/analyze
  Body: { "token_address": "...", "token_symbol": "...", "description": "..." }
  Returns: New Agent 4 analysis (async job)
```

### WebSocket Events

```javascript
// Agent 4 analysis started
{
  "event": "agent_4_started",
  "token_address": "...",
  "token_symbol": "...",
  "timestamp": "2026-03-03T14:07:47.000000"
}

// Agent 4 analysis complete
{
  "event": "agent_4_complete",
  "data": { /* full Agent 4 analysis object */ },
  "timestamp": "2026-03-03T14:07:47.100000"
}

// Discord community found
{
  "event": "agent_4_discord_found",
  "token_symbol": "DRLN",
  "server_name": "Droneland Official",
  "member_count": 1250,
  "timestamp": "2026-03-03T14:07:47.050000"
}

// Sentiment analysis complete
{
  "event": "agent_4_sentiment_complete",
  "token_symbol": "DRLN",
  "sentiment": {
    "positive": 0.72,
    "neutral": 0.15,
    "negative": 0.13
  },
  "verdict": "BULLISH",
  "timestamp": "2026-03-03T14:07:47.080000"
}

// Agent 4 error
{
  "event": "agent_4_error",
  "token_address": "...",
  "error": "Discord server not found",
  "timestamp": "2026-03-03T14:07:47.100000"
}
```

---

## Combined Signal Output (All Agents)

### Data Model (After All Agents Complete)

```json
{
  "signal_id": "SIG_20260303_001",
  "token_address": "DRLNhjM7jusYFPF1z5ZisK5DjdXLiquidxxx",
  "token_symbol": "DRLN",
  "token_name": "Droneland",
  "discovered_at": "2026-03-03T14:07:00.000000",
  
  "agent_results": {
    "agent_2": {
      "agent_id": 2,
      "status": "CLEARED",
      "score": 8.5,
      "confidence": 0.95,
      "completion_time": "2026-03-03T14:07:43.500000",
      "execution_time_ms": 1000,
      "failed_filter": null,
      "key_metrics": {
        "contract_age_minutes": 45,
        "liquidity_locked_days": 365,
        "deployer_rigs": 0,
        "top_10_concentration": 22.5,
        "unique_buyers": 125
      }
    },
    
    "agent_3": {
      "agent_id": 3,
      "status": "CLEARED",
      "score": 7.2,
      "confidence": 0.78,
      "completion_time": "2026-03-03T14:07:45.200000",
      "execution_time_ms": 1200,
      "key_metrics": {
        "smart_wallets_found": 2,
        "smart_wallets_points": 2.0,
        "insider_status": "holding",
        "copy_trade_detected": true
      }
    },
    
    "agent_4": {
      "agent_id": 4,
      "status": "CLEARED",
      "score": 6.8,
      "confidence": 0.72,
      "completion_time": "2026-03-03T14:07:47.100000",
      "execution_time_ms": 2100,
      "key_metrics": {
        "discord_members": 1250,
        "discord_sentiment_positive": 0.72,
        "narrative_clarity": 0.85,
        "growth_pattern": "organic"
      }
    }
  },
  
  "scoring": {
    "agent_2_weighted": 8.5 * 0.4,
    "agent_3_weighted": 7.2 * 0.3,
    "agent_4_weighted": 6.8 * 0.3,
    "combined_score": 7.54,
    "master_rules_bonus": 0.0,
    "final_score": 7.54,
    "confidence_level": 0.82
  },
  
  "decision": {
    "verdict": "BUY",
    "reason": "All agents cleared. Smart money detected. Positive community sentiment.",
    "confidence": 0.82,
    "entry_price": 0.00015,
    "position_size_usd": 50,
    "tp1_price": 0.00025,
    "tp1_target_percent": 66.7,
    "tp2_price": 0.00040,
    "tp2_target_percent": 166.7,
    "stop_loss_price": 0.00012,
    "stop_loss_percent": -20.0,
    "expected_profit_usd": 83.3,
    "expected_profit_percent": 166.7,
    "risk_reward_ratio": 3.5
  },
  
  "status": "SENT",
  "created_at": "2026-03-03T14:07:47.100000",
  "telegram_sent": true,
  "telegram_sent_at": "2026-03-03T14:07:48.000000"
}
```

### REST Endpoints

```
GET /api/v1/signals/latest
  Returns: Latest signal

GET /api/v1/signals/history?limit=20&offset=0
  Returns: Last N signals with full agent details

GET /api/v1/signals/{signal_id}
  Returns: Specific signal with complete breakdown

GET /api/v1/signals/token/{token_address}
  Returns: Signal for specific token (if exists)

GET /api/v1/analysis/pipeline?token_address=...
  Returns: Real-time pipeline status for a token
```

### WebSocket Events

```javascript
// Complete signal generated
{
  "event": "signal_complete",
  "data": { /* full signal object */ },
  "timestamp": "2026-03-03T14:07:47.100000"
}

// Signal verdict from Master Rules
{
  "event": "signal_verdict",
  "token_symbol": "DRLN",
  "verdict": "BUY",
  "combined_score": 7.54,
  "confidence": 0.82,
  "timestamp": "2026-03-03T14:07:47.100000"
}

// Signal sent to telegram
{
  "event": "signal_sent_telegram",
  "signal_id": "SIG_20260303_001",
  "token_symbol": "DRLN",
  "timestamp": "2026-03-03T14:07:48.000000"
}
```

---

## Real-Time Streaming Data

### Agent 3 Discord Community (Live)

```
GET /api/v1/realtime/agents/3/smart_wallets?limit=10
  Returns: Currently tracked smart wallets

GET /api/v1/realtime/agents/3/insider_activity?token_address=...
  Returns: Current deployer balance changes

WebSocket /ws/agents/3
  Events:
  - "smart_wallet_detected"
  - "insider_dump_detected"
  - "insider_accumulating"
```

### Agent 4 Community Sentiment (Live)

```
GET /api/v1/realtime/agents/4/discord/active
  Returns: Currently monitored Discord servers

GET /api/v1/realtime/agents/4/sentiment/{token_symbol}
  Returns: Real-time sentiment scores

WebSocket /ws/agents/4
  Events:
  - "discord_server_found"
  - "discord_sentiment_shift"
  - "community_growth_spike"
  - "sentiment_positive"
  - "sentiment_negative"
```

---

## Database Queries (For Frontend)

```sql
-- Get latest Agent 3+4 analyses
SELECT token_address, status, score, analysis_timestamp
FROM agent_3_analysis
WHERE analysis_timestamp > datetime('now', '-24 hours')
ORDER BY analysis_timestamp DESC
LIMIT 20;

-- Get combined signals with all agent scores
SELECT 
  s.signal_id, s.token_symbol, s.combined_score,
  a2.safety_score, a3.wallet_score, a4.intel_score,
  s.created_at
FROM signals s
LEFT JOIN agent_2_analysis a2 ON s.token_address = a2.token_address
LEFT JOIN agent_3_analysis a3 ON s.token_address = a3.token_address
LEFT JOIN agent_4_analysis a4 ON s.token_address = a4.token_address
WHERE s.created_at > datetime('now', '-7 days')
ORDER BY s.created_at DESC;
```

---

## Error Handling

### Agent 3 Errors

```json
{
  "error": "birdeye_api_unavailable",
  "code": "A3_001",
  "message": "Birdeye API returned 503",
  "fallback": "PASS",
  "status": "CLEARED",
  "reason": "Graceful failure - continue analysis"
}
```

### Agent 4 Errors

```json
{
  "error": "discord_server_not_found",
  "code": "A4_001",
  "message": "No Discord server found for token",
  "fallback": "SCORE_ZERO",
  "status": "CLEARED",
  "reason": "No community data available but other agents passed"
}
```

---

## Integration Checklist for Frontend

- [ ] Parse Agent 3 wallet data structure
- [ ] Display smart wallet detection results
- [ ] Show insider accumulation/dumping status
- [ ] Parse Agent 4 community metrics
- [ ] Display Discord member count + sentiment
- [ ] Show narrative clarity scores
- [ ] Display combined signal scoring
- [ ] Consume WebSocket events in real-time
- [ ] Handle API errors gracefully
- [ ] Cache agent results locally
- [ ] Update UI when new signals arrive

---

## Notes for Frontend Developer

1. **Agent 3 Latency**: <1.5 sec (Birdeye API)
2. **Agent 4 Latency**: <2 sec (Discord + LLM sentiment)
3. **Discord Sentiment Cost**: ~$0.001 per message analyzed
4. **Update Frequency**: Real-time via WebSocket preferred, fallback to REST poll every 5-10 sec
5. **Confidence Threshold**: Agent 3 + Agent 4 scores 0.6+ are reliable
6. **Error Resilience**: All agent failures are graceful (returns CLEARED, not ERROR)

---

## Agent 5: Signal Aggregator Output

### Data Model (Consensus Gate)

```json
{
  "agent_id": 5,
  "token_address": "DRLNhjM7jusYFPF1z5ZisK5DjdXLiquidxxx",
  "token_symbol": "DRLN",
  "analysis_timestamp": "2026-03-03T14:07:49.000000",
  "status": "CLEARED",
  "composite_score": 7.85,
  "confidence": 0.88,
  
  "sources": {
    "source_count": 3,
    "cleared_agents": ["agent_1", "agent_2", "agent_3"],
    "is_independent": true,
    "independence_factor": 1.0
  },
  
  "scoring_breakdown": {
    "base_score": 7.2,
    "confluence_multiplier": 1.4,
    "velocity_bonus_applied": true,
    "time_decay_applied": true,
    "age_penalty_applied": false,
    "token_age_minutes": 22.5
  },
  
  "agent_scores": {
    "agent_1": {
      "score": 7.0,
      "weight": 0.15
    },
    "agent_2": {
      "score": 8.5,
      "weight": 0.25
    },
    "agent_3": {
      "score": 7.2,
      "weight": 0.40
    }
  },
  
  "failure_reason": null,
  "decision": "PASSED_AGENT_5_GATE"
}
```

### REST Endpoints

```
GET /api/v1/agents/5/latest
  Returns: Latest aggregated signal

GET /api/v1/agents/5/token/{token_address}
  Returns: Agent 5 aggregation for specific token

POST /api/v1/agents/5/aggregate
  Body: { "agent_1": {...}, "agent_2": {...}, "agent_3": {...}, "agent_4": {...}, "discovered_at": "..." }
  Returns: Aggregated signal with composite score

GET /api/v1/agents/5/confluence-analysis?token_address=...
  Returns: Detailed breakdown of confluence detection and independence checking
```

### WebSocket Events

```javascript
// Confluence detected
{
  "event": "agent_5_confluence_detected",
  "token_symbol": "DRLN",
  "source_count": 3,
  "cleared_agents": ["agent_1", "agent_2", "agent_3"],
  "independence": true,
  "timestamp": "2026-03-03T14:07:48.000000"
}

// Independence check result
{
  "event": "agent_5_independence_check",
  "token_symbol": "DRLN",
  "is_independent": true,
  "independence_factor": 1.0,
  "dependencies_detected": 0,
  "timestamp": "2026-03-03T14:07:48.100000"
}

// Velocity bonus triggered
{
  "event": "agent_5_velocity_bonus",
  "token_symbol": "DRLN",
  "time_between_sources_min": 3.2,
  "bonus_points": 0.5,
  "timestamp": "2026-03-03T14:07:48.200000"
}

// Time decay applied
{
  "event": "agent_5_time_decay",
  "token_symbol": "DRLN",
  "token_age_minutes": 22.5,
  "decay_factor": 0.95,
  "score_before": 7.2,
  "score_after": 6.84,
  "timestamp": "2026-03-03T14:07:48.300000"
}

// Signal aggregation complete
{
  "event": "agent_5_aggregation_complete",
  "data": { /* full Agent 5 result object */ },
  "composite_score": 7.85,
  "status": "CLEARED",
  "confidence": 0.88,
  "timestamp": "2026-03-03T14:07:49.000000"
}

// Signal passed gate (meets 8.0+ threshold)
{
  "event": "agent_5_gate_passed",
  "token_symbol": "DRLN",
  "composite_score": 7.85,
  "passes_threshold": true,
  "forward_to": "command_division",
  "timestamp": "2026-03-03T14:07:49.000000"
}

// Signal killed (below 8.0 or time-killed)
{
  "event": "agent_5_gate_blocked",
  "token_symbol": "DRLN",
  "composite_score": 5.2,
  "reason": "Score below 8.0 threshold",
  "timestamp": "2026-03-03T14:07:49.000000"
}
```

### Scoring Rules (CRITICAL)

```
Weights (must sum to 1.0):
- Agent 3 (Wallet): 40%
- Agent 2 (Safety): 25%
- Agent 4 (Intel): 20%
- Agent 1 (Researcher): 15%

Confluence Multipliers:
- 1 source: ×1.0 (caps at 6/10)
- 2 sources: ×1.2
- 3 sources: ×1.4
- 4 sources: ×1.6

Velocity Bonus:
- +0.5 if 2+ sources within 5 minutes

Time Decay:
- Starts at 0 minutes
- -15% every 15 minutes
- Signal KILLED at 45+ minutes

Age Penalty:
- Optimal window: 15-45 minutes
- < 15 min: -1.0 point (too young/pump risk)
- > 45 min: -1.5 points (should be killed)

Pass Threshold:
- Minimum composite score: 8.0/10
- Below 8.0: KILLED, does not reach Command Division
- 8.0+: CLEARED, forwarded to Agents 6+7 (veto power)

Independence Check:
- Detects if sources use same data (e.g., Agent 2 → Agent 3)
- Reduces multiplier if dependency found
- Ensures true consensus, not echo chamber
```

---

**Last Updated**: March 4, 2026 - 10:00 UTC
**Status**: ✅ Agents 2-5 Complete & Verified
**Version**: 3.0 (Complete 5-Agent Edition)

