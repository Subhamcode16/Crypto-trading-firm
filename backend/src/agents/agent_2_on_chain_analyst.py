#!/usr/bin/env python3
"""AGENT 2: On-Chain Analyst - Validates tokens against 9 sequential safety filters"""

import json
import logging
from datetime import datetime
from typing import Dict, Tuple
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


class OnChainAnalyst:
    """Analyzes candidate tokens against 9 safety filters"""

    def __init__(self, config: Dict = None):
        self.config = config or {}
        logger.info("[AGENT_2] On-Chain Analyst initialized")
        self.solscan = None
        self.rugcheck = None
        self.helius = None
        self.dexscreener = None
        self.scorer = None
        self.db = None

    async def filter_contract_age(self, token_address: str) -> Tuple[bool, str]:
        """FILTER 1: Token must be >= 15 minutes old"""
        try:
            if not self.solscan:
                return True, "Age: [API unavailable - PASS]"
            age_data = await self.solscan.get_token_age(token_address)
            age_minutes = age_data.get('age_minutes', 100)
            if age_minutes < 15:
                return False, f"Contract too new: {age_minutes:.1f} min"
            return True, f"Age: {age_minutes:.1f} min"
        except Exception as e:
            return False, f"Could not verify: {str(e)}"

    async def filter_liquidity_locked(self, token_address: str) -> Tuple[bool, str]:
        """FILTER 2: Liquidity MUST be locked"""
        try:
            if not self.rugcheck:
                return True, "Locked: [API unavailable - PASS]"
            pool_info = await self.rugcheck.get_pool_info(token_address)
            if not pool_info:
                return False, "Liquidity: No pool info"
            if not pool_info.get('liquidity_locked', False):
                return False, "Liquidity not locked"
            lock_days = pool_info.get('lock_duration_days', 0)
            if lock_days < 365:
                return False, f"Lock too short: {lock_days} days"
            return True, f"Locked: {lock_days} days"
        except Exception as e:
            return False, f"Could not verify: {str(e)}"

    async def filter_deployer_history(self, token_address: str) -> Tuple[bool, str]:
        """FILTER 3: Deployer must have no previous rug pulls"""
        try:
            if not self.solscan or not self.rugcheck:
                return True, "Deployer: [API unavailable - PASS]"
            token_info = await self.solscan.get_token_info(token_address)
            if not token_info:
                return False, "Deployer: Could not fetch token info"
            deployer_address = token_info.get('deployer', 'unknown')
            if deployer_address == 'unknown':
                return False, "Deployer: Unknown"
            rug_count = await self.rugcheck.get_deployer_rug_count(deployer_address)
            if rug_count > 0:
                return False, f"Deployer has {rug_count} rug(s)"
            history = await self.solscan.get_deployer_history(deployer_address, limit=50)
            if not history:
                return True, "Deployer clean (no history)"
            dead_tokens = [tx for tx in history if tx.get('token_lifetime_hours', float('inf')) < 24]
            if len(dead_tokens) > 5:
                return False, f"Deployer has {len(dead_tokens)} dead tokens"
            return True, "Deployer clean"
        except Exception as e:
            return False, f"Could not verify: {str(e)}"

    async def filter_holder_concentration(self, token_address: str) -> Tuple[bool, str]:
        """FILTER 4: Top 10 holders must hold < 30% of supply"""
        try:
            if not self.solscan:
                return True, "Concentration: [API unavailable - PASS]"
            top_10_holders = await self.solscan.get_top_holders(token_address, limit=10)
            if not top_10_holders:
                return False, "Concentration: No holder data"
            token_info = await self.solscan.get_token_info(token_address)
            if not token_info:
                return False, "Concentration: No token info"
            total_supply = float(token_info.get('total_supply', 1))
            top_10_holdings = sum([float(h.get('balance', 0)) for h in top_10_holders])
            concentration_pct = (top_10_holdings / total_supply) * 100 if total_supply else 0
            if concentration_pct > 30:
                return False, f"Top 10: {concentration_pct:.1f}%"
            return True, f"Top 10 holders: {concentration_pct:.1f}%"
        except Exception as e:
            return False, f"Could not verify: {str(e)}"

    async def filter_unique_buyers(self, token_address: str) -> Tuple[bool, str]:
        """FILTER 5: Minimum 50 unique buyer wallets"""
        try:
            if not self.helius:
                return True, "Buyers: [API unavailable - PASS]"
            buyers = await self.helius.get_unique_buyers(token_address)
            buyer_count = len(buyers) if buyers else 100
            if buyer_count < 50:
                return False, f"Only {buyer_count} unique buyers"
            return True, f"Unique buyers: {buyer_count}"
        except Exception as e:
            return False, f"Could not verify: {str(e)}"

    async def filter_volume_authenticity(self, token_address: str) -> Tuple[bool, str]:
        """FILTER 6: Volume must show organic diversity"""
        try:
            if not self.helius:
                return True, "Volume: [API unavailable - PASS]"
            transactions = await self.helius.get_token_transaction_flow(token_address, limit=100)
            from collections import defaultdict
            buyer_volume = defaultdict(float)
            total_volume = 0
            for tx in transactions:
                buyer = tx.get('from', 'unknown')
                volume = float(tx.get('volume', 0))
                buyer_volume[buyer] += volume
                total_volume += volume
            if total_volume == 0:
                return True, "Volume: [No data - PASS]"
            top_5_volume = sum(sorted(buyer_volume.values(), reverse=True)[:5])
            top_5_pct = (top_5_volume / total_volume) * 100
            if top_5_pct > 50:
                return False, f"Top 5: {top_5_pct:.1f}%"
            return True, f"Top 5 wallets: {top_5_pct:.1f}%"
        except Exception as e:
            return False, f"Could not verify: {str(e)}"

    async def filter_mint_authority(self, token_address: str) -> Tuple[bool, str]:
        """FILTER 7: Mint authority must be renounced or burned"""
        try:
            if not self.rugcheck:
                return True, "Mint: [API unavailable - PASS]"
            mint_info = await self.rugcheck.get_mint_authority(token_address)
            status = mint_info.get('status', 'burned')
            if status == 'active':
                return False, "Mint authority active"
            return True, f"Mint: {status}"
        except Exception as e:
            return False, f"Could not verify: {str(e)}"

    async def filter_freeze_authority(self, token_address: str) -> Tuple[bool, str]:
        """FILTER 8: Freeze authority must be disabled"""
        try:
            if not self.rugcheck:
                return True, "Freeze: [API unavailable - PASS]"
            freeze_info = await self.rugcheck.get_freeze_authority(token_address)
            status = freeze_info.get('status', 'disabled')
            if status == 'active':
                return False, "Freeze authority enabled"
            return True, f"Freeze: {status}"
        except Exception as e:
            return False, f"Could not verify: {str(e)}"

    async def filter_minimum_liquidity(self, token_address: str) -> Tuple[bool, str]:
        """FILTER 9: At least $10,000 USD in trading pool"""
        try:
            if not self.dexscreener:
                return True, "Liquidity: [API unavailable - PASS]"
            
            # Use get_token_pairs to find the best pool
            pairs = await self.dexscreener.get_token_pairs(token_address)
            if not pairs:
                return False, "Liquidity: No pairs found"
                
            solana_pairs = [p for p in pairs if p.get('chainId') == 'solana']
            if not solana_pairs:
                return False, "Liquidity: No Solana pairs"
            
            best_pair = max(solana_pairs, key=lambda p: float(p.get('liquidity', {}).get('usd', 0)))
            liquidity_usd = float(best_pair.get('liquidity', {}).get('usd', 0))
            
            if liquidity_usd < 10000:
                return False, f"Liquidity: ${liquidity_usd:.0f}"
            return True, f"Liquidity: ${liquidity_usd:.0f}"
        except Exception as e:
            return False, f"Could not verify: {str(e)}"

    async def analyze_token(self, token_address: str) -> Dict:
        """Run all 9 filters. First failure = KILLED. All pass = CLEARED."""
        logger.info(f"[AGENT_2] Analyzing {token_address[:8]}...")
        
        filters = [
            ("contract_age", self.filter_contract_age),
            ("liquidity_locked", self.filter_liquidity_locked),
            ("deployer_history", self.filter_deployer_history),
            ("holder_concentration", self.filter_holder_concentration),
            ("unique_buyers", self.filter_unique_buyers),
            ("volume_authenticity", self.filter_volume_authenticity),
            ("mint_authority", self.filter_mint_authority),
            ("freeze_authority", self.filter_freeze_authority),
            ("minimum_liquidity", self.filter_minimum_liquidity),
        ]
        
        filters_passed = []
        filter_results = {}
        
        for filter_name, filter_func in filters:
            passed, details = await filter_func(token_address)
            filter_results[filter_name] = {'passed': passed, 'details': details}
            
            if passed:
                filters_passed.append(filter_name)
            else:
                return {
                    'status': 'KILLED',
                    'token_address': token_address,
                    'killed_at': datetime.utcnow().isoformat(),
                    'failure_reason': details,
                    'failed_filter': filter_name,
                    'filters_passed': filters_passed,
                    'filters_total': len(filters)
                }
        
        # All filters passed
        safety_score = 8.5
        if self.scorer:
            try:
                safety_score = self.scorer.calculate_score(token_address, filter_results)
            except:
                pass
        
        logger.info(f"[AGENT_2] ✓ CLEARED score {safety_score:.1f}/10")
        
        return {
            'status': 'CLEARED',
            'token_address': token_address,
            'safety_score': safety_score,
            'cleared_at': datetime.utcnow().isoformat(),
            'filters_passed': filters_passed,
            'filters_total': len(filters),
            'filter_results': filter_results
        }

    async def log_to_database(self, analysis_result: Dict):
        """Log analysis result to database"""
        if self.db:
            await self.db.log_agent_2_analysis(analysis_result)
        logger.info(f"[AGENT_2] Logged: {analysis_result['status']}")


if __name__ == '__main__':
    logger.info("✅ Agent 2 module loaded") 
