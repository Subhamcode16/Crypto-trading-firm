# Implementation Plan: Finalizing the Trading Firm (Agents 1, 6, 7)

This plan refactors the remaining core agents to align with the "Agentic Firm" architecture and user preferences for accuracy, safety, and automation.

## User Review Required

> [!IMPORTANT]
> - **Agent 1 Refactor**: The discovery logic from [ResearcherBot](file:///c:/Users/User/OneDrive/Desktop/projects/Crypto-trading-bot/backend/src/researcher_bot.py#33-940) will move to `Agent1Discovery`. [ResearcherBot](file:///c:/Users/User/OneDrive/Desktop/projects/Crypto-trading-bot/backend/src/researcher_bot.py#33-940) will become a lightweight "Firm Manager" that orchestrates the loop.
> - **Agent 6 Upgrade**: Switching from Haiku to Sonnet for macro regime sentiment to maximize accuracy as requested.
> - **Agent 7 Stripping**: Removing AI "optimization" of position sizes to ensure strict adherence to hard-coded risk tiers.

## Proposed Changes

### [Component] Intelligence Division (Discovery)
---
#### [NEW] [agent_1_discovery.py](file:///c:/Users/User/OneDrive/Desktop/projects/Crypto-trading-bot/backend/src/agents/agent_1_discovery.py)
- Move discovery methods ([get_dex_results](file:///c:/Users/User/OneDrive/Desktop/projects/Crypto-trading-bot/backend/src/researcher_bot.py#358-377), [get_pumpfun_results](file:///c:/Users/User/OneDrive/Desktop/projects/Crypto-trading-bot/backend/src/researcher_bot.py#429-453), etc.) from [ResearcherBot](file:///c:/Users/User/OneDrive/Desktop/projects/Crypto-trading-bot/backend/src/researcher_bot.py#33-940) to this class.
- Implement specialized "Scanner" methods for each source.
- Maintain a local cache of recently found tokens to prevent duplicates.

#### [MODIFY] [researcher_bot.py](file:///c:/Users/User/OneDrive/Desktop/projects/Crypto-trading-bot/backend/src/researcher_bot.py)
- Remove discovery methods.
- Inject `Agent1Discovery` via constructor.
- Update [scan()](file:///c:/Users/User/OneDrive/Desktop/projects/Crypto-trading-bot/backend/src/researcher_bot.py#336-564) to call `agent_1.discover_new_leads()`.

### [Component] Command Division (Macro & Risk)
---
#### [MODIFY] [agent_6_macro_sentinel.py](file:///c:/Users/User/OneDrive/Desktop/projects/Crypto-trading-bot/backend/src/agents/agent_6_macro_sentinel.py)
- Change `model_type` to `"sonnet"` for regime analysis.
- Update [analyze()](file:///c:/Users/User/OneDrive/Desktop/projects/Crypto-trading-bot/backend/src/agents/agent_6_macro_sentinel.py#305-390) to *always* run AI sentiment check for maximum accuracy.

#### [MODIFY] [agent_7_risk_manager.py](file:///c:/Users/User/OneDrive/Desktop/projects/Crypto-trading-bot/backend/src/agents/agent_7_risk_manager.py)
- **Remove AI Refinement**: Delete [refine_trade_instruction](file:///c:/Users/User/OneDrive/Desktop/projects/Crypto-trading-bot/backend/src/agents/agent_7_risk_manager.py#88-176) logic that overrides size or SL.
- **Strict Sizing**: Ensure the calculated size is final and cannot be bypassed.
- **Automated Kill Switch**: Update [evaluate_tier_triggers](file:///c:/Users/User/OneDrive/Desktop/projects/Crypto-trading-bot/backend/src/agents/agent_7_risk_manager.py#497-533) to ensure [_trigger_liquidation](file:///c:/Users/User/OneDrive/Desktop/projects/Crypto-trading-bot/backend/src/agents/agent_7_risk_manager.py#534-545) is called immediately upon Tier 3 breach.

### [Component] Firm Orchestration
---
#### [MODIFY] [main.py](file:///c:/Users/User/OneDrive/Desktop/projects/Crypto-trading-bot/backend/src/main.py)
- Update initialization to include `Agent 1`.
- Clean up agent wiring to ensure all 9 agents are properly connected.

## Verification Plan

### Automated Tests
- `python backend/src/agents/agent_1_discovery.py` (Mock scan test)
- `python backend/src/agents/agent_6_macro_sentinel.py` (Verify Sonnet call)
- `python backend/src/agents/agent_7_risk_manager.py` (Simulate drawdown to trigger Tier 3 liquidation)

### Manual Verification
- Start the bot using [./start-app.bat](file:///c:/Users/User/OneDrive/Desktop/projects/Crypto-trading-bot/start-app.bat).
- Check logs for `[AGENT_1]` discovery activity and `[AGENT_6]` high-accuracy macro verdicts.
