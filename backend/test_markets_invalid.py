import sys
sys.path.append('C:\\Users\\User\\OneDrive\\Desktop\\projects\\crypto-trading-bot')
import asyncio
import ccxt.async_support as ccxt
from ml_engine.data.sqlite_store import SQLiteStore

async def test():
    db = SQLiteStore('backend/paper_trades.db')
    state = db.load_gamification_state()
    api_key = state.get('binance_api_key', '')
    api_secret = state.get('binance_api_secret', '')
    
    print('Key len:', len(api_key) if api_key else 0)
    
    ex = ccxt.binance({
        'apiKey': api_key,
        'secret': api_secret,
        'enableRateLimit': True,
        'options': {'defaultType': 'spot'}
    })
    ex.set_sandbox_mode(True)
    
    try:
        print("Fetching balance...")
        await ex.fetch_balance()
        print("Success")
    except Exception as e:
        import traceback
        print('Error fetching balance:', type(e).__name__)
        traceback.print_exc()
        
    finally:
        await ex.close()

asyncio.run(test())
