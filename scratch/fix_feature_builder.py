import sys
import re

with open(r"c:\Users\User\OneDrive\Desktop\projects\Crypto-trading-bot\ml_engine\features\feature_builder.py", "r", encoding="utf-8") as f:
    content = f.read()

# 1. Trend Indicators
# Find the end of _add_trend_indicators to add our drops and modifications
trend_find = r'        df\["di_bullish"\]   = \(df\["plus_di"\] > df\["minus_di"\]\)\.astype\(float\)'
trend_replace = r'''        df["di_bullish"]   = (df["plus_di"] > df["minus_di"]).astype(float)

        # Normalize MACD
        df["macd"] = df["macd"] / (c + 1e-10)
        df["macd_signal"] = df["macd_signal"] / (c + 1e-10)
        df["macd_hist"] = df["macd_hist"] / (c + 1e-10)

        # Add EMA slopes and drop raw EMAs
        for period in [9, 21, 50, 200]:
            ema_s = pd.Series(df[f"ema_{period}"].values)
            df[f"ema_{period}_slope"] = (ema_s - ema_s.shift(5)) / (ema_s.shift(5) + 1e-10)
        
        df = df.drop(columns=["ema_9", "ema_21", "ema_50", "ema_200"])'''
content = re.sub(trend_find, trend_replace, content)

# 2. Volatility Indicators
vol_find = r'        df\["hv_20"\]   = log_returns\.rolling\(20\)\.std\(\)\.values \* np\.sqrt\(252\)  # annualized'
vol_replace = r'''        df["hv_20"]   = log_returns.rolling(20).std().values * np.sqrt(252)  # annualized

        # Drop raw absolute features
        df = df.drop(columns=["atr_14", "bb_upper", "bb_mid", "bb_lower"])'''
content = re.sub(vol_find, vol_replace, content)

# 3. Volume Indicators
volm_find = r'        df\["price_vs_vwap"\] = \(c_s - df\["vwap"\]\) / \(df\["vwap"\] \+ 1e-10\)'
volm_replace = r'''        df["price_vs_vwap"] = (c_s - df["vwap"]) / (df["vwap"] + 1e-10)

        # Drop raw absolute features
        df = df.drop(columns=["obv", "vwap"])'''
content = re.sub(volm_find, volm_replace, content)

with open(r"c:\Users\User\OneDrive\Desktop\projects\Crypto-trading-bot\ml_engine\features\feature_builder.py", "w", encoding="utf-8") as f:
    f.write(content)
print("Updated feature_builder.py successfully.")
