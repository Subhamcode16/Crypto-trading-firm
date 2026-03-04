import { create } from 'zustand';

export const useAgentStore = create((set, get) => ({
    agents: {
        1: { id: 1, name: 'Researcher', floor: 1, status: 'IDLE', is_online: true },
        2: { id: 2, name: 'OnChainAnalyst', floor: 1, status: 'IDLE', is_online: true },
        3: { id: 3, name: 'WalletTracker', floor: 1, status: 'MONITORING', is_online: true },
        4: { id: 4, name: 'IntelAgent', floor: 1, status: 'MONITORING', is_online: true },
        5: { id: 5, name: 'SignalAggregator', floor: 2, status: 'IDLE', is_online: true },
        6: { id: 6, name: 'MacroSentinel', floor: 2, status: 'WATCHING', is_online: true },
        7: { id: 7, name: 'RiskManager', floor: 2, status: 'MONITORING', is_online: true },
        8: { id: 8, name: 'TradingBot', floor: 3, status: 'STANDBY', is_online: true },
        9: { id: 9, name: 'PerformanceAnalyst', floor: 3, status: 'COLLECTING', is_online: true },
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
