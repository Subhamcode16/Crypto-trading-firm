import { create } from 'zustand';

export const useAgentStore = create((set, get) => ({
    agents: {
        1: { id: 1, name: 'Discovery', floor: 1, status: 'IDLE', is_online: true, activeToken: null, logs: [] },
        2: { id: 2, name: 'Safety', floor: 1, status: 'IDLE', is_online: true, activeToken: null, logs: [] },
        3: { id: 3, name: 'Wallets', floor: 1, status: 'MONITORING', is_online: true, activeToken: null, logs: [] },
        4: { id: 4, name: 'Community', floor: 1, status: 'MONITORING', is_online: true, activeToken: null, logs: [] },
        5: { id: 5, name: 'Aggregator', floor: 2, status: 'IDLE', is_online: true, activeToken: null, logs: [] },
        6: { id: 6, name: 'MacroSentinel', floor: 2, status: 'WATCHING', is_online: true, activeToken: null, logs: [] },
        7: { id: 7, name: 'RiskManager', floor: 2, status: 'MONITORING', is_online: true, activeToken: null, logs: [] },
        8: { id: 8, name: 'TradingBot', floor: 3, status: 'STANDBY', is_online: true, activeToken: null, logs: [] },
        9: { id: 9, name: 'PerformanceAnalyst', floor: 3, status: 'COLLECTING', is_online: true, activeToken: null, logs: [] },
    },

    setActiveToken: (agentId, tokenSymbol) => {
        set((state) => ({
            agents: {
                ...state.agents,
                [agentId]: { ...state.agents[agentId], activeToken: tokenSymbol },
            },
        }));
    },

    addAgentLog: (agentId, log) => {
        set((state) => ({
            agents: {
                ...state.agents,
                [agentId]: {
                    ...state.agents[agentId],
                    logs: [
                        { ...log, id: Date.now(), timestamp: new Date().toLocaleTimeString() },
                        ...state.agents[agentId].logs.slice(0, 49) // Keep last 50 logs
                    ],
                },
            },
        }));
    },

    fetchAgentLogs: async (agentId) => {
        try {
            const response = await fetch(`${import.meta.env.VITE_API_URL || 'http://localhost:8000'}/api/v1/agents/${agentId}/logs`);
            const data = await response.json();
            set((state) => ({
                agents: {
                    ...state.agents,
                    [agentId]: { ...state.agents[agentId], logs: data.logs || [] },
                },
            }));
        } catch (err) {
            console.error(`Failed to fetch logs for agent ${agentId}`, err);
        }
    },

    updateAgentStatus: (agentId, payload) => {
        set((state) => ({
            agents: {
                ...state.agents,
                [agentId]: {
                    ...state.agents[agentId],
                    status: payload.new_status || payload.status,
                    last_event: new Date().toLocaleTimeString(),
                },
            },
        }));
    },

    setAgentOnline: (agentId) => {
        set((state) => ({
            agents: {
                ...state.agents,
                [agentId]: { ...state.agents[agentId], is_online: true },
            },
        }));
    },

    setAgentOffline: (agentId, reason) => {
        set((state) => ({
            agents: {
                ...state.agents,
                [agentId]: { ...state.agents[agentId], is_online: false, error_message: reason },
            },
        }));
    },
}));
