import logging

logger = logging.getLogger(__name__)

class HeliusClient:
    """Mock Helius client for testing"""

    async def get_unique_buyers(self, token_address: str):
        try:
            return [f'wallet_{i}' for i in range(100)]
        except:
            return []
    
    async def get_token_transaction_flow(self, token_address: str, limit: int = 100):
        from datetime import datetime
        try:
            return [{'from': f'wallet_{i}', 'to': 'pool_address', 'volume': 100 + i*10, 'timestamp': datetime.utcnow().isoformat()} for i in range(min(limit, 20))]
        except:
            return []
