"""
ml_engine/agents/agent_gatekeeper.py
──────────────────────────────────────
LLM Agent A — Final Signal Gatekeeper.

Model: Gemini 2.5 Flash (fast, cheap — ~$0.002/call)
Trigger: Called for every STRONG signal that passes the ML ensemble threshold.
Role: Assess market regime context and approve/reject the signal.

Context it receives:
  - Symbol + direction (LONG/SHORT)
  - Ensemble score (how confident ML is)
  - Current market regime (bull/bear/ranging)
  - Fear & Greed Index
  - BTC dominance
  - Recent 5-trade performance

Output:
  - APPROVE: Signal passes, execute trade
  - REJECT:  Something looks wrong (black swan, macro risk, etc.)

Rate Limits:
  - Max 20 calls/hour (enforced internally)
  - Uses Gemini 2.5 Flash for speed + cost efficiency
"""

import asyncio
import json
import logging
import os
import time
from collections import deque
from datetime import datetime, timezone
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

MAX_CALLS_PER_HOUR = 20
CALL_WINDOW_SECONDS = 3600   # 1 hour window


class GatekeeperAgent:
    """
    Final LLM gatekeeper for ML-generated signals.
    
    Uses Gemini Flash for speed. Designed to catch macro risks and
    unusual market conditions that the ML models may have missed.
    """

    SYSTEM_PROMPT = """You are a disciplined institutional crypto trading risk manager.
Your job is to perform a final sanity check on ML-generated trading signals.

You will be given:
1. A trading signal (LONG or SHORT) for a crypto asset
2. The ML ensemble confidence score (0-1)
3. Current market regime assessment
4. Macro context (Fear & Greed, BTC dominance, etc.)

Your task:
- APPROVE if the signal makes sense given the macro context AND the current portfolio state
- REJECT if there are clear macro red flags (e.g., extreme fear during long signal, BTC flash crash)
- REJECT if the portfolio is taking heavy losses recently (e.g. 3+ consecutive losses) and the signal is weak
- REJECT if the 4H trend directly conflicts with the 1H signal (unless specifically mitigating circumstances exist)

Rules:
- Be CONSERVATIVE — when in doubt, REJECT
- APPROVE strong signals in aligned regimes
- REJECT longs during extreme bear/fear conditions
- REJECT shorts during extreme bull/euphoria
- Do NOT second-guess the ML on technical patterns (that's not your job)
- Keep reasoning to 1-2 sentences maximum

Respond ONLY with valid JSON: {"decision": "APPROVE" | "REJECT", "reason": "brief explanation"}"""

    def __init__(self):
        self._call_timestamps: deque = deque()
        self._client = None
        self._init_client()

    def _init_client(self):
        """Initialize Gemini client."""
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            logger.warning("[Gatekeeper] GEMINI_API_KEY not set — gatekeeper will auto-APPROVE")
            return

        try:
            import google.generativeai as genai
            genai.configure(api_key=api_key)
            self._client = genai.GenerativeModel(
                model_name="gemini-2.5-flash",
                generation_config={"temperature": 0.1, "max_output_tokens": 200},
            )
            logger.info("[Gatekeeper] ✅ Gemini Flash initialized")
        except ImportError:
            logger.warning("[Gatekeeper] google-generativeai not installed — auto-APPROVE mode")
        except Exception as e:
            logger.error(f"[Gatekeeper] Init failed: {e} — auto-APPROVE mode")

    def _is_rate_limited(self) -> bool:
        """Check if we've exceeded our hourly call limit."""
        now = time.time()
        # Remove timestamps older than 1 hour
        while self._call_timestamps and now - self._call_timestamps[0] > CALL_WINDOW_SECONDS:
            self._call_timestamps.popleft()
        return len(self._call_timestamps) >= MAX_CALLS_PER_HOUR

    def _record_call(self):
        """Record this call timestamp."""
        self._call_timestamps.append(time.time())

    def _build_prompt(
        self,
        symbol:         str,
        direction:      str,
        ensemble_score: float,
        regime:         str,
        macro_context:  Dict,
        portfolio_state: Dict,
        trade_ledger:   List[Dict],
        kill_switch_status: str = "NORMAL",
        models_disagree: bool = False
    ) -> str:
        """Build the gatekeeper prompt."""
        fear_greed    = macro_context.get("fear_greed_index", "N/A")
        btc_dominance = macro_context.get("btc_dominance", "N/A")
        vix           = macro_context.get("vix", "N/A")

        regime_descriptions = {
            "bull":         "Strong uptrend, higher highs and higher lows",
            "bear":         "Downtrend, lower lows, risk-off sentiment",
            "ranging":      "Sideways market, no clear direction",
            "extreme_bear": "Crash/panic conditions, extreme selling pressure",
            "trending":     "Strong directional momentum aligned with signal",
            "ambiguous":    "Unclear market structure, models lack strong conviction",
            "squeeze_breakout": "Volatility compression, explosive move pending",
        }
        regime_desc = regime_descriptions.get(regime.lower(), regime)
        consensus_status = "Conflict/Disagreement" if models_disagree else "Strong Agreement"

        return f"""SIGNAL CHECK REQUEST:

Symbol: {symbol}
Signal Direction: {direction}
ML Ensemble Confidence: {ensemble_score:.1%}
Market Regime (1H/4H Anchored): {regime.upper()} — {regime_desc}
Kill Switch Status: {kill_switch_status}
Consensus Layer Agreement: {consensus_status}

Portfolio State:
Consecutive Losses: {portfolio_state.get('consecutive_losses', 0)}
Session Drawdown: {portfolio_state.get('session_drawdown_pct', 0.0):.2%}
Total Drawdown: {portfolio_state.get('total_drawdown_from_start_pct', 0.0):.2%}

Recent Trades (last {len(trade_ledger[-5:]) if trade_ledger else 0}):
{chr(10).join([f"- {t.get('type')} {t.get('symbol', symbol)}: {'Win' if t.get('pnl_usd', 0) > 0 else 'Loss'} ({t.get('pnl_pct', 0):.2%})" for t in trade_ledger[-5:]]) if trade_ledger else "No recent trades."}

Macro Context:
Fear & Greed Index: {fear_greed}/100
BTC Dominance: {btc_dominance}%
VIX: {vix}

Should this {direction} signal be executed given the multi-timeframe and macro alignment?"""

    async def check(
        self,
        symbol:         str,
        direction:      str,
        ensemble_score: float,
        regime:         str,
        macro_context:  Dict,
        portfolio_state: Optional[Dict] = None,
        trade_ledger:    Optional[List[Dict]] = None,
        kill_switch_status: str = "NORMAL",
        models_disagree: bool = False
    ) -> Dict:
        """
        Run gatekeeper check on a signal.
        
        Returns:
            {"decision": "APPROVE" | "REJECT", "reason": str, "source": str}
        """
        # Auto-approve if no client
        if self._client is None:
            return {
                "decision": "APPROVE",
                "reason": "No LLM client — auto-approve",
                "source": "fallback",
            }

        # Rate limit check
        if self._is_rate_limited():
            logger.warning("[Gatekeeper] Rate limit reached — auto-approving")
            return {
                "decision": "APPROVE",
                "reason": "Rate limit reached",
                "source": "rate_limited",
            }

        # Build prompt
        prompt = self._build_prompt(
            symbol, direction, ensemble_score, regime, macro_context, 
            portfolio_state or {}, trade_ledger or [], kill_switch_status, models_disagree
        )

        try:
            self._record_call()
            response = await asyncio.to_thread(
                self._client.generate_content,
                f"{self.SYSTEM_PROMPT}\n\n{prompt}",
            )

            raw_text = response.text.strip()

            # Parse JSON response
            if "```json" in raw_text:
                raw_text = raw_text.split("```json")[1].split("```")[0].strip()
            elif "```" in raw_text:
                raw_text = raw_text.split("```")[1].split("```")[0].strip()

            result = json.loads(raw_text)
            decision = result.get("decision", "APPROVE").upper()
            reason   = result.get("reason", "")

            if decision not in ("APPROVE", "REJECT"):
                decision = "APPROVE"

            icon = "✅" if decision == "APPROVE" else "❌"
            logger.info(f"[Gatekeeper] {icon} {symbol} {direction}: {decision} — {reason}")

            return {
                "decision": decision,
                "reason":   reason,
                "source":   "gemini_flash",
                "prompt":   prompt,
            }

        except json.JSONDecodeError as e:
            logger.error(f"[Gatekeeper] JSON parse error: {e} — auto-approving")
            return {"decision": "APPROVE", "reason": "JSON parse error", "source": "error"}

        except Exception as e:
            logger.error(f"[Gatekeeper] API error: {e} — auto-approving")
            return {"decision": "APPROVE", "reason": str(e), "source": "error"}
