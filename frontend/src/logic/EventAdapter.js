import { useAgentStore } from '../stores/useAgentStore';
import { officeState, CharacterState } from '../engine/officeState';

// Agent Role mapping → FSM State trigger
const EVENT_TO_FSM = {
    // Agents 1 & 4 find signals
    'candidate_detected': { agentId: 1, state: CharacterState.SIGNAL_FOUND },
    'SIGNAL_FOUND': { agentId: 1, state: CharacterState.SIGNAL_FOUND },
    // Agent 2 verifies
    'verification_complete': { agentId: 2, state: CharacterState.VERIFYING },
    // Killed signals stamp red
    'signal_killed': { agentId: 2, state: CharacterState.STAMPING_RED },
    'SIGNAL_KILLED': { agentId: 2, state: CharacterState.STAMPING_RED },
    // Agent 3 sends urgent alerts
    'macro_status_changed': { agentId: 3, state: CharacterState.URGENT },
    'MACRO_RISK': { agentId: 6, state: CharacterState.HOLD_ACTIVE },
    // BTC crash → wallet tracer urgent + risk manager hold
    'BTC_CRASH': { agentId: 3, state: CharacterState.URGENT },
    // Agent 5 aggregates then achieves confluence
    'confluence_reached': { agentId: 5, state: CharacterState.CONFLUENCE },
    // Agent 6 activates a HOLD
    'macro_hold_active': { agentId: 6, state: CharacterState.HOLD_ACTIVE },
    // Agent 7 kills everything
    'kill_switch_triggered': { agentId: 7, state: CharacterState.KILL_TRIGGERED },
    'KILL_SWITCH_ACTIVE': { agentId: 7, state: CharacterState.KILL_TRIGGERED },
    // Agent 8 executes the trade
    'trade_executed': { agentId: 8, state: CharacterState.EXECUTING },
    'TRADE_EXECUTE': { agentId: 8, state: CharacterState.EXECUTING },
    'take_profit_hit': { agentId: 8, state: CharacterState.TP_HIT },
    'stop_loss_hit': { agentId: 8, state: CharacterState.STOPPED_OUT },
    // Agent 9 generates a report
    'position_update': { agentId: 9, state: CharacterState.REPORTING },
};

// Bubble messages for each event
const EVENT_BUBBLES = {
    'SIGNAL_FOUND': { agentId: 1, type: 'signal', text: 'SIGNAL!', duration: 4 },
    'candidate_detected': { agentId: 1, type: 'signal', text: 'SIGNAL!', duration: 4 },
    'BTC_CRASH': { agentId: 3, type: 'urgent', text: 'CRASH ALERT', duration: 4 },
    'MACRO_RISK': { agentId: 6, type: 'alert', text: 'HOLD ACTIVE', duration: 4 },
    'KILL_SWITCH_ACTIVE': { agentId: 7, type: 'alert', text: 'KILL SWITCH!', duration: 5 },
    'TRADE_EXECUTE': { agentId: 8, type: 'signal', text: 'EXECUTING...', duration: 4 },
    'SIGNAL_KILLED': { agentId: 2, type: 'alert', text: 'SIGNAL KILLED', duration: 4 },
    'verification_complete': { agentId: 2, type: 'wait', text: 'VERIFYING...', duration: 3 },
    'take_profit_hit': { agentId: 8, type: 'signal', text: 'TP HIT ✓', duration: 4 },
    'stop_loss_hit': { agentId: 8, type: 'urgent', text: 'SL HIT ▼', duration: 4 },
};

// Maps WS events to store actions + FSM state changes.
export const routeEvent = (msg) => {
    const { event, agent_id, signal_id, payload } = msg;

    // Route to FSM state first
    const fsmTarget = EVENT_TO_FSM[event];
    if (fsmTarget) {
        officeState.setAgentState(fsmTarget.agentId, true, fsmTarget.state);
        // Auto-revert to WORKING state after 4 seconds
        setTimeout(() => {
            officeState.setAgentState(fsmTarget.agentId, true, CharacterState.WORKING);
        }, 4000);
    }

    // Trigger speech bubble if mapped
    const bubbleTarget = EVENT_BUBBLES[event];
    if (bubbleTarget) {
        officeState.triggerBubble(bubbleTarget.agentId, bubbleTarget.type, bubbleTarget.text, bubbleTarget.duration || 3);
    }

    switch (event) {
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
            console.log('macro_status_changed payload', payload);
            break;
        case 'risk_state_update':
            break;
        default:
            console.warn(`Unknown event type: ${event}`);
    }
};
