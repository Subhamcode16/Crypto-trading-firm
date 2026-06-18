"""
ml_engine/models/lstm_model.py
───────────────────────────────
LSTM Sequence Model for price direction prediction.

Architecture:
  - Input: 60-bar lookback window of ~120 normalized features
  - LSTM(128) → Dropout(0.2) → LSTM(64) → Dropout(0.2) → Dense(32) → Dense(3, softmax)
  - Output: [P_UP, P_DOWN, P_NEUTRAL] probabilities

Usage:
  # Inference (production)
  model = LSTMModel.load("ml_engine/models/saved/lstm_btcusdt_1h.h5")
  probs = model.predict(feature_sequence_60bars)  # → {"up": 0.67, "down": 0.18, "neutral": 0.15}
  
  # Training is in lstm_trainer.py
"""

import logging
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

SAVED_DIR = Path(__file__).parent / "saved"
SAVED_DIR.mkdir(parents=True, exist_ok=True)

# Label mapping
LABEL_NAMES  = ["neutral", "up", "down"]
LABEL_UP     = 1
LABEL_DOWN   = 2
LABEL_NEUTRAL = 0

# Thresholds for labeling
UP_THRESHOLD   = 0.01    # >1% gain in next 4h = UP
DOWN_THRESHOLD = -0.01   # >1% loss in next 4h = DOWN


class LSTMModel:
    """
    LSTM sequence model for crypto price direction prediction.
    
    Wraps TensorFlow/Keras model with:
    - Automatic fallback to CPU if GPU unavailable
    - Scaler state persistence (for inference parity)
    - Confidence thresholding
    """

    SEQUENCE_LENGTH = 60     # 60-bar lookback window
    CONFIDENCE_THRESHOLD = 0.55   # Minimum confidence to issue signal

    def __init__(self, n_features: int, symbol: str = "BTC/USDT", timeframe: str = "1h"):
        self.n_features = n_features
        self.symbol     = symbol
        self.timeframe  = timeframe
        self._model     = None
        self._scaler    = None
        self._feature_names: List[str] = []
        self._trained_on: int = 0
        self._val_accuracy: float = 0.0

    def build(self) -> "LSTMModel":
        """Construct the Keras model architecture."""
        try:
            import tensorflow as tf
            from tensorflow.keras.models import Sequential
            from tensorflow.keras.layers import LSTM, Dense, Dropout, BatchNormalization
            from tensorflow.keras.regularizers import l2

            # Suppress TF info logs
            os.environ["TF_CPP_MIN_LOG_LEVEL"] = "2"
            tf.get_logger().setLevel("ERROR")

            logger.info(f"[LSTM] Building model | features={self.n_features} | seq={self.SEQUENCE_LENGTH}")

            model = Sequential([
                LSTM(128, return_sequences=True,
                     input_shape=(self.SEQUENCE_LENGTH, self.n_features),
                     kernel_regularizer=l2(1e-4),
                     recurrent_regularizer=l2(1e-4)),
                Dropout(0.2),
                BatchNormalization(),

                LSTM(64, return_sequences=False,
                     kernel_regularizer=l2(1e-4)),
                Dropout(0.2),
                BatchNormalization(),

                Dense(32, activation="relu", kernel_regularizer=l2(1e-4)),
                Dropout(0.1),

                Dense(3, activation="softmax"),   # [NEUTRAL, UP, DOWN]
            ], name=f"lstm_{self.symbol.replace('/', '_')}_{self.timeframe}")

            model.compile(
                optimizer="adam",
                loss="sparse_categorical_crossentropy",
                metrics=["accuracy"],
            )

            self._model = model
            logger.info(f"[LSTM] Model built: {model.count_params():,} parameters")
            return self

        except ImportError:
            raise RuntimeError(
                "TensorFlow is required for LSTM. Install with: pip install tensorflow>=2.15.0\n"
                "For Colab training: open notebooks/train_lstm_colab.ipynb"
            )

    def predict(self, sequence: np.ndarray) -> Dict[str, float]:
        """
        Predict price direction from a 60-bar feature sequence.
        
        Args:
            sequence: np.ndarray of shape (60, n_features) — already scaled
                      OR (1, 60, n_features)
        
        Returns:
            {
              "up":      float (0.0-1.0),
              "down":    float (0.0-1.0),
              "neutral": float (0.0-1.0),
              "signal":  "UP" | "DOWN" | "NEUTRAL" | "UNCERTAIN",
              "confidence": float
            }
        """
        if self._model is None:
            raise RuntimeError("Model not loaded. Call load() first.")

        # Shape: (1, 60, n_features)
        if sequence.ndim == 2:
            sequence = sequence[np.newaxis, :, :]

        probs = self._model.predict(sequence, verbose=0)[0]
        p_neutral, p_up, p_down = float(probs[0]), float(probs[1]), float(probs[2])

        max_prob = max(p_up, p_down, p_neutral)
        if max_prob < self.CONFIDENCE_THRESHOLD:
            signal = "UNCERTAIN"
        elif p_up == max_prob:
            signal = "UP"
        elif p_down == max_prob:
            signal = "DOWN"
        else:
            signal = "NEUTRAL"

        return {
            "up":         p_up,
            "down":       p_down,
            "neutral":    p_neutral,
            "signal":     signal,
            "confidence": max_prob,
        }

    def predict_batch(self, sequences: np.ndarray) -> List[Dict]:
        """Predict for multiple sequences at once (faster for backtesting)."""
        if self._model is None:
            raise RuntimeError("Model not loaded.")

        if sequences.ndim == 2:
            sequences = sequences[np.newaxis, :, :]

        all_probs = self._model.predict(sequences, verbose=0)
        results = []
        for probs in all_probs:
            p_neutral, p_up, p_down = float(probs[0]), float(probs[1]), float(probs[2])
            max_prob = max(p_up, p_down, p_neutral)
            signal = "UNCERTAIN"
            if max_prob >= self.CONFIDENCE_THRESHOLD:
                if p_up == max_prob:
                    signal = "UP"
                elif p_down == max_prob:
                    signal = "DOWN"
                else:
                    signal = "NEUTRAL"
            results.append({
                "up": p_up, "down": p_down, "neutral": p_neutral,
                "signal": signal, "confidence": max_prob
            })
        return results

    def get_sequence(
        self,
        feature_df: pd.DataFrame,
        feature_names: List[str],
        idx: int,
    ) -> Optional[np.ndarray]:
        """
        Extract a 60-bar lookback sequence ending at index idx.
        Returns None if insufficient history.
        """
        if idx < self.SEQUENCE_LENGTH:
            return None
        window = feature_df.iloc[idx - self.SEQUENCE_LENGTH: idx][feature_names].values
        if self._scaler is not None:
            window = self._scaler.transform(window)
        return window.astype(np.float32)

    # ─── Persistence ──────────────────────────────────────────────────────

    def save(self, path: Optional[str] = None) -> str:
        """Save model weights + scaler + metadata to disk."""
        import pickle, json

        if path is None:
            name = f"lstm_{self.symbol.replace('/','_')}_{self.timeframe}"
            path = str(SAVED_DIR / name)

        Path(path).mkdir(parents=True, exist_ok=True)

        # Save Keras model
        model_path = os.path.join(path, "model.h5")
        self._model.save(model_path)

        # Save scaler
        if self._scaler is not None:
            with open(os.path.join(path, "scaler.pkl"), "wb") as f:
                pickle.dump(self._scaler, f)

        # Save metadata
        meta = {
            "n_features":     self.n_features,
            "symbol":         self.symbol,
            "timeframe":      self.timeframe,
            "feature_names":  self._feature_names,
            "trained_on":     self._trained_on,
            "val_accuracy":   self._val_accuracy,
            "sequence_length": self.SEQUENCE_LENGTH,
        }
        with open(os.path.join(path, "metadata.json"), "w") as f:
            json.dump(meta, f, indent=2)

        logger.info(f"[LSTM] Model saved to {path} (val_acc={self._val_accuracy:.4f})")
        return path

    @classmethod
    def load(cls, path: str) -> "LSTMModel":
        """Load model from saved directory."""
        import pickle, json
        from tensorflow.keras.models import load_model

        with open(os.path.join(path, "metadata.json")) as f:
            meta = json.load(f)

        instance = cls(
            n_features=meta["n_features"],
            symbol=meta["symbol"],
            timeframe=meta["timeframe"],
        )
        instance._feature_names = meta.get("feature_names", [])
        instance._trained_on    = meta.get("trained_on", 0)
        instance._val_accuracy  = meta.get("val_accuracy", 0.0)

        instance._model = load_model(os.path.join(path, "model.h5"))

        scaler_path = os.path.join(path, "scaler.pkl")
        if os.path.exists(scaler_path):
            with open(scaler_path, "rb") as f:
                instance._scaler = pickle.load(f)

        logger.info(f"[LSTM] Loaded: {meta['symbol']} {meta['timeframe']} "
                    f"(val_acc={instance._val_accuracy:.4f}, "
                    f"trained on {instance._trained_on:,} bars)")
        return instance

    @staticmethod
    def get_save_path(symbol: str, timeframe: str) -> str:
        """Get the standard save path for a symbol/timeframe."""
        name = f"lstm_{symbol.replace('/', '_')}_{timeframe}"
        return str(SAVED_DIR / name)

    @staticmethod
    def exists(symbol: str, timeframe: str) -> bool:
        """Check if a trained model exists for the given symbol/timeframe."""
        path = LSTMModel.get_save_path(symbol, timeframe)
        return os.path.isfile(os.path.join(path, "model.h5"))

    # ─── Label Generation ─────────────────────────────────────────────────

    @staticmethod
    def generate_labels(
        df: pd.DataFrame,
        horizon: int = 4,
        up_threshold: float = UP_THRESHOLD,
        down_threshold: float = DOWN_THRESHOLD,
    ) -> pd.Series:
        """
        Generate direction labels for training.
        
        Args:
            df:           DataFrame with 'close' column
            horizon:      Number of bars to look ahead (default=4 bars)
            up_threshold: % gain required for UP label
            down_threshold: % loss required for DOWN label
        
        Returns:
            Series of labels: 0=NEUTRAL, 1=UP, 2=DOWN
        """
        future_return = df["close"].shift(-horizon) / df["close"] - 1

        labels = pd.Series(LABEL_NEUTRAL, index=df.index)
        labels[future_return > up_threshold]    = LABEL_UP
        labels[future_return < down_threshold]  = LABEL_DOWN

        # NaN for last `horizon` bars (no future data)
        labels.iloc[-horizon:] = np.nan

        label_counts = labels.value_counts()
        logger.info(f"[LSTM] Labels — UP: {label_counts.get(1, 0)}, "
                    f"DOWN: {label_counts.get(2, 0)}, "
                    f"NEUTRAL: {label_counts.get(0, 0)}")
        return labels
