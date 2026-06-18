import React, { useEffect, useState, useRef } from 'react';
import CatchemSimulator from '../components/Springfield/CatchemSimulator';

export function MissionDashboard() {
  const [status, setStatus] = useState(null);
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(true);
  const terminalRef = useRef(null);

  const fetchStatus = async () => {
    try {
      const res = await fetch('http://localhost:8001/api/agent/status');
      if (res.ok) {
        const data = await res.json();
        setStatus(data);
      }
    } catch (e) {
      console.error("Failed to fetch agent status", e);
    }
  };

  const fetchHistory = async () => {
    try {
      const res = await fetch('http://localhost:8001/api/agent/history');
      if (res.ok) {
        const data = await res.json();
        setHistory(data.history || []);
      }
    } catch (e) {
      console.error("Failed to fetch agent history", e);
    }
  };

  useEffect(() => {
    const init = async () => {
      await fetchStatus();
      await fetchHistory();
      setLoading(false);
    };
    init();
    
    // Poll every 10 seconds since it's "live"
    const interval = setInterval(() => {
      fetchStatus();
      fetchHistory();
    }, 10000);
    
    return () => clearInterval(interval);
  }, []);

  // Auto-scroll terminal
  useEffect(() => {
    if (terminalRef.current) {
      terminalRef.current.scrollTop = terminalRef.current.scrollHeight;
    }
  }, [history]);

  if (loading) {
    return (
      <div className="w-full h-full pt-[72px] flex items-center justify-center bg-springfield-bg">
        <div className="text-white font-comic text-3xl animate-pulse tracking-widest uppercase">Initializing the Professor's Lab...</div>
      </div>
    );
  }

  if (!status) {
    return (
      <div className="w-full h-full pt-[72px] flex items-center justify-center bg-springfield-bg">
        <div className="text-burns-red font-comic text-2xl uppercase border-4 border-black bg-white p-4 shadow-comic">Lab is Offline. Start the backend.</div>
      </div>
    );
  }

  const gamification = status.gamification || {
    winning_trades: 0,
    losing_trades: 0,
    total_trades: 0,
    virtual_balance: 0,
    starting_balance: 0,
    level: 1,
    xp: 0,
    status: 'UNKNOWN'
  };
  const target_trades = status.target_trades || 0;
  const progress_pct = status.progress_pct || 0;
  const active_positions = status.active_positions || [];
  
  const totalNetPnl = history.filter(h => h.type === 'SELL').reduce((acc, log) => acc + (log.pnl || 0), 0);

  return (
    <div className="w-full h-full pt-[72px] pb-32 bg-springfield-bg text-black px-6 overflow-y-auto custom-scrollbar">
      <div className="max-w-6xl mx-auto space-y-6">
        
        {/* Mission Header */}
        <div className="comic-panel p-6 bg-white flex flex-col md:flex-row justify-between items-center gap-4">
          <div className="flex-1">
            <h1 className="text-3xl font-comic text-radioactive-green uppercase mb-2 drop-shadow-[2px_2px_0px_rgba(0,0,0,1)]">MISSION: PROFESSOR'S ALGORITHM</h1>
            <p className="text-black font-mono font-bold text-sm">Target: Execute {target_trades} Profitable Trades. "It's mathematically un-un-profitable, with the glavin and the hoiven!"</p>
            
            <div className="w-full bg-gray-200 border-4 border-black h-6 mt-4 overflow-hidden shadow-comic-sm">
              <div className="bg-lisa-blue border-r-4 border-black h-full transition-all duration-1000" style={{ width: `${progress_pct}%` }}></div>
            </div>
            <div className="flex justify-between font-comic uppercase font-bold text-sm text-black mt-1">
              <span>0 Trades</span>
              <span>{gamification.winning_trades || 0} / {target_trades || 0} Wins ({(progress_pct || 0).toFixed(1)}%)</span>
            </div>
          </div>
          <div className="w-32 hidden md:block">
            {/* Frink decorative space */}
          </div>
        </div>

        {/* Stats Grid */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
          <div className="comic-panel p-4 flex flex-col items-center justify-center bg-white text-center">
            <span className="text-black text-sm font-comic tracking-widest uppercase mb-1 border-b-2 border-black w-full pb-1">Virtual Vault</span>
            <span className={`text-4xl font-comic ${(gamification.virtual_balance || 0) >= (gamification.starting_balance || 0) ? 'text-radioactive-green' : 'text-burns-red'} drop-shadow-[2px_2px_0px_rgba(0,0,0,1)]`}>
              ${(gamification.virtual_balance || 0).toFixed(2)}
            </span>
          </div>
          
          <div className="comic-panel p-4 flex flex-col items-center justify-center bg-white text-center">
            <span className="text-black text-sm font-comic tracking-widest uppercase mb-1 border-b-2 border-black w-full pb-1">Frink Level</span>
            <span className="text-4xl font-comic text-springfield-yellow drop-shadow-[2px_2px_0px_rgba(0,0,0,1)]">
              Lvl {gamification.level || 1}
            </span>
            <span className="text-xs font-mono font-bold mt-1 bg-black text-white px-2 uppercase">{gamification.xp || 0} XP</span>
          </div>

          <div className="comic-panel p-4 flex flex-col items-center justify-center bg-white text-center">
            <span className="text-black text-sm font-comic tracking-widest uppercase mb-1 border-b-2 border-black w-full pb-1">Win / Loss</span>
            <span className="text-4xl font-comic text-lisa-blue drop-shadow-[2px_2px_0px_rgba(0,0,0,1)]">
              {gamification.winning_trades || 0} <span className="text-black">/</span> {gamification.losing_trades || 0}
            </span>
            <span className="text-xs font-mono font-bold mt-1 bg-black text-white px-2 uppercase">{gamification.total_trades || 0} Trades</span>
          </div>

          <div className="comic-panel p-4 flex flex-col items-center justify-center bg-white text-center">
            <span className="text-black text-sm font-comic tracking-widest uppercase mb-1 border-b-2 border-black w-full pb-1">Agent Status</span>
            <div className="flex items-center gap-2 mt-2 border-4 border-black p-2 bg-gray-100 shadow-comic-sm">
              <div className={`w-4 h-4 border-2 border-black ${gamification.status === 'ACTIVE' ? 'bg-radioactive-green animate-pulse' : gamification.status === 'ANALYZING' ? 'bg-springfield-yellow' : 'bg-lisa-blue'}`}></div>
              <span className="text-lg font-comic uppercase font-bold text-black">{gamification.status}</span>
            </div>
          </div>
        </div>


        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Active Positions */}
          <div className="comic-panel bg-white overflow-hidden flex flex-col h-96">
            <div className="p-3 border-b-4 border-black bg-springfield-yellow">
              <h2 className="font-comic font-bold text-black tracking-widest uppercase text-lg">Active Experiments (Positions)</h2>
            </div>
            <div className="p-4 flex-1 overflow-y-auto custom-scrollbar">
              {active_positions.length === 0 ? (
                <div className="h-full flex items-center justify-center text-gray-500 font-comic uppercase text-lg border-4 border-dashed border-gray-300 p-4 text-center">
                  NO ACTIVE EXPERIMENTS... THE TANK IS EMPTY, GLAVIN!
                </div>
              ) : (
                <div className="space-y-4">
                  {active_positions.map((pos, idx) => (
                    <div key={idx} className="flex justify-between items-center bg-white p-3 border-4 border-black shadow-comic-sm">
                      <div className="flex items-center gap-3">
                        <div className="w-10 h-10 border-4 border-black bg-springfield-yellow flex items-center justify-center font-comic font-bold text-sm">
                          {pos.symbol.split('/')[0]}
                        </div>
                        <div>
                          <div className="font-comic font-bold text-lg">{pos.symbol}</div>
                          <div className="text-sm font-mono font-bold bg-black text-white px-1 mt-1 inline-block">Price: ${(pos.current_price || 0).toFixed(2)}</div>
                        </div>
                      </div>
                        <div className="text-right">
                        <div className="font-mono font-bold text-xl">{pos.amount.toFixed(4)}</div>
                        <div className="text-sm font-comic font-bold text-gray-700 uppercase">Value: ${(pos.value_usdt || 0).toFixed(2)}</div>
                        <div className={`text-lg font-comic font-bold uppercase [-webkit-text-stroke:1px_black] ${pos.unrealized_pnl >= 0 ? 'text-radioactive-green' : 'text-burns-red'}`}>
                          PnL: {pos.unrealized_pnl >= 0 ? '+' : ''}${(pos.unrealized_pnl || 0).toFixed(2)}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Live Terminal Log */}
          <div className="comic-panel-dark bg-[#111] overflow-hidden flex flex-col h-96">
            <div className="p-3 border-b-4 border-white bg-black flex justify-between items-center text-white">
              <h2 className="font-comic font-bold tracking-widest uppercase text-lg">Frink's Terminal</h2>
              <div className="flex gap-2">
                <div className="w-4 h-4 border-2 border-white bg-burns-red rounded-full"></div>
                <div className="w-4 h-4 border-2 border-white bg-springfield-yellow rounded-full"></div>
                <div className="w-4 h-4 border-2 border-white bg-radioactive-green rounded-full"></div>
              </div>
            </div>
            <div 
              ref={terminalRef}
              className="p-4 flex-1 overflow-y-auto font-mono text-sm space-y-3 custom-scrollbar text-white"
            >
              <div className="text-radioactive-green">{">"} INITIALIZING PROFESSOR'S VIRTUAL TRADING APPARATUS...</div>
              <div className="text-radioactive-green">{">"} TUBES CONNECTED TO YAHOO FINANCE LIVE FEED.</div>
              <div className="text-radioactive-green">{">"} LOADING XGBOOST AND OTHER COMPLICATED ACRONYMS... OK.</div>
              <div className="text-lisa-blue">{">"} AWAITING FINANCIAL ANOMALIES...</div>
              
              {history.map((log, idx) => (
                <div key={idx} className={`border-l-4 pl-2 py-1 ${log.type === 'BUY' ? 'border-springfield-yellow text-springfield-yellow' : log.pnl > 0 ? 'border-radioactive-green text-radioactive-green' : 'border-burns-red text-burns-red'}`}>
                  {`> [${new Date(log.time).toLocaleTimeString()}] ${log.type} ${log.amount ? log.amount.toFixed(4) + ' ' : ''}${log.symbol} @ $${(log.price || 0).toFixed(2)} | Conf: ${((log.confidence || 0) * 100).toFixed(1)}%`}
                  {log.type === 'SELL' && <div className="mt-1 bg-white/10 px-2 py-1 inline-block border border-white/20">{`-> PnL: $${(log.pnl || 0).toFixed(2)} (${((log.pnl_pct || 0) * 100).toFixed(2)}%)`}</div>}
                </div>
              ))}
            </div>
          </div>
        </div>
        
        {/* Catchem Simulator Panel */}
        <div className="mt-6">
            <CatchemSimulator />
        </div>

        {/* Trade History Vault */}
        <div className="comic-panel bg-white overflow-hidden flex flex-col mt-6">
          <div className="p-3 border-b-4 border-black bg-springfield-yellow flex justify-between items-center">
            <h2 className="font-comic font-bold tracking-widest uppercase text-lg text-black">Basement Archives (History)</h2>
            <span className="text-sm font-mono font-bold bg-black text-white px-2 py-1 uppercase">{history.length} Records</span>
          </div>
          <div className="p-0 overflow-x-auto custom-scrollbar max-h-96">
            <table className="w-full text-left font-mono text-sm">
              <thead className="bg-black text-white sticky top-0 border-b-4 border-black z-10 font-comic uppercase tracking-wider text-base">
                <tr>
                  <th className="px-4 py-3 font-normal">Date</th>
                  <th className="px-4 py-3 font-normal">Action</th>
                  <th className="px-4 py-3 font-normal">Symbol</th>
                  <th className="px-4 py-3 font-normal text-right">Price</th>
                  <th className="px-4 py-3 font-normal text-right">Confidence</th>
                  <th className="px-4 py-3 font-normal text-right">PnL</th>
                </tr>
              </thead>
              <tbody className="divide-y-4 divide-black">
                {history.length === 0 ? (
                  <tr>
                    <td colSpan="6" className="px-4 py-8 text-center text-gray-500 font-comic uppercase text-xl">The archives are completely empty.</td>
                  </tr>
                ) : (
                  history.slice().reverse().map((log, idx) => (
                    <tr key={idx} className="hover:bg-gray-100 transition-colors font-bold">
                      <td className="px-4 py-3">{new Date(log.time).toLocaleString()}</td>
                      <td className="px-4 py-3">
                        <span className={`px-2 py-1 border-2 border-black font-comic uppercase shadow-[2px_2px_0px_0px_rgba(0,0,0,1)] ${
                          log.type === 'BUY' ? 'bg-springfield-yellow text-black' :
                          'bg-burns-red text-white'
                        }`}>
                          {log.type}
                        </span>
                      </td>
                      <td className="px-4 py-3 font-comic text-lg uppercase">{log.symbol}</td>
                      <td className="px-4 py-3 text-right">${(log.price || 0).toFixed(2)}</td>
                      <td className="px-4 py-3 text-right text-lisa-blue">{((log.confidence || 0) * 100).toFixed(1)}%</td>
                      <td className={`px-4 py-3 text-right font-comic text-lg drop-shadow-sm ${
                        log.type === 'BUY' ? 'text-gray-500' :
                        (log.pnl || 0) > 0 ? 'text-radioactive-green' : 'text-burns-red'
                      }`}>
                        {log.type === 'BUY' ? '-' : `${(log.pnl || 0) > 0 ? '+' : ''}$${(log.pnl || 0).toFixed(2)} (${((log.pnl_pct || 0) * 100).toFixed(2)}%)`}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>

        {/* Total Net P&L (Small Footer) */}
        <div className="flex justify-end items-center mt-3 px-2 text-sm font-comic bg-white border-4 border-black p-2 shadow-comic-sm max-w-fit ml-auto">
          <span className="text-black mr-3 font-bold tracking-widest uppercase">Total Net P&L:</span>
          <span className={`font-bold text-2xl drop-shadow-[1px_1px_0px_rgba(0,0,0,1)] ${totalNetPnl >= 0 ? 'text-radioactive-green' : 'text-burns-red'}`}>
            {totalNetPnl >= 0 ? '+' : '-'}${Math.abs(totalNetPnl).toFixed(2)}
          </span>
        </div>

      </div>
    </div>
  );
}
