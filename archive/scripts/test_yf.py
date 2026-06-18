import traceback
import yfinance as yf

try:
    df = yf.download('^TNX', period='730d', progress=False)
    print(df.head())
except Exception as e:
    traceback.print_exc()
