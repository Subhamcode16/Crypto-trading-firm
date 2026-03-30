import React, { useEffect } from 'react';
import { useTradeStore } from '../stores/useTradeStore';
import { TrendingUp, TrendingDown, DollarSign, Target, History, Wallet, Activity } from 'lucide-react';

export const AccountView = () => {
    const { 
        initialCapital, 
        totalPnl, 
        open_positions, 
        closed_trades, 
        fetchTradeHistory,
        isLoadingHistory 
    } = useTradeStore();

    const currentBalance = initialCapital + totalPnl;
    const pnlPct = (totalPnl / initialCapital) * 100;
    
    const winCount = closed_trades.filter(t => t.pnl_usd > 0).length;
    const totalClosed = closed_trades.length;
    const winRate = totalClosed > 0 ? (winCount / totalClosed) * 100 : 0;

    useEffect(() => {
        // Refresh history on mount
        fetchTradeHistory('default_user', 'ADMIN_KEY_123'); // Assuming default user for now
    }, [fetchTradeHistory]);

    return (
        <div className="flex-1 overflow-y-auto p-4 md:p-8 pt-[80px] bg-[#f0f0f0] flex flex-col gap-6">
            
            {/* Header / Summary Cards */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                <div className="rpg-panel p-4 flex items-center gap-4">
                    <div className="w-12 h-12 bg-blue-100 rounded-full flex items-center justify-center text-blue-600">
                        <Wallet size={24} />
                    </div>
                    <div>
                        <div className="text-[8px] pixel-font uppercase text-gray-500">Total Portfolio</div>
                        <div className="text-xl font-bold title-font prose-black">${currentBalance.toLocaleString(undefined, { minimumFractionDigits: 2 })}</div>
                    </div>
                </div>

                <div className="rpg-panel p-4 flex items-center gap-4">
                    <div className={`w-12 h-12 rounded-full flex items-center justify-center ${totalPnl >= 0 ? 'bg-green-100 text-green-600' : 'bg-red-100 text-red-600'}`}>
                        {totalPnl >= 0 ? <TrendingUp size={24} /> : <TrendingDown size={24} />}
                    </div>
                    <div>
                        <div className="text-[8px] pixel-font uppercase text-gray-500">Unrealized PnL</div>
                        <div className={`text-xl font-bold title-font ${totalPnl >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                            {totalPnl >= 0 ? '+' : ''}${totalPnl.toLocaleString(undefined, { minimumFractionDigits: 4 })}
                        </div>
                    </div>
                </div>

                <div className="rpg-panel p-4 flex items-center gap-4">
                    <div className="w-12 h-12 bg-purple-100 rounded-full flex items-center justify-center text-purple-600">
                        <Target size={24} />
                    </div>
                    <div>
                        <div className="text-[8px] pixel-font uppercase text-gray-500">Win Rate</div>
                        <div className="text-xl font-bold title-font text-purple-600">{winRate.toFixed(1)}%</div>
                    </div>
                </div>

                <div className="rpg-panel p-4 flex items-center gap-4">
                    <div className={`w-12 h-12 rounded-full flex items-center justify-center ${pnlPct >= 0 ? 'bg-emerald-100 text-emerald-600' : 'bg-rose-100 text-rose-600'}`}>
                        {pnlPct >= 0 ? <TrendingUp size={24} /> : <TrendingDown size={24} />}
                    </div>
                    <div>
                        <div className="text-[8px] pixel-font uppercase text-gray-500">ROI Percentage</div>
                        <div className={`text-xl font-bold title-font ${pnlPct >= 0 ? 'text-emerald-600' : 'text-rose-600'}`}>
                            {pnlPct >= 0 ? '+' : ''}{pnlPct.toFixed(2)}%
                        </div>
                    </div>
                </div>
            </div>

            {/* Main Content Area */}
            <div className="flex flex-col lg:flex-row gap-6">
                
                {/* Active Positions */}
                <div className="flex-1 flex flex-col gap-4">
                    <div className="flex items-center gap-2 px-2">
                        <Activity size={16} className="text-blue-600" />
                        <h3 className="text-xs font-bold title-font uppercase tracking-wider">Active Positions</h3>
                        <span className="text-[10px] bg-blue-600 text-white px-1.5 py-0.5 rounded ml-auto">{Object.keys(open_positions).length}</span>
                    </div>
                    
                    <div className="rpg-panel overflow-hidden border-2 border-white border-b-black border-r-black">
                        <div className="overflow-x-auto">
                            <table className="w-full text-left border-collapse">
                                <thead className="bg-[#d0d0d0] border-b-2 border-black">
                                    <tr>
                                        <th className="p-3 text-[9px] pixel-font uppercase tracking-tighter">Token</th>
                                        <th className="p-3 text-[9px] pixel-font uppercase">Entry</th>
                                        <th className="p-3 text-[9px] pixel-font uppercase text-right">Size USD</th>
                                        <th className="p-3 text-[9px] pixel-font uppercase text-right">PnL</th>
                                        <th className="p-3 text-[9px] pixel-font uppercase text-center flex justify-center"><Activity size={10} /></th>
                                    </tr>
                                </thead>
                                <tbody className="bg-white">
                                    {Object.values(open_positions).length === 0 ? (
                                        <tr>
                                            <td colSpan="5" className="p-8 text-center text-[10px] italic text-gray-500">No active trades currently.</td>
                                        </tr>
                                    ) : (
                                        Object.values(open_positions).map((pos, i) => (
                                            <tr key={pos.position_id} className={`border-b border-gray-100 ${i % 2 === 0 ? 'bg-gray-50/50' : 'bg-white'} hover:bg-blue-50/50 transition-colors`}>
                                                <td className="p-3">
                                                    <div className="text-xs font-bold text-black">{pos.symbol}</div>
                                                    <div className="text-[7px] text-gray-400 font-mono truncate max-w-[80px]">{pos.token_address}</div>
                                                </td>
                                                <td className="p-3">
                                                    <div className="text-[10px] font-medium font-mono">${parseFloat(pos.entry_price || 0).toLocaleString(undefined, { maximumFractionDigits: 8 })}</div>
                                                </td>
                                                <td className="p-3 text-right">
                                                    <div className="text-[10px] font-bold font-mono">${parseFloat(pos.size_usd || 0).toFixed(4)}</div>
                                                </td>
                                                <td className="p-3 text-right">
                                                    <div className={`text-[10px] font-bold font-mono ${pos.pnl_usd >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                                                        {pos.pnl_usd >= 0 ? '+' : ''}${parseFloat(pos.pnl_usd || 0).toFixed(4)}
                                                    </div>
                                                </td>
                                                <td className="p-3 text-center">
                                                    <div className="w-1.5 h-1.5 rounded-full bg-blue-500 mx-auto animate-pulse"></div>
                                                </td>
                                            </tr>
                                        ))
                                    )}
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>

                {/* Trade History */}
                <div className="w-full lg:w-[400px] flex flex-col gap-4">
                    <div className="flex items-center gap-2 px-2">
                        <History size={16} className="text-gray-600" />
                        <h3 className="text-xs font-bold title-font uppercase tracking-wider">Recent History</h3>
                        {isLoadingHistory && <div className="ml-auto animate-spin h-3 w-3 border-2 border-blue-600 border-t-transparent rounded-full"></div>}
                    </div>

                    <div className="rpg-panel flex-1 bg-white overflow-hidden border-2 border-white border-b-black border-r-black max-h-[500px] overflow-y-auto custom-scrollbar">
                        {closed_trades.length === 0 ? (
                            <div className="p-8 text-center text-[10px] italic text-gray-500">History empty.</div>
                        ) : (
                            <div className="divide-y divide-gray-100">
                                {[...closed_trades].reverse().slice(0, 20).map(trade => (
                                    <div key={trade.position_id} className="p-3 hover:bg-gray-50 transition-colors flex justify-between items-center group">
                                        <div>
                                            <div className="text-[10px] font-bold text-black group-hover:text-blue-600 transition-colors uppercase tracking-tight">{trade.symbol}</div>
                                            <div className="text-[8px] text-gray-400 capitalize">{trade.exit_reason || 'Close'} • {new Date(trade.closed_at).toLocaleDateString()}</div>
                                        </div>
                                        <div className="text-right">
                                            <div className={`text-[10px] font-black font-mono ${trade.pnl_usd >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                                                {trade.pnl_usd >= 0 ? '+' : ''}${parseFloat(trade.pnl_usd || 0).toFixed(4)}
                                            </div>
                                            <div className="text-[7px] text-gray-400 uppercase pixel-font">PnL REALIZED</div>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        )}
                    </div>
                </div>
            </div>

            <style dangerouslySetInnerHTML={{ __html: `
                .custom-scrollbar::-webkit-scrollbar {
                    width: 4px;
                }
                .custom-scrollbar::-webkit-scrollbar-track {
                    background: #f0f0f0;
                }
                .custom-scrollbar::-webkit-scrollbar-thumb {
                    background: #bbb;
                    border-radius: 2px;
                }
            `}} />
        </div>
    );
};
