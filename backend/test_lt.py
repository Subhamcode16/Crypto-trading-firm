import asyncio
from ml_engine.execution.live_trader import LiveBinanceTrader

async def test():
    lt = LiveBinanceTrader('a', 'b')
    await lt.evaluate_market()
    print("Keys in explainability_data:", lt.explainability_data['BTC/USDT'].keys())

asyncio.run(test())
