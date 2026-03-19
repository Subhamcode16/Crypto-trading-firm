#!/usr/bin/env python3
"""
Birdeye API Client
Provides access to trader rankings and wallet data for Agent 3 (Wallet Tracker)
"""

import httpx
import logging
import os
import urllib3
import asyncio
from typing import Dict, List, Optional
from datetime import datetime
from dotenv import load_dotenv

# Disable warnings for insecure requests if we use verify=False
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger('birdeye')

class BirdeyeClient:
    """
    Connects to Birdeye API for smart wallet detection
    """
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Birdeye client
        """
        load_dotenv('backend/secrets.env')
        
        self.api_key = api_key or os.getenv('BIRDEYE_API_KEY')
        self.base_url = "https://public-api.birdeye.so"
        
        self.headers = {
            "x-chain": "solana",
            "X-API-KEY": self.api_key if self.api_key else "",
            "Accept": "application/json",
            "User-Agent": "birdeyepy/v0.0.9"
        }
        self.client = httpx.AsyncClient(headers=self.headers, timeout=10.0, verify=True)
        
        logger.info(f"[BIRDEYE] Client initialized (Key present: {bool(self.api_key)})")
    
    async def _make_request(self, endpoint: str, params: Dict = None) -> Optional[Dict]:
        """Internal helper for requests with SSL fallback"""
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        try:
            response = await self.client.get(url, params=params)
            
            # Fallback to verify=False if certificate issues arise
            if response.status_code == 401 or response.status_code == 403:
                # Auth issues are not SSL related, don't fallback
                pass
            elif response.status_code == 521 or response.status_code >= 500:
                logger.debug(f"[BIRDEYE] SSL/Origin fallback trial for {endpoint}...")
                async with httpx.AsyncClient(verify=False, headers=self.headers, timeout=10.0) as fallback_client:
                    response = await fallback_client.get(url, params=params)
                
            response.raise_for_status()
            return response.json()
        except Exception as e:
            # Final desperate fallback for SSL issues
            if "certificate" in str(e).lower() or "revocation" in str(e).lower():
                try:
                    async with httpx.AsyncClient(verify=False, headers=self.headers, timeout=10.0) as fallback_client:
                        response = await fallback_client.get(url, params=params)
                    return response.json()
                except: pass
            logger.error(f"[BIRDEYE] Request failed ({endpoint}): {e}")
            return None

    async def get_top_traders(self, limit: int = 20, sort_by: str = "PnL", time_frame: str = "1W") -> List[Dict]:
        """Get top trader wallets using gainers-losers"""
        # Mapping for backward compatibility or common name mismatches
        mapped_sort = "PnL" if sort_by.lower() in ["profit", "pnl"] else sort_by
        
        data = await self._make_request("trader/gainers-losers", {
            "sort_by": mapped_sort, 
            "sort_type": "desc", 
            "offset": 0, 
            "limit": limit,
            "time_frame": time_frame
        })
        if data and data.get('success'):
            items = data.get('data', {}).get('items', [])
            return items if items else []
        return []

    async def get_trending_tokens(self, limit: int = 10) -> List[Dict]:
        """Get trending tokens from Birdeye"""
        data = await self._make_request("defi/token_trending", {"limit": limit})
        if data and data.get('success'):
            tokens = data.get('data', {}).get('tokens', [])
            return tokens if tokens else []
        return []

    async def get_trader_profile(self, wallet_address: str) -> Optional[Dict]:
        """Get profile for trader"""
        data = await self._make_request("traders/profile", {"wallet": wallet_address})
        if data and data.get('success'):
            return data.get('data', {})
        return {"address": wallet_address, "is_placeholder": True}

    async def get_trader_holdings(self, wallet_address: str) -> List[Dict]:
        """Get token holdings for trader"""
        data = await self._make_request("v1/wallet/token_list", {"wallet": wallet_address})
        if data and data.get('success'):
            return data.get('data', {}).get('items', [])
        return []

    async def get_trader_trades(self, wallet_address: str, limit: int = 20) -> List[Dict]:
        """Get recent trades for wallet"""
        data = await self._make_request("v1/wallet/tx_list", {"wallet": wallet_address, "limit": limit})
        if data and data.get('success'):
            return data.get('data', {}).get('items', [])
        return []

    async def is_smart_money(self, wallet_address: str, win_rate_threshold: float = 0.55) -> bool:
        profile = await self.get_trader_profile(wallet_address)
        if not profile or profile.get('is_placeholder'): return True
        win_rate = profile.get('win_rate', 0)
        total_trades = profile.get('total_trades', 0)
        roi = profile.get('roi_percent', 0)
        return (win_rate >= win_rate_threshold and total_trades >= 5 and roi > 0)

    async def score_wallet(self, wallet_address: str) -> Dict:
        profile = await self.get_trader_profile(wallet_address) or {}
        win_rate = profile.get('win_rate', 0)
        total_trades = profile.get('total_trades', 0)
        roi = profile.get('roi_percent', 0)
        score = min(4, win_rate * 10) + min(3, total_trades / 50) + min(3, (roi / 100))
        return {
            "is_smart_money": score > 5,
            "win_rate": win_rate,
            "score": min(10.0, score),
            "profile": profile
        }

    async def close(self):
        """Close the httpx client"""
        await self.client.aclose()

if __name__ == '__main__':
    async def main():
        logging.basicConfig(level=logging.INFO)
        client = BirdeyeClient()
        print("\n--- Birdeye API Test ---")
        traders = await client.get_top_traders(limit=5)
        print(f"Result: {len(traders)} traders found")
        if traders:
            for t in traders:
                addr = t.get('address') or t.get('wallet_address')
                print(f"- Wallet: {addr[:10]}... | PnL: {t.get('PnL', t.get('profit', 'N/A'))}")
        else:
            print("No traders found. Check if API key is valid or if endpoints changed.")
        await client.close()
    
    asyncio.run(main())
