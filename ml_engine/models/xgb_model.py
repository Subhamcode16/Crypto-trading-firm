"""
ml_engine/models/xgb_model.py
───────────────────────────────
XGBoost Pattern Strength Classifier.

Predicts: STRONG_LONG / STRONG_SHORT / NO_SIGNAL
using a two-model binary architecture.
"""

import json
import logging
import os
import pickle
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

SAVED_DIR = Path(__file__).parent / "saved"
SAVED_DIR.mkdir(parents=True, exist_ok=True)

# Signal class mapping
SIGNAL_CLASSES = {
    0: "NO_SIGNAL",
    1: "STRONG_LONG",
    2: "STRONG_SHORT",
}
SIGNAL_COLORS = {
    "STRONG_LONG":  "🟢",
    "STRONG_SHORT": "🔴",
    "NO_SIGNAL":    "⚪",
}

DIRECTIONAL_FEATURES = [
    'rsi_slope_10',
    'price_acceleration',
    'body_persistence_10',
    'return_asymmetry_10',
    'macd_hist_slope',
    'price_vs_20h_low',
    'price_vs_20h_high',
    'price_vs_50h_low',    
    'price_vs_50h_high',   
]


class XGBModel:
    def __init__(self, symbol: str = "BTC/USDT", timeframe: str = "1h"):
        self.symbol       = symbol
        self.timeframe    = timeframe
        self._model_move  = None
        self._model_direction = None
        self._feature_names: List[str] = DIRECTIONAL_FEATURES.copy()
        self._trained_on: int = 0
        self._test_accuracy: float = 0.0
        self._importance: Dict[str, float] = {}

    def predict(self, features: Dict) -> Dict:
        """Predict signal class from a flat feature dict."""
        if self._model_move is None or self._model_direction is None:
            raise RuntimeError("Model not loaded. Call load() first.")

        X = self._build_input_vector(features)
        X = np.array([X], dtype=np.float32)
        
        move_prob = self._model_move.predict_proba(X)[0][1]
        
        if move_prob < 0.60:
            signal = "NO_SIGNAL"
            conf = move_prob
        else:
            dir_prob = self._model_direction.predict_proba(X)[0][1]
            if dir_prob > 0.60:
                signal = "STRONG_LONG"
                conf = dir_prob
            elif dir_prob < 0.40:
                signal = "STRONG_SHORT"
                conf = 1.0 - dir_prob
            else:
                signal = "NO_SIGNAL"
                conf = max(dir_prob, 1.0 - dir_prob)

        return {
            "signal":     signal,
            "confidence": round(float(conf), 4),
            "strong":     signal in ("STRONG_LONG", "STRONG_SHORT"),
            "icon":       SIGNAL_COLORS.get(signal, "⚪"),
        }

    def predict_df(self, df: pd.DataFrame, feature_names: List[str]) -> pd.DataFrame:
        """Vectorized prediction for entire DataFrame (training + backtest)."""
        if self._model_move is None or self._model_direction is None:
            raise RuntimeError("Model not loaded.")

        # Ensure we only use the selected directional features!
        X = df[self._feature_names].values.astype(np.float32)
        
        move_probs = self._model_move.predict_proba(X)[:, 1]
        dir_probs = self._model_direction.predict_proba(X)[:, 1]
        
        preds = np.zeros(len(df), dtype=int)
        confidences = np.zeros(len(df), dtype=float)
        
        strong_long_mask = (move_probs >= 0.60) & (dir_probs > 0.60)
        strong_short_mask = (move_probs >= 0.60) & (dir_probs < 0.40)
        
        preds[strong_long_mask] = 1
        preds[strong_short_mask] = 2
        
        confidences[strong_long_mask] = dir_probs[strong_long_mask]
        confidences[strong_short_mask] = 1.0 - dir_probs[strong_short_mask]
        
        no_signal_mask = ~(strong_long_mask | strong_short_mask)
        confidences[no_signal_mask] = move_probs[no_signal_mask]

        df = df.copy(deep=False)
        df["xgb_pred"]       = preds
        df["xgb_signal"]     = [SIGNAL_CLASSES[p] for p in preds]
        df["xgb_confidence"] = confidences
        df["xgb_strong"]     = (preds == 1) | (preds == 2)
        return df

    # ─── Persistence ─────────────────────────────────────────────────────

    def save(self, path: Optional[str] = None) -> str:
        if path is None:
            name = f"xgb_{self.symbol.replace('/','_')}_{self.timeframe}.pkl"
            path = str(SAVED_DIR / name)

        payload = {
            "model_move":      self._model_move,
            "model_direction": self._model_direction,
            "feature_names":   self._feature_names,
            "symbol":          self.symbol,
            "timeframe":       self.timeframe,
            "trained_on":      self._trained_on,
            "test_accuracy":   self._test_accuracy,
            "importance":      self._importance,
        }
        with open(path, "wb") as f:
            pickle.dump(payload, f)
        return path

    @classmethod
    def load(cls, path: str) -> "XGBModel":
        with open(path, "rb") as f:
            payload = pickle.load(f)

        instance = cls(
            symbol=payload.get("symbol", "BTC/USDT"),
            timeframe=payload.get("timeframe", "1h"),
        )
        instance._model_move = payload.get("model_move") or payload.get("model")
        instance._model_direction = payload.get("model_direction") or payload.get("model")
        instance._feature_names = payload.get("feature_names", DIRECTIONAL_FEATURES.copy())
        instance._trained_on    = payload.get("trained_on", 0)
        instance._test_accuracy = payload.get("test_accuracy", 0.0)
        instance._importance    = payload.get("importance", {})
        return instance

    @staticmethod
    def get_save_path(symbol: str, timeframe: str) -> str:
        name = f"xgb_{symbol.replace('/','_')}_{timeframe}.pkl"
        return str(SAVED_DIR / name)

    @staticmethod
    def exists(symbol: str, timeframe: str) -> bool:
        return os.path.isfile(XGBModel.get_save_path(symbol, timeframe))

    def _build_input_vector(self, features: Dict) -> List[float]:
        return [float(features.get(k, 0.0)) for k in self._feature_names]

    @staticmethod
    def generate_labels(df: pd.DataFrame, horizon: int = 8, min_move_pct: float = 0.004) -> pd.Series:
        close = df['close']
        future_return = close.shift(-horizon) / close - 1
        
        true_range = pd.concat([
            df['high'] - df['low'],
            (df['high'] - close.shift(1)).abs(),
            (df['low']  - close.shift(1)).abs()
        ], axis=1).max(axis=1)
        atr_pct = true_range.shift(1).rolling(14).mean() / close
        
        long_threshold  = np.maximum(1.2 * atr_pct, min_move_pct)
        short_threshold = np.maximum(1.2 * atr_pct, min_move_pct)
        
        labels = pd.Series(0, index=df.index)
        labels[future_return >= long_threshold]  = 1
        labels[future_return <= -short_threshold] = 2
        labels.iloc[-horizon:] = np.nan
        return labels


class XGBTrainer:
    def __init__(self, symbol: str = "BTC/USDT", timeframe: str = "1h"):
        self.symbol    = symbol
        self.timeframe = timeframe

    def train(
        self,
        df_feat: pd.DataFrame,
        feature_names: List[str],
        use_optuna: bool = False,
        retrain: bool = False,
    ) -> Tuple[XGBModel, Dict]:
        
        labels = XGBModel.generate_labels(df_feat, horizon=8)
        
        # Enforce exact features early to save memory!
        features_to_use = DIRECTIONAL_FEATURES
        
        valid_idx = labels.dropna().index
        df_feat = df_feat.loc[valid_idx, features_to_use].copy()
        labels = labels.loc[valid_idx].astype(int)
        
        X = df_feat.values.astype(np.float32)
        y = labels.values.astype(np.int32)

        n_test  = max(50, int(len(X) * 0.15))
        
        X_train, X_test = X[:-n_test], X[-n_test:]
        y_train, y_test = y[:-n_test], y[-n_test:]

        import xgboost as xgb
        from sklearn.metrics import classification_report, accuracy_score
        
        # --- Model A: Move Predictor ---
        y_train_move = (y_train != 0).astype(int)
        y_test_move  = (y_test != 0).astype(int)
        
        # Natural imbalance handling (from temp1.md)
        move_weight = (y_train_move == 0).sum() / max(1, (y_train_move == 1).sum())
        sample_weights_a = np.where(y_train_move == 0, 1.0, move_weight * 0.3)
        
        model_move = xgb.XGBClassifier(
            n_estimators     = 300,
            max_depth        = 4,
            learning_rate    = 0.05,
            subsample        = 0.8,
            colsample_bytree = 0.8,
            min_child_weight = 50,
            gamma            = 1.0,
            eval_metric      = 'logloss',
            early_stopping_rounds = 30,
            random_state     = 42,
            use_label_encoder=False,
            tree_method="hist",
        )
        model_move.fit(
            X_train, y_train_move,
            sample_weight=sample_weights_a,
            eval_set=[(X_test, y_test_move)],
            verbose=False
        )
        
        # --- Model B: Direction Predictor ---
        move_mask_train = y_train != 0
        X_train_dir = X_train[move_mask_train]
        y_train_dir = (y_train[move_mask_train] == 1).astype(int)
        
        move_mask_test = y_test != 0
        X_test_dir = X_test[move_mask_test]
        y_test_dir = (y_test[move_mask_test] == 1).astype(int)
        
        print(f"\nModel B training set: {len(X_train_dir)} bars")
        print(f"  LONG:  {y_train_dir.sum()} ({y_train_dir.mean():.1%})")
        print(f"  SHORT: {(len(y_train_dir) - y_train_dir.sum())} ({(1 - y_train_dir.mean()):.1%})")

        model_direction = xgb.XGBClassifier(
            n_estimators     = 200,
            max_depth        = 3,
            learning_rate    = 0.05,
            subsample        = 0.7,
            colsample_bytree = 0.7,
            min_child_weight = 20,
            gamma            = 2.0,
            eval_metric      = 'logloss',
            early_stopping_rounds = 30,
            random_state     = 42,
            use_label_encoder=False,
            tree_method="hist",
        )
        model_direction.fit(
            X_train_dir, y_train_dir,
            eval_set=[(X_test_dir, y_test_dir)],
            verbose=False
        )

        # --- Evaluate ---
        move_preds = model_move.predict(X_test)
        print("\n=== MODEL A: MOVE PREDICTOR ===")
        print(classification_report(y_test_move, move_preds, target_names=['NO_MOVE', 'MOVE'], zero_division=0))
        
        dir_preds = model_direction.predict(X_test_dir)
        print("\n=== MODEL B: DIRECTION PREDICTOR ===")
        print(classification_report(y_test_dir, dir_preds, target_names=['SHORT', 'LONG'], zero_division=0))

        xgb_model = XGBModel(symbol=self.symbol, timeframe=self.timeframe)
        xgb_model._model_move = model_move
        xgb_model._model_direction = model_direction
        xgb_model._feature_names = features_to_use
        xgb_model._trained_on = len(X_train)
        
        # Determine e2e accuracy
        test_df = pd.DataFrame(X_test, columns=features_to_use)
        test_df = xgb_model.predict_df(test_df, features_to_use)
        acc = float(accuracy_score(y_test, test_df['xgb_pred']))

        xgb_model._test_accuracy = acc
        if retrain or not XGBModel.exists(self.symbol, self.timeframe):
            xgb_model.save()

        report = {
            "test_accuracy": round(acc, 4),
            "model_saved":   True,
        }
        return xgb_model, report
