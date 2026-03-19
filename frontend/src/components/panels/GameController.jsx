import React, { useEffect } from 'react';
import { useSystemStore } from '../../stores/useSystemStore';
import { useAgentStore } from '../../stores/useAgentStore';

export function GameController() {
    const { isPaused, isStarting, setStarting, togglePause, zoomIn, zoomOut, syncStatus, zoom } = useSystemStore();
    const agents = useAgentStore((state) => state.agents);
    const onlineCount = Object.values(agents).filter(a => a.is_online).length;

    useEffect(() => {
        syncStatus();
        const interval = setInterval(syncStatus, 10000); // Polling as backup
        return () => clearInterval(interval);
    }, []);

    return (
        <div className="fixed right-6 top-24 z-50 flex flex-col gap-4 pointer-events-none">
            {/* Prominent Status Indicator Badge */}
            <div className={`pointer-events-auto flex items-center gap-3 px-4 py-2 rounded-l-full border-y-2 border-l-2 border-black shadow-[4px_4px_0px_0px_rgba(0,0,0,1)] ${isPaused ? 'bg-amber-100' : 'bg-green-100'}`}>
                <div className={`w-3 h-3 rounded-full border border-black ${isStarting ? 'bg-blue-500 animate-pulse' : isPaused ? 'bg-amber-500 animate-pulse' : 'bg-green-500'}`} />
                <span className="text-[10px] font-bold pixel-font tracking-tighter uppercase whitespace-nowrap">
                    {isStarting ? 'Starting...' : isPaused ? 'WAITING FOR YOUR COMMAND BOSS' : 'System Online'}
                </span>
            </div>

            {/* System Status Panel */}
            <div className="rpg-panel p-4 min-w-[220px] pointer-events-auto bg-white/95 backdrop-blur-md border-2 border-black shadow-[4px_4px_0px_0px_rgba(0,0,0,1)]">
                <div className="flex justify-between items-center mb-3">
                    <span className="text-[10px] font-bold uppercase tracking-wider pixel-font">Controller v1.1</span>
                    <div className="flex gap-1">
                        {[1,2,3].map(i => <div key={i} className="w-1.5 h-1.5 bg-black/20 rounded-full" />)}
                    </div>
                </div>

                <div className="space-y-2 pb-3 border-b border-black/10">
                    <div className="flex justify-between items-center text-[10px] pixel-font">
                        <span className="text-gray-500">ACTIVE_AGENTS</span>
                        <span className="font-bold">{onlineCount}/9</span>
                    </div>
                    <div className="flex justify-between items-center text-[10px] pixel-font">
                        <span className="text-gray-500">ZOOM_FACTOR</span>
                        <span className="font-bold">{zoom.toFixed(1)}x</span>
                    </div>
                </div>

                <div className="mt-3 grid grid-cols-2 gap-2">
                    <button 
                        onClick={zoomIn}
                        className="rpg-button py-1.5 text-[9px] pixel-font active:translate-y-1"
                    >
                        [+] ZOOM
                    </button>
                    <button 
                        onClick={zoomOut}
                        className="rpg-button py-1.5 text-[9px] pixel-font active:translate-y-1"
                    >
                        [-] ZOOM
                    </button>
                </div>

                <div className="mt-4 flex gap-2">
                    <button 
                        onClick={togglePause}
                        className={`w-full py-3 rpg-button active:translate-y-1 ${isPaused ? 'bg-green-500 text-white' : 'bg-amber-200 hover:bg-amber-300'}`}
                    >
                        <span className="text-[10px] font-bold title-font tracking-wide">
                            {isPaused ? '⏺ RESUME' : '⏸ PAUSE'}
                        </span>
                    </button>
                </div>
            </div>

            {/* Micro Instruction */}
            <div className="text-[8px] text-gray-500 pixel-font text-right uppercase opacity-60 pr-2">
                Use Controller to manage global agent activity
            </div>
        </div>
    );
}
