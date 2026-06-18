#!/usr/bin/env python3
"""
AGENT 5: Signal Aggregator - Consensus & Confluence Validator
Role: Cross-reference cleared signals from Agents 1-4, detect confluence, 
       assign composite confidence score. Nothing reaches Command Division without passing here.
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

# Import Master Trading Rules Engine (INTEGRATION POINT 1)
from src.rules.trading_rules_engine import TradingRulesEngine
from src.ml.feature_builder import FeatureBuilder
from src.ml.pump_predictor import PumpPredictor

logger = logging.getLogger(__name__)

class Agent5SignalAggregator:
    """Consensus-based signal validation and scoring"""
    
    def __init__(self, config: Dict = None):
        self.config = config or {}
        logger.info("[AGENT_5] Signal Aggregator initialized")
        
        # Initialize Master Trading Rules Engine (INTEGRATION POINT 1)
        try:
            self.rules_engine = TradingRulesEngine(rules_path='config/trader_rules_master.json')
            logger.info("[AGENT_5] ✅ Master Trading Rules Engine loaded (15 rules, 10 categories)")
        except Exception as e:
            logger.warning(f"[AGENT_5] ⚠️ Master Rules Engine failed to load: {e} (will continue without rules validation)")
            self.rules_engine = None
        
        # ML scoring layer
        try:
            self.feature_builder = FeatureBuilder()
            self.pump_predictor  = PumpPredictor()
            logger.info(f"[AGENT_5] ✅ ML Pump Predictor loaded (mode: {self.pump_predictor.get_mode()})")
        except Exception as e:
            logger.warning(f"[AGENT_5] ⚠️ ML Predictor not available: {e}")
            self.feature_builder = None
            self.pump_predictor  = None
        
        # Scoring configuration - STATIC DEFAULTS (overridden by market regime)
        self.weights_default = {
            'agent_3': 0.40,  # Wallet Tracker (smartest money)
            'agent_2': 0.25,  # Safety baseline
            'agent_4': 0.20,  # Community Intel
            'agent_1': 0.15   # Researcher discovery
        }
        
        # Dynamic weighting by market regime (NEW - March 6, 2026)
        self.weights_by_regime = {
            'bullish': {
                'agent_3': 0.35,  # Reduce wallet weighting (momentum matters more)
                'agent_2': 0.20,  # Less strict on safety (risk acceptable)
                'agent_4': 0.25,  # Boost community (FOMO driving)
                'agent_1': 0.20   # Discovery more important (new money in)
            },
            'mixed': {  # DEFAULT (most conservative)
                'agent_3': 0.40,  # Wallet Tracker most important
                'agent_2': 0.25,  # Safety critical
                'agent_4': 0.20,  # Community secondary
                'agent_1': 0.15   # Discovery tertiary
            },
            'choppy': {
                'agent_3': 0.50,  # PRIORITIZE smart money (only reliable signal)
                'agent_2': 0.30,  # Strict safety (volatility = risk)
                'agent_4': 0.10,  # Community noise is high
                'agent_1': 0.10   # Discovery less relevant
            },
            'flat': {
                'agent_3': 0.45,  # Still important (sideways = accumulation detection)
                'agent_2': 0.25,  # Standard safety
                'agent_4': 0.15,  # Community signals diluted
                'agent_1': 0.15   # Discovery relevant
            }
        }
        
        # Use default initially (will be set based on market regime)
        self.weights = self.weights_default.copy()
        
        # Confluence multipliers (based on number of independent confirmations)
        self.confluence_multipliers = {
            1: 1.0,   # Single source (previously capped at 6.0, now allows >9.0 outliers)
            2: 1.2,   # Dual confirmation
            3: 1.4,   # Triple confirmation
            4: 1.6    # Quad confirmation
        }
        
        # Time windows
        self.optimal_window_min = 15  # minutes (token must be 15+ min old)
        self.optimal_window_max = 45  # minutes (token must be 45- min old)
        self.decay_interval = 15      # minutes (score decays -15% every 15 min)
        self.decay_rate = 0.15        # 15% per interval
        self.kill_age = 45            # minutes (signal killed if older than this)
        self.velocity_window = 5      # minutes (for velocity bonus)
        
        # Pass threshold (reduced from 8.0 to 6.0 for higher volume)
        self.min_pass_score = 6.0
        
        self.db = None
    
    # ============================================================
    # MARKET REGIME & DYNAMIC WEIGHTING (NEW - March 6, 2026)
    # ============================================================
    
    def detect_market_regime(self) -> str:
        """
        Detect current market regime and return regime name
        
        Returns: 'bullish' | 'mixed' | 'choppy' | 'flat'
        
        Could be enhanced with:
        - Recent token success rate (bullish if >50% win rate)
        - Volatility index (choppy if >20% daily swings)
        - Volume trends (flat if volume declining)
        """
        # For now, read from config (would be enhanced with live data)
        regime = self.config.get('market_regime', 'mixed').lower()
        
        if regime not in self.weights_by_regime:
            regime = 'mixed'
        
        return regime
    
    def set_weights_for_regime(self, regime: str = None):
        """
        Dynamically set Agent 5 weights based on market regime
        
        Args:
            regime: Market regime (bullish/mixed/choppy/flat)
                    If None, detects automatically
        """
        if regime is None:
            regime = self.detect_market_regime()
        
        if regime in self.weights_by_regime:
            old_weights = self.weights.copy()
            self.weights = self.weights_by_regime[regime].copy()
            
            logger.info(f"[AGENT_5] Market Regime: {regime.upper()}")
            logger.info(f"[AGENT_5] Updated weights: A3={self.weights['agent_3']:.0%}, A2={self.weights['agent_2']:.0%}, A4={self.weights['agent_4']:.0%}, A1={self.weights['agent_1']:.0%}")
        else:
            logger.warning(f"[AGENT_5] Unknown regime '{regime}', using default")
            self.weights = self.weights_default.copy()
    
    # ============================================================
    # CONFLUENCE & INDEPENDENCE CHECKING
    # ============================================================
    
    def detect_confluence(self, signals: Dict[str, Dict]) -> Tuple[int, List[str]]:
        """
        Detect how many independent sources confirmed this token
        
        Args:
            signals: Dict with keys agent_1, agent_2, agent_3, agent_4
                    Each has 'cleared' (bool) and other metadata
        
        Returns:
            (source_count, independent_sources)
        """
        cleared_sources = []
        
        for agent_key in ['agent_1', 'agent_2', 'agent_3', 'agent_4']:
            if signals.get(agent_key, {}).get('cleared'):
                cleared_sources.append(agent_key)
        
        return len(cleared_sources), cleared_sources
    
    def check_independence(self, signals: Dict[str, Dict], cleared_sources: List[str]) -> Tuple[bool, float]:
        """
        Check if sources are truly independent or reacting to same public data
        
        Red flags for dependency:
        - Agent 2 + Agent 3 analyzing same wallet data
        - Agent 4 Discord + Agent 1 Telegram = same community
        - Multiple agents referencing same trending pair
        
        Args:
            signals: Full signal data from all agents
            cleared_sources: List of agents that cleared the token
        
        Returns:
            (is_independent, multiplier_reduction)
        """
        try:
            if len(cleared_sources) <= 1:
                # Single source is always "independent" (no dependency to detect)
                return True, 1.0
            
            dependency_count = 0
            
            # Check Agent 2 + 3 dependency (both analyzing wallet data)
            if 'agent_2' in cleared_sources and 'agent_3' in cleared_sources:
                # If Agent 3 detected wallets BECAUSE of Agent 2 discovery, dependency
                agent_2_discovery = signals.get('agent_2', {}).get('discovery_source')
                agent_3_inputs = signals.get('agent_3', {}).get('data_sources', [])
                
                if agent_2_discovery in agent_3_inputs:
                    dependency_count += 1
                    logger.debug("[AGENT_5] Dependency: Agent 2 → Agent 3")
            
            # Check Agent 4 community + Agent 1 discovery (same community)
            if 'agent_4' in cleared_sources and 'agent_1' in cleared_sources:
                agent_4_discord = signals.get('agent_4', {}).get('community', {}).get('discord', {})
                agent_1_source = signals.get('agent_1', {}).get('discovery_source')
                
                if agent_1_source == 'discord' and agent_4_discord.get('server_found'):
                    dependency_count += 1
                    logger.debug("[AGENT_5] Dependency: Agent 1 → Agent 4")
            
            # Calculate independence score
            # Each dependency reduces confidence
            # 0 dependencies = fully independent (no reduction)
            # 1 dependency = 10% reduction
            # 2 dependencies = 20% reduction
            reduction = 1.0 - (dependency_count * 0.1)
            reduction = max(0.8, reduction)  # Floor at 80% (not too harsh)
            
            is_independent = dependency_count == 0
            
            if not is_independent:
                logger.info(f"[AGENT_5] Detected {dependency_count} dependencies - multiplier reduction: {reduction:.1%}")
            
            return is_independent, reduction
            
        except Exception as e:
            logger.warning(f"[AGENT_5] Error checking independence: {e}")
            return True, 1.0
    
    # ============================================================
    # SCORING & TIME MODIFIERS
    # ============================================================
    
    def calculate_base_score(self, signals: Dict[str, Dict], cleared_sources: List[str]) -> float:
        """
        Calculate base weighted score from cleared agents
        
        Args:
            signals: Signal data from each agent
            cleared_sources: Which agents cleared the token
        
        Returns:
            Weighted score (0-10)
        """
        if not cleared_sources:
            return 0.0
        
        total_score = 0.0
        total_weight = 0.0
        
        for agent_key in cleared_sources:
            agent_score = signals.get(agent_key, {}).get('score', 5.0)
            weight = self.weights.get(agent_key, 0.0)
            
            total_score += agent_score * weight
            total_weight += weight
        
        # Normalize by actual weights (not all agents may have cleared)
        if total_weight > 0:
            base_score = total_score / total_weight
        else:
            base_score = 0.0
        
        logger.debug(f"[AGENT_5] Base score: {base_score:.2f} (sources: {len(cleared_sources)})")
        return base_score
    
    def apply_confluence_multiplier(self, base_score: float, source_count: int, 
                                  independence: float) -> float:
        """
        Apply confluence multiplier based on number of independent sources
        
        Multipliers:
        - 1 source: ×1.0 (now allows >9.0 if score is high enough)
        - 2 sources: ×1.2
        - 3 sources: ×1.4
        - 4 sources: ×1.6
        
        Args:
            base_score: Base weighted score
            source_count: Number of cleared sources
            independence: Independence reduction factor (0.8-1.0)
        
        Returns:
            Multiplied score
        """
        multiplier = self.confluence_multipliers.get(source_count, 1.0)
        
        # Apply independence reduction to multiplier
        multiplier *= independence
        
        # Apply cap for single-source signals
        if source_count == 1:
            multiplier = 1.0
            # NEW: Allow single source if the base score is exceptional (> 9.0)
            if base_score > 9.0:
                logger.info(f"[AGENT_5] 🌟 Exceptional single source: {base_score:.2f} (allowed above 6.0 cap)")
                return base_score
            
            capped_score = min(base_score, 6.0)  # Standard single source caps at 6/10
            logger.debug(f"[AGENT_5] Single source: {base_score:.2f} → {capped_score:.2f} (standard cap 6.0)")
            return capped_score
        
        # For multi-source, apply multiplier
        result_score = base_score * multiplier
        logger.debug(f"[AGENT_5] Confluence ×{multiplier:.2f}: {base_score:.2f} → {result_score:.2f}")
        
        return result_score
    
    def apply_velocity_bonus(self, current_score: float, signals: Dict[str, Dict],
                            cleared_sources: List[str]) -> Tuple[float, bool]:
        """
        Velocity bonus: +0.5 if two confirmations arrive within 5 minutes of each other
        
        Args:
            current_score: Score before velocity bonus
            signals: Signal metadata with timestamps
            cleared_sources: Which agents cleared
        
        Returns:
            (score_with_bonus, bonus_applied)
        """
        if len(cleared_sources) < 2:
            return current_score, False
        
        try:
            timestamps = []
            for agent_key in cleared_sources:
                ts = signals.get(agent_key, {}).get('analysis_timestamp')
                if ts:
                    timestamps.append(datetime.fromisoformat(ts))
            
            if len(timestamps) < 2:
                return current_score, False
            
            timestamps.sort()
            time_diff = (timestamps[-1] - timestamps[0]).total_seconds() / 60
            
            if time_diff <= self.velocity_window:
                bonus_score = current_score + 0.5
                logger.info(f"[AGENT_5] Velocity bonus: +0.5 ({time_diff:.1f} min apart) → {bonus_score:.2f}")
                return min(bonus_score, 10.0), True
            
            return current_score, False
            
        except Exception as e:
            logger.warning(f"[AGENT_5] Velocity bonus error: {e}")
            return current_score, False
    
    def apply_time_decay(self, current_score: float, token_age_minutes: float) -> float:
        """
        Time decay: Score drops 15% every 15 minutes unconfirmed
        Signal killed at 45 minutes
        
        Args:
            current_score: Score before decay
            token_age_minutes: Age of token in minutes
        
        Returns:
            Score after decay (or None if killed)
        """
        if token_age_minutes >= self.kill_age:
            logger.warning(f"[AGENT_5] Signal KILLED: Token age {token_age_minutes:.1f}min (max {self.kill_age}min)")
            return None
        
        intervals_elapsed = int(token_age_minutes / self.decay_interval)
        decay_factor = (1 - self.decay_rate) ** intervals_elapsed
        decayed_score = current_score * decay_factor
        
        if intervals_elapsed > 0:
            logger.debug(f"[AGENT_5] Time decay: {current_score:.2f} × {decay_factor:.2f} = {decayed_score:.2f} ({intervals_elapsed}×{self.decay_rate:.0%})")
        
        return decayed_score
    
    def apply_age_penalty(self, current_score: float, token_age_minutes: float) -> float:
        """
        Age penalty: Token outside 15-45 minute optimal window gets explicit penalty
        
        Args:
            current_score: Score before penalty
            token_age_minutes: Age of token in minutes
        
        Returns:
            Score after penalty
        """
        if self.optimal_window_min <= token_age_minutes <= self.optimal_window_max:
            # Perfect window - no penalty
            return current_score
        
        if token_age_minutes < self.optimal_window_min:
            # Too young (< 15 min) - might be pump
            penalty = 1.0  # 1 point penalty
            penalized = current_score - penalty
            logger.info(f"[AGENT_5] Age penalty (too young): -{penalty:.1f} → {penalized:.2f}")
            return penalized
        
        if token_age_minutes > self.optimal_window_max:
            # Too old (> 45 min) - should have killed by decay
            penalty = 1.5  # 1.5 point penalty
            penalized = current_score - penalty
            logger.info(f"[AGENT_5] Age penalty (too old): -{penalty:.1f} → {penalized:.2f}")
            return penalized
        
        return current_score
    
    # ============================================================
    # AGGREGATION & FINAL DECISION
    # ============================================================
    
    async def aggregate_signal(self, token_address: str, token_symbol: str,
                        signals: Dict[str, Dict], discovered_at: str, market_regime: str = None) -> Optional[Dict]:
        """
        Aggregate all agent signals into single composite score and decision
        
        Args:
            token_address: Token address
            token_symbol: Token symbol
            signals: Dict with agent_1, agent_2, agent_3, agent_4 results
            discovered_at: ISO timestamp when token was discovered
            market_regime: Optional market regime (bullish/mixed/choppy/flat)
        
        Returns:
            Aggregated signal with composite score, or None if killed
        """
        logger.info(f"[AGENT_5] Aggregating signal for {token_symbol}")
        
        try:
            # STEP 0: Set dynamic weights based on market regime
            self.set_weights_for_regime(market_regime)

            # STEP 0.1: Check for Agent 0 Commander Overrides in DB
            if self.db:
                try:
                    # Check for min score override
                    score_override = await self.db.get_system_state("agent_5_min_score")
                    if score_override:
                        self.min_pass_score = float(score_override)
                        logger.info(f"[AGENT_5] 🎖️ COMMAND OVERRIDE: min_pass_score={self.min_pass_score}")

                    # Check for weight overrides
                    weights_override_json = await self.db.get_system_state("agent_weights_json")
                    if weights_override_json:
                        weights_override = json.loads(weights_override_json)
                        self.weights.update(weights_override)
                        logger.info(f"[AGENT_5] 🎖️ COMMAND OVERRIDE: weights={self.weights}")
                except Exception as e:
                    logger.error(f"[AGENT_5] Failed to apply Commander overrides: {e}")
            
            # Step 1: Detect confluence
            source_count, cleared_sources = self.detect_confluence(signals)
            
            if source_count == 0:
                logger.warning(f"[AGENT_5] No cleared sources - KILLED")
                return None
            
            # Step 2: Check independence
            is_independent, independence_factor = self.check_independence(signals, cleared_sources)
            
            # Step 3: Calculate base score
            base_score = self.calculate_base_score(signals, cleared_sources)
            
            # Step 4: Apply confluence multiplier
            score = self.apply_confluence_multiplier(base_score, source_count, independence_factor)
            
            # Step 5: Calculate token age and apply time decay
            discovered_dt = datetime.fromisoformat(discovered_at)
            token_age_min = (datetime.utcnow() - discovered_dt).total_seconds() / 60
            
            score = self.apply_time_decay(score, token_age_min)
            if score is None:
                return None  # Killed by time decay
            
            # Step 6: Apply age penalty
            score = self.apply_age_penalty(score, token_age_min)
            score = max(0, score)  # Floor at 0
            
            # Step 7: Apply velocity bonus
            score, velocity_bonus = self.apply_velocity_bonus(score, signals, cleared_sources)
            
            # Step 7.1: Apply Narrative & Priority Bonuses (NEW - March 10, 2026)
            is_priority = any(signals.get(a, {}).get('is_priority') for a in cleared_sources)
            narrative_bonus = signals.get('agent_4', {}).get('narrative_bonus_awarded', False)
            
            if is_priority:
                score += 1.5  # Heavy boost for priority smart money
                logger.info(f"🚨 [AGENT_5] PRIORITY SIGNAL DETECTED: +1.5 Bonus → {score:.2f}")
                
            if narrative_bonus:
                score += 0.5  # Bonus move if it aligns with underground narrative
                logger.debug(f"✨ [AGENT_5] Narrative Alignment Bonus: +0.5 → {score:.2f}")

            # Step 7.2: ML Pump Probability Layer
            pump_prob = 0.5  # neutral default
            if self.pump_predictor and self.feature_builder:
                try:
                    # Generate trade_id BEFORE build() so it's embedded in the feature vector
                    trade_id = f"signal_{token_address[:8]}_{int(datetime.utcnow().timestamp())}"
                    
                    features = self.feature_builder.build(
                        token_address=token_address,
                        agent_1_data=signals.get('agent_1'),
                        agent_2_data=signals.get('agent_2'),
                        agent_3_data=signals.get('agent_3'),
                        agent_4_data=signals.get('agent_4'),
                        dex_data=signals.get('token_data'),
                        pumpfun_data=signals.get('pumpfun_data'),
                        trade_id=trade_id
                    )
                    pump_prob = self.pump_predictor.predict(features)
                    
                    # Save features for training (Async)
                    await self.feature_builder.save(features, trade_id)
                    
                    # 65% rule-based, 35% ML blend
                    ml_boost = (pump_prob - 0.5) * 2.0    # scale to +/- 1.0
                    score = (score * 0.65) + (ml_boost * 0.35)
                    logger.info(f"🧠 [AGENT_5] ML pump_prob={pump_prob:.3f} → blended score={score:.2f}")
                except Exception as e:
                    logger.warning(f"[AGENT_5] ML inference failed: {e}")

            # Step 8: Determine confidence
            confidence = self._calculate_confidence(source_count, is_independent, velocity_bonus or is_priority)
            
            # STEP 9: ✨ INTEGRATION POINT 1 - Validate with Master Trading Rules (NEW)
            rules_validation = None
            rules_pass = True  # Default if rules engine unavailable
            
            # Only validate if Agent 5 confidence is high (score >= 8.0)
            if score >= self.min_pass_score:
                # Try to validate with Master Rules if token_data available
                if 'token_data' in signals and signals['token_data']:
                    rules_validation = self.validate_with_master_rules(token_address, signals['token_data'])
                    if rules_validation:
                        rules_pass = rules_validation.get('pass', True)
                        # Apply position multiplier from rules
                        if 'position_size_multiplier' in rules_validation:
                            rules_multiplier = rules_validation['position_size_multiplier']
                        else:
                            rules_multiplier = 1.0
                    else:
                        rules_multiplier = 1.0
                else:
                    logger.debug("[AGENT_5] No token_data provided for Master Rules validation")
                    rules_multiplier = 1.0
            else:
                rules_pass = False
                rules_multiplier = 1.0
            
            # Step 10: Final decision (both Agent 5 AND Master Rules must pass)
            if score >= self.min_pass_score and rules_pass:
                status = "CLEARED"
            elif score < self.min_pass_score:
                status = "KILLED_AGENT5_GATE"
            else:
                status = "KILLED_MASTER_RULES_GATE"
            
            result = {
                "agent_id": 5,
                "token_address": token_address,
                "token_symbol": token_symbol,
                "analysis_timestamp": datetime.utcnow().isoformat(),
                "status": status,
                "composite_score": round(score, 2),
                "confidence": confidence,
                
                "sources": {
                    "source_count": source_count,
                    "cleared_agents": cleared_sources,
                    "is_independent": is_independent,
                    "independence_factor": independence_factor
                },
                
                "scoring_breakdown": {
                    "base_score": round(base_score, 2),
                    "confluence_multiplier": self.confluence_multipliers.get(source_count, 1.0),
                    "velocity_bonus_applied": velocity_bonus,
                    "time_decay_applied": token_age_min > 0,
                    "age_penalty_applied": token_age_min < self.optimal_window_min or token_age_min > self.optimal_window_max,
                    "token_age_minutes": round(token_age_min, 1)
                },
                
                "agent_scores": {
                    agent_key: {
                        "score": signals.get(agent_key, {}).get('score'),
                        "weight": self.weights.get(agent_key)
                    }
                    for agent_key in cleared_sources
                },
                
                # INTEGRATION POINT 1: Master Trading Rules validation results
                "master_rules_validation": rules_validation,
                "master_rules_passed": rules_pass,
                "position_size_multiplier": rules_multiplier,
                
                "failure_reason": (
                    f"Score {score:.2f} below {self.min_pass_score} threshold" if status == "KILLED_AGENT5_GATE"
                    else "Failed Master Trading Rules validation" if status == "KILLED_MASTER_RULES_GATE"
                    else None
                )
            }
            
            logger.info(f"[AGENT_5] Final: {token_symbol} = {score:.2f}/10 (Master Rules: {'✅ PASS' if rules_pass else '❌ FAIL'}) → {status}")
            
            return result
            
        except Exception as e:
            logger.error(f"[AGENT_5] Aggregation error: {e}")
            return None
    
    def _calculate_confidence(self, source_count: int, is_independent: bool, 
                             velocity_bonus: bool) -> float:
        """Calculate final confidence score (0-1.0)"""
        confidence = 0.5  # Base
        
        # Boost for source count
        confidence += (source_count - 1) * 0.15  # +0.15 per source beyond 1
        
        # Boost for independence
        if is_independent:
            confidence += 0.1
        
        # Boost for velocity
        if velocity_bonus:
            confidence += 0.1
        
        return min(1.0, confidence)
    
    def validate_with_master_rules(self, token_address: str, token_data: Dict) -> Optional[Dict]:
        """
        INTEGRATION POINT 1: Validate token against Master Trading Rules
        
        Evaluates token across 15 rules in 10 categories:
        - Tier 1: 4 critical rules (all must pass)
        - Tier 2: 5 recommended rules (3+ must pass)
        - Tier 3: 4 complementary rules (pick 1-2)
        
        Args:
            token_address: Solana token address
            token_data: Complete token metadata (market cap, holders, community, fees, etc.)
        
        Returns:
            {
                'pass': bool,
                'score': 0-10,
                'position_multiplier': 0.5-2.0,
                'failure_reasons': list,
                'tier_1_passed': int,
                'tier_2_passed': int,
                'tier_3_passed': int
            }
        """
        if not self.rules_engine:
            logger.warning("[AGENT_5] Master Rules Engine not available, skipping validation")
            return None
        
        try:
            result = self.rules_engine.evaluate_token_comprehensive(token_data)
            
            logger.info(f"""
[MASTER_RULES] Validation Result for {token_address[:16]}...
├─ Pass: {'✅ YES' if result['pass'] else '❌ NO'}
├─ Score: {result['overall_score']:.1f}/10
├─ Position Multiplier: {result['position_size_multiplier']:.2f}x
├─ Tier 1 (Critical): {result['tier_1_passed']}/{result['tier_1_total']}
├─ Tier 2 (Recommended): {result['tier_2_passed']}/{result['tier_2_total']}
└─ Tier 3 (Complementary): {result['tier_3_passed']}/{result['tier_3_total']}
""")
            
            return result
            
        except Exception as e:
            logger.error(f"[AGENT_5] Master Rules validation error: {e}")
            return None

    async def log_to_database(self, analysis_result: Dict):
        """Log aggregated signal to database"""
        if not self.db:
            logger.warning("[AGENT_5] Database not available, skipping log")
            return
        
        try:
            # Create agent_5_analysis table entry
            # (would need to extend database schema for full Agent 5 tracking)
            # For now, Agent 5 mainly used for command division but we could log it
            await self.db.log_agent_analysis("agent_5", analysis_result) # Generic log
            logger.info(f"[AGENT_5] Signal aggregated and stored: {analysis_result['token_symbol']}")
        except Exception as e:
            logger.error(f"[AGENT_5] Error logging to database: {e}")


if __name__ == '__main__':
    logger.info("✅ Agent 5 module loaded")
