import logging
from datetime import datetime
from typing import Optional, Dict
from src.ml.learning_loop import LearningLoop
from src.ml.trainer import MLTrainer

logger = logging.getLogger(__name__)

class PerformanceAnalyst:
    """
    Agent-9: The firm's Performance Analyst and Communications Director.
    Responsibilities include formatting and dispatching Telegram alerts for trades,
    kill switch events, generating daily EOD summaries, and comprehensive 4-hour digests.
    """
    def __init__(self, db_client, telegram_client):
        self.db = db_client
        self.telegram = telegram_client
        self.trading_bot = None  # Injected by main.py for open positions data
        self.learning_loop = LearningLoop(db_client)
        self.ml_trainer = MLTrainer()
        # Accumulate scan stats across cycles for 4-hour digest
        self._digest_scan_history = []
        logger.info("[AGENT_9] Performance Analyst initialized with Learning Loop + ML Trainer.")

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
        """Send a detailed summary of the discovery pipeline for the latest scan."""
        if not self.telegram:
            return False
        
        # Store for digest accumulation
        self._digest_scan_history.append(stats.copy())
            
        # Only notify if at least one token was found
        if stats.get('total_found', 0) == 0:
            return False

        total_found = stats.get('total_found', 0)
        a2_cleared = stats.get('agent_2_cleared', 0)
        a2_killed = stats.get('agent_2_killed', 0)
        a5_cleared = stats.get('agent_5_cleared', 0)
        a5_killed = stats.get('agent_5_killed', 0)
        a6_passed = stats.get('agent_6_passed', 0)
        a6_held = stats.get('agent_6_held', 0)
        a7_passed = stats.get('agent_7_passed', 0)
        a7_blocked = stats.get('agent_7_blocked', 0)
        a8_executed = stats.get('agent_8_executed', 0)
        a8_rejected = stats.get('agent_8_rejected', 0)
        
        cleared_tokens = stats.get('cleared_tokens', [])
        executed_tokens = stats.get('executed_tokens', [])
        kill_reasons = stats.get('kill_reasons', [])

        # Build per-agent breakdown
        lines = [
            "\ud83d\udce1 <b>SCAN CYCLE REPORT</b>",
            "",
            f"\ud83d\udd75\ufe0f <b>Agent 1 (Discovery):</b> {total_found} tokens found",
        ]
        
        if total_found > 0:
            lines.append(f"\ud83d\udd2c <b>Agent 2 (On-Chain Safety):</b> {a2_cleared} cleared, {a2_killed} killed")
            lines.append(f"\ud83d\udd0d <b>Agent 3 (Wallet Tracker):</b> {a2_cleared} analyzed")
            lines.append(f"\ud83d\udce1 <b>Agent 4 (Intel/Sentiment):</b> {a2_cleared} analyzed")
            lines.append(f"\u2696\ufe0f <b>Agent 5 (Signal Aggregator):</b> {a5_cleared} cleared, {a5_killed} dropped")
            lines.append("")
            
            if a5_cleared > 0:
                lines.append(f"\ud83d\udcca <b>Agent 6 (Macro Sentinel):</b> {a6_passed} passed, {a6_held} held")
                lines.append(f"\ud83d\udee1\ufe0f <b>Agent 7 (Risk Manager):</b> {a7_passed} approved, {a7_blocked} blocked")
                lines.append(f"\u26a1 <b>Agent 8 (Execution):</b> {a8_executed} filled, {a8_rejected} rejected")
        
        if executed_tokens:
            lines.append("")
            lines.append("<b>Executed Tokens:</b>")
            for t in executed_tokens[:5]:
                lines.append(f"  \ud83d\udcb8 {t.get('symbol', '?')} @ ${t.get('price', 0):.8f}")
        
        if kill_reasons:
            lines.append("")
            lines.append("<b>Drop Reasons:</b>")
            for r in kill_reasons[-3:]:
                lines.append(f"  \u274c {r}")
        
        lines.append("")
        lines.append("<i>Scan Cycle Complete</i>")
        
        message = "\n".join(lines)
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

        # Save trade outcome for ML trainer (XGBoost retraining pipeline)
        try:
            price_change_pct = ((position.current_price - position.entry_price) / position.entry_price) * 100 if position.entry_price > 0 else 0
            self.ml_trainer.save_outcome(
                trade_id=position.signal_id,
                price_change_pct=price_change_pct,
                profit_usd=position.pnl_usd
            )
            logger.info(f"[AGENT_9] 🧠 ML outcome saved for {position.token} (trade_id={position.signal_id})")
        except Exception as e:
            logger.error(f"[AGENT_9] ML outcome save failed: {e}")

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

    async def generate_agent_digest(self, user_id: str = "default_user") -> bool:
        """
        Generate a comprehensive 4-hour agent digest covering all agent activity.
        Sent alongside the Strategic Review every 4 hours.
        """
        if not self.telegram or not self.db:
            return False

        try:
            lines = [
                "📋 <b>4-HOUR AGENT ACTIVITY DIGEST</b>",
                f"⏰ {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}",
                "",
                "━━━━━━━━━━━━━━━━━━━━━━━━━━",
            ]

            # ── AGENTS 1-5: Research Division Summary ──
            scan_count = len(self._digest_scan_history)
            if scan_count > 0:
                total_found = sum(s.get('total_found', 0) for s in self._digest_scan_history)
                total_a2_cleared = sum(s.get('agent_2_cleared', 0) for s in self._digest_scan_history)
                total_a2_killed = sum(s.get('agent_2_killed', 0) for s in self._digest_scan_history)
                total_a5_cleared = sum(s.get('agent_5_cleared', 0) for s in self._digest_scan_history)
                total_a5_killed = sum(s.get('agent_5_killed', 0) for s in self._digest_scan_history)
                
                lines.extend([
                    "<b>🏢 RESEARCH DIVISION (Agents 1-5)</b>",
                    f"Scans Completed: {scan_count}",
                    "",
                    f"🕵️ <b>Agent 1 (Discovery):</b>",
                    f"  Tokens Found: {total_found}",
                    "",
                    f"🔬 <b>Agent 2 (On-Chain Safety):</b>",
                    f"  Cleared: {total_a2_cleared} | Killed: {total_a2_killed}",
                    f"  Pass Rate: {(total_a2_cleared / max(total_found, 1)) * 100:.0f}%",
                    "",
                    f"🔍 <b>Agent 3 (Wallet Tracker):</b>",
                    f"  Analyzed: {total_a2_cleared} tokens for smart money signals",
                    "",
                    f"📡 <b>Agent 4 (Intel/Sentiment):</b>",
                    f"  Community sentiment checked on {total_a2_cleared} tokens",
                    "",
                    f"⚖️ <b>Agent 5 (Signal Aggregator):</b>",
                    f"  Cleared: {total_a5_cleared} | Dropped: {total_a5_killed}",
                    f"  Pass Rate: {(total_a5_cleared / max(total_a2_cleared, 1)) * 100:.0f}%",
                    "",
                ])
                
                # Collect all kill reasons from scans
                all_kill_reasons = []
                for s in self._digest_scan_history:
                    all_kill_reasons.extend(s.get('kill_reasons', []))
                if all_kill_reasons:
                    lines.append("<b>Top Drop Reasons:</b>")
                    # Deduplicate and show top 5
                    from collections import Counter
                    reason_counts = Counter(all_kill_reasons)
                    for reason, count in reason_counts.most_common(5):
                        lines.append(f"  ❌ {reason} (×{count})")
                    lines.append("")
            else:
                lines.extend([
                    "<b>🏢 RESEARCH DIVISION (Agents 1-5)</b>",
                    "No scans completed in this period.",
                    "",
                ])

            # ── AGENTS 6-7: Command Division Strategy ──
            lines.extend([
                "━━━━━━━━━━━━━━━━━━━━━━━━━━",
                "<b>🎖️ COMMAND DIVISION (Agents 6-7)</b>",
                "",
            ])
            
            # Agent 6 Macro State
            try:
                macro_regime = await self.db.get_system_state("macro_regime") or "unknown"
                macro_summary = await self.db.get_system_state("macro_summary") or "No macro data"
                lines.extend([
                    f"📊 <b>Agent 6 (Macro Sentinel):</b>",
                    f"  Market Regime: <b>{macro_regime.upper()}</b>",
                    f"  Assessment: {macro_summary[:150]}",
                ])
                
                # Gather Agent 6 stats from scans
                total_a6_passed = sum(s.get('agent_6_passed', 0) for s in self._digest_scan_history)
                total_a6_held = sum(s.get('agent_6_held', 0) for s in self._digest_scan_history)
                lines.extend([
                    f"  Signals Passed: {total_a6_passed} | Held: {total_a6_held}",
                    f"  Indicators: BTC/SOL EMA50, Bollinger Bands (%B), RSI(14)",
                    "",
                ])
            except Exception as e:
                lines.append(f"  ⚠️ Could not fetch macro state: {e}")
                lines.append("")

            # Agent 7 Risk State
            try:
                today = datetime.utcnow().strftime("%Y-%m-%d")
                pnl_state = await self.db.get_daily_portfolio_state(user_id, today)
                ks_state = await self.db.get_kill_switch(user_id)
                risk_tier_high = float(await self.db.get_system_state("risk_tier_high") or 0.20)
                loss_limit = float(await self.db.get_system_state("daily_loss_limit_pct") or 0.30)
                
                total_a7_passed = sum(s.get('agent_7_passed', 0) for s in self._digest_scan_history)
                total_a7_blocked = sum(s.get('agent_7_blocked', 0) for s in self._digest_scan_history)
                
                realized_loss = pnl_state.get("realized_loss_usd", 0.0)
                daily_limit = pnl_state.get("daily_loss_limit_usd", 999.0)
                
                lines.extend([
                    f"🛡️ <b>Agent 7 (Risk Manager):</b>",
                    f"  Kill Switch: Tier <b>{ks_state.get('tier', 0)}</b>",
                    f"  Position Cap: <b>{risk_tier_high:.0%}</b> | Loss Limit: <b>{loss_limit:.0%}</b>",
                    f"  Daily Loss: ${realized_loss:.4f} / ${daily_limit:.4f}",
                    f"  Approved: {total_a7_passed} | Blocked: {total_a7_blocked}",
                    f"  SL Strategy: -20% (High), -10% (Venture/Low)",
                    f"  TP Strategy: TP1 at 2×, TP2 at 4×, Trailing 50%",
                    "",
                ])
                
                # Strategy Discussion
                if total_a7_passed > 0:
                    bullish_reason = "Signals meeting composite threshold with macro clearance"
                    if macro_regime in ["bullish"]:
                        bullish_reason = "Bullish regime — full allocation multiplier active"
                    elif macro_regime in ["choppy", "flat"]:
                        bullish_reason = f"{macro_regime.title()} regime — reduced allocation (×0.5-0.7)"
                    lines.extend([
                        "<b>Strategy Discussion:</b>",
                        f"  📈 Outlook: {bullish_reason}",
                        f"  💡 Risk Tiers: High(≥9.0)=20%, Med(≥8.0)=10%, Low(≥7.0)=5%, Venture(≥6.0)=2%",
                        "",
                    ])
            except Exception as e:
                lines.append(f"  ⚠️ Could not fetch risk state: {e}")
                lines.append("")

            # ── AGENT 8: Execution Summary ──
            lines.extend([
                "━━━━━━━━━━━━━━━━━━━━━━━━━━",
                "<b>⚡ EXECUTION DIVISION (Agent 8)</b>",
                "",
            ])
            
            total_a8_executed = sum(s.get('agent_8_executed', 0) for s in self._digest_scan_history)
            total_a8_rejected = sum(s.get('agent_8_rejected', 0) for s in self._digest_scan_history)
            
            lines.extend([
                f"Trades Executed: {total_a8_executed} | Rejected: {total_a8_rejected}",
            ])
            
            # Show executed token details
            all_executed = []
            for s in self._digest_scan_history:
                all_executed.extend(s.get('executed_tokens', []))
            
            if all_executed:
                lines.append("")
                lines.append("<b>Executed Trades:</b>")
                for t in all_executed:
                    symbol = t.get('symbol', '?')
                    price = t.get('price', 0)
                    size = t.get('size_usd', 0)
                    sl_pct = t.get('sl_pct', 0)
                    tp1_mult = t.get('tp1_mult', 0)
                    rationale = t.get('rationale', 'Standard entry')
                    lines.extend([
                        f"  💸 <b>{symbol}</b>",
                        f"     Entry: ${price:.8f} | Size: ${size:.4f}",
                        f"     SL: -{sl_pct:.0%} | TP1: {tp1_mult:.0f}× | TP2: {t.get('tp2_mult', 0):.0f}×",
                        f"     Logic: {rationale[:80]}",
                    ])
            
            # Open positions from Agent 8
            open_positions = await self._get_open_positions()
            if open_positions:
                lines.append("")
                lines.append(f"<b>Open Positions ({len(open_positions)}):</b>")
                for pos in open_positions:
                    pnl = pos.get('pnl_usd', 0)
                    pnl_emoji = '🟢' if pnl >= 0 else '🔴'
                    lines.extend([
                        f"  {pnl_emoji} <b>{pos.get('token', '?')}</b>",
                        f"     Entry: ${pos.get('entry_price', 0):.8f} | Current: ${pos.get('current_price', 0):.8f}",
                        f"     Size: ${pos.get('remaining_size_usd', 0):.4f} | PnL: ${pnl:.4f}",
                        f"     SL: ${pos.get('sl_price', 0):.8f} | TP1: ${pos.get('tp1_price', 0):.8f}",
                    ])
            else:
                lines.append("")
                lines.append("No open positions.")

            # ── DAILY PNL FOOTER ──
            try:
                daily_pnl = await self._get_daily_pnl(user_id)
                pnl_str = f"+${daily_pnl:,.4f}" if daily_pnl >= 0 else f"-${abs(daily_pnl):,.4f}"
                lines.extend([
                    "",
                    "━━━━━━━━━━━━━━━━━━━━━━━━━━",
                    f"💰 <b>Daily PnL: {pnl_str}</b>",
                    "<i>Digest generated by Agent 9 — Performance Analyst</i>",
                ])
            except:
                pass

            # Clear accumulated scan history for next period
            self._digest_scan_history = []

            message = "\n".join(lines)
            return await self._send_msg(message)

        except Exception as e:
            logger.error(f"[AGENT_9] Failed to generate agent digest: {e}")
            return False

    async def _get_open_positions(self) -> list:
        """Get open positions from Agent 8 trading bot or DB."""
        positions = []
        try:
            # Try to get from Agent 8 in-memory state first
            if self.trading_bot and hasattr(self.trading_bot, 'active_positions'):
                for pos_id, pos in self.trading_bot.active_positions.items():
                    positions.append({
                        'token': pos.token,
                        'entry_price': pos.entry_price,
                        'current_price': pos.current_price,
                        'remaining_size_usd': pos.remaining_size_usd,
                        'sl_price': pos.sl_price,
                        'tp1_price': pos.tp1_price,
                        'tp2_price': pos.tp2_price,
                        'pnl_usd': pos.pnl_usd,
                        'status': pos.status,
                    })
            elif self.db:
                # Fallback: read from DB
                all_positions = await self.db.get_all_positions()
                for p in all_positions.get('open', []):
                    positions.append({
                        'token': p.get('token', '?'),
                        'entry_price': float(p.get('entryPrice', 0)),
                        'current_price': float(p.get('currentPrice', p.get('entryPrice', 0))),
                        'remaining_size_usd': float(p.get('remainingSizeUsd', p.get('positionSizeUsd', 0))),
                        'sl_price': float(p.get('stopLossPrice', 0)),
                        'tp1_price': float(p.get('tp1Price', 0)),
                        'tp2_price': float(p.get('tp2Price', 0)),
                        'pnl_usd': float(p.get('pnlUsd', 0)),
                        'status': p.get('status', 'open'),
                    })
        except Exception as e:
            logger.warning(f"[AGENT_9] Could not fetch open positions: {e}")
        return positions

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
