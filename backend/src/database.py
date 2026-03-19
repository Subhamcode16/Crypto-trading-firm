import logging
import os
import json
from datetime import datetime
from typing import Any, Dict, Optional, List
from src.utils.convex_client import AsyncConvexClient

logger = logging.getLogger('database')

class Database:
    """Async Convex-powered abstraction layer for tracking signals, trades, and system events"""
    
    def __init__(self, db_path='unused_with_convex'):
        self.convex = AsyncConvexClient()
        logger.info("[DB] Initialized with Convex Backend Integration.")

    async def log_signal(self, signal_dict: dict):
        """Log a signal to Convex"""
        try:
            # Map Python dict to Convex schema
            args = {
                "signalId": signal_dict.get('signal_id'),
                "timestamp": signal_dict.get('timestamp') or datetime.utcnow().isoformat(),
                "tokenAddress": signal_dict.get('token_address'),
                "tokenName": signal_dict.get('token_name', 'Unknown'),
                "tokenSymbol": signal_dict.get('token_symbol', 'Unknown'),
                "entryPrice": float(signal_dict.get('entry_price', 0.0)),
                "positionSizeUsd": float(signal_dict.get('position_size_usd', 0.0)),
                "confidenceScore": float(signal_dict.get('confidence_score', 0.0)),
                "reason": signal_dict.get('reason', ''),
                "status": signal_dict.get('status', 'sent'),
                "telegramSent": bool(signal_dict.get('telegram_sent', False))
            }
            result = await self.convex.mutation("functions:logSignal", args)
            if result.get("success"):
                logger.info(f'[CONVEX] Signal logged: {args["signalId"]}')
            else:
                logger.error(f'[CONVEX] Failed to log signal: {result.get("error")}')
        except Exception as e:
            logger.error(f'[DB] Exception logging signal: {e}')

    async def log_trade(self, trade_dict: dict):
        """Log a trade execution to Convex"""
        try:
            args = {
                "tradeId": trade_dict.get('trade_id'),
                "userId": trade_dict.get('user_id', 'default_user'), # Added
                "signalId": trade_dict.get('signal_id'),
                "tokenAddress": trade_dict.get('token_address'),
                "entryPrice": float(trade_dict.get('entry_price', 0.0)),
                "entryTime": trade_dict.get('entry_time') or datetime.utcnow().isoformat(),
                "entryTxHash": trade_dict.get('entry_tx_hash', ''),
                "positionSizeUsd": float(trade_dict.get('position_size_usd', 0.0)),
                "status": trade_dict.get('status', 'open'),
                "stopLossPrice": float(trade_dict.get('stop_loss_price', 0.0)),
                "tp1Price": float(trade_dict.get('tp1_price', 0.0)),
                "tp2Price": float(trade_dict.get('tp2_price', 0.0)),
            }
            result = await self.convex.mutation("functions:logTrade", args)
            if result.get("success"):
                logger.info(f'[CONVEX] Trade logged: {args["tradeId"]}')
            return result
        except Exception as e:
            logger.error(f'[DB] Exception logging trade: {e}')
            return {"success": False, "error": str(e)}

    async def update_trade(self, trade_id: str, updates: dict):
        """Update an existing trade in Convex"""
        try:
            result = await self.convex.mutation("functions:updateTrade", {
                "tradeId": trade_id,
                "updates": updates
            })
            return result
        except Exception as e:
            logger.error(f'[DB] Exception updating trade {trade_id}: {e}')
            return {"success": False, "error": str(e)}

    async def log_agent_analysis(self, agent_type: str, analysis_result: dict):
        """Generic intel logger for Agents 2, 3, and 4"""
        try:
            args = {
                "tokenAddress": analysis_result['token_address'],
                "agentType": agent_type,
                "status": analysis_result['status'],
                "score": float(analysis_result.get('score', 0.0)),
                "confidence": float(analysis_result.get('confidence', 0.0)),
                "analysisData": analysis_result, # Store full dict as opaque JSON
                "timestamp": datetime.utcnow().isoformat()
            }
            result = await self.convex.mutation("functions:saveIntel", args)
            return result
        except Exception as e:
            logger.error(f'[DB] Exception logging {agent_type} analysis: {e}')
            return {"success": False, "error": str(e)}

    # Legacy method compatibility
    async def log_agent_2_analysis(self, res: dict): return await self.log_agent_analysis("agent_2", res)
    async def log_agent_3_analysis(self, res: dict): return await self.log_agent_analysis("agent_3", res)
    async def log_agent_4_analysis(self, res: dict): return await self.log_agent_analysis("agent_4", res)

    async def get_system_state(self, property_name: str) -> Optional[str]:
        """Fetch system state from Convex"""
        try:
            result = await self.convex.query("functions:getSystemState", {"property": property_name})
            if result.get("success") and result.get("data"):
                return result["data"].get("value")
            return None
        except Exception as e:
            logger.error(f'[DB] Exception fetching system state {property_name}: {e}')
            return None

    async def set_system_state(self, property_name: str, value: Any):
        """Save system state to Convex"""
        try:
            args = {
                "property": property_name,
                "value": str(value).lower(),
                "updatedAt": datetime.utcnow().isoformat()
            }
            await self.convex.mutation("functions:setSystemState", args)
            logger.info(f'[CONVEX] {property_name} set to {value}')
        except Exception as e:
            logger.error(f'[DB] Exception setting system state {property_name}: {e}')

    async def token_exists(self, token_address: str) -> bool:
        """Check if token signal exists in Convex"""
        try:
            result = await self.convex.query("functions:getSignalByToken", {"tokenAddress": token_address})
            return bool(result.get("success") and result.get("data"))
        except Exception as e:
            logger.error(f'[DB] Exception checking token existence: {e}')
            return False

    async def get_recent_analysis(self, token_address: str, cutoff_time: str) -> Optional[Dict]:
        """Fetch recent analysis for a token from Convex"""
        try:
            result = await self.convex.query("functions:getRecentAnalysis", {
                "tokenAddress": token_address,
                "cutoffTime": cutoff_time
            })
            if result.get("success"):
                return result.get("data")
            return None
        except Exception as e:
            logger.error(f'[DB] Exception fetching recent analysis for {token_address}: {e}')
            return None

    async def get_recent_signals(self, limit: int = 10) -> List[Dict]:
        """Fetch the most recent signals from Convex"""
        try:
            result = await self.convex.query("functions:getRecentSignals", {"limit": limit})
            if result.get("success"):
                return result.get("data", [])
            return []
        except Exception as e:
            logger.error(f'[DB] Exception fetching recent signals: {e}')
            return []

    # Pending Approvals for Agent 0
    async def create_pending_approval(self, user_id: str, proposal_id: str, action_json: dict, reasoning: str, agent_votes: dict) -> bool:
        try:
            args = {
                "proposalId": proposal_id,
                "userId": user_id,
                "actionJson": json.dumps(action_json),
                "reasoning": reasoning,
                "agentVotes": json.dumps(agent_votes),
                "status": "pending",
                "createdAt": datetime.utcnow().isoformat()
            }
            result = await self.convex.mutation("functions:createPendingApproval", args)
            return bool(result.get("success"))
        except Exception as e:
            logger.error(f'[DB] Exception creating pending approval: {e}')
            return False

    async def resolve_pending_approval(self, proposal_id: str, status: str) -> bool:
        try:
            args = {
                "proposalId": proposal_id,
                "status": status,
                "resolvedAt": datetime.utcnow().isoformat()
            }
            result = await self.convex.mutation("functions:updatePendingApproval", args)
            return bool(result.get("success"))
        except Exception as e:
            logger.error(f'[DB] Exception resolving approval: {e}')
            return False

    # --- User Profiles ---
    async def get_user_profile(self, user_id: str) -> Optional[Dict]:
        try:
            result = await self.convex.query("functions:getProfile", {"userId": str(user_id)})
            if result.get("success"):
                return result.get("data")
            return None
        except Exception as e:
            logger.error(f'[DB] Exception fetching profile for {user_id}: {e}')
            return None

    async def save_user_profile(self, profile: dict) -> bool:
        try:
            # Ensure userId is string
            profile["userId"] = str(profile["userId"])
            result = await self.convex.mutation("functions:saveProfile", profile)
            return bool(result.get("success"))
        except Exception as e:
            logger.error(f'[DB] Exception saving profile: {e}')
            return False

    # --- Chat History ---
    async def get_chat_history(self, user_id: str) -> List[Dict]:
        try:
            result = await self.convex.query("functions:getChatHistory", {"userId": str(user_id)})
            if result.get("success"):
                return result.get("data", [])
            return []
        except Exception as e:
            logger.error(f'[DB] Exception fetching history for {user_id}: {e}')
            return []

    async def append_chat_history(self, user_id: str, role: str, content: str):
        try:
            args = {
                "userId": str(user_id),
                "role": role,
                "content": content,
                "timestamp": datetime.utcnow().isoformat()
            }
            await self.convex.mutation("functions:appendChatHistory", args)
        except Exception as e:
            logger.error(f'[DB] Exception appending history: {e}')

    async def clear_chat_history(self, user_id: str):
        try:
            await self.convex.mutation("functions:clearChatHistory", {"userId": str(user_id)})
        except Exception as e:
            logger.error(f'[DB] Exception clearing history for {user_id}: {e}')

    async def get_all_positions(self, user_id: str = "default_user") -> Dict[str, List]:
        """Fetch all positions (OPEN/CLOSED) for a user from Convex"""
        try:
            result = await self.convex.query("functions:getPositions", {"userId": user_id})
            if result.get("success"):
                return result.get("data", {"open": [], "closed": []})
            return {"open": [], "closed": []}
        except Exception as e:
            logger.error(f'[DB] Exception fetching positions: {e}')
            return {"open": [], "closed": []}

    async def get_daily_portfolio_state(self, user_id: str, date_str: str) -> Dict:
        """Fetch portfolio daily stats from Convex"""
        try:
            result = await self.convex.query("functions:getDailyStats", {"userId": user_id, "date": date_str})
            if result.get("success") and result.get("data"):
                return result["data"]
            return {"realized_pnl_usd": 0.0, "realized_loss_usd": 0.0, "daily_loss_limit_usd": 0.0}
        except Exception as e:
            logger.error(f'[DB] Exception fetching daily stats: {e}')
            return {"realized_pnl_usd": 0.0, "realized_loss_usd": 0.0, "daily_loss_limit_usd": 0.0}

    async def update_daily_portfolio_state(self, user_id: str, date_str: str, **updates):
        """Update daily stats in Convex"""
        try:
            args = {
                "userId": user_id,
                "date": date_str,
                "updates": updates
            }
            await self.convex.mutation("functions:updateDailyStats", args)
            logger.info(f'[CONVEX] Daily stats updated for {date_str}')
        except Exception as e:
            logger.error(f'[DB] Exception updating daily stats: {e}')

    async def get_pending_approvals(self, user_id: str) -> List:
        """Fetch list of pending proposals from Convex"""
        try:
            result = await self.convex.query("functions:getPendingApprovals", {"userId": user_id})
            if result.get("success"):
                return result.get("data", [])
            return []
        except Exception as e:
            logger.error(f'[DB] Exception fetching pending approvals: {e}')
            return []

    async def get_pending_approval(self, proposal_id: str) -> Optional[Dict]:
        """Fetch a specific proposal from Convex"""
        try:
            result = await self.convex.query("functions:getPendingApproval", {"proposalId": proposal_id})
            if result.get("success"):
                return result.get("data")
            return None
        except Exception as e:
            logger.error(f'[DB] Exception fetching proposal {proposal_id}: {e}')
            return None

    # Kill Switch
    async def get_kill_switch(self, user_id: str = "default_user"):
        """Fetch kill switch status from Convex"""
        try:
            result = await self.convex.query("functions:getKillSwitch", {"userId": user_id})
            if result.get("success") and result.get("data"):
                return result["data"]
            return {"tier": 0, "macro_check_interval_seconds": 900}
        except Exception as e:
            logger.error(f'[DB] Exception fetching kill switch: {e}')
            return {"tier": 0, "macro_check_interval_seconds": 900}

    async def set_kill_switch(self, user_id: str, tier: int, reason: str, actor: str = "system", affected_tokens: List[str] = None):
        """Activate a kill switch tier in Convex"""
        try:
            args = {
                "userId": user_id,
                "tier": tier,
                "reason": reason,
                "actor": actor,
                "affectedTokens": affected_tokens or [],
                "activeSince": datetime.utcnow().isoformat()
            }
            await self.convex.mutation("functions:setKillSwitch", args)
            logger.warning(f'[CONVEX] KILL SWITCH ACTIVATED: Tier {tier} | Reason: {reason}')
        except Exception as e:
            logger.error(f'[DB] Exception setting kill switch: {e}')

    async def clear_kill_switch(self, user_id: str, actor: str = "system"):
        """Deactivate kill switch in Convex"""
        try:
            args = {
                "userId": user_id,
                "actor": actor,
                "resolvedAt": datetime.utcnow().isoformat()
            }
            await self.convex.mutation("functions:clearKillSwitch", args)
            logger.info(f'[CONVEX] Kill switch cleared by {actor}')
        except Exception as e:
            logger.error(f'[DB] Exception clearing kill switch: {e}')
        
    async def close(self):
        await self.convex.close()
