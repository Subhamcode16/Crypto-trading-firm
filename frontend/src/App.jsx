import React, { useState } from 'react';
import { Routes, Route, useNavigate, useLocation } from 'react-router-dom';
import { Header } from './components/layout/Header';
import { GameContainer } from './components/canvas/GameContainer';
import { AgentPanel } from './components/panels/AgentPanel';
import { GameController } from './components/panels/GameController';
import { useWebSocket } from './hooks/useWebSocket';
import { useAgentStore } from './stores/useAgentStore';
import { StatsDashboard } from './pages/StatsDashboard';
import { routeEvent } from './logic/EventAdapter';
import { InboxDrawer } from './components/panels/InboxDrawer';

// Extracted from original App.jsx
function OfficeView() {
  const [selectedId, setSelectedId] = useState(null);
  const { send } = useWebSocket('ws://localhost:8080');
  const agents = useAgentStore((state) => state.agents);
  const selectedAgent = selectedId ? agents[selectedId] : null;


  return (
    <main className="relative w-full h-full pt-[72px] flex flex-col">
      <GameContainer />
      <div className="absolute inset-x-0 bottom-0 pointer-events-none p-6 flex flex-col justify-end">
        <div className="flex gap-4 overflow-x-auto pb-4 hide-scrollbar">
          {Object.values(agents).map(agent => (
            <div
              key={agent.id}
              onClick={() => setSelectedId(agent.id)}
              className={`min-w-[180px] h-24 rpg-panel p-3 pointer-events-auto cursor-pointer transition-transform ${selectedId === agent.id ? 'translate-y-1 bg-[#ffffff]' : 'hover:bg-[#f0f0f0]'}`}
            >
              <div className="flex justify-between items-start mb-2">
                <span className="text-[10px] text-gray-700 font-bold uppercase tracking-widest pixel-font">AGT-{agent.id}</span>
                <div className={`w-2 h-2 rounded-full border border-black shadow-[inset_1px_1px_2px_rgba(255,255,255,0.5)] ${agent.is_online ? 'bg-green-400' : 'bg-red-500'}`}></div>
              </div>
              <div className="text-sm font-bold truncate transition-colors title-font">{agent.name}</div>
              <div className="mt-2 flex items-center gap-2">
                <div className="rpg-inset w-full">
                  <span className={`text-[8px] uppercase pixel-font tracking-wider ${agent.status === 'IDLE' ? 'text-gray-500' :
                    agent.status === 'ERROR' ? 'text-red-600' :
                      'text-blue-600'
                    }`}>
                    {agent.status}
                  </span>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
      <GameController />
      {selectedAgent && (
        <AgentPanel
          agent={selectedAgent}
          onClose={() => setSelectedId(null)}
        />
      )}
    </main>
  );
}

function App() {
  return (
    <div className="relative w-screen h-screen overflow-hidden bg-[#8b9bb4] text-black selection:bg-black/10">
      <Header />
      <InboxDrawer />
      <Routes>
        <Route path="/" element={<OfficeView />} />
        <Route path="/dashboard" element={<StatsDashboard />} />
      </Routes>
    </div>
  );
}

export default App;
