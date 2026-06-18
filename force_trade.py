import asyncio
import os
import sys
import time
from datetime import datetime, timezone
import logging

logging.basicConfig(level=logging.INFO)

# Make sure we can import ml_engine
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from ml_engine.execution.live_trader import LiveTrader
from ml_engine.data.mongo_store import MongoStore
from ml_engine.data import bybit_public

async def main():
    print("Testing CCXT Orders...")
    
    # 1. Grab credentials from the DB
    db = MongoStore()
    state = db.load_gamification_state()
    
    api_key = state.get('binance_api_key')
    api_secret = state.get('binance_api_secret')
    testnet = state.get('binance_testnet', True)
    
    if not api_key:
        print("No API key found in the database. Please connect via UI first.")
        return
        
    print(f"Initializing LiveTrader (Testnet={testnet})...")
    trader = LiveTrader(api_key=api_key, api_secret=api_secret, testnet=testnet)
    
    print("Checking balance to ensure time sync & connectivity...")
    bal = await trader.get_balance()
    usdt_free = bal.get('USDT', {}).get('free', 0)
    print(f"Free USDT: ${usdt_free:.2f}")
    
    if usdt_free < 10:
        print("Insufficient funds to place a test trade.")
        # Let's see if we can still try...
        # return
        
    print("\nFetching current SOL/USDT ticker from public API...")
    symbol = "SOL/USDT"
    ticker = await bybit_public.fetch_ticker(symbol)
    if not ticker:
        print("Could not fetch ticker.")
        return
        
    current_price = ticker['last']
    print(f"Current SOL Price: ${current_price:.2f}")
    
    print("\nForcing a BUY order on SOL/USDT to verify execution...")
    timestamp = str(datetime.now(timezone.utc))
    
    # Execute BUY (This hits ccxt create_market_buy_order and saves to sqlite)
    await trader._execute_action(
        symbol=symbol,
        action="BUY",
        price=current_price,
        timestamp=timestamp,
        confidence=1.0,
        amount_pct=1.0
    )
    
    print("\nVerifying open positions...")
    positions = await trader.get_positions()
    for p in positions:
        print(f"-> {p['side'].upper()} {p['symbol']} | Amount: {p['amount']} | Entry: ${p['entry_price']} | PNL: ${p['unrealized_pnl']}")
    
    print("\nDone. You should see this trade on your Bybit Demo dashboard and your UI.")

if __name__ == "__main__":
    asyncio.run(main())
