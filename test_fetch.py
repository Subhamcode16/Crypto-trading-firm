import asyncio
from ml_engine.data.fetcher import BinanceFetcher

async def test():
    async with BinanceFetcher() as f:
        df = await f.fetch_ohlcv('BTC/USDT', '1h', since='2022-01-01', until='2022-01-05')
        print('Success, fetched', len(df), 'candles')

asyncio.run(test())
