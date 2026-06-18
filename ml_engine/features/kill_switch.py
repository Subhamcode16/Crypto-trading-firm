import logging
import numpy as np

logger = logging.getLogger(__name__)

class KillSwitch:
    
    def __init__(self):
        # ── Portfolio Concentration Caps ───────────────────────────
        self.max_simultaneous_positions = 2      # Never more than 2 open
        self.max_portfolio_exposure_pct = 0.20   # Never more than 20% deployed

        # ── Keep these — valid for any signal type ─────────────────
        self.l1_consecutive_losses    = 3
        self.l1_session_drawdown      = 0.02
        
        self.l2_consecutive_losses    = 5
        self.l2_daily_drawdown        = 0.05
        self.l2_api_failures          = 5
        
        self.l3_total_drawdown        = 0.10
        self.l3_single_trade_loss     = 0.03
        self.l3_equity_floor          = 500
        self.l3_operator_kill         = False
        self.l3_balance_mismatch      = False
        
        # ── Replace ATR triggers with breakout-specific metrics ─────
        self.l1_false_breakout_rate   = 0.65  # >65% false over last 10
        self.l1_avg_holding_bars      = 2     # reversing within 2 bars
        self.l2_false_breakout_rate   = 0.80  # >80% false over last 10
    
    def evaluate(self, portfolio: dict, 
                       signal: dict,
                       breakout_history: list) -> tuple[int, str]:
        
        # ── NEW: Portfolio concentration check ──────────────────────
        open_count   = portfolio.get('open_count', 0)
        exposure_pct = portfolio.get('deployed_capital', 0) / portfolio.get('current_capital', 1)
        
        if open_count >= self.max_simultaneous_positions:
            return 2, 'MAX_SIMULTANEOUS_POSITIONS'
        
        if exposure_pct >= self.max_portfolio_exposure_pct:
            return 2, 'MAX_PORTFOLIO_EXPOSURE'

        # ── L3: Hard kill — check first, always ────────────────────
        if portfolio.get('total_drawdown_from_start_pct', 0) >= self.l3_total_drawdown:
            return 3, 'L3_TOTAL_DRAWDOWN_10PCT'
        
        if portfolio.get('single_trade_loss_pct', 0) >= self.l3_single_trade_loss:
            return 3, 'L3_SINGLE_TRADE_LOSS'
        
        if portfolio.get('equity', float('inf')) <= self.l3_equity_floor:
            return 3, 'L3_EQUITY_FLOOR'
        
        if portfolio.get('operator_kill_command', False):
            return 3, 'L3_OPERATOR_KILL'
        
        if portfolio.get('exchange_balance_mismatch', False):
            return 3, 'L3_BALANCE_MISMATCH'
        
        # ── L2: Entry freeze ────────────────────────────────────────
        if portfolio.get('consecutive_losses', 0) >= self.l2_consecutive_losses:
            return 2, 'L2_CONSECUTIVE_LOSSES'
        
        if portfolio.get('daily_drawdown_pct', 0) >= self.l2_daily_drawdown:
            return 2, 'L2_DAILY_DRAWDOWN'
        
        # Breakout-specific L2
        if len(breakout_history) >= 10:
            recent_false_rate = self._false_breakout_rate(breakout_history[-10:])
            if recent_false_rate >= self.l2_false_breakout_rate:
                return 2, 'L2_BREAKOUT_SYSTEM_FAILING'
        
        # ── L1: Soft degradation ────────────────────────────────────
        if portfolio.get('consecutive_losses', 0) >= self.l1_consecutive_losses:
            return 1, 'L1_CONSECUTIVE_LOSSES'
        
        if portfolio.get('session_drawdown_pct', 0) >= self.l1_session_drawdown:
            return 1, 'L1_SESSION_DRAWDOWN'
        
        # Breakout-specific L1
        if len(breakout_history) >= 10:
            recent_false_rate = self._false_breakout_rate(breakout_history[-10:])
            avg_hold = self._avg_holding_bars(breakout_history[-10:])
            
            if recent_false_rate >= self.l1_false_breakout_rate:
                return 1, 'L1_HIGH_FALSE_BREAKOUT_RATE'
            
            if avg_hold <= self.l1_avg_holding_bars:
                return 1, 'L1_BREAKOUTS_REVERSING_FAST'
        
        return 0, 'CLEAR'
    
    def _false_breakout_rate(self, history: list) -> float:
        false_breakouts = sum(
            1 for t in history 
            if t.get('pnl', 0) < 0 and t.get('hours_held', 0) <= 3
        )
        return false_breakouts / len(history) if history else 0.0
    
    def _avg_holding_bars(self, history: list) -> float:
        return np.mean([t.get('hours_held', 0) for t in history]) if history else 0.0
