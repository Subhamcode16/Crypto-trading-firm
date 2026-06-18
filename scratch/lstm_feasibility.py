import sqlite3
import pandas as pd
import numpy as np
from sklearn.preprocessing import StandardScaler
import tensorflow as tf

def lstm_feasibility_test(df_clean: pd.DataFrame, seq_len: int = 64) -> float:
    # Raw features — no indicator engineering
    # Just normalized price behavior
    returns      = df_clean['close'].pct_change()
    vol_ratio    = df_clean['volume'] / df_clean['volume'].rolling(20).mean()
    hl_range     = (df_clean['high'] - df_clean['low']) / df_clean['close']
    close_pos    = ((df_clean['close'] - df_clean['low']) / 
                    (df_clean['high'] - df_clean['low'] + 1e-8))
    
    data = np.column_stack([
        returns.fillna(0),
        vol_ratio.fillna(1),
        hl_range.fillna(0),
        close_pos.fillna(0.5)
    ])
    
    # Forward return label — binary: up or down
    future_ret = df_clean['close'].shift(-8) / df_clean['close'] - 1
    labels = (future_ret > 0).astype(int).fillna(0).values
    
    # Build sequences
    X, y = [], []
    for i in range(seq_len, len(data) - 8):
        X.append(data[i-seq_len:i])
        y.append(labels[i])
    
    X, y = np.array(X), np.array(y)
    
    # Strict temporal split
    split = int(len(X) * 0.80)
    X_train, X_test = X[:split], X[split:]
    y_train, y_test = y[:split], y[split:]
    
    # Minimal LSTM — just testing if signal exists
    model = tf.keras.Sequential([
        tf.keras.layers.LSTM(32, input_shape=(seq_len, 4)),
        tf.keras.layers.Dropout(0.3),
        tf.keras.layers.Dense(1, activation='sigmoid')
    ])
    
    model.compile(optimizer='adam', loss='binary_crossentropy',
                  metrics=['accuracy'])
    
    history = model.fit(
        X_train, y_train,
        validation_data = (X_test, y_test),
        epochs     = 20,
        batch_size = 64,
        verbose    = 1
    )
    
    val_acc = max(history.history['val_accuracy'])
    print(f"\nLSTM feasibility result: {val_acc:.4f}")
    
    if val_acc > 0.535:
        print("→ Sequential signal exists. Full LSTM build warranted.")
    elif val_acc > 0.515:
        print("→ Marginal signal. LSTM may work with more engineering.")
    else:
        print("→ No sequential signal detected. Consider Path 3.")
    
    return val_acc

if __name__ == "__main__":
    conn = sqlite3.connect('ml_engine/data/store/cryptobot.db')
    df_clean = pd.read_sql("SELECT * FROM ohlcv WHERE symbol='BTC/USDT' AND timeframe='1h' ORDER BY open_time", conn)
    lstm_feasibility_test(df_clean)
