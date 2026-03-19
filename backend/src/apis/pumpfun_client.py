#!/usr/bin/env python3
"""
pump.fun Client for Agent 1 (Researcher)
Monitors new token launches on pump.fun — the EARLIEST signal source.
Most viral Solana memecoins launch here before they hit DEXs or news.
"""

import httpx
import logging
import asyncio
from typing import List, Dict, Optional
from datetime import datetime, timezone

logger = logging.getLogger('pumpfun_client')

class PumpFunClient:
    """
    Monitors pump.fun for new token launches.
    
    Signals we extract:
    - New token creation events
    - Bonding curve progress (0% -> 100%)
    - Early buyer activity
    - Liquidity unlock events
    """

    # pump.fun API endpoints
    BASE_API = "https://frontend-api-v3.pump.fun"
    ADVANCED_API = "https://advanced-api-v2.pump.fun"

    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9",
            "Origin": "https://pump.fun",
            "Referer": "https://pump.fun/",
            "Sec-Ch-Ua": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"Windows"',
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-site"
        }
        self.client = httpx.AsyncClient(headers=self.headers, timeout=10.0)

    async def get_newest_tokens(self, limit: int = 50) -> List[Dict]:
        """
        Fetch the newest token launches from pump.fun v3. (Async)
        """
        try:
            url = f"{self.BASE_API}/coins"
            params = {
                "limit": limit,
                "offset": 0,
                "sort": "created_timestamp",
                "order": "DESC",
                "includeNsfw": "false"
            }
            
            response = await self.client.get(url, params=params)
            if response.status_code != 200:
                logger.error(f"[PUMPFUN] API v3 block or error: {response.status_code}")
                return []
            
            data = response.json()
            return [self._parse_coin(c) for c in data if self._parse_coin(c)]
            
        except Exception as e:
            logger.error(f"[PUMPFUN] Failed to fetch newest tokens: {e}")
            return []

    async def get_trending_tokens(self, limit: int = 20) -> List[Dict]:
        """
        Fetch currently live/trending tokens using v3 'currently-live' endpoint. (Async)
        """
        try:
            url = f"{self.BASE_API}/coins/currently-live"
            params = {
                "limit": limit,
                "offset": 0,
                "includeNsfw": "false"
            }
            
            response = await self.client.get(url, params=params)
            if response.status_code == 200:
                data = response.json()
                return [self._parse_coin(c) for c in data if self._parse_coin(c)]
            
            # Fallback
            return await self.get_newest_tokens(limit=limit)
            
        except Exception as e:
            logger.error(f"[PUMPFUN] Failed to fetch trending tokens: {e}")
            return []

    async def get_token_details(self, mint_address: str) -> Optional[Dict]:
        """
        Get detailed info for a specific pump.fun token. (Async)
        """
        try:
            url = f"{self.BASE_API}/coins/{mint_address}"
            response = await self.client.get(url)
            if response.status_code == 200:
                return self._parse_coin(response.json())
        except Exception as e:
            logger.error(f"[PUMPFUN] Failed to get token details for {mint_address}: {e}")
        return None

    async def get_advanced_metadata(self, mint_address: str) -> Optional[Dict]:
        """
        Get advanced analytics for a token. (Async)
        """
        try:
            url = f"{self.ADVANCED_API}/coins/metadata/{mint_address}"
            response = await self.client.get(url)
            if response.status_code == 200:
                return response.json()
        except:
            pass
        return None

    async def get_top_holders_depth(self, mint_address: str) -> List[Dict]:
        """
        Get detailed holder list with SOL balances. (Async)
        """
        try:
            url = f"{self.ADVANCED_API}/coins/top-holders-and-sol-balance/{mint_address}"
            response = await self.client.get(url)
            if response.status_code == 200:
                return response.json()
        except:
            pass
        return []

    async def get_king_of_hill(self) -> Optional[Dict]:
        """
        Get the current 'King of the Hill' via v3. (Async)
        """
        try:
            url = f"{self.BASE_API}/coins/king-of-the-hill"
            params = {"includeNsfw": "false"}
            response = await self.client.get(url, params=params)
            if response.status_code == 200:
                return self._parse_coin(response.json())
        except:
            pass
        return None

    async def close(self):
        """Close the httpx client"""
        await self.client.aclose()

    def score_token(self, token: Dict) -> float:
        """Calculate a launch quality score."""
        score = 5.0
        bonding_pct = token.get('bonding_curve_pct', 0)
        mc_usd = token.get('usd_market_cap', 0)
        
        if bonding_pct >= 95: score += 3.0
        elif bonding_pct >= 80: score += 2.0
        elif bonding_pct >= 50: score += 1.0
        elif bonding_pct < 5: score -= 0.5

        if mc_usd > 50_000: score += 1.0
        elif mc_usd < 2_000: score -= 1.0

        if token.get('reply_count', 0) > 50: score += 1.0
        
        return max(0.0, min(10.0, score))

    def _parse_coin(self, raw: Dict) -> Optional[Dict]:
        """Normalize pump.fun coin data into standard format."""
        if not raw or not raw.get('mint'):
            return None
            
        try:
            # v3 provides direct virtual_sol_reserves and usd_market_cap
            v_sol = raw.get('virtual_sol_reserves', 0)
            bonding_pct = 0.0
            if v_sol > 0:
                # 85 SOL is the graduation threshold
                bonding_pct = min(100.0, (v_sol / 1e9) / 85 * 100)

            token = {
                'source': 'pumpfun',
                'address': raw.get('mint'),
                'symbol': raw.get('symbol', 'UNKNOWN'),
                'name': raw.get('name', ''),
                'description': raw.get('description', ''),
                'market_cap_sol': raw.get('market_cap', 0),
                'usd_market_cap': raw.get('usd_market_cap', 0),
                'market_cap_usd': raw.get('usd_market_cap', 0), # Alias for compatibility
                'bonding_curve_pct': round(bonding_pct, 1),
                'bonding_curve_key': raw.get('bonding_curve'),
                'creator': raw.get('creator'),
                'reply_count': raw.get('reply_count', 0),
                'created_at': raw.get('created_timestamp'),
                'complete': raw.get('complete', False),
                'is_currently_live': raw.get('is_currently_live', False),
                'image_url': raw.get('image_uri'),
                'twitter': raw.get('twitter'),
                'telegram': raw.get('telegram'),
                'website': raw.get('website'),
                'ath_market_cap': raw.get('ath_market_cap', 0),
                'score': 5.0
            }
            
            token['score'] = self.score_token(token)
            return token
            
        except Exception as e:
            logger.error(f"[PUMPFUN] Parse error: {e}")
            return None


if __name__ == "__main__":
    async def main():
        logging.basicConfig(level=logging.INFO)
        client = PumpFunClient()
        
        print("=== Testing API v3 & Advanced Analytics ===")
        
        print("\n1. Fetching Newest...")
        try:
            tokens = await client.get_newest_tokens(limit=3)
            if not tokens:
                print("   No tokens found (check headers).")
            for t in tokens:
                print(f"   {t['symbol']} | Bonding: {t['bonding_curve_pct']}% | USD MC: ${t['usd_market_cap']:,.0f}")
                
                # Test Advanced Analytics
                print(f"   -> Fetching Advanced Depth for {t['symbol']}...")
                holders = await client.get_top_holders_depth(t['address'])
                if holders:
                    print(f"      Found {len(holders)} top holders with analytics.")
        except Exception as e:
            print(f"   Error in test: {e}")
        
        print("\n2. King of the Hill...")
        try:
            king = await client.get_king_of_hill()
            if king:
                print(f"   KOTH: {king['symbol']} | Score: {king['score']:.1f}/10")
            else:
                print("   KOTH fetch failed.")
        except Exception as e:
            print(f"   Error: {e}")
            
        await client.close()

    asyncio.run(main())
