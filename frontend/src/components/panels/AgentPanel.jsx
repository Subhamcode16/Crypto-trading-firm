import React from 'react';
import { X, ExternalLink, Shield } from 'lucide-react';

export const AgentPanel = ({ agent, onClose }) => {
    if (!agent) return null;

    return (
        <div className="fixed right-6 top-24 bottom-24 w-84 rpg-panel overflow-y-auto pointer-events-auto animate-in slide-in-from-right duration-200">
            <div className="flex justify-between items-start mb-4 border-b-2 border-black pb-2">
                <div>
                    <span className="text-[8px] text-gray-700 font-bold uppercase tracking-widest pixel-font">FLOOR {agent.floor}</span>
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
                    <span className="text-[8px] text-black font-bold uppercase pixel-font">STATUS</span>
                    <div className="flex items-center gap-2">
                        <div className={`w-3 h-3 rounded-full border border-black shadow-[inset_1px_1px_2px_rgba(255,255,255,0.7)] ${agent.is_online ? 'bg-green-500' : 'bg-red-500'}`}></div>
                        <span className="text-[10px] font-bold uppercase title-font text-black">{agent.status}</span>
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
                <div className="rpg-inset p-3">
                    <h3 className="text-[8px] font-bold text-black uppercase border-b border-black pb-1 mb-2 pixel-font">
                        LATEST LOGS
                    </h3>
                    <div className="space-y-2">
                        {[1, 2, 3].map(i => (
                            <div key={i} className="flex gap-2 text-[8px] pixel-font leading-relaxed">
                                <div className="flex-shrink-0 text-gray-500">14:0{i}</div>
                                <div className="text-black">
                                    Analyzing correlation <span className="font-bold text-blue-600">SOL</span> at node {i}x8F
                                </div>
                            </div>
                        ))}
                    </div>
                </div>

                {/* Action Buttons */}
                <div className="pt-2 space-y-2">
                    <button className="w-full py-2 bg-[#d0d0d0] border-2 border-white border-b-black border-r-black active:border-black active:border-b-white active:border-r-white text-black font-bold pixel-font text-[8px] flex items-center justify-center gap-2">
                        <ExternalLink size={14} className="text-black" />
                        INJECT PROMPT
                    </button>
                    <button className="w-full py-2 bg-[#ffcccc] border-2 border-white border-b-black border-r-black active:border-black active:border-b-white active:border-r-white text-red-600 font-bold pixel-font text-[8px] flex items-center justify-center gap-2">
                        <Shield size={14} className="text-red-600" />
                        FORCE KILL
                    </button>
                </div>
            </div>
        </div>
    );
};
