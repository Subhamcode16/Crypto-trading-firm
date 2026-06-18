# RISK MANAGER SPECIFICATION - HARD RULES

**Objective:** Implement the Risk Manager layer that enforces hard constraints and kill switch logic.

**Status:** Ready for Phase 4 integration  
**Scope:** Kill switch tiers, position sizing validation, daily loss tracking, portfolio exposure limits  
**Output:** Unbreakable risk constraints that override all other systems

---

## 1. RISK MANAGER OVERVIEW

### Core Philosophy
**Risk Manager > Researcher > Trading Bot**

The Risk Manager sits above both other systems and can override them without exception.

```
Signal arrives
    ↓
Risk Manager checks:
  ├─ Daily loss limit hit?
  ├─ Portfolio exposure exceeds 30%?
  ├─ Position size within hard caps?
  └─ Kill switch active?
    ↓
  If ALL checks pass → Forward to Trading Bot
  If ANY check fails → REJECT, do not trade
```

### Three Kill Switch Tiers

| Tier | Trigger | Action | Recovery |
|------|---------|--------|----------|
| **Soft Pause (Tier 1)** | Daily loss = $3 | Stop new trades, existing positions close naturally | Auto-resume at UTC midnight |
| **Hard Stop (Tier 2)** | Total capital < $5 | Close all positions, halt everything | Manual review + restart required |
| **Emergency Kill (Tier 3)** | Technical anomaly | Close all, halt, send urgent alert | Manual investigation + restart required |

---

## 2. POSITION SIZING & VALIDATION

### Hard Caps (Non-Negotiable)

```python
class PositionSizingRules:
    
    STARTING_CAPITAL = 10.0  # USD
    
    # Per-trade position sizes (deterministic)
    POSITION_SIZE_HIGH_CONFIDENCE = 2.0   # Confidence 8-10: $2 (20% of capital)
    POSITION_SIZE_MID_CONFIDENCE = 1.0    # Confidence 6-7: $1 (10% of capital)
    
    # Hard caps
    MAX_POSITION_SIZE = 2.0              # No single trade > $2
    MAX_PORTFOLIO_EXPOSURE = 0.30        # Open positions < 30% of capital
    MAX_POSITIONS_OPEN = 3               # Never more than 3 concurrent trades
    
    # Position sizing formula (for Phase 4+ with variable capital)
    def calculate_position_size(self, confidence: int, current_capital: float):
        """
        Deterministic position sizing based on confidence
        """
        if confidence >= 8:
            return min(2.0, current_capital * 0.20)  # $2 or 20% of capital
        elif confidence >= 6:
            return min(1.0, current_capital * 0.10)  # $1 or 10% of capital
        else:
            return 0.0  # Dropped signal, no position

class PositionValidator:
    """Validate that positions obey hard rules"""
    
    def validate_position_size(self, position_size: float) -> bool:
        """Verify position doesn't exceed hard cap"""
        if position_size > PositionSizingRules.MAX_POSITION_SIZE:
            return False, f'Position ${position_size} exceeds max ${PositionSizingRules.MAX_POSITION_SIZE}'
        return True, f'Position size OK: ${position_size}'
    
    def validate_portfolio_exposure(self, open_positions: list, position_to_add: float) -> bool:
        """Verify adding this position won't exceed 30% portfolio exposure"""
        
        current_capital = PositionSizingRules.STARTING_CAPITAL
        current_exposure = sum(p['position_size'] for p in open_positions)
        
        new_exposure = current_exposure + position_to_add
        exposure_percent = (new_exposure / current_capital) * 100
        
        if exposure_percent > 30:
            return False, f'Portfolio exposure {exposure_percent:.1f}% would exceed 30% max'
        
        return True, f'Portfolio exposure OK: {exposure_percent:.1f}%'
    
    def validate_position_count(self, open_positions: list) -> bool:
        """Never allow more than 3 concurrent positions"""
        if len(open_positions) >= PositionSizingRules.MAX_POSITIONS_OPEN:
            return False, f'{len(open_positions)} positions already open (max 3)'
        return True, f'Position count OK: {len(open_positions)}/3'
```

---

## 3. DAILY LOSS LIMIT & SOFT PAUSE (TIER 1)

### Daily Loss Tracking

```python
class DailyLossTracker:
    
    DAILY_LOSS_LIMIT = 3.0  # USD (30% of $10 capital)
    SOFT_PAUSE_THRESHOLD = 3.0  # Same as daily loss limit
    
    def __init__(self, db):
        self.db = db
        self.current_date = None
        self.daily_pnl = 0.0
    
    def reset_daily(self):
        """Called at UTC midnight - reset daily counter"""
        self.current_date = datetime.utcnow().date()
        self.daily_pnl = 0.0
        logger.info('Daily loss counter reset')
    
    def add_trade_pnl(self, trade_pnl: float):
        """Add a trade's P&L to daily total"""
        self.daily_pnl += trade_pnl
        
        # Log this trade
        logger.info(f'Trade P&L: {trade_pnl:+.2f} | Daily total: {self.daily_pnl:+.2f}')
        
        # Check if we hit the limit
        if self.daily_pnl <= -self.DAILY_LOSS_LIMIT:
            return 'SOFT_PAUSE_TRIGGERED'
        
        return None  # OK, continue trading
    
    def get_daily_status(self) -> dict:
        """Return current daily loss status"""
        return {
            'date': self.current_date.isoformat(),
            'daily_pnl': self.daily_pnl,
            'daily_loss_limit': -self.DAILY_LOSS_LIMIT,
            'percent_of_limit': abs(self.daily_pnl / self.DAILY_LOSS_LIMIT * 100),
            'status': 'OK' if self.daily_pnl > -self.DAILY_LOSS_LIMIT else 'SOFT_PAUSE'
        }
```

### Soft Pause Behavior

```python
class SoftPauseManager:
    """Manage Soft Pause (Tier 1) state and transitions"""
    
    def __init__(self, telegram_bot, db):
        self.telegram = telegram_bot
        self.db = db
        self.soft_pause_active = False
    
    def trigger_soft_pause(self):
        """Activate Soft Pause when daily loss = $3"""
        self.soft_pause_active = True
        logger.warning('SOFT PAUSE TRIGGERED - Daily loss limit hit')
        
        message = """
⚠️ SOFT PAUSE ACTIVATED

Daily loss limit reached: $3.00
No new trades will be executed.
Existing open positions will close on their own.

Resume: Automatic at UTC midnight
        """
        self.telegram.send_alert(message)
        
        # Log event
        self.db.log_event({
            'event_type': 'soft_pause_triggered',
            'severity': 'warning',
            'description': 'Daily loss limit ($3) reached',
            'timestamp': datetime.utcnow().isoformat()
        })
    
    def check_soft_pause(self) -> bool:
        """Check if Soft Pause is active"""
        return self.soft_pause_active
    
    def can_execute_trade(self) -> bool:
        """Return whether new trades should execute"""
        if self.soft_pause_active:
            logger.info('Trade rejected: Soft Pause active')
            return False
        return True
    
    def resolve_soft_pause(self):
        """Called at UTC midnight - lift Soft Pause"""
        self.soft_pause_active = False
        logger.info('SOFT PAUSE RESOLVED - Daily reset at midnight')
        
        self.telegram.send_alert('✅ SOFT PAUSE LIFTED - Daily reset, trading resumed')
```

---

## 4. HARD STOP (TIER 2)

### Total Capital Monitoring

```python
class CapitalMonitor:
    
    STARTING_CAPITAL = 10.0
    HARD_STOP_THRESHOLD = 5.0  # 50% drawdown ($5 remaining)
    
    def __init__(self, db):
        self.db = db
        self.current_capital = self.STARTING_CAPITAL
    
    def update_capital(self, pnl: float):
        """Update capital after each trade closes"""
        self.current_capital += pnl
        
        # Check hard stop condition
        if self.current_capital < self.HARD_STOP_THRESHOLD:
            return 'HARD_STOP_TRIGGERED'
        
        return None
    
    def get_capital_status(self) -> dict:
        """Return capital health status"""
        drawdown = self.STARTING_CAPITAL - self.current_capital
        drawdown_percent = (drawdown / self.STARTING_CAPITAL) * 100
        
        return {
            'starting_capital': self.STARTING_CAPITAL,
            'current_capital': self.current_capital,
            'total_pnl': self.current_capital - self.STARTING_CAPITAL,
            'drawdown': drawdown,
            'drawdown_percent': drawdown_percent,
            'status': 'OK' if self.current_capital >= self.HARD_STOP_THRESHOLD else 'HARD_STOP'
        }
```

### Hard Stop Execution

```python
class HardStopManager:
    """Execute Hard Stop when capital < $5"""
    
    def __init__(self, telegram_bot, db, trading_bot):
        self.telegram = telegram_bot
        self.db = db
        self.trading_bot = trading_bot  # To close positions
        self.hard_stop_active = False
    
    def trigger_hard_stop(self, current_capital: float):
        """Activate Hard Stop when capital drops below $5"""
        self.hard_stop_active = True
        logger.critical(f'HARD STOP TRIGGERED - Capital: ${current_capital:.2f}')
        
        # Immediately close all open positions
        open_positions = self.trading_bot.get_open_positions()
        
        for position in open_positions:
            self.trading_bot.close_position_market(position['position_id'])
        
        message = f"""
🛑 HARD STOP ACTIVATED

Capital dropped to ${current_capital:.2f} (50% drawdown from ${10.0})
All open positions closed at market price.
System halted completely.

MANUAL INTERVENTION REQUIRED:
1. Review what went wrong
2. Adjust parameters if needed
3. Add capital or reset
4. Manually restart the system

DO NOT restart automatically.
        """
        self.telegram.send_urgent_alert(message)
        
        # Log event with full diagnostics
        self.db.log_event({
            'event_type': 'hard_stop_triggered',
            'severity': 'critical',
            'description': f'Capital ${current_capital:.2f} < Hard Stop threshold',
            'diagnostic_data': {
                'current_capital': current_capital,
                'positions_closed': len(open_positions),
                'timestamp': datetime.utcnow().isoformat()
            }
        })
    
    def is_hard_stop_active(self) -> bool:
        """Check if Hard Stop is active"""
        return self.hard_stop_active
    
    def cannot_trade_hard_stop(self) -> bool:
        """Return whether trading is blocked"""
        return self.hard_stop_active
```

---

## 5. EMERGENCY KILL (TIER 3)

### Anomaly Detection

```python
class AnomalyDetector:
    """Detect technical anomalies that trigger Emergency Kill"""
    
    MAX_CONSECUTIVE_FAILURES = 3
    MAX_EXECUTION_SLIPPAGE = 0.50  # 50%
    
    def __init__(self):
        self.consecutive_failures = 0
    
    def check_transaction_failure(self, error: Exception):
        """Track consecutive transaction failures"""
        self.consecutive_failures += 1
        logger.error(f'Transaction failed ({self.consecutive_failures}/3): {error}')
        
        if self.consecutive_failures >= self.MAX_CONSECUTIVE_FAILURES:
            return 'EMERGENCY_KILL', f'{self.MAX_CONSECUTIVE_FAILURES} consecutive failures'
        
        return None, None
    
    def reset_failure_counter(self):
        """Reset after successful transaction"""
        self.consecutive_failures = 0
    
    def check_api_data_corruption(self, api_response: dict) -> bool:
        """Verify API response is valid and complete"""
        required_fields = ['price', 'liquidity', 'holders']
        
        for field in required_fields:
            if field not in api_response or api_response[field] is None:
                logger.error(f'API data corruption: missing {field}')
                return 'EMERGENCY_KILL', f'Corrupted API response: missing {field}'
        
        return None, None
    
    def check_position_size_violation(self, position_size: float, max_size: float) -> tuple:
        """Verify position size never exceeds hard cap"""
        if position_size > max_size:
            logger.critical(f'ANOMALY: Position size {position_size} > max {max_size}')
            return 'EMERGENCY_KILL', f'Position size violation: {position_size} > {max_size}'
        
        return None, None
    
    def check_execution_mismatch(self, signal: dict, execution: dict) -> tuple:
        """Verify trade execution matches signal parameters"""
        
        # Check entry price (allow 5% slippage)
        signal_price = signal['entry']['price']
        execution_price = execution['entry_price']
        slippage = abs(execution_price - signal_price) / signal_price
        
        if slippage > 0.05:
            return 'EMERGENCY_KILL', f'Entry slippage {slippage*100:.1f}% > 5% max'
        
        # Check position size matches exactly
        if execution['position_size'] != signal['entry']['position_size_usd']:
            return 'EMERGENCY_KILL', f'Position size mismatch: signal vs execution'
        
        return None, None
    
    def check_slippage_extreme(self, signal_price: float, execution_price: float) -> tuple:
        """Extreme slippage (>50%) indicates manipulation or liquidity issue"""
        slippage = abs(execution_price - signal_price) / signal_price
        
        if slippage > self.MAX_EXECUTION_SLIPPAGE:
            return 'EMERGENCY_KILL', f'Extreme slippage {slippage*100:.1f}% > 50% max'
        
        return None, None
```

### Emergency Kill Execution

```python
class EmergencyKillManager:
    """Execute Emergency Kill on technical anomalies"""
    
    def __init__(self, telegram_bot, db, trading_bot):
        self.telegram = telegram_bot
        self.db = db
        self.trading_bot = trading_bot
        self.emergency_kill_active = False
    
    def trigger_emergency_kill(self, anomaly_type: str, diagnostic_data: dict):
        """Activate Emergency Kill"""
        self.emergency_kill_active = True
        logger.critical(f'EMERGENCY KILL TRIGGERED: {anomaly_type}')
        
        # Close all positions immediately
        open_positions = self.trading_bot.get_open_positions()
        for position in open_positions:
            self.trading_bot.close_position_market(position['position_id'])
        
        # Generate diagnostic report
        diagnostic_report = {
            'anomaly_type': anomaly_type,
            'timestamp': datetime.utcnow().isoformat(),
            'open_positions_closed': len(open_positions),
            'data': diagnostic_data
        }
        
        # Alert user urgently
        message = f"""
🔴 EMERGENCY KILL ACTIVATED

Anomaly Detected: {anomaly_type}

Details:
{json.dumps(diagnostic_data, indent=2)}

All open positions closed at market.
System halted completely.

IMMEDIATE ACTION REQUIRED:
1. Investigate the error above
2. Review system logs
3. Fix the issue in code
4. Deploy fix
5. Manually restart

DO NOT auto-restart. This is a critical system error.
        """
        self.telegram.send_urgent_alert(message)
        
        # Log with full diagnostics for investigation
        self.db.log_event({
            'event_type': 'emergency_kill_triggered',
            'severity': 'critical',
            'description': f'Technical anomaly: {anomaly_type}',
            'diagnostic_data': json.dumps(diagnostic_report)
        })
    
    def is_emergency_kill_active(self) -> bool:
        return self.emergency_kill_active
```

---

## 6. MASTER RISK MANAGER CLASS

```python
class RiskManager:
    """Master risk enforcement layer - sits above all other systems"""
    
    def __init__(self, config, db, telegram, trading_bot):
        self.config = config
        self.db = db
        self.telegram = telegram
        self.trading_bot = trading_bot
        
        # Initialize all sub-managers
        self.daily_loss = DailyLossTracker(db)
        self.soft_pause = SoftPauseManager(telegram, db)
        self.capital_monitor = CapitalMonitor(db)
        self.hard_stop = HardStopManager(telegram, db, trading_bot)
        self.anomaly = AnomalyDetector()
        self.emergency = EmergencyKillManager(telegram, db, trading_bot)
        self.position_validator = PositionValidator()
    
    def pre_flight_check(self, signal: dict, open_positions: list) -> tuple:
        """
        Run all risk checks before executing a trade
        Return: (can_execute: bool, reason: str)
        """
        
        position_size = signal['entry'].get('position_size_usd')
        
        # Check 1: Is Emergency Kill active?
        if self.emergency.is_emergency_kill_active():
            return False, 'Emergency Kill active - system halted'
        
        # Check 2: Is Hard Stop active?
        if self.hard_stop.is_hard_stop_active():
            return False, 'Hard Stop active - system halted'
        
        # Check 3: Is Soft Pause active?
        if not self.soft_pause.can_execute_trade():
            return False, 'Soft Pause active - no new trades'
        
        # Check 4: Position size within hard cap?
        valid, msg = self.position_validator.validate_position_size(position_size)
        if not valid:
            return False, msg
        
        # Check 5: Portfolio exposure OK?
        valid, msg = self.position_validator.validate_portfolio_exposure(open_positions, position_size)
        if not valid:
            return False, msg
        
        # Check 6: Position count OK?
        valid, msg = self.position_validator.validate_position_count(open_positions)
        if not valid:
            return False, msg
        
        # All checks passed
        return True, 'All risk checks passed'
    
    def on_trade_executed(self, trade_result: dict):
        """Called when a trade executes - check for anomalies"""
        
        # Check execution matches signal
        anomaly, reason = self.anomaly.check_execution_mismatch(
            trade_result['signal'],
            trade_result['execution']
        )
        if anomaly:
            self.emergency.trigger_emergency_kill(anomaly, {
                'signal': trade_result['signal'],
                'execution': trade_result['execution'],
                'mismatch_reason': reason
            })
    
    def on_trade_closed(self, trade_pnl: float, current_capital: float):
        """Called when a trade closes - update daily loss and capital"""
        
        # Update daily loss
        status = self.daily_loss.add_trade_pnl(trade_pnl)
        if status == 'SOFT_PAUSE_TRIGGERED':
            self.soft_pause.trigger_soft_pause()
        
        # Update total capital
        status = self.capital_monitor.update_capital(trade_pnl)
        if status == 'HARD_STOP_TRIGGERED':
            self.hard_stop.trigger_hard_stop(current_capital)
    
    def on_api_error(self, error: Exception):
        """Called when API call fails"""
        anomaly, reason = self.anomaly.check_transaction_failure(error)
        if anomaly:
            self.emergency.trigger_emergency_kill(anomaly, {'error': str(error)})
    
    def on_api_data_issue(self, response: dict):
        """Called when API returns corrupted data"""
        anomaly, reason = self.anomaly.check_api_data_corruption(response)
        if anomaly:
            self.emergency.trigger_emergency_kill(anomaly, {'response': response})
    
    def on_midnight_reset(self):
        """Called at UTC midnight - reset daily counters"""
        self.daily_loss.reset_daily()
        self.soft_pause.resolve_soft_pause()
        logger.info('Midnight reset complete - daily loss counter cleared')
    
    def get_risk_status(self) -> dict:
        """Return complete risk status for monitoring"""
        return {
            'daily_loss': self.daily_loss.get_daily_status(),
            'capital': self.capital_monitor.get_capital_status(),
            'soft_pause_active': self.soft_pause.soft_pause_active,
            'hard_stop_active': self.hard_stop.hard_stop_active,
            'emergency_kill_active': self.emergency.emergency_kill_active,
            'timestamp': datetime.utcnow().isoformat()
        }
```

---

## 7. INTEGRATION WITH TRADING BOT

```python
class TradingBot:
    """Trading execution layer - uses Risk Manager for pre-flight checks"""
    
    def __init__(self, risk_manager):
        self.risk_manager = risk_manager
        self.jupiter_client = JupiterClient()
    
    def execute_signal(self, signal: dict):
        """Execute trade after Risk Manager approval"""
        
        open_positions = self._get_open_positions()
        
        # PRE-FLIGHT: Risk Manager checks
        can_execute, reason = self.risk_manager.pre_flight_check(signal, open_positions)
        
        if not can_execute:
            logger.warning(f'Trade rejected by Risk Manager: {reason}')
            return {'status': 'rejected', 'reason': reason}
        
        # Execute on Jupiter
        try:
            execution_result = self.jupiter_client.execute_swap(
                token_address=signal['token']['address'],
                amount_usd=signal['entry']['position_size_usd'],
                slippage=0.02  # 2% slippage protection
            )
            
            # Verify execution matches signal
            self.risk_manager.on_trade_executed({
                'signal': signal,
                'execution': execution_result
            })
            
            # Set stop loss and take profit orders
            self._set_stop_loss(execution_result['tx_hash'], signal['risk']['stop_loss_price'])
            self._set_take_profit_tiers(execution_result['tx_hash'], signal['profit_targets'])
            
            logger.info(f'Trade executed: {signal["token"]["symbol"]} @ ${signal["entry"]["price"]}')
            
            return {'status': 'success', 'tx_hash': execution_result['tx_hash']}
            
        except Exception as e:
            # Alert Risk Manager to anomaly
            self.risk_manager.on_api_error(e)
            return {'status': 'failed', 'error': str(e)}
```

---

## 8. TESTING RISK MANAGER

```python
# tests/test_risk_manager.py

def test_position_size_cap():
    """Verify position never exceeds $2"""
    validator = PositionValidator()
    
    assert validator.validate_position_size(2.0)[0] == True
    assert validator.validate_position_size(2.01)[0] == False
    assert validator.validate_position_size(5.0)[0] == False

def test_portfolio_exposure():
    """Verify portfolio never exceeds 30% exposure"""
    validator = PositionValidator()
    
    open_positions = [
        {'position_size': 2.0},  # 20%
        {'position_size': 1.0}   # 10%
    ]
    
    # Adding $1 would be 40% - should reject
    valid, msg = validator.validate_portfolio_exposure(open_positions, 1.0)
    assert valid == False

def test_soft_pause_activation():
    """Verify Soft Pause activates at -$3"""
    tracker = DailyLossTracker(db)
    
    tracker.add_trade_pnl(-1.5)
    assert tracker.check_soft_pause() == False
    
    tracker.add_trade_pnl(-1.5)  # Total -$3
    assert tracker.check_soft_pause() == True

def test_hard_stop_activation():
    """Verify Hard Stop activates at $5 capital"""
    monitor = CapitalMonitor(db)
    
    monitor.update_capital(-4.5)  # $5.5 remaining
    assert monitor.is_hard_stop_active() == False
    
    monitor.update_capital(-0.5)  # $5.00 remaining
    assert monitor.is_hard_stop_active() == False
    
    monitor.update_capital(-0.01)  # $4.99 remaining
    assert monitor.is_hard_stop_active() == True

def test_emergency_kill_on_consecutive_failures():
    """Verify Emergency Kill on 3 failures"""
    detector = AnomalyDetector()
    
    detector.check_transaction_failure(Exception('fail 1'))
    assert detector.is_emergency_kill_active() == False
    
    detector.check_transaction_failure(Exception('fail 2'))
    assert detector.is_emergency_kill_active() == False
    
    detector.check_transaction_failure(Exception('fail 3'))
    assert detector.is_emergency_kill_active() == True
```

---

## 9. KILL SWITCH STATE MACHINE

```
NORMAL STATE
├─ Daily loss check
│  └─ Loss >= -$3 → Trigger Soft Pause
│
├─ Capital check
│  └─ Capital < $5 → Trigger Hard Stop
│
├─ Anomaly check
│  ├─ 3 consecutive failures → Trigger Emergency Kill
│  ├─ Corrupted API data → Trigger Emergency Kill
│  ├─ Position size violation → Trigger Emergency Kill
│  └─ Execution mismatch → Trigger Emergency Kill
│
└─ No issues → Keep trading


SOFT PAUSE STATE
├─ Existing positions close naturally
├─ No new trades executed
├─ Resume at UTC midnight
└─ Return to Normal


HARD STOP STATE
├─ All positions force-closed
├─ System completely halted
├─ Requires manual investigation
├─ Requires manual restart
└─ Never auto-resume


EMERGENCY KILL STATE
├─ All positions force-closed
├─ System completely halted
├─ Send urgent diagnostic alert
├─ Requires manual code review
├─ Requires fix deployment
└─ Requires manual restart
```

---

## 10. SUCCESS CRITERIA - RISK MANAGER COMPLETE

✅ Position sizes never exceed hard caps ($2 max)  
✅ Portfolio exposure never exceeds 30%  
✅ Position count never exceeds 3 concurrent  
✅ Soft Pause triggers at exactly -$3 daily loss  
✅ Soft Pause auto-resumes at UTC midnight  
✅ Hard Stop triggers at $5 capital (50% drawdown)  
✅ Hard Stop requires manual restart  
✅ Emergency Kill triggers on technical anomalies  
✅ Emergency Kill sends urgent alerts with diagnostics  
✅ All kill switch transitions logged to database  
✅ Risk Manager overrides all other systems  
✅ No trade executes without Risk Manager approval  

---

**Risk Manager is the difference between controlled risk and account blowup.**

Every hard rule in this spec is there for a reason. No exceptions. No overrides.
