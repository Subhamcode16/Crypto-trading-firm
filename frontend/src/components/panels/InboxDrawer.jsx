import React, { useState, useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { X, Send, Bot, Shield, Zap, Search, MessageSquare, History } from 'lucide-react';
import { useMessageStore } from '../../stores/useMessageStore';
import { useAgentStore } from '../../stores/useAgentStore';

/**
 * InboxDrawer: A premium, glassmorphism slide-over panel
 * designed for real-time transparency of agent-to-agent communication.
 */
export function InboxDrawer() {
    const { messages, isDrawerOpen, setDrawerOpen } = useMessageStore();
    const agents = useAgentStore((state) => state.agents);
    const [selectedAgentId, setSelectedAgentId] = useState('global'); // 'global' or agent ID

    // Grouping: Global pipeline vs per-agent outbox
    const filteredMessages = useMemo(() => {
        if (selectedAgentId === 'global') return messages;
        return messages.filter(m => m.senderId === parseInt(selectedAgentId) || m.receiverId === parseInt(selectedAgentId));
    }, [messages, selectedAgentId]);

    const agentList = Object.values(agents);

    return (
        <AnimatePresence>
            {isDrawerOpen && (
                <>
                    {/* Backdrop */}
                    <motion.div
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        onClick={() => setDrawerOpen(false)}
                        className="fixed inset-0 bg-black/40 backdrop-blur-sm z-[100]"
                    />

                    {/* Drawer Panel */}
                    <motion.div
                        initial={{ x: '100%' }}
                        animate={{ x: 0 }}
                        exit={{ x: '100%' }}
                        transition={{ type: 'spring', damping: 25, stiffness: 200 }}
                        className="fixed right-0 top-0 h-full w-[480px] bg-[#050505]/90 backdrop-blur-2xl border-l border-white/10 z-[101] flex flex-col shadow-[-20px_0_50px_rgba(0,0,0,0.5)]"
                    >
                        {/* Header */}
                        <div className="p-6 border-b border-white/10 flex items-center justify-between">
                            <div className="flex items-center gap-3">
                                <div className="w-10 h-10 rounded-lg bg-emerald-500/20 border border-emerald-500/40 flex items-center justify-center">
                                    <MessageSquare className="text-emerald-400" size={20} />
                                </div>
                                <div>
                                    <h2 className="text-white font-bold tracking-tight text-lg">Agent Pipeline</h2>
                                    <p className="text-white/40 text-[10px] uppercase font-mono tracking-widest">Full Transparency Mode</p>
                                </div>
                            </div>
                            <button
                                onClick={() => setDrawerOpen(false)}
                                className="p-2 hover:bg-white/5 rounded-full transition-colors text-white/40 hover:text-white"
                            >
                                <X size={20} />
                            </button>
                        </div>

                        {/* Content Split: Agent Sidebar + Message Feed */}
                        <div className="flex-1 flex overflow-hidden">
                            {/* Left Navigation: Agent Selector */}
                            <div className="w-16 border-r border-white/5 flex flex-col items-center py-4 gap-4 overflow-y-auto no-scrollbar">
                                <button
                                    onClick={() => setSelectedAgentId('global')}
                                    className={`p-3 rounded-xl transition-all ${selectedAgentId === 'global' ? 'bg-white/10 text-white shadow-[0_0_15px_rgba(255,255,255,0.1)]' : 'text-white/30 hover:text-white/60'}`}
                                    title="Global Pipeline"
                                >
                                    <Zap size={20} />
                                </button>
                                <div className="w-8 h-[1px] bg-white/5" />
                                {agentList.map((agent) => (
                                    <button
                                        key={agent.id}
                                        onClick={() => setSelectedAgentId(agent.id.toString())}
                                        className={`group relative p-3 rounded-xl transition-all ${selectedAgentId === agent.id.toString() ? 'bg-white/10 text-white' : 'text-white/30 hover:text-white/60'}`}
                                        title={agent.name}
                                    >
                                        <div className={`absolute -right-1 -top-1 w-2 h-2 rounded-full border border-black ${agent.status !== 'IDLE' ? 'bg-green-500' : 'bg-gray-600'}`} />
                                        <Bot size={20} />
                                    </button>
                                ))}
                            </div>

                            {/* Right Panel: Message List */}
                            <div className="flex-1 flex flex-col overflow-hidden">
                                <div className="p-4 bg-white/[0.02] text-white/60 text-[10px] font-mono uppercase tracking-widest border-b border-white/5">
                                    {selectedAgentId === 'global' ? 'System-wide Stream' : agents[selectedAgentId]?.name}
                                </div>

                                <div className="flex-1 overflow-y-auto p-6 space-y-6 custom-scrollbar">
                                    {filteredMessages.length === 0 ? (
                                        <div className="h-full flex flex-col items-center justify-center opacity-20">
                                            <History size={48} />
                                            <p className="mt-4 text-xs font-mono">Pipeline quiescent</p>
                                        </div>
                                    ) : (
                                        filteredMessages.map((msg, idx) => (
                                            <div key={msg.id} className="group relative">
                                                <div className="flex items-start gap-4">
                                                    <div className="w-8 h-8 rounded bg-white/5 border border-white/10 flex items-center justify-center text-[10px] font-bold text-white/40 group-hover:border-white/20 transition-colors">
                                                        {msg.senderId ? `AGT-${msg.senderId}` : 'SYS'}
                                                    </div>
                                                    <div className="flex-1 min-w-0">
                                                        <div className="flex items-center gap-2 mb-1">
                                                            <span className="text-[10px] font-mono text-white/30">{new Date(msg.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                                                            {msg.receiverId && (
                                                                <>
                                                                    <div className="w-2 h-[1px] bg-white/20" />
                                                                    <span className="text-[10px] font-mono font-bold text-emerald-400">TO AGT-{msg.receiverId}</span>
                                                                </>
                                                            )}
                                                        </div>
                                                        <div className="p-3 rounded-lg bg-white/[0.03] border border-white/5 group-hover:bg-white/[0.05] transition-all">
                                                            <p className="text-sm text-white/80 leading-relaxed font-inter">
                                                                {msg.content}
                                                            </p>
                                                        </div>
                                                    </div>
                                                </div>
                                            </div>
                                        ))
                                    )}
                                </div>

                                {/* Footer / Input Simulation */}
                                <div className="p-6 bg-white/[0.02] border-t border-white/10">
                                    <div className="flex items-center gap-3 opacity-30 cursor-not-allowed">
                                        <div className="flex-1 bg-white/5 border border-white/10 rounded-lg px-4 py-2 text-xs text-white/40">
                                            Direct Command Entry Disabled (System Only)
                                        </div>
                                        <button className="p-2 bg-white/5 rounded-lg">
                                            <Send size={16} className="text-white/20" />
                                        </button>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </motion.div>
                </>
            )}
        </AnimatePresence>
    );
}
