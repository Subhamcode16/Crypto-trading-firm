import React from 'react';
import { LayoutDashboard, Mail, ShieldAlert, Activity, Monitor, Terminal, Wallet, Gamepad2, BrainCircuit } from 'lucide-react';
import { useMacroStore } from '../../stores/useMacroStore';
import { useMessageStore } from '../../stores/useMessageStore';
import { useTradeStore } from '../../stores/useTradeStore';
import { useNavigate, useLocation } from 'react-router-dom';

export const Header = () => {
    const macro = useMacroStore();
    const { unreadCount, setDrawerOpen, isDrawerOpen } = useMessageStore();
    const { initialCapital, totalPnl, fetchInitialCapital } = useTradeStore();
    const navigate = useNavigate();
    const location = useLocation();

    const currentBalance = initialCapital + totalPnl;

    React.useEffect(() => {
        fetchInitialCapital();
    }, [fetchInitialCapital]);

    return (
        <header className="fixed top-2 left-2 right-2 h-16 comic-panel flex flex-col md:flex-row items-center justify-between z-50 pointer-events-auto bg-white p-2">
            <div className="flex items-center gap-6 w-full md:w-auto overflow-x-auto hide-scrollbar">

                {/* Brand Logo Area */}
                <div className="flex items-center gap-2 bg-springfield-yellow border-2 border-black p-2 shadow-comic-sm">
                    <Activity size={24} className="text-black" />
                    <h1 className="text-lg font-comic uppercase text-black whitespace-nowrap tracking-widest leading-none">
                        Springfield Cap
                    </h1>
                </div>

                {/* View Navigation Switch */}
                <div className="flex bg-white border-4 border-black shadow-comic-sm divide-x-4 divide-black">
                    <button
                        onClick={() => navigate('/')}
                        className={`flex items-center gap-2 px-4 py-1 text-sm font-comic uppercase transition-colors ${location.pathname === '/' ? 'bg-black text-white' : 'text-black hover:bg-gray-200'} whitespace-nowrap`}
                    >
                        <Monitor size={16} />
                        OFFICE
                    </button>
                    <button
                        onClick={() => navigate('/mission')}
                        className={`flex items-center gap-2 px-4 py-1 text-sm font-comic uppercase transition-colors ${location.pathname === '/mission' ? 'bg-black text-white' : 'text-black hover:bg-gray-200'} whitespace-nowrap`}
                    >
                        <Gamepad2 size={16} />
                        MISSION
                    </button>
                    <button
                        onClick={() => navigate('/explain')}
                        className={`flex items-center gap-2 px-4 py-1 text-sm font-comic uppercase transition-colors ${location.pathname.startsWith('/explain') ? 'bg-black text-white' : 'text-black hover:bg-gray-200'} whitespace-nowrap`}
                    >
                        <BrainCircuit size={16} />
                        NEURAL
                    </button>
                </div>

            </div>

            <div className="hidden md:flex items-center gap-4">
                <div className="bg-white border-4 border-black shadow-comic-sm flex flex-col items-center min-w-[120px] px-3 py-1">
                    <span className="text-[10px] text-gray-500 font-comic uppercase tracking-wider mb-1">Vault Balance</span>
                    <span className={`text-sm font-mono font-bold ${currentBalance >= initialCapital ? 'text-radioactive-green' : 'text-burns-red'}`}>
                        ${currentBalance.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                    </span>
                </div>

                <div className="flex flex-col items-end">
                    <span className="text-[10px] text-gray-500 font-comic uppercase tracking-wider mb-1">Regime | Status</span>
                    <div className="flex items-center gap-2 py-1 px-2 border-4 border-black bg-white shadow-comic-sm">
                        <span className={`text-[10px] font-bold font-comic uppercase ${macro.market_regime === 'BULLISH' ? 'text-radioactive-green' :
                                macro.market_regime === 'CHOPPY' ? 'text-springfield-yellow text-shadow-sm' :
                                    macro.market_regime === 'FLAT' ? 'text-gray-500' : 'text-lisa-blue'
                            }`}>
                            {macro.market_regime}
                        </span>
                        <div className="w-[2px] h-3 bg-black mx-1"></div>
                        <div className="w-3 h-3 rounded-full border-2 border-black bg-radioactive-green animate-pulse"></div>
                        <span className="text-[10px] text-black font-bold font-comic uppercase">{macro.status}</span>
                    </div>
                </div>
            </div>

            {/* Action Buttons */}
            <nav className="hidden md:flex items-center gap-2">
                <button
                    onClick={() => setDrawerOpen(!isDrawerOpen)}
                    className="relative p-2 bg-white border-4 border-black hover:bg-gray-200 flex items-center justify-center cursor-pointer shadow-comic-sm transition-transform active:translate-y-1"
                >
                    <Mail size={20} className="text-black" />
                    {unreadCount > 0 && (
                        <div className="absolute -top-2 -right-2 w-6 h-6 bg-burns-red border-2 border-black rounded-full flex items-center justify-center animate-bounce">
                            <span className="text-xs text-white font-mono font-bold leading-none">{unreadCount}</span>
                        </div>
                    )}
                </button>
                <button className="p-2 bg-white border-4 border-black hover:bg-gray-200 flex items-center justify-center cursor-pointer shadow-comic-sm transition-transform active:translate-y-1">
                    <ShieldAlert size={20} className="text-burns-red" />
                </button>
            </nav>
        </header>
    );
};
