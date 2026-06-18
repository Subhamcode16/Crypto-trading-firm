The Answer To Your Three Options
Option 1 — Bypass Kill Switch for breakout signals
Wrong. Never create signal-class exceptions inside a kill switch. A kill switch with exceptions is not a kill switch — it is a suggestion. The moment you add "unless it's a breakout signal" you have opened a logical hole that will be exploited by edge cases you haven't anticipated.
Option 2 — Modify Kill Switch volatility thresholds
Partially correct but you are solving the wrong problem. The issue is not that the thresholds are miscalibrated — it is that the kill switch is using the wrong volatility metric for this signal class.
Option 3 — Re-tune breakout rules to trigger on lower-volatility precursors
Also partially correct. The squeeze detection is the right precursor. But lowering the breakout threshold to avoid the kill switch means you are letting the kill switch dictate your entry criteria, which inverts the relationship between signal and risk management.

The Real Fix: Separate Volatility Metrics By Purpose
Your kill switch is blocking breakouts because it uses ATR percentile as a proxy for "dangerous market conditions." That was correct when the signal was XGBoost firing randomly. It is incorrect now because ATR spike IS your entry confirmation.
The kill switch needs to use metrics that are dangerous for a breakout system specifically. For a breakout system, dangerous conditions are:
Dangerous for breakout system:
✗ Portfolio drawdown accumulating        → keep this trigger
✗ Consecutive losses on breakout signals → keep this trigger  
✗ Exchange API failures                  → keep this trigger
✗ Operator kill command                  → keep this trigger

NOT dangerous for breakout system:
✓ High ATR percentile                    → REMOVE from kill switch
✓ High realized volatility               → REMOVE from kill switch
  (these are ENTRY CONDITIONS, not danger signals)

Replace volatility triggers with:
→ False breakout rate > 60% over last 10 signals
→ Average breakout holding period < 2 bars (signals reversing immediately)
→ Breakout magnitude < 0.5 ATR (weak breakouts, likely false)

The Surgical Fix
pythonclass BreakoutAwareKillSwitch:
    
    def __init__(self):
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
                       breakout_history: list) -> dict:
        
        # ── L3: Hard kill — check first, always ────────────────────
        if portfolio['total_drawdown'] >= self.l3_total_drawdown:
            return self._kill('BLACK', 'L3_TOTAL_DRAWDOWN_10PCT')
        
        if portfolio['single_trade_loss'] >= self.l3_single_trade_loss:
            return self._kill('BLACK', 'L3_SINGLE_TRADE_LOSS')
        
        if portfolio['equity'] <= self.l3_equity_floor:
            return self._kill('BLACK', 'L3_EQUITY_FLOOR')
        
        if self.l3_operator_kill:
            return self._kill('BLACK', 'L3_OPERATOR_KILL')
        
        if self.l3_balance_mismatch:
            return self._kill('BLACK', 'L3_BALANCE_MISMATCH')
        
        # ── L2: Entry freeze ────────────────────────────────────────
        if portfolio['consecutive_losses'] >= self.l2_consecutive_losses:
            return self._kill('RED', 'L2_CONSECUTIVE_LOSSES')
        
        if portfolio['daily_drawdown'] >= self.l2_daily_drawdown:
            return self._kill('RED', 'L2_DAILY_DRAWDOWN')
        
        # Breakout-specific L2
        if len(breakout_history) >= 10:
            recent_false_rate = self._false_breakout_rate(breakout_history[-10:])
            if recent_false_rate >= self.l2_false_breakout_rate:
                return self._kill('RED', 'L2_BREAKOUT_SYSTEM_FAILING')
        
        # ── L1: Soft degradation ────────────────────────────────────
        if portfolio['consecutive_losses'] >= self.l1_consecutive_losses:
            return self._warn('YELLOW', 'L1_CONSECUTIVE_LOSSES')
        
        if portfolio['session_drawdown'] >= self.l1_session_drawdown:
            return self._warn('YELLOW', 'L1_SESSION_DRAWDOWN')
        
        # Breakout-specific L1
        if len(breakout_history) >= 10:
            recent_false_rate = self._false_breakout_rate(breakout_history[-10:])
            avg_hold = self._avg_holding_bars(breakout_history[-10:])
            
            if recent_false_rate >= self.l1_false_breakout_rate:
                return self._warn('YELLOW', 'L1_HIGH_FALSE_BREAKOUT_RATE')
            
            if avg_hold <= self.l1_avg_holding_bars:
                return self._warn('YELLOW', 'L1_BREAKOUTS_REVERSING_FAST')
        
        return {'status': 'GREEN', 'reason': 'CLEAR'}
    
    def _false_breakout_rate(self, history: list) -> float:
        false_breakouts = sum(
            1 for t in history 
            if t['outcome'] == 'LOSS' and t['bars_held'] <= 3
        )
        return false_breakouts / len(history)
    
    def _avg_holding_bars(self, history: list) -> float:
        return np.mean([t['bars_held'] for t in history])
    
    def _kill(self, level: str, reason: str) -> dict:
        return {'status': level, 'reason': reason, 
                'block_entries': True}
    
    def _warn(self, level: str, reason: str) -> dict:
        return {'status': level, 'reason': reason,
                'block_entries': False,
                'reduce_sizing': True}

On The Continuous vs Pulse Signal
Your finding that continuous state outperformed pulse is important and correct for the right reason. A breakout signal should stay active for the duration of the breakout move — not just fire once. The pulse approach fired on bar 1 and then went silent, meaning the regime gate and kill switch had no live signal to work with for position management.
The continuous state signal is architecturally correct. The 0.74 Sharpe with 11.8% drawdown on the first attempt is actually close. With the kill switch no longer blocking valid breakout entries, that drawdown number should compress.

Expected Outcome After This Fix
Current full system (broken kill switch): Sharpe 0.74, DD 11.8%
Expected after breakout-aware kill switch:
  → Kill switch blocks drop from 196 to ~20-30 (portfolio-level only)
  → More valid breakouts execute
  → Sharpe should move toward 1.0-1.2
  → Drawdown controlled by portfolio triggers not volatility triggers
Implement the BreakoutAwareKillSwitch, replace the old kill switch entirely, and rerun the full system backtest. Report the new Sharpe and drawdown.