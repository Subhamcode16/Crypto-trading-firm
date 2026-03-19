import React, { useEffect } from 'react';
import { X, ExternalLink, Shield, Terminal, Zap, Search } from 'lucide-react';
import { useAgentStore } from '../../stores/useAgentStore';

export const AgentPanel = ({ agent, onClose }) => {
    const fetchAgentLogs = useAgentStore(state => state.fetchAgentLogs);

    useEffect(() => {
        if (agent && agent.logs.length === 0) {
            fetchAgentLogs(agent.id);
        }
    }, [agent?.id, fetchAgentLogs]);

    if (!agent) return null;

    const getLogColor = (level) => {
        switch (level) {
            case 'discovery': return 'text-green-600';
            case 'scan': return 'text-blue-600';
            case 'alert': return 'text-red-600';
            case 'urgent': return 'text-orange-600';
            default: return 'text-black';
        }
    };

    const getLogIcon = (level) => {
        switch (level) {
            case 'discovery': return <Zap size={8} className="text-green-600" />;
            case 'scan': return <Search size={8} className="text-blue-600" />;
            case 'alert': return <Shield size={8} className="text-red-600" />;
            default: return <Terminal size={8} className="text-gray-500" />;
        }
    };

    return (
        <div className="fixed right-6 top-24 bottom-24 w-[420px] max-w-[90vw] rpg-panel overflow-y-auto pointer-events-auto animate-in slide-in-from-right duration-200 z-[1000]">
            <div className="flex justify-between items-start mb-4 border-b-2 border-black pb-2">
                <div>
                    <span className="text-[8px] text-gray-700 font-bold uppercase tracking-widest pixel-font">STATION {agent.floor}-{agent.id}</span>
                    <h2 className="text-xl font-bold tracking-widest text-black mt-1 title-font">
                        {agent.name.toUpperCase()}
                    </h2>
                </div>
                <button
                    onClick={onClose}
                    className="p-1 px-2 bg-[#d0d0d0] border-2 border-white border-b-black border-r-black active:border-black active:border-b-white active:border-r-white text-black pixel-font text-[10px]"
                >
                    X
                </button>
            </div>

            <div className="space-y-4">
                {/* Status Indicator */}
                <div className="flex items-center justify-between p-2 rpg-inset">
                    <span className="text-[8px] text-black font-bold uppercase pixel-font">CURRENT TASK</span>
                    <div className="flex items-center gap-2">
                        <div className={`w-3 h-3 rounded-full border border-black shadow-[inset_1px_1px_2px_rgba(255,255,255,0.7)] ${agent.is_online ? 'bg-green-500 animate-pulse' : 'bg-red-500'}`}></div>
                        <span className={`text-[10px] font-bold uppercase title-font ${agent.status === 'IDLE' ? 'text-gray-500' : 'text-blue-600'}`}>
                            {agent.status}
                        </span>
                    </div>
                </div>

                {/* Stats Grid */}
                <div className="grid grid-cols-2 gap-4">
                    <div className="p-2 rpg-inset flex flex-col items-center">
                        <div className="text-[7px] text-gray-600 font-bold mb-1 uppercase pixel-font">CONFIDENCE</div>
                        <div className="text-sm font-bold title-font text-black">74.2%</div>
                    </div>
                    <div className="p-2 rpg-inset flex flex-col items-center">
                        <div className="text-[7px] text-gray-600 font-bold mb-1 uppercase pixel-font">PROFIT</div>
                        <div className="text-sm font-bold title-font text-blue-600">+12%</div>
                    </div>
                </div>

                {/* Activity Feed */}
                <div className="rpg-inset p-3 min-h-[200px] flex flex-col">
                    <h3 className="text-[8px] font-bold text-black uppercase border-b border-black pb-1 mb-2 pixel-font flex items-center gap-2">
                        <Terminal size={10} />
                        DETAILED ACTIVITY LOGS
                    </h3>
                    <div className="space-y-3 overflow-y-auto max-h-[300px] pr-1 custom-scrollbar">
                        {agent.logs && agent.logs.length > 0 ? (
                            agent.logs.map((log) => (
                                <div key={log.id} className="flex gap-2 text-[8px] pixel-font leading-normal border-b border-gray-100 pb-2 last:border-0 transform transition-all hover:translate-x-1">
                                    <div className="flex-shrink-0 text-gray-400 font-bold w-12">{log.timestamp}</div>
                                    <div className="flex-shrink-0 mt-0.5">{getLogIcon(log.level)}</div>
                                    <div className={`flex-1 break-words font-medium ${getLogColor(log.level)}`}>
                                        {log.content}
                                    </div>
                                </div>
                            ))
                        ) : (
                            <div className="text-[8px] text-gray-400 italic text-center py-10 pixel-font">
                                No activity recorded...
                            </div>
                        )}
                    </div>
                </div>

                {/* Action Buttons */}
                <div className="pt-2 space-y-2">
                    <button className="w-full py-2 bg-[#d0d0d0] border-2 border-white border-b-black border-r-black active:border-black active:border-b-white active:border-r-white text-black font-bold pixel-font text-[8px] flex items-center justify-center gap-2 hover:bg-[#c0c0c0] transition-colors">
                        <ExternalLink size={14} className="text-black" />
                        INJECT PROMPT
                    </button>
                    <button className="w-full py-2 bg-[#ffcccc] border-2 border-white border-b-black border-r-black active:border-black active:border-b-white active:border-r-white text-red-600 font-bold pixel-font text-[8px] flex items-center justify-center gap-2 hover:bg-[#ffb3b3] transition-colors">
                        <Shield size={14} className="text-red-600" />
                        FORCE KILL
                    </button>
                </div>
            </div>
        </div>
    );
};
