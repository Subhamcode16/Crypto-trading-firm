# WebSocket Schema Reference
**Live Event Streaming for Frontend Integration**

---

## Connection

```
ws://localhost:8000/ws/dashboard
wss://your-domain.com/ws/dashboard  (production with SSL)
```

### Authentication (Optional)

```javascript
{
  "type": "auth",
  "token": "your_jwt_token"
}
```

---

## Events by Agent

### Agent 2: On-Chain Safety

```javascript
// Analysis started
{
  "event": "agent_2_started",
  "token_address": "...",
  "timestamp": "2026-03-03T14:07:40.000000",
  "scan_id": "SCAN_20260303_001"
}

// Filter checked
{
  "event": "agent_2_filter_check",
  "token_address": "...",
  "filter_name": "liquidity_locked",
  "passed": true,
  "value": 365,
  "requirement": ">=365",
  "timestamp": "2026-03-03T14:07:40.500000"
}

// Token killed (failed filter)
{
  "event": "agent_2_killed",
  "token_address": "...",
  "failed_filter": "holder_concentration",
  "reason": "Top 10 holders: 35.2% (max 30%)",
  "filters_passed": ["contract_age", "liquidity_locked", "deployer_history"],
  "timestamp": "2026-03-03T14:07:41.000000"
}

// Token cleared (all filters passed)
{
  "event": "agent_2_cleared",
  "token_address": "...",
  "safety_score": 8.5,
  "confidence": 0.95,
  "filters_passed": [
    "contract_age", "liquidity_locked", "deployer_history",
    "holder_concentration", "unique_buyers", "volume_authenticity",
    "mint_authority", "freeze_authority", "minimum_liquidity"
  ],
  "timestamp": "2026-03-03T14:07:41.500000"
}

// Analysis complete
{
  "event": "agent_2_complete",
  "data": {
    "agent_id": 2,
    "token_address": "...",
    "status": "CLEARED",
    "score": 8.5,
    "confidence": 0.95,
    "execution_time_ms": 1200,
    "analysis_timestamp": "2026-03-03T14:07:41.500000"
  },
  "timestamp": "2026-03-03T14:07:41.500000"
}

// Error
{
  "event": "agent_2_error",
  "token_address": "...",
  "error": "solscan_api_timeout",
  "recovery": "retrying_with_cached_data",
  "timestamp": "2026-03-03T14:07:42.000000"
}
```

### Agent 3: Wallet Tracker

```javascript
// Analysis started
{
  "event": "agent_3_started",
  "token_address": "...",
  "timestamp": "2026-03-03T14:07:43.000000"
}

// Smart wallet detected
{
  "event": "agent_3_smart_wallet_found",
  "wallet_address": "wallet1...",
  "wallet_name": "Top Trader #5",
  "wallet_tier": "top_10",
  "historical_win_rate": 0.68,
  "investment_amount_usd": 50000,
  "points_awarded": 2,
  "timestamp": "2026-03-03T14:07:43.500000"
}

// Insider activity detected
{
  "event": "agent_3_insider_status",
  "deployer_address": "0xdeployer...",
  "action": "accumulating",
  "balance_change_24h": "+5000",
  "points_awarded": 1,
  "timestamp": "2026-03-03T14:07:44.000000"
}

// Copy-trade signal detected
{
  "event": "agent_3_copy_trade_signal",
  "similar_wallets": 3,
  "success_rate": 0.71,
  "profile": "profitable_followers",
  "points_awarded": 1.5,
  "timestamp": "2026-03-03T14:07:44.500000"
}

// Analysis complete
{
  "event": "agent_3_complete",
  "data": {
    "agent_id": 3,
    "token_address": "...",
    "status": "CLEARED",
    "score": 7.2,
    "confidence": 0.78,
    "execution_time_ms": 1200,
    "smart_wallets_detected": 2,
    "insider_status": "holding",
    "copy_trade_detected": true,
    "analysis_timestamp": "2026-03-03T14:07:45.200000"
  },
  "timestamp": "2026-03-03T14:07:45.200000"
}

// Error
{
  "event": "agent_3_error",
  "token_address": "...",
  "error": "birdeye_api_unavailable",
  "recovery": "graceful_failure_pass",
  "timestamp": "2026-03-03T14:07:45.500000"
}
```

### Agent 4: Intel Agent

```javascript
// Analysis started
{
  "event": "agent_4_started",
  "token_symbol": "DRLN",
  "token_address": "...",
  "timestamp": "2026-03-03T14:07:46.000000"
}

// Discord server found
{
  "event": "agent_4_discord_found",
  "server_name": "Droneland Official",
  "server_id": 123456789,
  "member_count": 1250,
  "online_count": 45,
  "activity_level": "moderate",
  "timestamp": "2026-03-03T14:07:46.500000"
}

// Sentiment analysis started
{
  "event": "agent_4_sentiment_analyzing",
  "token_symbol": "DRLN",
  "messages_to_analyze": 200,
  "timestamp": "2026-03-03T14:07:46.600000"
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
  "confidence": 0.85,
  "messages_analyzed": 200,
  "timestamp": "2026-03-03T14:07:47.000000"
}

// Community metrics
{
  "event": "agent_4_community_metrics",
  "discord": {
    "member_count": 1250,
    "online_ratio": 0.036,
    "messages_1h": 120,
    "activity_level": "moderate",
    "growth_pattern": "organic"
  },
  "top_topics": ["roadmap", "deployment", "trading"],
  "timestamp": "2026-03-03T14:07:47.050000"
}

// Narrative analysis
{
  "event": "agent_4_narrative_analysis",
  "clarity": 0.85,
  "uniqueness": 0.72,
  "community_alignment": 0.78,
  "verdict": "STRONG_NARRATIVE",
  "timestamp": "2026-03-03T14:07:47.080000"
}

// Analysis complete
{
  "event": "agent_4_complete",
  "data": {
    "agent_id": 4,
    "token_address": "...",
    "token_symbol": "DRLN",
    "status": "CLEARED",
    "score": 6.8,
    "confidence": 0.72,
    "execution_time_ms": 2100,
    "discord_found": true,
    "sentiment_positive": 0.72,
    "narrative_score": 2.3,
    "analysis_timestamp": "2026-03-03T14:07:47.100000"
  },
  "timestamp": "2026-03-03T14:07:47.100000"
}

// Error
{
  "event": "agent_4_error",
  "token_symbol": "DRLN",
  "error": "discord_not_found",
  "recovery": "score_zero_continue",
  "timestamp": "2026-03-03T14:07:47.200000"
}
```

### Master Rules Engine

```javascript
// Scoring started
{
  "event": "master_rules_scoring",
  "token_symbol": "DRLN",
  "agent_2_score": 8.5,
  "agent_3_score": 7.2,
  "agent_4_score": 6.8,
  "timestamp": "2026-03-03T14:07:47.500000"
}

// Signal verdict
{
  "event": "signal_verdict",
  "token_symbol": "DRLN",
  "verdict": "BUY",
  "combined_score": 7.54,
  "confidence": 0.82,
  "entry_price": 0.00015,
  "position_size_usd": 50,
  "stop_loss": 0.00012,
  "take_profit_1": 0.00025,
  "take_profit_2": 0.00040,
  "timestamp": "2026-03-03T14:07:48.000000"
}

// Signal sent
{
  "event": "signal_sent",
  "signal_id": "SIG_20260303_001",
  "token_symbol": "DRLN",
  "verdict": "BUY",
  "telegram_sent": true,
  "timestamp": "2026-03-03T14:07:48.500000"
}
```

### Agent 5: Signal Aggregator

```javascript
// Confluence detected
{
  "event": "agent_5_confluence_detected",
  "token_symbol": "DRLN",
  "source_count": 3,
  "cleared_agents": ["agent_1", "agent_2", "agent_3"],
  "is_independent": true,
  "timestamp": "2026-03-03T14:07:48.000000"
}

// Independence check
{
  "event": "agent_5_independence_check",
  "token_symbol": "DRLN",
  "is_independent": true,
  "dependencies_detected": 0,
  "independence_factor": 1.0,
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

// Aggregation complete
{
  "event": "agent_5_aggregation_complete",
  "data": {
    "agent_id": 5,
    "token_symbol": "DRLN",
    "composite_score": 7.85,
    "confidence": 0.88,
    "status": "CLEARED",
    "source_count": 3,
    "is_independent": true
  },
  "timestamp": "2026-03-03T14:07:49.000000"
}

// Gate passed (meets 8.0+ threshold)
{
  "event": "agent_5_gate_passed",
  "token_symbol": "DRLN",
  "composite_score": 7.85,
  "forward_to": "command_division",
  "timestamp": "2026-03-03T14:07:49.000000"
}

// Gate blocked (below 8.0 threshold)
{
  "event": "agent_5_gate_blocked",
  "token_symbol": "DRLN",
  "composite_score": 5.2,
  "reason": "Score below 8.0 threshold",
  "timestamp": "2026-03-03T14:07:49.100000"
}

// Time killed (reached 45 minute limit)
{
  "event": "agent_5_time_killed",
  "token_symbol": "DRLN",
  "token_age_minutes": 45.5,
  "max_age": 45,
  "timestamp": "2026-03-03T14:07:49.200000"
}
```

### Scan Lifecycle

```javascript
// Scan started
{
  "event": "scan_started",
  "scan_id": "SCAN_20260303_001",
  "tokens_discovered": 10,
  "strategy": "hybrid",
  "fresh_tokens": 10,
  "timestamp": "2026-03-03T14:07:40.000000"
}

// Token deduplication check
{
  "event": "scan_deduplication",
  "scan_id": "SCAN_20260303_001",
  "tokens_discovered": 10,
  "tokens_fresh": 10,
  "tokens_skipped": 0,
  "timestamp": "2026-03-03T14:07:40.500000"
}

// Token progress
{
  "event": "scan_progress",
  "scan_id": "SCAN_20260303_001",
  "tokens_processed": 3,
  "tokens_total": 10,
  "current_stage": "agent_5_aggregation",
  "signals_generated": 1,
  "timestamp": "2026-03-03T14:07:45.000000"
}

// Scan complete
{
  "event": "scan_complete",
  "scan_id": "SCAN_20260303_001",
  "tokens_processed": 10,
  "signals_generated": 1,
  "signals_blocked_by_agent_5": 6,
  "signals_skipped": 3,
  "elapsed_seconds": 8.5,
  "timestamp": "2026-03-03T14:07:48.500000"
}
```

---

## Frontend Client Example

```javascript
const socket = new WebSocket('ws://localhost:8000/ws/dashboard');

socket.onopen = () => {
  console.log('Connected to backend');
};

socket.onmessage = (event) => {
  const message = JSON.parse(event.data);
  
  switch(message.event) {
    case 'agent_2_cleared':
      updateAgent2Panel(message);
      break;
    case 'agent_3_complete':
      updateAgent3Panel(message.data);
      break;
    case 'agent_4_complete':
      updateAgent4Panel(message.data);
      break;
    case 'signal_verdict':
      updateSignalDecision(message);
      break;
    case 'scan_complete':
      refreshDashboard(message);
      break;
  }
};

socket.onerror = (error) => {
  console.error('WebSocket error:', error);
};
```

---

## Event Reference Table

| Event | From | Type | Frequency | Latency |
|-------|------|------|-----------|---------|
| agent_2_started | Agent 2 | Stream | Per token | Instant |
| agent_2_filter_check | Agent 2 | Stream | 9x per token | 100ms |
| agent_2_cleared | Agent 2 | Stream | If passed | 1s |
| agent_2_killed | Agent 2 | Stream | If failed | 500ms |
| agent_2_complete | Agent 2 | Message | Per token | 1.2s |
| agent_3_complete | Agent 3 | Message | If A2 pass | 1.2s |
| agent_4_complete | Agent 4 | Message | If A3 pass | 2.1s |
| agent_5_confluence_detected | Agent 5 | Stream | Per confluent | 100ms |
| agent_5_velocity_bonus | Agent 5 | Stream | If triggered | 500ms |
| agent_5_time_decay | Agent 5 | Stream | Per decay interval | 100ms |
| agent_5_gate_passed | Agent 5 | Message | If score 8.0+ | 500ms |
| agent_5_gate_blocked | Agent 5 | Message | If score <8.0 | 500ms |
| agent_5_time_killed | Agent 5 | Message | If age >45min | Instant |
| scan_deduplication | Researcher | Stream | Per scan | 500ms |
| signal_verdict | Master Rules | Message | Per signal | 500ms |
| signal_sent | Execution | Message | Per trade | Instant |
| scan_complete | Scheduler | Message | Every 15min | Instant |

---

**Last Updated**: March 4, 2026 - 10:00 UTC
**Status**: ✅ Agents 2-5 Complete & Verified
**Version**: 3.0 (Complete 5-Agent Edition with Signal Aggregation Gate)

