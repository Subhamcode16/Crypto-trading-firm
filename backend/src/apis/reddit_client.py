#!/usr/bin/env python3
"""
Reddit Client for Researcher Agent (Agent 1)
Scans subreddits for new token contract addresses and ticker mentions.
"""

import re
import httpx
import logging
import asyncio
from typing import List, Dict, Optional
from datetime import datetime

logger = logging.getLogger('reddit_client')

class RedditClient:
    """Interface for Reddit crypto-subreddit scanning"""
    
    SUBREDDITS = [
        "cryptomoonshots",
        "solana",
        "SatoshisStreetBets",
        "CryptoCurrency",
        "SolanaCoins"
    ]
    
    # Regex for Solana Contract Address (CA)
    SOL_CA_PATTERN = r'[1-9A-HJ-NP-Za-km-z]{32,44}'
    
    def __init__(self, client_id: Optional[str] = None, client_secret: Optional[str] = None):
        self.client_id = client_id
        self.client_secret = client_secret
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        self.client = httpx.AsyncClient(headers=self.headers, timeout=10.0)
        
    async def scan_subreddits(self) -> List[Dict]:
        """Scan subreddits for CA and tickers using public .json endpoints (Async)"""
        all_candidates = []
        
        tasks = [self._scan_subreddit(sub) for sub in self.SUBREDDITS]
        results = await asyncio.gather(*tasks)
        
        for sub_candidates in results:
            all_candidates.extend(sub_candidates)
                
        return all_candidates

    async def _scan_subreddit(self, sub: str) -> List[Dict]:
        """Internal helper to scan a single subreddit"""
        candidates = []
        try:
            url = f"https://www.reddit.com/r/{sub}/new.json?limit=25"
            response = await self.client.get(url)
            
            if response.status_code == 404:
                logger.warning(f"Subreddit r/{sub} not found (404)")
                return []
            
            response.raise_for_status()
            
            data_json = response.json()
            if not data_json or 'data' not in data_json:
                return []
                
            posts = data_json.get('data', {}).get('children', [])
            
            for post in posts:
                data = post.get('data', {})
                text = f"{data.get('title', '')} {data.get('selftext', '')}"
                
                # Search for Solana addresses
                addresses = [a for a in re.findall(self.SOL_CA_PATTERN, text) if len(a) >= 32]
                
                if addresses:
                    for addr in set(addresses):
                        candidates.append({
                            'source': 'reddit_post',
                            'subreddit': sub,
                            'address': addr,
                            'title': data.get('title'),
                            'created_at': datetime.fromtimestamp(data.get('created_utc', 0)).isoformat(),
                            'score': 6.0,
                            'mentions': 1
                        })
                        
            logger.info(f"r/{sub}: Scanned {len(posts)} posts, found {len(candidates)} candidates")
        except Exception as e:
            logger.error(f"Failed to scan r/{sub}: {e}")
        return candidates

    async def close(self):
        """Close the httpx client"""
        await self.client.aclose()

if __name__ == "__main__":
    async def main():
        client = RedditClient()
        res = await client.scan_subreddits()
        for c in res[:5]:
            print(f"Candidate: {c['address']} from r/{c['subreddit']}")
        await client.close()
    
    import asyncio
    asyncio.run(main())
