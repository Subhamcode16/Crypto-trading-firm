const WebServer = require('ws');
const { runScenario } = require('./scenario_controller');

const wss = new WebServer.Server({ port: 8080 });

console.log('🚀 Pixel Firm Mock Server started on port 8080');

const agents = [1, 2, 3, 4, 5, 6, 7, 8, 9];
const statuses = {
    SEARCHER: ['IDLE', 'SCRAPING', 'SIGNAL_FOUND', 'ANALYZING'],
    EXECUTION: ['STANDBY', 'ORDER_PENDING', 'POSITION_OPEN', 'CELEBRATING'],
    MACRO: ['WATCHING', 'VOLATILITY_ALERT', 'HOLD_SIGNAL', 'CLEAR'],
};

function getRandomStatus(agentId) {
    if (agentId <= 4) return statuses.SEARCHER[Math.floor(Math.random() * statuses.SEARCHER.length)];
    if (agentId >= 8) return statuses.EXECUTION[Math.floor(Math.random() * statuses.EXECUTION.length)];
    return statuses.MACRO[Math.floor(Math.random() * statuses.MACRO.length)];
}

wss.on('connection', (ws) => {
    console.log('📱 Frontend connected');

    // Initial Sync
    agents.forEach(id => {
        ws.send(JSON.stringify({
            event: 'agent_status_changed',
            agent_id: id,
            payload: { new_status: getRandomStatus(id) }
        }));
    });

    // Simulation Loop
    const interval = setInterval(() => {
        const randomAgent = agents[Math.floor(Math.random() * agents.length)];
        ws.send(JSON.stringify({
            event: 'agent_status_changed',
            agent_id: randomAgent,
            payload: { new_status: getRandomStatus(randomAgent) }
        }));

        // Random Macro Event
        if (Math.random() > 0.9) {
            ws.send(JSON.stringify({
                event: 'macro_status_changed',
                payload: {
                    status: Math.random() > 0.5 ? 'HOLD' : 'CLEAR',
                    btc_1h_change: (Math.random() * 4 - 2).toFixed(2),
                    sol_1h_change: (Math.random() * 6 - 3).toFixed(2)
                }
            }));
        }
    }, 2000);

    ws.on('message', (message) => {
        try {
            const data = JSON.parse(message);
            
            // Bridge: If the message looks like an agent event (from Python backend or scenario),
            // broadcast it to all other connected clients (like the Frontend)
            if (data.event) {
                wss.clients.forEach((client) => {
                    if (client !== ws && client.readyState === WebServer.OPEN) {
                        client.send(JSON.stringify(data));
                    }
                });
            }

            if (data.type === 'RUN_SCENARIO') {
                runScenario(wss, data.name);
            }
        } catch (err) {
            console.error('Failed to process message', err);
        }
    });

    ws.on('close', () => {
        console.log('❌ Frontend disconnected');
        clearInterval(interval);
    });
});
