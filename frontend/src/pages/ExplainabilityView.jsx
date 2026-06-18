import React, { useEffect, useState, useRef } from 'react';
import { createChart, CandlestickSeries } from 'lightweight-charts';
import { useParams, useNavigate } from 'react-router-dom';
import YesManPanel from '../components/Springfield/YesManPanel';

export function ExplainabilityView() {
  const { symbol = 'BTC-USDT' } = useParams();
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [news, setNews] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const chartContainerRef = useRef();

  useEffect(() => {
    let timeoutId;
    let isMounted = true;

    const fetchData = async () => {
      try {
        const res = await fetch(`http://localhost:8001/api/agent/explain/${symbol}`);
        if (!res.ok) {
           if (res.status === 404) {
             if (isMounted) {
               setError("Backend is fetching live market data... Please wait.");
               timeoutId = setTimeout(fetchData, 2000);
             }
             return; // keep loading
           }
           const errJson = await res.json().catch(() => ({}));
           throw new Error(errJson.detail || 'Failed to fetch explainability data');
        }
        const json = await res.json();
        if (json.status === 'success') {
          if (isMounted) {
            setData(json.data);
            setError(null);
          }
        } else {
          throw new Error(json.message);
        }

        const newsRes = await fetch('http://localhost:8001/api/agent/news');
        if (newsRes.ok) {
          const newsJson = await newsRes.json();
          if (newsJson.status === 'success' && isMounted) {
            if (newsJson.data.headlines && newsJson.data.headlines.length > 0) {
              setNews(newsJson.data);
            } else if (json.data && json.data.latest_sentiment && json.data.latest_sentiment.headlines?.length > 0) {
              setNews(json.data.latest_sentiment);
            } else {
              setNews(newsJson.data);
            }
          }
        } else if (isMounted && json.data && json.data.latest_sentiment) {
           setNews(json.data.latest_sentiment);
        }
      } catch (err) {
        if (isMounted) {
          setError(err.message);
        }
      } finally {
        if (isMounted && !timeoutId) {
          setLoading(false);
        }
      }
    };
    
    setLoading(true);
    fetchData();

    return () => {
      isMounted = false;
      if (timeoutId) clearTimeout(timeoutId);
    };
  }, [symbol]);

  useEffect(() => {
    if (!data || !chartContainerRef.current) return;

    const chart = createChart(chartContainerRef.current, {
      autoSize: true,
      layout: {
        background: { type: 'solid', color: '#ffffff' },
        textColor: '#000000',
      },
      grid: {
        vertLines: { color: '#e5e7eb' },
        horzLines: { color: '#e5e7eb' },
      },
      crosshair: {
        mode: 0,
      },
      rightPriceScale: {
        borderColor: '#000000',
      },
      timeScale: {
        borderColor: '#000000',
        timeVisible: true,
      },
    });

    const handleResize = () => {
      if (chartContainerRef.current) {
        chart.applyOptions({
          width: chartContainerRef.current.clientWidth,
          height: chartContainerRef.current.clientHeight,
        });
      }
    };
    
    const resizeObserver = new ResizeObserver(handleResize);
    resizeObserver.observe(chartContainerRef.current);
    handleResize();

    const candlestickSeries = chart.addSeries(CandlestickSeries, {
      upColor: '#39ff14', // radioactive-green
      downColor: '#ff3b30', // burns-red
      borderVisible: true,
      borderColor: '#000000',
      wickUpColor: '#000000',
      wickDownColor: '#000000',
    });

    // Parse chart data
    if (data.chart_data && data.chart_data.length > 0) {
      const formattedData = data.chart_data
        .map(d => {
          return {
            time: Math.floor(new Date(d.timestamp).getTime() / 1000),
            open: Number(d.open),
            high: Number(d.high),
            low: Number(d.low),
            close: Number(d.close),
          };
        })
        .filter(d => !isNaN(d.time) && !isNaN(d.close));
        
      formattedData.sort((a, b) => a.time - b.time);
      
      const uniqueData = [];
      const times = new Set();
      formattedData.forEach(item => {
        if (!times.has(item.time)) {
          times.add(item.time);
          uniqueData.push(item);
        }
      });
      
      try {
        candlestickSeries.setData(uniqueData);
      } catch(err) {
        console.error("Failed to set chart data:", err);
      }
    }
    
    chart.timeScale().fitContent();

    return () => {
      resizeObserver.disconnect();
      chart.remove();
    };
  }, [data, isFullscreen]);

  return (
    <div className="w-full h-full pt-[72px] pb-20 bg-springfield-bg text-black overflow-y-auto flex flex-col custom-scrollbar">
      <div className="max-w-7xl mx-auto w-full p-6 space-y-6 flex-1">
        
        <div className="flex justify-between items-center comic-panel p-4 bg-springfield-yellow">
          <div>
            <h1 className="text-3xl font-comic text-black uppercase tracking-widest">The Boardroom: {symbol.replace('-', '/')}</h1>
            <p className="font-mono text-black font-bold">Ask the Yes-Men for their analysis.</p>
          </div>
          <div className="flex gap-2">
            <button onClick={() => navigate('/explain/BTC-USDT')} className={`px-4 py-2 border-4 border-black font-comic uppercase shadow-comic-sm comic-hover ${symbol === 'BTC-USDT' ? 'bg-springfield-yellow' : 'bg-white hover:bg-gray-200'}`}>BTC/USDT</button>
            <button onClick={() => navigate('/explain/ETH-USDT')} className={`px-4 py-2 border-4 border-black font-comic uppercase shadow-comic-sm comic-hover ${symbol === 'ETH-USDT' ? 'bg-springfield-yellow' : 'bg-white hover:bg-gray-200'}`}>ETH/USDT</button>
            <button onClick={() => navigate('/explain/SOL-USDT')} className={`px-4 py-2 border-4 border-black font-comic uppercase shadow-comic-sm comic-hover ${symbol === 'SOL-USDT' ? 'bg-springfield-yellow' : 'bg-white hover:bg-gray-200'}`}>SOL/USDT</button>
          </div>
        </div>

        {loading ? (
          <div className="text-center py-20 text-3xl font-comic uppercase tracking-widest animate-pulse">Summoning the Yes-Men...</div>
        ) : error ? (
          <div className="comic-panel-warning p-8 bg-burns-red text-white flex flex-col items-center">
             <div className="text-2xl font-comic mb-2 uppercase">{error.includes('fetching') ? 'PREPARING REPORTS...' : 'GLAVIN! ERROR!'}</div>
             <div className="text-lg font-mono font-bold bg-black p-2 border-2 border-white">{error}</div>
             <div className="text-sm mt-4 font-mono">The agent takes about 10-20 seconds to download live Yahoo Finance data on boot.</div>
          </div>
        ) : data ? (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            
            {/* Chart Column */}
            <div className={`col-span-1 lg:col-span-2 flex flex-col gap-4 ${isFullscreen ? 'fixed inset-0 z-[100] bg-springfield-bg p-6' : ''}`}>
               <div className="comic-panel p-2 flex-1 bg-white flex flex-col relative" style={{ minHeight: isFullscreen ? 'auto' : '500px' }}>
                 <div className="flex justify-between items-center mb-2 px-2 border-b-4 border-black pb-2">
                   <h2 className="font-comic text-xl uppercase tracking-widest">Price Action Chart</h2>
                   <button onClick={() => setIsFullscreen(!isFullscreen)} className="text-xs font-mono bg-black text-white px-2 py-1 uppercase hover:bg-gray-800 shadow-[2px_2px_0px_0px_rgba(150,150,150,1)] active:translate-y-px transition-all">
                     {isFullscreen ? 'Exit Fullscreen' : 'Fullscreen'}
                   </button>
                 </div>
                 <div ref={chartContainerRef} className="flex-1 w-full border-4 border-black" />
               </div>
               
               {/* News Feed - Comic Style */}
               <div className="comic-panel p-4 bg-white">
                 <h2 className="font-comic text-xl border-b-4 border-black pb-2 mb-4 tracking-widest uppercase">Kenton's Daily News</h2>
                 {news?.headlines?.length > 0 ? (
                   <ul className="space-y-3 font-mono text-sm">
                     {news.headlines.slice(0, 5).map((h, i) => {
                       const text = typeof h === 'string' ? h : h.title;
                       return (
                         <li key={i} className="flex items-start gap-2 border-b border-dashed border-gray-400 pb-2">
                           <span className="text-burns-red shrink-0">►</span>
                           <span>{text}</span>
                         </li>
                       );
                     })}
                   </ul>
                 ) : (
                   <div className="text-gray-500 font-mono italic">No news is good news... right?</div>
                 )}
               </div>
            </div>

            {/* Yes-Man Column */}
            <div className="col-span-1 flex flex-col gap-6">
              <YesManPanel symbol={symbol} />
            </div>

          </div>
        ) : null}
      </div>
    </div>
  );
}
