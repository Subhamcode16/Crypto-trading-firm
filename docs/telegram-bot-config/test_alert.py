"""
test_alert.py — Simulate agent alerts to verify the bot's push notification system.
Run this while the bot is running to confirm alerts arrive in Telegram.

Usage:
    python test_alert.py signal
    python test_alert.py trade_open
    python test_alert.py trade_close
    python test_alert.py kill_switch
"""

import json
import sys
import redis
from dotenv import load_dotenv
import os

load_dotenv()
r = redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379"), decode_responses=True)

ALERTS = {
    "signal": {
        "type": "signal",
        "token": "PEPE2",
        "mint": "DezXAZ8z7PnrnRJjz3wXBoRgixCa1XGkTfL1FNTMDv1",
        "score": 8.7,
        "reason": "Whale wallet accumulated 2.4M tokens in last 8 mins + Lookonchain mention",
        "dex_url": "https://dexscreener.com/solana/DezXAZ8z7PnrnRJjz3wXBoRgixCa1XGkTfL1FNTMDv1",
    },
    "trade_open": {
        "type": "trade_open",
        "token": "PEPE2",
        "entry_price": 0.000042,
        "size_sol": 0.5,
        "tp1_pct": 50,
        "tp2_pct": 150,
        "stop_pct": -25,
    },
    "trade_close": {
        "type": "trade_close",
        "token": "PEPE2",
        "pnl_pct": 47.3,
        "close_reason": "TP1 hit — trailing stop activated",
    },
    "kill_switch": {
        "type": "kill_switch",
        "level": 2,
        "reason": "Daily drawdown exceeded 15%",
        "action": "All new trades blocked. Existing positions managed.",
    },
}

alert_type = sys.argv[1] if len(sys.argv) > 1 else "signal"
payload = ALERTS.get(alert_type, ALERTS["signal"])

r.publish("pixelfirm:alerts", json.dumps(payload))
print(f"Published '{alert_type}' alert to pixelfirm:alerts channel.")
print(f"Payload: {json.dumps(payload, indent=2)}")
