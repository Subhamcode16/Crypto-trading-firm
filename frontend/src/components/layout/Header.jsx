import React from 'react';
import { LayoutDashboard, Mail, ShieldAlert, Activity, Monitor } from 'lucide-react';
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
        <header className="fixed top-2 left-2 right-2 h-16 rpg-panel flex flex-col md:flex-row items-center justify-between z-50 pointer-events-auto">
            <div className="flex items-center gap-6 w-full md:w-auto overflow-x-auto hide-scrollbar">

                {/* Brand Logo Area */}
                <div className="flex items-center gap-2">
                    <Activity size={20} className="text-black" />
                    <h1 className="text-sm font-bold title-font text-black whitespace-nowrap">
                        PIXEL FIRM
                    </h1>
                </div>

                {/* View Navigation Switch */}
                <div className="flex bg-[#d0d0d0] p-1 border-2 border-white border-b-black border-r-black">
                    <button
                        onClick={() => navigate('/')}
                        className={`flex items-center gap-1 px-3 py-1 text-[10px] font-bold title-font transition-colors ${location.pathname === '/' ? 'bg-black text-white shadow-inner' : 'text-black hover:bg-white'} whitespace-nowrap`}
                    >
                        <Monitor size={12} />
                        OFFICE
                    </button>
                    <button
                        onClick={() => navigate('/dashboard')}
                        className={`flex items-center gap-1 px-3 py-1 text-[10px] font-bold title-font transition-colors ${location.pathname === '/dashboard' ? 'bg-black text-white shadow-inner' : 'text-black hover:bg-white'} whitespace-nowrap`}
                    >
                        <LayoutDashboard size={12} />
                        STATS
                    </button>
                </div>

            </div>

            <div className="hidden md:flex items-center gap-4">
                <div className="rpg-inset flex flex-col items-center min-w-[120px] px-3">
                    <span className="text-[7px] text-gray-600 uppercase pixel-font mb-1">ACCOUNT BALANCE</span>
                    <span className={`text-[11px] font-black title-font ${currentBalance >= initialCapital ? 'text-emerald-600' : 'text-red-600'}`}>
                        ${currentBalance.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                    </span>
                </div>

                <div className="flex flex-col items-end">
                    <span className="text-[7px] text-gray-600 uppercase pixel-font mb-1">REGIME | STATUS</span>
                    <div className="flex items-center gap-2 py-1 px-2 rpg-inset">
                        <span className={`text-[9px] font-bold uppercase title-font ${macro.market_regime === 'BULLISH' ? 'text-green-600' :
                                macro.market_regime === 'CHOPPY' ? 'text-amber-600' :
                                    macro.market_regime === 'FLAT' ? 'text-gray-500' : 'text-blue-600'
                            }`}>
                            {macro.market_regime}
                        </span>
                        <div className="w-[1px] h-3 bg-black/20 mx-1"></div>
                        <div className="w-2 h-2 rounded-full border border-black shadow-[inset_1px_1px_2px_rgba(255,255,255,0.7)] bg-green-500 animate-pulse"></div>
                        <span className="text-[9px] text-black font-bold uppercase title-font">{macro.status}</span>
                    </div>
                </div>
            </div>

            {/* Action Buttons */}
            <nav className="hidden md:flex items-center gap-2">
                <button
                    onClick={() => setDrawerOpen(!isDrawerOpen)}
                    className="relative p-2 bg-[#d0d0d0] border-2 border-white border-b-black border-r-black active:border-black active:border-b-white active:border-r-white flex items-center justify-center cursor-pointer group"
                >
                    <Mail size={16} className="text-black group-hover:scale-110 transition-transform" />
                    {unreadCount > 0 && (
                        <div className="absolute -top-1 -right-1 w-4 h-4 bg-red-600 border border-black flex items-center justify-center animate-bounce">
                            <span className="text-[8px] text-white font-bold leading-none">{unreadCount}</span>
                        </div>
                    )}
                </button>
                <button className="p-2 bg-[#d0d0d0] border-2 border-white border-b-black border-r-black active:border-black active:border-b-white active:border-r-white flex items-center justify-center cursor-pointer">
                    <ShieldAlert size={16} className="text-red-600" />
                </button>
            </nav>
        </header>
    );
};
