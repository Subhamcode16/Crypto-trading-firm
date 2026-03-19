import { useMacroStore } from '../stores/useMacroStore';
import { useInsightStore } from '../stores/useInsightStore';
import { useSystemStore } from '../stores/useSystemStore';
import { officeState, CharacterState } from '../engine/officeState';

// v4.0 Event to FSM Mapping (Agents 1-5 focus)
const EVENT_TO_FSM = {
    // Agent 1: Discovery
    'agent_1_discovery_started': { agentId: 1, state: CharacterState.IDLE },
    'SIGNAL_FOUND': { agentId: 1, state: CharacterState.SIGNAL_FOUND },

    // Agent 2: Safety
    'agent_2_safety_validation': { agentId: 2, state: CharacterState.VERIFYING },
    'SIGNAL_KILLED': { agentId: 2, state: CharacterState.STAMPING_RED },

    // Agent 3: Wallets
    'agent_3_wallet_scan': { agentId: 3, state: CharacterState.VERIFYING },
    'BTC_CRASH': { agentId: 3, state: CharacterState.URGENT },

    // Agent 4: Community
    'community_sentiment_check': { agentId: 4, state: CharacterState.VERIFYING },

    // Agent 5: Aggregator (Gate 1)
    'agent_5_confluence_detected': { agentId: 5, state: CharacterState.CONFLUENCE },
    'agent_5_weighting_applied': { agentId: 5, state: CharacterState.IDLE },
    'agent_5_gate_result': { agentId: 5, state: CharacterState.WORKING },
};

// Communication logs for transparency (v4.0 focus)
const COMMUNICATION_LOGS = {
    'SIGNAL_FOUND': { senderId: 1, receiverId: 5, content: "IntelAgent found a potential alpha signal on BTC/USD. Passing to Aggregator." },
    'BTC_CRASH': { senderId: 3, receiverId: 7, content: "CRITICAL: BTC price drop detected. Suggesting immediate Kill Switch review." },
    'MACRO_RISK': { senderId: 6, receiverId: 8, content: "Macro risk elevated. Instructing TradingBot to pause new entries." },
    'KILL_SWITCH_ACTIVE': { senderId: 7, receiverId: 8, content: "GLOBAL KILL SWITCH TRIGGERED. Closing all active positions." },
    'TRADE_EXECUTE': { senderId: 8, receiverId: 9, content: "Orders executed successfully. Passing trade data to Performance Analyst." },
    'SIGNAL_KILLED': { senderId: 2, receiverId: 1, content: "Signal rejected. Analysis does not meet confidence threshold." },

    // Added v4.0 Specific Logs
    'agent_5_confluence_detected': { senderId: 5, receiverId: null, content: "Confluence detected! Aggregating scores from Agents 1, 2, and 3." },
    'agent_5_weighting_applied': { senderId: 5, receiverId: null, content: "Dynamic weighting adjusted due to market volatility." }
};

// Bubble messages for each event
const EVENT_BUBBLES = {
    'SIGNAL_FOUND': { agentId: 1, type: 'signal', text: 'SIGNAL!', duration: 4 },
    'BTC_CRASH': { agentId: 3, type: 'urgent', text: 'CRASH ALERT', duration: 4 },
    'MACRO_RISK': { agentId: 6, type: 'alert', text: 'HOLD ACTIVE', duration: 4 },
    'KILL_SWITCH_ACTIVE': { agentId: 7, type: 'alert', text: 'KILL SWITCH!', duration: 5 },
    'TRADE_EXECUTE': { agentId: 8, type: 'signal', text: 'EXECUTING...', duration: 4 },
    'SIGNAL_KILLED': { agentId: 2, type: 'alert', text: 'KILLED', duration: 4 },
    'agent_5_confluence_detected': { agentId: 5, type: 'signal', text: 'CONFLUENCE', duration: 3 },
};

// Maps WS events to store actions + FSM state changes.
export const routeEvent = (msg) => {
    const { event, agent_id, token_symbol, signal_id, payload } = msg;

    // Clear starting state on first signal/event
    const { isStarting, setStarting } = useSystemStore.getState();
    if (isStarting) setStarting(false);

    // 1. Update activeToken per agent if signal/token is involved
    if (token_symbol) {
        // If it's a specific agent event, update just that agent
        const fsmEntry = EVENT_TO_FSM[event];
        if (fsmEntry) {
            useAgentStore.getState().setActiveToken(fsmEntry.agentId, token_symbol);
        } else if (agent_id) {
            useAgentStore.getState().setActiveToken(agent_id, token_symbol);
        }
    }

    // 2. Route to FSM state
    const fsmTarget = EVENT_TO_FSM[event];
    if (fsmTarget) {
        officeState.setAgentState(fsmTarget.agentId, true, fsmTarget.state);
        // Auto-revert to WORKING state after a delay
        setTimeout(() => {
            officeState.setAgentState(fsmTarget.agentId, true, CharacterState.WORKING);
        }, 4000);
    }

    // 3. Trigger speech bubble if mapped
    const bubbleTarget = EVENT_BUBBLES[event];
    if (bubbleTarget) {
        officeState.triggerBubble(bubbleTarget.agentId, bubbleTarget.type, bubbleTarget.text, bubbleTarget.duration || 3);
    }

    // 4. Log to communication pipeline
    const logTarget = COMMUNICATION_LOGS[event];
    if (logTarget) {
        useMessageStore.getState().addMessage({
            senderId: logTarget.senderId,
            receiverId: logTarget.receiverId,
            content: logTarget.content,
            type: event
        });
    }

    // 5. Granular Agent Activity Logs (Real-time logs for all agents)
    const logAgentId = agent_id || (fsmTarget && fsmTarget.agentId);
    if (logAgentId) {
        let content = "";
        let level = "info";

        // Specialized log content based on event type
        switch (event) {
            case 'agent_1_discovery_started':
                content = `INITIATING NEW DISCOVERY PULSE ON ${token_symbol || 'SOL'}`;
                level = "scan";
                break;
            case 'SIGNAL_FOUND':
                content = `ALPHA DETECTED: ${token_symbol} - CONTEXT SCORE 84%`;
                level = "discovery";
                break;
            case 'agent_2_safety_validation':
                content = `VALIDATING CONTRACT SECURITY FOR ${token_symbol}`;
                level = "scan";
                break;
            case 'SIGNAL_KILLED':
                content = `THREAT DETECTED: REJECTING ${token_symbol} - REASON: ${payload?.reason || 'Unknown'}`;
                level = "alert";
                break;
            case 'agent_3_wallet_scan':
                content = `SCANNING WHALE CLUSTERS FOR ${token_symbol}`;
                level = "scan";
                break;
            case 'agent_5_confluence_detected':
                content = `CONFLUENCE POINT TRIGGERED FOR ${token_symbol}`;
                level = "discovery";
                break;
            case 'agent_5_weighting_applied':
                content = `DYNAMIC WEIGHTING ADJUSTED: +15% TO COMMMUNITY SCORE`;
                level = "info";
                break;
            case 'agent_status_changed':
                content = `STATUS TRANSITION -> ${payload?.new_status || payload?.status}`;
                level = "info";
                break;
            default:
                // Generic fallback for any other agent event
                if (token_symbol) {
                    content = `PROCESSING ${token_symbol} - ${event.replace(/_/g, ' ').toUpperCase()}`;
                } else {
                    content = `EVENT: ${event.replace(/_/g, ' ').toUpperCase()}`;
                }
        }

        useAgentStore.getState().addAgentLog(logAgentId, {
            content,
            level,
            token_symbol
        });
    }

    // 6. Direct store updates
    switch (event) {
        case 'agent_5_market_regime_detected':
            useMacroStore.getState().updateMacroStatus({ market_regime: (payload.market_regime || '').toUpperCase() });
            break;
        case 'agent_status_changed':
            useAgentStore.getState().updateAgentStatus(agent_id, payload);
            break;
        case 'agent_online':
            useAgentStore.getState().setAgentOnline(agent_id);
            officeState.setAgentState(agent_id, true, CharacterState.WORKING);
            break;
        case 'agent_offline':
            useAgentStore.getState().setAgentOffline(agent_id, payload.reason);
            officeState.setAgentState(agent_id, false, CharacterState.IDLE);
            break;
        // ── Dev Scenario: toggle all agents on/off ────────────────────────────
        case 'ALL_AGENTS_ONLINE':
            for (let i = 1; i <= 9; i++) {
                officeState.setAgentState(i, true, CharacterState.WORKING);
            }
            break;
        case 'ALL_AGENTS_OFFLINE':
            for (let i = 1; i <= 9; i++) {
                officeState.setAgentState(i, false, CharacterState.IDLE);
            }
            break;
        case 'macro_status_changed':
            useMacroStore.getState().updateMacroStatus(payload);
            break;
        case 'NEWS_FEED_UPDATE':
            useInsightStore.getState().addNews(payload);
            break;
        case 'PIPELINE_STATS_UPDATE':
            useInsightStore.getState().updatePipeline(payload);
            break;
        default:
        // Silence unknown events unless debugging
        // console.warn(`Unhandled event: ${event}`);
    }
};
