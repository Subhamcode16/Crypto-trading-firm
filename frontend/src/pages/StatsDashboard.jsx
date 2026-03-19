import React from 'react';
import { useAgentStore } from '../stores/useAgentStore';
import { useTradeStore } from '../stores/useTradeStore';
import { useInsightStore } from '../stores/useInsightStore';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, BarChart, Bar, AreaChart, Area } from 'recharts';

// Mock data generator for PnL chart 
const mockChartData = Array.from({ length: 24 }).map((_, i) => ({
    time: `${i}:00`,
    pnl: 10000 + Math.random() * 5000 + (i * 200),
}));

export const StatsDashboard = () => {
    const agentsMap = useAgentStore((state) => state.agents);
    const agents = Object.values(agentsMap);
    const { open_positions, closed_trades } = useTradeStore();
    const { news, pipeline, lastSync } = useInsightStore();

    // Calculate real stats from the trade history
    const allTrades = [...Object.values(open_positions), ...closed_trades];
    const totalPnl = allTrades.reduce((sum, trade) => sum + (trade.pnl_usd || 0), 0);
    const winningTrades = closed_trades.filter(t => (t.pnl_usd || 0) > 0).length;
    const totalClosed = closed_trades.length;
    const winRate = totalClosed > 0 ? Math.round((winningTrades / totalClosed) * 100) : 0;

    const kpiStats = [
        { label: 'TOTAL PNL', value: `${totalPnl >= 0 ? '+' : '-'}$${Math.abs(totalPnl).toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}`, color: 'text-emerald-700', border: 'border-l-emerald-600' },
        { label: 'WIN RATE', value: `${winRate}%`, color: 'text-blue-700', border: 'border-l-blue-600' },
        { label: 'ACTIVE EXECUTIONS', value: Object.keys(open_positions).length, color: 'text-orange-700', border: 'border-l-orange-600' },
        { label: 'LIFETIME SIGNALS', value: allTrades.length, color: 'text-purple-700', border: 'border-l-purple-600' }
    ];

    return (
        <div className="w-full h-full pt-16 px-4 pb-6 overflow-y-auto bg-[#8b9bb4] text-black hide-scrollbar">
            <div className="max-w-[1600px] mx-auto">
                
                {/* Header Title with animated glow */}
                <div className="flex justify-between items-center mb-6 px-2">
                    <div className="relative">
                        <h1 className="text-3xl font-black title-font tracking-tighter text-black">
                            FIRM <span className="text-emerald-700">INSIGHTS</span>
                        </h1>
                        <div className="h-1.5 w-32 bg-emerald-700 mt-1"></div>
                    </div>
                    <div className="text-right">
                        <p className="text-[10px] font-bold pixel-font text-emerald-800 uppercase">System Status: Optimal</p>
                        <p className="text-[8px] pixel-font text-gray-700 mt-1">Sync: {lastSync || 'Initializing...'}</p>
                    </div>
                </div>

                {/* MAIN BENTO GRID */}
                <div className="grid grid-cols-1 md:grid-cols-12 gap-4 auto-rows-auto">
                    
                    {/* KPI CARDS - Top Row */}
                    {kpiStats.map((stat, i) => (
                        <div key={i} className={`md:col-span-3 rpg-panel p-4 border-2 border-black ${stat.border} hover:scale-[1.02] transition-transform cursor-default group`}>
                            <p className="text-[9px] font-bold pixel-font text-gray-800 mb-2 group-hover:text-black transition-colors">{stat.label}</p>
                            <p className={`text-2xl font-black title-font ${stat.color}`}>{stat.value}</p>
                            <div className="mt-2 text-[7px] pixel-font text-gray-500 italic">LIVE_FEED_SYNCED</div>
                        </div>
                    ))}

                    {/* PNL CHART - Major Tile */}
                    <div className="md:col-span-8 md:row-span-2 rpg-panel p-6 border-2 border-black flex flex-col min-h-[400px]">
                        <div className="flex justify-between items-center mb-6">
                            <h2 className="text-sm font-bold title-font text-black border-l-4 border-emerald-700 pl-3 uppercase">Equity Growth</h2>
                            <div className="flex gap-2">
                                <span className="px-2 py-1 bg-green-500/10 border border-green-500/20 text-[8px] pixel-font text-green-500">24H</span>
                                <span className="px-2 py-1 bg-white/5 border border-white/10 text-[8px] pixel-font text-gray-500 hover:text-white transition-colors cursor-pointer">7D</span>
                            </div>
                        </div>
                        <div className="flex-1 w-full">
                            <ResponsiveContainer width="100%" height="100%">
                                <AreaChart data={mockChartData} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
                                    <defs>
                                        <linearGradient id="chartGradient" x1="0" y1="0" x2="0" y2="1">
                                            <stop offset="5%" stopColor="#22c55e" stopOpacity={0.3} />
                                            <stop offset="95%" stopColor="#22c55e" stopOpacity={0} />
                                        </linearGradient>
                                    </defs>
                                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(0,0,0,0.1)" vertical={false} />
                                    <XAxis dataKey="time" axisLine={false} tickLine={false} tick={{ fontSize: 9, fill: '#333', fontFamily: 'monospace', fontWeight: 'bold' }} />
                                    <YAxis axisLine={false} tickLine={false} tick={{ fontSize: 9, fill: '#333', fontFamily: 'monospace', fontWeight: 'bold' }} />
                                    <Tooltip
                                        contentStyle={{ backgroundColor: '#000', border: '1px solid #333', borderRadius: '4px', fontFamily: '"Press Start 2P"', fontSize: '7px' }}
                                        itemStyle={{ color: '#22c55e' }}
                                    />
                                    <Area type="monotone" dataKey="pnl" stroke="#22c55e" strokeWidth={3} fill="url(#chartGradient)" />
                                </AreaChart>
                            </ResponsiveContainer>
                        </div>
                    </div>

                    {/* NEWS PANEL - Right Spanning Tile */}
                    <div className="md:col-span-4 md:row-span-4 rpg-panel flex flex-col max-h-[816px]">
                        <div className="p-4 border-b border-black/10 flex justify-between items-center">
                            <h2 className="text-xs font-bold title-font text-blue-800">GLOBAL INTEL FEED</h2>
                            <div className="flex items-center gap-2">
                                <span className="w-1.5 h-1.5 bg-cyan-500 rounded-full animate-pulse"></span>
                                <span className="text-[8px] pixel-font text-gray-500">LIVE</span>
                            </div>
                        </div>
                        <div className="flex-1 overflow-y-auto p-4 space-y-4 custom-scrollbar">
                            {news.map((item) => (
                                <div key={item.id} className="group border-l-2 border-white/10 pl-3 py-1 hover:border-cyan-500/50 transition-colors">
                                    <div className="flex justify-between items-center mb-1">
                                        <span className={`text-[7px] font-bold pixel-font px-1 py-0.5 rounded-sm border ${
                                            item.importance === 'URGENT' ? 'bg-red-100 text-red-800 border-red-200' :
                                            item.importance === 'HIGH' ? 'bg-amber-100 text-amber-800 border-amber-200' :
                                            'bg-blue-100 text-blue-800 border-blue-200'
                                        }`}>
                                            [{item.type}] {item.source}
                                        </span>
                                        <span className="text-[8px] pixel-font text-gray-800">{item.timestamp}</span>
                                    </div>
                                    <p className="text-[10px] leading-relaxed text-black font-bold group-hover:text-blue-900 transition-colors uppercase tracking-tight">{item.title}</p>
                                </div>
                            ))}
                        </div>
                        <div className="p-3 border-t border-white/10 bg-black/30">
                            <p className="text-[8px] pixel-font text-cyan-800 text-center">SCANNING GLOBAL CHANNELS...</p>
                        </div>
                    </div>

                    {/* PIPELINE TRANSPARENCY - Bottom Left Tile */}
                    <div className="md:col-span-4 md:row-span-2 rpg-panel flex flex-col p-5 border-2 border-black">
                        <div className="flex justify-between items-center mb-4">
                            <h2 className="text-xs font-bold title-font text-purple-800 uppercase tracking-widest">Pipeline Efficiency</h2>
                            <div className="flex items-center gap-1">
                                <span className="w-1.5 h-1.5 bg-purple-700 rounded-full animate-ping"></span>
                                <span className="text-[7px] pixel-font text-purple-900 font-bold">SYNC</span>
                            </div>
                        </div>
                        <div className="flex-1 flex flex-col justify-center space-y-6">
                            <div className="space-y-2">
                                <div className="flex justify-between items-end">
                                    <span className="text-[9px] pixel-font text-gray-700 font-bold">TOKENS_FOUND</span>
                                    <span className="text-sm font-bold title-font text-black">{pipeline.found}</span>
                                </div>
                                <div className="h-2 w-full bg-white rounded-full overflow-hidden border-2 border-black">
                                    <div className="h-full bg-purple-600" style={{ width: pipeline.found > 0 ? '100%' : '0%' }}></div>
                                </div>
                            </div>
                            <div className="grid grid-cols-2 gap-4">
                                <div className="space-y-2 border-l-4 border-emerald-700 pl-3">
                                    <p className="text-[8px] pixel-font text-gray-800 font-bold">PASSED</p>
                                    <p className="text-xl font-bold title-font text-emerald-800">{pipeline.passed}</p>
                                    <p className="text-[7px] pixel-font text-emerald-900 font-bold">CONV: {pipeline.conversion_rate}</p>
                                </div>
                                <div className="space-y-2 border-l-4 border-red-700 pl-3">
                                    <p className="text-[8px] pixel-font text-gray-800 font-bold">DROPPED</p>
                                    <p className="text-xl font-bold title-font text-red-800">{pipeline.dropped}</p>
                                    <p className="text-[7px] pixel-font text-red-900 font-bold">FAIL: {100 - parseFloat(pipeline.conversion_rate || 0)}%</p>
                                </div>
                            </div>
                        </div>
                    </div>

                    {/* AGENT DISTRIBUTION - Bottom Center Tile */}
                    <div className="md:col-span-4 md:row-span-2 rpg-panel p-5 border-2 border-black">
                        <h2 className="text-xs font-bold title-font mb-4 text-blue-800 uppercase tracking-widest">Workflow Load</h2>
                        <div className="h-40 w-full">
                            <ResponsiveContainer width="100%" height="100%">
                                <BarChart data={[
                                    { name: 'SCTR', value: 85 },
                                    { name: 'VRFY', value: 45 },
                                    { name: 'EXEC', value: 32 },
                                    { name: 'PRFT', value: 22 }
                                ]} margin={{ top: 0, right: 10, left: -20, bottom: 0 }}>
                                    <XAxis dataKey="name" axisLine={false} tickLine={false} tick={{ fontSize: 8, fill: '#000', fontFamily: 'monospace', fontWeight: 'bold' }} />
                                    <Tooltip contentStyle={{ backgroundColor: '#fff', border: '2px solid #000', fontSize: '7px', color: '#000' }} />
                                    <Bar dataKey="value" fill="#1e40af" radius={[4, 4, 0, 0]} barSize={35} />
                                </BarChart>
                            </ResponsiveContainer>
                        </div>
                        <p className="text-[8px] pixel-font text-blue-900 font-bold text-center mt-2">AGENT CLUSTER STIMULATION: 42%</p>
                    </div>

                    {/* AGENT ROSTER - Wide Tile */}
                    <div className="md:col-span-12 rpg-panel p-6 border-2 border-black">
                        <h2 className="text-xs font-bold title-font mb-6 text-black border-l-4 border-blue-700 pl-3 uppercase">Resource Allocation</h2>
                        <div className="overflow-x-auto">
                            <table className="w-full text-left min-w-[700px]">
                                <thead>
                                    <tr className="border-b border-white/10">
                                        <th className="pb-3 text-[9px] font-bold uppercase pixel-font text-black">ID / Agent Name</th>
                                        <th className="pb-3 text-[9px] font-bold uppercase pixel-font text-black">Module Floor</th>
                                        <th className="pb-3 text-[9px] font-bold uppercase pixel-font text-black">Operation Mode</th>
                                        <th className="pb-3 text-[9px] font-bold uppercase pixel-font text-black text-right">System Load</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {agents.map((agent) => (
                                        <tr key={agent.id} className="border-b border-white/5 hover:bg-white/5 transition-colors group">
                                            <td className="py-4">
                                                <div className="flex items-center gap-3">
                                                    <div className={`w-2 h-2 rounded-full border border-black/40 shadow-[0_0_8px] ${agent.is_online ? 'bg-green-400 shadow-green-500/50' : 'bg-red-500 shadow-red-500/50'}`}></div>
                                                    <span className="font-bold text-[11px] title-font text-black">{agent.name}</span>
                                                </div>
                                            </td>
                                            <td className="py-4">
                                                <span className="text-[10px] font-bold pixel-font text-black uppercase">LVL_0{agent.floor}</span>
                                            </td>
                                            <td className="py-4">
                                                <span className={`text-[9px] uppercase pixel-font tracking-wider px-2 py-1 rounded-sm bg-black/40 border border-white/5 ${
                                                    agent.status === 'IDLE' ? 'text-gray-300' :
                                                    agent.status === 'ERROR' ? 'text-red-500' :
                                                    'text-cyan-400'
                                                }`}>
                                                    {agent.status}
                                                </span>
                                            </td>
                                            <td className="py-4 text-right">
                                                <div className="flex items-center justify-end gap-3">
                                                    <div className="w-24 bg-black/50 rounded-full h-1 border border-white/5 overflow-hidden">
                                                        <div className="bg-cyan-500 h-full" style={{ width: `${Math.random() * 60 + 20}%` }}></div>
                                                    </div>
                                                    <span className="text-[8px] pixel-font text-black font-bold">OPTIMAL</span>
                                                </div>
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    </div>

                    {/* TRADE HISTORY - Wide Tile */}
                    <div className="md:col-span-12">
                        <TradeHistoryTable />
                    </div>

                </div>
            </div>
        </div>
    );
};

const TradeHistoryTable = () => {
    const { open_positions, closed_trades, fetchTradeHistory, isLoadingHistory } = useTradeStore();
    const { lastSync } = useInsightStore();
    const API_KEY = "test_admin_key_123"; 

    React.useEffect(() => {
        fetchTradeHistory("default_user", API_KEY);
        const interval = setInterval(() => {
            fetchTradeHistory("default_user", API_KEY);
        }, 30000);
        return () => clearInterval(interval);
    }, [fetchTradeHistory]);

    const allTrades = [
        ...Object.values(open_positions).map(p => ({ ...p, is_active: true })),
        ...closed_trades.map(p => ({ ...p, is_active: false }))
    ].sort((a, b) => new Date(b.opened_at || b.created_at || Date.now()) - new Date(a.opened_at || a.created_at || Date.now()));

    return (
        <div className="rpg-panel p-6 border-2 border-black relative mt-4">
            <div className="flex justify-between items-center mb-6 border-b-4 border-black pb-4">
                <div className="flex items-center gap-3">
                    <h2 className="text-sm font-bold title-font text-black uppercase tracking-wider">Historical Operations</h2>
                    <span className="text-[10px] pixel-font text-gray-800 bg-white border-2 border-black px-2 py-1 rounded font-bold">LOG_LEN: {allTrades.length}</span>
                </div>
                <button 
                    onClick={() => fetchTradeHistory("default_user", API_KEY)}
                    disabled={isLoadingHistory}
                    className="rpg-button px-4 py-2 text-[9px] pixel-font transition-all disabled:opacity-50 flex items-center gap-2"
                >
                    {isLoadingHistory ? <span className="animate-spin text-xs">↻</span> : '⟳'} SYNC_DB
                </button>
            </div>
            
            <div className="overflow-x-auto">
                <table className="w-full text-left min-w-[900px]">
                    <thead>
                        <tr className="border-b border-white/10 uppercase">
                            <th className="pb-3 text-[9px] font-bold pixel-font text-gray-500">ID / Time</th>
                            <th className="pb-3 text-[9px] font-bold pixel-font text-gray-500">Asset</th>
                            <th className="pb-3 text-[9px] font-bold pixel-font text-gray-500">Operation</th>
                            <th className="pb-3 text-[9px] font-bold pixel-font text-gray-500 text-right">Launch</th>
                            <th className="pb-3 text-[9px] font-bold pixel-font text-gray-500 text-right">Target</th>
                            <th className="pb-3 text-[9px] font-bold pixel-font text-gray-500 text-right">Delta</th>
                            <th className="pb-3 text-[9px] font-bold pixel-font text-gray-500 text-center">Status</th>
                        </tr>
                    </thead>
                    <tbody>
                        {allTrades.length === 0 ? (
                            <tr>
                                <td colSpan="7" className="py-12 text-center text-gray-600 font-bold pixel-font text-[10px] uppercase tracking-widest">
                                    [ No Active Operations Found in Archive ]
                                </td>
                            </tr>
                        ) : (
                            allTrades.map((trade, idx) => {
                                const pnlStr = trade.pnl_usd !== undefined ? `$${Math.abs(trade.pnl_usd).toFixed(2)}` : '$0.00';
                                const isProfit = trade.pnl_usd >= 0;
                                const isBuy = trade.action?.toUpperCase() === 'BUY';
                                const timeStr = trade.opened_at || trade.created_at;
                                const dateObj = timeStr ? new Date(timeStr) : new Date();
                                const displayTime = dateObj.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });

                                return (
                                    <tr key={trade.position_id || idx} className={`border-b border-white/5 hover:bg-white/5 transition-colors ${trade.is_active ? 'bg-blue-500/5' : ''}`}>
                                        <td className="py-4">
                                            <div className="flex flex-col">
                                                <span className="text-[10px] font-mono text-gray-400">{displayTime}</span>
                                                <span className="text-[7px] text-gray-600 font-mono">TX_00{idx+1}</span>
                                            </div>
                                        </td>
                                        <td className="py-4">
                                            <span className="font-bold text-xs title-font text-white">{trade.token}</span>
                                        </td>
                                        <td className="py-4">
                                            <span className={`text-[8px] font-bold pixel-font tracking-wider px-2 py-1 rounded-sm border ${
                                                isBuy ? 'bg-green-500/10 text-green-400 border-green-500/20' : 'bg-red-500/10 text-red-400 border-red-500/20'
                                            }`}>
                                                {trade.action || 'BUY'}
                                            </span>
                                        </td>
                                        <td className="py-4 text-right font-mono text-[11px] text-gray-300">
                                            ${trade.entry_price?.toFixed(6) || '---'}
                                        </td>
                                        <td className="py-4 text-right font-mono text-[11px] text-gray-300">
                                            ${trade.current_price?.toFixed(6) || trade.exit_price?.toFixed(6) || '---'}
                                        </td>
                                        <td className={`py-4 text-right font-bold title-font text-sm ${isProfit ? 'text-green-500' : 'text-red-500'}`}>
                                            {isProfit ? '▲' : '▼'}{pnlStr}
                                        </td>
                                        <td className="py-4 text-center">
                                            <span className={`text-[8px] uppercase pixel-font tracking-wider px-2 py-1 rounded bg-black/50 border border-white/5 shadow-sm ${
                                                trade.status === 'OPEN' ? 'text-blue-400 shadow-blue-500/20' :
                                                trade.status === 'PARTIAL' ? 'text-yellow-400 shadow-yellow-500/20' :
                                                'text-gray-500'
                                            }`}>
                                                {trade.status || (trade.is_active ? 'OPEN' : 'CLOSED')}
                                            </span>
                                        </td>
                                    </tr>
                                );
                            })
                        )}
                    </tbody>
                </table>
            </div>
        </div>
    );
};
