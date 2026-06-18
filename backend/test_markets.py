import asyncio
import ccxt.async_support as ccxt

async def test():
    ex = ccxt.binance({
        'enableRateLimit': True,
        'options': {'defaultType': 'spot'}
    })
    ex.set_sandbox_mode(True)
    # The hack that is currently in live_trader.py
    ex.urls['api']['fapiPublic'] = 'https://testnet.binance.vision/api/v3'
    ex.urls['api']['fapiPrivate'] = 'https://testnet.binance.vision/api/v3'
    
    try:
        print('Loading markets...')
        await ex.load_markets()
        print('Markets loaded!')
        klines = await ex.fetch_ohlcv('BTC/USDT', '1h', limit=5)
        print('Klines:', len(klines))
    except Exception as e:
        print('Error:', type(e).__name__, str(e))
    finally:
        await ex.close()

asyncio.run(test())
