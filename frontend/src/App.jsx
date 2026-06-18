import React, { useState } from 'react';
import { Routes, Route, useNavigate, useLocation } from 'react-router-dom';
import { Header } from './components/layout/Header';
import { MissionDashboard } from './pages/MissionDashboard';
import { ExplainabilityView } from './pages/ExplainabilityView';
import { InboxDrawer } from './components/panels/InboxDrawer';
import { OfficeDashboard } from './pages/OfficeDashboard';
import BurnsTicker from './components/Springfield/BurnsTicker';

function App() {
  return (
    <div className="relative w-screen h-screen overflow-hidden bg-springfield-bg text-white selection:bg-white/20 pb-10">
      <Header />
      <InboxDrawer />
      <Routes>
        <Route path="/" element={<OfficeDashboard />} />
        <Route path="/mission" element={<MissionDashboard />} />
        <Route path="/explain/:symbol" element={<ExplainabilityView />} />
        <Route path="/explain" element={<ExplainabilityView />} />
      </Routes>
      <BurnsTicker />
    </div>
  );
}

export default App;
