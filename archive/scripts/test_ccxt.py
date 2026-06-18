import asyncio
import ccxt.async_support as ccxt
import sys

async def main():
    api_key = "dummy"
    api_secret = "dummy"
    
    exchange = ccxt.binance({
        'apiKey': api_key,
        'secret': api_secret,
        'enableRateLimit': True,
    })
    exchange.set_sandbox_mode(True)
    
    print("Testnet URL:", exchange.urls['api'])
    try:
        await exchange.fetch_balance()
    except Exception as e:
        print(f"Error: {type(e).__name__} - {e}")
    finally:
        await exchange.close()

if __name__ == "__main__":
    asyncio.run(main())
