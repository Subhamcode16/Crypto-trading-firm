import React, { useEffect, useRef, useState } from 'react';
import gsap from 'gsap';

export const AgentAssistant = () => {
  const [message, setMessage] = useState("");
  const characterRef = useRef(null);
  const bubbleRef = useRef(null);
  const containerRef = useRef(null);
  const tl = useRef(null);

  useEffect(() => {
    // Initial state: Character off-screen (slid down), bubble hidden
    gsap.set(characterRef.current, { y: 400 });
    gsap.set(bubbleRef.current, { scale: 0, opacity: 0 });

    const handleSpeak = (e) => {
      const text = e.detail;
      setMessage(text);
      
      if (tl.current) {
        tl.current.kill();
      }
      
      tl.current = gsap.timeline();
      
      // 1. Slide character in
      tl.current.to(characterRef.current, {
        y: 0,
        duration: 0.5,
        ease: "back.out(1.2)"
      });
      
      // 2. Pop thought bubble
      tl.current.fromTo(bubbleRef.current, 
        { scale: 0, opacity: 0, transformOrigin: "bottom left" },
        { scale: 1, opacity: 1, duration: 0.4, ease: "back.out(1.5)" },
        "+=0.1" // slight delay
      );

      // 3. Wait 8 seconds
      tl.current.to(bubbleRef.current, {
        scale: 0, opacity: 0, duration: 0.3, ease: "back.in(1.5)"
      }, "+=8");

      // 4. Slide character out
      tl.current.to(characterRef.current, {
        y: 400,
        duration: 0.5,
        ease: "power2.in"
      }, "+=0.2");
    };

    window.addEventListener('agent-speak', handleSpeak);
    return () => window.removeEventListener('agent-speak', handleSpeak);
  }, []);

  return (
    <div ref={containerRef} className="absolute bottom-0 left-8 z-50 flex items-end pointer-events-none w-72 h-96">
      
      {/* Thought Bubble */}
      <div 
        ref={bubbleRef} 
        className="absolute bottom-64 left-44 z-10 w-64 h-48 flex items-center justify-center"
      >
        <svg viewBox="0 0 200 150" className="absolute inset-0 w-full h-full drop-shadow-[4px_4px_0px_rgba(0,0,0,1)]" preserveAspectRatio="none">
          {/* Main Cloud */}
          <path d="M 40,70 Q 20,70 20,50 Q 20,30 40,30 Q 50,10 80,10 Q 110,10 120,30 Q 150,20 170,40 Q 190,50 180,70 Q 200,90 180,110 Q 160,130 130,120 Q 110,140 80,130 Q 60,140 40,120 Q 20,100 40,70 Z" className="fill-white stroke-black stroke-[3px]" />
          {/* Thought bubbles pointing down-left */}
          <circle cx="45" cy="135" r="8" className="fill-white stroke-black stroke-[3px]" />
          <circle cx="30" cy="150" r="4" className="fill-white stroke-black stroke-[3px]" />
        </svg>
        <div className="relative z-20 font-comic text-black text-center text-lg leading-tight w-4/5 pt-2 px-4">
          {message}
        </div>
      </div>

      {/* Character Image */}
      <img 
        ref={characterRef}
        src="/agent_transparent.png" 
        alt="Agent Assistant" 
        className="w-72 h-auto drop-shadow-[4px_4px_0px_rgba(0,0,0,1)]"
        style={{ transform: "translateY(400px)" }} // Fallback initial state
      />
    </div>
  );
};
