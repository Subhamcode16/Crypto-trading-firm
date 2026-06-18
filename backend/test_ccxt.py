import asyncio
import ccxt.async_support as ccxt
import sys

async def test():
    print("Testing CCXT")
    try:
        ex = ccxt.binance({
            'enableRateLimit': True,
            'options': {
                'defaultType': 'spot',
                'warnOnFetchOpenOrdersWithoutSymbol': False,
            }
        })
        ex.set_sandbox_mode(True)
        # Attempt to restrict markets loaded to avoid fapi
        ex.urls['api']['public'] = 'https://testnet.binance.vision/api/v3'
        ex.urls['api']['fapiPublic'] = 'https://testnet.binance.vision/api/v3'
        ex.urls['api']['fapiPrivate'] = 'https://testnet.binance.vision/api/v3'
        ex.urls['api']['dapiPublic'] = 'https://testnet.binance.vision/api/v3'
        ex.urls['api']['dapiPrivate'] = 'https://testnet.binance.vision/api/v3'
        
        await ex.load_markets()
        print('Markets loaded successfully!')
        await ex.close()
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

asyncio.run(test())
