import { create } from 'zustand';

export const useTradeStore = create((set) => ({
    open_positions: {},
    closed_trades: [],

    openPosition: (payload) => {
        set((state) => ({
            open_positions: {
                ...state.open_positions,
                [payload.position_id]: { ...payload, time_open_mins: 0, cancel_window_active: true },
            },
        }));
    },

    updatePosition: (payload) => {
        set((state) => {
            if (!state.open_positions[payload.position_id]) return state;
            return {
                open_positions: {
                    ...state.open_positions,
                    [payload.position_id]: { ...state.open_positions[payload.position_id], ...payload },
                },
            };
        });
    },

    closeTrade: (position_id, payload, reason) => {
        set((state) => {
            const pos = state.open_positions[position_id];
            if (!pos) return state;
            const { [position_id]: removed, ...remaining } = state.open_positions;
            return {
                open_positions: remaining,
                closed_trades: [...state.closed_trades, { ...pos, ...payload, exit_reason: reason, closed_at: new Date().toISOString() }],
            };
        });
    },
}));
