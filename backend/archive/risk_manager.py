"""
Enhanced Risk Manager - Integrated with skill-learned patterns and 3-Tier Kill Switch
"""

import logging
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger('risk_manager')

class MarketRegime(Enum):
    """Market conditions affect optimal trade frequency"""
    BULLISH = "bullish"      
    MIXED = "mixed"          
    CHOPPY = "choppy"        
    FLAT = "flat"            

@dataclass
class TradeValidation:
    """Result of pre-entry risk validation"""
    passed: bool
    risk_per_trade: float
    reward_ratio: float
    equity_risk_percent: float
    reasons: list
    
    def summary(self) -> str:
        status = "✅ PASS" if self.passed else "❌ FAIL"
        return f"{status} | Risk: {self.risk_per_trade:.4f} | R:R: {self.reward_ratio:.1f}:1 | Equity Risk: {self.equity_risk_percent:.2f}%"

class RiskManager:
    """
    Agent-7: Risk Manager & Kill Switch Enforcer
    """
    
    def __init__(self, db, starting_capital: float = 10.0):
        self.db = db
        self.starting_capital = starting_capital
        self.current_capital = starting_capital
        self.daily_loss_limit = 3.0  # Default 30% of capital
        self.daily_pnl = 0.0
        self.trades_today = 0
        self.last_reset = datetime.utcnow()
        
        # Risk limits
        self.max_risk_per_trade_percent = 2.0  
        self.max_position_size_percent = 25.0  
        self.max_simultaneous_exposure = 30.0  
        self.min_reward_ratio = 2.0  
        
        logger.info('💰 Agent-7: Risk Manager initialized')
    
    async def _get_portfolio_state(self, user_id: str):
        """Fetches live portfolio state from database."""
        today = datetime.utcnow().strftime("%Y-%m-%d")
        state = await self.db.get_daily_portfolio_state(user_id, today)
        self.daily_pnl = -state.get("realized_loss_usd", 0.0)  # DB stores loss as positive
        self.daily_loss_limit = state.get("daily_loss_limit_usd", 3.0)

    async def evaluate_signal(self, signal: dict, user_id: str = "default_user") -> dict:
        """
        Enforces the 3-Tier Kill Switch strictly before any sizing logic.
        """
        await self._get_portfolio_state(user_id)
        
        # First, evaluate if a tier upgrade is needed based on current daily PnL
        await self.evaluate_tier_triggers(user_id, signal.get("token_symbol", ""))
        
        # Read the current enforced tier from DB
        ks_state = await self.db.get_kill_switch(user_id)
        tier = ks_state.get("tier", 0)
        active_since = ks_state.get("active_since")
        affected_tokens = ks_state.get("affected_tokens", [])
        
        # Auto-recovery checks
        if tier == 1 and active_since:
            activation_time = datetime.fromisoformat(active_since)
            if datetime.utcnow() > activation_time + timedelta(hours=2):
                logger.info(f"[Agent-7] Tier 1 auto-recovery 2h cooldown expired for {user_id}.")
                await self.db.clear_kill_switch(user_id, "system_auto_recovery")
                tier = 0

        # Tier Enforcements
        if tier == 3:
            signal['status'] = "rejected_killswitch_tier_3"
            signal['reason'] = "Blocked by Agent-7: Tier 3 Full Stop Active. Manual resume required."
            logger.warning(f"[Agent-7] Rejected {signal.get('token_symbol')}: Tier 3 Active.")
            return signal
            
        if tier == 2:
            signal['status'] = "rejected_killswitch_tier_2"
            signal['reason'] = "Blocked by Agent-7: Tier 2 Defense Active. Portfolio-wide block."
            logger.warning(f"[Agent-7] Rejected {signal.get('token_symbol')}: Tier 2 Active.")
            return signal
            
        if tier == 1:
            if signal.get("token_symbol") in affected_tokens:
                signal['status'] = "rejected_killswitch_tier_1"
                signal['reason'] = f"Blocked by Agent-7: Tier 1 Caution Active for {signal.get('token_symbol')}."
                logger.warning(f"[Agent-7] Rejected {signal.get('token_symbol')}: Tier 1 Token Block.")
                return signal
            else:
                # Apply 0.70x global sizing multiplier for new entries
                original_size = signal.get("position_size_usd", 0)
                signal["position_size_usd"] = original_size * 0.70
                signal["reason"] = signal.get("reason", "") + " [Tier 1 Sizing (0.70x)]"

        return signal

    async def evaluate_tier_triggers(self, user_id: str, trigger_token: str = ""):
        """
        Calculates losses and upgrades Kill Switch tiers if thresholds are breached.
        """
        loss = -self.daily_pnl  # Convert to positive loss
        loss_ratio = loss / self.daily_loss_limit if self.daily_loss_limit > 0 else 0
        
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
        """Mock function for triggering Agent-8 liquidation."""
        logger.error(f"🔴🔴🔴 [EMERGENCY] Agent-7 triggered FULL LIQUIDATION for user {user_id}. 🔴🔴🔴")
        # In actual implementation, signal Agent-8 to close all positions.

    def validate_trade(self, 
                       entry_price: float,
                       stop_loss_price: float,
                       take_profit_price: float,
                       position_size_usd: float,
                       market_regime: MarketRegime = MarketRegime.BULLISH) -> TradeValidation:
        """
        Validate trade before entry using risk-management skill rules
        """
        reasons = []
        
        # Check 1: Daily trade frequency
        if not self._check_trade_frequency(market_regime):
            reasons.append(f'Too many trades today ({self.trades_today}) for {market_regime.value} market')
        
        # Check 2: Calculate risk metrics
        risk_per_trade = abs(entry_price - stop_loss_price)
        reward = abs(take_profit_price - entry_price)
        reward_ratio = reward / risk_per_trade if risk_per_trade > 0 else 0
        
        # Check 3: Risk per trade as % of equity
        equity_risk = (risk_per_trade * position_size_usd / entry_price) if entry_price > 0 else 0
        equity_risk_percent = (equity_risk / self.current_capital) * 100
        
        # Check 4: Position size vs capital
        position_percent = (position_size_usd / self.current_capital) * 100
        
        # Check 5: Daily loss limit
        projected_loss_on_sl = -equity_risk
        remaining_daily_loss = self.daily_loss_limit - abs(self.daily_pnl)
        
        passed = True
        
        if equity_risk_percent > self.max_risk_per_trade_percent:
            passed = False
            reasons.append(f'❌ Equity risk {equity_risk_percent:.2f}% > {self.max_risk_per_trade_percent}% limit')
        else:
            reasons.append(f'✅ Equity risk {equity_risk_percent:.2f}% ≤ {self.max_risk_per_trade_percent}%')
        
        if position_percent > self.max_position_size_percent:
            passed = False
            reasons.append(f'❌ Position {position_percent:.2f}% > {self.max_position_size_percent}% max')
        else:
            reasons.append(f'✅ Position {position_percent:.2f}% ≤ {self.max_position_size_percent}%')
        
        if reward_ratio < self.min_reward_ratio:
            passed = False
            reasons.append(f'❌ Reward ratio {reward_ratio:.2f}:1 < {self.min_reward_ratio}:1 minimum')
        else:
            reasons.append(f'✅ Reward ratio {reward_ratio:.2f}:1 ≥ {self.min_reward_ratio}:1')
        
        if projected_loss_on_sl > remaining_daily_loss:
            passed = False
            reasons.append(f'❌ Loss ${projected_loss_on_sl:.2f} would exceed daily limit ${self.daily_loss_limit:.2f}')
        else:
            reasons.append(f'✅ Within daily loss limit (${remaining_daily_loss:.2f} remaining)')
        
        return TradeValidation(
            passed=passed,
            risk_per_trade=risk_per_trade,
            reward_ratio=reward_ratio,
            equity_risk_percent=equity_risk_percent,
            reasons=reasons
        )
    
    def _check_trade_frequency(self, market_regime: MarketRegime) -> bool:
        max_trades = {
            MarketRegime.BULLISH: 30,
            MarketRegime.MIXED: 10,
            MarketRegime.CHOPPY: 5,
            MarketRegime.FLAT: 3
        }
        limit = max_trades[market_regime]
        if self.trades_today >= limit:
            return False
        return True
    
    async def record_trade_execution(self, position_size_usd: float, pnl: float = 0.0, user_id: str = "default_user"):
        """Record a trade execution and update DB stats"""
        self.trades_today += 1
        self.daily_pnl += pnl
        self.current_capital += pnl
        
        loss_usd = max(0.0, -self.daily_pnl)
        today = datetime.utcnow().strftime("%Y-%m-%d")
        await self.db.update_daily_portfolio_state(user_id, today, realized_loss_usd=loss_usd)
        
        logger.info(f'📊 Trade recorded: #{self.trades_today} | PnL: ${pnl:+.2f} | Daily PnL: ${self.daily_pnl:+.2f}')
        
        # Check tier upgrades after a trade closes
        if pnl < 0:
            await self.evaluate_tier_triggers(user_id)
    
    async def reset_daily(self, user_id: str = "default_user"):
        """Reset daily counters (called at midnight UTC)"""
        self.trades_today = 0
        self.daily_pnl = 0.0
        self.last_reset = datetime.utcnow()
        
        today = datetime.utcnow().strftime("%Y-%m-%d")
        await self.db.update_daily_portfolio_state(user_id, today, realized_loss_usd=0.0)
        
        # Auto-recover Tier 2 at midnight
        ks_state = await self.db.get_kill_switch(user_id)
        if ks_state.get("tier") == 2:
            await self.db.clear_kill_switch(user_id, "system_midnight_reset")
            logger.info(f'🔄 Daily reset: Auto-recovered Tier 2 Kill Switch for {user_id}.')
        
        logger.info('🔄 Daily reset: Counters cleared for new trading day')

    def get_status(self) -> dict:
        return {
            'capital': self.current_capital,
            'daily_pnl': self.daily_pnl,
            'daily_loss_used': abs(self.daily_pnl) / self.daily_loss_limit if self.daily_loss_limit > 0 else 0,
            'trades_today': self.trades_today,
            'max_position_percent': self.max_position_size_percent,
            'max_risk_per_trade_percent': self.max_risk_per_trade_percent,
            'min_reward_ratio': self.min_reward_ratio
        }
