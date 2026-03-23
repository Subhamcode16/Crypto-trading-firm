import { create } from 'zustand';

export const useSystemStore = create((set, get) => ({
    isPaused: false,
    isStarting: false,
    zoom: 1.2,
    
    setPaused: (paused) => set({ isPaused: paused }),
    setStarting: (starting) => set({ isStarting: starting }),
    
    togglePause: async () => {
        const { isPaused } = get();
        const nextState = !isPaused;
        const endpoint = nextState ? '/api/system/pause' : '/api/system/resume';
        
        try {
            const response = await fetch(`${import.meta.env.VITE_API_URL || 'http://localhost:8000'}${endpoint}`, {
                method: 'POST',
                headers: {
                    'X-Admin-Key': 'dev-admin-key' // In prod, this would be from env/auth
                }
            });
            const data = await response.json();
            if (data.status === 'success') {
                set({ isPaused: nextState });
            }
        } catch (err) {
            console.error('Failed to toggle system pause', err);
        }
    },

    startSystem: async (wsSend) => {
        if (wsSend) {
            wsSend({ type: 'RUN_SCENARIO', name: 'v4_PIPELINE_START' });
        }
    },
    
    setZoom: (newZoom) => {
        const limitedZoom = Math.max(0.2, Math.min(5.0, newZoom));
        set({ zoom: limitedZoom });
    },
    
    zoomIn: () => {
        const { zoom, setZoom } = get();
        setZoom(zoom + 0.2);
    },
    
    zoomOut: () => {
        const { zoom, setZoom } = get();
        setZoom(zoom - 0.2);
    },
    
    syncStatus: async () => {
        try {
            const response = await fetch(`${import.meta.env.VITE_API_URL || 'http://localhost:8000'}/api/system/status`);
            const data = await response.json();
            if (data.status === 'success') {
                set({ isPaused: data.is_paused });
            }
        } catch (err) {
            console.error('Failed to sync system status', err);
        }
    }
}));
