"""
ml_engine/rl/rl_trainer.py
────────────────────────────
PPO Reinforcement Learning Trainer.

Trains a Proximal Policy Optimization agent using stable-baselines3
on the CryptoTradingEnv environment.

Training Strategy:
  - Train on 70% of historical data (2021-2024)
  - Validate on 15% (2024-2025)
  - True holdout: last 15% (2025-2026)
  - Multi-environment training (4 parallel envs for speed on CPU)

Usage:
  python -m ml_engine.rl.rl_trainer --symbol BTC/USDT --timesteps 500000
  python -m ml_engine.rl.rl_trainer --all --timesteps 1000000
"""

import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np

logger = logging.getLogger(__name__)

POLICIES_DIR = Path(__file__).parent / "policies"
POLICIES_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_TIMESTEPS = 500_000    # CPU-optimized (≈30-60 min per symbol)
LOG_INTERVAL      = 10_000


class RLTrainer:
    """
    Trains a PPO agent for crypto trading using stable-baselines3.
    CPU-optimized with 4 parallel environments.
    """

    def __init__(self, symbol: str = "BTC/USDT", timeframe: str = "1h"):
        self.symbol    = symbol
        self.timeframe = timeframe

    def train(
        self,
        timesteps: int = DEFAULT_TIMESTEPS,
        retrain:   bool = False,
    ) -> Dict:
        """
        Full PPO training pipeline.
        
        Args:
            timesteps: Total environment steps (more = better, but slower)
            retrain:   Force retrain even if policy exists
        
        Returns:
            Training report dict
        """
        try:
            from stable_baselines3 import PPO
            from stable_baselines3.common.env_util import make_vec_env
            from stable_baselines3.common.callbacks import (
                EvalCallback, CheckpointCallback, CallbackList
            )
            from stable_baselines3.common.monitor import Monitor
        except ImportError:
            return {
                "status": "error",
                "reason": "stable-baselines3 not installed. Run: pip install stable-baselines3",
            }

        from ml_engine.data.pipeline import DataPipeline
        from ml_engine.features.feature_builder import FeatureBuilder
        from ml_engine.rl.trading_env import CryptoTradingEnv

        logger.info(f"\n{'='*60}")
        logger.info(f"[RL Trainer] Training PPO: {self.symbol} {self.timeframe}")
        logger.info(f"[RL Trainer] Timesteps: {timesteps:,}")
        logger.info(f"{'='*60}")

        # 1. Load data
        pipeline = DataPipeline()
        df_raw   = pipeline.get_training_data(self.symbol, self.timeframe)
        logger.info(f"[RL Trainer] Raw data: {len(df_raw):,} bars")

        # 2. Build features
        fb       = FeatureBuilder()
        df_feat  = fb.build_dataset(df_raw, dropna=True)
        feature_names = fb.get_feature_columns(df_feat)
        logger.info(f"[RL Trainer] Features: {len(feature_names)} dimensions")

        # 3. Time-aware split (no shuffling)
        n = len(df_feat)
        n_train = int(n * 0.70)
        n_val   = int(n * 0.15)

        df_train = df_feat.iloc[:n_train].reset_index(drop=True)
        df_val   = df_feat.iloc[n_train: n_train + n_val].reset_index(drop=True)

        logger.info(f"[RL Trainer] Train: {len(df_train):,} | Val: {len(df_val):,}")

        # 4. Create vectorized training environments (CPU: use 4 envs)
        def make_train_env():
            env = CryptoTradingEnv(df_train, feature_names)
            return Monitor(env)

        def make_val_env():
            env = CryptoTradingEnv(df_val, feature_names)
            return Monitor(env)

        n_envs = 4   # CPU-friendly parallel envs
        vec_train_env = make_vec_env(make_train_env, n_envs=n_envs)
        vec_val_env   = make_vec_env(make_val_env,   n_envs=1)

        # 4.5 Normalize observations (CRITICAL for PPO with raw price/volume data)
        from stable_baselines3.common.vec_env import VecNormalize
        vec_train_env = VecNormalize(vec_train_env, norm_obs=True, norm_reward=True, clip_obs=10.0)
        
        # Validation env must share the SAME running mean/std as training env
        vec_val_env = VecNormalize(vec_val_env, norm_obs=True, norm_reward=False, clip_obs=10.0)
        vec_val_env.obs_rms = vec_train_env.obs_rms  # sync stats
        vec_val_env.training = False                 # don't update stats during eval

        # 5. Load existing policy or create new one
        policy_path = self._get_policy_path()
        save_path   = str(POLICIES_DIR / f"ppo_{self.symbol.replace('/', '_')}_{self.timeframe}")

        existing_mean_reward = -np.inf
        if not retrain and (POLICIES_DIR / f"ppo_{self.symbol.replace('/', '_')}_{self.timeframe}.zip").exists():
            logger.info(f"[RL Trainer] Loading existing policy for continued training")
            model = PPO.load(save_path, env=vec_train_env)
        else:
            model = PPO(
                "MlpPolicy",
                vec_train_env,
                learning_rate=3e-4,
                n_steps=2048,
                batch_size=64,
                n_epochs=10,
                gamma=0.99,
                gae_lambda=0.95,
                clip_range=0.2,
                ent_coef=0.01,           # Encourage exploration
                vf_coef=0.5,
                max_grad_norm=0.5,
                verbose=0,
                tensorboard_log=None,    # Disable TB for simplicity
            )

        # 6. Callbacks
        eval_callback = EvalCallback(
            vec_val_env,
            best_model_save_path=str(POLICIES_DIR),
            log_path=str(POLICIES_DIR),
            eval_freq=max(LOG_INTERVAL // n_envs, 1000),
            n_eval_episodes=5,
            deterministic=True,
            verbose=1,
        )

        checkpoint_callback = CheckpointCallback(
            save_freq=max(50_000 // n_envs, 1000),
            save_path=str(POLICIES_DIR / "checkpoints"),
            name_prefix=f"rl_{self.symbol.replace('/', '_')}",
        )

        # 7. Train
        logger.info(f"[RL Trainer] Starting training ({timesteps:,} timesteps, {n_envs} envs)...")
        logger.info(f"[RL Trainer] Expected time: {timesteps // 10_000 * 2:.0f}–{timesteps // 10_000 * 4:.0f} minutes on CPU")

        model.learn(
            total_timesteps=timesteps,
            callback=CallbackList([eval_callback, checkpoint_callback]),
            log_interval=LOG_INTERVAL // n_envs,
            progress_bar=True,
        )

        # 8. Save final policy
        model.save(save_path)
        vec_train_env.save(str(POLICIES_DIR / f"vec_normalize_{self.symbol.replace('/', '_')}_{self.timeframe}.pkl"))
        logger.info(f"[RL Trainer] ✅ Policy saved: {save_path}.zip")

        # 9. Evaluate on validation set
        val_metrics = self._evaluate_policy(model, df_val, feature_names)

        report = {
            "timestamp":      datetime.now(timezone.utc).isoformat(),
            "symbol":         self.symbol,
            "timeframe":      self.timeframe,
            "timesteps":      timesteps,
            "train_bars":     n_train,
            "val_bars":       n_val,
            "n_features":     len(feature_names),
            "val_sharpe":     val_metrics.get("sharpe", 0.0),
            "val_win_rate":   val_metrics.get("win_rate", 0.0),
            "val_total_return": val_metrics.get("total_return", 0.0),
            "policy_path":    f"{save_path}.zip",
            "status":         "success",
        }

        logger.info(f"\n[RL Trainer] Training complete!")
        logger.info(f"[RL Trainer] Val Sharpe: {val_metrics.get('sharpe', 0):.4f}")
        logger.info(f"[RL Trainer] Val Win Rate: {val_metrics.get('win_rate', 0):.1%}")
        logger.info(f"[RL Trainer] Val Return: {val_metrics.get('total_return', 0):.2f}%")

        return report

    def _evaluate_policy(
        self,
        model,
        df: "pd.DataFrame",
        feature_names: List[str],
        n_episodes: int = 3,
    ) -> Dict:
        """Evaluate trained policy on validation set."""
        from ml_engine.rl.trading_env import CryptoTradingEnv
        import numpy as np

        all_summaries = []

        for _ in range(n_episodes):
            env = CryptoTradingEnv(df, feature_names)
            obs, _ = env.reset()
            done = False

            while not done:
                action, _ = model.predict(obs, deterministic=True)
                obs, _, terminated, truncated, _ = env.step(int(action))
                done = terminated or truncated

            summary = env.get_trade_summary()
            all_summaries.append(summary)

        # Average across episodes
        avg_metrics = {
            "sharpe":       np.mean([s["sharpe"] for s in all_summaries]),
            "win_rate":     np.mean([s["win_rate"] for s in all_summaries]),
            "total_return": np.mean([s["total_return"] for s in all_summaries]),
            "avg_trades":   np.mean([s["trades"] for s in all_summaries]),
        }

        return {k: round(float(v), 4) for k, v in avg_metrics.items()}

    def _get_policy_path(self) -> Path:
        name = f"ppo_{self.symbol.replace('/', '_')}_{self.timeframe}.zip"
        return POLICIES_DIR / name

    @staticmethod
    def load_policy(symbol: str, timeframe: str):
        """Load a saved PPO policy for inference."""
        from stable_baselines3 import PPO
        path = POLICIES_DIR / f"ppo_{symbol.replace('/','_')}_{timeframe}"
        if not (POLICIES_DIR / f"ppo_{symbol.replace('/','_')}_{timeframe}.zip").exists():
            raise FileNotFoundError(f"No policy found at {path}.zip")
        return PPO.load(str(path))

    @staticmethod
    def exists(symbol: str, timeframe: str) -> bool:
        name = f"ppo_{symbol.replace('/','_')}_{timeframe}.zip"
        return (POLICIES_DIR / name).exists()


class RLInferenceAgent:
    """
    Lightweight wrapper for RL policy inference during live trading.
    Loads the policy once and keeps it in memory.
    """

    def __init__(self, symbol: str, timeframe: str):
        self.symbol    = symbol
        self.timeframe = timeframe
        self._policy   = None
        self._load()

    def _load(self):
        """Load policy from disk."""
        try:
            self._policy = RLTrainer.load_policy(self.symbol, self.timeframe)
            logger.info(f"[RL Agent] Loaded policy: {self.symbol} {self.timeframe}")
            
            # Load normalization stats if they exist
            from stable_baselines3.common.vec_env import VecNormalize
            stats_path = POLICIES_DIR / f"vec_normalize_{self.symbol.replace('/', '_')}_{self.timeframe}.pkl"
            if stats_path.exists():
                self._vec_normalize = VecNormalize.load(str(stats_path), None)
                self._vec_normalize.training = False
                self._vec_normalize.norm_reward = False
            else:
                self._vec_normalize = None
                
        except FileNotFoundError:
            logger.warning(f"[RL Agent] No policy found for {self.symbol} {self.timeframe} — using random baseline")
            self._vec_normalize = None

    def predict(self, observation: "np.ndarray") -> Dict:
        """
        Get action from RL policy.
        
        Args:
            observation: State vector from CryptoTradingEnv._get_observation()
        
        Returns:
            {"action": "BUY"|"SELL"|"HOLD", "action_id": int, "confidence": float}
        """
        if self._policy is None:
            return {"action": "HOLD", "action_id": 0, "confidence": 0.5, "source": "fallback"}

        # Normalize observation if stats exist
        if getattr(self, "_vec_normalize", None) is not None:
            # VecNormalize expects batched obs (1, dim)
            observation = self._vec_normalize.normalize_obs(observation.reshape(1, -1))[0]

        action_id, _ = self._policy.predict(observation, deterministic=True)
        action_names = {0: "HOLD", 1: "BUY", 2: "SELL"}

        # Get action probabilities for confidence estimate
        try:
            import torch
            obs_tensor = self._policy.policy.obs_to_tensor(observation.reshape(1, -1))[0]
            with torch.no_grad():
                action_dist = self._policy.policy.get_distribution(obs_tensor)
                probs = action_dist.distribution.probs.numpy()[0]
            confidence = float(probs[int(action_id)])
        except Exception:
            confidence = 0.6   # Default confidence

        return {
            "action":     action_names.get(int(action_id), "HOLD"),
            "action_id":  int(action_id),
            "confidence": round(confidence, 4),
            "source":     "rl_ppo",
        }


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
        stream=sys.stdout,
    )

    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol",     default="BTC/USDT")
    parser.add_argument("--timeframe",  default="1h")
    parser.add_argument("--timesteps",  type=int, default=DEFAULT_TIMESTEPS)
    parser.add_argument("--retrain",    action="store_true")
    parser.add_argument("--all",        action="store_true")
    args = parser.parse_args()

    if args.all:
        for sym in ["BTC/USDT", "ETH/USDT", "SOL/USDT"]:
            trainer = RLTrainer(symbol=sym, timeframe=args.timeframe)
            report  = trainer.train(timesteps=args.timesteps, retrain=args.retrain)
            print(json.dumps(report, indent=2))
    else:
        trainer = RLTrainer(symbol=args.symbol, timeframe=args.timeframe)
        report  = trainer.train(timesteps=args.timesteps, retrain=args.retrain)
        print(json.dumps(report, indent=2))
