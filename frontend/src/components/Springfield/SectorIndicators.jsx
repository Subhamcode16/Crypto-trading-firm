import React from 'react';

const SectorIndicators = () => {
  // We can mock this or use the macro_context from backend if available
  // For the sake of the aesthetic, let's hardcode some values that fluctuate or just static visual.
  const mappleScore = 72;
  const krustyScore = 35;

  return (
    <div className="comic-panel p-4 flex flex-col justify-center h-full bg-white">
      <h2 className="font-comic text-xl border-b-4 border-black pb-2 mb-4 uppercase tracking-wider">Sector Indicators</h2>
      
      <div className="space-y-6">
        {/* Mapple (Luxury/Tech) */}
        <div>
          <div className="flex justify-between font-comic text-lg uppercase mb-1">
            <span>🏷️ Mapple (Luxury)</span>
            <span>{mappleScore}%</span>
          </div>
          <div className="w-full h-6 border-4 border-black bg-gray-200 overflow-hidden shadow-comic-sm">
            <div 
              className="h-full bg-mapple-silver border-r-4 border-black" 
              style={{ width: `${mappleScore}%` }}
            ></div>
          </div>
        </div>

        {/* Krusty (Basics/Consumer) */}
        <div>
          <div className="flex justify-between font-comic text-lg uppercase mb-1">
            <span>🍔 Krusty (Basics)</span>
            <span>{krustyScore}%</span>
          </div>
          <div className="w-full h-6 border-4 border-black bg-gray-200 overflow-hidden shadow-comic-sm">
            <div 
              className="h-full bg-burns-red border-r-4 border-black" 
              style={{ width: `${krustyScore}%` }}
            ></div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default SectorIndicators;
