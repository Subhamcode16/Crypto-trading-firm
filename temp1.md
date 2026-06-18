# xgb_model.py — Binary Architecture

import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import classification_report
import joblib

# ── Final directional feature set ────────────────────────────────────
DIRECTIONAL_FEATURES = [
    'rsi_slope_10',
    'price_acceleration',
    'body_persistence_10',
    'return_asymmetry_10',
    'macd_hist_slope',
    'price_vs_20h_low',
    'price_vs_20h_high',
    'price_vs_50h_low',    # narrow miss — include as structural pair
    'price_vs_50h_high',   # narrow miss — include as structural pair
]

class BinarySignalEngine:
    
    def __init__(self):
        self.model_a = None   # Move predictor
        self.model_b = None   # Direction predictor
        self.move_threshold     = 0.60
        self.long_threshold     = 0.60
        self.short_threshold    = 0.40
    
    # ── Training ──────────────────────────────────────────────────────
    
    def train(self, df_features: pd.DataFrame, 
                    labels: pd.Series) -> dict:
        
        X = df_features[DIRECTIONAL_FEATURES].copy()
        
        # ── Model A: Will a significant move occur? ───────────────────
        y_move = (labels != 0).astype(int)
        
        # Natural imbalance: ~20-30% moves, ~70-80% no-signal
        # Do NOT balance — preserve the natural distribution
        move_weight = (y_move == 0).sum() / (y_move == 1).sum()
        sample_weights_a = y_move.map({0: 1.0, 1: move_weight * 0.3})
        # 0.3 multiplier: slight boost to minority without flooding
        
        self.model_a = xgb.XGBClassifier(
            n_estimators     = 300,
            max_depth        = 4,       # Shallow — 9 features, avoid overfit
            learning_rate    = 0.05,
            subsample        = 0.8,
            colsample_bytree = 0.8,
            min_child_weight = 50,      # High — forces conservative splits
            gamma            = 1.0,     # Pruning — prevents noise memorization
            eval_metric      = 'logloss',
            early_stopping_rounds = 30,
            random_state     = 42,
        )
        
        tscv = TimeSeriesSplit(n_splits=5)
        splits = list(tscv.split(X))
        train_idx, val_idx = splits[-1]   # Use last fold for early stopping
        
        self.model_a.fit(
            X.iloc[train_idx], y_move.iloc[train_idx],
            sample_weight = sample_weights_a.iloc[train_idx],
            eval_set      = [(X.iloc[val_idx], y_move.iloc[val_idx])],
            verbose       = 50,
        )
        
        # ── Model B: Which direction? ─────────────────────────────────
        # Train ONLY on bars where a move occurred
        signal_mask = labels != 0
        X_signals   = X[signal_mask]
        y_direction = (labels[signal_mask] == 1).astype(int)  # 1=LONG, 0=SHORT
        
        print(f"\nModel B training set: {len(X_signals)} bars")
        print(f"  LONG:  {y_direction.sum()} ({y_direction.mean():.1%})")
        print(f"  SHORT: {(~y_direction.astype(bool)).sum()} "
              f"({(1-y_direction.mean()):.1%})")
        
        # Direction should be roughly balanced — check this
        # If severely imbalanced (>65/35), the market had strong
        # directional bias in training period — acceptable but note it
        
        self.model_b = xgb.XGBClassifier(
            n_estimators     = 200,
            max_depth        = 3,       # Even shallower — direction is harder
            learning_rate    = 0.05,
            subsample        = 0.7,
            colsample_bytree = 0.7,
            min_child_weight = 20,
            gamma            = 2.0,     # More aggressive pruning
            eval_metric      = 'logloss',
            early_stopping_rounds = 30,
            random_state     = 42,
        )
        
        # For direction: no weighting — let the natural distribution stand
        signal_splits = list(tscv.split(X_signals))
        s_train_idx, s_val_idx = signal_splits[-1]
        
        self.model_b.fit(
            X_signals.iloc[s_train_idx], y_direction.iloc[s_train_idx],
            eval_set = [(X_signals.iloc[s_val_idx], 
                         y_direction.iloc[s_val_idx])],
            verbose  = 50,
        )
        
        return self._evaluate(X, labels, signal_mask)
    
    # ── Inference ─────────────────────────────────────────────────────
    
    def predict(self, features: pd.Series) -> dict:
        X = features[DIRECTIONAL_FEATURES].values.reshape(1, -1)
        
        # Gate 1: Is a move coming?
        move_prob = self.model_a.predict_proba(X)[0][1]
        
        if move_prob < self.move_threshold:
            return {
                'action':     'NO_SIGNAL',
                'confidence': move_prob,
                'move_prob':  move_prob,
                'dir_prob':   None,
            }
        
        # Gate 2: Which direction?
        dir_prob = self.model_b.predict_proba(X)[0][1]  # P(LONG)
        
        if dir_prob > self.long_threshold:
            action = 'STRONG_LONG'
        elif dir_prob < self.short_threshold:
            action = 'STRONG_SHORT'
        else:
            action = 'NO_SIGNAL'   # Move likely, direction ambiguous
        
        return {
            'action':     action,
            'confidence': dir_prob if action != 'NO_SIGNAL' else move_prob,
            'move_prob':  move_prob,
            'dir_prob':   dir_prob,
        }
    
    # ── Evaluation ────────────────────────────────────────────────────
    
    def _evaluate(self, X: pd.DataFrame, 
                        labels: pd.Series,
                        signal_mask: pd.Series) -> dict:
        
        move_preds = self.model_a.predict(X)
        move_true  = (labels != 0).astype(int)
        
        print("\n=== MODEL A: MOVE PREDICTOR ===")
        print(classification_report(move_true, move_preds,
                                     target_names=['NO_MOVE', 'MOVE']))
        
        X_signals   = X[signal_mask]
        dir_preds   = self.model_b.predict(X_signals)
        dir_true    = (labels[signal_mask] == 1).astype(int)
        
        print("\n=== MODEL B: DIRECTION PREDICTOR ===")
        print(classification_report(dir_true, dir_preds,
                                     target_names=['SHORT', 'LONG']))
        
        return {
            'model_a_accuracy': (move_preds == move_true).mean(),
            'model_b_accuracy': (dir_preds == dir_true).mean(),
        }
    
    # ── Persistence ───────────────────────────────────────────────────
    
    def save(self, path: str) -> None:
        joblib.dump({'model_a': self.model_a, 
                     'model_b': self.model_b}, path)
    
    def load(self, path: str) -> None:
        models = joblib.load(path)
        self.model_a = models['model_a']
        self.model_b = models['model_b']


The Three Numbers To Report After Training
When you run this, the output that matters before any backtest is:
Model A — Precision on MOVE class
  Target: > 0.35
  Why: With ~20-30% natural move rate, random = 0.25
       Anything above 0.35 means the model has genuine signal
       
Model B — Overall accuracy on direction
  Target: > 0.53
  Why: Random = 0.50. You need consistent above-chance direction
       prediction. 53% sounds small but compounds significantly.

Model B — LONG vs SHORT balance in training set
  Target: 45/55 to 55/45
  Why: Severe imbalance means the market had strong directional
       bias in training — model will inherit that bias
Train the model. Report those three numbers before running any backtest. If Model A precision on MOVE is below 0.30 or Model B accuracy is below 0.51, the feature set is still insufficient and we need to discuss whether a tree model is the right architecture for this problem. If both clear the targets, run the raw baseline backtest immediately.