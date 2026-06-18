"""
ml_engine/feedback/accuracy_tracker.py
────────────────────────────────────────
Tracks the real-world accuracy of models over time.
Provides metrics for the retraining scheduler.
"""

import pandas as pd
import logging
from typing import Dict

logger = logging.getLogger(__name__)

class AccuracyTracker:
    def __init__(self, db_conn):
        self.db = db_conn

    def calculate_model_accuracy(self, model_source: str, days: int = 7) -> Dict:
        """
        Calculate win rate, sharpe ratio, and total return of a specific model source
        (e.g., 'lstm', 'xgboost', 'rl', 'ensemble') over the last N days.
        """
        query = f"""
            SELECT pnl, timestamp 
            FROM trades 
            WHERE source = '{model_source}' 
              AND timestamp >= NOW() - INTERVAL '{days} days'
        """
        try:
            df = pd.read_sql(query, self.db)
            if df.empty:
                return {"win_rate": 0.0, "total_return": 0.0, "trades": 0}
                
            wins = len(df[df['pnl'] > 0])
            total = len(df)
            
            return {
                "win_rate": wins / total if total > 0 else 0.0,
                "total_return": df['pnl'].sum(),
                "trades": total
            }
        except Exception as e:
            logger.error(f"[AccuracyTracker] Error calculating accuracy for {model_source}: {e}")
            return {"win_rate": 0.0, "total_return": 0.0, "trades": 0}
