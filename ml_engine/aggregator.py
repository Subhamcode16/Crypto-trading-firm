"""
ml_engine/aggregator.py
────────────────────────
Signal Aggregator — combines LSTM + XGBoost + RL into one ensemble signal.

Ensemble weights:
  LSTM:  35%  (sequence-based direction probability)
  XGB:   35%  (pattern strength classifier)
  RL:    30%  (policy action confidence)

Regime Gate:
  Queries LLM Agent A (Gemini Flash) to assess macro regime.
  Blocks ALL trades during "extreme_bear" regimes.

Usage:
  aggregator = SignalAggregator()
  result = await aggregator.aggregate(
      symbol="BTC/USDT",
      features=feature_dict,         # from FeatureBuilder
      lstm_result=lstm_probs,        # from LSTMModel.predict()
      xgb_result=xgb_signal,        # from XGBModel.predict()
      rl_action=rl_action_dict,      # from RLAgent.predict()
      macro_context=macro_dict,      # optional
  )
"""

import logging
from datetime import datetime, timezone
from typing import Dict, Optional
import pandas as pd

from ml_engine.features.kill_switch import KillSwitch
from ml_engine.features.regime_detector import RegimeDetector

logger = logging.getLogger(__name__)

# Ensemble weights (must sum to 1.0)
LSTM_WEIGHT = 0.35
XGB_WEIGHT  = 0.35
RL_WEIGHT   = 0.30

# Minimum ensemble score to generate a signal
SIGNAL_THRESHOLD  = 0.60   # Directional conviction needed
# Minimum score to issue STRONG signal (passes to LLM gatekeeper)
STRONG_THRESHOLD  = 0.70

# Regime multipliers
REGIME_MULTIPLIERS = {
    "bull":         1.0,
    "ranging":      0.85,   # Reduce conviction in sideways market
    "bear":         0.70,   # Tighten threshold in downtrend
    "extreme_bear": 0.0,    # Block all longs in crash/panic mode
}


class SignalAggregator:
    """
    Ensemble combiner for ML model outputs → final tradeable signal.
    
    Flow:
      1. Compute ensemble score from LSTM + XGB + RL
      2. Apply regime multiplier (from macro context)
      3. Determine final action (BUY/SELL/HOLD/SKIP)
      4. Route strong signals to LLM Gatekeeper
    """

    def __init__(self):
        self._gatekeeper = None   # Lazy-loaded LLM agent
        self.kill_switch = KillSwitch()
        self.regime_detector = RegimeDetector()

    async def aggregate(
        self,
        symbol:        str,
        features:      Dict,
        lstm_result:   Optional[Dict] = None,
        xgb_result:    Optional[Dict] = None,
        rl_action:     Optional[Dict] = None,
        macro_context: Optional[Dict] = None,
        bar_time:      Optional[str]  = None,
        df_1h:         Optional[pd.DataFrame] = None,
        df_4h:         Optional[pd.DataFrame] = None,
        portfolio_state: Optional[Dict] = None,
        trade_ledger:  Optional[list] = None,
        regime_history: Optional[list] = None
    ) -> Dict:
        """
        Combine model outputs into a single trading signal.
        
        Args:
            symbol:       Trading pair (e.g. "BTC/USDT")
            features:     120-dim feature dict from FeatureBuilder
            lstm_result:  {"signal": "UP", "confidence": 0.67, "up": 0.67, ...}
            xgb_result:   {"signal": "STRONG_LONG", "confidence": 0.72, ...}
            rl_action:    {"action": "BUY", "confidence": 0.81, "action_id": 1}
            macro_context: {"regime": "bull", "fear_greed": 55, "btc_dominance": 52}
            bar_time:     ISO timestamp of the bar
            df_1h:        1H OHLCV DataFrame
            df_4h:        4H OHLCV DataFrame
            portfolio_state: Dict representing current portfolio state
            trade_ledger: List of recent trades
        
        Returns:
            {
              "final_action":    "BUY" | "SELL" | "HOLD" | "SKIP",
              "ensemble_score":  float,
              "direction":       "LONG" | "SHORT" | "NEUTRAL",
              "confidence":      float,
              "regime":          str,
              "components":      {"lstm": ..., "xgb": ..., "rl": ...},
              "gatekeeper_check": bool,   # was LLM gatekeeper invoked?
              "gatekeeper_result": str | None,
              "timestamp":       str,
              "signal_strength": "STRONG" | "MODERATE" | "WEAK" | "SKIP",
            }
        """
        timestamp = bar_time or datetime.now(timezone.utc).isoformat()
        
        if portfolio_state is None:
            portfolio_state = {}
            
        # ── Step 0: Kill Switch & Base Regime check ────────────────────────────
        kill_level, kill_reason = 0, "NORMAL"
        if df_1h is not None and df_4h is not None:
            kill_level, kill_reason = self.kill_switch.evaluate(
                df_1h, df_4h, portfolio_state, macro_context or {}, regime_history or []
            )
            
        if kill_level >= 2:
            logger.warning(f"[Aggregator] 🛑 Kill Switch Active for {symbol}: {kill_reason} (Level {kill_level})")
            return {
                "final_action": "SKIP" if kill_level == 2 else "PANIC_CLOSE",
                "direction": "NEUTRAL",
                "ensemble_score": 0.0,
                "confidence": 0.0,
                "signal_strength": "SKIP",
                "regime": "KILL_SWITCH",
                "timestamp": timestamp,
                "kill_reason": kill_reason
            }

        # ── Step 1: Extract individual scores ────────────────────────────
        lstm_score, lstm_dir  = self._score_lstm(lstm_result)
        xgb_score,  xgb_dir  = self._score_xgb(xgb_result)
        rl_score,   rl_dir   = self._score_rl(rl_action)

        # ── Step 2: Compute ensemble ──────────────────────────────────────
        # Direction consensus: weighted majority vote
        long_score  = (
            (lstm_score * LSTM_WEIGHT if lstm_dir == "LONG"  else 0) +
            (xgb_score  * XGB_WEIGHT  if xgb_dir  == "LONG"  else 0) +
            (rl_score   * RL_WEIGHT   if rl_dir   == "LONG"  else 0)
        )
        short_score = (
            (lstm_score * LSTM_WEIGHT if lstm_dir == "SHORT" else 0) +
            (xgb_score  * XGB_WEIGHT  if xgb_dir  == "SHORT" else 0) +
            (rl_score   * RL_WEIGHT   if rl_dir   == "SHORT" else 0)
        )

        if long_score > short_score:
            direction      = "LONG"
            ensemble_score = long_score
        elif short_score > long_score:
            direction      = "SHORT"
            ensemble_score = short_score
        else:
            direction      = "NEUTRAL"
            ensemble_score = 0.0

        # ── Step 3: Apply regime multiplier ──────────────────────────────
        regime = "ranging"
        if macro_context:
            regime = macro_context.get("regime", "ranging").lower()
            
        # Detect true regime using RegimeDetector
        regime_data = {"regime": regime}
        if df_1h is not None and df_4h is not None:
            regime_data = self.regime_detector.detect(df_1h, df_4h, signal_direction=direction)
            regime = regime_data.get("regime", regime)

        # Enforce hard rejects
        if regime in ["VOLATILE_CHOP", "DEAD_RANGE", "COUNTER_TREND_REJECTED"]:
            logger.info(f"[Aggregator] ⛔ Regime Block for {symbol}: {regime}")
            return {
                "final_action": "HOLD",
                "direction": direction,
                "ensemble_score": 0.0,
                "confidence": 0.0,
                "signal_strength": "SKIP",
                "regime": regime,
                "timestamp": timestamp,
            }

        multiplier = REGIME_MULTIPLIERS.get(regime, 0.85)
        # If the regime is highly favorable (TRENDING), give a slight boost
        if regime == "TRENDING":
            multiplier = 1.0
            
        adjusted_score = ensemble_score * multiplier

        # Check for model disagreement (edge case flag)
        directions = [lstm_dir, xgb_dir, rl_dir]
        unique_dirs = set(d for d in directions if d != "NEUTRAL")
        models_disagree = len(unique_dirs) > 1
        
        # Enforce strict consensus rules during AMBIGUOUS regime
        if regime == "AMBIGUOUS" and models_disagree:
            logger.info(f"[Aggregator] ⚠️ Model disagreement during AMBIGUOUS regime for {symbol}. Blocking trade.")
            adjusted_score = 0.0 # Force HOLD

        # ── Step 4: Determine final action ───────────────────────────────
        if multiplier == 0.0:
            # Extreme bear regime — block all longs
            if direction == "SHORT" and adjusted_score > SIGNAL_THRESHOLD:
                final_action    = "SELL"
                signal_strength = "MODERATE"
            else:
                final_action    = "SKIP"
                signal_strength = "SKIP"

        elif adjusted_score < SIGNAL_THRESHOLD:
            final_action    = "HOLD"
            signal_strength = "WEAK"

        elif adjusted_score >= STRONG_THRESHOLD:
            final_action    = "BUY" if direction == "LONG" else "SELL"
            signal_strength = "STRONG"
        else:
            final_action    = "BUY" if direction == "LONG" else "SELL"
            signal_strength = "MODERATE"

        # ── Step 5: LLM Gatekeeper for STRONG signals ─────────────────────
        gatekeeper_check  = False
        gatekeeper_result = None

        if signal_strength == "STRONG" and final_action in ("BUY", "SELL"):
            gatekeeper_check = True
            gk_result = await self._run_gatekeeper(
                symbol=symbol,
                direction=direction,
                ensemble_score=adjusted_score,
                regime=regime,
                macro_context=macro_context,
                features=features,
                portfolio_state=portfolio_state,
                trade_ledger=trade_ledger,
                kill_switch_status=kill_reason,
                models_disagree=models_disagree
            )
            gatekeeper_result = gk_result.get("decision", "APPROVE")
            if gatekeeper_result == "REJECT":
                final_action    = "SKIP"
                signal_strength = "SKIP"

        # ── Step 6: Edge case resolver ────────────────────────────────────
        if models_disagree and signal_strength not in ("SKIP", "WEAK"):
            logger.info(f"[Aggregator] ⚠️ Model disagreement detected for {symbol}: {directions}")
            # Edge resolver is called from the execution engine, not here
            # Just flag it in the result
            pass

        result = {
            "final_action":      final_action,
            "direction":         direction,
            "ensemble_score":    round(adjusted_score, 4),
            "raw_ensemble_score": round(ensemble_score, 4),
            "confidence":        round(adjusted_score, 4),
            "signal_strength":   signal_strength,
            "regime":            regime,
            "regime_multiplier": multiplier,
            "models_disagree":   models_disagree,
            "gatekeeper_check":  gatekeeper_check,
            "gatekeeper_result": gatekeeper_result,
            "timestamp":         timestamp,
            "symbol":            symbol,
            "components": {
                "lstm": {
                    "direction":  lstm_dir,
                    "score":      round(lstm_score, 4),
                    "raw":        lstm_result,
                },
                "xgb": {
                    "direction":  xgb_dir,
                    "score":      round(xgb_score, 4),
                    "raw":        xgb_result,
                },
                "rl": {
                    "direction":  rl_dir,
                    "score":      round(rl_score, 4),
                    "raw":        rl_action,
                },
            },
        }

        icon = {"BUY": "🟢", "SELL": "🔴", "HOLD": "⚪", "SKIP": "⛔"}.get(final_action, "⚪")
        logger.info(
            f"[Aggregator] {icon} {symbol} → {final_action} | "
            f"score={adjusted_score:.3f} | regime={regime} | "
            f"LSTM={lstm_dir}({lstm_score:.2f}) XGB={xgb_dir}({xgb_score:.2f}) RL={rl_dir}({rl_score:.2f})"
        )

        return result

    # ─── Score Extractors ─────────────────────────────────────────────────

    def _score_lstm(self, lstm_result: Optional[Dict]) -> tuple:
        """Extract directional score and direction from LSTM output."""
        if not lstm_result:
            return 0.0, "NEUTRAL"
        signal = lstm_result.get("signal", "NEUTRAL")
        if signal == "UP":
            return float(lstm_result.get("up", 0)), "LONG"
        elif signal == "DOWN":
            return float(lstm_result.get("down", 0)), "SHORT"
        return float(lstm_result.get("neutral", 0.33)), "NEUTRAL"

    def _score_xgb(self, xgb_result: Optional[Dict]) -> tuple:
        """Extract directional score from XGBoost output."""
        if not xgb_result:
            return 0.0, "NEUTRAL"
        signal = xgb_result.get("signal", "NO_SIGNAL")
        conf   = float(xgb_result.get("confidence", 0))
        if signal == "STRONG_LONG":
            return conf, "LONG"
        elif signal == "STRONG_SHORT":
            return conf, "SHORT"
        elif signal == "WEAK":
            return conf * 0.5, "NEUTRAL"
        return 0.0, "NEUTRAL"

    def _score_rl(self, rl_action: Optional[Dict]) -> tuple:
        """Extract directional score from RL policy output."""
        if not rl_action:
            return 0.0, "NEUTRAL"
        action = rl_action.get("action", "HOLD")
        conf   = float(rl_action.get("confidence", 0))
        if action == "BUY":
            return conf, "LONG"
        elif action == "SELL":
            return conf, "SHORT"
        return 0.0, "NEUTRAL"

    # ─── LLM Gatekeeper ───────────────────────────────────────────────────

    async def _run_gatekeeper(
        self,
        symbol:         str,
        direction:      str,
        ensemble_score: float,
        regime:         str,
        macro_context:  Optional[Dict],
        features:       Dict,
        portfolio_state: Optional[Dict] = None,
        trade_ledger:   Optional[list] = None,
        kill_switch_status: str = "NORMAL",
        models_disagree: bool = False
    ) -> Dict:
        """Invoke the Gemini Flash gatekeeper for final signal approval."""
        try:
            from ml_engine.agents.agent_gatekeeper import GatekeeperAgent
            if self._gatekeeper is None:
                self._gatekeeper = GatekeeperAgent()

            return await self._gatekeeper.check(
                symbol=symbol,
                direction=direction,
                ensemble_score=ensemble_score,
                regime=regime,
                macro_context=macro_context or {},
                portfolio_state=portfolio_state or {},
                trade_ledger=trade_ledger or [],
                kill_switch_status=kill_switch_status,
                models_disagree=models_disagree
            )
        except Exception as e:
            logger.error(f"[Aggregator] Gatekeeper failed: {e} — defaulting to APPROVE")
            return {"decision": "APPROVE", "reason": f"gatekeeper_error: {e}"}
