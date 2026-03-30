import React, { useState, useEffect, useRef } from 'react';
import { useAgentStore } from '../stores/useAgentStore';
import { Terminal, Filter, Trash2, Cpu } from 'lucide-react';

export const ConsoleView = () => {
    const agents = useAgentStore((state) => state.agents);
    const [selectedAgentId, setSelectedAgentId] = useState('all');
    const scrollRef = useRef(null);

    // Flatten all logs and sort by timestamp if 'all' is selected
    const allLogs = Object.values(agents).flatMap(agent => 
        agent.logs.map(log => ({ ...log, agentName: agent.name, agentId: agent.id }))
    ).sort((a, b) => b.id - a.id); // Newer first for simpler unshift logic or keep old first for terminal

    // Actually, terminal usually appends to bottom. Let's do chronological.
    const displayLogs = (selectedAgentId === 'all' 
        ? Object.values(agents).flatMap(agent => 
            agent.logs.map(log => ({ ...log, agentName: agent.name, agentId: agent.id }))
          ).sort((a, b) => a.id - b.id)
        : agents[selectedAgentId]?.logs.map(log => ({ ...log, agentName: agents[selectedAgentId].name, agentId: selectedAgentId }))
          .sort((a, b) => a.id - b.id)
    ) || [];

    useEffect(() => {
        if (scrollRef.current) {
            scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
        }
    }, [displayLogs]);

    return (
        <div className="flex-1 flex flex-col bg-black text-[#00ff41] font-mono p-4 md:p-8 overflow-hidden pt-[80px]">
            {/* Header / Toolbar */}
            <div className="flex flex-wrap items-center justify-between gap-4 mb-6 border-b border-[#00ff41]/30 pb-4">
                <div className="flex items-center gap-3">
                    <Terminal size={20} className="animate-pulse" />
                    <h2 className="text-xl font-bold tracking-tiler uppercase">Agent Terminal v4.0.5</h2>
                </div>
                
                <div className="flex items-center gap-2 overflow-x-auto pb-2 md:pb-0 no-scrollbar">
                    <button 
                        onClick={() => setSelectedAgentId('all')}
                        className={`px-3 py-1 border border-[#00ff41] text-[10px] uppercase transition-colors ${selectedAgentId === 'all' ? 'bg-[#00ff41] text-black shadow-[0_0_10px_#00ff41]' : 'hover:bg-[#00ff41]/20'}`}
                    >
                        ALL_STREAMS
                    </button>
                    {Object.values(agents).map(agent => (
                        <button 
                            key={agent.id}
                            onClick={() => setSelectedAgentId(agent.id)}
                            className={`px-3 py-1 border border-[#00ff41] text-[10px] uppercase transition-colors whitespace-nowrap ${selectedAgentId === agent.id ? 'bg-[#00ff41] text-black shadow-[0_0_10px_#00ff41]' : 'hover:bg-[#00ff41]/20'}`}
                        >
                            AGT_{agent.id}
                        </button>
                    ))}
                </div>
            </div>

            {/* Console Body */}
            <div 
                ref={scrollRef}
                className="flex-1 overflow-y-auto pr-4 custom-terminal-scrollbar bg-[#050505] border border-[#00ff41]/20 p-4 shadow-[inset_0_0_20px_rgba(0,255,65,0.05)]"
            >
                <div className="space-y-1">
                    {displayLogs.length === 0 ? (
                        <div className="animate-pulse italic opacity-50 text-sm">Wait for incoming packets...</div>
                    ) : (
                        displayLogs.map((log, index) => (
                            <div key={log.id} className="group hover:bg-[#00ff41]/10 px-2 py-0.5 rounded transition-colors text-xs md:text-sm flex gap-3">
                                <span className="text-[#00ff41]/40 shrink-0">[{log.timestamp}]</span>
                                <span className="text-white bg-[#00ff41]/20 px-1 rounded shrink-0 font-bold">
                                    {log.agentName || `AGT_${log.agentId}`}
                                </span>
                                <span className={
                                    log.type === 'error' ? 'text-red-500' :
                                    log.type === 'trade' ? 'text-blue-400' :
                                    log.type === 'risk' ? 'text-amber-400' :
                                    'text-[#00ff41]'
                                }>
                                    {log.message}
                                </span>
                            </div>
                        ))
                    )}
                    <div className="h-4 flex items-center gap-2">
                        <span className="w-2 h-4 bg-[#00ff41] animate-[blink_1s_infinite]"></span>
                        <span className="text-[10px] opacity-30">LISTENING_FOR_EVENTS...</span>
                    </div>
                </div>
            </div>

            {/* Matrix Scanline Overlay */}
            <div className="pointer-events-none fixed inset-0 z-50 overflow-hidden opacity-[0.03]">
                <div className="absolute inset-0 bg-[linear-gradient(rgba(18,16,16,0)_50%,rgba(0,0,0,0.25)_50%),linear-gradient(90deg,rgba(255,0,0,0.06),rgba(0,255,0,0.02),rgba(0,0,255,0.06))] bg-[length:100%_2px,3px_100%]"></div>
            </div>

            <style dangerouslySetInnerHTML={{ __html: `
                @keyframes blink {
                    0%, 100% { opacity: 1; }
                    50% { opacity: 0; }
                }
                .custom-terminal-scrollbar::-webkit-scrollbar {
                    width: 4px;
                }
                .custom-terminal-scrollbar::-webkit-scrollbar-track {
                    background: transparent;
                }
                .custom-terminal-scrollbar::-webkit-scrollbar-thumb {
                    background: #00ff41;
                    border-radius: 2px;
                }
                .no-scrollbar::-webkit-scrollbar {
                    display: none;
                }
            `}} />
        </div>
    );
};
