#!/usr/bin/env python3
"""
Master Rules Feedback Loop System
=================================

Tracks accuracy of each Master Trading Rule across trades.
Enables data-driven rule weight optimization.

Features:
- Per-rule accuracy tracking (% of passed signals that won)
- Category-level analytics (which categories most predictive?)
- Weekly feedback reports
- Auto-adjustment recommendations

Data Structure:
{
    "rule_id": "market_cap_range",
    "rule_name": "Market Cap $100K-$10M",
    "category": "Market Cap",
    "tier": 1,
    "signals_tested": 47,
    "signals_passed": 35,
    "signals_won": 28,
    "signals_lost": 7,
    "win_rate": 0.80,
    "false_positive_rate": 0.20,
    "confidence": 0.95
}
"""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger('master_rules_feedback')


class MasterRulesFeedback:
    """Track Master Rules accuracy and optimize weights"""
    
    def __init__(self, feedback_db_path: str = 'data/rules_feedback.json'):
        """
        Initialize feedback system
        
        Args:
            feedback_db_path: Path to feedback JSON file
        """
        self.feedback_db_path = feedback_db_path
        self.feedback_data = self._load_feedback()
        self.stats = self._calculate_stats()
        
        logger.info(f"✅ Master Rules Feedback System initialized ({feedback_db_path})")
    
    def _load_feedback(self) -> Dict:
        """Load feedback from disk, or create new structure"""
        path = Path(self.feedback_db_path)
        
        if path.exists():
            try:
                with open(path, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load feedback: {e}, starting fresh")
        
        # Initialize empty structure
        return {
            'rules': {},
            'last_updated': datetime.utcnow().isoformat(),
            'version': '1.0'
        }
    
    def _save_feedback(self):
        """Save feedback to disk"""
        try:
            Path(self.feedback_db_path).parent.mkdir(parents=True, exist_ok=True)
            with open(self.feedback_db_path, 'w') as f:
                json.dump(self.feedback_data, f, indent=2)
            logger.debug(f"Feedback saved to {self.feedback_db_path}")
        except Exception as e:
            logger.error(f"Failed to save feedback: {e}")
    
    def record_signal_result(self, signal_id: str, rules_validation: Dict, 
                            trade_result: Dict, won: bool):
        """
        Record the outcome of a signal for feedback
        
        Args:
            signal_id: Unique signal identifier
            rules_validation: Result from TradingRulesEngine.evaluate_token_comprehensive()
            trade_result: Trade outcome (entry, exit, P&L, etc.)
            won: Whether the trade was profitable
        """
        if not rules_validation or 'rules_evaluation' not in rules_validation:
            logger.warning("No rules evaluation data provided")
            return
        
        rules_eval = rules_validation.get('rules_evaluation', {})
        
        # For each rule, record if token passed and if trade won
        for rule_id, rule_eval in rules_eval.items():
            if rule_id not in self.feedback_data['rules']:
                self.feedback_data['rules'][rule_id] = {
                    'rule_id': rule_id,
                    'rule_name': rule_eval.get('rule_name', rule_id),
                    'category': rule_eval.get('category', 'unknown'),
                    'tier': rule_eval.get('tier', 3),
                    'signals_tested': 0,
                    'signals_passed': 0,
                    'signals_won': 0,
                    'signals_lost': 0,
                    'win_rate': 0.0,
                    'false_positive_rate': 0.0,
                    'test_history': []
                }
            
            rule_data = self.feedback_data['rules'][rule_id]
            rule_passed = rule_eval.get('passed', False)
            
            # Record test
            rule_data['signals_tested'] += 1
            
            if rule_passed:
                rule_data['signals_passed'] += 1
                
                if won:
                    rule_data['signals_won'] += 1
                else:
                    rule_data['signals_lost'] += 1
            
            # Recalculate metrics
            if rule_data['signals_passed'] > 0:
                rule_data['win_rate'] = rule_data['signals_won'] / rule_data['signals_passed']
            
            # False positive rate: signals that passed but lost
            if rule_data['signals_passed'] > 0:
                rule_data['false_positive_rate'] = rule_data['signals_lost'] / rule_data['signals_passed']
            
            # Test history (last 20 tests)
            rule_data['test_history'].append({
                'signal_id': signal_id,
                'passed': rule_passed,
                'won': won if rule_passed else None,
                'timestamp': datetime.utcnow().isoformat()
            })
            rule_data['test_history'] = rule_data['test_history'][-20:]
        
        self.feedback_data['last_updated'] = datetime.utcnow().isoformat()
        self._save_feedback()
        self.stats = self._calculate_stats()
    
    def _calculate_stats(self) -> Dict:
        """Calculate aggregate statistics"""
        stats = {
            'total_rules': len(self.feedback_data.get('rules', {})),
            'high_confidence_rules': [],  # >80% win rate
            'low_confidence_rules': [],   # <50% win rate
            'untested_rules': [],
            'category_performance': {}
        }
        
        for rule_id, rule_data in self.feedback_data.get('rules', {}).items():
            win_rate = rule_data.get('win_rate', 0)
            tested = rule_data.get('signals_tested', 0)
            category = rule_data.get('category', 'unknown')
            
            # Track by category
            if category not in stats['category_performance']:
                stats['category_performance'][category] = {
                    'rules': [],
                    'avg_win_rate': 0,
                    'total_tested': 0
                }
            
            stats['category_performance'][category]['rules'].append(rule_id)
            stats['category_performance'][category]['total_tested'] += tested
            
            # Classify confidence
            if tested == 0:
                stats['untested_rules'].append(rule_id)
            elif win_rate >= 0.80:
                stats['high_confidence_rules'].append({
                    'rule_id': rule_id,
                    'win_rate': win_rate,
                    'tested': tested
                })
            elif win_rate < 0.50 and tested >= 5:
                stats['low_confidence_rules'].append({
                    'rule_id': rule_id,
                    'win_rate': win_rate,
                    'tested': tested
                })
        
        # Calculate category averages
        for category in stats['category_performance']:
            rules = stats['category_performance'][category]['rules']
            avg_win_rate = sum(
                self.feedback_data['rules'][r].get('win_rate', 0) 
                for r in rules
            ) / len(rules) if rules else 0
            stats['category_performance'][category]['avg_win_rate'] = avg_win_rate
        
        return stats
    
    def get_weekly_report(self) -> Dict:
        """Generate weekly feedback report"""
        week_ago = (datetime.utcnow() - timedelta(days=7)).isoformat()
        
        report = {
            'period': 'Last 7 days',
            'generated_at': datetime.utcnow().isoformat(),
            'high_performers': self.stats['high_confidence_rules'][:5],
            'low_performers': self.stats['low_confidence_rules'],
            'untested_rules': self.stats['untested_rules'],
            'category_summary': self.stats['category_performance'],
            'recommendations': self._generate_recommendations()
        }
        
        return report
    
    def _generate_recommendations(self) -> List[str]:
        """Generate auto-recommendations for rule adjustments"""
        recommendations = []
        
        # High performers: can increase weight
        for rule in self.stats['high_confidence_rules']:
            recommendations.append(
                f"✅ BOOST: {rule['rule_id']} ({rule['win_rate']:.0%} win rate, "
                f"{rule['tested']} tests) — Increase weight in Master Rules"
            )
        
        # Low performers: decrease weight or remove
        for rule in self.stats['low_confidence_rules']:
            recommendations.append(
                f"⚠️ REVIEW: {rule['rule_id']} ({rule['win_rate']:.0%} win rate, "
                f"{rule['tested']} tests) — Consider decreasing weight or removing"
            )
        
        # Untested: need more data
        if self.stats['untested_rules']:
            recommendations.append(
                f"📊 DATA NEEDED: {len(self.stats['untested_rules'])} rules untested yet — "
                f"collect 10+ test cases before optimizing"
            )
        
        return recommendations
    
    def generate_full_report(self) -> str:
        """Generate full text report for logging/export"""
        report_lines = [
            "=" * 70,
            "MASTER TRADING RULES - FEEDBACK & OPTIMIZATION REPORT",
            "=" * 70,
            f"\nGenerated: {datetime.utcnow().isoformat()}",
            f"Database: {self.feedback_db_path}",
            f"\nTotal Rules Tracked: {self.stats['total_rules']}",
            f"High Performers (≥80% win rate): {len(self.stats['high_confidence_rules'])}",
            f"Low Performers (<50% win rate): {len(self.stats['low_confidence_rules'])}",
            f"Untested Rules: {len(self.stats['untested_rules'])}",
            "\n" + "=" * 70,
            "RECOMMENDATIONS",
            "=" * 70
        ]
        
        for rec in self._generate_recommendations():
            report_lines.append(f"\n{rec}")
        
        # Category performance
        report_lines.extend([
            "\n" + "=" * 70,
            "CATEGORY PERFORMANCE",
            "=" * 70
        ])
        
        for category, data in self.stats['category_performance'].items():
            report_lines.append(
                f"\n{category}: {data['avg_win_rate']:.0%} avg win rate "
                f"({data['total_tested']} tests)"
            )
            for rule_id in data['rules']:
                rule_data = self.feedback_data['rules'][rule_id]
                report_lines.append(
                    f"  • {rule_data['rule_name']}: "
                    f"{rule_data['win_rate']:.0%} ({rule_data['signals_tested']} tests)"
                )
        
        report_lines.append("\n" + "=" * 70)
        return "\n".join(report_lines)


if __name__ == '__main__':
    # Example usage
    feedback = MasterRulesFeedback()
    
    # Simulate a trade result
    feedback.record_signal_result(
        signal_id='SIGNAL_001',
        rules_validation={
            'rules_evaluation': {
                'market_cap_range': {'rule_name': 'Market Cap', 'category': 'Market Cap', 'tier': 1, 'passed': True},
                'liquidity_locked': {'rule_name': 'Liquidity Locked', 'category': 'Security', 'tier': 1, 'passed': True}
            }
        },
        trade_result={'entry': 0.001, 'exit': 0.002, 'pnl': 50},
        won=True
    )
    
    print(feedback.generate_full_report())
