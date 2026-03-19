#!/usr/bin/env python3
"""
ML Feature Builder — Aggregates real signals from all agents into a flat feature vector.
This is the bridge between the 9-agent pipeline and the XGBoost ML model.

Runs INSIDE Agent 5 (Signal Aggregator) right before calling pump_predictor.predict().
Saves feature vectors to disk alongside trade entries for future training.
"""

import json
import logging
import os
from datetime import datetime
from typing import Dict, Optional

logger = logging.getLogger('feature_builder')


class FeatureBuilder:
    """
    Converts raw agent output signals into a normalized ML feature vector.

    Feature categories:
    - Social signals (Agent 1: Reddit, X, RSS)
    - Safety signals (Agent 2: on-chain filters)
    - Smart money signals (Agent 3: wallet tracker)
    - Narrative signals (Agent 4: intel agent)
    - DEX/on-chain raw metrics
    - pump.fun launch signals
    """

    FEATURE_VERSION = "1.0"

    def build(
        self,
        token_address: str,
        agent_1_data: Optional[Dict] = None,
        agent_2_data: Optional[Dict] = None,
        agent_3_data: Optional[Dict] = None,
        agent_4_data: Optional[Dict] = None,
        dex_data: Optional[Dict] = None,
        pumpfun_data: Optional[Dict] = None,
    ) -> Dict:
        """
        Build a complete flat feature vector from all agent outputs.

        Args:
            token_address: Solana token address (for logging)
            agent_1_data: Discovery data (scores, source, reddit/X metrics)
            agent_2_data: Safety analysis result (9 filters)
            agent_3_data: Wallet tracker result (smart wallets, insider)
            agent_4_data: Intel agent result (narrative, influencers)
            dex_data:     Raw DexScreener pair data
            pumpfun_data: pump.fun token data (if applicable)

        Returns:
            Flat dict of floats (feature_vector)
        """
        features = {}

        # ── AGENT 1: Discovery & Social Signals ──────────────────────────
        a1 = agent_1_data or {}
        raw_a1 = a1.get('raw', {})
        features['source_pumpfun']   = 1.0 if a1.get('source') == 'pumpfun' else 0.0
        features['source_dexscreener']= 1.0 if a1.get('source') == 'dexscreener' else 0.0
        features['source_reddit']    = 1.0 if a1.get('source') == 'reddit_post' else 0.0
        features['source_coingecko'] = 1.0 if a1.get('source') == 'coingecko' else 0.0
        features['source_twitter']   = 1.0 if a1.get('source') == 'twitter_search' else 0.0
        features['source_rss']       = 1.0 if a1.get('source') == 'rss_news' else 0.0
        features['agent1_score']     = float(a1.get('score', 5.0))

        # Reddit-specific metrics (if source is reddit)
        features['reddit_mention_count']    = float(raw_a1.get('mention_count', 0))
        features['reddit_upvote_velocity']  = float(raw_a1.get('upvote_velocity', 0))
        features['reddit_comment_velocity'] = float(raw_a1.get('comment_velocity', 0))

        # ── AGENT 2: On-Chain Safety Signals ─────────────────────────────
        a2 = agent_2_data or {}
        features['safety_score']              = float(a2.get('score', 0))
        features['safety_cleared']            = 1.0 if a2.get('status') == 'CLEARED' else 0.0
        features['lp_locked']                 = float(a2.get('filters', {}).get('lp_locked', {}).get('passed', 0))
        features['mint_authority_disabled']   = float(a2.get('filters', {}).get('mint_authority', {}).get('passed', 0))
        features['top_holder_pct_safe']       = float(a2.get('filters', {}).get('holder_concentration', {}).get('passed', 0))
        features['rugcheck_passed']           = float(a2.get('filters', {}).get('rugcheck', {}).get('passed', 0))
        features['liquidity_usd_safe']        = float(a2.get('filters', {}).get('liquidity_check', {}).get('passed', 0))

        # ── AGENT 3: Smart Money / Wallet Signals ─────────────────────────
        a3 = agent_3_data or {}
        features['smart_wallet_count']      = float(len(a3.get('smart_wallets_detected', [])))
        features['is_priority_signal']      = 1.0 if a3.get('is_priority') else 0.0
        features['insider_action_holding']  = 1.0 if a3.get('insider_status', {}).get('deployer_action') in ['holding', 'accumulating'] else 0.0
        features['copy_trade_detected']     = 1.0 if a3.get('copy_trade_signal', {}).get('detected') else 0.0
        features['copy_trade_win_rate']     = float(a3.get('copy_trade_signal', {}).get('historical_success_rate', 0))
        features['agent3_score']            = float(a3.get('score', 0))

        # ── AGENT 4: Narrative / Intel Signals ────────────────────────────
        a4 = agent_4_data or {}
        features['narrative_bonus_awarded'] = 1.0 if a4.get('narrative_bonus_awarded') else 0.0
        features['influencer_mentions']     = float(a4.get('influencer_mentions', 0))
        features['narrative_theme_count']   = float(len(a4.get('narrative_themes', {})))
        features['agent4_score']            = float(a4.get('score', 0))

        # ── DEX (DexScreener) Raw Metrics ────────────────────────────────
        dex = dex_data or {}
        pair_data = dex.get('info', dex)
        features['liquidity_usd']           = float(pair_data.get('liquidity', {}).get('usd', 0) if isinstance(pair_data.get('liquidity'), dict) else 0)
        features['volume_h24']              = float(pair_data.get('volume', {}).get('h24', 0) if isinstance(pair_data.get('volume'), dict) else 0)
        features['volume_h1']               = float(pair_data.get('volume', {}).get('h1', 0) if isinstance(pair_data.get('volume'), dict) else 0)
        features['price_change_h1']         = float(pair_data.get('priceChange', {}).get('h1', 0) if isinstance(pair_data.get('priceChange'), dict) else 0)
        features['price_change_h24']        = float(pair_data.get('priceChange', {}).get('h24', 0) if isinstance(pair_data.get('priceChange'), dict) else 0)
        features['txns_h1_buys']            = float(pair_data.get('txns', {}).get('h1', {}).get('buys', 0) if isinstance(pair_data.get('txns'), dict) else 0)

        # ── pump.fun Launch Signals ────────────────────────────────────────
        pf = pumpfun_data or {}
        features['pumpfun_bonding_curve_pct']  = float(pf.get('bonding_curve_pct', 0))
        features['pumpfun_reply_count']        = float(pf.get('reply_count', 0))
        features['pumpfun_has_twitter']        = 1.0 if pf.get('twitter') else 0.0
        features['pumpfun_has_telegram']       = 1.0 if pf.get('telegram') else 0.0
        features['pumpfun_graduated']          = 1.0 if pf.get('complete') else 0.0

        # ── Derived Composite Signals (from PDF formula) ──────────────────
        social_score = min(1.0, (
            features['reddit_mention_count'] * 0.4 +
            features['reddit_upvote_velocity'] * 0.3 +
            features['reddit_comment_velocity'] * 0.3
        ) / 10)

        liquidity_score = min(1.0, features['liquidity_usd'] / 100_000)

        smart_money_score = min(1.0, (
            features['smart_wallet_count'] * 0.3 +
            features['copy_trade_win_rate'] * 0.4 +
            features['is_priority_signal'] * 0.3
        ))

        features['social_score']       = social_score
        features['liquidity_score']    = liquidity_score
        features['smart_money_score']  = smart_money_score

        # Master signal score from PDF: social*0.3 + liquidity*0.4 + smart*0.3
        features['pdf_signal_score'] = (
            social_score * 0.3 +
            liquidity_score * 0.4 +
            smart_money_score * 0.3
        )

        # ── Metadata (not used in model, for logging only) ─────────────────
        features['_token_address']   = token_address
        features['_timestamp']       = datetime.utcnow().isoformat()
        features['_feature_version'] = self.FEATURE_VERSION

        return features

    async def save(self, features: Dict, trade_id: str, data_dir: str = 'src/ml/data'):
        """Save a feature vector to disk for future training."""
        import asyncio
        os.makedirs(data_dir, exist_ok=True)
        filepath = os.path.join(data_dir, f"features_{trade_id}.json")
        
        def _save_sync():
            with open(filepath, 'w') as f:
                json.dump(features, f, indent=2)
        
        try:
            await asyncio.to_thread(_save_sync)
            logger.info(f"[ML] Feature vector saved: {filepath}")
        except Exception as e:
            logger.error(f"[ML] Failed to save features: {e}")

    def get_model_input(self, features: Dict) -> list:
        """Extract only numeric features (excludes _metadata keys) as ordered list."""
        return [v for k, v in features.items() if not k.startswith('_')]

    def get_feature_names(self, features: Dict) -> list:
        """Return feature names in the same order as get_model_input()."""
        return [k for k in features.keys() if not k.startswith('_')]
