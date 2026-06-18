import React, { useRef } from 'react';
import gsap from 'gsap';
import { useGSAP } from '@gsap/react';

const CatchemSimulator = () => {
  const containerRef = useRef(null);
  const gearRef1 = useRef(null);
  const gearRef2 = useRef(null);
  const frinkRef = useRef(null);

  useGSAP(() => {
    // Continuous gear rotation
    gsap.to(gearRef1.current, {
      rotation: 360,
      duration: 5,
      repeat: -1,
      ease: "linear"
    });
    
    gsap.to(gearRef2.current, {
      rotation: -360,
      duration: 3,
      repeat: -1,
      ease: "linear"
    });

    // Frink hover animation
    gsap.to(frinkRef.current, {
      y: -10,
      duration: 1.5,
      yoyo: true,
      repeat: -1,
      ease: "sine.inOut"
    });
  }, { scope: containerRef });

  return (
    <div ref={containerRef} className="comic-panel-dark p-6 flex items-center justify-between h-full text-center relative overflow-hidden">
      
      {/* Professor Frink Image */}
      <div className="w-1/3 flex flex-col items-center z-10">
        <div ref={frinkRef} className="w-32 h-32 border-4 border-white bg-springfield-bg rounded-full overflow-hidden shadow-[4px_4px_0px_rgba(255,255,255,1)] mb-4 flex items-center justify-center">
          <img src="/assets/frink.png" alt="Professor Frink" className="w-full h-full object-cover" />
        </div>
        <div className="bg-white text-black font-comic uppercase px-2 py-1 border-2 border-white text-sm">
          Prof. Frink
        </div>
      </div>

      <div className="w-2/3 flex flex-col items-center justify-center z-10">
        <h2 className="font-comic text-2xl uppercase tracking-wider mb-2 text-radioactive-green bg-black/50 px-2">CATCHEM SIMULATOR</h2>
        <p className="font-mono text-sm mb-6 text-gray-300 bg-black/50 px-2">"GLAVIN! Computing historical probabilities..."</p>
        
        <button className="comic-btn text-xl relative group overflow-hidden">
          <span className="relative z-10">Run Frink Engine</span>
          <div className="absolute inset-0 bg-white translate-y-full group-hover:translate-y-0 transition-transform duration-300 z-0 opacity-20"></div>
        </button>

        {/* Decorative sci-fi elements */}
        <div className="mt-8 flex gap-4">
          <div className="w-4 h-4 bg-radioactive-green rounded-full shadow-[0_0_10px_rgba(57,255,20,1)]"></div>
          <div className="w-4 h-4 bg-burns-red rounded-full shadow-[0_0_10px_rgba(255,59,48,1)]"></div>
          <div className="w-4 h-4 bg-lisa-blue rounded-full shadow-[0_0_10px_rgba(0,122,255,1)]"></div>
        </div>
      </div>

      {/* Background Gears */}
      <div ref={gearRef1} className="absolute -right-10 -bottom-10 opacity-20 text-white font-mono text-9xl leading-none">⚙</div>
      <div ref={gearRef2} className="absolute right-20 -bottom-5 opacity-10 text-white font-mono text-7xl leading-none">⚙</div>
    </div>
  );
};

export default CatchemSimulator;
