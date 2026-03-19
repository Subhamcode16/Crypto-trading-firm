"""
Trading Rules Engine - Master Rule Engine Implementation
Synthesized from 4 expert traders' systems
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger('rules_engine')


class TradingRulesEngine:
    """
    Applies consensus rules from 4 expert traders to token evaluation
    
    Rules sourced from:
    - Video 1: Position sizing + market cap analysis
    - Video 2: Token filtering + scam detection + psychology
    - Video 3: Insider wallet tracking
    - Video 4: Execution + fee optimization + account scaling
    """
    
    def __init__(self, rules_path='config/trader_rules_master.json'):
        """Initialize rules engine with JSON config"""
        rules_file = Path(__file__).parent.parent.parent / rules_path
        
        with open(rules_file) as f:
            self.rules = json.load(f)
        
        logger.info(f"✅ Rules engine loaded: {self.rules['name']} v{self.rules['version']}")
    
    # ============================================================================
    # TIER 1: CRITICAL RULES (All 4 Traders Agree)
    # ============================================================================
    
    def evaluate_market_cap(self, market_cap_usd: float) -> Dict[str, Any]:
        """Rule 1: Market cap must be within range"""
        min_cap = self.rules['market_cap_rules']['minimum_market_cap_usd']
        
        if market_cap_usd < min_cap:
            return {
                "pass": False,
                "reason": f"Market cap ${market_cap_usd:,} below minimum ${min_cap:,}",
                "confidence": 2
            }
        
        return {
            "pass": True,
            "reason": f"Market cap ${market_cap_usd:,} acceptable",
            "confidence": 8
        }
    
    def get_position_size_multiplier(self, market_cap_usd: float) -> float:
        """Rule 1 Extended: Position size adjusted by market cap risk tier"""
        tiers = self.rules['market_cap_rules']['position_size_tiers']
        
        for cap_range, multiplier in tiers.items():
            if '-' in cap_range:
                low, high = map(int, cap_range.split('-'))
                if low <= market_cap_usd < high:
                    logger.info(f"Market cap tier: ${low:,}-${high:,} → {multiplier}x multiplier")
                    return multiplier
        
        # Default for highest tier
        return 1.0
    
    def evaluate_holder_concentration(self, 
                                     top_holder_pct: float, 
                                     top_10_pct: float,
                                     bundle_pct: float,
                                     gini_coefficient: Optional[float] = None) -> Dict[str, Any]:
        """Rule 2: Holder distribution must be clean"""
        rules = self.rules['holder_rules']
        
        # Check individual top holder
        if top_holder_pct > rules['red_flag_holder_percentage']:
            return {
                "pass": False,
                "reason": f"Top holder {top_holder_pct:.1f}% exceeds red flag {rules['red_flag_holder_percentage']:.1%}",
                "confidence": 2
            }
        
        if top_holder_pct > rules['max_single_holder_percentage']:
            logger.warning(f"Top holder at {top_holder_pct:.1f}% - threshold warning")
        
        # Check top 10 concentration
        if top_10_pct > rules['top_10_concentration_max']:
            return {
                "pass": False,
                "reason": f"Top 10 concentration {top_10_pct:.1f}% exceeds limit {rules['top_10_concentration_max']:.1%}",
                "confidence": 3
            }
        
        # Check bundle percentage
        if bundle_pct > rules['max_bundle_percentage']:
            return {
                "pass": False,
                "reason": f"Bundle percentage {bundle_pct:.1f}% exceeds limit {rules['max_bundle_percentage']:.1%}",
                "confidence": 4
            }
        
        # Check Gini coefficient if provided
        if gini_coefficient and gini_coefficient > rules['gini_coefficient_max']:
            return {
                "pass": False,
                "reason": f"Gini coefficient {gini_coefficient:.2f} exceeds limit {rules['gini_coefficient_max']}",
                "confidence": 3
            }
        
        return {
            "pass": True,
            "reason": "Holder distribution looks clean",
            "confidence": 8
        }
    
    def validate_community(self, has_community: bool, is_active: bool, 
                          posting_frequency_minutes: Optional[float] = None) -> Dict[str, Any]:
        """Rule 3: Community must exist AND be active"""
        if not has_community:
            return {
                "pass": False,
                "reason": "No community detected",
                "confidence": 3
            }
        
        if not is_active:
            return {
                "pass": False,
                "reason": "Community exists but is stagnant (not active)",
                "confidence": 4
            }
        
        if posting_frequency_minutes:
            min_freq = self.rules['community_rules']['posting_frequency_min_minutes']
            if posting_frequency_minutes > min_freq:
                logger.warning(f"Community posting frequency {posting_frequency_minutes}m > {min_freq}m threshold")
        
        return {
            "pass": True,
            "reason": "Community exists and is active",
            "confidence": 8
        }
    
    def get_psychology_rules(self) -> Dict[str, bool]:
        """Rule 4: Psychology discipline rules (most important)"""
        return {rule: True for rule in self.rules['psychology_rules']['rules']}
    
    def check_fee_impact(self, position_usd: float, platform_fees_usd: float) -> Dict[str, Any]:
        """Rule 5: Calculate fee impact on small positions"""
        min_position = self.rules['fee_optimization']['minimum_profitable_position_usd']
        
        if position_usd < min_position:
            breakeven_pct = (platform_fees_usd / position_usd) * 100
            return {
                "pass": False,
                "reason": f"Position ${position_usd} too small for ${platform_fees_usd} fees",
                "breakeven_percentage": breakeven_pct,
                "confidence": 2
            }
        
        breakeven_pct = (platform_fees_usd / position_usd) * 100
        return {
            "pass": True,
            "reason": f"Position ${position_usd} large enough for ${platform_fees_usd} fees",
            "breakeven_percentage": breakeven_pct,
            "confidence": 8
        }
    
    # ============================================================================
    # TIER 2: HIGHLY RECOMMENDED RULES
    # ============================================================================
    
    def detect_scam_via_global_fees(self, market_cap_usd: float, 
                                   global_fees_paid_sol: float) -> Dict[str, Any]:
        """Rule 6 (Video 2): Detect scams via global fees paid metric"""
        if global_fees_paid_sol <= 0:
            return {
                "fraud_risk": "UNKNOWN",
                "reason": "No fee data available"
            }
        
        ratio = global_fees_paid_sol / (market_cap_usd / 1_000_000)
        min_ratio = self.rules['scam_detection_rules']['global_fees_to_market_cap_ratio_min']
        
        if ratio < min_ratio:
            return {
                "fraud_risk": "HIGH",
                "reason": f"Fee ratio {ratio:.2f} < {min_ratio} (likely bundlers/bots, not real volume)",
                "ratio": ratio
            }
        
        return {
            "fraud_risk": "LOW",
            "reason": f"Fee ratio {ratio:.2f} suggests real people trading",
            "ratio": ratio
        }
    
    def get_narrative_bonus(self, token_name: str, token_description: str, 
                           social_data: Optional[str] = None) -> Dict[str, Any]:
        """Rule 7 (Video 1): Detect narrative strength and return confidence bonus"""
        narratives = self.rules['narrative_rules']['strong_narratives']
        
        combined_text = f"{token_name} {token_description}".lower()
        if social_data:
            combined_text += f" {social_data}".lower()
        
        narrative_bonus = 0
        detected = []
        
        for narrative, bonus in narratives.items():
            if narrative in combined_text:
                narrative_bonus += bonus
                detected.append(narrative)
        
        narrative_bonus = min(narrative_bonus, self.rules['narrative_rules']['max_narrative_boost'])
        
        if detected:
            logger.info(f"🎯 Narratives detected: {detected} (bonus: +{narrative_bonus})")
        
        return {
            "bonus": narrative_bonus,
            "detected_narratives": detected,
            "max_bonus": self.rules['narrative_rules']['max_narrative_boost']
        }
    
    def detect_migration_dump_setup(self, just_migrated: bool, dump_percentage: float,
                                   floor_held: bool, price_pushing_up: bool) -> Dict[str, Any]:
        """Rule 8 (Video 4): Detect post-migration dump & pump setup"""
        if not just_migrated:
            return {"setup_ready": False, "reason": "Token not recently migrated"}
        
        expected_dump = self.rules['migration_dump_rules']['expect_dump_percentage']
        
        if dump_percentage < expected_dump:
            return {
                "setup_ready": False,
                "reason": f"Dump {dump_percentage:.0%} below expected {expected_dump:.0%}"
            }
        
        if not floor_held:
            return {
                "setup_ready": False,
                "reason": "Floor not established yet"
            }
        
        if not price_pushing_up:
            return {
                "setup_ready": False,
                "reason": "Price not yet pushing back up from floor"
            }
        
        return {
            "setup_ready": True,
            "reason": "Post-migration dump & floor formation detected - ready for rebound entry",
            "dump_percentage": dump_percentage,
            "expected_rebound_target": self.rules['migration_dump_rules']['rebound_target_percentage']
        }
    
    def validate_entry_confirmation(self, has_volume: bool, holders_confident: bool,
                                   floor_formed: bool) -> Dict[str, Any]:
        """Rule 9 (Video 4): Require confirmation before entry (anti-FOMO)"""
        confirmations = sum([has_volume, holders_confident, floor_formed])
        
        if confirmations < 2:
            return {
                "pass": False,
                "reason": f"Only {confirmations}/3 confirmations met - wait longer",
                "confirmations": confirmations
            }
        
        return {
            "pass": True,
            "reason": f"Entry confirmed ({confirmations}/3 signals)",
            "confirmations": confirmations
        }
    
    # ============================================================================
    # TIER 3: COMPLEMENTARY STRATEGIES
    # ============================================================================
    
    def evaluate_insider_wallet(self, win_rate: float, trades_count: int, 
                               is_sniper: bool = False) -> Dict[str, Any]:
        """Rule 10 (Video 3): Evaluate insider wallet for copy-trading"""
        min_wr = self.rules['insider_tracking']['min_win_rate_for_follow']
        
        if win_rate < min_wr:
            return {
                "follow": False,
                "reason": f"Win rate {win_rate:.0%} below threshold {min_wr:.0%}"
            }
        
        if trades_count < 20:
            return {
                "follow": False,
                "reason": f"Too few trades ({trades_count}) - insufficient data"
            }
        
        return {
            "follow": True,
            "reason": f"Insider wallet qualifies (WR: {win_rate:.0%}, trades: {trades_count})",
            "risk_level": "HIGH" if is_sniper else "MEDIUM",
            "recommended_stops": "aggressive" if is_sniper else "normal"
        }
    
    def get_position_size_for_account(self, account_balance_sol: float) -> float:
        """Rule 11 (Video 4): Get position size tier based on account balance"""
        tiers = self.rules['account_scaling']['tiers']
        
        for (min_bal, max_bal), position_size in tiers.items():
            if min_bal <= account_balance_sol < max_bal:
                return position_size
        
        return self.rules['account_scaling']['max_position_size_sol']
    
    def should_take_profit(self, entry_price: float, current_price: float,
                          market_hesitation: bool = False) -> Dict[str, Any]:
        """Rule 12 (Videos 2,4): Flexible profit-taking based on market behavior"""
        profit_pct = ((current_price - entry_price) / entry_price)
        
        min_target = self.rules['exit_rules']['profit_target_min_pct']
        max_target = self.rules['exit_rules']['profit_target_max_pct']
        
        if profit_pct >= max_target:
            return {
                "take_profit": True,
                "reason": f"Hit max target {max_target:.0%}",
                "profit_pct": profit_pct
            }
        
        if profit_pct >= min_target:
            if market_hesitation:
                return {
                    "take_profit": True,
                    "reason": f"Hit min target {min_target:.0%} with market hesitation",
                    "profit_pct": profit_pct
                }
        
        return {
            "take_profit": False,
            "reason": f"Hold (profit {profit_pct:.0%}, waiting for hesitation or {max_target:.0%} target)",
            "profit_pct": profit_pct
        }
    
    def get_stop_loss_level(self, entry_price: float, is_profitable: bool = False) -> Dict[str, Any]:
        """Rule 13 (Video 2): Dynamic stop loss (trail winners, protect losers)"""
        hard_stop = entry_price * (1 + self.rules['exit_rules']['stop_loss_hard_pct'])
        soft_stop = entry_price * (1 + self.rules['exit_rules']['stop_loss_soft_pct'])
        
        if is_profitable:
            # Trail winners: set stop at entry (protect profits)
            return {
                "soft_stop": entry_price * 0.98,  # Just below entry
                "hard_stop": entry_price * 0.95,  # 5% below entry
                "strategy": "profit_protection",
                "reason": "Position in profit - protect gains"
            }
        else:
            # Cut losers: standard stops
            return {
                "soft_stop": soft_stop,
                "hard_stop": hard_stop,
                "strategy": "loss_cutting",
                "reason": "Position down - cut quickly"
            }
    
    # ============================================================================
    # UTILITY METHODS
    # ============================================================================
    
    def evaluate_token_comprehensive(self, token_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Run comprehensive evaluation using ALL rules
        Returns pass/fail + detailed reasoning
        """
        results = {
            "pass": True,
            "reasons": [],
            "warnings": [],
            "confidence": 0,
            "details": {}
        }
        
        # Check market cap
        if token_data.get('market_cap'):
            mc_result = self.evaluate_market_cap(token_data['market_cap'])
            results['details']['market_cap'] = mc_result
            if not mc_result['pass']:
                results['pass'] = False
                results['reasons'].append(mc_result['reason'])
            results['confidence'] = mc_result['confidence']
        
        # Check holders
        if all(k in token_data for k in ['top_holder_pct', 'top_10_pct', 'bundle_pct']):
            holder_result = self.evaluate_holder_concentration(
                token_data['top_holder_pct'],
                token_data['top_10_pct'],
                token_data['bundle_pct'],
                token_data.get('gini_coefficient')
            )
            results['details']['holders'] = holder_result
            if not holder_result['pass']:
                results['pass'] = False
                results['reasons'].append(holder_result['reason'])
            results['confidence'] = min(results['confidence'], holder_result['confidence'])
        
        # Check community
        if 'has_community' in token_data:
            community_result = self.validate_community(
                token_data['has_community'],
                token_data.get('is_active', False),
                token_data.get('posting_frequency_minutes')
            )
            results['details']['community'] = community_result
            if not community_result['pass']:
                results['pass'] = False
                results['reasons'].append(community_result['reason'])
            results['confidence'] = min(results['confidence'], community_result['confidence'])
        
        # Check scams via fees
        if 'market_cap' in token_data and 'global_fees_paid_sol' in token_data:
            fraud_result = self.detect_scam_via_global_fees(
                token_data['market_cap'],
                token_data['global_fees_paid_sol']
            )
            results['details']['fraud_risk'] = fraud_result
            if fraud_result['fraud_risk'] == 'HIGH':
                results['pass'] = False
                results['reasons'].append(fraud_result['reason'])
        
        # Get narrative bonus
        if 'name' in token_data and 'description' in token_data:
            narrative_result = self.get_narrative_bonus(
                token_data['name'],
                token_data['description'],
                token_data.get('social_data')
            )
            results['details']['narrative'] = narrative_result
            results['confidence'] += narrative_result['bonus']
        
        # Clamp confidence 0-10
        results['confidence'] = max(0, min(10, results['confidence']))
        
        return results
    
    def get_all_rules_summary(self) -> Dict[str, Any]:
        """Get summary of all rules loaded"""
        return {
            "version": self.rules['version'],
            "name": self.rules['name'],
            "sources": self.rules['consensus_sources'],
            "tier_1_critical": [
                "Market cap minimum (50K)",
                "Holder concentration (<4%)",
                "Community (active required)",
                "Psychology discipline",
                "Fee awareness",
                "Avoid micro-caps"
            ],
            "tier_2_recommended": [
                "Global fees paid (scam detection)",
                "Narrative bonus",
                "Migration dump & pump",
                "Entry confirmation required",
                "Insider wallet tracking"
            ],
            "tier_3_optional": [
                "Position sizing by confidence",
                "Market cap tiers",
                "ACID test",
                "Small account scaling",
                "Dynamic profit-taking"
            ]
        }
