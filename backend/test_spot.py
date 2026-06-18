import asyncio
import ccxt.async_support as ccxt

async def test():
    ex = ccxt.binance({
        'options': {
            'defaultType': 'spot',
            'fetchMarkets': ['spot']
        }
    })
    ex.set_sandbox_mode(True)
    try:
        markets = await ex.load_markets()
        print('Markets loaded:', len(markets))
    except Exception as e:
        import traceback
        traceback.print_exc()
    finally:
        await ex.close()

asyncio.run(test())
