"""
ml_engine/features/feature_builder.py
───────────────────────────────────────
Master Feature Builder — converts raw OHLCV DataFrame into a
120+ dimensional feature vector for ML models.

Feature Groups:
  1. Candlestick patterns   (30+ patterns via TA-Lib or fallback)
  2. Trend indicators       (EMA 9/21/50/200, MACD, ADX, Ichimoku)
  3. Momentum indicators    (RSI, Stochastic, ROC, Williams %R)
  4. Volatility indicators  (Bollinger Bands, ATR, Keltner Channels)
  5. Volume indicators      (OBV, VWAP, MFI, Volume Profile)
  6. Multi-timeframe bias   (HTF trend alignment score)
  7. Market context         (Fear & Greed, BTC dominance)

Usage:
  from ml_engine.features.feature_builder import FeatureBuilder
  
  fb = FeatureBuilder()
  features_df = fb.build_dataset(ohlcv_df)   # For training (returns full DF)
  feature_vec = fb.build_single(ohlcv_df)    # For inference (returns last bar dict)
"""

import logging
import warnings
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore", category=pd.errors.PerformanceWarning)
logger = logging.getLogger(__name__)

SCALER_DIR = Path(__file__).parent.parent / "models" / "saved"


class FeatureBuilder:
    """
    Converts raw OHLCV DataFrames into ML-ready feature vectors.
    
    Gracefully handles missing TA-Lib by using pandas-ta as fallback.
    Feature count: ~120 features per bar.
    """

    FEATURE_VERSION = "2.0"

    def __init__(self, use_talib: bool = True):
        self._talib_available = False
        self._pandas_ta_available = False

        if use_talib:
            try:
                import talib
                self._talib = talib
                self._talib_available = True
                logger.info("[FeatureBuilder] ✅ TA-Lib loaded")
            except ImportError:
                logger.warning("[FeatureBuilder] TA-Lib not found, trying pandas-ta fallback")

        if not self._talib_available:
            try:
                import pandas_ta as pta
                self._pta = pta
                self._pandas_ta_available = True
                logger.info("[FeatureBuilder] ✅ pandas-ta loaded (TA-Lib fallback)")
            except ImportError:
                logger.warning("[FeatureBuilder] pandas-ta not found, computing basic indicators only")

    # ─── Public Interface ──────────────────────────────────────────────────

    def build_dataset(
        self,
        df: pd.DataFrame,
        macro_df: Optional[pd.DataFrame] = None,
        dropna: bool = True,
    ) -> pd.DataFrame:
        """
        Build features for an entire OHLCV DataFrame (training mode).
        
        Args:
            df:       OHLCV DataFrame (sorted by time, with open_time column)
            macro_df: Optional DataFrame with vix, dxy, fear_greed columns
            dropna:   Drop rows with NaN features (from indicator warm-up)
            
        Returns:
            DataFrame with all OHLCV columns + 120+ feature columns
        """
        logger.info(f"[FeatureBuilder] Building features for {len(df):,} bars...")
        result = df.copy()

        # Extract OHLCV as numpy arrays for speed
        o = df["open"].values.astype(float)
        h = df["high"].values.astype(float)
        l = df["low"].values.astype(float)
        c = df["close"].values.astype(float)
        v = df["volume"].values.astype(float)

        # Build all feature groups
        result = self._add_candlestick_patterns(result, o, h, l, c)
        result = self._add_trend_indicators(result, o, h, l, c, v)
        result = self._add_momentum_indicators(result, o, h, l, c, v)
        result = self._add_volatility_indicators(result, h, l, c)
        result = self._add_volume_indicators(result, h, l, c, v)
        result = self._add_price_action_features(result, o, h, l, c)
        result = self._add_time_features(result)
        result = self._add_bear_market_features(result, c)  # FIX 3: Bear market regime features

        if macro_df is not None:
            result = self._add_macro_features(result, macro_df)

        if dropna:
            pre_drop = len(result)
            result = result.dropna(subset=self.get_feature_columns(result))
            result = result.reset_index(drop=True)
            dropped = pre_drop - len(result)
            if dropped > 0:
                logger.info(f"[FeatureBuilder] Dropped {dropped} rows with NaN (indicator warm-up)")

        logger.info(f"[FeatureBuilder] PASS: {len(result):,} bars with {len(self.get_feature_columns(result))} features")
        return result

    def build_single(self, df: pd.DataFrame, macro_context: Optional[Dict] = None) -> Dict:
        """
        Build feature vector for the most recent bar (inference mode).
        Requires df with at least 200 bars for indicator warm-up.
        
        Returns:
            Dict of {feature_name: float_value} for the last bar
        """
        if len(df) < 200:
            logger.warning(f"[FeatureBuilder] Only {len(df)} bars — indicators may be inaccurate (need 200+)")

        feat_df = self.build_dataset(df, dropna=False)
        if feat_df.empty:
            return {}

        last_row = feat_df.iloc[-1]
        feature_cols = self.get_feature_columns(feat_df)

        features = {col: float(last_row[col]) if pd.notna(last_row[col]) else 0.0
                    for col in feature_cols}

        # Inject macro context if provided at inference time
        if macro_context:
            features["fear_greed_index"]  = float(macro_context.get("fear_greed_index", 50))
            features["btc_dominance"]     = float(macro_context.get("btc_dominance", 50))
            features["vix"]              = float(macro_context.get("vix", 20))
            features["dxy"]              = float(macro_context.get("dxy", 100))
            features["tnx"]              = float(macro_context.get("tnx", 4.0))

        features["_feature_version"] = self.FEATURE_VERSION
        features["_bar_time"]        = str(last_row.get("timestamp", last_row.get("open_time", "")))
        return features

    def get_feature_columns(self, df: pd.DataFrame) -> List[str]:
        """Return list of feature column names (excludes OHLCV + metadata cols)."""
        exclude = {"timestamp", "open_time", "close_time", "symbol", "timeframe",
                   "open", "high", "low", "close", "volume",
                   "quote_volume", "num_trades", "taker_buy_base",
                   "taker_buy_quote", "created_at", "id"}
        return [c for c in df.columns if c not in exclude and not c.startswith("_")]

    # ─── Feature Group 1: Candlestick Patterns ────────────────────────────

    def _add_candlestick_patterns(self, df: pd.DataFrame, o, h, l, c) -> pd.DataFrame:
        """
        Add 30+ candlestick pattern recognition features.
        Values: -100 (bearish), 0 (no pattern), +100 (bullish)
        """
        if self._talib_available:
            t = self._talib
            patterns = {
                "cdl_doji":           t.CDLDOJI(o, h, l, c),
                "cdl_hammer":         t.CDLHAMMER(o, h, l, c),
                "cdl_invhammer":      t.CDLINVERTEDHAMMER(o, h, l, c),
                "cdl_shooting_star":  t.CDLSHOOTINGSTAR(o, h, l, c),
                "cdl_engulfing":      t.CDLENGULFING(o, h, l, c),
                "cdl_morning_star":   t.CDLMORNINGSTAR(o, h, l, c),
                "cdl_evening_star":   t.CDLEVENINGSTAR(o, h, l, c),
                "cdl_3white_soldiers":t.CDL3WHITESOLDIERS(o, h, l, c),
                "cdl_3black_crows":   t.CDL3BLACKCROWS(o, h, l, c),
                "cdl_harami":         t.CDLHARAMI(o, h, l, c),
                "cdl_harami_cross":   t.CDLHARAMICROSS(o, h, l, c),
                "cdl_hanging_man":    t.CDLHANGINGMAN(o, h, l, c),
                "cdl_dragonfly_doji": t.CDLDRAGONFLYDOJI(o, h, l, c),
                "cdl_gravestone_doji":t.CDLGRAVESTONEDOJI(o, h, l, c),
                "cdl_spinning_top":   t.CDLSPINNINGTOP(o, h, l, c),
                "cdl_marubozu":       t.CDLMARUBOZU(o, h, l, c),
                "cdl_piercing":       t.CDLPIERCING(o, h, l, c),
                "cdl_dark_cloud":     t.CDLDARKCLOUDCOVER(o, h, l, c),
                "cdl_rising_3":       t.CDLRISEFALL3METHODS(o, h, l, c),
                "cdl_3inside":        t.CDL3INSIDE(o, h, l, c),
                "cdl_3outside":       t.CDL3OUTSIDE(o, h, l, c),
                "cdl_belt_hold":      t.CDLBELTHOLD(o, h, l, c),
                "cdl_kicking":        t.CDLKICKING(o, h, l, c),
                "cdl_tasuki_gap":     t.CDLTASUKIGAP(o, h, l, c),
                "cdl_identical_3crows": t.CDLIDENTICAL3CROWS(o, h, l, c),
            }
            for name, values in patterns.items():
                df[name] = values / 100.0   # Normalize to -1, 0, +1
        else:
            # Fallback: compute basic patterns manually
            df = self._add_patterns_fallback(df, o, h, l, c)

        # Aggregate pattern signals
        pat_cols = [col for col in df.columns if col.startswith("cdl_")]
        if pat_cols:
            df["cdl_bullish_count"] = (df[pat_cols] > 0).sum(axis=1).astype(float)
            df["cdl_bearish_count"] = (df[pat_cols] < 0).sum(axis=1).astype(float)
            df["cdl_net_signal"]    = df["cdl_bullish_count"] - df["cdl_bearish_count"]

        return df

    def _add_patterns_fallback(self, df: pd.DataFrame, o, h, l, c) -> pd.DataFrame:
        """Manual candlestick pattern detection when TA-Lib is unavailable."""
        body = c - o
        upper_wick = h - np.maximum(o, c)
        lower_wick = np.minimum(o, c) - l
        total_range = np.where(h - l > 0, h - l, 1e-10)

        # Doji: tiny body relative to range
        df["cdl_doji"] = np.where(np.abs(body) / total_range < 0.1, 1.0, 0.0)

        # Hammer: small body at top, long lower wick (bullish)
        is_hammer = (lower_wick > 2 * np.abs(body)) & (upper_wick < 0.3 * np.abs(body))
        df["cdl_hammer"] = np.where(is_hammer, 1.0, 0.0)

        # Shooting Star: small body at bottom, long upper wick (bearish)
        is_shooting = (upper_wick > 2 * np.abs(body)) & (lower_wick < 0.3 * np.abs(body))
        df["cdl_shooting_star"] = np.where(is_shooting, -1.0, 0.0)

        # Bullish Engulfing
        prev_body = np.roll(body, 1)
        prev_o    = np.roll(o, 1)
        prev_c    = np.roll(c, 1)
        bullish_eng = (body > 0) & (prev_body < 0) & (o <= prev_c) & (c >= prev_o)
        df["cdl_engulfing"] = np.where(bullish_eng, 1.0, 0.0)

        # Marubozu: full-body candle (strong momentum)
        marubozu_bull = (body > 0) & (upper_wick / total_range < 0.02) & (lower_wick / total_range < 0.02)
        marubozu_bear = (body < 0) & (upper_wick / total_range < 0.02) & (lower_wick / total_range < 0.02)
        df["cdl_marubozu"] = np.where(marubozu_bull, 1.0, np.where(marubozu_bear, -1.0, 0.0))

        # Fill remaining expected columns with zeros for consistency
        for col in ["cdl_invhammer", "cdl_morning_star", "cdl_evening_star",
                    "cdl_3white_soldiers", "cdl_3black_crows", "cdl_harami",
                    "cdl_harami_cross", "cdl_hanging_man", "cdl_dragonfly_doji",
                    "cdl_gravestone_doji", "cdl_spinning_top", "cdl_piercing",
                    "cdl_dark_cloud", "cdl_rising_3", "cdl_3inside", "cdl_3outside",
                    "cdl_belt_hold", "cdl_kicking", "cdl_tasuki_gap", "cdl_identical_3crows"]:
            df[col] = 0.0

        return df

    # ─── Feature Group 2: Trend Indicators ────────────────────────────────

    def _add_trend_indicators(self, df, o, h, l, c, v) -> pd.DataFrame:
        """EMA crosses, MACD, ADX, Parabolic SAR, Supertrend."""
        ta = self._talib if self._talib_available else None

        # EMAs
        for period in [9, 21, 50, 200]:
            key = f"ema_{period}"
            if ta:
                df[key] = ta.EMA(c, timeperiod=period)
            else:
                df[key] = pd.Series(c, index=df.index).ewm(span=period, adjust=False).mean()

        # Price relative to EMAs (normalized)
        df["price_vs_ema9"]   = (c - df["ema_9"]) / (df["ema_9"] + 1e-10)
        df["price_vs_ema21"]  = (c - df["ema_21"]) / (df["ema_21"] + 1e-10)
        df["price_vs_ema50"]  = (c - df["ema_50"]) / (df["ema_50"] + 1e-10)
        df["price_vs_ema200"] = (c - df["ema_200"]) / (df["ema_200"] + 1e-10)

        # EMA alignment score: how many EMAs are stacked bullishly
        ema_stack = (
            (df["ema_9"] > df["ema_21"]).astype(float) +
            (df["ema_21"] > df["ema_50"]).astype(float) +
            (df["ema_50"] > df["ema_200"]).astype(float)
        )
        df["ema_alignment"] = ema_stack / 3.0  # 0=fully bearish, 1=fully bullish

        # EMA crosses (binary: 1 if golden cross happened in last 3 bars)
        ema9  = df["ema_9"]
        ema21 = df["ema_21"]
        golden_cross = ((ema9 > ema21) & (ema9.shift(1) <= ema21.shift(1)))
        death_cross  = ((ema9 < ema21) & (ema9.shift(1) >= ema21.shift(1)))
        df["ema_golden_cross"] = golden_cross.rolling(3, min_periods=1).max()
        df["ema_death_cross"]  = death_cross.rolling(3, min_periods=1).max()

        # MACD
        if ta:
            macd, signal, hist = ta.MACD(c, fastperiod=12, slowperiod=26, signalperiod=9)
            df["macd"]        = macd
            df["macd_signal"] = signal
            df["macd_hist"]   = hist
        else:
            ema12 = pd.Series(c, index=df.index).ewm(span=12, adjust=False).mean()
            ema26 = pd.Series(c, index=df.index).ewm(span=26, adjust=False).mean()
            macd_line = ema12 - ema26
            signal_line = macd_line.ewm(span=9, adjust=False).mean()
            df["macd"]        = macd_line
            df["macd_signal"] = signal_line
            df["macd_hist"]   = (macd_line - signal_line)

        df["macd_bullish"] = (df["macd"] > df["macd_signal"]).astype(float)
        df["macd_cross_up"] = ((df["macd"] > df["macd_signal"]) &
                               (df["macd"].shift(1) <= df["macd_signal"].shift(1))).astype(float)

        # ADX (trend strength)
        if ta:
            df["adx"]  = ta.ADX(h, l, c, timeperiod=14)
            df["plus_di"]  = ta.PLUS_DI(h, l, c, timeperiod=14)
            df["minus_di"] = ta.MINUS_DI(h, l, c, timeperiod=14)
        elif self._pandas_ta_available:
            h_s = pd.Series(h, index=df.index)
            l_s = pd.Series(l, index=df.index)
            c_s = pd.Series(c, index=df.index)
            adx_df = self._pta.adx(h_s, l_s, c_s, length=14)
            if adx_df is not None:
                df["adx"] = adx_df.iloc[:, 0].values
                df["plus_di"] = adx_df.iloc[:, 1].values
                df["minus_di"] = adx_df.iloc[:, 2].values
            else:
                df["adx"]      = 25.0
                df["plus_di"]  = 25.0
                df["minus_di"] = 25.0
        else:
            # Approximate ADX
            df["adx"]      = 25.0  # placeholder
            df["plus_di"]  = 25.0
            df["minus_di"] = 25.0

        df["adx_strong"]   = (df["adx"] > 25).astype(float)
        df["adx_very_strong"] = (df["adx"] > 50).astype(float)
        df["di_bullish"]   = (df["plus_di"] > df["minus_di"]).astype(float)

        # Normalize MACD
        df["macd"] = df["macd"] / (c + 1e-10)
        df["macd_signal"] = df["macd_signal"] / (c + 1e-10)
        df["macd_hist"] = df["macd_hist"] / (c + 1e-10)

        # Add EMA slopes and drop raw EMAs
        for period in [9, 21, 50, 200]:
            ema_s = df[f"ema_{period}"]
            df[f"ema_{period}_slope"] = (ema_s - ema_s.shift(5)) / (ema_s.shift(5) + 1e-10)
            
        # Directional Feature: MACD Hist Slope
        df["macd_hist_slope"] = df["macd_hist"].diff(3)
        
        df = df.drop(columns=["ema_9", "ema_21", "ema_50", "ema_200"])

        return df

    # ─── Feature Group 3: Momentum Indicators ─────────────────────────────

    def _add_momentum_indicators(self, df, o, h, l, c, v) -> pd.DataFrame:
        """RSI, Stochastic, Williams %R, ROC, CCI."""
        ta = self._talib if self._talib_available else None
        c_s = pd.Series(c, index=df.index)

        # RSI (14)
        if ta:
            df["rsi_14"] = ta.RSI(c, timeperiod=14)
        else:
            delta = c_s.diff()
            gain  = delta.where(delta > 0, 0).rolling(14).mean()
            loss  = (-delta.where(delta < 0, 0)).rolling(14).mean()
            rs    = gain / (loss + 1e-10)
            df["rsi_14"] = (100 - 100 / (1 + rs)).values

        df["rsi_overbought"]  = (df["rsi_14"] > 70).astype(float)
        df["rsi_oversold"]    = (df["rsi_14"] < 30).astype(float)
        df["rsi_bullish"]     = (df["rsi_14"] > 50).astype(float)
        df["rsi_normalized"]  = df["rsi_14"] / 100.0

        # Directional Feature: RSI Slope
        df["rsi_slope_10"] = df["rsi_14"].diff(10)

        # RSI fast (7) for shorter-term momentum
        if ta:
            df["rsi_7"] = ta.RSI(c, timeperiod=7)
        else:
            delta = c_s.diff()
            gain  = delta.where(delta > 0, 0).rolling(7).mean()
            loss  = (-delta.where(delta < 0, 0)).rolling(7).mean()
            rs    = gain / (loss + 1e-10)
            df["rsi_7"] = (100 - 100 / (1 + rs)).values

        # Stochastic (14,3,3)
        if ta:
            stoch_k, stoch_d = ta.STOCH(h, l, c, fastk_period=14, slowk_period=3,
                                         slowk_matype=0, slowd_period=3, slowd_matype=0)
            df["stoch_k"] = stoch_k
            df["stoch_d"] = stoch_d
        else:
            h_s, l_s = pd.Series(h, index=df.index), pd.Series(l, index=df.index)
            lowest_low   = l_s.rolling(14).min()
            highest_high = h_s.rolling(14).max()
            raw_k = 100 * (c_s - lowest_low) / (highest_high - lowest_low + 1e-10)
            df["stoch_k"] = raw_k.rolling(3).mean()
            df["stoch_d"] = df["stoch_k"].rolling(3).mean()

        df["stoch_oversold"]  = (df["stoch_k"] < 20).astype(float)
        df["stoch_overbought"]= (df["stoch_k"] > 80).astype(float)
        df["stoch_cross_up"]  = ((df["stoch_k"] > df["stoch_d"]) &
                                 (df["stoch_k"].shift(1) <= df["stoch_d"].shift(1))).astype(float)

        # Rate of Change (momentum)
        for period in [5, 10, 20]:
            df[f"roc_{period}"] = c_s.pct_change(period).values

        # CCI (Commodity Channel Index)
        if ta:
            df["cci_14"] = ta.CCI(h, l, c, timeperiod=14)
        else:
            tp  = (pd.Series(h, index=df.index) + pd.Series(l, index=df.index) + c_s) / 3
            sma = tp.rolling(14).mean()
            mad = tp.rolling(14).apply(lambda x: np.abs(x - x.mean()).mean(), raw=True)
            df["cci_14"] = ((tp - sma) / (0.015 * mad + 1e-10)).values

        df["cci_overbought"]  = (df["cci_14"] > 100).astype(float)
        df["cci_oversold"]    = (df["cci_14"] < -100).astype(float)

        return df

    # ─── Feature Group 4: Volatility Indicators ───────────────────────────

    def _add_volatility_indicators(self, df, h, l, c) -> pd.DataFrame:
        """Bollinger Bands, ATR, Keltner Channels."""
        ta = self._talib if self._talib_available else None
        c_s, h_s, l_s = pd.Series(c, index=df.index), pd.Series(h, index=df.index), pd.Series(l, index=df.index)

        # ATR (14) — key for position sizing
        if ta:
            df["atr_14"] = ta.ATR(h, l, c, timeperiod=14)
        else:
            tr = pd.concat([
                h_s - l_s,
                (h_s - c_s.shift(1)).abs(),
                (l_s - c_s.shift(1)).abs()
            ], axis=1).max(axis=1)
            df["atr_14"] = tr.rolling(14).mean().values

        df["atr_normalized"] = df["atr_14"] / (c_s + 1e-10)   # ATR as % of price

        # Bollinger Bands (20, 2)
        if ta:
            upper, mid, lower = ta.BBANDS(c, timeperiod=20, nbdevup=2, nbdevdn=2, matype=0)
            df["bb_upper"] = upper
            df["bb_mid"]   = mid
            df["bb_lower"] = lower
        else:
            sma20 = c_s.rolling(20).mean()
            std20 = c_s.rolling(20).std()
            df["bb_upper"] = sma20 + 2 * std20
            df["bb_mid"]   = sma20
            df["bb_lower"] = sma20 - 2 * std20

        bb_width = (df["bb_upper"] - df["bb_lower"]) / (df["bb_mid"] + 1e-10)
        df["bb_width"]      = bb_width
        df["bb_pct_b"]      = (c_s - df["bb_lower"]) / (df["bb_upper"] - df["bb_lower"] + 1e-10)
        df["bb_squeeze"]    = (bb_width < bb_width.rolling(50, min_periods=1).mean() * 0.7).astype(float)
        df["bb_above_upper"]= (c_s > df["bb_upper"]).astype(float)
        df["bb_below_lower"]= (c_s < df["bb_lower"]).astype(float)

        # Historical Volatility (20-bar)
        log_returns   = np.log(c_s / c_s.shift(1))
        df["hv_20"]   = log_returns.rolling(20).std().values * np.sqrt(252)  # annualized

        # Drop raw absolute features
        df = df.drop(columns=["atr_14", "bb_upper", "bb_mid", "bb_lower"])

        return df

    # ─── Feature Group 5: Volume Indicators ───────────────────────────────

    def _add_volume_indicators(self, df, h, l, c, v) -> pd.DataFrame:
        """OBV, VWAP, MFI, Volume Profile."""
        ta = self._talib if self._talib_available else None
        c_s, h_s, l_s, v_s = pd.Series(c, index=df.index), pd.Series(h, index=df.index), pd.Series(l, index=df.index), pd.Series(v, index=df.index)

        # OBV (On-Balance Volume)
        if ta:
            df["obv"] = ta.OBV(c, v)
        else:
            signs = np.sign(np.diff(c, prepend=c[0]))
            df["obv"] = (signs * v).cumsum()

        # OBV trend (normalized slope)
        obv_s = df["obv"]
        df["obv_slope"] = obv_s.diff(5) / (obv_s.abs().rolling(5).mean() + 1e-10)

        # Volume SMA ratios (volume surge detection)
        vol_sma20 = v_s.rolling(20).mean()
        df["vol_ratio_20"]  = (v_s / (vol_sma20 + 1e-10)).values
        df["vol_surge"]     = (df["vol_ratio_20"] > 2.0).astype(float)

        # MFI (Money Flow Index)
        if ta:
            df["mfi_14"] = ta.MFI(h, l, c, v, timeperiod=14)
        else:
            typical_price = (h_s + l_s + c_s) / 3
            raw_mf = typical_price * v_s
            pos_mf = raw_mf.where(typical_price > typical_price.shift(1), 0)
            neg_mf = raw_mf.where(typical_price < typical_price.shift(1), 0)
            mf_ratio = pos_mf.rolling(14).sum() / (neg_mf.rolling(14).sum() + 1e-10)
            df["mfi_14"] = (100 - 100 / (1 + mf_ratio)).values

        df["mfi_oversold"]   = (df["mfi_14"] < 20).astype(float)
        df["mfi_overbought"] = (df["mfi_14"] > 80).astype(float)

        # VWAP (rolling, using available bars)
        typical_price = (h_s + l_s + c_s) / 3
        df["vwap"] = (typical_price * v_s).rolling(20).sum() / (v_s.rolling(20).sum() + 1e-10)
        df["price_vs_vwap"] = (c_s - df["vwap"]) / (df["vwap"] + 1e-10)

        # Drop raw absolute features
        df = df.drop(columns=["obv", "vwap"])

        return df

    # ─── Feature Group 6: Price Action Features ───────────────────────────

    def _add_price_action_features(self, df, o, h, l, c) -> pd.DataFrame:
        """Bar structure, support/resistance proximity, trend strength."""
        c_s, h_s, l_s, o_s = pd.Series(c, index=df.index), pd.Series(h, index=df.index), pd.Series(l, index=df.index), pd.Series(o, index=df.index)

        # Bar body metrics
        body       = c_s - o_s
        total_range = h_s - l_s + 1e-10
        upper_wick  = h_s - pd.Series(np.maximum(o, c), index=df.index)
        lower_wick  = pd.Series(np.minimum(o, c), index=df.index) - l_s

        df["bar_body_pct"]       = (body.abs() / total_range).values
        df["bar_upper_wick_pct"] = (upper_wick / total_range).values
        df["bar_lower_wick_pct"] = (lower_wick / total_range).values
        df["bar_is_bullish"]     = (body > 0).astype(float).values
        df["bar_is_bearish"]     = (body < 0).astype(float).values

        # Multi-bar returns
        for n in [1, 3, 5, 10, 20]:
            df[f"return_{n}b"] = c_s.pct_change(n).values

        # 52-week high/low proximity (rolling 200 bars ≈ 8 days on 1h)
        rolling_high = h_s.rolling(200, min_periods=1).max()
        rolling_low  = l_s.rolling(200, min_periods=1).min()
        df["pct_from_high"] = ((c_s - rolling_high) / (rolling_high + 1e-10)).values
        df["pct_from_low"]  = ((c_s - rolling_low)  / (rolling_low + 1e-10)).values

        # Breakout detection (price breaking above recent range)
        resistance = h_s.rolling(20, min_periods=1).max().shift(1)
        support    = l_s.rolling(20, min_periods=1).min().shift(1)
        df["breakout_up"]   = (c_s > resistance).astype(float).values
        df["breakout_down"] = (c_s < support).astype(float).values
        
        # Smart Money Concepts: Liquidity Sweeps
        # Bullish: Price dips below support (grabbing stop losses) but closes back above
        df["liquidity_sweep_bullish"] = ((l_s < support) & (c_s > support)).astype(float).values
        # Bearish: Price spikes above resistance but closes back below
        df["liquidity_sweep_bearish"] = ((h_s > resistance) & (c_s < resistance)).astype(float).values

        # Consecutive bull/bear bars
        is_bull = (c_s > o_s)
        bull_streak = is_bull.rolling(5, min_periods=1).sum()
        df["bull_streak_5"] = bull_streak.values
        df["bear_streak_5"] = (5 - bull_streak).values

        # --- Directional Price Structure Features ---
        df['price_vs_20h_high'] = (c_s / h_s.rolling(20).max() - 1).values
        df['price_vs_20h_low']  = (c_s / l_s.rolling(20).min() - 1).values
        
        df['price_vs_50h_high'] = (c_s / h_s.rolling(50).max() - 1).values
        df['price_vs_50h_low']  = (c_s / l_s.rolling(50).min() - 1).values
        
        # Multi-period return asymmetry
        up_moves   = c_s.diff().clip(lower=0).rolling(10).mean()
        down_moves = c_s.diff().clip(upper=0).abs().rolling(10).mean()
        df['return_asymmetry_10'] = ((up_moves - down_moves) / (up_moves + down_moves + 1e-8)).values

        # Candle body direction persistence
        body_direction = np.sign(c_s - o_s)
        df['body_persistence_10'] = body_direction.rolling(10).mean().values

        # Price acceleration
        returns = c_s.pct_change()
        df['price_acceleration'] = returns.diff(3).rolling(5).mean().values

        return df

    # ─── Feature Group 8: Bear Market Regime Features (FIX 3) ─────────────

    def _add_bear_market_features(self, df: pd.DataFrame, c) -> pd.DataFrame:
        """
        Inject macro-regime awareness into XGBoost's feature set.
        Teaches XGBoost that in bear market conditions, LONG signal reliability
        drops drastically — it should learn to suppress those signals from the data.

        Features:
          btc_200_ema_distance  : % distance from 200 EMA (negative in bear markets)
          realized_vol_30d      : annualized realized volatility over 30 days
          vol_percentile_90d    : how extreme current vol is vs last 90 days (0-1)
          ema_200_slope         : slope of the 200 EMA over last 20 bars (trend direction proxy)
          trend_direction_bull  : binary 1=bull macro trend, 0=bear/neutral
        """
        c_s = pd.Series(c, index=df.index)
        ema_200 = c_s.ewm(span=200, adjust=False).mean()

        # % distance from 200 EMA — deeply negative in bear markets
        df["btc_200_ema_distance"] = ((c_s - ema_200) / (ema_200 + 1e-10)).values

        # Realized hourly returns
        log_rets = np.log(c_s / c_s.shift(1)).fillna(0)

        # 30-day (720 1H bars) realized volatility, annualized
        realized_vol_30d = log_rets.rolling(720, min_periods=50).std() * np.sqrt(365 * 24)
        df["realized_vol_30d"] = realized_vol_30d.values

        # 90-day (2160 1H bars) volatility percentile — how extreme is current vol?
        vol_pctile_90d = realized_vol_30d.rolling(2160, min_periods=100).rank(pct=True)
        df["vol_percentile_90d"] = vol_pctile_90d.values

        # 200 EMA slope over last 20 bars — positive = rising trend, negative = falling
        ema_200_slope = (ema_200 - ema_200.shift(20)) / (ema_200.shift(20) + 1e-10)
        df["ema_200_slope"] = ema_200_slope.values

        # Binary macro trend direction: 1 if rising 200 EMA (bull), 0 if falling (bear)
        df["trend_direction_bull"] = (ema_200_slope > 0.002).astype(float).values

        return df

    # ─── Feature Group 7: Time Features ──────────────────────────────────

    def _add_time_features(self, df) -> pd.DataFrame:
        """Cyclical time encoding (hour of day, day of week)."""
        time_col = "timestamp" if "timestamp" in df.columns else "open_time"
        if time_col not in df.columns:
            return df

        dt = pd.to_datetime(df[time_col], utc=True)
        hour = dt.dt.hour
        dow  = dt.dt.dayofweek  # 0=Monday

        # Cyclical encoding (avoids 23→0 discontinuity)
        df["hour_sin"] = np.sin(2 * np.pi * hour / 24)
        df["hour_cos"] = np.cos(2 * np.pi * hour / 24)
        df["dow_sin"]  = np.sin(2 * np.pi * dow / 7)
        df["dow_cos"]  = np.cos(2 * np.pi * dow / 7)

        # Binary flags
        df["is_weekend"]        = (dow >= 5).astype(float)
        df["is_asia_session"]   = ((hour >= 0)  & (hour < 8)).astype(float)
        df["is_london_session"] = ((hour >= 8)  & (hour < 16)).astype(float)
        df["is_ny_session"]     = ((hour >= 13) & (hour < 22)).astype(float)

        return df

    # ─── Feature Group 8: Macro Features ─────────────────────────────────

    def _add_macro_features(self, df, macro_df: pd.DataFrame) -> pd.DataFrame:
        """
        Merge macro indicators (VIX, DXY, Fear & Greed) by date.
        Macro data is daily; forward-fill to match higher timeframes.
        """
        df = df.copy()
        time_col = "timestamp" if "timestamp" in df.columns else "open_time"
        if time_col in df.columns:
            dt = pd.to_datetime(df[time_col], utc=True).dt.normalize()
        else:
            return df
            
        if macro_df.empty:
            return df

        macro_df = macro_df.copy()
        if "date" in macro_df.columns:
            macro_df["date"] = pd.to_datetime(macro_df["date"], utc=True)
            macro_df = macro_df.set_index("date").sort_index()

        # Map macro values to each bar
        for col in ["vix", "dxy", "spy_close", "tnx", "fear_greed_index"]:
            if col in macro_df.columns:
                macro_series = macro_df[col]
                df[col] = dt.map(macro_series).ffill().values

        # Derived macro features
        if "vix" in df.columns:
            df["vix_elevated"] = (df["vix"] > 25).astype(float)
            df["vix_extreme"]  = (df["vix"] > 40).astype(float)

        if "fear_greed_index" in df.columns:
            df["fg_extreme_greed"] = (df["fear_greed_index"] > 75).astype(float)
            df["fg_extreme_fear"]  = (df["fear_greed_index"] < 25).astype(float)
            df["fg_normalized"]    = df["fear_greed_index"] / 100.0

        return df


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)

    # Smoke test with synthetic data
    n = 300
    np.random.seed(42)
    price = 50000 + np.cumsum(np.random.randn(n) * 100)
    df_test = pd.DataFrame({
        "open_time": pd.date_range("2024-01-01", periods=n, freq="1h", tz="UTC"),
        "open":  price + np.random.randn(n) * 10,
        "high":  price + np.abs(np.random.randn(n)) * 50,
        "low":   price - np.abs(np.random.randn(n)) * 50,
        "close": price,
        "volume": np.random.rand(n) * 1_000_000,
    })
    df_test["high"] = df_test[["open", "high", "close"]].max(axis=1)
    df_test["low"]  = df_test[["open", "low", "close"]].min(axis=1)

    fb = FeatureBuilder()
    result = fb.build_dataset(df_test)
    feat_cols = fb.get_feature_columns(result)

    print(f"\n✅ Feature count: {len(feat_cols)}")
    print(f"✅ Dataset shape: {result.shape}")
    print(f"✅ First 10 features: {feat_cols[:10]}")

    # Inference test
    vec = fb.build_single(df_test)
    print(f"✅ Inference vector: {len(vec)} keys")
    nans = [k for k, v in vec.items() if not k.startswith("_") and isinstance(v, float) and np.isnan(v)]
    print(f"✅ NaN features: {len(nans)} (should be 0 or very few)")
