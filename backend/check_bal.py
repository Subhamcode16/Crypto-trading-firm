import ccxt
import asyncio
import sqlite3
import json

async def main():
    db = sqlite3.connect('paper_trades.db')
    rows = db.execute('SELECT * FROM gamification_state').fetchall()
    state = {row[0]: json.loads(row[1]) for row in rows}
    exc = ccxt.binance({'apiKey': state.get('binance_api_key'), 'secret': state.get('binance_api_secret')})
    exc.set_sandbox_mode(True)
    bal = await exc.fetch_balance()
    print('USDT:', bal.get('USDT', {}).get('total', 0))
    print('BTC:', bal.get('BTC', {}).get('total', 0))
    print('ETH:', bal.get('ETH', {}).get('total', 0))
    print('SOL:', bal.get('SOL', {}).get('total', 0))
    await exc.close()

if __name__ == '__main__':
    asyncio.run(main())
