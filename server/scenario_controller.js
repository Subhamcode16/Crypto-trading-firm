/**
 * scenario_controller.js
 * Logic to trigger specific trading scenarios for the Pixel Trading Firm dashboard.
 */

const SCENARIOS = {
    BTC_CRASH: [
        { event: 'macro_status_changed', payload: { status: 'HOLD', btc_1h_change: '-8.50', sol_1h_change: '-12.20', hold_reason: 'VOLATILITY_ALERT' } },
        { agent_id: 6, event: 'agent_status_changed', payload: { new_status: 'VOLATILITY_ALERT' } },
        { agent_id: 7, event: 'agent_status_changed', payload: { new_status: 'EVALUATING_EXPOSURE' } },
    ],
    BIG_BUY: [
        { event: 'candidate_detected', agent_id: 1, signal_id: 'sig_999', payload: { symbol: 'SOL', type: 'WHALE_ACCUMULATION', confidence: 0.92 } },
        { agent_id: 1, event: 'agent_status_changed', payload: { new_status: 'SIGNAL_FOUND' } },
        { agent_id: 5, event: 'agent_status_changed', payload: { new_status: 'CONFLUENCE_SCAN' } },
    ],
    KILL_SWITCH_ACTIVE: [
        { event: 'risk_state_update', payload: { kill_switch_states: { tier1: 'ACTIVE', tier2: 'ACTIVE', tier3: 'ACTIVE', tier4: 'ARMED' } } },
        { agent_id: 7, event: 'agent_status_changed', payload: { new_status: 'KILL_SWITCH_ENGAGED' } },
    ]
};

function runScenario(wss, name) {
    const events = SCENARIOS[name];
    if (!events) return;

    console.log(`[SCENARIO] Running: ${name}`);
    events.forEach((evt, index) => {
        setTimeout(() => {
            wss.clients.forEach(client => {
                if (client.readyState === 1) { // OPEN
                    client.send(JSON.stringify(evt));
                }
            });
        }, index * 500);
    });
}

module.exports = { runScenario };
