#!/usr/bin/env python3
"""
RSS Feed Client for Researcher Agent (Agent 1)
Fetches and parses headlines from major crypto news outlets.
"""

import feedparser
import logging
import httpx
import asyncio
from typing import List, Dict
from datetime import datetime

logger = logging.getLogger('rss_client')

class RSSClient:
    """Interface for crypto news RSS feeds"""
    
    DEFAULT_FEEDS = [
        "https://www.coindesk.com/arc/outboundfeeds/rss/",
        "https://cointelegraph.com/rss",
        "https://cryptoslate.com/feed",
        "https://bitcoinmagazine.com/.rss/full/",
        "https://decrypt.co/feed"
    ]
    
    # Keyword list for discovery
    KEYWORDS = ["launch", "trending", "solana", "listing", "partnership", "utility", "meme"]
    
    def __init__(self, feeds: List[str] = None):
        self.feeds = feeds or self.DEFAULT_FEEDS
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        self.client = httpx.AsyncClient(headers=self.headers, follow_redirects=True, timeout=10.0)
        
    async def get_latest_headlines(self) -> List[Dict]:
        """Fetch and parse headlines from all feeds (Async)"""
        headlines = []
        
        tasks = [self._fetch_feed(url) for url in self.feeds]
        feed_results = await asyncio.gather(*tasks)
        
        for feed_data in feed_results:
            if feed_data:
                headlines.extend(feed_data)
                
        logger.info(f"Fetched {len(headlines)} news headlines from RSS feeds")
        return headlines

    async def _fetch_feed(self, url: str) -> List[Dict]:
        """Internal helper to fetch and parse a single feed"""
        try:
            response = await self.client.get(url)
            response.raise_for_status()
            
            feed = feedparser.parse(response.text)
            feed_headlines = []
            
            for entry in feed.entries[:10]:
                title = entry.get('title', '').lower()
                summary = entry.get('summary', '').lower()
                
                found_keywords = [kw for kw in self.KEYWORDS if kw in title or kw in summary]
                
                if found_keywords:
                    feed_headlines.append({
                        'source': 'rss_news',
                        'feed': url,
                        'title': entry.get('title'),
                        'link': entry.get('link'),
                        'published': entry.get('published'),
                        'keywords': found_keywords,
                        'score': 6.5
                    })
            return feed_headlines
        except Exception as e:
            logger.error(f"Failed to fetch RSS feed {url}: {e}")
            return []

    async def close(self):
        """Close the httpx client"""
        await self.client.aclose()

if __name__ == "__main__":
    async def main():
        client = RSSClient()
        res = await client.get_latest_headlines()
        for h in res[:5]:
            print(f"[{h['keywords']}] {h['title']}")
        await client.close()
    
    import asyncio
    asyncio.run(main())
