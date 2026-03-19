#!/usr/bin/env python3
"""
ML Trainer — Weekly retraining pipeline for the XGBoost pump probability model.
Triggered by Agent 9 (Performance Analyst) on its weekly review cycle.

How it works:
1. Loads all saved feature vectors from past week (src/ml/data/)
2. Loads trade outcomes (win/loss) from trade history
3. Labels each trade (pump > 50% in 30min = 1, else = 0)
4. Trains (or retrains) an XGBoost classifier
5. Compares new model vs old model accuracy
6. If improved → hot-swaps the model file (pump_model.pkl)
7. Logs results for Agent 9's audit report
"""

import os
import json
import pickle
import logging
import glob
from datetime import datetime
from typing import Dict, List, Tuple, Optional

logger = logging.getLogger('ml_trainer')

MODEL_PATH   = os.path.join(os.path.dirname(__file__), 'models', 'pump_model.pkl')
DATA_DIR     = os.path.join(os.path.dirname(__file__), 'data')
PUMP_THRESHOLD = 0.5   # 50% gain in 30min = positive label

os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)
os.makedirs(DATA_DIR, exist_ok=True)


class MLTrainer:
    """Weekly training loop for the pump probability ML model."""

    def retrain(self, trade_outcomes: List[Dict]) -> Dict:
        """
        Main entry point. Called by Agent 9 weekly.

        Args:
            trade_outcomes: List of dicts with keys:
                - trade_id: str
                - entry_price: float
                - exit_price: float (or None if still open)
                - price_change_pct: float (actual outcome)
                - profit_usd: float

        Returns:
            Retraining report dict
        """
        logger.info(f"[TRAINER] Starting weekly ML retraining with {len(trade_outcomes)} trades")
        
        # 1. Load saved feature vectors
        features, labels, trade_ids = self._load_training_data(trade_outcomes)
        
        if len(features) < 30:
            logger.warning(f"[TRAINER] Only {len(features)} trades with features. Need 30+ for reliable training.")
            return {
                "status": "skipped",
                "reason": f"Insufficient data: {len(features)} trades (min: 30)",
                "timestamp": datetime.utcnow().isoformat()
            }

        # 2. Train new model
        new_model, accuracy, precision, recall = self._train(features, labels)

        # 3. Compare with existing model
        existing_accuracy = self._get_existing_accuracy()
        improved = accuracy > existing_accuracy

        report = {
            "status": "completed",
            "timestamp": datetime.utcnow().isoformat(),
            "training_samples": len(features),
            "positive_labels": sum(labels),
            "negative_labels": len(labels) - sum(labels),
            "new_accuracy":     round(accuracy, 4),
            "new_precision":    round(precision, 4),
            "new_recall":       round(recall, 4),
            "old_accuracy":     round(existing_accuracy, 4),
            "model_improved":   improved,
        }

        # 4. Save if improved (or first model)
        if improved or existing_accuracy == 0.0:
            self._save_model(new_model, features[0].keys() if features else [], len(features), accuracy)
            report["action"] = "model_updated"
            logger.info(f"[TRAINER] Model UPDATED: {existing_accuracy:.3f} → {accuracy:.3f}")
        else:
            report["action"] = "model_kept"
            logger.info(f"[TRAINER] Keeping old model: {accuracy:.3f} < {existing_accuracy:.3f}")

        return report

    def _load_training_data(self, trade_outcomes: List[Dict]) -> Tuple[List[Dict], List[int], List[str]]:
        """Match saved feature vectors with trade outcomes to build training set."""
        features = []
        labels   = []
        ids      = []

        outcome_map = {t['trade_id']: t for t in trade_outcomes}

        # Scan feature files
        pattern = os.path.join(DATA_DIR, "features_*.json")
        for filepath in glob.glob(pattern):
            try:
                with open(filepath) as f:
                    feat = json.load(f)
                
                trade_id    = feat.get('_trade_id')
                token_addr  = feat.get('_token_address')
                
                outcome = outcome_map.get(trade_id) or outcome_map.get(token_addr)
                if not outcome:
                    continue
                
                price_change = outcome.get('price_change_pct', 0)
                label = 1 if price_change >= PUMP_THRESHOLD * 100 else 0

                # Clean: remove metadata keys
                clean_feat = {k: v for k, v in feat.items() if not k.startswith('_') and isinstance(v, (int, float))}
                
                features.append(clean_feat)
                labels.append(label)
                ids.append(trade_id or token_addr)
                
            except Exception as e:
                logger.debug(f"[TRAINER] Skipping {filepath}: {e}")

        logger.info(f"[TRAINER] Loaded {len(features)} training samples ({sum(labels)} pumps, {len(labels)-sum(labels)} no-pumps)")
        return features, labels, ids

    def _train(self, features: List[Dict], labels: List[int]):
        """Train XGBoost classifier. Falls back to RandomForest if xgboost not installed."""
        try:
            import xgboost as xgb
            from sklearn.model_selection import train_test_split
            from sklearn.metrics import accuracy_score, precision_score, recall_score
            import numpy as np

            # Build feature matrix
            feature_names = list(features[0].keys())
            X = [[row.get(k, 0.0) for k in feature_names] for row in features]
            y = labels

            X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

            model = xgb.XGBClassifier(
                n_estimators=100,
                max_depth=5,
                learning_rate=0.1,
                scale_pos_weight=max(1, len(y) / max(1, sum(y))),  # Handle imbalance
                use_label_encoder=False,
                eval_metric='logloss',
                random_state=42
            )
            model.fit(X_train, y_train, verbose=False)

            y_pred = model.predict(X_test)
            acc  = accuracy_score(y_test, y_pred)
            prec = precision_score(y_test, y_pred, zero_division=0)
            rec  = recall_score(y_test, y_pred, zero_division=0)

            logger.info(f"[TRAINER] XGBoost trained: acc={acc:.3f}, prec={prec:.3f}, rec={rec:.3f}")
            return model, acc, prec, rec

        except ImportError:
            logger.warning("[TRAINER] xgboost not installed, using RandomForest fallback")
            return self._train_fallback(features, labels)

    def _train_fallback(self, features: List[Dict], labels: List[int]):
        """Fallback: train with sklearn RandomForest if xgboost unavailable."""
        from sklearn.ensemble import RandomForestClassifier
        from sklearn.model_selection import train_test_split
        from sklearn.metrics import accuracy_score, precision_score, recall_score

        feature_names = list(features[0].keys())
        X = [[row.get(k, 0.0) for k in feature_names] for row in features]

        X_train, X_test, y_train, y_test = train_test_split(X, labels, test_size=0.2, random_state=42)
        model = RandomForestClassifier(n_estimators=100, random_state=42)
        model.fit(X_train, y_train)

        y_pred = model.predict(X_test)
        return (
            model,
            accuracy_score(y_test, y_pred),
            precision_score(y_test, y_pred, zero_division=0),
            recall_score(y_test, y_pred, zero_division=0)
        )

    def _get_existing_accuracy(self) -> float:
        """Load accuracy of the currently saved model."""
        if not os.path.exists(MODEL_PATH):
            return 0.0
        try:
            with open(MODEL_PATH, 'rb') as f:
                saved = pickle.load(f)
            return saved.get('accuracy', 0.0)
        except:
            return 0.0

    def _save_model(self, model, feature_names, trade_count: int, accuracy: float):
        """Save model + metadata to disk."""
        os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)
        payload = {
            'model':         model,
            'feature_names': list(feature_names),
            'accuracy':      accuracy,
            'trained_on':    trade_count,
            'trained_at':    datetime.utcnow().isoformat()
        }
        with open(MODEL_PATH, 'wb') as f:
            pickle.dump(payload, f)
        logger.info(f"[TRAINER] Model saved to {MODEL_PATH} (accuracy={accuracy:.3f})")

    def save_outcome(self, trade_id: str, price_change_pct: float, profit_usd: float):
        """
        Store trade outcome for a specific trade_id.
        Called by Agent 9 after a trade closes.
        """
        outcome_path = os.path.join(DATA_DIR, f"outcome_{trade_id}.json")
        outcome = {
            "trade_id": trade_id,
            "price_change_pct": price_change_pct,
            "profit_usd": profit_usd,
            "recorded_at": datetime.utcnow().isoformat()
        }
        try:
            with open(outcome_path, 'w') as f:
                json.dump(outcome, f, indent=2)
        except Exception as e:
            logger.error(f"[TRAINER] Failed to save outcome: {e}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    # Test with mock outcomes
    mock_outcomes = [
        {"trade_id": "test_1", "price_change_pct": 75,  "profit_usd": 120},
        {"trade_id": "test_2", "price_change_pct": -10, "profit_usd": -40},
    ]
    
    trainer = MLTrainer()
    report = trainer.retrain(mock_outcomes)
    print(json.dumps(report, indent=2))
