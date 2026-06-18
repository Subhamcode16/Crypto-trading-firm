"""
ml_engine/execution/risk_manager.py
─────────────────────────────────────
Risk Manager for ML Trading Engine

Handles:
- Daily loss limits
- Position sizing based on ATR / Volatility
- Multi-asset exposure limits
- Maximum risk per trade
"""

import logging
from typing import Dict

logger = logging.getLogger(__name__)

class RiskManager:
    """
    ML-Engine Risk Manager.
    Calculates position sizes and enforces portfolio risk rules.
    """

    def __init__(self, 
                 initial_capital: float = 1000.0,
                 max_risk_per_trade_pct: float = 0.02, # 2% risk
                 max_position_size_pct: float = 0.25,  # 25% max capital per trade
                 daily_loss_limit_pct: float = 0.05):  # 5% daily loss limit
        
        self.initial_capital = initial_capital
        self.current_capital = initial_capital
        
        self.max_risk_pct = max_risk_per_trade_pct
        self.max_position_pct = max_position_size_pct
        self.daily_loss_limit_pct = daily_loss_limit_pct
        
        self.daily_pnl = 0.0
        logger.info(f"[RiskManager] Initialized: Capital=${initial_capital:.2f}, Max Risk/Trade={max_risk_per_trade_pct*100}%, Max Pos={max_position_size_pct*100}%")

    def update_capital(self, pnl: float):
        """Update capital after a trade closes."""
        self.current_capital += pnl
        self.daily_pnl += pnl

    def reset_daily_pnl(self):
        """Reset daily PnL counter."""
        self.daily_pnl = 0.0

    def calculate_size(self, symbol: str, signal: Dict) -> float:
        """
        Calculate position size based on ATR (Volatility) and Signal Strength.
        
        Args:
            symbol: Trading pair (e.g. BTC/USDT)
            signal: Dict containing 'final_action', 'signal_strength', 'atr', 'close_price'
        
        Returns:
            Position size in base asset units (e.g., amount of BTC)
        """
        if self.daily_pnl <= -(self.initial_capital * self.daily_loss_limit_pct):
            logger.warning(f"[RiskManager] Daily loss limit reached. No sizing allowed.")
            return 0.0

        close_price = signal.get("close_price")
        if not close_price or close_price <= 0:
            logger.warning(f"[RiskManager] Invalid close price for {symbol}: {close_price}")
            return 0.0

        # ATR-based stop loss calculation
        atr = signal.get("atr")
        if atr and atr > 0:
            # e.g., 2 ATR for stop loss
            stop_loss_distance = 2 * atr
            stop_loss_pct = stop_loss_distance / close_price
        else:
            # Fallback to fixed 3% stop loss if ATR missing
            stop_loss_pct = 0.03

        # How much capital we are willing to risk
        risk_amount_usd = self.current_capital * self.max_risk_pct
        
        # Position size in USD based on risk and stop loss distance
        # If we lose stop_loss_pct, we lose risk_amount_usd.
        # Position Size (USD) = Risk Amount (USD) / Stop Loss Pct
        target_size_usd = risk_amount_usd / stop_loss_pct

        # Apply max position size cap
        max_size_usd = self.current_capital * self.max_position_pct
        size_usd = min(target_size_usd, max_size_usd)

        # Scale by ML signal strength (0.5 to 1.0 confidence range usually)
        strength = signal.get("signal_strength", 1.0)
        size_usd = size_usd * strength

        # Convert to base asset amount
        size_base = size_usd / close_price
        
        logger.info(f"[RiskManager] Size {symbol}: ${size_usd:.2f} ({size_base:.6f} units) | StopPct: {stop_loss_pct*100:.2f}% | Strength: {strength:.2f}")
        return size_base
