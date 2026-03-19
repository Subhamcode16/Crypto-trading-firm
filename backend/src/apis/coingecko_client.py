#!/usr/bin/env python3
"""
CoinGecko API Client for Researcher Agent (Agent 1)
Fetches trending tokens and new listings.
"""

import httpx
import logging
import asyncio
from typing import List, Dict, Optional

logger = logging.getLogger('coingecko_client')

class CoinGeckoClient:
    """Interface for CoinGecko Public API"""
    
    BASE_URL = "https://api.coingecko.com/api/v3"
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key
        self.headers = {
            "Accept": "application/json"
        }
        if api_key:
            self.headers["x-cg-demo-api-key"] = api_key
        self.client = httpx.AsyncClient(headers=self.headers, timeout=10.0)
            
    async def get_trending_solana(self) -> List[Dict]:
        """Fetch trending coins on Solana network specifically (Async)"""
        try:
            url = f"{self.BASE_URL}/search/trending"
            response = await self.client.get(url)
            response.raise_for_status()
            
            data = response.json()
            trending_coins = data.get('coins', [])
            
            solana_candidates = []
            for item in trending_coins:
                coin = item.get('item', {})
                solana_candidates.append({
                    'source': 'coingecko_trending',
                    'name': coin.get('name'),
                    'symbol': coin.get('symbol'),
                    'market_cap_rank': coin.get('market_cap_rank'),
                    'id': coin.get('id'),
                    'price_btc': coin.get('price_btc'),
                    'score': 7.0
                })
            
            logger.info(f"Fetched {len(solana_candidates)} global trending coins from CoinGecko")
            return solana_candidates
            
        except Exception as e:
            logger.error(f"CoinGecko trending fetch failed: {e}")
            return []

    async def get_new_listings(self) -> List[Dict]:
        """Fetch recently added coins (Async)"""
        try:
            url = f"{self.BASE_URL}/coins/list/new"
            response = await self.client.get(url)
            if response.status_code == 404:
                return []
            
            response.raise_for_status()
            return response.json()
            
        except Exception:
            return []

    async def close(self):
        """Close the httpx client"""
        await self.client.aclose()

if __name__ == "__main__":
    async def main():
        client = CoinGeckoClient()
        res = await client.get_trending_solana()
        print(f"Found {len(res)} trending coins")
        await client.close()
        
    asyncio.run(main())
