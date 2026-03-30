import logging
import asyncio
from typing import List, Dict, Optional
import yfinance as yf
from datetime import datetime

logger = logging.getLogger('yahoo_finance')

class YahooFinanceClient:
    """
    Client for fetching stock market data from Yahoo Finance.
    Used by Agent 1 (Discovery) to find trending and volatile stocks.
    """
    
    def __init__(self):
        # A basket of high-volatility/highly traded stocks for paper trading experiments
        self.default_tickers = ["TSLA", "NVDA", "AAPL", "AMD", "MSFT", "GOOGL", "AMZN", "META", "NFLX", "COIN", "MARA", "RIOT"]
        logger.info("📈 Yahoo Finance Client initialized")

    async def get_trending_stocks(self, limit: int = 10) -> List[Dict]:
        """
        Fetch trending stocks or high-volume stocks for discovery.
        """
        try:
            # yfinance's trending_tickers would be better but it's often broken in the lib
            # We'll fetch the basket in a loop (concurrently for performance)
            async def _fetch_info(ticker: str):
                try:
                    # Ticker.info is blocking, wrap in executor
                    t = yf.Ticker(ticker)
                    info = t.history(period="1d", interval="1m") # Current price and change
                    if info.empty: return None
                    
                    latest = info.iloc[-1]
                    prev_close = t.history(period="2d")['Close'].iloc[-2] if len(t.history(period="2d")['Close']) > 1 else latest['Close']
                    change_pct = ((latest['Close'] - prev_close) / prev_close) * 100
                    
                    # Return lead format
                    return {
                        'symbol': ticker,
                        'name': ticker,
                        'price': latest['Close'],
                        'change_pct': change_pct,
                        'volume': latest['Volume'],
                        'market_cap': 0, # Placeholder for mock
                        'type': 'stock',
                        'timestamp': datetime.utcnow().isoformat(),
                        'source': 'yahoo_finance'
                    }
                except:
                    return None

            tasks = [_fetch_info(tick) for tick in self.default_tickers[:limit]]
            results = await asyncio.gather(*tasks)
            leads = [r for r in results if r is not None]
            
            logger.info(f"✅ Fetched {len(leads)} stock leads from Yahoo Finance")
            return leads
            
        except Exception as e:
            logger.error(f"Failed to fetch stocks from Yahoo Finance: {e}")
            return []

    async def get_stock_data(self, ticker: str) -> Optional[Dict]:
        """Fetch detailed data for a specific stock"""
        try:
            stock = yf.Ticker(ticker)
            info = stock.info
            return {
                'symbol': ticker,
                'price': info.get('currentPrice', info.get('regularMarketPrice')),
                'market_cap': info.get('marketCap'),
                'volume': info.get('regularMarketVolume'),
                'description': info.get('longBusinessSummary')
            }
        except Exception as e:
            logger.error(f"Error fetching data for {ticker}: {e}")
            return None

    async def close(self):
        """Cleanup if needed (yfinance doesn't use standard sessions we manage)"""
        pass
