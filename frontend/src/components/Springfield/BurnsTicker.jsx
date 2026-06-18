import React from 'react';

const jokes = [
  "BITCOIN SOARS TO INFINITY SYMBOL",
  "ANIMOTION UP AN EIGHTH",
  "DUFF BEER DECLARES BANKRUPTCY, MARKET RALLIES",
  "MR. BURNS ACQUIRES ENTIRE INTERNET",
  "COMIC BOOK GUY RATES ECONOMY: WORST. QUARTER. EVER.",
  "MAPPLE STOCK UP AFTER NEW ICAR ANNOUNCEMENT",
  "KRUSTY BURGER MEAT SUPPLY CHAIN DISRUPTED BY UNKNOWN ANIMAL",
  "POWER PLANT STOCK STABLE DESPITE 42ND MELTDOWN THREAT",
  "S&P 500 REPLACED BY S&P 1 (MR. BURNS)",
  "MAYOR QUIMBY EMBEZZLES FUNDS, INFLATION DROPS 2%"
];

const BurnsTicker = () => {
  return (
    <div className="fixed bottom-0 left-0 w-full bg-springfield-yellow border-t-4 border-black text-black z-50 h-10 flex flex-col justify-center overflow-hidden">
      <div className="whitespace-nowrap inline-block animate-marquee font-mono text-xl font-bold uppercase tracking-widest">
        {jokes.map((item, idx) => (
          <span key={idx} className="mx-8">
            {idx % 2 === 0 ? <span className="text-burns-red">♦</span> : <span className="text-radioactive-green">●</span>}
            <span className="mx-4">{item}</span>
          </span>
        ))}
        {/* Duplicate for seamless looping */}
        {jokes.map((item, idx) => (
          <span key={`dup-${idx}`} className="mx-8">
            {idx % 2 === 0 ? <span className="text-burns-red">♦</span> : <span className="text-radioactive-green">●</span>}
            <span className="mx-4">{item}</span>
          </span>
        ))}
      </div>
    </div>
  );
};

export default BurnsTicker;
