import asyncio
import ccxt.async_support as ccxt

async def test():
    ex = ccxt.binance({'options': {'defaultType': 'spot'}})
    ex.set_sandbox_mode(True)
    try:
        res = await ex.load_markets()
        print('Success, markets loaded:', len(res))
    except Exception as e:
        print('Error:', type(e), e)
    await ex.close()

asyncio.run(test())
