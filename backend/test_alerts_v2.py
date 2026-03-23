import redis
import json
import time
import os
from dotenv import load_dotenv

# Load environment
load_dotenv("secrets.env")

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
r = redis.from_url(REDIS_URL)

def send_test_signal():
    alert = {
        "type": "signal",
        "data": {
            "token_name": "Test Token",
            "token_symbol": "TEST",
            "token_address": "6p6W7...solana",
            "entry_price": 0.0001234,
            "market_cap": "$50k",
            "reason": "Volume spike detected on Raydium"
        }
    }
    r.publish("pixelfirm:alerts", json.dumps(alert))
    print("✅ TEST SIGNAL pushed to Redis.")

def send_test_trade():
    alert = {
        "type": "trade",
        "message": "Just entered a small moonshot position.",
        "data": {
            "action": "ENTRY",
            "token": "SOLAMA",
            "pnl_usd": 0.0
        }
    }
    r.publish("pixelfirm:alerts", json.dumps(alert))
    print("✅ TEST TRADE pushed to Redis.")

def send_test_kill_switch():
    alert = {
        "type": "kill_switch",
        "tier": "1",
        "message": "High volatility detected. Stopping all bot activity."
    }
    r.publish("pixelfirm:alerts", json.dumps(alert))
    print("✅ TEST KILL SWITCH pushed to Redis.")

if __name__ == "__main__":
    print(f"Connecting to Redis at {REDIS_URL}...")
    try:
        send_test_signal()
        time.sleep(1)
        send_test_trade()
        time.sleep(1)
        send_test_kill_switch()
        print("\nAll test alerts dispatched. Check your Telegram bot!")
    except Exception as e:
        print(f"❌ Error: {e}")
