import httpx
import logging
import asyncio
import os

logger = logging.getLogger('helius')

class HeliusRPCClient:
    """Interact with Solana blockchain via Helius RPC"""
    
    def __init__(self, rpc_url: str = None):
        self.rpc_url = rpc_url or os.getenv('HELIUS_RPC_URL', 'https://api.mainnet-beta.solana.com')
        self.client = httpx.AsyncClient(timeout=10.0)
    
    async def _make_request(self, method: str, params: list = None, timeout: int = 10):
        """Make JSON-RPC request to Solana (Async)"""
        try:
            payload = {
                'jsonrpc': '2.0',
                'id': 1,
                'method': method,
                'params': params or []
            }
            
            response = await self.client.post(self.rpc_url, json=payload)
            response.raise_for_status()
            
            data = response.json()
            
            if 'error' in data:
                logger.error(f'RPC error: {data["error"]}')
                return None
            
            return data.get('result')
            
        except Exception as e:
            logger.error(f'RPC request failed: {e}')
            return None

    async def close(self):
        """Close the httpx client"""
        await self.client.aclose()
    
    async def get_token_metadata(self, token_address: str):
        """Get token metadata (Async)"""
        try:
            result = await self._make_request('getMint', [token_address])
            return result if result else {}
        except Exception as e:
            logger.error(f'Error getting token metadata: {e}')
            return {}
    
    async def get_account_info(self, account_address: str):
        """Get account information (Async)"""
        try:
            result = await self._make_request('getAccountInfo', [account_address])
            return result if result else {}
        except Exception as e:
            logger.error(f'Error getting account info: {e}')
            return {}
    
    async def get_recent_transactions(self, wallet_address: str, limit: int = 100):
        """Get recent transactions for an address (Async)"""
        try:
            result = await self._make_request(
                'getSignaturesForAddress',
                [wallet_address, {'limit': limit}]
            )
            return result if result else []
        except Exception as e:
            logger.error(f'Error getting recent transactions: {e}')
            return []
    
    async def get_token_accounts_by_owner(self, owner_address: str, token_program_id: str = 'TokenkegQfeZyiNwAJsyFbPVwwQQYoNDAs2ayHgaQQc'):
        """Get all token accounts owned by an address (Async)"""
        try:
            result = await self._make_request(
                'getTokenAccountsByOwner',
                [owner_address, {'programId': token_program_id}]
            )
            return result if result else {}
        except Exception as e:
            logger.error(f'Error getting token accounts: {e}')
            return {}
    
    async def get_slot(self):
        """Get current slot number (Async)"""
        try:
            result = await self._make_request('getSlot')
            return result
        except Exception as e:
            logger.error(f'Error getting slot: {e}')
            return None
    
    async def get_block_time(self, slot: int):
        """Get block time for a slot (Async)"""
        try:
            result = await self._make_request('getBlockTime', [slot])
            return result
        except Exception as e:
            logger.error(f'Error getting block time: {e}')
            return None
