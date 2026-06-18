#!/usr/bin/env python3
"""
AGENT 3: Wallet Tracker - Smart Money Detection
Role: Identify if smart wallets and insiders are accumulating the token
"""

import json
import logging
from datetime import datetime
from typing import Dict, List, Tuple
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

logger = logging.getLogger(__name__)

from src.apis.helius_webhook import HeliusWebhookManager

class Agent3WalletTracker:
    """Detects smart money and insider activity in real-time"""
    
    PRIORITY_WALLETS = [
        "6dnSkU3D9K1vL5T7F9Y2EaQ2kZ7B9yX9wP5M7vH8P9uJ", # Example S-Tier Wallet 1
        "8fN7Q9wL5P4M2X9yX9wP5M7vH8P9uJ6dnSkU3D9K1v", # Example S-Tier Wallet 2
        # ... user would add 10-20 more here
    ]
    
    def __init__(self, config: Dict = None):
        self.config = config or {}
        logger.info("[AGENT_3] Wallet Tracker (The Stalker) initialized")
        
        # Helius Webhook Manager (for real-time monitoring)
        self.helius_key = self.config.get('secrets', {}).get('HELIUS_API_KEY')
        self.webhook_mgr = HeliusWebhookManager(self.helius_key) if self.helius_key else None
        
        self.solscan = None
        self.birdeye = None
        self.helius     = None
        self.db         = None
        self.agent_2    = None  # Will be set to route priority signals
    
    async def process_priority_signal(self, tx_data: Dict) -> Dict:
        """
        PRIORITY FLOW: Direct entry point for Helius Webhook alerts.
        Immediately triggers Agent 2 safety checks.
        """
        token_addr = tx_data.get('address')
        wallet_addr = tx_data.get('wallet')
        
        logger.info(f"🚨 [PRIORITY_ALERT] Smart Wallet {wallet_addr[:8]} bought {token_addr[:8]}")
        
        # Route directly to Agent 2 (On-Chain Analyst)
        if self.agent_2:
            safety_check = await self.agent_2.analyze_token(token_addr)
            
            # If cleared, prepare priority signal for Aggregator
            if safety_check.get('status') == 'CLEARED':
                priority_signal = {
                    'token_address': token_addr,
                    'is_priority': True,
                    'source': 'smart_money_buy',
                    'wallet': wallet_addr,
                    'safety_score': safety_check.get('score'),
                    'narrative_bonus': 1.5 # Wallet accumulation bonus
                }
                logger.info(f"🔥 [AGENT_3] Priority Signal Cleared -> Agent 5")
                return priority_signal
                
        return {"status": "filtered", "reason": "Failed safety check"}
    
    async def get_trending_tokens(self) -> List[Dict]:
        """
        DISCOVERY SOURCE: Smart Money Trending
        Fetches tokens that top traders are currently accumulating.
        """
        try:
            if not self.birdeye:
                return []
            
            # Get list of top traders
            top_traders = await self.birdeye.get_top_traders(limit=20, sort_by="PnL")
            if not top_traders:
                return []
            
            smart_tokens = {}
            for trader in top_traders:
                addr = trader.get('wallet_address')
                if not addr: continue
                
                # Check recent transactions for this wallet
                # (Simplified: look at common holdings for now)
                # In a full impl, we'd use Birdeye's wallet portfolio API
                pass

            # Placeholder for now: Return some high-confidence tokens from Birdeye's general trending
            # that match Solana network requirements
            trending = await self.birdeye.get_trending_tokens(limit=10)
            return trending
            
        except Exception as e:
            logger.error(f"Agent 3 discovery failed: {e}")
            return []
    
    # ============================================================
    # DETECTION LOGIC
    # ============================================================
    
    async def detect_smart_wallets(self, token_address: str) -> Tuple[List[Dict], int]:
        """
        DETECTION 1: Smart Money Wallets
        Check if top traders/smart wallets are buying this token
        
        Returns:
            (list of smart wallets found, points awarded 0-2)
        """
        smart_wallets = []
        points = 0
        
        try:
            if not self.birdeye:
                logger.debug("[AGENT_3] Smart wallet detection: Birdeye unavailable")
                return smart_wallets, 0
            
            if not self.solscan:
                logger.debug("[AGENT_3] Smart wallet detection: Solscan unavailable")
                return smart_wallets, 0
            
            # Get token holder list from Solscan
            top_holders = await self.solscan.get_top_holders(token_address, limit=20)
            
            if not top_holders:
                logger.debug(f"[AGENT_3] No holders found for {token_address}")
                return smart_wallets, 0
            
            # Get top traders from Birdeye
            top_traders = await self.birdeye.get_top_traders(limit=500, sort_by="win_rate")
            
            if not top_traders:
                logger.debug("[AGENT_3] Could not fetch top traders from Birdeye")
                return smart_wallets, 0
            
            # Create a set of top trader addresses for quick lookup
            top_trader_addrs = {t.get('wallet_address', '').lower() for t in top_traders}
            
            # Check each token holder against top traders
            for holder in top_holders:
                holder_addr = holder.get('address', '').lower()
                
                # Check if this holder is a top trader
                if holder_addr in top_trader_addrs:
                    # Get full profile from Birdeye
                    profile = await self.birdeye.get_trader_profile(holder_addr)
                    
                    if profile:
                        smart_wallet_info = {
                            "wallet_address": holder_addr,
                            "wallet_name": profile.get('profile_name', 'Smart Wallet'),
                            "wallet_tier": self._calculate_tier(profile.get('rank', 10000)),
                            "historical_wr": profile.get('win_rate', 0),
                            "total_trades": profile.get('total_trades', 0),
                            "roi_percent": profile.get('roi_percent', 0),
                            "investment_amount": holder.get('balance', 0),
                            "rank": profile.get('rank', 10000)
                        }
                        
                        smart_wallets.append(smart_wallet_info)
                        
                        # Award points based on tier
                        if smart_wallet_info['wallet_tier'] == 'top_10':
                            points += 2
                        elif smart_wallet_info['wallet_tier'] == 'top_50':
                            points += 1
                        else:
                            points += 0.5
                        
                        logger.debug(f"[AGENT_3] Found smart wallet: {smart_wallet_info['wallet_name']} (WR={smart_wallet_info['historical_wr']:.2%})")
            
            # Cap points at 2
            points = min(2, points)
            
            logger.info(f"[AGENT_3] Smart wallets: {len(smart_wallets)} found, {points} points")
            
        except Exception as e:
            logger.warning(f"[AGENT_3] Smart wallet detection failed: {e}")
        
        return smart_wallets, points
    
    async def detect_insider_activity(self, token_address: str) -> Tuple[Dict, int]:
        """
        DETECTION 2: Insider Activity
        Check if deployer and early holders are accumulating or dumping
        
        Returns:
            (activity status dict, points awarded 0-1)
        """
        insider_status = {
            "deployer": None,
            "deployer_action": "unknown",  # "holding", "accumulating", "selling"
            "deployer_balance_change_24h": 0,
            "early_holders_action": "unknown",
            "red_flags": [],
            "green_flags": []
        }
        points = 0
        
        try:
            if not self.solscan:
                logger.debug("[AGENT_3] Insider detection: Solscan unavailable")
                return insider_status, 0
            
            # Get deployer info
            token_info = await self.solscan.get_token_info(token_address)
            if not token_info:
                logger.debug(f"[AGENT_3] No token info found for {token_address}")
                return insider_status, 0
                
            deployer = token_info.get('deployer', 'unknown')
            insider_status['deployer'] = deployer
            
            # Get deployer's current token holdings
            top_holders = await self.solscan.get_top_holders(token_address, limit=20)
            deployer_holding = None
            
            if top_holders:
                for holder in top_holders:
                    if holder.get('address', '').lower() == deployer.lower():
                        deployer_holding = holder.get('balance', 0)
                        break
            
            # Analyze deployer behavior
            if deployer_holding is not None:
                # If deployer holds tokens (especially top 10), they're likely holding/accumulating
                total_supply = token_info.get('total_supply', 1)
                deployer_percentage = (deployer_holding / total_supply * 100) if total_supply else 0
                
                if deployer_percentage > 5:  # Significant holding
                    insider_status['deployer_action'] = "accumulating"
                    insider_status['green_flags'].append("Deployer holds >5% (aligned incentives)")
                    points += 1
                elif deployer_percentage > 0.1:  # Still holding some
                    insider_status['deployer_action'] = "holding"
                    insider_status['green_flags'].append("Deployer holds position")
                    points += 0.5
                else:
                    insider_status['deployer_action'] = "minimal_holding"
                    insider_status['red_flags'].append("Deployer has minimal position")
            else:
                # Deployer not in top 20 holders - either dumped or intentionally low profile
                insider_status['deployer_action'] = "minimal_holding"
                insider_status['red_flags'].append("Deployer not in top 20 holders")
            
            # Check early holders (top 10)
            early_holders = top_holders[:10]
            selling_count = 0
            holding_count = 0
            
            # Heuristic: if early holders have significant holdings, they're likely holding
            for holder in early_holders:
                balance = holder.get('balance', 0)
                if balance > 0:
                    holding_count += 1
            
            if holding_count >= 8:  # 8+ of top 10 still holding
                insider_status['early_holders_action'] = "holding"
                insider_status['green_flags'].append("Early holders accumulating")
            else:
                insider_status['early_holders_action'] = "mixed"
                insider_status['red_flags'].append("Early holders selling/dispersing")
            
            logger.info(f"[AGENT_3] Insider activity: deployer={insider_status['deployer_action']}, early={insider_status['early_holders_action']}, points={points}")
            
        except Exception as e:
            logger.warning(f"[AGENT_3] Insider detection failed: {e}")
        
        # Cap points at 1
        points = min(1, points)
        return insider_status, points
    
    async def detect_copy_trade_signal(self, token_address: str) -> Tuple[Dict, float]:
        """
        DETECTION 3: Copy-Trading Signal
        Check if similar wallets to successful traders bought this token
        
        Returns:
            (copy trade signal dict, points awarded 0-1.5)
        """
        copy_signal = {
            "detected": False,
            "similar_wallets": 0,
            "historical_success_rate": 0.0,
            "profile": "unknown"
        }
        points = 0.0
        
        try:
            if not self.birdeye or not self.solscan:
                logger.debug("[AGENT_3] Copy trade detection: APIs unavailable")
                return copy_signal, 0.0
            
            # Get recent token transactions (buyers)
            if not self.helius:
                logger.debug("[AGENT_3] Copy trade detection: Helius unavailable")
                return copy_signal, 0.0
            
            # Get token transaction flow (recent buyers)
            # Use heliuss's async method
            transactions = await self.helius.get_token_transaction_flow(token_address, limit=50)
            
            if not transactions:
                logger.debug("[AGENT_3] No recent transactions found")
                return copy_signal, 0.0
            
            # Extract unique buyer wallets from recent transactions
            buyer_wallets = {}
            for tx in transactions:
                buyer = tx.get('from', '')
                if buyer:
                    buyer_wallets[buyer] = buyer_wallets.get(buyer, 0) + 1
            
            # Get top traders from Birdeye
            top_traders = await self.birdeye.get_top_traders(limit=100, sort_by="win_rate")
            if not top_traders:
                return copy_signal, 0.0
            top_trader_addrs = {t.get('wallet_address', '').lower() for t in top_traders}
            
            # Check if any recent buyers match top traders
            matching_wallets = []
            total_success_rates = 0
            
            for buyer in buyer_wallets.keys():
                if buyer.lower() in top_trader_addrs:
                    profile = await self.birdeye.get_trader_profile(buyer)
                    if profile:
                        win_rate = profile.get('win_rate', 0)
                        matching_wallets.append({
                            'wallet': buyer,
                            'win_rate': win_rate,
                            'tier': self._calculate_tier(profile.get('rank', 10000))
                        })
                        total_success_rates += win_rate
            
            if matching_wallets:
                avg_success_rate = total_success_rates / len(matching_wallets)
                
                copy_signal['detected'] = True
                copy_signal['similar_wallets'] = len(matching_wallets)
                copy_signal['historical_success_rate'] = avg_success_rate
                
                # Points based on success rate
                if avg_success_rate >= 0.65:
                    points = 1.5
                    copy_signal['profile'] = "top_tier"
                elif avg_success_rate >= 0.60:
                    points = 1.0
                    copy_signal['profile'] = "strong"
                else:
                    points = 0.5
                    copy_signal['profile'] = "moderate"
                
                logger.info(f"[AGENT_3] Copy trade signal: {len(matching_wallets)} wallets, {avg_success_rate:.2%} avg WR, {points} points")
            else:
                logger.debug("[AGENT_3] No matching trader wallets found in recent buyers")
                copy_signal['profile'] = "no_signal"
            
        except Exception as e:
            logger.warning(f"[AGENT_3] Copy trade detection failed: {e}")
        
        return copy_signal, points
    
    def _calculate_tier(self, rank: int) -> str:
        """Helper: Calculate trader tier based on Birdeye rank"""
        if rank <= 10:
            return "top_10"
        elif rank <= 50:
            return "top_50"
        elif rank <= 100:
            return "top_100"
        else:
            return "ranked"
    
    # ============================================================
    # SCORING & ANALYSIS
    # ============================================================
    
    async def analyze_token(self, token_address: str) -> Dict:
        """
        Run all wallet tracker checks. 
        
        Returns:
            Analysis result with score 0-10
        """
        if not token_address:
            logger.warning("[AGENT_3] Cannot analyze token with None address")
            return {
                "agent_id": 3,
                "token_address": None,
                "status": "KILLED",
                "failure_reason": "Missing token address",
                "score": 0
            }
            
        logger.info(f"[AGENT_3] Analyzing {token_address[:8]}...")
        
        start_time = datetime.utcnow()
        
        # Detection 1: Smart Wallets
        smart_wallets, smart_points = await self.detect_smart_wallets(token_address)
        
        # Detection 2: Insider Activity
        insider_status, insider_points = await self.detect_insider_activity(token_address)
        
        # Detection 3: Copy Trade Signal
        copy_signal, copy_points = await self.detect_copy_trade_signal(token_address)
        
        # Calculate total score
        total_points = smart_points + insider_points + copy_points
        score = min(10.0, total_points)  # Cap at 10
        confidence = self._calculate_confidence(smart_wallets, insider_status, copy_signal)
        
        # Determine status (for now, only KILLED if all blank)
        status = "CLEARED" if score >= 5.0 else "KILLED"
        failure_reason = None if status == "CLEARED" else "Insufficient smart money signals"
        
        elapsed_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
        
        result = {
            "agent_id": 3,
            "token_address": token_address,
            "analysis_timestamp": datetime.utcnow().isoformat(),
            "status": status,
            "score": score,
            "confidence": confidence,
            "execution_time_ms": elapsed_ms,
            "smart_wallets_detected": smart_wallets,
            "insider_status": insider_status,
            "copy_trade_signal": copy_signal,
            "failure_reason": failure_reason,
            "summary": {
                "smart_points": smart_points,
                "insider_points": insider_points,
                "copy_points": copy_points,
                "total_points": total_points
            }
        }
        
        if status == "CLEARED":
            logger.info(f"[AGENT_3] ✓ CLEARED {token_address[:8]}... score {score:.1f}/10")
        else:
            logger.warning(f"[AGENT_3] ✗ KILLED {token_address[:8]}... score {score:.1f}/10")
        
        return result
    
    def _calculate_confidence(self, smart_wallets: List, insider_status: Dict, copy_signal: Dict) -> float:
        """
        Calculate confidence score based on signal strength
        
        Logic:
        - More smart wallets = higher confidence
        - Clear insider action = higher confidence
        - Detected copy signal = higher confidence
        """
        confidence = 0.5  # Base confidence
        
        # Boost for smart wallets
        if smart_wallets:
            confidence += 0.15 * min(len(smart_wallets) / 2, 1.0)  # +0.15 per 2 wallets, max +0.15
        
        # Boost for clear insider action
        if insider_status.get('deployer_action') in ['holding', 'accumulating']:
            confidence += 0.15
        
        # Boost for copy signal
        if copy_signal.get('detected'):
            confidence += 0.10
        
        # Cap at 1.0
        return min(1.0, confidence)
    
    async def log_to_database(self, analysis_result: Dict):
        """Log analysis result to database"""
        if not self.db:
            logger.warning("[AGENT_3] Database not available, skipping log")
            return
        
        try:
            await self.db.log_agent_3_analysis(analysis_result)
            logger.info(f"[AGENT_3] Logged: {analysis_result['token_address'][:8]}... status={analysis_result['status']}")
        except Exception as e:
            logger.error(f"[AGENT_3] Error logging to database: {e}")


if __name__ == '__main__':
    logger.info("✅ Agent 3 module loaded")
