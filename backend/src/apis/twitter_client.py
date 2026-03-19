#!/usr/bin/env python3
"""
Twitter/X Client for Researcher Agent (Agent 1)
Scaffolds search and list monitoring for Solana contract addresses.
"""

import httpx
import logging
from typing import List, Dict, Optional
import asyncio

logger = logging.getLogger('twitter_client')

class TwitterClient:
    """Interface for Twitter/X Search API V2"""
    
    BASE_URL = "https://api.twitter.com/2"
    
    def __init__(self, bearer_token: Optional[str] = None):
        if not bearer_token:
            logger.warning("Twitter Bearer Token missing. Twitter/X discovery will be disabled.")
        self.bearer_token = bearer_token
        self.headers = {
            "Authorization": f"Bearer {bearer_token}" if bearer_token else "",
            "User-Agent": "v2RecentSearchPython"
        }
        self.client = httpx.AsyncClient(headers=self.headers, timeout=10.0)
        
    async def search_solana_keywords(self) -> List[Dict]:
        """Search for Solana contract addresses in recent tweets"""
        if not self.bearer_token:
            return []
            
        # Example query: (Solana OR SOL) (address OR CA OR "contract address") -is:retweet
        # This requires V2 Bearer Token
        try:
            url = f"{self.BASE_URL}/tweets/search/recent"
            params = {
                'query': '(Solana OR SOL) (address OR CA OR "contract address") -is:retweet',
                'max_results': 20,
                'tweet.fields': 'created_at,text,author_id'
            }
            
            response = await self.client.get(url, params=params)
            response.raise_for_status()
            
            data = response.json()
            tweets = data.get('data', [])
            
            # Simple parsing for CA
            import re
            ca_pattern = r'[1-9A-HJ-NP-Za-km-z]{32,44}'
            
            all_candidates = []
            for tweet in tweets:
                text = tweet.get('text', '')
                addresses = re.findall(ca_pattern, text)
                
                if addresses:
                    for addr in set(addresses):
                        all_candidates.append({
                            'source': 'twitter_search',
                            'tweet_id': tweet.get('id'),
                            'address': addr,
                            'text': text,
                            'score': 6.5,
                            'created_at': tweet.get('created_at')
                        })
            
            logger.info(f"Twitter: Scanned {len(tweets)} tweets, found {len(all_candidates)} candidates")
            return all_candidates
            
        except Exception as e:
            logger.error(f"Twitter search failed: {e}")
            return []

    async def close(self):
        """Close the httpx client"""
        await self.client.aclose()

if __name__ == "__main__":
    async def main():
        client = TwitterClient()
        print("Twitter client initialized (mock mode if no token)")
        # result = await client.search_solana_keywords()
        await client.close()
    
    asyncio.run(main())
