# Complete API Contract - All Agents + Gates (v4.0)
**Updated March 6, 2026 — For Production Deployment**

---

## 🎯 Overview

This document defines the **complete data flow** from token discovery through final signal execution, including:

- **Agents 1-5** (Discovery → Aggregation)
- **Gate 1: Master Trading Rules** (15-rule validation)
- **Gate 2: Risk Manager** (5-point trade validation)
- **Dynamic weighting** by market regime
- **REST API endpoints** and **WebSocket events**

---

## 📊 Complete Pipeline

```
┌─ Agent 1: Discovery (6.5/10) ─┐
│                                │
├─ Agent 2: Safety (9 filters)──┤ KILLS 30-40%
│                                │
├─ Agent 3: Wallets (0-10)  ────┤ Survives
│                                │
├─ Agent 4: Community (0-10)────┤
│                                ▼
          ┌─────────────────────────────┐
          │ Agent 5: Aggregation        │
          │ Dynamic Weights (by regime) │
          │ Confluence x Multiplier     │
          │ Composite Score 0-10        │
          └─────────────────────────────┘
                       │
                       ▼ (≥8.0 passes)
          ┌─────────────────────────────┐
          │ GATE 1: Master Rules        │
          │ 15 Rules → Position Mult    │
          │ 0.5x-2.0x applied          │
          └─────────────────────────────┘
                       │
                       ▼ (passes)
          ┌─────────────────────────────┐
          │ GATE 2: Risk Manager        │
          │ 5-Point Validation          │
          │ Kill Switches Active        │
          └─────────────────────────────┘
                       │
                       ▼ (all pass)
          ┌─────────────────────────────┐
          │ ✅ SIGNAL → TELEGRAM ALERT  │
          │ Ready for Manual/Auto Trade │
          └─────────────────────────────┘
```

---

## 🔄 Agent 5: Signal Aggregator (With Dynamic Weighting)

### Data Model

```json
{
  "agent_id": 5,
  "token_address": "DRLNhjM7jusYFPF1z5ZisK5DjdXLiquidxxx",
  "token_symbol": "DRLN",
  "analysis_timestamp": "2026-03-06T14:07:49.000000",
  "status": "CLEARED|KILLED",
  "composite_score": 8.2,
  "confidence": 0.88,
  
  "market_regime": "bullish|mixed|choppy|flat",
  "weighting_applied": {
    "market_regime": "choppy",
    "weights": {
      "agent_3": 0.50,
      "agent_2": 0.30,
      "agent_4": 0.10,
      "agent_1": 0.10
    },
    "reason": "Prioritize smart money signals in volatile market"
  },
  
  "sources": {
    "source_count": 3,
    "cleared_agents": ["agent_1", "agent_2", "agent_3"],
    "is_independent": true,
    "independence_factor": 1.0,
    "shared_data_sources": []
  },
  
  "scoring_breakdown": {
    "base_score": 7.8,
    "confluence_multiplier": 1.4,
    "confluence_sources": 3,
    "velocity_bonus_applied": false,
    "velocity_bonus_points": 0,
    "time_decay_applied": true,
    "time_decay_factor": 0.95,
    "age_penalty_applied": false,
    "age_penalty_points": 0,
    "token_age_minutes": 22.5,
    "final_score": 8.2
  },
  
  "agent_scores": {
    "agent_1": { "score": 6.5, "weight": 0.10, "contribution": 0.65 },
    "agent_2": { "score": 10.0, "weight": 0.30, "contribution": 3.0 },
    "agent_3": { "score": 7.5, "weight": 0.50, "contribution": 3.75 },
    "agent_4": { "score": 8.6, "weight": 0.10, "contribution": 0.86 }
  },
  
  "gate_1_master_rules": null,  // Will be populated after Agent 5 passes
  "gate_2_risk_manager": null,  // Will be populated after Gate 1 passes
  
  "failure_reason": null,
  "gate_status": "PASSED_AGENT_5"
}
```

### REST Endpoints

```bash
# Get latest aggregation
GET /api/v1/agents/5/latest
  Headers: { "Accept": "application/json" }
  Response: { Agent 5 result }

# Get aggregation for specific token
GET /api/v1/agents/5/token/{token_address}
  Response: { Agent 5 result for that token }

# Get confluence analysis
GET /api/v1/agents/5/confluence?token_address=...
  Response: Detailed confluence breakdown

# Get weighting rules (for current market regime)
GET /api/v1/agents/5/weights?market_regime=bullish
  Response: {
    "market_regime": "bullish",
    "weights": {
      "agent_3": 0.35,
      "agent_2": 0.20,
      "agent_4": 0.25,
      "agent_1": 0.20
    }
  }

# Get all signals passing Agent 5 gate (last 24h)
GET /api/v1/agents/5/signals?status=PASSED&hours=24
  Response: [ { signal 1 }, { signal 2 }, ... ]
```

---

## 🎯 Gate 1: Master Trading Rules (Position Multiplier)

### Data Model

```json
{
  "gate_id": 1,
  "gate_name": "Master Trading Rules",
  "token_address": "DRLNhjM7jusYFPF1z5ZisK5DjdXLiquidxxx",
  "analysis_timestamp": "2026-03-06T14:07:50.000000",
  "status": "PASSED|FAILED",
  
  "rules_evaluated": 15,
  "rules_passed": 14,
  "rules_failed": 1,
  "overall_score": 7.8,
  "confidence": 0.92,
  
  "tier_1_critical": {
    "passed": 4,
    "total": 4,
    "status": "ALL_PASSED",
    "rules": [
      {
        "rule_id": "market_cap_range",
        "rule_name": "Market Cap $100K-$10M",
        "category": "Market Cap",
        "tier": 1,
        "passed": true,
        "value": 500000,
        "requirement": "100000-10000000"
      },
      {
        "rule_id": "liquidity_locked",
        "rule_name": "Liquidity Locked 365+ Days",
        "category": "Security",
        "tier": 1,
        "passed": true,
        "value": 730,
        "requirement": ">=365"
      },
      {
        "rule_id": "community_presence",
        "rule_name": "Active Community Present",
        "category": "Community",
        "tier": 1,
        "passed": true,
        "value": "discord_30members",
        "requirement": "discord OR telegram"
      },
      {
        "rule_id": "fees_normal",
        "rule_name": "Normal Fee Structure",
        "category": "Fees",
        "tier": 1,
        "passed": true,
        "buy_fee": 0.5,
        "sell_fee": 0.5,
        "max_fee": 5
      }
    ]
  },
  
  "tier_2_recommended": {
    "passed": 5,
    "total": 5,
    "status": "ALL_PASSED",
    "rules": [ /* similar structure */ ]
  },
  
  "tier_3_complementary": {
    "passed": 3,
    "total": 4,
    "status": "MOSTLY_PASSED (1 failed)",
    "failed_rule": {
      "rule_id": "holder_diversity",
      "rule_name": "Holder Diversity",
      "category": "Holders",
      "tier": 3,
      "passed": false,
      "value": "Top 10: 32%",
      "requirement": "<30%",
      "impact": "non_critical"
    }
  },
  
  "position_multiplier": {
    "base_multiplier": 1.0,
    "rule_adjustments": {
      "market_cap_tier": 1.0,
      "security_score": 1.2,
      "community_strength": 0.9,
      "holder_quality": 0.85
    },
    "final_multiplier": 0.95,
    "range": "0.5x-2.0x",
    "meaning": "Position size *= 0.95x (slightly conservative)"
  },
  
  "gate_decision": "PASSED",
  "reason": "All Tier 1 rules passed + Tier 2 fully passed + only 1 Tier 3 failure",
  "forward_to_gate": "risk_manager"
}
```

### REST Endpoints

```bash
# Validate token against Master Rules
POST /api/v1/gates/1/validate
  Body: { "token_address": "...", "token_data": { ... } }
  Response: { Master Rules result with multiplier }

# Get rules evaluation for a token
GET /api/v1/gates/1/token/{token_address}
  Response: { Full rules breakdown }

# Get rule feedback (accuracy tracking)
GET /api/v1/gates/1/feedback?days=7
  Response: {
    "period": "last_7_days",
    "rules_evaluated": 120,
    "high_performers": [
      { "rule_id": "liquidity_locked", "win_rate": 0.92 },
      { "rule_id": "market_cap_range", "win_rate": 0.88 }
    ],
    "low_performers": [
      { "rule_id": "holder_diversity", "win_rate": 0.34 }
    ]
  }

# Get position multiplier reference
GET /api/v1/gates/1/multiplier-scale
  Response: { Multiplier ranges and tier mappings }
```

---

## ⚡ Gate 2: Risk Manager (Hard Kill Switch)

### Data Model

```json
{
  "gate_id": 2,
  "gate_name": "Risk Manager",
  "token_address": "DRLNhjM7jusYFPF1z5ZisK5DjdXLiquidxxx",
  "analysis_timestamp": "2026-03-06T14:07:51.000000",
  "status": "APPROVED|REJECTED",
  
  "market_regime": "mixed",
  "account_state": {
    "starting_capital": 10.0,
    "current_balance": 8.5,
    "daily_pnl": -1.5,
    "daily_loss_limit": 3.0,
    "daily_loss_remaining": 1.5,
    "trades_today": 2,
    "regime_trade_limit": 4
  },
  
  "trade_parameters": {
    "entry_price": 0.00015,
    "stop_loss_price": 0.00012,
    "take_profit_price": 0.00030,
    "position_size_usd": 2.0,
    "position_percentage": 23.5,
    "reward_ratio": 2.0
  },
  
  "validation_checks": [
    {
      "check_id": 1,
      "check_name": "Equity Risk per Trade",
      "requirement": "≤2.0%",
      "equity_risk_percent": 1.8,
      "passed": true,
      "details": "Position size creates 1.8% equity risk (target 2%)"
    },
    {
      "check_id": 2,
      "check_name": "Position Size Limit",
      "requirement": "≤25% of capital",
      "position_percent": 23.5,
      "passed": true,
      "details": "Position is 23.5% of account"
    },
    {
      "check_id": 3,
      "check_name": "Reward/Risk Ratio",
      "requirement": "≥2.0:1",
      "reward_ratio": 2.0,
      "passed": true,
      "details": "Risk $0.06, reward $0.12 (exactly 2:1)"
    },
    {
      "check_id": 4,
      "check_name": "Daily Loss Respect",
      "requirement": "<$3.0 daily total",
      "daily_loss_remaining": 1.5,
      "passed": true,
      "details": "$1.5 remaining before daily limit"
    },
    {
      "check_id": 5,
      "check_name": "Trade Frequency Regime Match",
      "requirement": "Current <4/day (mixed regime)",
      "trades_today": 2,
      "regime_trade_limit": 4,
      "passed": true,
      "details": "2 trades today, can do 2 more this regime"
    }
  ],
  
  "kill_switches": {
    "soft_pause": {
      "threshold": 3.0,
      "current_loss": -1.5,
      "triggered": false,
      "action": "Pause new trades, close losers"
    },
    "hard_stop": {
      "threshold": 5.0,
      "current_loss": -1.5,
      "triggered": false,
      "action": "Close ALL positions, stop all trading"
    },
    "emergency_kill": {
      "triggers": [ "api_error", "invalid_data", "execution_failure" ],
      "current_status": "OK",
      "triggered": false,
      "action": "Immediate liquidation, manual review required"
    }
  },
  
  "all_checks_passed": true,
  "gate_decision": "APPROVED",
  "reason": "All 5 validation checks passed",
  "forward_to": "execution"
}
```

### REST Endpoints

```bash
# Validate trade against Risk Manager
POST /api/v1/gates/2/validate-trade
  Body: {
    "entry_price": 0.00015,
    "stop_loss_price": 0.00012,
    "take_profit_price": 0.00030,
    "position_size_usd": 2.0,
    "market_regime": "mixed"
  }
  Response: { Validation result with all 5 checks }

# Get current account state
GET /api/v1/gates/2/account-state
  Response: {
    "balance": 8.5,
    "daily_pnl": -1.5,
    "trades_today": 2,
    "daily_loss_remaining": 1.5
  }

# Get kill switch status
GET /api/v1/gates/2/kill-switches
  Response: { Soft/hard/emergency thresholds and triggers }

# Get risk validation history (last 24h)
GET /api/v1/gates/2/validation-history?hours=24
  Response: [ { validation 1 }, { validation 2 }, ... ]
```

---

## 🎬 Complete Signal Object (After Both Gates)

```json
{
  "signal_id": "SIG_20260306_001",
  "token_address": "DRLNhjM7jusYFPF1z5ZisK5DjdXLiquidxxx",
  "token_symbol": "DRLN",
  "discovered_at": "2026-03-06T14:07:00.000000",
  
  "pipeline_status": {
    "agent_1": { "score": 6.5, "status": "CLEARED" },
    "agent_2": { "score": 10.0, "status": "CLEARED" },
    "agent_3": { "score": 7.5, "status": "CLEARED" },
    "agent_4": { "score": 8.6, "status": "CLEARED" },
    "agent_5": { "score": 8.2, "status": "PASSED_AGENT_5_GATE" },
    "gate_1": { "score": 7.8, "multiplier": 0.95, "status": "PASSED" },
    "gate_2": { "checks_passed": 5, "status": "APPROVED" }
  },
  
  "entry": {
    "price": 0.00015,
    "position_size_usd_base": 2.0,
    "position_size_multiplier": 0.95,
    "position_size_usd_final": 1.90,
    "confidence_score": 8.2,
    "reason": "Multi-agent confluence: strong safety (10/10) + smart money signals (7.5/10) + positive community (8.6/10)"
  },
  
  "risk": {
    "stop_loss_price": 0.00012,
    "stop_loss_percent": 20.0,
    "equity_risk": 1.8
  },
  
  "profit_targets": [
    { "tier": 1, "price": 0.00025, "sell_percent": 40, "profit_2x": true },
    { "tier": 2, "price": 0.00040, "sell_percent": 40, "profit_4x": true },
    { "tier": 3, "price": "trailing_50%", "sell_percent": 20, "trailing_stop": true }
  ],
  
  "expected_metrics": {
    "reward_ratio": 2.0,
    "expected_return_percent": 100,
    "max_loss_percent": -20
  },
  
  "final_decision": "EXECUTE",
  "sent_to_telegram": true,
  "requires_confirmation": true,
  "approved_by_user": false,
  "timestamp": "2026-03-06T14:07:51.000000"
}
```

---

## 📡 WebSocket Events (Complete)

### Connection

```javascript
const ws = new WebSocket('ws://localhost:8000/ws/signals');

ws.onopen = () => {
  ws.send(JSON.stringify({
    "type": "subscribe",
    "channels": ["agent_5", "master_rules", "risk_manager", "signals"]
  }));
};
```

### Agent 5 Events

```javascript
// Confluence detected
{
  "event": "agent_5_confluence_detected",
  "token_symbol": "DRLN",
  "source_count": 3,
  "cleared_agents": ["agent_1", "agent_2", "agent_3"],
  "market_regime": "choppy",
  "weights_applied": {
    "agent_3": 0.50,
    "agent_2": 0.30,
    "agent_4": 0.10,
    "agent_1": 0.10
  },
  "timestamp": "2026-03-06T14:07:48.000000"
}

// Weighting applied
{
  "event": "agent_5_weighting_applied",
  "token_symbol": "DRLN",
  "market_regime": "choppy",
  "base_weights": { "agent_3": 0.40, "agent_2": 0.25, "agent_4": 0.20, "agent_1": 0.15 },
  "adjusted_weights": { "agent_3": 0.50, "agent_2": 0.30, "agent_4": 0.10, "agent_1": 0.10 },
  "reason": "Prioritize smart money in choppy market",
  "timestamp": "2026-03-06T14:07:48.050000"
}

// Aggregation complete
{
  "event": "agent_5_aggregation_complete",
  "token_symbol": "DRLN",
  "composite_score": 8.2,
  "confidence": 0.88,
  "status": "PASSED_AGENT_5_GATE",
  "timestamp": "2026-03-06T14:07:49.000000"
}

// Agent 5 gate result
{
  "event": "agent_5_gate_result",
  "token_symbol": "DRLN",
  "composite_score": 8.2,
  "threshold": 8.0,
  "passes_threshold": true,
  "forward_to": "master_rules_gate",
  "timestamp": "2026-03-06T14:07:49.100000"
}
```

### Master Rules Gate Events

```javascript
// Rules evaluation started
{
  "event": "master_rules_validation_started",
  "token_symbol": "DRLN",
  "rules_count": 15,
  "timestamp": "2026-03-06T14:07:49.200000"
}

// Tier 1 critical rules evaluated
{
  "event": "master_rules_tier_1_complete",
  "token_symbol": "DRLN",
  "tier": 1,
  "rules_passed": 4,
  "rules_total": 4,
  "status": "ALL_PASSED",
  "timestamp": "2026-03-06T14:07:49.500000"
}

// Position multiplier calculated
{
  "event": "master_rules_multiplier_calculated",
  "token_symbol": "DRLN",
  "overall_score": 7.8,
  "position_multiplier": 0.95,
  "multiplier_range": "0.5x-2.0x",
  "meaning": "Position size will be reduced by 5%",
  "timestamp": "2026-03-06T14:07:49.800000"
}

// Master Rules gate result
{
  "event": "master_rules_gate_result",
  "token_symbol": "DRLN",
  "score": 7.8,
  "passes": true,
  "forward_to": "risk_manager_gate",
  "timestamp": "2026-03-06T14:07:50.000000"
}
```

### Risk Manager Gate Events

```javascript
// Risk validation started
{
  "event": "risk_validation_started",
  "token_symbol": "DRLN",
  "checks_total": 5,
  "timestamp": "2026-03-06T14:07:50.100000"
}

// Individual check result
{
  "event": "risk_check_result",
  "token_symbol": "DRLN",
  "check_id": 1,
  "check_name": "Equity Risk per Trade",
  "requirement": "≤2.0%",
  "value": 1.8,
  "passed": true,
  "timestamp": "2026-03-06T14:07:50.200000"
}

// All checks complete
{
  "event": "risk_validation_complete",
  "token_symbol": "DRLN",
  "checks_passed": 5,
  "checks_total": 5,
  "all_passed": true,
  "forward_to": "execution",
  "timestamp": "2026-03-06T14:07:50.500000"
}

// Kill switch status
{
  "event": "kill_switch_status",
  "timestamp": "2026-03-06T14:07:50.600000",
  "soft_pause": {
    "threshold": 3.0,
    "current_loss": -1.5,
    "triggered": false
  },
  "hard_stop": {
    "threshold": 5.0,
    "current_loss": -1.5,
    "triggered": false
  }
}
```

### Final Signal Event

```javascript
// Signal ready for execution
{
  "event": "signal_ready_for_execution",
  "signal_id": "SIG_20260306_001",
  "token_symbol": "DRLN",
  "confidence_score": 8.2,
  "entry_price": 0.00015,
  "position_size_usd": 1.90,
  "stop_loss_price": 0.00012,
  "take_profit_targets": [
    { "tier": 1, "price": 0.00025, "sell": 40 },
    { "tier": 2, "price": 0.00040, "sell": 40 },
    { "tier": 3, "type": "trailing_50%", "sell": 20 }
  ],
  "pipeline_passed": [
    "agent_1", "agent_2", "agent_3", "agent_4", 
    "agent_5_gate", "master_rules_gate", "risk_manager_gate"
  ],
  "requires_user_approval": true,
  "timestamp": "2026-03-06T14:07:51.000000"
}
```

---

## 📊 Event Timing & Latency

| Event | Agent | Latency | Frequency |
|-------|-------|---------|-----------|
| confluence_detected | A5 | 50ms | Per token |
| weighting_applied | A5 | 10ms | Per token |
| aggregation_complete | A5 | 100ms | Per token |
| agent_5_gate_result | A5 | 50ms | Per token |
| rules_validation_started | Rules | 10ms | Per signal |
| tier_1_complete | Rules | 150ms | Per signal |
| multiplier_calculated | Rules | 20ms | Per signal |
| rules_gate_result | Rules | 30ms | Per signal |
| risk_validation_started | Risk | 10ms | Per signal |
| check_result | Risk | 50ms | Per check (5) |
| validation_complete | Risk | 100ms | Per signal |
| kill_switch_status | Risk | 100ms | Per 30sec |
| signal_ready_execution | Final | 50ms | Per approved signal |

**Total latency (token→signal):** 600-800ms (target <4.5 seconds per batch of 6-10)

---

## 🔗 Complete Integration Flow

```
Backend                             Frontend
  │
  ├─ /api/v1/agents/5/latest ◄──── GET (real-time)
  │
  ├─ ws://localhost:8000/ws ◄────── SUBSCRIBE (events)
  │
  │ (Events stream: agent_5 → master_rules → risk_manager → signal)
  │
  ├─ /api/v1/gates/1/feedback ◄──── GET (weekly report)
  │
  ├─ /api/v1/gates/2/kill-switches ◄ GET (status check)
  │
  └─ /api/v1/signals (all gated) ◄─ GET (dashboard display)
```

---

**Version:** 4.0  
**Updated:** March 6, 2026  
**Status:** Production Ready ✅
