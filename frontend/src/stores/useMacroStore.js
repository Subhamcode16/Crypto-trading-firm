import { create } from 'zustand';

export const useMacroStore = create((set) => ({
    status: 'CLEAR',
    btc_1h_change: "0.0",
    sol_1h_change: "0.0",
    fear_greed_index: "50",
    hold_reason: null,
    signals_paused: false,
    hold_history: [],

    updateMacroStatus: (payload) => {
        set((state) => ({
            ...state,
            ...payload,
            hold_history: payload.new_status === 'HOLD'
                ? [{ ...payload, timestamp: new Date().toISOString() }, ...state.hold_history]
                : state.hold_history
        }));
    },
}));
