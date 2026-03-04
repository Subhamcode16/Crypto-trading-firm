import { create } from 'zustand';

export const useSignalStore = create((set) => ({
    active_signals: {},
    killed_signals: [],
    expired_signals: [],

    addSignal: (payload) => {
        set((state) => ({
            active_signals: {
                ...state.active_signals,
                [payload.signal_id]: { ...payload, status: 'CANDIDATE', created_at: new Date().toISOString() },
            },
        }));
    },

    updateSignalStage: (id, stage) => {
        set((state) => {
            if (!state.active_signals[id]) return state;
            return {
                active_signals: {
                    ...state.active_signals,
                    [id]: { ...state.active_signals[id], status: stage, last_updated: new Date().toISOString() },
                },
            };
        });
    },

    killSignal: (id, reason) => {
        set((state) => {
            const signal = state.active_signals[id];
            if (!signal) return state;
            const { [id]: removed, ...remaining } = state.active_signals;
            return {
                active_signals: remaining,
                killed_signals: [...state.killed_signals, { ...signal, killed_reason: reason }],
            };
        });
    },

    setConfluenceReached: (id, score) => {
        set((state) => {
            if (!state.active_signals[id]) return state;
            return {
                active_signals: {
                    ...state.active_signals,
                    [id]: { ...state.active_signals[id], confidence_score: score, status: 'CONFLUENCE_REACHED' },
                },
            };
        });
    },
}));
