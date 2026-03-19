import { create } from 'zustand';

export const useInsightStore = create((set, get) => ({
    pipeline: {
        found: 0,
        dropped: 0,
        passed: 0,
        conversion_rate: '0%'
    },
    
    news: [],

    lastSync: null,

    addNews: (item) => set((state) => ({
        news: [{ ...item, id: Date.now() }, ...state.news].slice(0, 50),
        lastSync: new Date().toLocaleTimeString()
    })),

    updatePipeline: (updates) => set((state) => ({
        pipeline: { ...state.pipeline, ...updates },
        lastSync: new Date().toLocaleTimeString()
    }))
}));
