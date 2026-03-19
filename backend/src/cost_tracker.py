"""
Cost Tracker - Monitor API usage and costs in real-time

Tracks:
- Haiku API calls (token count, cost)
- Daily spending
- Monthly budget vs. actual
"""

import logging
import json
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger('cost_tracker')

class CostTracker:
    """Track API costs throughout the day"""
    
    HAIKU_INPUT_COST = 0.80 / 1_000_000  # $0.80 per 1M input tokens
    HAIKU_OUTPUT_COST = 4.00 / 1_000_000  # $4.00 per 1M output tokens
    
    def __init__(self, cost_log_path='data/costs.json'):
        self.cost_log_path = Path(cost_log_path)
        self.cost_log_path.parent.mkdir(parents=True, exist_ok=True)
        self.daily_costs = self._load_costs()
        
        logger.info(f'💰 Cost tracker initialized')
    
    def log_haiku_call(self, input_tokens: int, output_tokens: int, token_symbol: str = 'UNKNOWN'):
        """Log a Haiku API call"""
        today = datetime.utcnow().strftime('%Y-%m-%d')
        
        # Calculate cost
        input_cost = input_tokens * self.HAIKU_INPUT_COST
        output_cost = output_tokens * self.HAIKU_OUTPUT_COST
        total_cost = input_cost + output_cost
        
        # Update daily total
        if today not in self.daily_costs:
            self.daily_costs[today] = {
                'total_calls': 0,
                'total_input_tokens': 0,
                'total_output_tokens': 0,
                'total_cost_usd': 0.0,
                'calls': []
            }
        
        self.daily_costs[today]['total_calls'] += 1
        self.daily_costs[today]['total_input_tokens'] += input_tokens
        self.daily_costs[today]['total_output_tokens'] += output_tokens
        self.daily_costs[today]['total_cost_usd'] += total_cost
        self.daily_costs[today]['calls'].append({
            'timestamp': datetime.utcnow().isoformat(),
            'token': token_symbol,
            'input_tokens': input_tokens,
            'output_tokens': output_tokens,
            'cost_usd': total_cost
        })
        
        # Save to disk
        self._save_costs()
        
        # Log to console
        logger.info(f'💰 Haiku call: {token_symbol} | Input: {input_tokens:,} | Output: {output_tokens:,} | Cost: ${total_cost:.4f}')
        
        # Show daily total
        daily_total = self.daily_costs[today]['total_cost_usd']
        logger.info(f'   📊 Today\'s total: ${daily_total:.2f} ({self.daily_costs[today]["total_calls"]} calls)')
    
    def get_daily_cost(self, date: str = None) -> float:
        """Get cost for a specific day (default: today)"""
        if date is None:
            date = datetime.utcnow().strftime('%Y-%m-%d')
        
        return self.daily_costs.get(date, {}).get('total_cost_usd', 0.0)
    
    def get_monthly_cost(self) -> float:
        """Get total cost for current month"""
        today = datetime.utcnow()
        month_start = today.replace(day=1).strftime('%Y-%m')
        
        total = 0.0
        for date, data in self.daily_costs.items():
            if date.startswith(month_start):
                total += data['total_cost_usd']
        
        return total
    
    def get_cost_summary(self) -> dict:
        """Get cost summary for logging/alerts"""
        today = datetime.utcnow().strftime('%Y-%m-%d')
        daily_cost = self.get_daily_cost(today)
        monthly_cost = self.get_monthly_cost()
        
        return {
            'date': today,
            'daily_cost': daily_cost,
            'daily_limit': 5.00,
            'daily_percent': (daily_cost / 5.00) * 100,
            'monthly_cost': monthly_cost,
            'monthly_limit': 200.00,
            'monthly_percent': (monthly_cost / 200.00) * 100,
            'warning_daily': daily_cost > 3.75,  # 75% of $5
            'warning_monthly': monthly_cost > 150.00  # 75% of $200
        }
    
    def check_and_alert(self) -> str:
        """Check limits and return alert if exceeded"""
        summary = self.get_cost_summary()
        
        if summary['warning_monthly']:
            msg = f"⚠️  MONTHLY BUDGET WARNING: ${summary['monthly_cost']:.2f} / $200 ({summary['monthly_percent']:.1f}%)"
            logger.warning(msg)
            return msg
        
        if summary['warning_daily']:
            msg = f"⚠️  DAILY BUDGET WARNING: ${summary['daily_cost']:.2f} / $5 ({summary['daily_percent']:.1f}%)"
            logger.warning(msg)
            return msg
        
        return None
    
    def _load_costs(self) -> dict:
        """Load cost data from disk"""
        if self.cost_log_path.exists():
            try:
                with open(self.cost_log_path) as f:
                    return json.load(f)
            except:
                return {}
        return {}
    
    def _save_costs(self):
        """Save cost data to disk"""
        with open(self.cost_log_path, 'w') as f:
            json.dump(self.daily_costs, f, indent=2)
