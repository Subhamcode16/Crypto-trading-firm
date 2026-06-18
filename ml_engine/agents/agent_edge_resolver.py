"""
ml_engine/agents/agent_edge_resolver.py
─────────────────────────────────────────
LLM Agent B — Edge Case Resolver.

Model: Gemini 2.5 Pro (powerful, used sparingly — ~$0.02/call)
Trigger: Called ONLY when ML models disagree with each other.
Role: Resolve conflicting signals using deep market reasoning.

Triggers when:
  - LSTM says UP but XGB says STRONG_SHORT (or vice versa)
  - RL agent contradicts both LSTM and XGB
  - ensemble_score is in the "grey zone" (0.55-0.65) with disagreement

Context:
  - Full feature explanation (most important features and their values)
  - What each model is saying and why
  - Historical similar patterns from the past 30 days

Expected frequency: 1-3 times per week (NOT per day)
"""

import asyncio
import json
import logging
import os
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

MAX_CALLS_PER_DAY = 5   # Very strict limit — Gemini Pro is expensive


class EdgeResolverAgent:
    """
    Gemini Pro agent for resolving edge cases where ML models disagree.
    Invoked sparingly, designed for deep analysis.
    """

    SYSTEM_PROMPT = """You are an expert quantitative analyst reviewing conflicting signals from multiple ML trading models.

You will receive:
1. Conflicting signals from LSTM (sequence model) and XGBoost (pattern classifier)
2. The key features driving each model's prediction
3. Current market context

Your task: Determine which model's signal is likely correct and provide a FINAL decision.

Consider:
- Is the LSTM capturing a trend that XGBoost's pattern-based approach is missing?
- Is XGBoost seeing a specific reversal pattern the LSTM trend hasn't processed yet?
- What is the dominant regime? (trending = trust LSTM; ranging = trust XGBoost)
- Does the RL agent's experience-based action add clarity?

Respond ONLY with valid JSON:
{
  "final_decision": "LONG" | "SHORT" | "STAY_FLAT",
  "trust_model": "LSTM" | "XGB" | "RL" | "NONE",
  "confidence": float (0.5-1.0),
  "reasoning": "2-3 sentence explanation",
  "edge_type": "TREND_VS_REVERSAL" | "REGIME_MISMATCH" | "VOLUME_DIVERGENCE" | "OTHER"
}"""

    def __init__(self):
        self._calls_today   = 0
        self._last_reset    = datetime.now(timezone.utc).date()
        self._client        = None
        self._call_log: List[Dict] = []
        self._init_client()

    def _init_client(self):
        """Initialize Gemini Pro client."""
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            logger.warning("[EdgeResolver] GEMINI_API_KEY not set")
            return

        try:
            import google.generativeai as genai
            genai.configure(api_key=api_key)
            self._client = genai.GenerativeModel(
                model_name="gemini-2.5-pro",
                generation_config={
                    "temperature": 0.2,
                    "max_output_tokens": 500,
                },
            )
            logger.info("[EdgeResolver] ✅ Gemini Pro initialized")
        except ImportError:
            logger.warning("[EdgeResolver] google-generativeai not installed")
        except Exception as e:
            logger.error(f"[EdgeResolver] Init failed: {e}")

    def _check_daily_limit(self) -> bool:
        """Reset counter daily and check if limit reached."""
        today = datetime.now(timezone.utc).date()
        if today != self._last_reset:
            self._calls_today = 0
            self._last_reset  = today
        return self._calls_today < MAX_CALLS_PER_DAY

    def _build_prompt(
        self,
        symbol:       str,
        lstm_result:  Dict,
        xgb_result:   Dict,
        rl_action:    Dict,
        top_features: Dict,
        regime:       str,
    ) -> str:
        """Build detailed analysis prompt."""
        lstm_signal = lstm_result.get("signal", "UNCERTAIN")
        lstm_conf   = lstm_result.get("confidence", 0)
        xgb_signal  = xgb_result.get("signal", "NO_SIGNAL")
        xgb_conf    = xgb_result.get("confidence", 0)
        rl_act      = rl_action.get("action", "HOLD")
        rl_conf     = rl_action.get("confidence", 0)

        # Top 10 most important features for context
        feat_str = "\n".join([f"  {k}: {v:.4f}" for k, v in list(top_features.items())[:10]])

        return f"""EDGE CASE RESOLUTION REQUEST:

Symbol: {symbol}
Market Regime: {regime}

MODEL SIGNALS (CONFLICTING):
  • LSTM Sequence Model: {lstm_signal} (confidence: {lstm_conf:.1%})
    - UP probability:  {lstm_result.get('up', 0):.1%}
    - DOWN probability: {lstm_result.get('down', 0):.1%}
  
  • XGBoost Pattern Classifier: {xgb_signal} (confidence: {xgb_conf:.1%})
    - Raw probs: {json.dumps(xgb_result.get('raw_probs', {}), indent=0)}
  
  • RL Policy Agent: {rl_act} (confidence: {rl_conf:.1%})

TOP DRIVING FEATURES:
{feat_str}

What is the correct trading decision for {symbol}?"""

    async def resolve(
        self,
        symbol:       str,
        lstm_result:  Dict,
        xgb_result:   Dict,
        rl_action:    Dict,
        features:     Dict,
        regime:       str = "ranging",
    ) -> Dict:
        """
        Resolve conflicting model signals.
        
        Returns:
            {
              "final_decision":  "LONG" | "SHORT" | "STAY_FLAT",
              "trust_model":     str,
              "confidence":      float,
              "reasoning":       str,
              "edge_type":       str,
              "source":          str,
            }
        """
        default_result = {
            "final_decision": "STAY_FLAT",
            "trust_model":    "NONE",
            "confidence":     0.5,
            "reasoning":      "Model disagreement unresolved — staying flat is safest",
            "edge_type":      "OTHER",
            "source":         "fallback",
        }

        if self._client is None:
            return default_result

        if not self._check_daily_limit():
            logger.warning(f"[EdgeResolver] Daily limit ({MAX_CALLS_PER_DAY}) reached")
            return {**default_result, "source": "daily_limit"}

        # Get top features (most informative for the resolver)
        top_features = {k: v for k, v in features.items()
                       if not k.startswith("_") and isinstance(v, (int, float))}
        # Sort by absolute value to get most extreme features
        top_features = dict(sorted(top_features.items(),
                                   key=lambda x: abs(x[1]),
                                   reverse=True)[:15])

        prompt = self._build_prompt(
            symbol, lstm_result, xgb_result, rl_action, top_features, regime
        )

        try:
            self._calls_today += 1
            response = await asyncio.to_thread(
                self._client.generate_content,
                f"{self.SYSTEM_PROMPT}\n\n{prompt}",
            )

            raw_text = response.text.strip()
            if "```json" in raw_text:
                raw_text = raw_text.split("```json")[1].split("```")[0].strip()
            elif "```" in raw_text:
                raw_text = raw_text.split("```")[1].split("```")[0].strip()

            result = json.loads(raw_text)
            result["source"] = "gemini_pro"

            # Log for audit trail
            self._call_log.append({
                "timestamp":       datetime.now(timezone.utc).isoformat(),
                "symbol":          symbol,
                "lstm_signal":     lstm_result.get("signal"),
                "xgb_signal":      xgb_result.get("signal"),
                "final_decision":  result.get("final_decision"),
                "edge_type":       result.get("edge_type"),
            })

            logger.info(
                f"[EdgeResolver] 🔬 {symbol}: {result.get('final_decision')} "
                f"(trust {result.get('trust_model')}) — {result.get('edge_type')}"
            )
            return result

        except json.JSONDecodeError as e:
            logger.error(f"[EdgeResolver] JSON parse error: {e}")
            return {**default_result, "source": "json_error"}
        except Exception as e:
            logger.error(f"[EdgeResolver] API error: {e}")
            return {**default_result, "source": "api_error"}

    def get_call_summary(self) -> Dict:
        """Return usage statistics."""
        return {
            "calls_today":  self._calls_today,
            "daily_limit":  MAX_CALLS_PER_DAY,
            "recent_calls": self._call_log[-5:] if self._call_log else [],
        }
