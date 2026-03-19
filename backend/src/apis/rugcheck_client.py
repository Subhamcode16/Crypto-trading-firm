#!/usr/bin/env python3
"""Rugcheck API Client - Free tier: ~50 checks/day"""

import httpx
import logging

logger = logging.getLogger(__name__)


class RugcheckClient:
    """Free Rugcheck API integration"""
    
    def __init__(self):
        self.base_url = "https://api.rugcheck.xyz/v1"
        self.client = httpx.AsyncClient(timeout=10.0)
    
    async def get_pool_info(self, token_address: str):
        """Check liquidity lock status"""
        try:
            url = f"{self.base_url}/tokens/{token_address}/pools"
            response = await self.client.get(url)
            data = response.json()
            pools = data.get('pools', [])
            if pools:
                pool = pools[0]
                return {
                    'liquidity_locked': pool.get('locked', False),
                    'lock_duration_days': pool.get('lockDays', 0)
                }
            return {'liquidity_locked': False, 'lock_duration_days': 0}
        except Exception as e:
            logger.warning(f"Error checking pool info: {e}")
            return {'liquidity_locked': False, 'lock_duration_days': 0}
    
    async def get_mint_authority(self, token_address: str):
        """Check mint authority status"""
        try:
            url = f"{self.base_url}/tokens/{token_address}"
            response = await self.client.get(url)
            data = response.json()
            mint_authority = data.get('mint_authority')
            
            if not mint_authority or mint_authority == '0x0':
                return {'status': 'burned'}
            elif mint_authority:
                return {'status': 'active'}
            else:
                return {'status': 'renounced'}
        except Exception as e:
            logger.warning(f"Error checking mint authority: {e}")
            return {'status': 'unknown'}
    
    async def get_freeze_authority(self, token_address: str):
        """Check freeze authority status"""
        try:
            url = f"{self.base_url}/tokens/{token_address}"
            response = await self.client.get(url)
            data = response.json()
            freeze_authority = data.get('freeze_authority')
            
            if not freeze_authority or freeze_authority == '0x0':
                return {'status': 'disabled'}
            else:
                return {'status': 'active'}
        except Exception as e:
            logger.warning(f"Error checking freeze authority: {e}")
            return {'status': 'unknown'}
    
    async def get_deployer_rug_count(self, deployer_address: str):
        """Check if deployer has previous rugs"""
        try:
            url = f"{self.base_url}/accounts/{deployer_address}/risks"
            response = await self.client.get(url)
            data = response.json()
            rug_count = data.get('rugCount', 0)
            return rug_count
        except Exception as e:
            logger.warning(f"Error checking deployer rugs: {e}")
            return 0

    async def close(self):
        """Close the httpx client"""
        await self.client.aclose()
