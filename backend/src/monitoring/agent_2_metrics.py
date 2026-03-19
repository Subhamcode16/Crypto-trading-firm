#!/usr/bin/env python3
"""
Agent 2 Continuous Monitoring
Collects metrics for 48-hour validation period
"""

import sqlite3
import json
from datetime import datetime, timedelta
import logging
from pathlib import Path

logger = logging.getLogger('metrics')

class Agent2Metrics:
    """Tracks Agent 2 performance metrics"""
    
    def __init__(self, db_path='data/database.db'):
        self.db_path = db_path
        self.metrics_file = 'data/metrics/agent_2_metrics.json'
        Path(self.metrics_file).parent.mkdir(parents=True, exist_ok=True)
        self.metrics = self._load_metrics()
    
    def _load_metrics(self):
        """Load existing metrics or create new"""
        if Path(self.metrics_file).exists():
            with open(self.metrics_file) as f:
                return json.load(f)
        return {
            'validation_started': datetime.utcnow().isoformat(),
            'scans': [],
            'filters': {},
            'aggregate': {
                'total_tokens': 0,
                'total_killed': 0,
                'total_cleared': 0,
                'latency_samples': [],
                'filter_hit_rates': {}
            }
        }
    
    def record_scan(self, scan_data):
        """Record one scan cycle"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        try:
            # Get all analyses from last scan
            c.execute("""
                SELECT token_address, status, failure_reason, failed_filter, analysis_timestamp
                FROM agent_2_analysis
                ORDER BY analysis_timestamp DESC
                LIMIT 6
            """)
            
            analyses = c.fetchall()
            scan_record = {
                'timestamp': datetime.utcnow().isoformat(),
                'token_count': len(analyses),
                'killed_count': sum(1 for a in analyses if a[1] == 'KILLED'),
                'cleared_count': sum(1 for a in analyses if a[1] == 'CLEARED'),
                'filters_hit': {}
            }
            
            # Track filter hits
            for addr, status, reason, failed_filter, ts in analyses:
                if failed_filter:
                    if failed_filter not in scan_record['filters_hit']:
                        scan_record['filters_hit'][failed_filter] = 0
                    scan_record['filters_hit'][failed_filter] += 1
            
            self.metrics['scans'].append(scan_record)
            self.metrics['aggregate']['total_tokens'] += scan_record['token_count']
            self.metrics['aggregate']['total_killed'] += scan_record['killed_count']
            self.metrics['aggregate']['total_cleared'] += scan_record['cleared_count']
            
            # Update filter hit rates
            for filter_name, count in scan_record['filters_hit'].items():
                if filter_name not in self.metrics['aggregate']['filter_hit_rates']:
                    self.metrics['aggregate']['filter_hit_rates'][filter_name] = 0
                self.metrics['aggregate']['filter_hit_rates'][filter_name] += count
            
            self._save_metrics()
            logger.info(f"Metrics recorded: {scan_record['token_count']} tokens, {scan_record['killed_count']} killed, {scan_record['cleared_count']} cleared")
            
        except Exception as e:
            logger.error(f"Error recording metrics: {e}")
        finally:
            conn.close()
    
    def _save_metrics(self):
        """Save metrics to file"""
        with open(self.metrics_file, 'w') as f:
            json.dump(self.metrics, f, indent=2)
    
    def get_summary(self):
        """Get 48-hour validation summary"""
        total_scans = len(self.metrics['scans'])
        start_time = datetime.fromisoformat(self.metrics['validation_started'])
        elapsed = datetime.utcnow() - start_time
        
        # Calculate averages
        if total_scans > 0:
            avg_tokens = self.metrics['aggregate']['total_tokens'] / total_scans
            avg_kill_rate = (self.metrics['aggregate']['total_killed'] / self.metrics['aggregate']['total_tokens'] * 100) if self.metrics['aggregate']['total_tokens'] > 0 else 0
        else:
            avg_tokens = 0
            avg_kill_rate = 0
        
        return {
            'validation_started': self.metrics['validation_started'],
            'elapsed_hours': elapsed.total_seconds() / 3600,
            'scans_completed': total_scans,
            'total_tokens_analyzed': self.metrics['aggregate']['total_tokens'],
            'total_killed': self.metrics['aggregate']['total_killed'],
            'total_cleared': self.metrics['aggregate']['total_cleared'],
            'avg_tokens_per_scan': avg_tokens,
            'kill_rate_percent': avg_kill_rate,
            'filter_hit_rates': self.metrics['aggregate']['filter_hit_rates']
        }

if __name__ == '__main__':
    metrics = Agent2Metrics()
    metrics.record_scan({})
    summary = metrics.get_summary()
    print(json.dumps(summary, indent=2))
