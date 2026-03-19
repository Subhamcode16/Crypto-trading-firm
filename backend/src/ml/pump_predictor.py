#!/usr/bin/env python3
"""
ML Pump Predictor — XGBoost-based pump probability model.
Predicts the probability (0.0–1.0) that a token will pump >50% in 30 minutes.

Cold Start Strategy:
- Weeks 1-2: Returns rule-based heuristic score (from PDF formula)
- Week 3+ : Uses trained XGBoost model on actual trade outcomes
- Weekly: Agent 9 triggers trainer.py to retrain with new data

Integration point: Called from Agent 5 (Signal Aggregator) in aggregate_signal()
"""

import os
import json
import logging
import pickle
from typing import Dict, Optional

logger = logging.getLogger('pump_predictor')

MODEL_PATH = os.path.join(os.path.dirname(__file__), 'models', 'pump_model.pkl')
MIN_TRADES_FOR_ML = 50  # Minimum trades needed before switching from heuristic to ML


class PumpPredictor:
    """
    Main inference class for the pump probability model.
    
    Modes:
    1. HEURISTIC (cold start, < 50 trades): Uses the PDF signal formula directly
    2. ML (production): Uses trained XGBoost model from pump_model.pkl
    """

    def __init__(self):
        self.model = None
        self.feature_names = None
        self.mode = 'heuristic'
        self._load_model()

    def _load_model(self):
        """Load the trained model if it exists."""
        if os.path.exists(MODEL_PATH):
            try:
                with open(MODEL_PATH, 'rb') as f:
                    saved = pickle.load(f)
                    self.model = saved.get('model')
                    self.feature_names = saved.get('feature_names')
                    trade_count = saved.get('trained_on', 0)

                if trade_count >= MIN_TRADES_FOR_ML:
                    self.mode = 'ml'
                    logger.info(f"[ML] Loaded XGBoost model (trained on {trade_count} trades) → ML mode")
                else:
                    self.mode = 'heuristic'
                    logger.info(f"[ML] Model has {trade_count}/{MIN_TRADES_FOR_ML} trades → Heuristic mode")
            except Exception as e:
                logger.warning(f"[ML] Model load failed: {e} → Heuristic mode")
        else:
            logger.info("[ML] No model file found → Heuristic mode (cold start)")

    def predict(self, features: Dict) -> float:
        """
        Predict pump probability for a token.

        Args:
            features: Feature dict from FeatureBuilder.build()

        Returns:
            float: Probability 0.0–1.0 that token will pump > 50% in 30min
        """
        if self.mode == 'ml' and self.model is not None:
            return self._predict_ml(features)
        else:
            return self._predict_heuristic(features)

    def _predict_heuristic(self, features: Dict) -> float:
        """
        Cold-start heuristic: Directly apply the signal formula from the research PDF.
        
        PDF formula: signal_score = social * 0.3 + liquidity * 0.4 + smart_money * 0.3
        We also add pump.fun and safety bonuses on top.
        """
        social_score      = features.get('social_score', 0.0)
        liquidity_score   = features.get('liquidity_score', 0.0)
        smart_money_score = features.get('smart_money_score', 0.0)

        # Base score from PDF formula
        base = (social_score * 0.3) + (liquidity_score * 0.4) + (smart_money_score * 0.3)

        # Bonuses for high-confidence signals
        if features.get('is_priority_signal', 0):
            base += 0.20    # Smart money webhook = strong signal
        if features.get('safety_cleared', 0):
            base += 0.10    # Passed all safety filters
        if features.get('pumpfun_bonding_curve_pct', 0) >= 50:
            base += 0.15    # Bonding curve past midpoint
        if features.get('narrative_bonus_awarded', 0):
            base += 0.08    # Narrative alignment
        if features.get('copy_trade_detected', 0):
            base += 0.07    # Copy-trade signal

        prob = max(0.0, min(1.0, base))
        logger.debug(f"[ML] Heuristic pump_prob: {prob:.3f} (social={social_score:.2f}, liq={liquidity_score:.2f}, smart={smart_money_score:.2f})")
        return prob

    def _predict_ml(self, features: Dict) -> float:
        """Use trained XGBoost model for inference."""
        try:
            X = self._build_input(features)
            prob = float(self.model.predict_proba([X])[0][1])
            logger.debug(f"[ML] XGBoost pump_prob: {prob:.3f}")
            return prob
        except Exception as e:
            logger.error(f"[ML] XGBoost inference failed: {e} → falling back to heuristic")
            return self._predict_heuristic(features)

    def _build_input(self, features: Dict) -> list:
        """Build ordered input vector for the model, aligning with stored feature_names."""
        if self.feature_names:
            return [features.get(name, 0.0) for name in self.feature_names]
        return [v for k, v in features.items() if not k.startswith('_')]

    def get_mode(self) -> str:
        """Return current prediction mode: 'ml' or 'heuristic'."""
        return self.mode


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    predictor = PumpPredictor()
    
    # Test with a mock high-confidence feature set
    mock_features = {
        'social_score': 0.7,
        'liquidity_score': 0.8,
        'smart_money_score': 0.9,
        'is_priority_signal': 1.0,
        'safety_cleared': 1.0,
        'pumpfun_bonding_curve_pct': 65.0,
        'narrative_bonus_awarded': 1.0,
        'copy_trade_detected': 0.0,
    }
    
    prob = predictor.predict(mock_features)
    print(f"\n[TEST] pump_prob = {prob:.3f} (mode: {predictor.get_mode()})")
    print(f"[TEST] Trade threshold: {'EXECUTE ✅' if prob > 0.75 else 'SKIP ❌'}")
