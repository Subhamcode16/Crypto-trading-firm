import { create } from 'zustand';

export const useRiskStore = create((set) => ({
    daily_loss_usd: "0.00",
    daily_loss_pct: "0.0",
    daily_loss_limit_usd: "100.00",
    portfolio_exposure_usd: "0.00",
    portfolio_exposure_pct: "0.0",
    portfolio_max_usd: "500.00",
    open_positions_count: 0,
    kill_switch_states: {
        tier1: "ARMED",
        tier2: "ARMED",
        tier3: "ARMED",
        tier4: "MONITORING"
    },
    audit_trail: [],

    updateRiskState: (payload) => {
        set((state) => ({ ...state, ...payload }));
    },

    recordKillEvent: (payload) => {
        set((state) => ({
            audit_trail: [{ ...payload, timestamp: new Date().toISOString() }, ...state.audit_trail]
        }));
    },
}));
