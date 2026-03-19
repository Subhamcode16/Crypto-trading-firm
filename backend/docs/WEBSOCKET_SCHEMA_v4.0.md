# WebSocket Schema - Complete Real-Time Events (v4.0)
**Updated March 6, 2026 — Production Ready**

---

## Connection Setup

```javascript
// Frontend code
const ws = new WebSocket('ws://localhost:8000/ws/signals');

ws.onopen = () => {
  // Subscribe to all event streams
  ws.send(JSON.stringify({
    "type": "subscribe",
    "channels": [
      "agent_1", "agent_2", "agent_3", "agent_4", "agent_5",
      "master_rules", "risk_manager", "signals",
      "market_regime", "kill_switches"
    ]
  }));
};

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log(`Event: ${data.event}`, data);
  
  // Route to appropriate handler
  handleEvent(data);
};
```

---

## 📡 Real-Time Events

### Agent 5: Consensus Gating

```javascript
// Event 1: Market regime detected
{
  "event": "agent_5_market_regime_detected",
  "timestamp": "2026-03-06T14:07:40.000000",
  "market_regime": "choppy",
  "regime_description": "High volatility, prioritize smart money",
  "scan_id": "SCAN_20260306_001"
}

// Event 2: Confluence detected (2+ agents cleared)
{
  "event": "agent_5_confluence_detected",
  "timestamp": "2026-03-06T14:07:48.000000",
  "token_symbol": "DRLN",
  "source_count": 3,
  "cleared_agents": ["agent_1", "agent_2", "agent_3"],
  "is_independent": true,
  "confluence_description": "3 independent sources cleared token"
}

// Event 3: Dynamic weighting applied (based on market regime)
{
  "event": "agent_5_weighting_applied",
  "timestamp": "2026-03-06T14:07:48.050000",
  "token_symbol": "DRLN",
  "market_regime": "choppy",
  "base_weights": {
    "agent_3": 0.40,
    "agent_2": 0.25,
    "agent_4": 0.20,
    "agent_1": 0.15
  },
  "adjusted_weights": {
    "agent_3": 0.50,
    "agent_2": 0.30,
    "agent_4": 0.10,
    "agent_1": 0.10
  },
  "reason": "In choppy market: prioritize smart money (A3), increase safety (A2), reduce sentiment/discovery"
}

// Event 4: Independence check
{
  "event": "agent_5_independence_check",
  "timestamp": "2026-03-06T14:07:48.100000",
  "token_symbol": "DRLN",
  "is_independent": true,
  "independence_factor": 1.0,
  "shared_data_sources": [],
  "check_result": "All 3 agents derived signals from different data streams"
}

// Event 5: Confluence multiplier applied
{
  "event": "agent_5_confluence_multiplier",
  "timestamp": "2026-03-06T14:07:48.200000",
  "token_symbol": "DRLN",
  "source_count": 3,
  "base_score": 7.2,
  "multiplier": 1.4,
  "multiplied_score": 10.08,
  "capped_at": 10.0,
  "explanation": "3 independent sources: ×1.4 multiplier (capped at max 10)"
}

// Event 6: Velocity bonus
{
  "event": "agent_5_velocity_bonus",
  "timestamp": "2026-03-06T14:07:48.300000",
  "token_symbol": "DRLN",
  "triggered": false,
  "time_between_sources_min": 8.5,
  "requirement": "<=5 minutes",
  "bonus_points": 0,
  "reason": "Sources separated by 8.5 min (need <=5 for bonus)"
}

// Event 7: Time decay applied
{
  "event": "agent_5_time_decay",
  "timestamp": "2026-03-06T14:07:48.400000",
  "token_symbol": "DRLN",
  "token_age_minutes": 22.5,
  "decay_factor": 0.95,
  "score_before_decay": 10.0,
  "score_after_decay": 9.5,
  "explanation": "Token 22.5 min old in optimal 15-45 min window: minimal penalty"
}

// Event 8: Aggregation complete
{
  "event": "agent_5_aggregation_complete",
  "timestamp": "2026-03-06T14:07:49.000000",
  "token_symbol": "DRLN",
  "composite_score": 8.2,
  "confidence": 0.88,
  "source_count": 3,
  "market_regime": "choppy",
  "passes_8_0_threshold": true,
  "breakdown": {
    "agent_1": { "score": 6.5, "weight": 0.10, "contribution": 0.65 },
    "agent_2": { "score": 10.0, "weight": 0.30, "contribution": 3.0 },
    "agent_3": { "score": 7.5, "weight": 0.50, "contribution": 3.75 },
    "agent_4": { "score": 8.6, "weight": 0.10, "contribution": 0.86 }
  }
}

// Event 9: Agent 5 gate decision
{
  "event": "agent_5_gate_result",
  "timestamp": "2026-03-06T14:07:49.100000",
  "token_symbol": "DRLN",
  "composite_score": 8.2,
  "threshold": 8.0,
  "passes_threshold": true,
  "gate_status": "PASSED",
  "forward_to": "master_rules_gate",
  "time_in_agent_5_ms": 1100
}
```

### Gate 1: Master Trading Rules

```javascript
// Event 10: Rules validation started
{
  "event": "master_rules_validation_started",
  "timestamp": "2026-03-06T14:07:49.200000",
  "token_symbol": "DRLN",
  "rules_to_evaluate": 15,
  "categories": 10
}

// Event 11: Tier 1 (Critical) evaluated
{
  "event": "master_rules_tier_1_complete",
  "timestamp": "2026-03-06T14:07:49.400000",
  "token_symbol": "DRLN",
  "tier": 1,
  "rules_passed": 4,
  "rules_total": 4,
  "all_passed": true,
  "rules": [
    { "rule_id": "market_cap_range", "passed": true, "value": "$500K" },
    { "rule_id": "liquidity_locked", "passed": true, "value": "730 days" },
    { "rule_id": "community_presence", "passed": true, "value": "Discord" },
    { "rule_id": "fees_normal", "passed": true, "value": "0.5% buy/sell" }
  ],
  "status": "CRITICAL_PASSED"
}

// Event 12: Tier 2 (Recommended) evaluated
{
  "event": "master_rules_tier_2_complete",
  "timestamp": "2026-03-06T14:07:49.500000",
  "token_symbol": "DRLN",
  "tier": 2,
  "rules_passed": 5,
  "rules_total": 5,
  "all_passed": true,
  "status": "RECOMMENDED_PASSED"
}

// Event 13: Tier 3 (Complementary) evaluated
{
  "event": "master_rules_tier_3_complete",
  "timestamp": "2026-03-06T14:07:49.600000",
  "token_symbol": "DRLN",
  "tier": 3,
  "rules_passed": 3,
  "rules_total": 4,
  "all_passed": false,
  "failed_rules": [
    {
      "rule_id": "holder_diversity",
      "passed": false,
      "value": "Top 10: 32%",
      "requirement": "<30%",
      "impact": "non_critical"
    }
  ],
  "status": "COMPLEMENTARY_MOSTLY_PASSED"
}

// Event 14: Position multiplier calculated
{
  "event": "master_rules_multiplier_calculated",
  "timestamp": "2026-03-06T14:07:49.700000",
  "token_symbol": "DRLN",
  "overall_score": 7.8,
  "score_breakdown": {
    "market_cap_tier": 1.0,
    "security_score": 1.2,
    "community_strength": 0.9,
    "holder_quality": 0.85
  },
  "position_multiplier": 0.95,
  "multiplier_range": "0.5x-2.0x",
  "meaning": "Position will be sized at 95% of standard (slightly conservative due to holder concentration)"
}

// Event 15: Master Rules gate result
{
  "event": "master_rules_gate_result",
  "timestamp": "2026-03-06T14:07:49.800000",
  "token_symbol": "DRLN",
  "overall_score": 7.8,
  "tiers_passed": "1 (critical) + 2 (recommended) + 3 (mostly)",
  "passes_gate": true,
  "position_multiplier": 0.95,
  "forward_to": "risk_manager_gate",
  "time_in_master_rules_ms": 600
}
```

### Gate 2: Risk Manager

```javascript
// Event 16: Risk validation started
{
  "event": "risk_validation_started",
  "timestamp": "2026-03-06T14:07:50.000000",
  "token_symbol": "DRLN",
  "checks_to_validate": 5,
  "account_snapshot": {
    "balance": 8.5,
    "daily_pnl": -1.5,
    "trades_today": 2,
    "daily_limit": 3.0
  }
}

// Event 17: Check 1 - Equity Risk
{
  "event": "risk_check_1_equity_risk",
  "timestamp": "2026-03-06T14:07:50.100000",
  "token_symbol": "DRLN",
  "check_id": 1,
  "check_name": "Equity Risk per Trade",
  "requirement": "≤2.0%",
  "equity_risk_percent": 1.8,
  "passed": true,
  "details": "Position size $1.90 on $8.5 capital = 1.8% risk"
}

// Event 18: Check 2 - Position Size
{
  "event": "risk_check_2_position_size",
  "timestamp": "2026-03-06T14:07:50.200000",
  "token_symbol": "DRLN",
  "check_id": 2,
  "check_name": "Position Size Limit",
  "requirement": "≤25% of capital",
  "position_percent": 23.5,
  "passed": true,
  "details": "$1.90 position on $8.5 capital = 23.5% (under 25% limit)"
}

// Event 19: Check 3 - Reward Ratio
{
  "event": "risk_check_3_reward_ratio",
  "timestamp": "2026-03-06T14:07:50.300000",
  "token_symbol": "DRLN",
  "check_id": 3,
  "check_name": "Reward/Risk Ratio",
  "requirement": "≥2.0:1",
  "stop_loss_price": 0.00012,
  "take_profit_price": 0.00030,
  "entry_price": 0.00015,
  "risk_amount": 0.00003,
  "reward_amount": 0.00015,
  "ratio": 5.0,
  "passed": true,
  "details": "Reward $0.15 vs Risk $0.03 = 5:1 ratio (exceeds 2:1 requirement)"
}

// Event 20: Check 4 - Daily Loss
{
  "event": "risk_check_4_daily_loss",
  "timestamp": "2026-03-06T14:07:50.400000",
  "token_symbol": "DRLN",
  "check_id": 4,
  "check_name": "Daily Loss Respect",
  "requirement": "<$3.0 daily total",
  "current_daily_loss": -1.5,
  "daily_limit": 3.0,
  "remaining": 1.5,
  "passed": true,
  "details": "Current loss $1.5, can lose $1.5 more before daily limit"
}

// Event 21: Check 5 - Trade Frequency
{
  "event": "risk_check_5_frequency",
  "timestamp": "2026-03-06T14:07:50.500000",
  "token_symbol": "DRLN",
  "check_id": 5,
  "check_name": "Trade Frequency Regime Match",
  "market_regime": "mixed",
  "trades_today": 2,
  "regime_max": 4,
  "passed": true,
  "details": "2 trades done, regime allows 4/day max"
}

// Event 22: All checks complete
{
  "event": "risk_validation_complete",
  "timestamp": "2026-03-06T14:07:50.600000",
  "token_symbol": "DRLN",
  "checks_passed": 5,
  "checks_total": 5,
  "all_passed": true,
  "gate_decision": "APPROVED",
  "forward_to": "execution"
}

// Event 23: Kill switch status (periodic)
{
  "event": "kill_switch_status",
  "timestamp": "2026-03-06T14:07:50.700000",
  "current_loss": -1.5,
  "soft_pause_threshold": 3.0,
  "soft_pause_triggered": false,
  "hard_stop_threshold": 5.0,
  "hard_stop_triggered": false,
  "emergency_triggered": false,
  "status": "NORMAL"
}
```

### Final Signal Events

```javascript
// Event 24: Signal ready for execution
{
  "event": "signal_ready_for_execution",
  "timestamp": "2026-03-06T14:07:51.000000",
  "signal_id": "SIG_20260306_001",
  "token_symbol": "DRLN",
  "confidence_score": 8.2,
  "entry_price": 0.00015,
  "position_size_usd": 1.90,
  "stop_loss": 0.00012,
  "take_profit_targets": [
    { "tier": 1, "price": 0.00025, "sell": 40, "multiplier": 1.67 },
    { "tier": 2, "price": 0.00040, "sell": 40, "multiplier": 2.67 },
    { "tier": 3, "type": "trailing_50%", "sell": 20 }
  ],
  "pipeline_passed": [
    "agent_1_discovery",
    "agent_2_safety",
    "agent_3_wallets",
    "agent_4_community",
    "agent_5_consensus",
    "master_rules_gate",
    "risk_manager_gate"
  ],
  "requires_user_approval": true,
  "time_in_pipeline_ms": 2650
}

// Event 25: Signal sent to Telegram
{
  "event": "signal_telegram_sent",
  "timestamp": "2026-03-06T14:07:51.500000",
  "signal_id": "SIG_20260306_001",
  "token_symbol": "DRLN",
  "telegram_message_id": 12345,
  "status": "PENDING_USER_CONFIRMATION"
}

// Event 26: User confirmed trade (manual action)
{
  "event": "user_confirmed_trade",
  "timestamp": "2026-03-06T14:07:55.000000",
  "signal_id": "SIG_20260306_001",
  "token_symbol": "DRLN",
  "user_action": "APPROVE",
  "forward_to": "execution_engine"
}
```

---

## 📊 Event Frequency & Latency Table

| Event | Component | Type | Latency | Frequency |
|-------|-----------|------|---------|-----------|
| market_regime_detected | A5 | Stream | 10ms | Per scan |
| confluence_detected | A5 | Stream | 50ms | Per token |
| weighting_applied | A5 | Stream | 10ms | Per token |
| independence_check | A5 | Stream | 20ms | Per token |
| confluence_multiplier | A5 | Stream | 15ms | Per token |
| velocity_bonus | A5 | Stream | 20ms | Per token |
| time_decay | A5 | Stream | 15ms | Per token |
| aggregation_complete | A5 | Message | 50ms | Per token |
| agent_5_gate_result | A5 | Message | 100ms | Per token |
| validation_started | Rules | Stream | 10ms | Per signal |
| tier_1_complete | Rules | Stream | 150ms | Per signal |
| tier_2_complete | Rules | Stream | 100ms | Per signal |
| tier_3_complete | Rules | Stream | 120ms | Per signal |
| multiplier_calculated | Rules | Stream | 20ms | Per signal |
| rules_gate_result | Rules | Message | 50ms | Per signal |
| validation_started | Risk | Stream | 10ms | Per signal |
| check_*_result | Risk | Stream | 50ms | Per check (5) |
| validation_complete | Risk | Message | 100ms | Per signal |
| kill_switch_status | Risk | Stream | 50ms | Every 30sec |
| signal_ready_execution | Final | Message | 50ms | Per approved signal |

**Total end-to-end latency:** 500-800ms per token (9 tokens in parallel = 800ms-1.2s per batch)

---

## 🔌 Client-Side Event Handlers (Example)

```javascript
class SignalStreamHandler {
  handleEvent(event) {
    const { event: eventType, token_symbol } = event;
    
    switch(eventType) {
      // Market awareness
      case 'agent_5_market_regime_detected':
        this.updateMarketRegimeUI(event);
        break;
      
      // Confidence building
      case 'agent_5_confluence_detected':
        this.highlightToken(token_symbol, 'confluence');
        this.updateConfidenceBar(event.source_count);
        break;
      
      case 'agent_5_weighting_applied':
        this.displayWeightingAdjustment(event);
        break;
      
      // Gate tracking
      case 'agent_5_gate_result':
        if(event.passes_threshold) {
          this.moveToGate('MASTER_RULES', event);
        } else {
          this.signalKilled(token_symbol, 'Agent 5 gate');
        }
        break;
      
      case 'master_rules_gate_result':
        if(event.passes_gate) {
          this.moveToGate('RISK_MANAGER', event);
          this.displayMultiplier(event.position_multiplier);
        } else {
          this.signalKilled(token_symbol, 'Master Rules gate');
        }
        break;
      
      case 'risk_validation_complete':
        if(event.all_passed) {
          this.signalApproved(event);
          this.playNotification('signal_ready');
        } else {
          this.signalKilled(token_symbol, 'Risk check failed');
        }
        break;
      
      case 'signal_ready_for_execution':
        this.displayApprovalPrompt(event);
        break;
      
      case 'kill_switch_status':
        this.updateKillSwitchIndicator(event);
        break;
      
      default:
        console.log(`Unhandled event: ${eventType}`);
    }
  }
  
  // Helper methods
  updateMarketRegimeUI(event) {
    const { market_regime, regime_description } = event;
    document.querySelector('.market-regime').textContent = market_regime.toUpperCase();
    document.querySelector('.regime-desc').textContent = regime_description;
  }
  
  displayMultiplier(multiplier) {
    const element = document.querySelector('.position-multiplier');
    element.textContent = `${(multiplier * 100).toFixed(0)}%`;
    element.style.color = multiplier > 1 ? 'green' : 'orange';
  }
  
  signalApproved(event) {
    const { token_symbol, confidence_score } = event;
    console.log(`✅ ${token_symbol} approved with ${confidence_score.toFixed(1)}/10 confidence`);
  }
}
```

---

**Version:** 4.0  
**Updated:** March 6, 2026  
**Status:** Production Ready ✅  
**Total Events:** 26 per signal  
**Total Latency:** 500-800ms per token
