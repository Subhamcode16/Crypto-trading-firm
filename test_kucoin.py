import requests
import time

start_at = int(time.mktime(time.strptime('2022-01-01', '%Y-%m-%d')))
end_at = int(time.mktime(time.strptime('2022-01-05', '%Y-%m-%d')))
url = f"https://api.kucoin.com/api/v1/market/candles?type=1hour&symbol=BTC-USDT&startAt={start_at}&endAt={end_at}"

print("Fetching from Kucoin...")
try:
    resp = requests.get(url, timeout=10)
    data = resp.json()
    if data['code'] == '200000':
        print(f"Success, fetched {len(data['data'])} candles")
        if len(data['data']) > 0:
            print("Sample:", data['data'][0])
    else:
        print("Error:", data)
except Exception as e:
    print("Exception:", e)
