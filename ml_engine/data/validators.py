"""
ml_engine/data/validators.py
─────────────────────────────
Data quality validation for OHLCV DataFrames.

Checks:
  - Required column presence
  - OHLCV logical consistency (high >= low, close within range)
  - Duplicate timestamp detection
  - Gap detection (missing bars)
  - Outlier detection (>10x price moves in a single bar)
  - Volume sanity checks
"""

import logging
from datetime import timedelta
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

TIMEFRAME_DELTA = {
    "1m":  timedelta(minutes=1),
    "5m":  timedelta(minutes=5),
    "15m": timedelta(minutes=15),
    "1h":  timedelta(hours=1),
    "4h":  timedelta(hours=4),
    "1d":  timedelta(days=1),
}

OUTLIER_THRESHOLD   = 0.50   # 50% single-bar move is suspicious
MAX_ZERO_VOL_STREAK = 10     # >10 consecutive zero-volume bars = data issue


class DataValidator:
    """
    Validates and cleans OHLCV DataFrames before storage and ML use.
    Non-destructive: returns cleaned DataFrame + validation report.
    """

    def validate(
        self,
        df: pd.DataFrame,
        symbol: str,
        timeframe: str,
    ) -> Tuple[pd.DataFrame, Dict]:
        """
        Run all validation checks on a DataFrame.

        Returns:
            (cleaned_df, report_dict)
        """
        report = {
            "symbol":       symbol,
            "timeframe":    timeframe,
            "original_rows": len(df),
            "rows_dropped": 0,
            "issues":       [],
        }

        if df.empty:
            report["issues"].append("EMPTY_DATAFRAME")
            return df, report

        # 1. Ensure required columns exist
        df = self._check_columns(df, report)
        if df.empty:
            return df, report

        # 2. Convert types
        df = self._cast_types(df)

        # 3. Remove duplicates
        before = len(df)
        df = df.drop_duplicates(subset=["open_time"])
        dupes = before - len(df)
        if dupes:
            report["issues"].append(f"DUPLICATES_REMOVED:{dupes}")

        # 4. Sort by time
        df = df.sort_values("open_time").reset_index(drop=True)

        # 5. OHLCV logical checks (drop invalid bars)
        bad_ohlcv = (
            (df["high"] < df["low"]) |
            (df["close"] > df["high"]) |
            (df["close"] < df["low"]) |
            (df["open"] > df["high"]) |
            (df["open"] < df["low"]) |
            (df["high"] <= 0) |
            (df["low"] <= 0) |
            (df["volume"] < 0)
        )
        if bad_ohlcv.any():
            count = bad_ohlcv.sum()
            logger.warning(f"[Validator] {symbol} {timeframe}: {count} bars with invalid OHLCV, dropping")
            report["issues"].append(f"INVALID_OHLCV:{count}")
            df = df[~bad_ohlcv].reset_index(drop=True)

        # 6. Outlier detection (extreme single-bar moves)
        if len(df) > 10:
            returns = df["close"].pct_change().abs()
            outliers = returns > OUTLIER_THRESHOLD
            if outliers.sum() > 0:
                report["issues"].append(f"OUTLIER_BARS:{outliers.sum()}")
                logger.debug(f"[Validator] {symbol} {timeframe}: {outliers.sum()} outlier bars (>{OUTLIER_THRESHOLD*100:.0f}% move)")
                # Don't drop — these could be real flash crashes/pumps

        # 7. Gap detection (informational only)
        tf_delta = TIMEFRAME_DELTA.get(timeframe)
        if tf_delta and len(df) > 1:
            time_diffs = df["open_time"].diff().dt.total_seconds()
            expected_s = tf_delta.total_seconds()
            gaps = (time_diffs > expected_s * 2).sum()
            if gaps > 0:
                report["issues"].append(f"TIME_GAPS:{gaps}")
                logger.debug(f"[Validator] {symbol} {timeframe}: {gaps} time gaps detected")

        # 8. NaN check
        nan_counts = df[["open", "high", "low", "close", "volume"]].isna().sum()
        total_nans = nan_counts.sum()
        if total_nans > 0:
            # Forward-fill then back-fill NaNs (standard for OHLCV)
            df[["open", "high", "low", "close"]] = (
                df[["open", "high", "low", "close"]]
                .ffill()
                .bfill()
            )
            df["volume"] = df["volume"].fillna(0)
            report["issues"].append(f"NANS_FILLED:{total_nans}")

        report["rows_dropped"] = report["original_rows"] - len(df)
        report["final_rows"]   = len(df)
        report["status"]       = "CLEAN" if not report["issues"] else "CLEANED"

        if report["rows_dropped"] > 0:
            logger.info(f"[Validator] {symbol} {timeframe}: {report['rows_dropped']} rows dropped, {len(df)} remain")

        return df, report

    def _check_columns(self, df: pd.DataFrame, report: Dict) -> pd.DataFrame:
        """Ensure all required OHLCV columns are present."""
        required = {"open_time", "open", "high", "low", "close", "volume"}
        missing = required - set(df.columns)
        if missing:
            report["issues"].append(f"MISSING_COLUMNS:{missing}")
            logger.error(f"[Validator] Missing required columns: {missing}")
            return pd.DataFrame()
        return df

    def _cast_types(self, df: pd.DataFrame) -> pd.DataFrame:
        """Ensure correct dtypes for all columns."""
        df = df.copy()
        if not pd.api.types.is_datetime64_any_dtype(df["open_time"]):
            df["open_time"] = pd.to_datetime(df["open_time"], utc=True, errors="coerce")
        for col in ["open", "high", "low", "close", "volume"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        return df

    def validate_feature_vector(self, features: Dict) -> Tuple[bool, List[str]]:
        """
        Validate a feature vector dict before ML inference.
        Returns (is_valid, list_of_issues).
        """
        issues = []

        # Check for NaN/Inf values
        for key, val in features.items():
            if key.startswith("_"):
                continue
            if not isinstance(val, (int, float)):
                issues.append(f"NON_NUMERIC:{key}={val}")
            elif np.isnan(val):
                issues.append(f"NAN:{key}")
            elif np.isinf(val):
                issues.append(f"INF:{key}")

        if not features:
            issues.append("EMPTY_FEATURE_VECTOR")

        return len(issues) == 0, issues
