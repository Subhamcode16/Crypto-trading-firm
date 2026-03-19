import { create } from 'zustand';

export const useTradeStore = create((set) => ({
    open_positions: {},
    closed_trades: [],
    isLoadingHistory: false,
    initialCapital: 10.0,
    totalPnl: 0,

    fetchInitialCapital: async () => {
        try {
            const response = await fetch('http://localhost:8000/api/portfolio/balance');
            const result = await response.json();
            if (result.status === 'success') {
                set({ initialCapital: result.initial_capital });
            }
        } catch (error) {
            console.error("Error fetching initial capital:", error);
        }
    },

    fetchTradeHistory: async (userId, apiKey) => {
        set({ isLoadingHistory: true });
        try {
            const response = await fetch(`http://localhost:8000/api/trades/history/${userId}`, {
                method: 'GET',
                headers: {
                    'X-Admin-Key': apiKey,
                    'Content-Type': 'application/json'
                }
            });
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            const result = await response.json();
            
            if (result.status === 'success') {
                // Convert arrays from backend to what frontend expects
                const openPositionsMap = {};
                if (result.data && result.data.active) {
                    result.data.active.forEach(pos => {
                        openPositionsMap[pos.position_id] = pos;
                    });
                }
                
                const allTrades = [...Object.values(openPositionsMap), ...(result.data?.closed || [])];
                const totalPnl = allTrades.reduce((sum, trade) => sum + (trade.pnl_usd || 0), 0);

                set({ 
                    open_positions: openPositionsMap,
                    closed_trades: (result.data && result.data.closed) ? result.data.closed : [],
                    totalPnl: totalPnl
                });
            }
        } catch (error) {
            console.error("Error fetching trade history:", error);
        } finally {
            set({ isLoadingHistory: false });
        }
    },

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
