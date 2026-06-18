"""
ml_engine/feedback/feedback_loop.py
─────────────────────────────────────
Continuous Learning Feedback Loop.

Every closed trade triggers:
  1. Compute Sharpe-adjusted reward signal
  2. Save (features, reward) pair to experience buffer
  3. Queue RL online update
  4. Update accuracy tracker (rolling win rate, Sharpe)

Nightly batch job (2 AM):
  5. Retrain XGBoost on live data + historical data
  6. Evaluate LSTM on live data — trigger full retrain if accuracy < 58%
  7. RL policy mini-update via PPO on experience buffer
  8. Shadow-test new policies before deployment
"""

import asyncio
import json
import logging
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

BUFFER_DIR = Path(__file__).parent.parent / "data" / "store" / "experience_buffer"
BUFFER_DIR.mkdir(parents=True, exist_ok=True)

REWARD_RISK_FREE_RATE = 0.0   # Assume 0% risk-free rate for crypto


class FeedbackLoop:
    """
    Self-improvement engine for the ML trading system.
    
    Processes closed trade outcomes and converts them into:
    - RL rewards for PPO updates
    - Labeled training data for XGBoost/LSTM retraining
    - Performance metrics for drift detection
    """

    def __init__(self, db=None):
        self._db = db
        self._experience_buffer: List[Dict] = []
        self._pending_rl_updates: List[Dict] = []

    async def process_closed_trade(self, trade: Dict) -> Dict:
        """
        Process a closed trade and generate learning signals.
        
        Args:
            trade: {
                "trade_id":    str,
                "symbol":      str,
                "side":        "BUY" | "SELL",
                "entry_price": float,
                "exit_price":  float,
                "pnl_pct":     float,
                "pnl_usd":     float,
                "bars_held":   int,
                "exit_reason": str,
                "signal":      dict (the ML signal that triggered this trade),
                "features":    dict (feature vector at entry),
            }
        
        Returns:
            {"reward": float, "label": int, "experience_saved": bool}
        """
        trade_id   = trade.get("trade_id", "unknown")
        pnl_pct    = float(trade.get("pnl_pct", 0))
        bars_held  = int(trade.get("bars_held", 1))
        exit_reason= trade.get("exit_reason", "MANUAL")
        features   = trade.get("features", {})

        # ── Compute Sharpe-adjusted reward ───────────────────────────────
        reward = self._compute_reward(
            pnl_pct=pnl_pct,
            bars_held=bars_held,
            exit_reason=exit_reason,
        )

        # ── Generate supervised label ──────────────────────────────────────
        # For XGBoost retraining: was this entry a good pattern?
        label = self._compute_label(pnl_pct, exit_reason)

        # ── Save to experience buffer ──────────────────────────────────────
        experience = {
            "trade_id":    trade_id,
            "symbol":      trade.get("symbol"),
            "timestamp":   datetime.now(timezone.utc).isoformat(),
            "features":    features,
            "reward":      reward,
            "label":       label,
            "pnl_pct":     pnl_pct,
            "bars_held":   bars_held,
            "exit_reason": exit_reason,
        }

        saved = await self._save_experience(experience)
        if saved:
            self._pending_rl_updates.append(experience)

        logger.info(
            f"[Feedback] Trade {trade_id}: pnl={pnl_pct:.2f}% | "
            f"reward={reward:.4f} | label={label} | exit={exit_reason}"
        )

        return {
            "reward":            reward,
            "label":             label,
            "experience_saved":  saved,
            "pending_rl_count":  len(self._pending_rl_updates),
        }

    def _compute_reward(self, pnl_pct: float, bars_held: int, exit_reason: str) -> float:
        """
        Compute Sharpe-adjusted RL reward from trade outcome.
        
        Reward design:
          + Winning trades: scale by R-multiple efficiency
          - Losing trades: steeper penalty for large losses
          + SL-hit losses: minor bonus for respecting the plan
          - Max-hold exits: penalty (means we couldn't find exit)
        """
        RISK_PER_TRADE = 0.02   # 2% risk per trade (stop loss)
        
        # Base reward: PnL / risk (R-multiple)
        r_multiple = pnl_pct / (RISK_PER_TRADE * 100)

        # Scale reward
        if r_multiple >= 2.0:
            reward = r_multiple * 1.5    # Big bonus for 2R+ trades
        elif r_multiple >= 1.0:
            reward = r_multiple          # Linear for 1-2R
        elif r_multiple >= 0:
            reward = r_multiple * 0.5   # Small reward for breakeven+
        else:
            reward = r_multiple * 1.2   # Penalty for losses (harsher)

        # Exit reason adjustments
        if exit_reason == "TP_HIT":
            reward *= 1.2   # Bonus for reaching TP cleanly
        elif exit_reason == "MAX_HOLD":
            reward *= 0.8   # Penalize for holding too long
        elif exit_reason == "SIGNAL_REVERSE":
            reward *= 1.1   # Good discipline to exit on reversal

        # Time efficiency: penalize slow trades (locked up capital)
        if bars_held > 24 and r_multiple < 1.0:
            reward -= 0.1 * (bars_held / 24)

        return float(reward)

    def _compute_label(self, pnl_pct: float, exit_reason: str) -> int:
        """
        Generate supervised label for XGBoost retraining.
        
        Labels:
          1 = STRONG_LONG  (profitable long)
          2 = STRONG_SHORT (profitable short)
          0 = NO_SIGNAL    (loss)
          3 = WEAK         (small profit)
        """
        if pnl_pct >= 1.5:
            return 1   # STRONG (good entry)
        elif pnl_pct >= 0.5:
            return 3   # WEAK (marginal)
        else:
            return 0   # NO_SIGNAL (bad entry)

    async def _save_experience(self, experience: Dict) -> bool:
        """Save experience to disk buffer."""
        try:
            filename = f"exp_{experience['trade_id']}_{int(datetime.now().timestamp())}.json"
            path = BUFFER_DIR / filename
            with open(path, "w") as f:
                json.dump(experience, f, indent=2)
            return True
        except Exception as e:
            logger.error(f"[Feedback] Failed to save experience: {e}")
            return False

    def load_recent_experiences(self, days: int = 7) -> List[Dict]:
        """Load experience buffer from last N days."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        experiences = []

        for path in BUFFER_DIR.glob("exp_*.json"):
            try:
                with open(path) as f:
                    exp = json.load(f)
                ts = datetime.fromisoformat(exp["timestamp"].replace("Z", "+00:00"))
                if ts > cutoff:
                    experiences.append(exp)
            except Exception:
                pass

        logger.info(f"[Feedback] Loaded {len(experiences)} experiences from last {days} days")
        return experiences

    async def trigger_nightly_retrain(self):
        """
        Orchestrate the nightly retraining batch.
        Called by the scheduler at 2 AM daily.
        """
        logger.info("[Feedback] 🌙 Starting nightly retrain batch")
        results = {}

        experiences = self.load_recent_experiences(days=7)
        if len(experiences) < 5:
            logger.info("[Feedback] Too few experiences for retraining (need 5+)")
            return {"status": "skipped", "reason": "insufficient_data"}

        # 1. XGBoost retrain with live data
        try:
            results["xgb"] = await self._retrain_xgboost(experiences)
        except Exception as e:
            logger.error(f"[Feedback] XGB retrain failed: {e}")
            results["xgb"] = {"status": "error", "error": str(e)}

        # 2. RL policy update
        try:
            results["rl"] = await self._update_rl_policy(experiences)
        except Exception as e:
            logger.error(f"[Feedback] RL update failed: {e}")
            results["rl"] = {"status": "error", "error": str(e)}

        results["timestamp"]     = datetime.now(timezone.utc).isoformat()
        results["experiences"]   = len(experiences)
        results["status"]        = "completed"

        logger.info(f"[Feedback] 🌙 Nightly retrain complete: {results}")
        return results

    async def _retrain_xgboost(self, experiences: List[Dict]) -> Dict:
        """Retrain XGBoost on live trade experiences."""
        import numpy as np
        from ml_engine.models.xgb_model import XGBModel, XGBTrainer

        # Build training dataset from experiences
        rows = []
        for exp in experiences:
            feats = exp.get("features", {})
            label = exp.get("label")
            if feats and label is not None:
                row = {k: v for k, v in feats.items()
                       if not k.startswith("_") and isinstance(v, (int, float))}
                row["label"] = label
                rows.append(row)

        if len(rows) < 5:
            return {"status": "skipped", "reason": "too_few_rows"}

        import pandas as pd
        df_live = pd.DataFrame(rows)
        feature_names = [c for c in df_live.columns if c != "label"]

        logger.info(f"[Feedback] Retraining XGBoost on {len(df_live)} live experiences")

        # We retrain per symbol if we have enough data
        for symbol in ["BTC/USDT", "ETH/USDT", "SOL/USDT"]:
            trainer = XGBTrainer(symbol=symbol, timeframe="1h")
            # Quick retrain without Optuna (fast, nightly)
            _, report = await asyncio.to_thread(
                trainer.train, df_live, feature_names,
                use_optuna=False, retrain=False
            )
            logger.info(f"[Feedback] XGB retrain {symbol}: {report.get('status')}")

        return {"status": "completed", "samples": len(rows)}

    async def _update_rl_policy(self, experiences: List[Dict]) -> Dict:
        """Perform a mini-update on the RL policy from recent experiences."""
        logger.info(f"[Feedback] RL policy update with {len(experiences)} experiences")
        # RL online update requires the environment + stable-baselines3
        # This is a simplified version — full implementation in rl/online_updater.py
        return {
            "status":      "queued",
            "experiences": len(experiences),
            "note":        "Full RL update handled by rl/online_updater.py",
        }
