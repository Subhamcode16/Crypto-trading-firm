import React from 'react';
import { Play, Flame, TrendingDown, ShieldCheck } from 'lucide-react';

export const ScenarioMenu = ({ onTrigger }) => {
    const scenarios = [
        { name: 'BTC_CRASH', icon: <TrendingDown size={14} />, label: 'MARKET_CRASH' },
        { name: 'BIG_BUY', icon: <Flame size={14} />, label: 'WHALE_SIGNAL' },
        { name: 'KILL_SWITCH_ACTIVE', icon: <ShieldCheck size={14} />, label: 'EMERGENCY' },
    ];

    return (
        <div className="fixed left-6 bottom-32 z-50 pointer-events-auto">
            <div className="rpg-panel flex flex-col gap-2">
                <div className="px-2 py-1 mb-2 border-b-2 border-black">
                    <span className="text-[10px] font-bold text-black uppercase pixel-font">DEV MENU</span>
                </div>
                {scenarios.map(s => (
                    <button
                        key={s.name}
                        onClick={() => onTrigger(s.name)}
                        className="flex items-center gap-3 px-3 py-2 bg-[#d0d0d0] border-2 border-white border-b-black border-r-black active:border-black active:border-b-white active:border-r-white text-black text-[8px] pixel-font transition-all"
                    >
                        <span className="text-black">{s.icon}</span>
                        {s.label}
                    </button>
                ))}
            </div>
        </div>
    );
};
