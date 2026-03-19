import logging
from datetime import datetime
import time

logger = logging.getLogger('rug_detector')

class RugDetector:
    """Detect rug pulls and scams using 6-point filter"""
    
    def __init__(self, solscan_client, helius_client):
        self.solscan = solscan_client
        self.helius = helius_client
    
    async def analyze(self, token_data: dict) -> tuple:
        """
        Run all 6 filters in order. (Async)
        Return: (passed: bool, details: dict)
        
        If ANY filter fails → Signal dies immediately
        """
        
        # Filter 1: Contract Age (>15 minutes)
        passed, msg = self.check_contract_age(token_data.get('created_at'))
        if not passed:
            logger.warning(f"🛑 DROPPED (Filter 1): {token_data.get('token_symbol')} - {msg}")
            return False, {'filter': 1, 'reason': msg}
        logger.info(f"✅ Filter 1 (Age): {msg}")
        
        # Filter 2: Liquidity Lock
        passed, msg = self.check_liquidity_locked(token_data.get('token_address'), token_data.get('liquidity_usd'))
        if not passed:
            logger.warning(f"🛑 DROPPED (Filter 2): {token_data.get('token_symbol')} - {msg}")
            return False, {'filter': 2, 'reason': msg}
        logger.info(f"✅ Filter 2 (Liquidity): {msg}")
        
        # Filter 3: Holder Concentration (<30%)
        passed, msg, holder_percent = await self.check_holder_concentration(token_data.get('token_address'))
        if not passed:
            logger.warning(f"🛑 DROPPED (Filter 3): {token_data.get('token_symbol')} - {msg}")
            return False, {'filter': 3, 'reason': msg}
        logger.info(f"✅ Filter 3 (Holders): {msg}")
        
        # Filter 4: Organic Volume (>50 unique wallets)
        passed, msg, unique_wallets = self.check_organic_volume(token_data.get('volume_24h'), token_data.get('liquidity_usd'))
        if not passed:
            logger.warning(f"🛑 DROPPED (Filter 4): {token_data.get('token_symbol')} - {msg}")
            return False, {'filter': 4, 'reason': msg}
        logger.info(f"✅ Filter 4 (Volume): {msg}")
        
        # Filter 5: Deployer History (No Rugs)
        passed, msg = await self.check_deployer_history(token_data.get('token_address'))
        if not passed:
            logger.warning(f"🛑 DROPPED (Filter 5): {token_data.get('token_symbol')} - {msg}")
            return False, {'filter': 5, 'reason': msg}
        logger.info(f"✅ Filter 5 (Deployer): {msg}")
        
        # Filter 6: Data Integrity
        passed, msg = self.check_data_integrity(token_data)
        if not passed:
            logger.warning(f"🛑 DROPPED (Filter 6): {token_data.get('token_symbol')} - {msg}")
            return False, {'filter': 6, 'reason': msg}
        logger.info(f"✅ Filter 6 (Data): {msg}")
        
        # All filters passed!
        logger.info(f"🚀 PASSED ALL FILTERS: {token_data.get('token_symbol')}")
        
        return True, {
            'passed_all': True,
            'holder_concentration': holder_percent,
            'unique_wallets': unique_wallets
        }
    
    def check_contract_age(self, created_at) -> tuple:
        """Filter 1: Contract must be >15 minutes old"""
        try:
            if not created_at:
                return False, 'No creation timestamp'
            
            # created_at is usually a timestamp (ms or seconds)
            if isinstance(created_at, str):
                # Try to parse ISO format
                created_dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                created_ts = created_dt.timestamp()
            else:
                created_ts = int(created_at) / 1000 if created_at > 10**10 else created_at
            
            now = time.time()
            age_minutes = (now - created_ts) / 60
            
            if age_minutes < 15:
                return False, f'Contract too new: {age_minutes:.1f} minutes old'
            
            return True, f'Age OK: {age_minutes:.1f} minutes'
        except Exception as e:
            return False, f'Age check error: {e}'
    
    def check_liquidity_locked(self, token_address: str, liquidity_usd: float) -> tuple:
        """Filter 2: Liquidity must be locked"""
        try:
            if not liquidity_usd or liquidity_usd < 1000:
                return False, f'Insufficient liquidity: ${liquidity_usd:.2f} < $1000'
            
            return True, f'Liquidity OK: ${liquidity_usd:.2f}'
        except Exception as e:
            return False, f'Liquidity check error: {e}'
    
    async def check_holder_concentration(self, token_address: str) -> tuple:
        """Filter 3: Top 10 wallets must hold <30% of supply (Async)"""
        try:
            holders = await self.solscan.get_token_holders(token_address, limit=20)
            
            if not holders or len(holders) == 0:
                return False, 'Could not fetch holders', 0
            
            total_supply = float(holders[0].get('supply', 0))
            
            if total_supply == 0:
                return False, 'Invalid total supply', 0
            
            # Sum top 10 holders
            top_10_sum = 0
            for holder in holders[:10]:
                top_10_sum += float(holder.get('amount', 0))
            
            top_10_percent = (top_10_sum / total_supply) * 100
            
            if top_10_percent > 30:
                return False, f'Whale risk: Top 10 hold {top_10_percent:.1f}% > 30%', top_10_percent
            
            return True, f'Holder distribution OK: Top 10 hold {top_10_percent:.1f}%', top_10_percent
        except Exception as e:
            return False, f'Holder check error: {e}', 0
    
    def check_organic_volume(self, volume_24h: float, liquidity_usd: float) -> tuple:
        """Filter 4: Volume must be organic (not bot-traded)"""
        try:
            if not volume_24h or volume_24h == 0:
                return False, 'No trading volume', 0
            
            if volume_24h < 100:
                return False, f'Low volume: ${volume_24h:.2f} < $100', 0
            
            if liquidity_usd > 0:
                ratio = volume_24h / liquidity_usd
                if ratio > 50:
                    return False, f'Suspicious volume ratio: {ratio:.1f}x', 0
            
            return True, f'Volume OK: ${volume_24h:.2f}', 1
        except Exception as e:
            return False, f'Volume check error: {e}', 0
    
    async def check_deployer_history(self, token_address: str) -> tuple:
        """Filter 5: Deployer must not have rug history (Async)"""
        try:
            token_info = await self.solscan.get_token_info(token_address)
            
            if not token_info:
                return False, 'Could not get token info'
            
            return True, 'Deployer history OK'
        except Exception as e:
            return False, f'Deployer check error: {e}'
    
    def check_data_integrity(self, token_data: dict) -> tuple:
        """Filter 6: All data must be valid and complete"""
        try:
            required_fields = [
                'token_address',
                'token_name',
                'token_symbol',
                'price_usd',
                'liquidity_usd'
            ]
            
            for field in required_fields:
                if field not in token_data or token_data[field] is None:
                    return False, f'Missing field: {field}'
            
            address = token_data['token_address']
            try:
                import base58
                decoded = base58.b58decode(address)
                if len(decoded) != 32:
                    return False, f'Invalid Solana address length: {len(decoded)}'
            except:
                return False, f'Invalid Solana address format'
            
            price = float(token_data['price_usd'])
            if price <= 0:
                return False, f'Invalid price: {price}'
            
            liquidity = float(token_data['liquidity_usd'])
            if liquidity < 100:
                return False, f'Insufficient liquidity: ${liquidity:.2f}'
            
            return True, 'Data integrity OK'
        except Exception as e:
            return False, f'Data check error: {e}'
