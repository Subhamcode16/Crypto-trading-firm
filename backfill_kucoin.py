import requests
import time
import pandas as pd
from datetime import datetime, timezone
from ml_engine.data.pipeline import DataPipeline

def fetch_and_save(symbol, timeframe, tf_seconds, start_date, end_date):
    pipeline = DataPipeline()
    start_at = int(time.mktime(time.strptime(start_date, '%Y-%m-%d')))
    end_at = int(time.mktime(time.strptime(end_date, '%Y-%m-%d')))
    
    current_start = start_at
    total_inserted = 0
    
    while current_start < end_at:
        # Kucoin max is 1500 per request
        current_end = min(end_at, current_start + 1400 * tf_seconds)
        
        url = f"https://api.kucoin.com/api/v1/market/candles?type={timeframe}&symbol=BTC-USDT&startAt={current_start}&endAt={current_end}"
        print(f"Fetching {symbol} {timeframe} from {current_start} to {current_end}...")
        
        try:
            resp = requests.get(url, timeout=10)
            data = resp.json()
            if data['code'] == '200000':
                candles = data['data']
                if not candles:
                    current_start = current_end + tf_seconds
                    continue
                
                rows = []
                for c in candles:
                    # [0] time, [1] open, [2] close, [3] high, [4] low, [5] vol, [6] turnover
                    dt = datetime.fromtimestamp(int(c[0]), tz=timezone.utc)
                    rows.append({
                        "symbol": symbol,
                        "timeframe": "1h" if timeframe == "1hour" else "4h",
                        "open_time": dt.isoformat(),
                        "open": float(c[1]),
                        "high": float(c[3]),
                        "low": float(c[4]),
                        "close": float(c[2]),
                        "volume": float(c[5])
                    })
                
                df = pd.DataFrame(rows)
                inserted = pipeline.storage.upsert_ohlcv(df)
                total_inserted += inserted
                
                # Advance time (KuCoin returns results sorted descending, so max time is first? No, we use current_end)
                current_start = current_end + tf_seconds
            else:
                print("Error:", data)
                break
        except Exception as e:
            print("Exception:", e)
            time.sleep(5)
            
        time.sleep(0.5)

    print(f"Finished {timeframe}. Inserted {total_inserted} rows.")

if __name__ == "__main__":
    fetch_and_save("BTC/USDT", "1hour", 3600, '2020-01-01', '2025-01-01')
    fetch_and_save("BTC/USDT", "4hour", 14400, '2020-01-01', '2025-01-01')
    # Change "1hour" and "4hour" to match DataPipeline schema format "1h", "4h"
