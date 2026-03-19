import logging
from datetime import datetime
from typing import Optional, Dict
from src.ml.learning_loop import LearningLoop

logger = logging.getLogger(__name__)

class PerformanceAnalyst:
    """
    Agent-9: The firm's Performance Analyst and Communications Director.
    Responsiblities include formatting and dispatching Telegram alerts for trades,
    kill switch events, and generating daily EOD summaries.
    """
    def __init__(self, db_client, telegram_client):
        self.db = db_client
        self.telegram = telegram_client
        self.learning_loop = LearningLoop(db_client)
        logger.info("[AGENT_9] Performance Analyst initialized with Learning Loop.")

    async def notify_trade_opened(self, position) -> bool:
        """Called by Agent-8 when a trade is successfully executed and entered."""
        if not self.telegram:
            return False

        # Calculate percentages
        entry_price = position.entry_price or 1.0 # Avoid div zero
        tp1_pct = ((position.tp1_price - entry_price) / entry_price) * 100
        sl_pct = ((position.sl_price - entry_price) / entry_price) * 100
        
        # Determine strategies and rationale (if available)
        strategies = getattr(position, 'strategy_breakdown', [])
        strategy_text = "\n".join([f"  • {s}" for s in strategies]) if strategies else "  • Systematic breakout entry"
        
        sl_tp_rationale = getattr(position, 'sl_tp_rationale', "Standard risk parameters applied.")

        message = f"""
NEW POSITION EXECUTED

Token: {position.token}
Action: {position.action.upper()}
Entry Price: ${position.entry_price:,.8f}
Size: ${position.position_size_usd:,.2f}

Target TP1: ${position.tp1_price:,.8f} (+{tp1_pct:.2f}%)
Stop Loss: ${position.sl_price:,.8f} ({sl_pct:.2f}%)

Strategy Breakdown:
{strategy_text}

Risk Decision:
{sl_tp_rationale}

Trace ID: {position.position_id[:8]}
"""
        return await self._send_msg(message)

    async def notify_pipeline_summary(self, stats: Dict) -> bool:
        """Send a summary of the discovery pipeline for the latest scan."""
        if not self.telegram:
            return False
            
        # Only notify if at least one token reached Agent 6 (Macro)
        if stats.get('agent_6_passed', 0) == 0:
            return False

        message = f"""
PIPELINE SCAN SUMMARY

Tokens Discovered (Agent 1): {stats.get('total_found', 0)}
Tokens Processed (Intelligence Division): {stats.get('total_processed', 0)}
Passed Agent 6 (Macro): {stats.get('agent_6_passed', 0)}
Approved Agent 7 (Risk): {stats.get('agent_7_passed', 0)}
Executed Agent 8 (Trade): {stats.get('agent_8_executed', 0)}

Status: Scan Cycle Complete.
"""
        return await self._send_msg(message)


    async def notify_trade_closed(self, position, exit_reason: str) -> bool:
        """Called by Agent-8 when a position hits SL, TP, or TS."""
        if not self.telegram:
            return False

        # Calculate PnL stats
        pnl_str = f"+${position.pnl_usd:,.2f}" if position.pnl_usd >= 0 else f"-${abs(position.pnl_usd):,.2f}"
        pnl_pct = (position.pnl_usd / position.position_size_usd) * 100 if position.position_size_usd > 0 else 0
        pct_str = f"+{pnl_pct:.2f}%" if pnl_pct >= 0 else f"{pnl_pct:.2f}%"

        # Determine header and emoji
        if "TP" in exit_reason.upper() or position.pnl_usd > 0:
            header = "💰 <b>TAKE PROFIT HIT</b> 💰"
        elif "SL" in exit_reason.upper() or position.pnl_usd < 0:
            header = "🛑 <b>STOP LOSS HIT</b> 🛑"
        else:
            header = "⚠️ <b>POSITION CLOSED</b> ⚠️"

        daily_pnl = await self._get_daily_pnl(position.user_id)
        daily_pnl_str = f"+${daily_pnl:,.2f}" if daily_pnl >= 0 else f"-${abs(daily_pnl):,.2f}"

        message = f"""
{header}

Token: <b>{position.token}</b>
Exit Price: ${position.current_price:,.4f}
Status: {position.status}
Reason: {exit_reason}

PnL: <b>{pnl_str} ({pct_str})</b>

📊 Firm Daily PnL: {daily_pnl_str}
"""
        # Trigger Learning Loop for post-trade analysis
        try:
            # We wrap position in a dict for the learner
            trade_data = {
                "token": position.token,
                "entry_price": position.entry_price,
                "current_price": position.current_price,
                "pnl_usd": position.pnl_usd,
                "exit_reason": exit_reason,
                "agent_analysis": getattr(position, 'agent_analysis', {}),
                "refined_by": getattr(position, 'refined_by', None),
                "refinement_reason": getattr(position, 'refinement_reason', None)
            }
            lesson = await self.learning_loop.analyze_trade_outcome(trade_data)
            if lesson.get("learned_trait"):
                message += f"\n\n🧠 <b>AI Lesson:</b> {lesson.get('learned_trait')}"
        except Exception as e:
            logger.error(f"[AGENT_9] Learning loop trigger failed: {e}")

        return await self._send_msg(message)

    async def notify_kill_switch(self, tier: int, reason: str, user_id: str = "default_user") -> bool:
        """Send emergency kill switch alerts."""
        if not self.telegram:
            return False

        message = f"""
🚨 <b>KILL SWITCH TRIGGERED: TIER {tier}</b> 🚨

Reason: {reason}

"""
        if tier == 1:
            message += "Action: Reduced sizing and paused new entries for affected token (2h cooldown)."
        elif tier == 2:
            message += "Action: Paused all new portfolio entries. Existing trades being monitored. Resets at UTC midnight."
        elif tier == 3:
            message += "⚠️ <b>CRITICAL:</b> All positions liquidated at market. System isolated. Manual /resume required to restore node operations."

        try:
            # Reusing the existing method if possible, or just raw sending
            if hasattr(self.telegram, 'send_kill_switch_alert'):
                return await self.telegram.send_kill_switch_alert(str(tier), {"message": reason})
            else:
                return await self._send_msg(message)
        except Exception as e:
            logger.error(f"[AGENT_9] Failed to send kill switch notification: {e}")
            return False

    async def generate_daily_report(self, user_id: str = "default_user") -> bool:
        """Generates the EOD summary report from the DB and sends it to Telegram."""
        if not self.telegram or not self.db:
            return False

        try:
            positions = await self.db.get_all_positions(user_id)
            closed = positions.get("closed", [])
            
            today = datetime.utcnow().date()
            today_trades = []
            
            for c in closed:
                try:
                    c_date = datetime.fromisoformat(c.get("closed_at", "").replace("Z", "+00:00")).date()
                    if c_date == today:
                        today_trades.append(c)
                except:
                    pass
            
            total_trades = len(today_trades)
            if total_trades == 0:
                logger.info("[AGENT_9] No trades today for daily report.")
                return False

            winning_trades = [t for t in today_trades if t.get("pnl_usd", 0) > 0]
            net_pnl = sum(t.get("pnl_usd", 0) for t in today_trades)
            win_rate = (len(winning_trades) / total_trades) * 100 if total_trades > 0 else 0

            best_trade = max(today_trades, key=lambda x: x.get("pnl_usd", -999999), default=None)
            worst_trade = min(today_trades, key=lambda x: x.get("pnl_usd", 999999), default=None)

            pnl_str = f"+${net_pnl:,.2f}" if net_pnl >= 0 else f"-${abs(net_pnl):,.2f}"
            
            message = f"""
📋 <b>DAILY FIRM REPORT</b> 📋
Date: {today.isoformat()}

Trades Executed: {total_trades}
Win Rate: {win_rate:.1f}%

<b>Net PnL: {pnl_str}</b>
"""
            if best_trade and best_trade.get("pnl_usd", 0) > 0:
                message += f"\n🏆 Best Trade: {best_trade.get('token')} (+${best_trade.get('pnl_usd', 0):,.2f})"
            if worst_trade and worst_trade.get("pnl_usd", 0) < 0:
                message += f"\n🩸 Worst Trade: {worst_trade.get('token')} (-${abs(worst_trade.get('pnl_usd', 0)):,.2f})"

            return await self._send_msg(message)
            
        except Exception as e:
            logger.error(f"[AGENT_9] Failed to generate daily report: {e}")
            return False

    async def _get_daily_pnl(self, user_id: str) -> float:
        """Helper to get current daily PnL."""
        daily_pnl = 0.0
        try:
            if self.db:
                positions = await self.db.get_all_positions(user_id)
                closed = positions.get("closed", [])
                today = datetime.utcnow().date()
                for c in closed:
                    try:
                        c_date = datetime.fromisoformat(c.get("closed_at", "").replace("Z", "+00:00")).date()
                        if c_date == today:
                            daily_pnl += c.get("pnl_usd", 0.0)
                    except:
                        pass
        except Exception as e:
            logger.warning(f"[AGENT_9] Could not fetch daily PnL: {e}")
        return daily_pnl

    async def _send_msg(self, message: str) -> bool:
        """Helper to safely ping telegram."""
        try:
            # We use send_status_update from TelegramBot to reach all users
            if hasattr(self.telegram, 'send_status_update'):
                return await self.telegram.send_status_update({"message": message.strip()})
            else:
                # Fallback to direct bot send if telegram is a raw bot (not recommended)
                await self.telegram.app.bot.send_message(chat_id=self.telegram.chat_id, text=message.strip(), parse_mode='HTML')
                logger.info("[AGENT_9] Notification sent via raw bot.")
                return True
        except Exception as e:
            logger.error(f"[AGENT_9] Failed to send notification: {e}")
            return False
