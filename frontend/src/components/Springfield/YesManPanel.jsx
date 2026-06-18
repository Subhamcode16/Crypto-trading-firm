import React, { useEffect, useState, useRef } from 'react';
import gsap from 'gsap';
import { useGSAP } from '@gsap/react';

const characters = [
  { name: "Smithers Agent", color: "bg-radioactive-green text-black", img: "/assets/smithers.png" },
  { name: "Blue-Haired Lawyer", color: "bg-lisa-blue text-white", img: "/assets/lawyer.png" }
];

const YesManPanel = ({ symbol = "BTC-USDT" }) => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [activeCharacter, setActiveCharacter] = useState(characters[0]);
  
  const containerRef = useRef(null);
  const bubbleRef = useRef(null);
  const avatarRef = useRef(null);

  const fetchData = async () => {
    try {
      const res = await fetch(`http://localhost:8001/api/agent/explain/${symbol}`);
      if (res.ok) {
        const json = await res.json();
        const explainData = json.data;
        if (!data || data.llm_rationale !== explainData.llm_rationale) {
          setData(explainData);
          setActiveCharacter(characters[Math.floor(Math.random() * characters.length)]);
        }
      }
    } catch (e) {
      console.error("Failed to fetch explainability data", e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 5000);
    return () => clearInterval(interval);
  }, [symbol]);

  // GSAP Animation whenever data/rationale changes
  useGSAP(() => {
    if (bubbleRef.current && avatarRef.current && data) {
      const tl = gsap.timeline();
      
      // Avatar jump
      tl.fromTo(avatarRef.current, 
        { y: 20 }, 
        { y: 0, duration: 0.3, ease: "back.out(1.7)" }
      );

      // Bubble pop-in
      tl.fromTo(bubbleRef.current, 
        { scale: 0, opacity: 0, transformOrigin: "bottom left" }, 
        { scale: 1, opacity: 1, duration: 0.4, ease: "elastic.out(1, 0.7)" },
        "-=0.1"
      );
    }
  }, { dependencies: [data], scope: containerRef });

  if (loading) {
    return <div className="comic-panel p-6 animate-pulse">Consulting the Board...</div>;
  }

  if (!data) {
    return <div className="comic-panel p-6">No data available for {symbol}. Wait for the AI to analyze the market.</div>;
  }

  const confidencePct = data.prediction?.confidence ? (data.prediction.confidence * 100).toFixed(1) : 0;
  const decision = data.llm_decision || data.prediction?.action || "HOLD";
  
  let glowColor = "shadow-comic";
  if (decision === "BUY") glowColor = "shadow-[0_0_15px_rgba(57,255,20,1)] border-radioactive-green";
  if (decision === "SELL") glowColor = "shadow-[0_0_15px_rgba(255,59,48,1)] border-burns-red";

  return (
    <div className={`comic-panel flex flex-col h-full ${glowColor} transition-all duration-500`} ref={containerRef}>
      <div className="bg-black text-white p-2 font-comic text-xl uppercase flex justify-between border-b-4 border-black">
        <span>The "Yes-Man" Boardroom</span>
        <span>{symbol}</span>
      </div>
      
      <div className="p-4 flex-grow flex flex-col justify-end relative bg-[url('data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSI0IiBoZWlnaHQ9IjQiPjxyZWN0IHdpZHRoPSI0IiBoZWlnaHQ9IjQiIGZpbGw9IiNmZmYiLz48cmVjdCB3aWR0aD0iMSIgaGVpZ2h0PSIxIiBmaWxsPSIjY2NjIi8+PC9zdmc+')]">
        
        {/* Chat Bubble */}
        <div ref={bubbleRef} className="relative bg-white border-4 border-black p-4 mb-8 shadow-comic-sm self-start max-w-[80%] z-10">
          <p className="font-mono text-lg font-bold leading-tight">{data.llm_rationale || "Sir, I have no idea what the market is doing."}</p>
          <div className="mt-2 text-sm font-comic border-t-2 border-dashed border-black pt-2">
            Action: <span className={decision === 'BUY' ? 'text-radioactive-green' : decision === 'SELL' ? 'text-burns-red' : 'text-gray-500'}>{decision}</span> | Confidence: {confidencePct}%
          </div>
          {/* Bubble tail */}
          <div className="absolute -bottom-6 left-8 w-0 h-0 border-l-[10px] border-r-[10px] border-t-[20px] border-l-transparent border-r-transparent border-t-black"></div>
          <div className="absolute -bottom-4 left-[34px] w-0 h-0 border-l-[6px] border-r-[6px] border-t-[14px] border-l-transparent border-r-transparent border-t-white z-10"></div>
        </div>

        {/* Character Avatar */}
        <div className="flex items-end gap-4 mt-auto">
          <div ref={avatarRef} className={`w-32 h-32 border-4 border-black bg-white shadow-comic-sm rounded-full overflow-hidden flex items-center justify-center`}>
            <img src={activeCharacter.img} alt={activeCharacter.name} className="w-full h-full object-cover" />
          </div>
          <div className={`border-4 border-black px-4 py-1 font-comic text-xl shadow-comic-sm mb-4 ${activeCharacter.color}`}>
            [{activeCharacter.name}]
          </div>
        </div>
      </div>
    </div>
  );
};

export default YesManPanel;
