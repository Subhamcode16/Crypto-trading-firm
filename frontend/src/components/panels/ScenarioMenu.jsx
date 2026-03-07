import React from 'react';
import { TrendingDown, Flame, ShieldCheck, AlertTriangle, CheckCircle, XCircle, Wifi, WifiOff } from 'lucide-react';

export const ScenarioMenu = ({ onTrigger }) => {
    const scenarios = [
        { name: 'ALL_AGENTS_ONLINE', icon: <Wifi size={14} />, label: 'ALL ONLINE', color: 'bg-emerald-100 text-emerald-800' },
        { name: 'ALL_AGENTS_OFFLINE', icon: <WifiOff size={14} />, label: 'ALL OFFLINE', color: 'bg-gray-200 text-gray-600' },
        { name: 'SIGNAL_FOUND', icon: <Flame size={14} />, label: 'SIGNAL FOUND', color: '' },
        { name: 'BTC_CRASH', icon: <TrendingDown size={14} />, label: 'MARKET CRASH', color: '' },
        { name: 'KILL_SWITCH_ACTIVE', icon: <ShieldCheck size={14} />, label: 'KILL SWITCH', color: '' },
        { name: 'TRADE_EXECUTE', icon: <CheckCircle size={14} />, label: 'EXECUTE TRADE', color: '' },
        { name: 'MACRO_RISK', icon: <AlertTriangle size={14} />, label: 'MACRO RISK', color: '' },
        { name: 'SIGNAL_KILLED', icon: <XCircle size={14} />, label: 'SIGNAL KILLED', color: '' },
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
                        className={`flex items-center gap-3 px-3 py-2 border-2 border-white border-b-black border-r-black active:border-black active:border-b-white active:border-r-white text-black text-[8px] pixel-font transition-all ${s.color || 'bg-[#d0d0d0]'}`}
                    >
                        <span className="text-black">{s.icon}</span>
                        {s.label}
                    </button>
                ))}
            </div>
        </div>
    );
};
