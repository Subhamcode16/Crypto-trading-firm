import { useAgentStore } from '../stores/useAgentStore';
import { officeState, CharacterState } from '../engine/officeState';

// Agent Role mapping → FSM State trigger
const EVENT_TO_FSM = {
    // Agents 1 & 4 find signals
    'candidate_detected': { agentId: 1, state: CharacterState.SIGNAL_FOUND },
    // Agent 2 verifies
    'verification_complete': { agentId: 2, state: CharacterState.VERIFYING },
    // Killed signals stamp red
    'signal_killed': { agentId: 2, state: CharacterState.STAMPING_RED },
    // Agent 3 sends urgent alerts
    'macro_status_changed': { agentId: 3, state: CharacterState.URGENT },
    // Agent 5 aggregates then achieves confluence
    'confluence_reached': { agentId: 5, state: CharacterState.CONFLUENCE },
    // Agent 6 activates a HOLD
    'macro_hold_active': { agentId: 6, state: CharacterState.HOLD_ACTIVE },
    // Agent 7 kills everything
    'kill_switch_triggered': { agentId: 7, state: CharacterState.KILL_TRIGGERED },
    // Agent 8 executes the trade
    'trade_executed': { agentId: 8, state: CharacterState.EXECUTING },
    'take_profit_hit': { agentId: 8, state: CharacterState.TP_HIT },
    'stop_loss_hit': { agentId: 8, state: CharacterState.STOPPED_OUT },
    // Agent 9 generates a report
    'position_update': { agentId: 9, state: CharacterState.REPORTING },
};

// Maps WS events to store actions + FSM state changes.
export const routeEvent = (msg) => {
    const { event, agent_id, signal_id, payload } = msg;

    console.log(`[WS Event] ${event}`, payload);

    // Route to FSM state first
    const fsmTarget = EVENT_TO_FSM[event];
    if (fsmTarget) {
        officeState.setAgentState(fsmTarget.agentId, true, fsmTarget.state);
        // Auto-revert to WORKING state after 3 seconds
        setTimeout(() => {
            officeState.setAgentState(fsmTarget.agentId, true, CharacterState.WORKING);
        }, 3000);
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
        case 'macro_status_changed':
            console.log('macro_status_changed payload', payload);
            break;
        case 'risk_state_update':
            break;
        default:
            console.warn(`Unknown event type: ${event}`);
    }
};
