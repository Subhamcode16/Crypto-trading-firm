import React from 'react';
import { useAgentStore } from '../stores/useAgentStore';
import { useTradeStore } from '../stores/useTradeStore';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, BarChart, Bar, AreaChart, Area } from 'recharts';

// Mock data generator for PnL chart (We'll use actual stores later, testing layout first)
const mockChartData = Array.from({ length: 24 }).map((_, i) => ({
    time: `${i}:00`,
    pnl: 10000 + Math.random() * 5000 + (i * 200),
}));

export const StatsDashboard = () => {
    const agentsMap = useAgentStore((state) => state.agents);
    const agents = Object.values(agentsMap);

    // In future phases, these will be wired up to actual aggregated data
    const globalStats = {
        totalPnl: '+$42,504.00',
        winRate: '68%',
        activeTrades: 12,
        totalSignals: 145
    };

    return (
        <div className="w-full h-full pt-20 px-6 pb-6 overflow-y-auto hide-scrollbar">
            <div className="max-w-7xl mx-auto space-y-6">

                {/* Header Title */}
                <div className="rpg-panel p-4 flex justify-between items-center">
                    <div>
                        <h1 className="text-2xl font-bold title-font tracking-wide text-green-400">FIRM PERFORMANCE</h1>
                        <p className="text-xs font-bold pixel-font text-green-700 mt-1">GLOBAL TRADING STATISTICS</p>
                    </div>
                </div>

                {/* KPI Grid */}
                <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                    <div className="rpg-panel p-4 flex flex-col items-center justify-center border-l-4 border-l-green-500">
                        <span className="text-[10px] uppercase font-bold pixel-font text-gray-500 mb-2">TOTAL PNL</span>
                        <span className="text-2xl font-bold title-font text-green-400">{globalStats.totalPnl}</span>
                    </div>
                    <div className="rpg-panel p-4 flex flex-col items-center justify-center border-l-4 border-l-blue-500">
                        <span className="text-[10px] uppercase font-bold pixel-font text-gray-500 mb-2">WIN RATE</span>
                        <span className="text-2xl font-bold title-font text-blue-400">{globalStats.winRate}</span>
                    </div>
                    <div className="rpg-panel p-4 flex flex-col items-center justify-center border-l-4 border-l-orange-500">
                        <span className="text-[10px] uppercase font-bold pixel-font text-gray-500 mb-2">ACTIVE TRADES</span>
                        <span className="text-2xl font-bold title-font text-orange-400">{globalStats.activeTrades}</span>
                    </div>
                    <div className="rpg-panel p-4 flex flex-col items-center justify-center border-l-4 border-l-purple-500">
                        <span className="text-[10px] uppercase font-bold pixel-font text-gray-500 mb-2">SIGNALS GENERATED</span>
                        <span className="text-2xl font-bold title-font text-white">{globalStats.totalSignals}</span>
                    </div>
                </div>

                {/* Chart Section */}
                <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                    <div className="lg:col-span-2 rpg-panel p-4">
                        <h2 className="text-sm font-bold title-font mb-4 border-b-2 border-black pb-2">PNL OVER TIME</h2>
                        <div className="h-64 cursor-crosshair relative w-full overflow-hidden">
                            <ResponsiveContainer width="99%" height="100%">
                                <AreaChart data={mockChartData} margin={{ top: 5, right: 0, left: -20, bottom: 0 }}>
                                    <defs>
                                        <linearGradient id="colorPnl" x1="0" y1="0" x2="0" y2="1">
                                            <stop offset="5%" stopColor="#4ade80" stopOpacity={0.5} />
                                            <stop offset="95%" stopColor="#4ade80" stopOpacity={0} />
                                        </linearGradient>
                                    </defs>
                                    <CartesianGrid strokeDasharray="3 3" stroke="#333" />
                                    <XAxis dataKey="time" tick={{ fontSize: 10, fontFamily: 'monospace' }} />
                                    <YAxis tick={{ fontSize: 10, fontFamily: 'monospace' }} />
                                    <Tooltip
                                        contentStyle={{ backgroundColor: '#fff', border: '2px solid black', borderRadius: '4px', fontFamily: '"Press Start 2P"', fontSize: '8px' }}
                                    />
                                    <Area type="monotone" dataKey="pnl" stroke="#22c55e" strokeWidth={3} fillOpacity={1} fill="url(#colorPnl)" />
                                </AreaChart>
                            </ResponsiveContainer>
                        </div>
                    </div>

                    <div className="rpg-panel p-4">
                        <h2 className="text-sm font-bold title-font mb-4 border-b-2 border-black pb-2">AGENT DISTRIBUTION</h2>
                        <div className="h-64 relative w-full overflow-hidden">
                            <ResponsiveContainer width="99%" height="100%">
                                <BarChart data={[
                                    { name: 'Signals', value: 85 },
                                    { name: 'Verified', value: 45 },
                                    { name: 'Executed', value: 32 },
                                    { name: 'Profitable', value: 22 }
                                ]} layout="vertical" margin={{ top: 5, right: 20, left: 10, bottom: 5 }}>
                                    <XAxis type="number" hide />
                                    <YAxis dataKey="name" type="category" width={80} tick={{ fontSize: 8, fontFamily: 'monospace' }} />
                                    <Bar dataKey="value" fill="#3b82f6" radius={[0, 4, 4, 0]} barSize={20} />
                                </BarChart>
                            </ResponsiveContainer>
                        </div>
                    </div>
                </div>

                {/* Agent Roster Table */}
                <div className="rpg-panel p-4 overflow-x-auto">
                    <h2 className="text-sm font-bold title-font mb-4 border-b-2 border-black pb-2">AGENT ROSTER</h2>
                    <table className="w-full text-left min-w-[700px]">
                        <thead>
                            <tr className="border-b-2 border-gray-300">
                                <th className="py-2 text-[10px] font-bold uppercase pixel-font tracking-wider">Agent</th>
                                <th className="py-2 text-[10px] font-bold uppercase pixel-font tracking-wider">Floor / Role</th>
                                <th className="py-2 text-[10px] font-bold uppercase pixel-font tracking-wider">Status</th>
                                <th className="py-2 text-[10px] font-bold uppercase pixel-font tracking-wider text-right">Activity Level</th>
                            </tr>
                        </thead>
                        <tbody>
                            {agents.map((agent) => (
                                <tr key={agent.id} className="border-b border-[#333] hover:bg-[#1a1a1a] transition-colors">
                                    <td className="py-3">
                                        <div className="flex items-center gap-2">
                                            <div className={`w-2 h-2 rounded-full border border-black shadow-[inset_1px_1px_2px_rgba(255,255,255,0.5)] ${agent.is_online ? 'bg-green-400' : 'bg-red-500'}`}></div>
                                            <span className="font-bold title-font">{agent.name}</span>
                                        </div>
                                    </td>
                                    <td className="py-3">
                                        <span className="text-xs font-bold pixel-font text-gray-600 uppercase">FLR {agent.floor}</span>
                                    </td>
                                    <td className="py-3">
                                        <div className="inline-block px-2 py-1 bg-black border border-[#333] rounded shadow-sm">
                                            <span className={`text-[8px] uppercase pixel-font tracking-wider ${agent.status === 'IDLE' ? 'text-gray-500' :
                                                agent.status === 'ERROR' ? 'text-red-500' :
                                                    'text-blue-400'
                                                }`}>
                                                {agent.status}
                                            </span>
                                        </div>
                                    </td>
                                    <td className="py-3 text-right">
                                        <div className="w-full bg-black rounded-full h-1.5 border border-[#444] overflow-hidden">
                                            <div className="bg-blue-500 h-1.5" style={{ width: `${Math.random() * 60 + 20}%` }}></div>
                                        </div>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>

            </div>
        </div>
    );
};
