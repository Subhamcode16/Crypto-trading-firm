#!/usr/bin/env python3
import logging

logger = logging.getLogger(__name__)


class SafetyScorer:
    def calculate_score(self, token_address: str, filter_results: dict) -> float:
        score = 10.0
        
        age_details = filter_results.get('contract_age', {}).get('details', '')
        if '15' in age_details or '20' in age_details or '25' in age_details:
            score -= 1
        
        concentration_details = filter_results.get('holder_concentration', {}).get('details', '')
        if '2' in concentration_details and '%' in concentration_details:
            score -= 1
        
        buyers_details = filter_results.get('unique_buyers', {}).get('details', '')
        if '50' in buyers_details or '60' in buyers_details or '70' in buyers_details:
            score -= 0.5
        
        if '200' in buyers_details or '300' in buyers_details or '400' in buyers_details:
            score += 0.5
        
        if '1' in concentration_details and '5' in concentration_details:
            score += 1
        
        return max(0, min(10, score))
