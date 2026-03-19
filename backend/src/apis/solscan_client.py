import httpx
import logging
import asyncio
import time
import os

logger = logging.getLogger('solscan')

class SolscanClient:
    """Fetch on-chain data from Solscan"""
    
    BASE_URL = 'https://api.solscan.io/api'
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv('SOLSCAN_API_KEY', '')
        self.headers = {'token': self.api_key} if self.api_key else {}
        self.client = httpx.AsyncClient(headers=self.headers, timeout=10.0)
        self.last_request_time = 0
        self.min_interval = 0.5
    
    async def _rate_limit(self):
        """Respect rate limits"""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.min_interval:
            await asyncio.sleep(self.min_interval - elapsed)
        self.last_request_time = time.time()
    
    async def get_token_info(self, token_address: str):
        """Get token metadata and info"""
        try:
            await self._rate_limit()
            
            url = f'{self.BASE_URL}/token/meta'
            params = {'tokenAddress': token_address}
            
            response = await self.client.get(url, params=params)
            response.raise_for_status()
            
            data = response.json()
            if data.get('success'):
                return data.get('data', {})
            else:
                logger.warning(f'Token info not found: {token_address}')
                return {}
                
        except Exception as e:
            logger.error(f'Error getting token info: {e}')
            return {}
    
    async def get_token_holders(self, token_address: str, limit: int = 100):
        """Get top token holders"""
        try:
            await self._rate_limit()
            
            url = f'{self.BASE_URL}/token/holders'
            params = {
                'tokenAddress': token_address,
                'limit': limit
            }
            
            response = await self.client.get(url, params=params)
            response.raise_for_status()
            
            data = response.json()
            if data.get('success'):
                holders = data.get('data', {}).get('holders', [])
                total_supply = float(data.get('data', {}).get('supply', 0))
                
                # Add supply to first item for easy access
                if holders:
                    holders[0]['supply'] = total_supply
                
                return holders
            else:
                logger.warning(f'Could not fetch holders for {token_address}')
                return []
                
        except Exception as e:
            logger.error(f'Error getting token holders: {e}')
            return []

    async def get_top_holders(self, token_address: str, limit: int = 100):
        """Alias for get_token_holders for Agent 3 compatibility"""
        return await self.get_token_holders(token_address, limit)
    
    async def get_wallet_created_tokens(self, wallet_address: str):
        """Get tokens created by a wallet"""
        try:
            await self._rate_limit()
            
            url = f'{self.BASE_URL}/account/splTokens'
            params = {'account': wallet_address}
            
            response = await self.client.get(url, params=params)
            response.raise_for_status()
            
            data = response.json()
            if data.get('success'):
                return data.get('data', [])
            else:
                logger.warning(f'No tokens found for wallet: {wallet_address}')
                return []
                
        except Exception as e:
            logger.error(f'Error getting wallet tokens: {e}')
            return []
    
    async def get_transaction_details(self, tx_hash: str):
        """Get transaction details"""
        try:
            await self._rate_limit()
            
            url = f'{self.BASE_URL}/tx'
            params = {'tx': tx_hash}
            
            response = await self.client.get(url, params=params)
            response.raise_for_status()
            
            data = response.json()
            if data.get('success'):
                return data.get('data', {})
            else:
                return {}
                
        except Exception as e:
            logger.error(f'Error getting transaction: {e}')
            return {}

    async def get_token_age(self, token_address: str):
        try:
            url = f"https://api.solscan.io/token/meta?token={token_address}"
            async with httpx.AsyncClient() as client:
                response = await client.get(url, timeout=10)
                data = response.json()
            result = data.get('result')
            if result:
                deploy_timestamp = result.get('deployedTime', 0)
                if deploy_timestamp > 0:
                    age_seconds = time.time() - deploy_timestamp
                    return {'age_minutes': age_seconds / 60}
            return {'age_minutes': 0}
        except:
            return {'age_minutes': 0}

    async def get_deployer_history(self, deployer_address: str, limit: int = 50):
        try:
            url = f"https://api.solscan.io/account/tokens?account={deployer_address}&limit={limit}"
            async with httpx.AsyncClient() as client:
                response = await client.get(url, timeout=10)
                data = response.json()
            if 'result' in data:
                return [{'token_address': t.get('mint'), 'token_lifetime_hours': 1} for t in data.get('result', [])]
            return []
        except:
            return []
    async def close(self):
        """Close the httpx client"""
        await self.client.aclose()
