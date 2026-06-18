import numpy as np
import pandas as pd

class VolatilityBreakoutSignal:
    """
    Volatility Breakout Signal Generator.
    Replaces XGBoost model when ML accuracy is insufficient.
    
    Logic:
    - ENTER LONG: Price breaks above Bollinger Band Upper.
    - HOLD LONG: Price remains above Bollinger Band Middle (bb_pct_b > 0.5).
    - ENTER SHORT: Price breaks below Bollinger Band Lower.
    - HOLD SHORT: Price remains below Bollinger Band Middle (bb_pct_b < 0.5).
    """
    def __init__(self, symbol: str = "BTC/USDT", timeframe: str = "1h"):
        self.symbol = symbol
        self.timeframe = timeframe
        # We specify feature names so pipeline doesn't crash if it checks them
        self._feature_names = ['bb_above_upper', 'bb_below_lower', 'bb_pct_b', 'bb_squeeze', 'vol_surge']
        self._trained_on = 0
        self._test_accuracy = 0.0

    @classmethod
    def load(cls, path: str):
        return cls()
        
    def save(self, path: str = None):
        pass

    def predict_df(self, df: pd.DataFrame, feature_names: list) -> pd.DataFrame:
        df = df.copy(deep=False)
        preds = np.zeros(len(df), dtype=int)
        
        bb_pct_b = df.get('bb_pct_b', pd.Series(np.ones(len(df))*0.5)).values
        bb_above_upper = df.get('bb_above_upper', pd.Series(np.zeros(len(df)))).values
        bb_below_lower = df.get('bb_below_lower', pd.Series(np.zeros(len(df)))).values
        vol_surge = df.get('vol_surge', pd.Series(np.zeros(len(df)))).values
        breakout_up = df.get('breakout_up', pd.Series(np.zeros(len(df)))).values
        breakout_down = df.get('breakout_down', pd.Series(np.zeros(len(df)))).values
        ema_alignment = df.get('ema_alignment', pd.Series(np.ones(len(df))*0.5)).values
        
        close_prices = df.get('close', pd.Series(np.zeros(len(df)))).values
        
        current_pos = 0
        breakout_level = 0.0
        for i in range(len(df)):
            if current_pos == 0:
                # Stricter Entry LONG
                if breakout_up[i] > 0 and bb_above_upper[i] > 0 and vol_surge[i] > 0 and ema_alignment[i] >= 0.66:
                    current_pos = 1
                    breakout_level = close_prices[i]
                # Stricter Entry SHORT
                elif breakout_down[i] > 0 and bb_below_lower[i] > 0 and vol_surge[i] > 0 and ema_alignment[i] <= 0.33:
                    current_pos = 2
                    breakout_level = close_prices[i]
            elif current_pos == 1:
                # Exit LONG if price falls below 20-EMA (bb_pct_b < 0.5) or alignment flips
                # OR price falls below original breakout level (reset)
                if bb_pct_b[i] < 0.4 or ema_alignment[i] < 0.5 or close_prices[i] < breakout_level:
                    current_pos = 0
                elif breakout_down[i] > 0 and bb_below_lower[i] > 0 and vol_surge[i] > 0 and ema_alignment[i] <= 0.33:
                    current_pos = 2
                    breakout_level = close_prices[i]
            elif current_pos == 2:
                # Exit SHORT if price rises above 20-EMA (bb_pct_b > 0.5) or alignment flips
                # OR price rises above original breakout level (reset)
                if bb_pct_b[i] > 0.6 or ema_alignment[i] > 0.5 or close_prices[i] > breakout_level:
                    current_pos = 0
                elif breakout_up[i] > 0 and bb_above_upper[i] > 0 and vol_surge[i] > 0 and ema_alignment[i] >= 0.66:
                    current_pos = 1
                    breakout_level = close_prices[i]
                    
            preds[i] = current_pos
            
        confidences = np.where(preds != 0, 0.8, 0.0)
        
        SIGNAL_CLASSES = {
            0: "NO_SIGNAL",
            1: "STRONG_LONG",
            2: "STRONG_SHORT",
        }
        
        df["xgb_pred"]       = preds
        df["xgb_signal"]     = [SIGNAL_CLASSES[p] for p in preds]
        df["xgb_confidence"] = confidences
        df["xgb_strong"]     = (preds == 1) | (preds == 2)
        return df

    def predict(self, features: dict) -> dict:
        bb_pct_b = features.get('bb_pct_b', 0.5)
        bb_above_upper = features.get('bb_above_upper', 0)
        bb_below_lower = features.get('bb_below_lower', 0)
        vol_surge = features.get('vol_surge', 0)
        breakout_up = features.get('breakout_up', 0)
        breakout_down = features.get('breakout_down', 0)
        ema_alignment = features.get('ema_alignment', 0.5)
        
        # Simplified stateless version for compatibility
        if breakout_up > 0 and bb_above_upper > 0 and vol_surge > 0 and ema_alignment >= 0.66:
            signal = "STRONG_LONG"
        elif breakout_down > 0 and bb_below_lower > 0 and vol_surge > 0 and ema_alignment <= 0.33:
            signal = "STRONG_SHORT"
        elif bb_pct_b > 0.6 and ema_alignment >= 0.5:
            signal = "STRONG_LONG"
        elif bb_pct_b < 0.4 and ema_alignment <= 0.5:
            signal = "STRONG_SHORT"
        else:
            signal = "NO_SIGNAL"
            
        return {
            "signal":     signal,
            "confidence": 0.8 if signal != "NO_SIGNAL" else 0.0,
            "strong":     signal in ("STRONG_LONG", "STRONG_SHORT"),
            "raw_probs":  {"STRONG_LONG": 0.8 if signal == "STRONG_LONG" else 0.0, 
                           "STRONG_SHORT": 0.8 if signal == "STRONG_SHORT" else 0.0}
        }
