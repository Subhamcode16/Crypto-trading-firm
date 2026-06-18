import logging
import asyncio
import os
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import websockets
import json

from src.apis.dexscreener_client import DexscreenerClient
from src.apis.coingecko_client import CoinGeckoClient
from src.apis.rss_client import RSSClient
from src.apis.reddit_client import RedditClient
from src.apis.twitter_client import TwitterClient
from src.apis.pumpfun_client import PumpFunClient
from src.apis.yahoo_finance_client import YahooFinanceClient
from src.agents.agent_3_wallet_tracker import Agent3WalletTracker
from src.config import Config

logger = logging.getLogger('agent_1_discovery')

class Agent1Discovery:
    """
    AGENT 1: The Scout (Discovery Division)
    
    Role: Multi-source on-chain and off-chain discovery.
    Finds "leads" (token addresses) and filters for basic eligibility before passing 
    to Agent 2 (Safety).
    """
    
    def __init__(self, config: Config, db=None, dexscreener=None, solscan=None, birdeye=None, helius=None):
        self.config = config
        self.db = db
        self.dexscreener = dexscreener or DexscreenerClient()
        self.solscan = solscan
        self.birdeye = birdeye
        self.helius = helius
        
        # Discovery Clients
        self.coingecko = CoinGeckoClient()
        self.rss = RSSClient()
        self.reddit = RedditClient()
        self.twitter = TwitterClient(self.config.get_optional_secret('TWITTER_BEARER_TOKEN'))
        self.pumpfun = PumpFunClient()
        self.yahoo_finance = YahooFinanceClient()
        
        # Tracking & Deduplication
        self.analyzed_recently = {}  # {address: timestamp}
        self.ws_url = os.getenv("WS_SERVER_URL", "ws://localhost:8080")
        self.is_scanning = False
        
        logger.info("🕵️ Agent 1 (Discovery) initialized")

    async def start_auto_scan(self, interval_minutes: int = 15):
        """Management loop for automated scanning (Hybrid Orchestration)"""
        if self.is_scanning:
            logger.warning("Agent 1 is already scanning.")
            return
            
        self.is_scanning = True
        logger.info(f"🚀 Agent 1 starting auto-scan cycle (every {interval_minutes}m)")
        
        while self.is_scanning:
            try:
                await self.discover_new_leads()
            except Exception as e:
                logger.error(f"Error in Agent 1 discovery cycle: {e}")
            
            await asyncio.sleep(interval_minutes * 60)

    async def stop_auto_scan(self):
        self.is_scanning = False
        logger.info("🛑 Agent 1 stopping auto-scan cycle")

    async def _send_news_event(self, type: str, source: str, title: str, importance: str = 'MEDIUM'):
        """Send a news item to the frontend news panel"""
        try:
            async with websockets.connect(self.ws_url) as ws:
                msg = {
                    "event": "NEWS_FEED_UPDATE",
                    "payload": {
                        "type": type,
                        "source": source,
                        "title": title,
                        "timestamp": datetime.now().strftime("%H:%M"),
                        "importance": importance
                    }
                }
                await ws.send(json.dumps(msg))
        except:
            pass

    async def _resolve_candidate_address(self, candidate: dict) -> Optional[str]:
        """Try to find a Solana contract address for a candidate"""
        addr = candidate.get('address') or candidate.get('token_address')
        if addr: return addr
        
        symbol = candidate.get('symbol')
        if not symbol: return None
        
        try:
            results = await self.dexscreener.search_pairs(symbol)
            for pair in results:
                if pair.get('chainId') == 'solana':
                    return pair.get('baseToken', {}).get('address')
        except:
            pass
        return None

    async def _token_analyzed_recently(self, address: str, hours: int = 24) -> bool:
        """Check local cache and DB if token was already found"""
        now = datetime.utcnow()
        if address in self.analyzed_recently:
            if now < self.analyzed_recently[address] + timedelta(hours=hours):
                return True
        
        if self.db:
            return await self.db.token_exists(address)
        return False

    async def discover_new_leads(self) -> List[Dict]:
        """
        Gather potential trade leads from all sources in parallel.
        Returns a list of unique, un-processed candidates.
        """
        logger.info('📡 [AGENT_1] Multi-source lead discovery starting...')
        
        discovery_results = []
        
        async def get_dex_results():
            try:
                dex_pairs = await self.dexscreener.get_solana_pairs(limit=10, strategy='hybrid')
                results = []
                if dex_pairs:
                    for p in dex_pairs:
                        results.append({
                            'source': 'dexscreener',
                            'address': p.get('baseToken', {}).get('address'),
                            'symbol': p.get('baseToken', {}).get('symbol'),
                            'score': 7.5 if 'trending' in p.get('strategy', '') else 7.0,
                            'raw': p
                        })
                    await self._send_news_event("MARKET", "DexScreener", f"Found {len(dex_pairs)} trending pairs on Solana", "MEDIUM")
                return results
            except Exception as e:
                logger.error(f"DexScreener discovery failed: {e}")
                return []

        async def get_cg_results():
            try:
                # NEW: Expanding beyond trending to get high-cap Solana tokens
                cg_market_data = await self.coingecko.get_top_solana_tokens(limit=20)
                results = []
                if cg_market_data:
                    for c in cg_market_data:
                        addr = c.get('address') or await self._resolve_candidate_address(c)
                        if addr:
                            results.append({
                                'source': 'coingecko',
                                'address': addr,
                                'symbol': c.get('symbol'),
                                'score': 7.5,
                                'type': 'solana_token', # Categorized as established token
                                'raw': c
                            })
                return results
            except Exception as e:
                logger.error(f"CoinGecko discovery failed: {e}")
                return []

        async def get_stock_results():
            try:
                # NEW: Traditional stocks discovery
                stocks = await self.yahoo_finance.get_trending_stocks(limit=10)
                results = []
                for s in stocks:
                    results.append({
                        'source': 'yahoo_finance',
                        'address': s.get('symbol'), # Use symbol as unique key for stocks
                        'symbol': s.get('symbol'),
                        'score': 8.0 if abs(s.get('change_pct', 0)) > 2 else 7.0,
                        'type': 'stock',
                        'raw': s
                    })
                return results
            except Exception as e:
                logger.error(f"Stock discovery failed: {e}")
                return []

        async def get_reddit_results():
            try:
                return await self.reddit.scan_subreddits() or []
            except Exception as e:
                logger.error(f"Reddit discovery failed: {e}")
                return []

        async def get_rss_results():
            try:
                news = await self.rss.get_latest_headlines()
                results = []
                if news:
                    for n in news:
                        await self._send_news_event("RSS", n.get('source', 'News'), n.get('title', 'Market Update'), "HIGH")
                        addr = await self._resolve_candidate_address(n)
                        if addr:
                            results.append({
                                'source': 'rss_news',
                                'address': addr,
                                'symbol': n.get('symbol', 'UNKNOWN'),
                                'score': 6.5,
                                'raw': n
                            })
                return results
            except Exception as e:
                logger.error(f"RSS discovery failed: {e}")
                return []

        async def get_pumpfun_results():
            try:
                pumpfun_tokens = await self.pumpfun.get_newest_tokens(limit=10) or []
                koth = await self.pumpfun.get_king_of_hill()
                if koth:
                    pumpfun_tokens.insert(0, koth)

                results = []
                for p in pumpfun_tokens:
                    addr = p.get('address')
                    if not addr or p.get('bonding_curve_pct', 0) < 10:
                        continue
                    results.append({
                        'source': 'pumpfun',
                        'address': addr,
                        'symbol': p.get('symbol'),
                        'score': p.get('score', 6.0),
                        'raw': p
                    })
                return results
            except Exception as e:
                logger.error(f"Pump.fun discovery failed: {e}")
                return []

        async def get_twitter_results():
            if self.twitter and hasattr(self.twitter, 'bearer_token') and self.twitter.bearer_token:
                try:
                    return await self.twitter.search_solana_keywords() or []
                except Exception as e:
                    logger.error(f"Twitter discovery failed: {e}")
            return []

        async def get_smart_money_results():
            try:
                tracker_3 = Agent3WalletTracker(self.config)
                tracker_3.solscan = self.solscan
                tracker_3.birdeye = self.birdeye
                tracker_3.helius  = self.helius
                
                if hasattr(tracker_3, 'get_trending_tokens'):
                    smart_tokens = await tracker_3.get_trending_tokens() 
                    results = []
                    if smart_tokens and isinstance(smart_tokens, list):
                        for st in smart_tokens:
                            if not st or not isinstance(st, dict): continue
                            symbol = st.get('symbol', 'UNKNOWN')
                            addr = st.get('address')
                            if not addr: continue

                            await self._send_news_event("WHALE", "Agent 3", f"Smart Money detected accumulating {symbol} ({addr[:8]})", "URGENT")
                            results.append({
                                'source': 'agent_3_wallet',
                                'address': addr,
                                'symbol': symbol,
                                'score': 8.0,
                                'raw': st
                            })
                        return results
            except Exception as e:
                logger.debug(f"Agent 3 discovery failed: {e}")
            return []

        # Gather all in parallel
        tasks = [
            get_dex_results(),
            get_cg_results(),
            get_reddit_results(),
            get_rss_results(),
            get_pumpfun_results(),
            get_twitter_results(),
            get_smart_money_results(),
            get_stock_results()
        ]
        
        batches = await asyncio.gather(*tasks)
        
        # Flatten and filter
        unique_leads = {}
        for batch in batches:
            for lead in batch:
                addr = lead.get('address')
                if not addr or await self._token_analyzed_recently(addr):
                    continue
                
                # Assign default type if missing
                if 'type' not in lead:
                    if lead['source'] == 'pumpfun':
                        lead['type'] = 'solana_meme'
                    else:
                        lead['type'] = 'solana_token'

                if addr not in unique_leads or lead['score'] > unique_leads[addr]['score']:
                    unique_leads[addr] = lead
        
        leads = list(unique_leads.values())
        logger.info(f"✅ [AGENT_1] Found {len(leads)} new leads.")
        
        # Track for next 24h
        for lead in leads:
            self.analyzed_recently[lead['address']] = datetime.utcnow()
            
        return leads

if __name__ == "__main__":
    # Mock test
    from src.config import Config
    cfg = Config()
    discovery = Agent1Discovery(cfg)
    async def test():
        results = await discovery.discover_new_leads()
        print(f"Found {len(results)} results")
    asyncio.run(test())
