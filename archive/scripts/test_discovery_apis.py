#!/usr/bin/env python3
"""
Comprehensive End-to-End Test for Discovery APIs
Tests CoinGecko, Reddit, RSS, Pump.fun, and optionally Discord.
"""

import os
import sys
import logging
import asyncio
from pprint import pprint
from dotenv import load_dotenv

sys.path.insert(0, '.')

# Load environment variables
load_dotenv('secrets.env')

from src.apis.coingecko_client import CoinGeckoClient
from src.apis.reddit_client import RedditClient
from src.apis.rss_client import RSSClient
from src.apis.pumpfun_client import PumpFunClient
from src.apis.discord_client import AsyncDiscordClient

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('api_test')

async def test_all():
    print("="*60)
    print("🚀 DISCOVERY API END-TO-END VERIFICATION")
    print("="*60)
    
    # 1. CoinGecko API
    print("\n[1] Testing CoinGecko API (Trending Tokens)")
    try:
        cg = CoinGeckoClient()
        trending = cg.get_trending_tokens()
        solana_tokens = [t for t in trending if t.get('network') == 'solana']
        print(f"✅ Found {len(trending)} trending tokens globally, {len(solana_tokens)} on Solana.")
        if solana_tokens:
            print(f"Sample: {solana_tokens[0]['symbol']} - Address: {solana_tokens[0]['address']}")
    except Exception as e:
        print(f"❌ CoinGecko Error: {e}")
        
    # 2. Reddit API
    print("\n[2] Testing Reddit API (Crypto/Solana Subreddits)")
    try:
        reddit = RedditClient()
        reddit_candidates = reddit.scan_subreddits()
        print(f"✅ Scanned Reddit, found {len(reddit_candidates)} candidates.")
        if reddit_candidates:
            print(f"Sample CA: {reddit_candidates[0]['address'][:20]}... Score: {reddit_candidates[0]['score']}")
    except Exception as e:
        print(f"❌ Reddit Error: {e}")

    # 3. RSS News API
    print("\n[3] Testing RSS News Feeds")
    try:
        rss = RSSClient()
        news_candidates = rss.fetch_latest_news()
        print(f"✅ Scanned RSS Feeds, found {len(news_candidates)} candidates/mentions.")
        if news_candidates:
            print(f"Sample Keyword Mentions: {news_candidates[0]['keywords_found']}")
    except Exception as e:
        print(f"❌ RSS Error: {e}")
        
    # 4. Pump.fun API
    print("\n[4] Testing pump.fun API")
    try:
        pf = PumpFunClient()
        new_tokens = pf.get_newest_tokens(limit=5)
        print(f"✅ Fetched {len(new_tokens)} newest pump.fun tokens.")
        if new_tokens:
            t = new_tokens[0]
            print(f"Sample: {t['symbol']} | Bonding: {t['bonding_curve_pct']}% | Score: {t['score']:.1f}/10")
            
        koth = pf.get_king_of_hill()
        if koth:
            print(f"✅ King of the Hill: {koth['symbol']} | Bonding: {koth['bonding_curve_pct']}%")
    except Exception as e:
        print(f"❌ Pump.fun Error: {e}")

    # 5. Discord API (Optional)
    print("\n[5] Testing Discord API")
    discord_token = os.getenv('DISCORD_BOT_TOKEN')
    if discord_token:
        try:
            print("⏳ Attempting Discord connection...")
            discord_client = AsyncDiscordClient(discord_token)
            success = await discord_client.initialize()
            if success:
                print("✅ Successfully connected to Discord bot.")
                # We won't test a specific server unless we pass a known name,
                # just validating auth here
                print("Disconnecting...")
                await discord_client.cleanup()
            else:
                print("❌ Failed to connect explicitly.")
        except Exception as e:
            print(f"❌ Discord test failed: {e}")
    else:
        print("⚠️ Skipped: DISCORD_BOT_TOKEN not found in secrets.env")
        

    print("\n" + "="*60)
    print("✅ TEST SUITE COMPLETED")
    print("="*60)

if __name__ == "__main__":
    asyncio.run(test_all())
