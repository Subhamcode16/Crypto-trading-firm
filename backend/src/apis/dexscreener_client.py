import httpx
import logging
import asyncio
from datetime import datetime
import time

logger = logging.getLogger('dexscreener')

class DexscreenerClient:
    """Fetch real-time Solana token pairs from Dexscreener"""
    
    BASE_URL = 'https://api.dexscreener.com/latest/dex'
    
    def __init__(self):
        self.headers = {'User-Agent': 'SolanaTraderBot/1.0'}
        self.client = httpx.AsyncClient(headers=self.headers, timeout=10.0)
        self.last_request_time = 0
        self.min_interval = 0.5  # Min 500ms between requests
    
    async def _rate_limit(self):
        """Respect rate limits"""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.min_interval:
            await asyncio.sleep(self.min_interval - elapsed)
        self.last_request_time = time.time()
    
    async def get_solana_pairs(self, limit=10, strategy='hybrid'):
        """
        Fetch Solana pairs using HYBRID strategy (Option C)
        """
        all_pairs = {}  # Use dict to deduplicate by pair address
        
        try:
            if strategy in ['trending', 'hybrid']:
                trending = await self._get_trending_pairs()
                for pair in trending:
                    addr = pair.get('pairAddress')
                    if addr:
                        all_pairs[addr] = {**pair, 'source': 'trending', 'is_new': False}
            
            if strategy in ['new', 'hybrid']:
                new = await self._get_new_pairs()
                for pair in new:
                    addr = pair.get('pairAddress')
                    if addr:
                        # Prioritize new over trending
                        all_pairs[addr] = {**pair, 'source': 'new', 'is_new': True}
            
            # Convert to list and sort by discovery time (newest first)
            pairs_list = list(all_pairs.values())
            pairs_list.sort(
                key=lambda p: p.get('createdAt', 0),
                reverse=True
            )
            
            # Return top N
            result = pairs_list[:limit]
            trending_count = sum(1 for p in result if not p.get('is_new'))
            new_count = sum(1 for p in result if p.get('is_new'))
            
            logger.info(f'✅ Fetched {len(result)} pairs (trending:{trending_count}, new:{new_count})')
            return result
            
        except Exception as e:
            logger.error(f'❌ Error fetching pairs: {e}')
            return []
    
    async def _get_trending_pairs(self):
        """Fetch trending Solana pairs"""
        try:
            await self._rate_limit()
            
            # Dexscreener search doesn't support generic trending
            # Return empty for now; rely on new pairs instead
            logger.debug(f'📊 Trending: Using new pairs strategy (Dexscreener trending unavailable)')
            return []
            
        except Exception as e:
            logger.error(f'❌ Trending API error: {e}')
            return []
    
    async def _get_new_pairs(self):
        """Fetch NEW Solana pairs (newest first)"""
        try:
            await self._rate_limit()
            
            # Dexscreener search with generic 'sol' query returns new Solana tokens
            # This is a workaround since the API doesn't have a dedicated trending endpoint
            url = 'https://api.dexscreener.com/latest/dex/search'
            params = {
                'q': 'sol'  # Search for SOL-based pairs (shorter query)
            }
            
            response = await self.client.get(url, params=params)
            response.raise_for_status()
            
            data = response.json()
            pairs = data.get('pairs', [])
            
            # Filter for Solana chain and sort by creation time (newest first)
            solana_pairs = [
                p for p in pairs 
                if p.get('chainId') == 'solana'
            ]
            
            # Sort by creation time (newest first)
            solana_pairs.sort(
                key=lambda p: p.get('pairCreatedAt', 0) or 0,
                reverse=True
            )
            
            logger.debug(f'🆕 New: {len(solana_pairs)} Solana pairs')
            return solana_pairs
            
        except Exception as e:
            logger.error(f'❌ New pairs API error: {e}')
            # Fallback: return empty list (deduplication will handle it)
            return []
    

    
    def _get_pairs_fallback(self):
        """Fallback: Return mock data for testing"""
        logger.warning('⚠️ Using mock data for testing (API unavailable)')
        # Return empty list - researcher will skip
        return []
    
    async def get_pool(self, chain_id: str, pair_address: str):
        """Get details for a specific pair/pool"""
        try:
            await self._rate_limit()
            url = f"{self.BASE_URL}/pairs/{chain_id}/{pair_address}"
            response = await self.client.get(url)
            response.raise_for_status()
            data = response.json()
            pairs = data.get('pairs', [])
            return pairs[0] if pairs else None
        except Exception as e:
            logger.error(f"❌ Error fetching pair {pair_address}: {e}")
            return None

    async def get_token_pairs(self, token_address: str):
        """Get all pairs for a specific token address"""
        try:
            await self._rate_limit()
            url = f"{self.BASE_URL}/tokens/{token_address}"
            response = await self.client.get(url)
            response.raise_for_status()
            data = response.json()
            return data.get('pairs', [])
        except Exception as e:
            logger.error(f"❌ Error fetching token pairs for {token_address}: {e}")
            return []
    
    def parse_pair(self, pair_data: dict) -> dict:
        """Extract relevant fields from Dexscreener pair data"""
        try:
            return {
                'pair_address': pair_data.get('pairAddress'),
                'token_address': pair_data.get('baseToken', {}).get('address'),
                'token_name': pair_data.get('baseToken', {}).get('name'),
                'token_symbol': pair_data.get('baseToken', {}).get('symbol'),
                'decimals': pair_data.get('baseToken', {}).get('decimals', 6),
                'price_usd': float(pair_data.get('priceUsd', 0)),
                'liquidity_usd': float(pair_data.get('liquidity', {}).get('usd', 0)),
                'volume_24h': float(pair_data.get('volume', {}).get('h24', 0)),
                'volume_1h': float(pair_data.get('volume', {}).get('h1', 0)),
                'price_change_24h': float(pair_data.get('priceChange', {}).get('h24', 0)),
                'price_change_1h': float(pair_data.get('priceChange', {}).get('h1', 0)),
                'created_at': pair_data.get('pairCreatedAt'),
                'dex': pair_data.get('dex'),
                'raw': pair_data
            }
        except Exception as e:
            logger.error(f'Error parsing pair: {e}')
            return None

    async def close(self):
        """Close the httpx client"""
        await self.client.aclose()
