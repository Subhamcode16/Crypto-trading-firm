#!/usr/bin/env python3
"""
AGENT 0: The Commander — [STRATEGIC HEADQUARTERS]

Role: Managing Director and Chief Strategist.
Orchestrates all other agents by adjusting their parameters based on
Sonnet's high-level oversight of firm performance and market conditions.

Capabilities:
- Interprets natural language commands via Telegram (LLM-powered NLP)
- Semi-autonomous: Defensive moves auto-apply, Offensive moves need approval
- Adjusts Agent 7 Risk Parameters (Tier pcts, Loss Limits)
- Adjusts Agent 5 Signal Weights (Trust levels between agents)
- Manages System State (Pause/Resume/Emergency Halt)
- Generates briefings citing Agent 6 (Macro) and Agent 7 (Risk) intelligence
- Interprets Agent 9's performance reports to 'tune' the machine.
"""

import json
import logging
import uuid
from datetime import datetime
from typing import Dict, Optional, Tuple
from src.utils.llm_client import LLMClient

logger = logging.getLogger(__name__)

# Intent categories
OFFENSIVE_ACTIONS = {"RAISE_RISK", "INCREASE_POSITION_SIZE", "LOOSEN_LOSS_LIMIT", "LOWER_THRESHOLD"}
DEFENSIVE_ACTIONS = {"REDUCE_RISK", "LOWER_POSITION_SIZE", "TIGHTEN_LOSS_LIMIT", "RAISE_THRESHOLD",
                     "PAUSE_TRADING", "RESUME_TRADING", "MAINTAIN"}


class Agent0Commander:
    def __init__(self, db_client, telegram_client=None):
        self.db = db_client
        self.telegram = telegram_client   # Injected after init to avoid circular imports
        self.llm = LLMClient()
        self.haiku_type = "haiku"
        self.sonnet_type = "sonnet"
        self.model_type = "haiku-strategic"

        logger.info("[AGENT_0] Commander initialized. Strategic intelligence set to Claude 3.5 Sonnet.")

    # ─────────────────────────────────────────────────────────────────
    # PUBLIC: NATURAL LANGUAGE COMMAND PROCESSOR (Telegram entry point)
    # ─────────────────────────────────────────────────────────────────

    async def process_telegram_command(self, text: str, user_id: str, profile: Dict = None) -> str:
        """
        Main entry point for Telegram. Now focuses on a professional 'Wall Street' persona.
        """
        try:
            profile = profile or await self.db.get_user_profile(user_id)
            user_name = profile.get("userName", "Trader") if profile else "Trader"
            bot_name = profile.get("botName", "Commander") if profile else "Commander"

            logger.info(f"[AGENT_0] 💬 Processing command from {user_name}: '{text[:80]}'")

            # 1. Parse intent to check for structured actions (Pause, Status, etc.)
            intent = await self._parse_intent_with_llm(text)
            action = intent.get("action", "UNCLEAR")
            
            # 2. If it's a known command, process it
            if action != "UNCLEAR" and action != "MAINTAIN":
                if action == "STATUS":
                    return await self._get_status_report(user_id)
                
                # Assess and apply/request
                agent_votes = await self._assess_proposal_with_agents(intent, user_id)
                if action in DEFENSIVE_ACTIONS:
                    await self._auto_apply_defensive(intent, user_id)
                    return self._format_defensive_notification(intent, agent_votes)
                elif action in OFFENSIVE_ACTIONS:
                    proposal_id = await self._create_approval_request(intent, agent_votes, user_id)
                    return self._format_approval_request(intent, agent_votes, proposal_id)

            # 3. If action is UNCLEAR or MAINTAIN, handle as a professional "Wall Street" conversation
            return await self._generate_professional_response(text, user_id, profile)

        except Exception as e:
            logger.error(f"[AGENT_0] process_telegram_command failed: {e}")
            return f"❌ 💼 <b>Executive Error:</b> System interruption in command processing."

    async def _generate_professional_response(self, text: str, user_id: str, profile: Dict = None) -> str:
        """Generate a response as a professional Wall Street trader, restricted to trading."""
        profile = profile or await self.db.get_user_profile(user_id)
        user_name = profile.get("userName", "Trader") if profile else "Trader"
        bot_name = profile.get("botName", "MD") if profile else "MD"

        system_prompt = (
            f"You are {bot_name}, the MD of an elite, top-tier quantitative Solana trading firm. "
            f"Your persona is a high-stakes Wall Street trader. Direct, authoritative, and sharp. "
            f"The user's name is {user_name}. Maintain this professional relationship. "
            "STRICT RULE: Only talk about trading, market conditions, or bot performance. "
            "If asked about anything else, firmly redirect them to the P&L."
        )
        
        # Get history from Convex
        raw_history = await self.db.get_chat_history(user_id)
        
        # Add current message
        await self.db.append_chat_history(user_id, "user", text)
        
        # Build messages list with STRICT alternation (Anthropic requirement)
        # and ensure it starts with 'user'
        messages = []
        last_role = None
        
        for h in raw_history:
            role = h["role"]
            content = h["content"]
            
            if role == last_role:
                # Merge consecutive messages of same role
                if messages:
                    messages[-1]["content"] += "\n" + content
            else:
                messages.append({"role": role, "content": content})
                last_role = role

        # Ensure the first message is always 'user' (Anthropic Requirement)
        while messages and messages[0]["role"] != "user":
            messages.pop(0)

        if not messages:
            messages.append({"role": "user", "content": text})

        # Debug logging to file
        with open("commander_debug.log", "a", encoding="utf-8") as f:
            f.write(f"\n--- {datetime.utcnow().isoformat()} ---\n")
            f.write(f"USER_ID: {user_id}\n")
            f.write(f"PROMPT: {system_prompt[:100]}...\n")
            f.write(f"MESSAGES: {json.dumps(messages, indent=2)}\n")

        try:
            resp = await self.llm.create_message(
                model_type=self.model_type,
                system_prompt=system_prompt,
                messages=messages,
                max_tokens=600,
                temperature=0.7
            )
            
            # Check for LLM error before processing text
            if resp.get('error'):
                logger.error(f"[AGENT_0] LLM error in professional response: {resp.get('error')}")
                return (
                    f"💼 <b>{bot_name}:</b> Strategic desk is temporarily offline, {user_name}. "
                    f"Our AI systems are being recalibrated. Try again in a moment."
                )
            
            content = resp.get('text', '').strip()
            if not content:
                return f"💼 <b>{bot_name}:</b> Strategic desk is silent. Stand by."
                
            # Save response to history
            await self.db.append_chat_history(user_id, "assistant", content)
            return f"🎖️ <b>{bot_name}:</b>\n\n{content}"
            
        except Exception as e:
            logger.error(f"[AGENT_0] Professional response failed: {e}")
            return f"💼 <b>{bot_name}:</b> Strategic desk connection unstable. Stand by, {user_name}."

    # ─────────────────────────────────────────────────────────────────
    # STEP 1: NLP — Parse User Intent with Haiku
    # ─────────────────────────────────────────────────────────────────

    async def _parse_intent_with_llm(self, text: str) -> Dict:
        """Use Claude Haiku to translate freeform text → structured intent."""
        system_prompt = (
            "You are an AI assistant that translates crypto trading bot commands into structured JSON. "
            "The user is the managing director of an autonomous trading firm."
        )
        prompt = f"""Translate this user command into a structured JSON intent.

USER COMMAND: "{text}"

Valid actions:
- REDUCE_RISK: Lower position sizes or daily loss limit (defensive)
- RAISE_RISK: Increase position sizes or daily loss limit (offensive, needs approval)
- INCREASE_POSITION_SIZE: Explicitly increase position % (offensive)
- LOWER_POSITION_SIZE: Explicitly lower position % (defensive)
- TIGHTEN_LOSS_LIMIT: Lower daily loss limit % (defensive)
- LOOSEN_LOSS_LIMIT: Raise daily loss limit % (offensive)
- PAUSE_TRADING: Pause all trading activity (defensive)
- RESUME_TRADING: Resume trading (defensive)
- RAISE_THRESHOLD: Increase Agent 5 min score threshold, more selective (defensive)
- LOWER_THRESHOLD: Decrease Agent 5 min score threshold, less selective (offensive)
- MAINTAIN: No changes needed
- STATUS: User wants a status report
- UNCLEAR: You couldn't understand the request

Respond ONLY with JSON:
{{
  "action": "<action>",
  "reasoning": "<one sentence: why you mapped it to this action>",
  "suggested_params": {{
    "position_size_pct": <float or null>,
    "loss_limit_pct": <float or null>,
    "min_pass_score": <float or null>
  }}
}}"""

        try:
            resp = await self.llm.create_message(
                model_type=self.haiku_type,
                system_prompt=system_prompt,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=300,
                temperature=0.1
            )
            return json.loads(resp.get("text", "{}"))
        except Exception as e:
            logger.error(f"[AGENT_0] Intent parsing failed: {e}")
            return {"action": "UNCLEAR", "reasoning": str(e)}

    # ─────────────────────────────────────────────────────────────────
    # STEP 2: Gather Agent Votes (Agent 6 Macro + Agent 7 Risk State)
    # ─────────────────────────────────────────────────────────────────

    async def _assess_proposal_with_agents(self, intent: Dict, user_id: str = "default_user") -> Dict:
        """Gather intelligence from Agent 6 and Agent 7 to build the briefing."""
        votes = {}

        # Agent 6: Macro Regime
        try:
            macro_regime = await self.db.get_system_state("macro_regime") or "unknown"
            macro_summary = await self.db.get_system_state("macro_summary") or "No macro data available"
            votes["agent_6_macro"] = {
                "regime": macro_regime,
                "summary": macro_summary[:200]
            }
        except Exception as e:
            votes["agent_6_macro"] = {"regime": "unknown", "summary": f"Error: {e}"}

        # Agent 7: Risk State
        try:
            today = datetime.utcnow().strftime("%Y-%m-%d")
            pnl_state = await self.db.get_daily_portfolio_state(user_id, today)
            ks_state = await self.db.get_kill_switch(user_id)
            risk_tier_high = float(await self.db.get_system_state("risk_tier_high") or 0.20)
            loss_limit = float(await self.db.get_system_state("daily_loss_limit_pct") or 0.30)

            realized_loss = pnl_state.get("realized_loss_usd", 0.0)
            daily_limit = pnl_state.get("daily_loss_limit_usd", 999.0)
            loss_pct = (realized_loss / daily_limit * 100) if daily_limit > 0 else 0

            votes["agent_7_risk"] = {
                "kill_switch_tier": ks_state.get("tier", 0),
                "daily_loss_pct_used": round(loss_pct, 1),
                "current_position_pct": round(risk_tier_high * 100, 1),
                "current_loss_limit_pct": round(loss_limit * 100, 1)
            }
        except Exception as e:
            votes["agent_7_risk"] = {"error": str(e)}

        return votes

    # ─────────────────────────────────────────────────────────────────
    # STEP 3A: Auto-Apply Defensive Actions
    # ─────────────────────────────────────────────────────────────────

    async def _auto_apply_defensive(self, intent: Dict, user_id: str = "default_user"):
        """Apply defensive action immediately without approval."""
        action = intent.get("action")
        params = intent.get("suggested_params", {})

        try:
            if action == "PAUSE_TRADING":
                await self.db.set_system_state("is_paused", "true")
                logger.info("[AGENT_0] 🛡️ AUTO-APPLIED: Paused trading")

            elif action == "RESUME_TRADING":
                await self.db.set_system_state("is_paused", "false")
                logger.info("[AGENT_0] ✅ AUTO-APPLIED: Resumed trading")

            elif action in {"REDUCE_RISK", "LOWER_POSITION_SIZE"}:
                new_pct = params.get("position_size_pct")
                if new_pct:
                    await self.db.set_system_state("risk_tier_high", str(new_pct))
                    logger.info(f"[AGENT_0] 🛡️ AUTO-APPLIED: position size → {new_pct:.1%}")

            elif action == "TIGHTEN_LOSS_LIMIT":
                new_limit = params.get("loss_limit_pct")
                if new_limit:
                    await self.db.set_system_state("daily_loss_limit_pct", str(new_limit))
                    logger.info(f"[AGENT_0] 🛡️ AUTO-APPLIED: daily loss limit → {new_limit:.1%}")

            elif action == "RAISE_THRESHOLD":
                new_score = params.get("min_pass_score")
                if new_score:
                    await self.db.set_system_state("agent_5_min_score", str(new_score))
                    logger.info(f"[AGENT_0] 🛡️ AUTO-APPLIED: Agent 5 min score → {new_score}")

        except Exception as e:
            logger.error(f"[AGENT_0] Failed to auto-apply defensive action: {e}")

    # ─────────────────────────────────────────────────────────────────
    # STEP 3B: Create Approval Request (Offensive Actions)
    # ─────────────────────────────────────────────────────────────────

    async def _create_approval_request(self, intent: Dict, agent_votes: Dict, user_id: str) -> str:
        """Store the proposal in DB and return the proposal_id."""
        proposal_id = uuid.uuid4().hex[:8]
        reasoning = intent.get("reasoning", "Strategic adjustment requested")

        await self.db.create_pending_approval(
            user_id=user_id,
            proposal_id=proposal_id,
            action_json=intent,
            reasoning=reasoning,
            agent_votes=agent_votes
        )
        logger.info(f"[AGENT_0] 📋 Approval request created: {proposal_id}")
        return proposal_id

    # ─────────────────────────────────────────────────────────────────
    # RESOLVE: Process /approve or /reject from Telegram
    # ─────────────────────────────────────────────────────────────────

    async def resolve_approval(self, proposal_id: str, approved: bool, user_id: str = "default_user") -> str:
        """
        Called when you reply /approve <id> or /reject <id> on Telegram.
        Returns a status string to send back.
        """
        proposal = await self.db.get_pending_approval(proposal_id)

        if not proposal:
            return f"❌ Proposal <code>{proposal_id}</code> not found or already resolved."

        if proposal.get("status") != "pending":
            return f"⚠️ Proposal <code>{proposal_id}</code> is already <b>{proposal['status']}</b>."

        if not approved:
            await self.db.resolve_pending_approval(proposal_id, "rejected")
            logger.info(f"[AGENT_0] ❌ Proposal {proposal_id} rejected by user.")
            return f"❌ <b>Proposal {proposal_id} rejected.</b> No changes applied."

        # Apply the action
        intent = proposal.get("action_json", {})
        action = intent.get("action", "UNKNOWN")

        try:
            params = intent.get("suggested_params", {})

            if action in {"RAISE_RISK", "INCREASE_POSITION_SIZE"}:
                new_pct = params.get("position_size_pct")
                if new_pct:
                    await self.db.set_system_state("risk_tier_high", str(new_pct))

            elif action == "LOOSEN_LOSS_LIMIT":
                new_limit = params.get("loss_limit_pct")
                if new_limit:
                    await self.db.set_system_state("daily_loss_limit_pct", str(new_limit))

            elif action == "LOWER_THRESHOLD":
                new_score = params.get("min_pass_score")
                if new_score:
                    await self.db.set_system_state("agent_5_min_score", str(new_score))

            await self.db.resolve_pending_approval(proposal_id, "approved")
            logger.info(f"[AGENT_0] ✅ Proposal {proposal_id} approved and applied: {action}")
            return (
                f"✅ <b>Proposal {proposal_id} approved and applied.</b>\n\n"
                f"Action: <b>{action}</b>\n"
                f"Params: <code>{json.dumps(params)}</code>"
            )

        except Exception as e:
            logger.error(f"[AGENT_0] Failed to apply approved proposal {proposal_id}: {e}")
            return f"❌ <b>Error applying proposal {proposal_id}:</b> {e}"

    # ─────────────────────────────────────────────────────────────────
    # FORMATTING: Telegram message builders
    # ─────────────────────────────────────────────────────────────────

    def _format_defensive_notification(self, intent: Dict, agent_votes: Dict) -> str:
        """Format a Telegram notification for an auto-applied defensive action."""
        action = intent.get("action", "UNKNOWN")
        reasoning = intent.get("reasoning", "")
        macro = agent_votes.get("agent_6_macro", {})
        risk = agent_votes.get("agent_7_risk", {})

        return (
            f"🛡️ <b>Commander — Defensive Action Applied</b>\n\n"
            f"📊 <b>Agent 6 (Macro):</b> Regime = <b>{macro.get('regime', 'unknown').upper()}</b>\n"
            f"<i>{macro.get('summary', 'N/A')}</i>\n\n"
            f"⚖️ <b>Agent 7 (Risk):</b> Kill Switch Tier <b>{risk.get('kill_switch_tier', 0)}</b> | "
            f"Daily loss used: <b>{risk.get('daily_loss_pct_used', 0)}%</b> | "
            f"Position cap: <b>{risk.get('current_position_pct', 0)}%</b>\n\n"
            f"🧠 <b>My Reading:</b> {reasoning}\n\n"
            f"✅ Action <b>{action}</b> has been applied automatically.\n"
            f"<i>No approval needed for defensive moves.</i>"
        )

    def _format_approval_request(self, intent: Dict, agent_votes: Dict, proposal_id: str) -> str:
        """Format a Telegram approval request for an offensive action."""
        action = intent.get("action", "UNKNOWN")
        reasoning = intent.get("reasoning", "")
        params = intent.get("suggested_params", {})
        macro = agent_votes.get("agent_6_macro", {})
        risk = agent_votes.get("agent_7_risk", {})

        params_str = ""
        if params.get("position_size_pct"):
            params_str += f"Position size → <b>{params['position_size_pct']:.1%}</b> "
        if params.get("loss_limit_pct"):
            params_str += f"Loss limit → <b>{params['loss_limit_pct']:.1%}</b> "
        if params.get("min_pass_score"):
            params_str += f"Min score → <b>{params['min_pass_score']}</b>"

        return (
            f"🎖️ <b>Commander Proposal — Needs Your Approval</b>\n\n"
            f"📊 <b>Agent 6 (Macro):</b> Regime = <b>{macro.get('regime', 'unknown').upper()}</b>\n"
            f"<i>{macro.get('summary', 'N/A')}</i>\n\n"
            f"⚖️ <b>Agent 7 (Risk):</b> Kill Switch Tier <b>{risk.get('kill_switch_tier', 0)}</b> | "
            f"Daily loss used: <b>{risk.get('daily_loss_pct_used', 0)}%</b>\n\n"
            f"🧠 <b>My Reading:</b> {reasoning}\n\n"
            f"📋 <b>Proposed Change:</b> {params_str or action}\n\n"
            f"⚠️ <i>This is an offensive action. It increases risk exposure.</i>\n\n"
            f"Reply:\n"
            f"✅ <code>/approve {proposal_id}</code> to confirm\n"
            f"❌ <code>/reject {proposal_id}</code> to cancel\n"
            f"━━━━━━━━\n"
            f"<i>Proposal ID: {proposal_id} | Expires in 30 mins</i>"
        )

    async def _get_status_report(self, user_id: str = "default_user") -> str:
        """Return a quick system status snapshot."""
        try:
            today = datetime.utcnow().strftime("%Y-%m-%d")
            is_paused = await self.db.get_system_state("is_paused") == "true"
            ks_state = await self.db.get_kill_switch(user_id)
            pnl = await self.db.get_daily_portfolio_state(user_id, today)
            pending = await self.db.get_pending_approvals(user_id)
            macro_regime = await self.db.get_system_state("macro_regime") or "unknown"
            risk_pct = float(await self.db.get_system_state("risk_tier_high") or 0.20)
            loss_limit = float(await self.db.get_system_state("daily_loss_limit_pct") or 0.30)

            status_icon = "⏸️ PAUSED" if is_paused else "🟢 ONLINE"
            ks_tier = ks_state.get("tier", 0)
            realized = pnl.get("realized_loss_usd", 0.0)
            limit_usd = pnl.get("daily_loss_limit_usd", 999.0)

            pending_str = f"\n📋 <b>Pending Approvals:</b> {len(pending)}" if pending else ""

            return (
                f"🎖️ <b>COMMANDER STATUS REPORT</b>\n\n"
                f"System: <b>{status_icon}</b>\n"
                f"Kill Switch: Tier <b>{ks_tier}</b>\n"
                f"Macro Regime: <b>{macro_regime.upper()}</b>\n\n"
                f"<b>Risk Parameters:</b>\n"
                f"  Position Size (High): <b>{risk_pct:.0%}</b>\n"
                f"  Daily Loss Limit: <b>{loss_limit:.0%}</b>\n\n"
                f"<b>Today's PnL:</b>\n"
                f"  Realized Loss: <b>${realized:.4f}</b> / ${limit_usd:.4f} limit\n"
                f"{pending_str}\n\n"
                f"<i>As of {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}</i>"
            )
        except Exception as e:
            return f"❌ Status report error: {e}"

    def get_model_info(self) -> str:
        """Return information about the active LLM models."""
        from src.utils.llm_client import LLMClient
        models = LLMClient.MODELS
        active_id = models.get(self.model_type, "Unknown")
        
        return (
            f"🤖 <b>LLM INFRASTRUCTURE REPORT</b>\n\n"
            f"Strategic Model: <b>Claude Haiku 4.5</b>\n"
            f"Active Model ID: <code>{active_id}</code>\n"
            f"Mapping Key: <code>{self.model_type}</code>\n\n"
            f"<i>Model scaling is currently optimized for professional Wall Street persona and real-time strategic oversight.</i>"
        )

    async def execute_pause(self) -> str:
        """Immediately pause all trading operations."""
        try:
            await self.db.set_system_state("is_paused", "true")
            logger.info("[AGENT_0] ⏸️ System paused via slash command.")
            return "⏸️ <b>System Paused.</b> All trading operations have been halted by executive order."
        except Exception as e:
            logger.error(f"[AGENT_0] Pause failed: {e}")
            return f"❌ <b>Error:</b> Failed to pause system. {e}"

    async def execute_resume(self, user_id: str = "default_user") -> str:
        """Resume trading operations and clear any active Tier 3 kill switches."""
        try:
            # 1. Clear pause state
            await self.db.set_system_state("is_paused", "false")
            
            # 2. Clear Tier 3 Kill Switch if present
            ks_state = await self.db.get_kill_switch(user_id)
            if ks_state.get("tier") == 3:
                await self.db.clear_kill_switch(user_id, "user")
                logger.info(f"[AGENT_0] ✅ System resumed and Tier 3 Kill Switch cleared via /resume")
                return "✅ <b>System Resumed.</b> Trading operations online and Tier 3 Kill Switch has been cleared."
            
            logger.info("[AGENT_0] ✅ System resumed via slash command.")
            return "✅ <b>System Resumed.</b> Trading operations are now online."
        except Exception as e:
            logger.error(f"[AGENT_0] Resume failed: {e}")
            return f"❌ <b>Error:</b> Failed to resume system. {e}"

    # ─────────────────────────────────────────────────────────────────
    # STRATEGIC REVIEW (4-hour periodic job, now with semi-autonomous logic)
    # ─────────────────────────────────────────────────────────────────

    async def run_strategic_review(self, user_id: str = "default_user") -> Dict:
        """
        Conduct a top-level review of the firm's status and adjust parameters.
        Called every 4 hours by the scheduler.
        Defensive actions are auto-applied. Offensive ones are sent as approval requests.
        """
        try:
            today = datetime.utcnow().strftime("%Y-%m-%d")
            pnl_state = await self.db.get_daily_portfolio_state(user_id, today)
            ks_state = await self.db.get_kill_switch(user_id)
            is_paused = await self.db.get_system_state("is_paused") == "true"
            macro_regime = await self.db.get_system_state("macro_regime") or "unknown"

            positions = await self.db.get_all_positions(user_id)
            closed_trades = positions.get("closed", [])[-10:]

            current_config = {
                "risk_tier_high": float(await self.db.get_system_state("risk_tier_high") or 0.20),
                "daily_loss_limit": float(await self.db.get_system_state("daily_loss_limit_pct") or 0.30),
                "agent_5_min_score": float(await self.db.get_system_state("agent_5_min_score") or 8.0)
            }

            system_report = {
                "daily_realized_loss_usd": pnl_state.get("realized_loss_usd", 0),
                "daily_loss_limit_usd": pnl_state.get("daily_loss_limit_usd", 999),
                "kill_switch_tier": ks_state.get("tier", 0),
                "is_paused": is_paused,
                "macro_regime": macro_regime,
                "recent_trades": [
                    {"token": t.get("token"), "pnl": t.get("pnl_usd"),
                     "outcome": "win" if t.get("pnl_usd", 0) > 0 else "loss"}
                    for t in closed_trades
                ],
                "current_config": current_config
            }

            system_prompt = (
                "You are the Managing Director of an elite HFT crypto firm on Solana. "
                "Analyze performance and market data to decide if parameters should be tuned. "
                "Prefer MAINTAIN unless data clearly signals an adjustment is needed."
            )

            prompt = f"""QUARTERLY STRATEGIC REVIEW — {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}

SYSTEM REPORT:
{json.dumps(system_report, indent=2)}

INSTRUCTIONS:
- If losing (win rate < 40%): suggest REDUCE_RISK
- If market is choppy/bearish: suggest RAISE_THRESHOLD
- If PnL is very positive and regime is bullish: suggest RAISE_RISK (this will need boss approval)
- Otherwise: MAINTAIN

Respond with ONLY this JSON structure:
{{
  "action": "REDUCE_RISK" | "RAISE_RISK" | "RAISE_THRESHOLD" | "LOWER_THRESHOLD" | "MAINTAIN",
  "reasoning": "One clear paragraph explaining your recommendation citing the data.",
  "agent_votes": {{
    "agent_6_macro": "Brief macro context.",
    "agent_7_risk": "Brief risk state observation."
  }},
  "suggested_params": {{
    "position_size_pct": <float or null>,
    "loss_limit_pct": <float or null>,
    "min_pass_score": <float or null>
  }}
}}"""

            messages = [{"role": "user", "content": prompt}]
            response = await self.llm.create_message(
                model_type=self.model_type,
                system_prompt=system_prompt,
                messages=messages,
                max_tokens=600,
                temperature=0.1
            )

            order = json.loads(response.get("text", "{}"))
            action = order.get("action", "MAINTAIN")
            agent_votes = order.get("agent_votes", {})

            logger.info(f"[AGENT_0] 🎖️ STRATEGIC REVIEW ORDER: {action} | {order.get('reasoning', '')[:100]}")

            if action in DEFENSIVE_ACTIONS:
                await self._auto_apply_defensive(order, user_id)
                if self.telegram:
                    msg = self._format_defensive_notification(order, {
                        "agent_6_macro": {"regime": macro_regime, "summary": agent_votes.get("agent_6_macro", "")},
                        "agent_7_risk": {"kill_switch_tier": ks_state.get("tier", 0),
                                         "daily_loss_pct_used": 0,
                                         "current_position_pct": current_config["risk_tier_high"] * 100}
                    })
                    await self.telegram.send_status_update({"message": msg})

            elif action in OFFENSIVE_ACTIONS:
                proposal_id = await self._create_approval_request(order, {
                    "agent_6_macro": {"regime": macro_regime, "summary": agent_votes.get("agent_6_macro", "")},
                    "agent_7_risk": {"kill_switch_tier": ks_state.get("tier", 0)}
                }, user_id)
                if self.telegram:
                    msg = self._format_approval_request(order, {
                        "agent_6_macro": {"regime": macro_regime, "summary": agent_votes.get("agent_6_macro", "")},
                        "agent_7_risk": {"kill_switch_tier": ks_state.get("tier", 0),
                                         "daily_loss_pct_used": 0}
                    }, proposal_id)
                    await self.telegram.send_status_update({"message": msg})

            return order

        except Exception as e:
            logger.error(f"[AGENT_0] Strategic review failed: {e}")
            return {"action": "ERROR", "reason": str(e)}

    async def _apply_config_overrides(self, overrides: Dict):
        """Persist new parameters (kept for backward compatibility)."""
        try:
            if "risk" in overrides:
                risk = overrides["risk"]
                if "high" in risk:
                    await self.db.set_system_state("risk_tier_high", str(risk["high"]))
                if "loss_limit" in risk:
                    await self.db.set_system_state("daily_loss_limit_pct", str(risk["loss_limit"]))
            if "weights" in overrides:
                await self.db.set_system_state("agent_weights_json", json.dumps(overrides["weights"]))
            if "min_pass_score" in overrides:
                await self.db.set_system_state("agent_5_min_score", str(overrides["min_pass_score"]))
        except Exception as e:
            logger.error(f"[AGENT_0] Failed to apply overrides: {e}")


if __name__ == "__main__":
    import sys
    import os
    sys.path.append(os.getcwd())
    from src.database import Database
    db = Database()
    commander = Agent0Commander(db)
    # commander.run_strategic_review()
