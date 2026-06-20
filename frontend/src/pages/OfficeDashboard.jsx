import React, { useEffect, useState, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { Gamepad2, BrainCircuit, Activity, Wallet, Target, Network, KeyRound, LogOut, Terminal as TerminalIcon } from 'lucide-react';
import gsap from 'gsap';
import { useGSAP } from '@gsap/react';
import SimpsonBarometer from '../components/Springfield/SimpsonBarometer';
import SectorIndicators from '../components/Springfield/SectorIndicators';
import { AgentAssistant } from '../components/panels/AgentAssistant';

export function OfficeDashboard() {
  const navigate = useNavigate();
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Connection Form State
  const [apiKey, setApiKey] = useState('');
  const [apiSecret, setApiSecret] = useState('');
  const [isTestnet, setIsTestnet] = useState(true);
  const [connecting, setConnecting] = useState(false);

  const vaultRef = useRef(null);
  
  useGSAP(() => {
    if (status?.status === "WAITING_FOR_CREDENTIALS" && vaultRef.current) {
      gsap.from(vaultRef.current, {
        y: -50,
        opacity: 0,
        duration: 0.8,
        ease: "bounce.out"
      });
    }
  }, [status?.status]);
  const fetchStatus = async () => {
    try {
      const res = await fetch('http://localhost:8001/api/agent/status');
      if (res.ok) {
        const data = await res.json();
        setStatus(data);
      } else {
        throw new Error('Failed to fetch status');
      }
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchStatus();
    const interval = setInterval(fetchStatus, 10000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    if (status?.status === 'WAITING_FOR_CREDENTIALS') {
      setTimeout(() => {
        window.dispatchEvent(new CustomEvent('agent-speak', { detail: "Excellent... Bybit keys required." }));
      }, 1000);
    } else if (status?.status) {
      setTimeout(() => {
        window.dispatchEvent(new CustomEvent('agent-speak', { detail: "Monitoring the markets for optimal avarice." }));
      }, 1000);
    }
  }, [status?.status]);

  const handleConnect = async (e) => {
    e.preventDefault();
    setConnecting(true);
    try {
      const res = await fetch('http://localhost:8001/api/exchange/connect', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          api_key: apiKey,
          api_secret: apiSecret,
          testnet: isTestnet
        })
      });
      if (res.ok) {
        await fetchStatus();
      } else {
        const err = await res.json();
        alert(`Connection Failed: ${err.detail}`);
      }
    } catch(err) {
      alert(`Connection Error: ${err.message}`);
    } finally {
      setConnecting(false);
    }
  };

  const handleLogout = async () => {
    if (!window.confirm("Are you sure you want to disconnect from Binance?")) return;
    try {
      const res = await fetch('http://localhost:8001/api/exchange/disconnect', {
        method: 'POST'
      });
      if (res.ok) {
        setApiKey('');
        setApiSecret('');
        await fetchStatus();
      }
    } catch (err) {
      alert(`Disconnect Error: ${err.message}`);
    }
  };

  if (loading) {
    return (
      <div className="w-full h-full pt-[72px] flex items-center justify-center bg-springfield-bg">
        <div className="text-white font-comic text-2xl animate-pulse tracking-widest">WAKING UP THE STAFF...</div>
      </div>
    );
  }

  // --- CONNECT EXCHANGE VIEW ---
  if (status?.status === 'WAITING_FOR_CREDENTIALS') {
    return (
      <div className="w-full h-screen bg-springfield-bg flex items-center justify-center p-4 overflow-hidden relative">
        {/* Animated Background Elements */}
        <div className="absolute top-10 left-10 w-32 h-32 bg-white/5 rounded-full blur-xl"></div>
        <div className="absolute bottom-10 right-10 w-48 h-48 bg-black/5 rounded-full blur-2xl"></div>
        
        <AgentAssistant />
        <div ref={vaultRef} className="max-w-md w-full comic-panel bg-white p-6 relative">
          
          <div className="text-center mb-6 relative z-20">
            <KeyRound size={48} className="mx-auto text-burns-red mb-4" />
            <h1 className="text-3xl font-comic tracking-wider">SECURE VAULT DOOR</h1>
            <p className="text-sm font-mono mt-2">Mr. Burns demands your Bybit API credentials. "Excellent..."</p>
          </div>
          <form onSubmit={handleConnect} className="space-y-4 relative z-20">
            <div>
              <label className="block text-sm font-bold font-comic tracking-widest mb-1">API KEY</label>
              <input 
                type="password"
                required
                value={apiKey}
                onChange={e => setApiKey(e.target.value)}
                className="w-full border-4 border-black p-2 font-mono text-xl focus:outline-none focus:border-burns-red"
                placeholder="Key..."
              />
            </div>
            <div>
              <label className="block text-sm font-bold font-comic tracking-widest mb-1">API SECRET</label>
              <input 
                type="password"
                required
                value={apiSecret}
                onChange={e => setApiSecret(e.target.value)}
                className="w-full border-4 border-black p-2 font-mono text-xl focus:outline-none focus:border-burns-red"
                placeholder="Secret..."
              />
            </div>
            <label className="flex items-center space-x-2 font-bold font-comic tracking-wider">
              <input 
                type="checkbox" 
                checked={isTestnet}
                onChange={e => setIsTestnet(e.target.checked)}
                className="w-5 h-5 accent-burns-red"
              />
              <span>USE DEMO TRADING (HOMER SAFE)</span>
            </label>
            <button 
              type="submit" 
              disabled={connecting}
              className="w-full mt-4 comic-btn text-xl tracking-widest disabled:opacity-50"
            >
              {connecting ? "UNLOCKING..." : "ENTER VAULT"}
            </button>
          </form>
        </div>
      </div>
    );
  }

  // --- DIRECTOR DASHBOARD VIEW ---
  return (
    <div className="w-full h-full pt-[72px] bg-springfield-bg text-black px-6 overflow-y-auto pb-20 custom-scrollbar">
      <AgentAssistant />
      <div className="max-w-6xl mx-auto space-y-6 mt-6">
        
        {/* Executive Header */}
        <div className="comic-panel-warning p-6 flex flex-col md:flex-row justify-between items-center bg-springfield-yellow">
          <div>
            <h1 className="text-4xl font-comic tracking-widest mb-2 flex items-center gap-4">
              SPRINGFIELD CAPITAL <span className="bg-black text-springfield-yellow px-2 py-1 text-xl rotate-3">LIVE</span>
            </h1>
            <p className="font-mono font-bold text-lg">"Excellence in computational avarice."</p>
          </div>
          
          <div className="flex items-center gap-4 mt-6 md:mt-0 font-comic uppercase tracking-wider">
            <div className="flex items-center gap-2 px-4 py-2 border-4 border-black bg-white shadow-comic-sm">
              <div className={`w-4 h-4 border-2 border-black ${status?.status === 'IDLE' ? 'bg-lisa-blue' : 'bg-radioactive-green animate-pulse'}`}></div>
              <span>{status?.status || 'UNKNOWN'}</span>
            </div>
            <div className={`flex items-center gap-2 px-4 py-2 border-4 border-black shadow-comic-sm ${status?.testnet ? 'bg-white' : 'bg-burns-red text-white'}`}>
              <Network size={16} />
              <span>{status?.testnet ? 'TESTNET' : 'LIVE NET'}</span>
            </div>
            <button 
              onClick={handleLogout}
              className="flex items-center gap-2 px-4 py-2 bg-burns-red hover:bg-red-600 text-white border-4 border-black shadow-comic-sm transition-transform active:translate-y-1"
              title="Disconnect Exchange"
            >
              <LogOut size={16} />
              <span className="hidden md:inline">EJECT</span>
            </button>
          </div>
        </div>

        {/* Top Metrics & Springfield Components */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
          <div className="col-span-1 comic-panel p-6">
            <div className="font-comic text-xl mb-4 border-b-4 border-black pb-2 uppercase tracking-wide flex justify-between">
              <span>Vault Balance</span>
              <Wallet size={24} />
            </div>
            <div className="font-mono text-4xl font-bold mb-2 text-radioactive-green drop-shadow-[2px_2px_0px_rgba(0,0,0,1)]">
              ${status?.balance?.total?.toFixed(2) || '0.00'}
            </div>
            <div className="font-mono text-sm font-bold bg-gray-200 border-2 border-black inline-block px-2">
              FREE: ${status?.balance?.free?.toFixed(2) || '0.00'}
            </div>
          </div>
          
          <div className="col-span-2">
             <SimpsonBarometer />
          </div>
          
          <div className="col-span-1">
             <SectorIndicators />
          </div>
        </div>

        {/* Live AI Telemetry Stream */}
        {status?.telemetry && Object.keys(status.telemetry).length > 0 && (
          <div className="comic-panel p-6 bg-white">
            <h2 className="text-2xl font-comic uppercase tracking-widest border-b-4 border-black pb-2 mb-4 flex items-center gap-2">
              <BrainCircuit className="text-burns-red" />
              Live AI Telemetry Stream
            </h2>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {Object.entries(status.telemetry).map(([sym, data]) => (
                <div key={sym} className="border-4 border-black p-4 shadow-comic-sm bg-gray-50 flex flex-col h-full">
                  <div className="flex justify-between items-center mb-2">
                    <span className="font-comic font-bold text-lg">{sym.replace('-', '/')}</span>
                    <span className={`px-2 py-1 border-2 border-black font-mono text-sm font-bold ${data.action === 'BUY' ? 'bg-radioactive-green' : data.action === 'SELL' ? 'bg-burns-red text-white' : 'bg-springfield-yellow'}`}>
                      {data.action}
                    </span>
                  </div>
                  <div className="font-mono text-xs mb-2">
                    Confidence: <span className="font-bold">{(data.confidence * 100).toFixed(1)}%</span>
                  </div>
                  <div className="text-sm font-mono flex-1 overflow-y-auto custom-scrollbar pr-1 max-h-40 border-t-2 border-dashed border-gray-400 pt-2 text-gray-800">
                    {data.llm_rationale || 'Awaiting reasoning...'}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Engine Scanner Terminal Feed */}
        {status?.scanner_logs && status.scanner_logs.length > 0 && (
          <div className="comic-panel p-0 bg-black overflow-hidden mt-6 flex flex-col h-64 border-4 border-black">
            <div className="bg-[#111] border-b-2 border-[#00ff41]/30 p-2 flex items-center justify-between">
              <h2 className="text-[#00ff41] font-mono text-sm uppercase tracking-widest flex items-center gap-2">
                <TerminalIcon size={16} />
                Under the Hood: Real-time Math Engine Scan Logs
              </h2>
              <div className="flex gap-2">
                <span className="w-3 h-3 rounded-full bg-red-500"></span>
                <span className="w-3 h-3 rounded-full bg-yellow-500"></span>
                <span className="w-3 h-3 rounded-full bg-green-500"></span>
              </div>
            </div>
            <div className="flex-1 overflow-y-auto p-4 custom-terminal-scrollbar font-mono text-xs flex flex-col-reverse space-y-reverse space-y-1">
              {[...status.scanner_logs].reverse().map((log, i) => (
                <div key={i} className="flex gap-2 text-[#00ff41] hover:bg-[#00ff41]/10 px-1 rounded transition-colors break-words">
                  <span className="text-[#00ff41]/50 shrink-0">[{log.timestamp}]</span>
                  <span className="shrink-0 text-white bg-[#00ff41]/20 px-1 rounded">{log.symbol.replace('-', '/')}</span>
                  <span className={`${log.message.includes('Blocked') ? 'text-yellow-400' : 'text-[#00ff41]'}`}>{log.message}</span>
                </div>
              ))}
            </div>
            <style dangerouslySetInnerHTML={{ __html: `
                .custom-terminal-scrollbar::-webkit-scrollbar { width: 6px; }
                .custom-terminal-scrollbar::-webkit-scrollbar-track { background: #050505; }
                .custom-terminal-scrollbar::-webkit-scrollbar-thumb { background: #00ff41; border-radius: 3px; }
            `}} />
          </div>
        )}

        {/* Navigation Portals */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mt-6">
          <button 
            onClick={() => navigate('/mission')}
            className="comic-panel-dark p-8 hover:bg-[#1f1f3a] transition-all group flex flex-col items-center justify-center text-center cursor-pointer"
          >
            <div className="text-lisa-blue mb-4 bg-white border-4 border-white rounded-full p-4 group-hover:scale-110 transition-transform shadow-[4px_4px_0px_0px_rgba(255,255,255,0.5)]">
              <Gamepad2 size={48} className="text-black" />
            </div>
            <h2 className="text-3xl font-comic tracking-widest mb-2 text-white uppercase">Simulation Deck</h2>
            <p className="font-mono text-gray-300">View Active Positions & Trade Vault History</p>
          </button>
          
          <button 
            onClick={() => navigate('/explain')}
            className="comic-panel-dark p-8 hover:bg-[#1f1f3a] transition-all group flex flex-col items-center justify-center text-center cursor-pointer"
          >
            <div className="text-burns-red mb-4 bg-white border-4 border-white rounded-full p-4 group-hover:scale-110 transition-transform shadow-[4px_4px_0px_0px_rgba(255,255,255,0.5)]">
              <BrainCircuit size={48} className="text-black" />
            </div>
            <h2 className="text-3xl font-comic tracking-widest mb-2 text-white uppercase">The Boardroom</h2>
            <p className="font-mono text-gray-300">Monitor Live AI Analytics & Yes-Men Rationales</p>
          </button>
        </div>

      </div>
    </div>
  );
}
