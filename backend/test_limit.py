import asyncio
import ccxt.async_support as ccxt

async def test():
    ex = ccxt.binance({'options': {'defaultType': 'spot'}})
    ex.set_sandbox_mode(True)
    ex.urls['api']['fapiPublic'] = 'https://testnet.binance.vision/api/v3'
    klines = await ex.fetch_ohlcv('BTC/USDT', '1h', limit=360)
    print("Fetched", len(klines), "klines for BTC/USDT")
    await ex.close()

asyncio.run(test())
