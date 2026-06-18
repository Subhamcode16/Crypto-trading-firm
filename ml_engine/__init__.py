"""
ml_engine/__init__.py
──────────────────────
ML Engine for Crypto Trading Bot v2.0

Architecture:
  data/        → OHLCV fetching, storage, validation
  features/    → 120-dim feature engineering
  models/      → LSTM + XGBoost models
  rl/          → Reinforcement Learning (PPO)
  agents/      → 2 LLM agents (Gatekeeper + EdgeResolver)
  aggregator   → Ensemble signal combiner
  feedback/    → Continuous learning loop
  execution/   → Order management (in progress)
"""

__version__ = "2.0.0"
__author__  = "ML Engine"
