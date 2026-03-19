import logging
import json
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta

from src.utils.llm_client import LLMClient
logger = logging.getLogger(__name__)

@dataclass
class TradeInstruction:
    """
    Fully-sized, risk-approved trade instruction sent to Agent 8.
    All fields are required before execution.
    """
    token_address: str
    token_symbol: str
    entry_price: float
    position_size_usd: float
    stop_loss_price: float
    stop_loss_pct: float
    take_profit_1_price: float
    take_profit_1_pct: float
    take_profit_1_sell_pct: float   # e.g. 0.40 (sell 40% at TP1)
    take_profit_2_price: float
    take_profit_2_pct: float
    take_profit_2_sell_pct: float   # e.g. 0.40 (sell 40% at TP2)
    trailing_stop_pct: float        # e.g. 0.50 (trail 50% from peak)
    confidence_score: float
    market_regime: str
    agent_5_composite: float
    issued_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    approved_by: str = "Agent7_RiskManager"
    refined_by: Optional[str] = None # e.g. "Claude_3_5_Sonnet"
    refinement_reason: Optional[str] = None
    strategy_breakdown: List[str] = field(default_factory=list)
    sl_tp_rationale: Optional[str] = None


class Agent7RiskManager:
    """
    CFO of the trading firm. Validates every trade before execution.
    Enforces hard limits that NO other agent can override.

    All parameters are percentage-based — scales for any account size.
    """

    KILL_SWITCH = False  # Firm-wide trading halt — flip to True to stop all execution

    def __init__(self, db=None, config: Dict = None, starting_capital: float = 10.0):
        self.config = config or {}
        self.db = None
        
        # ── Capital ────────────────────────────────────────────────────
        self.starting_capital  = starting_capital
        self.available_capital = starting_capital  # Updated from DB if available

        # ── Risk parameters (all % of capital — strict enforcement) ──
        # Risk Tiers are hardcoded and cannot be overridden by AI
        self.position_size_pcts = {
            "high":    0.20,   # 20% of capital — confidence ≥9.0
            "medium":  0.10,   # 10% of capital — confidence ≥8.0
            "low":     0.05,   # 5%  of capital — confidence ≥7.0
            "venture": 0.02    # 2%  of capital — confidence ≥6.0
        }

        self.daily_loss_limit_pct    = 0.30   # 30% of capital
        self.max_position_exposure_pct = 0.30  # 30% cap per trade
        self.max_daily_trades = 5

        # ── SL / TP parameters (price-based %) ─────────────────────────
        self.stop_loss_pct           = 0.20   # SL at -20% 
        self.take_profit_1_mult      = 2.00   # TP1 at 2× 
        self.take_profit_1_sell_pct  = 0.40   # Sell 40% at TP1
        self.take_profit_2_mult      = 4.00   # TP2 at 4× 
        self.take_profit_2_sell_pct  = 0.40   # Sell 40% at TP2
        self.trailing_stop_pct       = 0.50   # Trail 50% from peak

        # ── Daily tracking ──────────────────
        self.daily_loss_usd       = 0.0
        self.daily_trades_count   = 0
        self.last_reset_date      = datetime.utcnow().date()
        self.trading_bot          = None # Set during initialization in main.py

        logger.info(f"[AGENT_7] Risk Manager initialized | HARD LIMIT ENFORCER mode active")


    # ─────────────────────────────────────────────────────────────────
    # DAILY RESET
    # ─────────────────────────────────────────────────────────────────

    async def _check_and_reset_daily(self, user_id: str = "default_user"):
        """Reset daily counters at midnight UTC and auto-recover Tier 2."""
        today = datetime.utcnow().date()
        if today > self.last_reset_date:
            logger.info(f"[AGENT_7] Daily reset | Previous loss: ${self.daily_loss_usd:.2f}")
            self.daily_loss_usd     = 0.0
            self.daily_trades_count = 0
            self.last_reset_date    = today
            
            if self.db:
                # Update today's PnL to 0 in DB
                await self.db.update_daily_portfolio_state(user_id, today.strftime("%Y-%m-%d"), realized_loss_usd=0.0)
                
                # Auto-recover Tier 2 Kill Switch
                ks_state = await self.db.get_kill_switch(user_id)
                if ks_state.get("tier") == 2:
                    await self.db.clear_kill_switch(user_id, "system_midnight_reset")
                    logger.info(f'[AGENT_7] 🔄 Daily reset: Auto-recovered Tier 2 Kill Switch for {user_id}.')

    # ─────────────────────────────────────────────────────────────────
    # POSITION SIZING
    # ─────────────────────────────────────────────────────────────────

    def _calculate_position_size(self, composite_score: float, market_regime: str) -> float:
        """
        Calculate position size as a percentage of available capital.
        Scales automatically for any account size.

        Confidence tiers (% of capital):
          - Score ≥9.0 → 'high'   tier → 20% of capital
          - Score ≥8.0 → 'medium' tier → 10% of capital
          - Score ≥6.0 → 'low'    tier →  5% of capital

        Regime multipliers:
          - bullish: ×1.0 (full allocation)
          - mixed:   ×0.8
          - flat:    ×0.7
          - choppy:  ×0.5 (reduced allocation — volatile market)

        Result is capped by max_position_exposure_pct (30% default).

        Returns:
            Position size in USD (scales with account)
        """
        # Select base tier percentage
        if composite_score >= 9.0:
            base_pct = self.position_size_pcts["high"]
            tier     = "high"
        elif composite_score >= 8.0:
            base_pct = self.position_size_pcts["medium"]
            tier     = "medium"
        elif composite_score >= 7.0:
            base_pct = self.position_size_pcts["low"]
            tier     = "low"
        else:
            base_pct = self.position_size_pcts["venture"]
            tier     = "venture"

        # Market regime adjustment
        regime_multiplier = {
            "bullish": 1.0,
            "mixed":   0.8,
            "flat":    0.7,
            "choppy":  0.5,
        }.get(market_regime, 0.8)

        # Calculate final percentage and enforce exposure cap
        adjusted_pct = min(base_pct * regime_multiplier, self.max_position_exposure_pct)

        # Convert to USD using current available capital
        position_usd = self.available_capital * adjusted_pct

        logger.info(
            f"[AGENT_7] Position sizing: tier={tier} ({base_pct:.0%}) "
            f"× regime={market_regime} ({regime_multiplier:.1f}) "
            f"= {adjusted_pct:.1%} of ${self.available_capital:.2f} "
            f"→ ${position_usd:.4f}"
        )
        return round(position_usd, 6)  # 6 decimal places for micro-cap tokens

    # ─────────────────────────────────────────────────────────────────
    # VALIDATION CHECKS
    # ─────────────────────────────────────────────────────────────────

    async def _check_kill_switch(self, user_id: str, token_symbol: str) -> Tuple[bool, Optional[str], float]:
        """
        Enforce the 3-Tier Kill Switch strictly reading from DB.
        Returns: (passed: bool, reason: str | None, size_multiplier: float)
        """
        if Agent7RiskManager.KILL_SWITCH:
            return False, "GLOBAL SYSTEM KILL SWITCH ACTIVE — all trading halted", 1.0

        if not self.db:
            return True, None, 1.0

        ks_state = await self.db.get_kill_switch(user_id)
        tier = ks_state.get("tier", 0)
        active_since = ks_state.get("active_since")
        affected_tokens = ks_state.get("affected_tokens", [])

        # Auto-recovery for Tier 1
        if tier == 1 and active_since:
            activation_time = datetime.fromisoformat(active_since)
            if datetime.utcnow() > activation_time + timedelta(hours=2):
                logger.info(f"[AGENT_7] Tier 1 auto-recovery 2h cooldown expired for {user_id}.")
                await self.db.clear_kill_switch(user_id, "system_auto_recovery")
                ks_state = await self.db.get_kill_switch(user_id) # Refresh
                tier = ks_state.get("tier", 0)
                affected_tokens = ks_state.get("affected_tokens", [])

        if tier == 3:
            return False, "Tier 3 Full Stop Active. Manual resume required.", 1.0
        if tier == 2:
            return False, "Tier 2 Defense Active. Portfolio-wide block.", 1.0
        if tier == 1:
            if token_symbol in affected_tokens:
                return False, f"Tier 1 Caution Active for {token_symbol}.", 1.0
            else:
                return True, "Tier 1 Caution Active - Sizing reduced", 0.70

        return True, None, 1.0

    def _check_daily_loss_limit(self) -> Tuple[bool, Optional[str]]:
        """Block trading if today's losses exceed the configured % of capital."""
        limit_usd = self.available_capital * self.daily_loss_limit_pct
        if self.daily_loss_usd >= limit_usd:
            return False, (
                f"Daily loss limit reached: ${self.daily_loss_usd:.4f} / "
                f"${limit_usd:.4f} ({self.daily_loss_limit_pct:.0%} of "
                f"${self.available_capital:.2f} capital)"
            )
        return True, None

    def _check_daily_trade_count(self) -> Tuple[bool, Optional[str]]:
        if self.daily_trades_count >= self.max_daily_trades:
            return False, (
                f"Daily trade limit reached: {self.daily_trades_count} / "
                f"{self.max_daily_trades}"
            )
        return True, None

    def _check_capital_available(self, position_size: float) -> Tuple[bool, Optional[str]]:
        """Ensure position does not exceed max exposure % of capital."""
        max_allowed = self.available_capital * self.max_position_exposure_pct
        if position_size > max_allowed:
            return False, (
                f"Position ${position_size:.4f} exceeds "
                f"{self.max_position_exposure_pct:.0%} cap "
                f"(max: ${max_allowed:.4f} of ${self.available_capital:.2f} capital)"
            )
        return True, None

    # ─────────────────────────────────────────────────────────────────
    # MAIN: VALIDATE & PRODUCE TRADE INSTRUCTION
    # ─────────────────────────────────────────────────────────────────

    async def validate_and_size(
        self,
        agent_5_signal: Dict,
        agent_6_result: Dict,
        entry_price: float,
        user_id: str = "default_user",
        agent_analysis: Optional[Dict] = None
    ) -> Tuple[bool, Optional[TradeInstruction], str]:
        """
        Full risk validation and trade instruction creation.
        """
        await self._check_and_reset_daily()

        token_address  = agent_5_signal.get("token_address", "")
        token_symbol   = agent_5_signal.get("token_symbol", "UNKNOWN")
        composite      = agent_5_signal.get("composite_score", 0.0)
        market_regime  = agent_6_result.get("market_regime", "mixed")

        # ── COMMAND OVERRIDES ──
        if self.db:
            try:
                # Override high tier pct
                tier_high_override = await self.db.get_system_state("risk_tier_high")
                if tier_high_override:
                    self.position_size_pcts["high"] = float(tier_high_override)
                    logger.info(f"[AGENT_7] 🎖️ COMMAND OVERRIDE: risk_tier_high={tier_high_override}")
                
                # Override daily loss limit
                loss_limit_override = await self.db.get_system_state("daily_loss_limit_pct")
                if loss_limit_override:
                    self.daily_loss_limit_pct = float(loss_limit_override)
                    logger.info(f"[AGENT_7] 🎖️ COMMAND OVERRIDE: daily_loss_limit_pct={loss_limit_override}")
            except Exception as e:
                logger.error(f"[AGENT_7] Failed to apply Commander overrides: {e}")

        logger.info(f"[AGENT_7] Validating trade: {token_symbol} | score={composite:.2f}")

        # Run all gating checks in order
        ks_passed, ks_reason, size_multiplier = await self._check_kill_switch(user_id, token_symbol)
        if not ks_passed:
            logger.warning(f"[AGENT_7] ❌ RISK_BLOCKED: {token_symbol} | {ks_reason}")
            return False, None, ks_reason
            
        checks = [
            self._check_daily_loss_limit(),
            self._check_daily_trade_count(),
        ]

        for passed, reason in checks:
            if not passed:
                logger.warning(f"[AGENT_7] ❌ RISK_BLOCKED: {token_symbol} | {reason}")
                return False, None, reason

        # Calculate position size
        position_usd = self._calculate_position_size(composite, market_regime)
        if size_multiplier != 1.0:
            logger.info(f"[AGENT_7] Applying Tier 1 Caution Multiplier x{size_multiplier} to position size")
            position_usd *= size_multiplier

        # Capital exposure check
        cap_ok, cap_reason = self._check_capital_available(position_usd)
        if not cap_ok:
            logger.warning(f"[AGENT_7] ❌ RISK_BLOCKED: {token_symbol} | {cap_reason}")
            return False, None, cap_reason

        # Build SL/TP prices from entry price + configured multiples
        # NEW: Apply tighter Stop Loss (10%) for Venture tier
        sl_pct = self.stop_loss_pct
        if composite < 8.0:
            sl_pct = 0.10  # 10% SL for Low/Venture tiers to protect capital
            logger.info(f"[AGENT_7] 🛡️ Tighter SL activated for {token_symbol} (-10.0%)")

        sl_price  = entry_price * (1 - sl_pct)
        tp1_price = entry_price * self.take_profit_1_mult
        tp2_price = entry_price * self.take_profit_2_mult

        # Generate strategy breakdown and rationale
        strategy_breakdown = []
        if composite >= 9.0:
            strategy_breakdown.append("High-confidence signal aggregation")
        if agent_6_result.get('bollinger_squeeze'):
            strategy_breakdown.append("Bollinger Band Squeeze breakout detected")
        if agent_6_result.get('rsi_divergence'):
            strategy_breakdown.append("RSI Divergence reversal confirmation")
        if agent_analysis and agent_analysis.get('agent_3_wallets', {}).get('status') == 'CLEARED':
            strategy_breakdown.append("Smart Money tracking: Heavy whale accumulation")
        
        tier = "unknown"
        if composite >= 9.0: tier = "high"
        elif composite >= 8.0: tier = "medium"
        elif composite >= 7.0: tier = "low"
        elif composite >= 6.0: tier = "venture"
        
        sl_tp_rationale = f"Risk Tier: {tier.upper()}."
        if tier == "venture":
            sl_tp_rationale += " Tight 10% SL for capital preservation on low-confidence entry."
        elif tier == "low":
            sl_tp_rationale += " 10% SL for defensive positioning."
        else:
            sl_tp_rationale += f" Standard {self.stop_loss_pct:.0%} SL for normalized volatility."

        instruction = TradeInstruction(
            token_address          = token_address,
            token_symbol           = token_symbol,
            entry_price            = entry_price,
            position_size_usd      = position_usd,
            stop_loss_price        = sl_price,
            stop_loss_pct          = sl_pct,
            take_profit_1_price    = tp1_price,
            take_profit_1_pct      = self.take_profit_1_mult,
            take_profit_1_sell_pct = self.take_profit_1_sell_pct,
            take_profit_2_price    = tp2_price,
            take_profit_2_pct      = self.take_profit_2_mult,
            take_profit_2_sell_pct = self.take_profit_2_sell_pct,
            trailing_stop_pct      = self.trailing_stop_pct,
            confidence_score       = composite,
            market_regime          = market_regime,
            agent_5_composite      = composite,
            strategy_breakdown     = strategy_breakdown,
            sl_tp_rationale        = sl_tp_rationale
        )


        # ── HARD RISK LIMITS (No AI Overrides) ──
        logger.info(
            f"[AGENT_7] ✅ RISK_APPROVED: {token_symbol} | "
            f"Size=${instruction.position_size_usd:.4f} | "
            f"SL={instruction.stop_loss_pct:.1%} | "
            f"TP1={instruction.take_profit_1_pct:.1f}x"
        )
        return True, instruction, "APPROVED"

    async def record_trade_result(self, token_symbol: str, pnl_usd: float, user_id: str = "default_user"):
        """
        Record post-trade P&L for daily loss tracking.
        Updates daily_loss_usd which is checked against the % threshold.
        """
        await self._check_and_reset_daily()
        if pnl_usd < 0:
            self.daily_loss_usd += abs(pnl_usd)
        self.daily_trades_count += 1
        limit_usd = self.available_capital * self.daily_loss_limit_pct
        
        if self.db:
            today = datetime.utcnow().strftime("%Y-%m-%d")
            await self.db.update_daily_portfolio_state(user_id, today, realized_loss_usd=self.daily_loss_usd)

        logger.info(
            f"[AGENT_7] Trade recorded: {token_symbol} P&L=${pnl_usd:+.4f} | "
            f"Daily loss: ${self.daily_loss_usd:.4f} / ${limit_usd:.4f} "
            f"({self.daily_loss_limit_pct:.0%} of ${self.available_capital:.2f})"
        )
        
        if pnl_usd < 0:
            await self.evaluate_tier_triggers(user_id, token_symbol)

    async def evaluate_tier_triggers(self, user_id: str, trigger_token: str = ""):
        """
        Calculates losses and upgrades Kill Switch tiers if thresholds are breached.
        """
        if not self.db:
            return
            
        limit_usd = self.available_capital * self.daily_loss_limit_pct
        loss_ratio = self.daily_loss_usd / limit_usd if limit_usd > 0 else 0
        
        current_state = await self.db.get_kill_switch(user_id)
        current_tier = current_state.get("tier", 0)

        new_tier = current_tier
        reason = ""
        tokens = current_state.get("affected_tokens", [])

        if loss_ratio >= 1.0 and current_tier < 3:
            new_tier = 3
            reason = f"Daily loss limit fully breached ({loss_ratio*100:.1f}%)"
            tokens = []
        elif loss_ratio >= 0.70 and current_tier < 2:
            new_tier = 2
            reason = f"Daily loss hit 70% of limit ({loss_ratio*100:.1f}%)"
            tokens = []
        elif loss_ratio >= 0.40 and current_tier < 1:
            new_tier = 1
            reason = f"Daily loss hit 40% of limit ({loss_ratio*100:.1f}%)"
            if trigger_token and trigger_token not in tokens:
                tokens.append(trigger_token)
        
        if new_tier > current_tier:
            await self.db.set_kill_switch(user_id, new_tier, reason, "system", affected_tokens=tokens)
            # Emit liquidation command if Tier 3
            if new_tier == 3:
                await self._trigger_liquidation(user_id)

    async def _trigger_liquidation(self, user_id: str):
        """Trigger Agent-8 emergency liquidation hook using Priority Limit orders."""
        logger.error(f"🔴🔴🔴 [EMERGENCY] Agent-7 triggered FULL LIQUIDATION for user {user_id}. 🔴🔴🔴")
        if hasattr(self, 'trading_bot') and self.trading_bot:
            try:
                # Priority Limit liquidation balances speed and execution quality
                res = await self.trading_bot.liquidate_all_positions(user_id, execution_type="priority_limit")
                logger.warning(f"🔴🔴🔴 [LIQUIDATION COMPLETE] {res.get('liquidated', 0)} positions closed via PRIORITY_LIMIT. Total PnL: ${res.get('total_pnl_usd', 0):.2f}")
            except Exception as e:
                logger.error(f"❌ [CRITICAL] Liquidation call to Agent-8 failed: {e}")
        else:
            logger.error("❌ [CRITICAL] trading_bot instance not found in Agent-7. Cannot liquidate!")

    async def log_to_database(self, result: Dict):
        """Persist risk analysis to DB."""
        if not self.db:
            return
        try:
            await self.db.log_agent_7_analysis(result)
        except Exception as e:
            logger.error(f"[AGENT_7] DB log error: {e}")


if __name__ == "__main__":
    import asyncio
    logging.basicConfig(level=logging.INFO)

    async def test():
        # Test on multiple account sizes
        for capital in [10.0, 100.0, 1000.0, 10000.0]:
            rm = Agent7RiskManager(starting_capital=capital)
            mock_5 = {"token_address": "Addr", "token_symbol": "TEST", "composite_score": 8.7}
            mock_6 = {"market_regime": "mixed"}
            approved, instr, reason = await rm.validate_and_size(mock_5, mock_6, entry_price=0.000042)
            if approved:
                print(
                    f"Capital=${capital:.0f} → "
                    f"Position=${instr.position_size_usd:.4f} "
                    f"({instr.position_size_usd/capital:.1%}) | "
                    f"SL=${instr.stop_loss_price:.8f} | "
                    f"TP1=${instr.take_profit_1_price:.8f} | "
                    f"TP2=${instr.take_profit_2_price:.8f}"
                )
            else:
                print(f"Capital=${capital:.0f} → Blocked: {reason}")
    
    asyncio.run(test())
