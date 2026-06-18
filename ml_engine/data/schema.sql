-- ============================================================
-- ML Crypto Trading Bot — PostgreSQL Schema
-- TimescaleDB hypertable for time-series OHLCV data
-- Run: psql -U postgres -d cryptobot -f schema.sql
-- ============================================================

-- Enable TimescaleDB extension (if available)
CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;

-- ─────────────────────────────────────────────────────────────
-- OHLCV Candlestick Data
-- ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS ohlcv (
    id          BIGSERIAL,
    symbol      VARCHAR(20)     NOT NULL,   -- e.g. BTC/USDT
    timeframe   VARCHAR(5)      NOT NULL,   -- 1m, 5m, 15m, 1h, 4h, 1d
    open_time   TIMESTAMPTZ     NOT NULL,
    open        NUMERIC(24, 8)  NOT NULL,
    high        NUMERIC(24, 8)  NOT NULL,
    low         NUMERIC(24, 8)  NOT NULL,
    close       NUMERIC(24, 8)  NOT NULL,
    volume      NUMERIC(32, 8)  NOT NULL,
    close_time  TIMESTAMPTZ,
    quote_volume NUMERIC(32, 8) DEFAULT 0,
    num_trades  INTEGER         DEFAULT 0,
    taker_buy_base  NUMERIC(32, 8) DEFAULT 0,
    taker_buy_quote NUMERIC(32, 8) DEFAULT 0,
    created_at  TIMESTAMPTZ     DEFAULT NOW(),
    PRIMARY KEY (symbol, timeframe, open_time)
);

-- Convert to TimescaleDB hypertable for efficient time-range queries
-- (Only runs if TimescaleDB is installed; safe to skip otherwise)
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'timescaledb') THEN
        PERFORM create_hypertable('ohlcv', 'open_time',
            partitioning_column => 'symbol',
            number_partitions => 4,
            if_not_exists => TRUE,
            migrate_data => TRUE
        );
    END IF;
END $$;

-- Indexes for common query patterns
CREATE INDEX IF NOT EXISTS idx_ohlcv_symbol_tf_time
    ON ohlcv (symbol, timeframe, open_time DESC);

CREATE INDEX IF NOT EXISTS idx_ohlcv_time
    ON ohlcv (open_time DESC);

-- ─────────────────────────────────────────────────────────────
-- Market Metadata (Fear/Greed, Dominance, Macro)
-- ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS market_metadata (
    id              BIGSERIAL PRIMARY KEY,
    recorded_at     TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    fear_greed_index INTEGER,          -- 0-100 (Alternative.me)
    fear_greed_label VARCHAR(20),       -- "Fear", "Greed" etc.
    btc_dominance   NUMERIC(6, 3),      -- BTC market cap %
    total_market_cap NUMERIC(24, 2),    -- in USD
    vix             NUMERIC(10, 4),     -- CBOE VIX
    dxy             NUMERIC(10, 4),     -- US Dollar Index
    spy_close       NUMERIC(10, 4),     -- S&P 500 close
    UNIQUE (recorded_at)
);

CREATE INDEX IF NOT EXISTS idx_metadata_time ON market_metadata (recorded_at DESC);

-- ─────────────────────────────────────────────────────────────
-- Feature Vectors (pre-computed, ready for ML inference)
-- ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS feature_vectors (
    id              BIGSERIAL PRIMARY KEY,
    symbol          VARCHAR(20)     NOT NULL,
    timeframe       VARCHAR(5)      NOT NULL,
    bar_time        TIMESTAMPTZ     NOT NULL,
    feature_version VARCHAR(10)     NOT NULL DEFAULT '1.0',
    features        JSONB           NOT NULL,  -- flat dict of 120 floats
    created_at      TIMESTAMPTZ     DEFAULT NOW(),
    UNIQUE (symbol, timeframe, bar_time, feature_version)
);

CREATE INDEX IF NOT EXISTS idx_features_symbol_time
    ON feature_vectors (symbol, timeframe, bar_time DESC);

-- ─────────────────────────────────────────────────────────────
-- ML Signals (predictions from the ensemble)
-- ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS ml_signals (
    id              BIGSERIAL PRIMARY KEY,
    symbol          VARCHAR(20)     NOT NULL,
    signal_time     TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    lstm_prob_up    NUMERIC(6, 4),
    lstm_prob_down  NUMERIC(6, 4),
    lstm_prob_neutral NUMERIC(6, 4),
    xgb_confidence  NUMERIC(6, 4),
    xgb_signal_class VARCHAR(20),   -- STRONG_LONG, STRONG_SHORT, WEAK, NO_SIGNAL
    rl_action       SMALLINT,        -- 0=HOLD, 1=BUY, 2=SELL
    rl_confidence   NUMERIC(6, 4),
    ensemble_score  NUMERIC(6, 4),  -- final blended score
    market_regime   VARCHAR(20),    -- bull, bear, ranging, extreme_bear
    gatekeeper_decision VARCHAR(10), -- APPROVE, REJECT
    gatekeeper_reason TEXT,
    edge_case_triggered BOOLEAN     DEFAULT FALSE,
    edge_resolver_decision VARCHAR(10),
    final_action    VARCHAR(10),    -- BUY, SELL, HOLD, SKIP
    UNIQUE (symbol, signal_time)
);

-- ─────────────────────────────────────────────────────────────
-- Trades (paper + live)
-- ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS trades (
    id              BIGSERIAL PRIMARY KEY,
    trade_id        VARCHAR(50)     UNIQUE NOT NULL,
    symbol          VARCHAR(20)     NOT NULL,
    mode            VARCHAR(10)     NOT NULL DEFAULT 'paper', -- paper, live
    side            VARCHAR(5)      NOT NULL,  -- BUY, SELL
    entry_price     NUMERIC(24, 8),
    exit_price      NUMERIC(24, 8),
    quantity        NUMERIC(24, 8),
    stop_loss       NUMERIC(24, 8),
    take_profit     NUMERIC(24, 8),
    entry_time      TIMESTAMPTZ,
    exit_time       TIMESTAMPTZ,
    exit_reason     VARCHAR(30),    -- TP_HIT, SL_HIT, SIGNAL_REVERSE, MANUAL
    pnl_usd         NUMERIC(16, 4),
    pnl_pct         NUMERIC(10, 4),
    commission_usd  NUMERIC(12, 4)  DEFAULT 0,
    signal_id       BIGINT          REFERENCES ml_signals(id),
    rl_reward       NUMERIC(12, 6),  -- computed after close (Sharpe-adjusted PnL)
    status          VARCHAR(10)     NOT NULL DEFAULT 'open',  -- open, closed
    created_at      TIMESTAMPTZ     DEFAULT NOW(),
    updated_at      TIMESTAMPTZ     DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_trades_symbol ON trades (symbol, entry_time DESC);
CREATE INDEX IF NOT EXISTS idx_trades_status  ON trades (status);

-- ─────────────────────────────────────────────────────────────
-- Model Performance Log
-- ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS model_performance (
    id              BIGSERIAL PRIMARY KEY,
    logged_at       TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    model_name      VARCHAR(30)     NOT NULL,  -- lstm, xgboost, rl_ppo, ensemble
    version         VARCHAR(20),
    window_trades   INTEGER,        -- number of trades in measurement window
    win_rate        NUMERIC(6, 4),
    avg_r_multiple  NUMERIC(8, 4),
    sharpe_ratio    NUMERIC(8, 4),
    max_drawdown    NUMERIC(8, 4),
    accuracy        NUMERIC(6, 4),  -- for classification models
    notes           TEXT
);

-- ─────────────────────────────────────────────────────────────
-- Data Fetch Log (track what was downloaded)
-- ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS fetch_log (
    id              BIGSERIAL PRIMARY KEY,
    fetched_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    source          VARCHAR(20),    -- binance, coingecko, yfinance
    symbol          VARCHAR(20),
    timeframe       VARCHAR(5),
    rows_fetched    INTEGER,
    from_time       TIMESTAMPTZ,
    to_time         TIMESTAMPTZ,
    success         BOOLEAN         DEFAULT TRUE,
    error_msg       TEXT
);

-- ─────────────────────────────────────────────────────────────
-- System Events / Audit Log
-- ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS system_events (
    id              BIGSERIAL PRIMARY KEY,
    event_time      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    event_type      VARCHAR(30)     NOT NULL,  -- RETRAIN, DEPLOY, KILL_SWITCH, DRIFT_ALERT
    severity        VARCHAR(10)     NOT NULL DEFAULT 'INFO',
    description     TEXT,
    metadata        JSONB
);

-- Convenience view: recent trade performance
CREATE OR REPLACE VIEW v_recent_performance AS
SELECT
    symbol,
    COUNT(*)                                    AS total_trades,
    SUM(CASE WHEN pnl_usd > 0 THEN 1 ELSE 0 END) AS wins,
    ROUND(AVG(pnl_pct)::numeric, 4)             AS avg_pnl_pct,
    ROUND(SUM(pnl_usd)::numeric, 2)             AS total_pnl_usd,
    MAX(entry_time)                             AS last_trade_at
FROM trades
WHERE status = 'closed'
  AND entry_time > NOW() - INTERVAL '30 days'
GROUP BY symbol;

COMMENT ON TABLE ohlcv             IS 'OHLCV candlestick data from Binance (primary) and other sources';
COMMENT ON TABLE market_metadata   IS 'Daily macro snapshots: Fear/Greed, BTC dominance, VIX, DXY';
COMMENT ON TABLE feature_vectors   IS 'Pre-computed 120-dim ML feature vectors for each bar';
COMMENT ON TABLE ml_signals        IS 'All ML predictions and LLM agent decisions per signal';
COMMENT ON TABLE trades            IS 'All paper and live trades with outcomes';
COMMENT ON TABLE model_performance IS 'Rolling accuracy and performance metrics per model';
