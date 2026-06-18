import os, asyncio
import ccxt.async_support as ccxt
from dotenv import load_dotenv

load_dotenv('secrets.env')

async def test():
    ex = ccxt.binance({
        'apiKey': os.getenv('BINANCE_API_KEY'),
        'secret': os.getenv('BINANCE_SECRET_KEY'),
        'enableRateLimit': True,
        'options': {'defaultType': 'spot'}
    })
    ex.set_sandbox_mode(True)
    try:
        bal = await ex.fetch_balance()
        print('Balance Success', bal.get('USDT'))
    except Exception as e:
        print(f'Error: {type(e).__name__} - {str(e)}')
    await ex.close()

asyncio.run(test())
