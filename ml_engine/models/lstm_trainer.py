"""
ml_engine/models/lstm_trainer.py
──────────────────────────────────
LSTM Training Pipeline.

Handles:
  - Loading data from the pipeline
  - Building feature vectors + sequences
  - Time-aware train/val/test split (no data leakage)
  - Class imbalance handling (UP/DOWN/NEUTRAL often unequal)
  - Early stopping + learning rate scheduling
  - Model comparison (only saves if improved)
  - Training metrics export to JSONL log

Usage:
  # Full train from scratch
  python -m ml_engine.models.lstm_trainer --symbol BTC/USDT --timeframe 1h

  # Retrain with latest data
  python -m ml_engine.models.lstm_trainer --symbol BTC/USDT --timeframe 1h --retrain
"""

import argparse
import json
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from ml_engine.data.pipeline import DataPipeline
from ml_engine.features.feature_builder import FeatureBuilder
from ml_engine.models.lstm_model import LSTMModel

logger = logging.getLogger(__name__)

TRAINING_LOG = Path(__file__).parent.parent / "data" / "store" / "training_log.jsonl"
TRAINING_LOG.parent.mkdir(parents=True, exist_ok=True)


class LSTMTrainer:
    """
    Complete LSTM training pipeline with walk-forward evaluation.
    CPU-optimized with configurable batch sizes.
    """

    # Training config (CPU-optimized defaults)
    BATCH_SIZE        = 32     # Small batches for CPU
    MAX_EPOCHS        = 50
    EARLY_STOP_PATIENCE = 10
    VALIDATION_SPLIT  = 0.15   # 15% val
    TEST_SPLIT        = 0.10   # 10% test (true holdout)
    MIN_ACCURACY_GATE = 0.54   # Don't save if accuracy < this

    def __init__(self, symbol: str = "BTC/USDT", timeframe: str = "1h"):
        self.symbol    = symbol
        self.timeframe = timeframe
        self.pipeline  = DataPipeline()
        self.fb        = FeatureBuilder()

    def train(self, retrain: bool = False) -> Dict:
        """
        Full training pipeline.
        
        Args:
            retrain: If True, retrain even if a model exists
        
        Returns:
            Training report dict
        """
        start = time.time()
        logger.info(f"\n{'='*60}")
        logger.info(f"[Trainer] Starting LSTM training: {self.symbol} {self.timeframe}")
        logger.info(f"{'='*60}")

        # 1. Load raw data
        df_raw = self.pipeline.get_training_data(self.symbol, self.timeframe)
        logger.info(f"[Trainer] Raw data: {len(df_raw):,} bars")

        if len(df_raw) < 500:
            return self._fail_report("Insufficient data (need 500+ bars)")

        # 2. Build features
        df_feat = self.fb.build_dataset(df_raw, dropna=True)
        feature_names = self.fb.get_feature_columns(df_feat)
        logger.info(f"[Trainer] Feature matrix: {len(df_feat):,} bars × {len(feature_names)} features")

        # 3. Generate labels
        labels = LSTMModel.generate_labels(df_feat, horizon=4)
        df_feat["label"] = labels
        df_feat = df_feat.dropna(subset=["label"])
        df_feat["label"] = df_feat["label"].astype(int)

        # 4. Scale features (fit on train set only — no leakage)
        X_all = df_feat[feature_names].values.astype(np.float32)
        y_all = df_feat["label"].values.astype(np.int32)

        n_total = len(X_all)
        n_test  = max(60, int(n_total * self.TEST_SPLIT))
        n_val   = max(60, int(n_total * self.VALIDATION_SPLIT))
        n_train = n_total - n_val - n_test

        if n_train < 500:
            return self._fail_report(f"Not enough training bars after split: {n_train}")

        # Time-aware split (no shuffling)
        X_train_raw = X_all[:n_train]
        X_val_raw   = X_all[n_train: n_train + n_val]
        X_test_raw  = X_all[n_train + n_val:]

        y_train = y_all[:n_train]
        y_val   = y_all[n_train: n_train + n_val]
        y_test  = y_all[n_train + n_val:]

        logger.info(f"[Trainer] Split: train={n_train:,} | val={n_val:,} | test={n_test:,}")

        # 5. Fit scaler on train only
        from sklearn.preprocessing import StandardScaler
        scaler = StandardScaler()
        X_train_scaled = scaler.fit_transform(X_train_raw).astype(np.float32)
        X_val_scaled   = scaler.transform(X_val_raw).astype(np.float32)
        X_test_scaled  = scaler.transform(X_test_raw).astype(np.float32)

        # 6. Build sequences (sliding window of 60 bars)
        SEQ = LSTMModel.SEQUENCE_LENGTH
        X_train_seq, y_train_seq = self._make_sequences(X_train_scaled, y_train, SEQ)
        X_val_seq,   y_val_seq   = self._make_sequences(X_val_scaled,   y_val,   SEQ)
        X_test_seq,  y_test_seq  = self._make_sequences(X_test_scaled,  y_test,  SEQ)

        logger.info(f"[Trainer] Sequences: train={len(X_train_seq):,} | val={len(X_val_seq):,} | test={len(X_test_seq):,}")

        # 7. Class weights (handle UP/DOWN/NEUTRAL imbalance)
        class_weights = self._compute_class_weights(y_train_seq)
        logger.info(f"[Trainer] Class weights: {class_weights}")

        # 8. Build and train model
        model = LSTMModel(n_features=len(feature_names), symbol=self.symbol, timeframe=self.timeframe)
        model.build()
        model._scaler       = scaler
        model._feature_names = feature_names

        history = self._fit(model, X_train_seq, y_train_seq, X_val_seq, y_val_seq, class_weights)

        # 9. Evaluate on holdout test set
        test_metrics = self._evaluate(model, X_test_seq, y_test_seq)
        logger.info(f"[Trainer] Test metrics: {test_metrics}")

        # 10. Compare with existing model
        existing_acc = 0.0
        if LSTMModel.exists(self.symbol, self.timeframe) and not retrain:
            try:
                existing = LSTMModel.load(LSTMModel.get_save_path(self.symbol, self.timeframe))
                existing_probs = existing._model.predict(X_test_seq, verbose=0)
                existing_preds = np.argmax(existing_probs, axis=1)
                existing_acc = float(np.mean(existing_preds == y_test_seq))
                logger.info(f"[Trainer] Existing model test accuracy: {existing_acc:.4f}")
            except Exception as e:
                logger.warning(f"[Trainer] Could not load existing model: {e}")

        new_acc = test_metrics["accuracy"]
        model._val_accuracy = new_acc
        model._trained_on   = n_train

        # 11. Save if improved or no existing model
        saved = False
        if new_acc > max(existing_acc, self.MIN_ACCURACY_GATE):
            save_path = model.save()
            saved = True
            logger.info(f"[Trainer] ✅ Model saved: {existing_acc:.4f} → {new_acc:.4f}")
        else:
            logger.info(f"[Trainer] ⏭ Keeping old model ({existing_acc:.4f} >= {new_acc:.4f})")

        elapsed = round(time.time() - start, 1)
        report = {
            "timestamp":       datetime.now(timezone.utc).isoformat(),
            "symbol":          self.symbol,
            "timeframe":       self.timeframe,
            "train_bars":      n_train,
            "val_bars":        n_val,
            "test_bars":       n_test,
            "n_features":      len(feature_names),
            "epochs_run":      len(history.get("loss", [])),
            "final_val_loss":  round(min(history.get("val_loss", [99.0])), 4),
            "test_accuracy":   round(new_acc, 4),
            "test_precision":  test_metrics.get("precision", 0.0),
            "test_recall":     test_metrics.get("recall", 0.0),
            "old_accuracy":    round(existing_acc, 4),
            "model_saved":     saved,
            "elapsed_seconds": elapsed,
            "status":          "success",
        }

        self._log_training(report)
        logger.info(f"\n[Trainer] Done in {elapsed}s — accuracy={new_acc:.4f}")
        return report

    def _make_sequences(
        self,
        X: np.ndarray,
        y: np.ndarray,
        seq_len: int,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Convert flat array to overlapping sequences."""
        Xs, ys = [], []
        for i in range(seq_len, len(X)):
            Xs.append(X[i - seq_len: i])
            ys.append(y[i])
        return np.array(Xs, dtype=np.float32), np.array(ys, dtype=np.int32)

    def _compute_class_weights(self, y: np.ndarray) -> Dict:
        """Inverse frequency class weighting."""
        from sklearn.utils.class_weight import compute_class_weight
        classes = np.unique(y)
        weights = compute_class_weight("balanced", classes=classes, y=y)
        return {int(cls): float(w) for cls, w in zip(classes, weights)}

    def _fit(
        self,
        model: LSTMModel,
        X_train: np.ndarray,
        y_train: np.ndarray,
        X_val: np.ndarray,
        y_val: np.ndarray,
        class_weights: Dict,
    ) -> Dict:
        """Run the Keras training loop."""
        from tensorflow.keras.callbacks import (
            EarlyStopping, ReduceLROnPlateau, ModelCheckpoint
        )

        callbacks = [
            EarlyStopping(
                monitor="val_accuracy",
                patience=self.EARLY_STOP_PATIENCE,
                restore_best_weights=True,
                verbose=1,
            ),
            ReduceLROnPlateau(
                monitor="val_loss",
                factor=0.5,
                patience=5,
                min_lr=1e-6,
                verbose=1,
            ),
        ]

        hist = model._model.fit(
            X_train, y_train,
            validation_data=(X_val, y_val),
            epochs=self.MAX_EPOCHS,
            batch_size=self.BATCH_SIZE,
            class_weight=class_weights,
            callbacks=callbacks,
            verbose=1,
        )

        return {
            "loss":     hist.history.get("loss", []),
            "val_loss": hist.history.get("val_loss", []),
            "accuracy": hist.history.get("accuracy", []),
            "val_accuracy": hist.history.get("val_accuracy", []),
        }

    def _evaluate(self, model: LSTMModel, X_test: np.ndarray, y_test: np.ndarray) -> Dict:
        """Evaluate model on test set."""
        from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score

        probs = model._model.predict(X_test, verbose=0)
        preds = np.argmax(probs, axis=1)

        return {
            "accuracy":  round(float(accuracy_score(y_test, preds)), 4),
            "precision": round(float(precision_score(y_test, preds, average="macro", zero_division=0)), 4),
            "recall":    round(float(recall_score(y_test, preds, average="macro", zero_division=0)), 4),
            "f1":        round(float(f1_score(y_test, preds, average="macro", zero_division=0)), 4),
        }

    def _fail_report(self, reason: str) -> Dict:
        logger.error(f"[Trainer] Training failed: {reason}")
        return {
            "status":    "failed",
            "reason":    reason,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "symbol":    self.symbol,
            "timeframe": self.timeframe,
        }

    def _log_training(self, report: Dict):
        """Append training report to JSONL log."""
        try:
            with open(TRAINING_LOG, "a") as f:
                f.write(json.dumps(report) + "\n")
        except Exception as e:
            logger.warning(f"[Trainer] Could not write training log: {e}")


# ─── CLI ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
        stream=sys.stdout,
    )

    parser = argparse.ArgumentParser(description="Train LSTM model for crypto direction prediction")
    parser.add_argument("--symbol",    default="BTC/USDT", help="Trading pair (e.g. BTC/USDT)")
    parser.add_argument("--timeframe", default="1h",       help="Candle timeframe (e.g. 1h, 4h)")
    parser.add_argument("--retrain",   action="store_true", help="Force retrain even if model exists")
    parser.add_argument("--all",       action="store_true", help="Train all symbols: BTC, ETH, SOL")
    args = parser.parse_args()

    if args.all:
        for sym in ["BTC/USDT", "ETH/USDT", "SOL/USDT"]:
            for tf in ["1h", "4h"]:
                t = LSTMTrainer(symbol=sym, timeframe=tf)
                report = t.train(retrain=args.retrain)
                print(json.dumps(report, indent=2))
    else:
        trainer = LSTMTrainer(symbol=args.symbol, timeframe=args.timeframe)
        report  = trainer.train(retrain=args.retrain)
        print("\n" + json.dumps(report, indent=2))
