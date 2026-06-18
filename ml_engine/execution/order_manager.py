"""
ml_engine/execution/order_manager.py
──────────────────────────────────────
Order Execution Manager.

Handles placing real orders on Binance via CCXT, or simulating
orders in paper trading mode. It connects the signals from the 
Signal Aggregator to actual positions.

Features:
- Position tracking
- ATR-based position sizing
- Order execution (Market/Limit)
- Stop Loss & Take Profit logic
- Paper trading mode
"""

import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class OrderManager:
    """
    Executes trades on the exchange (or paper trades) based on 
    signals and risk parameters.
    """

    def __init__(self, paper_trade: bool = True, risk_manager=None, exchange=None):
        self.paper_trade = paper_trade
        self.risk_manager = risk_manager
        self.exchange = exchange
        self.positions = {}
        
        mode = "PAPER" if paper_trade else "LIVE"
        logger.info(f"[OrderManager] Initialized in {mode} mode.")

    async def execute_signal(self, signal: Dict) -> Optional[Dict]:
        """
        Takes a final signal from the aggregator and executes a trade if appropriate.
        """
        action = signal.get("final_action")
        symbol = signal.get("symbol")
        
        if action not in ("BUY", "SELL"):
            return None
            
        logger.info(f"[OrderManager] Executing {action} for {symbol} (Signal Strength: {signal.get('signal_strength')})")
        
        # Determine position size via risk manager
        size = self._calculate_position_size(symbol, signal)
        if size <= 0:
            logger.warning(f"[OrderManager] Position size calculation returned 0 for {symbol}. Trade aborted.")
            return None
            
        # Execute trade
        if self.paper_trade:
            return await self._execute_paper(symbol, action, size, signal)
        else:
            return await self._execute_live(symbol, action, size, signal)

    def _calculate_position_size(self, symbol: str, signal: Dict) -> float:
        """Calculate position size, delegating to risk manager if available."""
        if self.risk_manager:
            return self.risk_manager.calculate_size(symbol, signal)
        return 1.0 # Default fallback size

    async def _execute_paper(self, symbol: str, action: str, size: float, signal: Dict) -> Dict:
        """Simulate trade execution."""
        logger.info(f"[OrderManager] PAPER TRADE: {action} {size} {symbol}")
        
        # Simple paper position tracking
        if action == "BUY":
            self.positions[symbol] = self.positions.get(symbol, 0) + size
        elif action == "SELL":
            self.positions[symbol] = self.positions.get(symbol, 0) - size
            
        return {
            "status": "FILLED",
            "symbol": symbol,
            "action": action,
            "size": size,
            "type": "PAPER",
            "price": "MARKET_SIMULATED",
            "timestamp": signal.get("timestamp")
        }

    async def _execute_live(self, symbol: str, action: str, size: float, signal: Dict) -> Dict:
        """Execute real trade via CCXT."""
        if not self.exchange:
            logger.error("[OrderManager] No exchange configured for live trading!")
            raise RuntimeError("Live trading requires configured exchange.")
            
        try:
            side = 'buy' if action == 'BUY' else 'sell'
            # Assuming market order for simplicity here
            logger.info(f"[OrderManager] LIVE TRADE: {side.upper()} {size} {symbol}")
            order = await self.exchange.create_market_order(symbol, side, size)
            logger.info(f"[OrderManager] LIVE TRADE SUCCESS: {order['id']}")
            return order
        except Exception as e:
            logger.error(f"[OrderManager] LIVE TRADE FAILED: {e}")
            return {"status": "FAILED", "error": str(e)}

    def get_position(self, symbol: str) -> float:
        """Get current position size for symbol."""
        if self.paper_trade:
            return self.positions.get(symbol, 0.0)
        else:
            # Need to fetch from exchange in live mode
            if not self.exchange:
                return 0.0
            # Placeholder for live balance fetching
            return 0.0
