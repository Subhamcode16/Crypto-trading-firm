import sqlite3
import pandas as pd
import numpy as np
import warnings

warnings.filterwarnings("ignore")

def generate_directional_labels(df: pd.DataFrame, horizon: int = 8, min_move_pct: float = 0.004) -> pd.Series:
    close = df['close']
    future_return = close.shift(-horizon) / close - 1
    
    true_range = pd.concat([
        df['high'] - df['low'],
        (df['high'] - close.shift(1)).abs(),
        (df['low']  - close.shift(1)).abs()
    ], axis=1).max(axis=1)
    atr_pct = true_range.shift(1).rolling(14).mean() / close
    
    long_threshold  = np.maximum(1.2 * atr_pct, min_move_pct)
    short_threshold = np.maximum(1.2 * atr_pct, min_move_pct)
    
    labels = pd.Series(0, index=df.index)
    labels[future_return >= long_threshold]  = 1
    labels[future_return <= -short_threshold] = 2
    labels.iloc[-horizon:] = np.nan
    
    return labels, future_return

def add_directional_features(df: pd.DataFrame) -> pd.DataFrame:
    # We assume 'macd_hist', 'rsi_14', 'adx', 'plus_di', 'minus_di' already exist, 
    # but since we are running this on raw OHLCV, we should use feature_builder first.
    return df

if __name__ == "__main__":
    from ml_engine.features.feature_builder import FeatureBuilder
    
    db_path = "ml_engine/data/store/cryptobot.db"
    conn = sqlite3.connect(db_path)
    df = pd.read_sql("SELECT * FROM ohlcv WHERE symbol='BTC/USDT' AND timeframe='1h' ORDER BY open_time", conn)
    
    fb = FeatureBuilder()
    df_feat = fb.build_dataset(df.copy())
    
    # Generate labels & future return
    labels, future_return = generate_directional_labels(df_feat)
    df_feat['future_return'] = future_return
    
    # --- Add Category 1 ---
    df_feat['macd_hist_slope']     = df_feat['macd_hist'].diff(3)
    df_feat['rsi_slope_5']         = df_feat['rsi_14'].diff(5)
    df_feat['rsi_slope_10']        = df_feat['rsi_14'].diff(10)
    df_feat['adx_slope']           = df_feat['adx'].diff(5)
    df_feat['plus_di_minus_di']    = df_feat['plus_di'] - df_feat['minus_di']
    df_feat['ema_9_21_cross']      = (
        (df_feat['close'] - df_feat['close'].ewm(span=9).mean()) - 
        (df_feat['close'] - df_feat['close'].ewm(span=21).mean())
    ) / df_feat['close']
    
    # --- Add Category 2 ---
    df_feat['price_vs_20h_high']   = df_feat['close'] / df_feat['high'].rolling(20).max() - 1
    df_feat['price_vs_20h_low']    = df_feat['close'] / df_feat['low'].rolling(20).min() - 1
    df_feat['price_vs_50h_high']   = df_feat['close'] / df_feat['high'].rolling(50).max() - 1
    df_feat['price_vs_50h_low']    = df_feat['close'] / df_feat['low'].rolling(50).min() - 1
    df_feat['hh_pattern']          = (df_feat['high'].rolling(5).max() > df_feat['high'].rolling(5).max().shift(5)).astype(int)
    df_feat['ll_pattern']          = (df_feat['low'].rolling(5).min() < df_feat['low'].rolling(5).min().shift(5)).astype(int)
    df_feat['close_position']      = (df_feat['close'] - df_feat['low']) / (df_feat['high'] - df_feat['low'] + 1e-8)
    
    # --- Add Category 3 ---
    df_feat['bull_close_streak']   = (
        (df_feat['close'] > df_feat['close'].shift(1)).astype(int)
        .groupby((df_feat['close'] <= df_feat['close'].shift(1)).cumsum())
        .cumsum()
    )
    df_feat['bear_close_streak']   = (
        (df_feat['close'] < df_feat['close'].shift(1)).astype(int)
        .groupby((df_feat['close'] >= df_feat['close'].shift(1)).cumsum())
        .cumsum()
    )
    df_feat['vwdp_5'] = ((df_feat['close'] - df_feat['open']) * df_feat['volume']).rolling(5).sum() / (df_feat['volume'].rolling(5).sum() + 1e-10)
    df_feat['vwdp_20'] = ((df_feat['close'] - df_feat['open']) * df_feat['volume']).rolling(20).sum() / (df_feat['volume'].rolling(20).sum() + 1e-10)
    
    # --- Add 5 Pure Pandas Features ---
    # 1. Multi-period return asymmetry
    up_moves   = df_feat['close'].diff().clip(lower=0).rolling(10).mean()
    down_moves = df_feat['close'].diff().clip(upper=0).abs().rolling(10).mean()
    df_feat['return_asymmetry_10'] = (up_moves - down_moves) / (up_moves + down_moves + 1e-8)

    # 2. Volume delta pressure
    df_feat['vol_buy_pressure'] = (
        df_feat['volume'] * ((df_feat['close'] - df_feat['low']) / (df_feat['high'] - df_feat['low'] + 1e-8))
    ).rolling(10).mean() / df_feat['volume'].rolling(10).mean()

    # 3. Candle body direction persistence
    body_direction = np.sign(df_feat['close'] - df_feat['open'])
    df_feat['body_persistence_5']  = body_direction.rolling(5).mean()
    df_feat['body_persistence_10'] = body_direction.rolling(10).mean()

    # 4. High-low range asymmetry
    df_feat['wick_asymmetry'] = (
        (df_feat['high'] - df_feat['close']) - (df_feat['close'] - df_feat['low'])
    ) / (df_feat['high'] - df_feat['low'] + 1e-8)

    # 5. Price acceleration
    returns = df_feat['close'].pct_change()
    df_feat['price_acceleration'] = returns.diff(3).rolling(5).mean()
    
    new_features = [
        'macd_hist_slope', 'rsi_slope_5', 'rsi_slope_10', 'adx_slope', 'plus_di_minus_di', 'ema_9_21_cross',
        'price_vs_20h_high', 'price_vs_20h_low', 'price_vs_50h_high', 'price_vs_50h_low', 'hh_pattern', 'll_pattern', 'close_position',
        'bull_close_streak', 'bear_close_streak', 'vwdp_5', 'vwdp_20',
        'return_asymmetry_10', 'vol_buy_pressure', 'body_persistence_5', 'body_persistence_10', 'wick_asymmetry', 'price_acceleration'
    ]
    
    print("\n--- Feature Correlation with future_return ---")
    corrs = {}
    for col in new_features:
        corr = df_feat[col].corr(df_feat['future_return'])
        corrs[col] = corr
        
    for k, v in sorted(corrs.items(), key=lambda item: abs(item[1]), reverse=True):
        print(f"{k:20}: {v:.4f}")
