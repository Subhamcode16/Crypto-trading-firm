"""
ml_engine/feedback/retrain_scheduler.py
─────────────────────────────────────────
Evaluates model accuracy drops and triggers retraining
jobs via Colab integration or background tasks.
"""

import logging
from typing import List

from ml_engine.feedback.accuracy_tracker import AccuracyTracker

logger = logging.getLogger(__name__)

class RetrainScheduler:
    def __init__(self, db_conn):
        self.tracker = AccuracyTracker(db_conn)
        self.threshold_win_rate = 0.45  # If win rate falls below 45%, trigger retrain

    def evaluate_models(self) -> List[str]:
        """
        Check all models and return a list of sources that need retraining.
        """
        models_to_retrain = []
        for model in ["lstm", "xgboost", "rl_ppo"]:
            metrics = self.tracker.calculate_model_accuracy(model, days=7)
            
            # Require at least 20 trades to make a judgement
            if metrics["trades"] >= 20 and metrics["win_rate"] < self.threshold_win_rate:
                logger.warning(f"[RetrainScheduler] {model} accuracy degraded to {metrics['win_rate']:.2%}. Scheduling retrain.")
                models_to_retrain.append(model)
                
        return models_to_retrain

    def trigger_retrain(self, models: List[str]):
        """
        Trigger the actual retraining process.
        For heavy models like LSTM/RL, this alerts the user to run Colab.
        """
        if not models:
            return
            
        logger.info(f"[RetrainScheduler] Triggering retraining for: {', '.join(models)}")
        
        # XGBoost is fast, we could retrain it locally in a background thread
        if "xgboost" in models:
            logger.info("[RetrainScheduler] XGBoost can be retrained locally. Firing async job...")
            # In real system: launch background thread for XGBoost retrain
            
        if "lstm" in models or "rl_ppo" in models:
            logger.critical(f"[RetrainScheduler] GPU recommended for {models}. Please run notebooks/colab_train.py!")
            
