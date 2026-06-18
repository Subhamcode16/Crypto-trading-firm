"""
ml_engine/data/pipeline.py
──────────────────────────
Data Pipeline Orchestrator.

Responsibilities:
  - Bootstrap: Fetch 3 years of historical OHLCV on first run
  - Incremental: Pick up from last stored timestamp (no re-downloads)
  - Store to PostgreSQL (production) or SQLite (dev/fallback)
  - Save Parquet snapshots for offline ML training
  - Schedule nightly updates

Usage:
  python -m ml_engine.data.pipeline bootstrap       # First run: full history
  python -m ml_engine.data.pipeline update          # Incremental update only
  python -m ml_engine.data.pipeline export          # Export to Parquet
"""

import asyncio
import logging
import os
import sys
import sqlite3
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd

from ml_engine.data.fetcher import (
    BinanceFetcher, CoinGeckoFetcher, FearGreedFetcher, MacroFetcher,
    DEFAULT_SYMBOLS, TIMEFRAME_MS
)
from ml_engine.data.validators import DataValidator

logger = logging.getLogger(__name__)

# ─── Config ─────────────────────────────────────────────────────────────────
PROJECT_ROOT  = Path(__file__).parent.parent.parent
DATA_DIR      = PROJECT_ROOT / "ml_engine" / "data" / "store"
PARQUET_DIR   = DATA_DIR / "parquet"
SQLITE_PATH   = DATA_DIR / "cryptobot.db"

BOOTSTRAP_SINCE = "2021-01-01"   # Start of training dataset
TARGET_SYMBOLS  = DEFAULT_SYMBOLS
TARGET_TIMEFRAMES = ["1h", "4h", "1d"]   # Primary timeframes for ML

for _d in [DATA_DIR, PARQUET_DIR]:
    _d.mkdir(parents=True, exist_ok=True)


class StorageBackend:
    """
    Abstraction over storage backends.
    Tries PostgreSQL first, falls back to SQLite automatically.
    """

    def __init__(self):
        self._pg_engine = None
        self._sqlite_conn: Optional[sqlite3.Connection] = None
        self._backend = None
        self._init_backend()

    def _init_backend(self):
        """Try PostgreSQL, fall back to SQLite."""
        db_url = os.getenv("DATABASE_URL", "")
        if db_url:
            try:
                from sqlalchemy import create_engine, text
                engine = create_engine(db_url, pool_pre_ping=True)
                with engine.connect() as conn:
                    conn.execute(text("SELECT 1"))
                self._pg_engine = engine
                self._backend = "postgres"
                logger.info(f"[Storage] ✅ PostgreSQL connected: {db_url[:30]}...")
                return
            except Exception as e:
                logger.warning(f"[Storage] PostgreSQL unavailable ({e}), falling back to SQLite")

        # SQLite fallback
        self._sqlite_conn = sqlite3.connect(str(SQLITE_PATH), check_same_thread=False)
        self._init_sqlite()
        self._backend = "sqlite"
        logger.info(f"[Storage] ✅ SQLite backend: {SQLITE_PATH}")

    def _init_sqlite(self):
        """Create SQLite tables matching the PostgreSQL schema."""
        cur = self._sqlite_conn.cursor()
        cur.executescript("""
            CREATE TABLE IF NOT EXISTS ohlcv (
                symbol    TEXT    NOT NULL,
                timeframe TEXT    NOT NULL,
                open_time TEXT    NOT NULL,
                open      REAL    NOT NULL,
                high      REAL    NOT NULL,
                low       REAL    NOT NULL,
                close     REAL    NOT NULL,
                volume    REAL    NOT NULL,
                close_time TEXT,
                quote_volume REAL DEFAULT 0,
                num_trades   INTEGER DEFAULT 0,
                taker_buy_base  REAL DEFAULT 0,
                taker_buy_quote REAL DEFAULT 0,
                PRIMARY KEY (symbol, timeframe, open_time)
            );
            CREATE TABLE IF NOT EXISTS market_metadata (
                recorded_at TEXT PRIMARY KEY,
                fear_greed_index INTEGER,
                fear_greed_label TEXT,
                btc_dominance    REAL,
                total_market_cap REAL,
                vix  REAL,
                dxy  REAL,
                spy_close REAL
            );
            CREATE TABLE IF NOT EXISTS fetch_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fetched_at TEXT,
                source     TEXT,
                symbol     TEXT,
                timeframe  TEXT,
                rows_fetched INTEGER,
                from_time  TEXT,
                to_time    TEXT,
                success    INTEGER DEFAULT 1,
                error_msg  TEXT
            );
        """)
        self._sqlite_conn.commit()

    def get_last_stored_time(self, symbol: str, timeframe: str) -> Optional[datetime]:
        """
        Find the most recent open_time stored for a given symbol+timeframe.
        Returns None if no data exists yet (first run).
        """
        if self._backend == "postgres":
            from sqlalchemy import text
            with self._pg_engine.connect() as conn:
                row = conn.execute(text(
                    "SELECT MAX(open_time) FROM ohlcv WHERE symbol=:s AND timeframe=:tf"
                ), {"s": symbol, "tf": timeframe}).fetchone()
            return row[0] if row and row[0] else None
        else:
            cur = self._sqlite_conn.cursor()
            cur.execute(
                "SELECT MAX(open_time) FROM ohlcv WHERE symbol=? AND timeframe=?",
                (symbol, timeframe)
            )
            row = cur.fetchone()
            if row and row[0]:
                return datetime.fromisoformat(row[0]).replace(tzinfo=timezone.utc)
            return None

    def upsert_ohlcv(self, df: pd.DataFrame) -> int:
        """
        Insert or replace OHLCV rows. Returns number of rows written.
        Uses ON CONFLICT DO NOTHING to avoid duplicates.
        """
        if df.empty:
            return 0

        # Normalize for storage
        df = df.copy()
        df["open_time"]  = df["open_time"].astype(str)
        df["close_time"] = df["close_time"].astype(str) if "close_time" in df else ""

        cols = ["symbol", "timeframe", "open_time", "open", "high", "low",
                "close", "volume", "close_time", "quote_volume",
                "num_trades", "taker_buy_base", "taker_buy_quote"]

        # Fill missing columns with defaults
        for c in cols:
            if c not in df.columns:
                df[c] = 0

        rows = df[cols].to_dict(orient="records")

        if self._backend == "postgres":
            from sqlalchemy import text
            sql = text("""
                INSERT INTO ohlcv (symbol, timeframe, open_time, open, high, low,
                    close, volume, close_time, quote_volume, num_trades,
                    taker_buy_base, taker_buy_quote)
                VALUES (:symbol, :timeframe, :open_time, :open, :high, :low,
                    :close, :volume, :close_time, :quote_volume, :num_trades,
                    :taker_buy_base, :taker_buy_quote)
                ON CONFLICT (symbol, timeframe, open_time) DO NOTHING
            """)
            with self._pg_engine.begin() as conn:
                conn.execute(sql, rows)
        else:
            sql = """
                INSERT OR IGNORE INTO ohlcv
                (symbol, timeframe, open_time, open, high, low, close, volume,
                 close_time, quote_volume, num_trades, taker_buy_base, taker_buy_quote)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
            data = [(r["symbol"], r["timeframe"], r["open_time"],
                     r["open"], r["high"], r["low"], r["close"], r["volume"],
                     r["close_time"], r["quote_volume"], r["num_trades"],
                     r["taker_buy_base"], r["taker_buy_quote"]) for r in rows]
            self._sqlite_conn.executemany(sql, data)
            self._sqlite_conn.commit()

        return len(rows)

    def load_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        since: Optional[str] = None,
        until: Optional[str] = None,
    ) -> pd.DataFrame:
        """
        Load OHLCV data from storage into a DataFrame.
        Used by the feature builder and model trainers.
        """
        if self._backend == "postgres":
            from sqlalchemy import text
            conditions = ["symbol=:s", "timeframe=:tf"]
            params: dict = {"s": symbol, "tf": timeframe}
            if since:
                conditions.append("open_time >= :since")
                params["since"] = since
            if until:
                conditions.append("open_time <= :until")
                params["until"] = until
            where = " AND ".join(conditions)
            sql = text(f"SELECT * FROM ohlcv WHERE {where} ORDER BY open_time")
            with self._pg_engine.connect() as conn:
                df = pd.read_sql(sql, conn, params=params)
        else:
            conditions = ["symbol=?", "timeframe=?"]
            params_list = [symbol, timeframe]
            if since:
                conditions.append("open_time >= ?")
                params_list.append(since)
            if until:
                conditions.append("open_time <= ?")
                params_list.append(until)
            where = " AND ".join(conditions)
            sql = f"SELECT * FROM ohlcv WHERE {where} ORDER BY open_time"
            df = pd.read_sql_query(sql, self._sqlite_conn, params=params_list)

        if not df.empty:
            df["open_time"] = pd.to_datetime(df["open_time"], utc=True, format="mixed")
            if "close_time" in df.columns:
                df["close_time"] = pd.to_datetime(df["close_time"], utc=True, errors="coerce")
            for col in ["open", "high", "low", "close", "volume"]:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        return df

    def log_fetch(self, source: str, symbol: str, timeframe: str,
                  rows: int, from_time: str, to_time: str,
                  success: bool = True, error: str = ""):
        """Log a data fetch operation."""
        now = datetime.now(timezone.utc).isoformat()
        if self._backend == "postgres":
            from sqlalchemy import text
            with self._pg_engine.begin() as conn:
                conn.execute(text("""
                    INSERT INTO fetch_log
                    (fetched_at, source, symbol, timeframe, rows_fetched, from_time, to_time, success, error_msg)
                    VALUES (:at, :src, :sym, :tf, :rows, :from, :to, :ok, :err)
                """), {"at": now, "src": source, "sym": symbol, "tf": timeframe,
                       "rows": rows, "from": from_time, "to": to_time,
                       "ok": success, "err": error})
        else:
            self._sqlite_conn.execute("""
                INSERT INTO fetch_log
                (fetched_at, source, symbol, timeframe, rows_fetched, from_time, to_time, success, error_msg)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (now, source, symbol, timeframe, rows, from_time, to_time,
                  int(success), error))
            self._sqlite_conn.commit()

    @property
    def backend_name(self) -> str:
        return self._backend

    @property
    def engine_or_conn(self):
        """Return SQLAlchemy engine or SQLite connection for pandas."""
        return self._pg_engine if self._backend == "postgres" else self._sqlite_conn

class DataPipeline:
    """
    Main orchestrator for the ML data pipeline.

    Modes:
      bootstrap  — Full historical fetch (3 years), first run only
      update     — Incremental fetch (only new bars since last stored)
      export     — Dump stored data to Parquet for ML training
    """

    def __init__(self):
        self.storage = StorageBackend()
        self.validator = DataValidator()
        logger.info(f"[Pipeline] Initialized with {self.storage.backend_name} backend")

    async def bootstrap(
        self,
        symbols: List[str] = TARGET_SYMBOLS,
        timeframes: List[str] = TARGET_TIMEFRAMES,
        since: str = BOOTSTRAP_SINCE,
    ):
        """
        Full historical data download. Run once on first setup.
        Skips data that already exists in storage.
        """
        logger.info("=" * 60)
        logger.info(f"[Pipeline] BOOTSTRAP MODE | since={since}")
        logger.info(f"[Pipeline] Symbols: {symbols} | Timeframes: {timeframes}")
        logger.info("=" * 60)

        total_rows = 0
        async with BinanceFetcher() as fetcher:
            for symbol in symbols:
                for tf in timeframes:
                    last_stored = self.storage.get_last_stored_time(symbol, tf)

                    if last_stored:
                        # Resume from last stored point
                        fetch_from = (last_stored + timedelta(
                            milliseconds=TIMEFRAME_MS.get(tf, 3_600_000)
                        )).isoformat()
                        logger.info(f"[Pipeline] {symbol} {tf}: resuming from {fetch_from}")
                    else:
                        fetch_from = since
                        logger.info(f"[Pipeline] {symbol} {tf}: fresh start from {since}")

                    try:
                        df = await fetcher.fetch_ohlcv(symbol, tf, since=fetch_from)
                        if df.empty:
                            logger.info(f"[Pipeline] {symbol} {tf}: no new data")
                            continue

                        # Validate before storing
                        df, report = self.validator.validate(df, symbol, tf)
                        if report["rows_dropped"] > 0:
                            logger.warning(f"[Pipeline] {symbol} {tf}: dropped {report['rows_dropped']} invalid rows")

                        rows = self.storage.upsert_ohlcv(df)
                        total_rows += rows
                        self.storage.log_fetch(
                            "binance", symbol, tf, rows,
                            str(df["open_time"].min()), str(df["open_time"].max())
                        )
                        logger.info(f"[Pipeline] ✅ {symbol} {tf}: {rows:,} rows stored")

                    except Exception as e:
                        logger.error(f"[Pipeline] ❌ {symbol} {tf}: {e}")
                        self.storage.log_fetch("binance", symbol, tf, 0, "", "", False, str(e))

        logger.info(f"\n[Pipeline] 🎯 Bootstrap complete: {total_rows:,} total rows stored")
        return total_rows

    async def update(
        self,
        symbols: List[str] = TARGET_SYMBOLS,
        timeframes: List[str] = TARGET_TIMEFRAMES,
    ):
        """
        Incremental update — fetch only new bars since last stored timestamp.
        Designed to run nightly via scheduler.
        """
        logger.info("[Pipeline] UPDATE MODE — fetching latest bars")
        total_new = 0

        async with BinanceFetcher() as fetcher:
            for symbol in symbols:
                for tf in timeframes:
                    last_stored = self.storage.get_last_stored_time(symbol, tf)

                    if last_stored is None:
                        logger.warning(f"[Pipeline] {symbol} {tf}: no data found, run bootstrap first")
                        continue

                    # Fetch last 500 bars to catch up (handles weekends, gaps)
                    df = await fetcher.fetch_latest(symbol, tf, last_n=500)
                    if df.empty:
                        continue

                    # Only keep rows newer than last stored
                    df = df[df["open_time"] > last_stored]
                    if df.empty:
                        logger.info(f"[Pipeline] {symbol} {tf}: already up to date")
                        continue

                    df, _ = self.validator.validate(df, symbol, tf)
                    rows = self.storage.upsert_ohlcv(df)
                    total_new += rows

                    if rows > 0:
                        logger.info(f"[Pipeline] {symbol} {tf}: +{rows} new bars")

        logger.info(f"[Pipeline] Update complete: {total_new} new rows")
        return total_new

    def export_parquet(
        self,
        symbols: List[str] = TARGET_SYMBOLS,
        timeframes: List[str] = TARGET_TIMEFRAMES,
        since: Optional[str] = None,
    ) -> Dict[str, Path]:
        """
        Export data to Parquet files for fast ML training.
        Returns dict of {symbol_timeframe: path}.
        """
        logger.info("[Pipeline] Exporting to Parquet...")
        exported = {}

        for symbol in symbols:
            for tf in timeframes:
                df = self.storage.load_ohlcv(symbol, tf, since=since)
                if df.empty:
                    logger.warning(f"[Pipeline] No data to export: {symbol} {tf}")
                    continue

                filename = f"{symbol.replace('/', '_')}_{tf}.parquet"
                path = PARQUET_DIR / filename
                df.to_parquet(path, index=False, engine="pyarrow", compression="snappy")

                exported[f"{symbol}_{tf}"] = path
                logger.info(f"[Pipeline] ✅ Exported {symbol} {tf}: {len(df):,} rows → {path}")

        return exported

    async def fetch_macro_data(self):
        """Fetch and store macro indicators (VIX, DXY, SPY, Fear & Greed)."""
        logger.info("[Pipeline] Fetching macro data...")

        # Fear & Greed (async)
        fg_fetcher = FearGreedFetcher()
        fg_df = await fg_fetcher.get_history(days=365 * 3)
        logger.info(f"[Pipeline] Fear & Greed: {len(fg_df)} days fetched")

        # Macro (sync, run in thread)
        macro_fetcher = MacroFetcher()
        macro_df = await asyncio.to_thread(macro_fetcher.fetch_macro_data, BOOTSTRAP_SINCE)
        logger.info(f"[Pipeline] Macro (VIX/DXY/SPY): {len(macro_df)} days fetched")

        return {"fear_greed": fg_df, "macro": macro_df}

    def get_training_data(
        self,
        symbol: str,
        timeframe: str = "1h",
        since: Optional[str] = None,
    ) -> pd.DataFrame:
        """
        Load OHLCV data ready for ML training.
        This is the primary interface for model trainers.
        """
        df = self.storage.load_ohlcv(symbol, timeframe, since=since)
        if df.empty:
            raise RuntimeError(
                f"No data for {symbol} {timeframe}. Run: python -m ml_engine.data.pipeline bootstrap"
            )
        logger.info(f"[Pipeline] Loaded {len(df):,} bars for {symbol} {timeframe} training")
        return df

    def get_status(self) -> Dict:
        """Return status of data availability per symbol/timeframe."""
        status = {"backend": self.storage.backend_name, "data": {}}
        for sym in TARGET_SYMBOLS:
            status["data"][sym] = {}
            for tf in TARGET_TIMEFRAMES:
                last = self.storage.get_last_stored_time(sym, tf)
                df = self.storage.load_ohlcv(sym, tf)
                status["data"][sym][tf] = {
                    "rows":      len(df),
                    "last_bar":  str(last.date()) if last else "NO DATA",
                    "ready":     len(df) > 100,
                }
        return status


# ─── CLI Entry Point ──────────────────────────────────────────────────────
if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
        stream=sys.stdout
    )

    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    pipeline = DataPipeline()

    if cmd == "bootstrap":
        asyncio.run(pipeline.bootstrap())
        asyncio.run(pipeline.fetch_macro_data())

    elif cmd == "update":
        asyncio.run(pipeline.update())

    elif cmd == "export":
        exported = pipeline.export_parquet()
        print(f"\nExported {len(exported)} Parquet files:")
        for key, path in exported.items():
            print(f"  {key}: {path}")

    elif cmd == "status":
        import json
        status = pipeline.get_status()
        print("\n📊 Data Pipeline Status:")
        print(json.dumps(status, indent=2, default=str))

    else:
        print(f"Unknown command: {cmd}")
        print("Usage: python -m ml_engine.data.pipeline [bootstrap|update|export|status]")
