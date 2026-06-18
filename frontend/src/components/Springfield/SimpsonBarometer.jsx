import React, { useEffect, useState, useRef } from 'react';
import gsap from 'gsap';

const SimpsonBarometer = () => {
  const [needleAngle, setNeedleAngle] = useState(0); // -45 to 45
  const needleRef = useRef(null);
  
  useEffect(() => {
    // Randomly fluctuate the barometer to show "active" AI thinking
    const interval = setInterval(() => {
      const newAngle = Math.random() * 90 - 45; // -45 to +45
      setNeedleAngle(newAngle);
    }, 3000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    if (needleRef.current) {
      gsap.to(needleRef.current, {
        rotation: needleAngle,
        duration: 1.5,
        ease: "elastic.out(1, 0.5)",
        transformOrigin: "bottom center"
      });
    }
  }, [needleAngle]);

  return (
    <div className="comic-panel p-4 flex flex-col items-center justify-between h-full bg-white">
      <h2 className="font-comic text-xl text-center uppercase tracking-wider mb-2 border-b-2 border-black pb-1 w-full">The Simpson Family Barometer</h2>
      
      <div className="relative w-full h-32 flex items-end justify-center overflow-hidden mt-4">
        {/* Semicircle Dial */}
        <div className="absolute bottom-0 w-48 h-24 bg-gradient-to-r from-springfield-yellow via-burns-red to-lisa-blue rounded-t-full border-4 border-black border-b-0"></div>
        
        {/* Labels */}
        <div className="absolute bottom-2 w-56 flex justify-between px-2 font-comic text-xs z-10 font-bold bg-white/80 p-1 border-2 border-black">
          <span className="text-springfield-yellow drop-shadow-md">HOMER (PANIC)</span>
          <span className="text-burns-red drop-shadow-md">BURNS</span>
          <span className="text-lisa-blue drop-shadow-md">LISA (SAFE)</span>
        </div>
        
        {/* Needle pivot */}
        <div className="absolute bottom-0 w-6 h-6 bg-black rounded-full z-20 translate-y-1/2"></div>
        
        {/* Needle */}
        <div 
          ref={needleRef}
          className="absolute bottom-0 w-2 h-24 bg-black origin-bottom z-10 shadow-comic-sm"
        >
          {/* Arrow tip */}
          <div className="absolute -top-2 -left-2 w-0 h-0 border-l-[6px] border-r-[6px] border-b-[10px] border-l-transparent border-r-transparent border-b-black"></div>
        </div>
      </div>
    </div>
  );
};

export default SimpsonBarometer;
