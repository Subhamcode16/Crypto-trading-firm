"""
ml_engine/rl/trading_env.py
────────────────────────────
Custom OpenAI Gymnasium Environment for Crypto Trading.

State Space (~130-dim):
  - OHLCV features + TA indicators from FeatureBuilder (120-dim)
  - Portfolio state: [position, unrealized_pnl, time_in_trade, cash_ratio] (4-dim)
  - LSTM signal: [p_up, p_down, p_neutral] (3-dim)
  - XGB signal:  [is_strong_long, is_strong_short, xgb_confidence] (3-dim)

Action Space: Discrete(3)
  0 = HOLD  (no change)
  1 = BUY   (enter/add long)
  2 = SELL  (exit or short)

Reward Function (Sharpe-adjusted):
  + Realized PnL on close (net of commission)
  + Bonus for catching >2R moves
  - Penalty for overtrading (>5 trades/day)
  - Penalty for max drawdown exceeding 5%
  - Penalty for holding losing trades > N bars

Usage:
  env = CryptoTradingEnv(df_btc_features, feature_names)
  obs, _ = env.reset()
  action = env.action_space.sample()
  obs, reward, done, truncated, info = env.step(action)
"""

import logging
from typing import Dict, List, Optional, Tuple

import gymnasium as gym
import numpy as np
import pandas as pd
from gymnasium import spaces

logger = logging.getLogger(__name__)

# Trading parameters
COMMISSION_RATE   = 0.001    # 0.1% per trade (Binance Futures)
INITIAL_CAPITAL   = 10_000   # Starting in USD (paper)
MAX_POSITION_PCT  = 0.95     # Use max 95% of capital per trade
STOP_LOSS_PCT     = 0.02     # 2% stop loss (ATR-based in production)
TAKE_PROFIT_PCT   = 0.04     # 4% take profit (2R)
MAX_TRADE_BARS    = 48       # Max bars to hold a position (48h on 1h TF)

# Reward shaping
OVERTRADE_PENALTY = -0.5    # Per extra trade above 5/day
DRAWDOWN_PENALTY  = -1.0    # Per % of drawdown above 5%
HOLD_LOSS_PENALTY = -0.05   # Per bar holding a losing trade beyond 12 bars
TIME_BONUS        = 0.1     # Small bonus for staying flat during no-signal


class CryptoTradingEnv(gym.Env):
    """
    Custom Gymnasium environment for ML-driven crypto trading.
    
    Designed to:
    1. Train a PPO agent on historical OHLCV + feature data
    2. Provide realistic simulation with commission, slippage, SL/TP
    3. Shape rewards to encourage disciplined, profitable trading
    4. Track Sharpe ratio as the primary optimization target
    """

    metadata = {"render_modes": ["human", "rgb_array"]}

    def __init__(
        self,
        df: pd.DataFrame,
        feature_names: List[str],
        initial_capital: float = INITIAL_CAPITAL,
        commission: float = COMMISSION_RATE,
        sl_pct: float = STOP_LOSS_PCT,
        tp_pct: float = TAKE_PROFIT_PCT,
        max_hold_bars: int = MAX_TRADE_BARS,
        render_mode: Optional[str] = None,
        # Optional LSTM/XGB signals to include in state
        lstm_signals: Optional[pd.DataFrame] = None,
        xgb_signals: Optional[pd.DataFrame] = None,
    ):
        super().__init__()

        self.df            = df.reset_index(drop=True)
        self.feature_names = feature_names
        self.initial_capital = initial_capital
        self.commission    = commission
        self.sl_pct        = sl_pct
        self.tp_pct        = tp_pct
        self.max_hold_bars = max_hold_bars
        self.render_mode   = render_mode
        self.lstm_signals  = lstm_signals
        self.xgb_signals   = xgb_signals

        # Observation space
        n_ml_features   = len(feature_names)
        n_portfolio_feats = 5   # position, unreal_pnl, time_in_trade, cash_ratio, daily_trades
        n_signal_feats   = 6   # LSTM [up,down,neutral] + XGB [strong_long, strong_short, conf]
        self.n_obs = n_ml_features + n_portfolio_feats + n_signal_feats

        self.observation_space = spaces.Box(
            low=-np.inf,
            high=np.inf,
            shape=(self.n_obs,),
            dtype=np.float32,
        )

        # Action space: HOLD=0, BUY=1, SELL=2
        self.action_space = spaces.Discrete(3)

        # Internal state (reset on env.reset())
        self._current_idx      = 0
        self._position         = 0.0    # 0=flat, 1=long
        self._entry_price      = 0.0
        self._entry_idx        = 0
        self._capital          = initial_capital
        self._peak_capital     = initial_capital
        self._trade_count_day  = 0
        self._day_start_capital = initial_capital
        self._all_returns: List[float] = []
        self._trade_log: List[Dict] = []

        # Pre-extract feature matrix for speed
        self._X = df[feature_names].values.astype(np.float32)
        self._closes = df["close"].values.astype(np.float32)

        logger.info(f"[Env] Initialized: {len(df):,} bars | obs_dim={self.n_obs} | capital=${initial_capital:,.0f}")

    # ─── Gymnasium Interface ──────────────────────────────────────────────

    def reset(
        self,
        seed: Optional[int] = None,
        options: Optional[Dict] = None,
    ) -> Tuple[np.ndarray, Dict]:
        """Reset environment to a starting state."""
        super().reset(seed=seed)

        # Random start within first 30% of data (enables diverse starts during training)
        max_start = max(0, int(len(self.df) * 0.3))
        start_offset = self.np_random.integers(0, max(1, max_start)) if max_start > 0 else 0

        self._current_idx      = max(60, start_offset)   # Need 60 bars of history
        self._position         = 0.0
        self._entry_price      = 0.0
        self._entry_idx        = 0
        self._capital          = self.initial_capital
        self._peak_capital     = self.initial_capital
        self._trade_count_day  = 0
        self._day_start_capital = self.initial_capital
        self._all_returns      = []
        self._trade_log        = []

        obs = self._get_observation()
        return obs, {}

    def step(self, action: int) -> Tuple[np.ndarray, float, bool, bool, Dict]:
        """
        Execute one trading step.
        
        Returns:
            (observation, reward, terminated, truncated, info)
        """
        current_price = float(self._closes[self._current_idx])
        reward = 0.0

        # ── Execute action ───────────────────────────────────────────────
        if action == 1:   # BUY
            reward += self._action_buy(current_price)
        elif action == 2: # SELL
            reward += self._action_sell(current_price)
        else:             # HOLD
            reward += self._action_hold(current_price)

        # ── Check SL/TP (auto-exit) ──────────────────────────────────────
        if self._position > 0:
            reward += self._check_sl_tp(current_price)

        # ── Check max hold duration ──────────────────────────────────────
        if self._position > 0:
            bars_held = self._current_idx - self._entry_idx
            if bars_held > self.max_hold_bars:
                # Force exit
                reward += self._execute_exit(current_price, reason="MAX_HOLD")

        # ── Daily metrics reset (on new day detection) ───────────────────
        # Simplified: reset trade count every 24 bars (≈1 day on 1h TF)
        if self._current_idx % 24 == 0:
            self._trade_count_day = 0
            self._day_start_capital = self._capital

        # ── Drawdown penalty ─────────────────────────────────────────────
        self._peak_capital = max(self._peak_capital, self._capital)
        drawdown_pct = (self._peak_capital - self._capital) / self._peak_capital
        if drawdown_pct > 0.05:
            excess_dd = drawdown_pct - 0.05
            reward += DRAWDOWN_PENALTY * excess_dd * 100

        # ── Advance timestep ─────────────────────────────────────────────
        self._current_idx += 1

        # ── Check termination ─────────────────────────────────────────────
        terminated = self._current_idx >= len(self.df) - 1
        truncated  = self._capital < self.initial_capital * 0.5  # Lost 50% max drawdown limit
        
        # Cap capital to prevent exponential math overflow if agent becomes a billionaire
        self._capital = min(self._capital, 1e9)

        info = {
            "capital":         self._capital,
            "position":        self._position,
            "total_return_pct": (self._capital / self.initial_capital - 1) * 100,
            "trade_count":     len(self._trade_log),
            "sharpe":          self._compute_sharpe(),
        }

        obs = self._get_observation()
        
        # Hard clip reward to completely eliminate float32 overflow risk
        reward = np.clip(float(reward), -100.0, 100.0)
        return obs, float(reward), terminated, truncated, info

    # ─── Private Helpers ─────────────────────────────────────────────────

    def _action_buy(self, price: float) -> float:
        """Execute a BUY action."""
        if self._position > 0:
            return -0.01   # Small penalty for buying when already long

        if self._trade_count_day >= 5:
            return OVERTRADE_PENALTY   # Overtrading penalty

        # Open long position
        trade_capital = self._capital * MAX_POSITION_PCT
        commission_cost = trade_capital * self.commission

        self._position    = trade_capital / price
        self._entry_price = price
        self._entry_idx   = self._current_idx
        self._capital    -= commission_cost
        self._trade_count_day += 1

        # Constant reward penalty, independent of exploding capital
        return -float(self.commission * MAX_POSITION_PCT)

    def _action_sell(self, price: float) -> float:
        """Execute a SELL / exit action."""
        if self._position <= 0:
            return -0.01   # Small penalty for selling when flat

        return self._execute_exit(price, reason="SIGNAL")

    def _action_hold(self, price: float) -> float:
        """Hold action — small time bonus if flat, unrealized PnL update if in trade."""
        if self._position <= 0:
            return TIME_BONUS * 0.01   # Tiny bonus for staying disciplined (flat)

        # Penalize for holding losing trade too long
        bars_held = self._current_idx - self._entry_idx
        if bars_held > 12 and price < self._entry_price:
            return HOLD_LOSS_PENALTY

        return 0.0

    def _check_sl_tp(self, price: float) -> float:
        """Check if stop-loss or take-profit is triggered."""
        if self._position <= 0 or self._entry_price <= 0:
            return 0.0

        change = (price - self._entry_price) / self._entry_price

        if change <= -self.sl_pct:
            return self._execute_exit(price, reason="SL_HIT")
        if change >= self.tp_pct:
            return self._execute_exit(price, reason="TP_HIT")

        return 0.0

    def _execute_exit(self, price: float, reason: str = "MANUAL") -> float:
        """Close open position and compute realized reward."""
        if self._position <= 0:
            return 0.0

        exit_value      = self._position * price
        entry_value     = self._position * self._entry_price
        commission_cost = exit_value * self.commission
        pnl             = exit_value - entry_value - commission_cost

        self._capital  += entry_value + pnl   # Restore capital + profit/loss
        pnl_pct         = pnl / entry_value

        self._all_returns.append(pnl_pct)
        self._trade_log.append({
            "entry_price": self._entry_price,
            "exit_price":  price,
            "pnl_pct":     round(pnl_pct * 100, 3),
            "pnl_usd":     round(pnl, 2),
            "reason":      reason,
            "bars_held":   self._current_idx - self._entry_idx,
        })

        self._position    = 0.0
        self._entry_price = 0.0

        # Sharpe-adjusted reward
        if pnl_pct > 0:
            # Winning trade — scale by R-multiple achieved
            r_multiple = pnl_pct / self.sl_pct
            reward = pnl_pct * (1 + min(r_multiple, 3.0))
        else:
            # Losing trade — penalize more if stopped out at max SL
            reward = pnl_pct * 1.5

        logger.debug(f"[Env] Exit [{reason}]: pnl={pnl_pct*100:.2f}% | reward={reward:.4f}")
        return float(reward)

    def _get_observation(self) -> np.ndarray:
        """Build the observation vector for current state."""
        idx = min(self._current_idx, len(self._X) - 1)

        # Feature vector (120 TA features)
        market_features = self._X[idx].copy()

        # Portfolio state
        current_price   = float(self._closes[idx])
        unrealized_pnl  = 0.0
        if self._position > 0 and self._entry_price > 0:
            unrealized_pnl = (current_price - self._entry_price) / self._entry_price

        portfolio_state = np.array([
            float(self._position > 0),                              # is_long
            np.clip(unrealized_pnl, -0.5, 0.5),                    # unrealized PnL (clipped)
            float(self._current_idx - self._entry_idx) / self.max_hold_bars,   # time in trade
            min(self._capital / self.initial_capital, 2.0),        # capital ratio
            float(self._trade_count_day) / 5.0,                    # trades today / max
        ], dtype=np.float32)

        # ML signals (LSTM + XGB if available)
        signal_state = np.zeros(6, dtype=np.float32)
        if self.lstm_signals is not None and idx < len(self.lstm_signals):
            row = self.lstm_signals.iloc[idx]
            signal_state[0] = float(row.get("lstm_prob_up", 0.33))
            signal_state[1] = float(row.get("lstm_prob_down", 0.33))
            signal_state[2] = float(row.get("lstm_prob_neutral", 0.33))
        else:
            signal_state[0:3] = 0.33   # Uniform uncertainty

        if self.xgb_signals is not None and idx < len(self.xgb_signals):
            row = self.xgb_signals.iloc[idx]
            signal_state[3] = 1.0 if str(row.get("xgb_signal","")) == "STRONG_LONG" else 0.0
            signal_state[4] = 1.0 if str(row.get("xgb_signal","")) == "STRONG_SHORT" else 0.0
            signal_state[5] = float(row.get("xgb_confidence", 0.0))

        obs = np.concatenate([market_features, portfolio_state, signal_state])

        # Cast to float32 FIRST so any values > 3.4e38 become np.inf
        obs = np.asarray(obs, dtype=np.float32)
        # Replace NaN/Inf with 0 (safety net)
        obs = np.where(np.isfinite(obs), obs, 0.0)
        # Hard clip to prevent massive outliers from destroying VecNormalize variance
        obs = np.clip(obs, -1e6, 1e6)
        return obs

    def _compute_sharpe(self) -> float:
        """Compute Sharpe ratio on trade returns so far."""
        if len(self._all_returns) < 2:
            return 0.0
        returns = np.array(self._all_returns)
        mean_r  = returns.mean()
        std_r   = returns.std() + 1e-10
        return float(mean_r / std_r * np.sqrt(252))   # Annualized

    def render(self):
        """Simple render for debugging."""
        if self.render_mode == "human":
            price = float(self._closes[min(self._current_idx, len(self._closes)-1)])
            print(f"[Env] Bar {self._current_idx} | Price={price:.2f} | "
                  f"Position={'LONG' if self._position > 0 else 'FLAT'} | "
                  f"Capital=${self._capital:,.2f} | "
                  f"Trades={len(self._trade_log)}")

    def get_trade_summary(self) -> Dict:
        """Return trading summary after episode ends."""
        if not self._trade_log:
            return {"trades": 0, "win_rate": 0.0, "sharpe": 0.0}

        pnls = [t["pnl_pct"] for t in self._trade_log]
        wins = sum(1 for p in pnls if p > 0)

        return {
            "trades":       len(self._trade_log),
            "win_rate":     round(wins / len(pnls), 4) if pnls else 0.0,
            "avg_pnl_pct":  round(np.mean(pnls), 4) if pnls else 0.0,
            "total_return": round((self._capital / self.initial_capital - 1) * 100, 2),
            "sharpe":       round(self._compute_sharpe(), 4),
            "max_drawdown": round((self._peak_capital - self._capital) / self._peak_capital * 100, 2),
        }
