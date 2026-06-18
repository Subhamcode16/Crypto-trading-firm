@echo off
REM ============================================================
REM  ML Engine Setup Script — Crypto Trading Bot v2.0
REM  Windows PowerShell / CMD compatible
REM  Run as: .\setup_ml.bat
REM ============================================================

echo.
echo ====================================================
echo   ML Crypto Trading Bot - Setup Script
echo ====================================================
echo.

REM Check Python version
python --version 2>nul || (echo [ERROR] Python not found. Install from https://python.org & pause & exit /b 1)

REM Check if venv exists, create if not
if not exist ".venv\Scripts\activate.bat" (
    echo [1/7] Creating virtual environment...
    python -m venv .venv
) else (
    echo [1/7] Virtual environment already exists, skipping creation.
)

echo [2/7] Activating virtual environment...
call .venv\Scripts\activate.bat

echo [3/7] Upgrading pip, setuptools, wheel...
python -m pip install --upgrade pip setuptools wheel --quiet

REM ── TA-Lib Windows Binary Install ─────────────────────────────
echo [4/7] Installing TA-Lib (Windows pre-compiled binary)...
echo       Detecting Python version and architecture...

python -c "import platform; v=platform.python_version_tuple(); arch=platform.architecture()[0]; print(f'{v[0]}.{v[1]} {arch}')" > talib_info.tmp 2>nul
set /p PYINFO=<talib_info.tmp
del talib_info.tmp

echo       Python: %PYINFO%
echo       Downloading TA-Lib wheel from unofficial binaries...

REM Detect Python version for correct wheel
python -c "import sys; print(f'cp{sys.version_info.major}{sys.version_info.minor}')" > py_tag.tmp
set /p PY_TAG=<py_tag.tmp
del py_tag.tmp

REM Try installing TA-Lib from pre-compiled wheel
pip install "TA-Lib" --quiet 2>nul || (
    echo       Direct pip install failed, trying alternative...
    pip install "https://github.com/cgohlke/talib-build/releases/download/v0.4.28/TA_Lib-0.4.28-%PY_TAG%-win_amd64.whl" --quiet 2>nul || (
        echo       TA-Lib binary not found for this Python version.
        echo       Falling back to pandas-ta (no TA-Lib needed, all features available)
        echo       Note: TA-Lib gives slightly faster candlestick detection but is optional.
    )
)

REM Verify TA-Lib or confirm fallback
python -c "import talib; print('TA-Lib: OK')" 2>nul || echo       TA-Lib: NOT installed (pandas-ta fallback will be used)

echo [5/7] Installing ML core dependencies...
pip install tensorflow>=2.15.0 --quiet || echo [WARN] TensorFlow install failed - try Colab for training
pip install xgboost scikit-learn optuna --quiet
pip install "stable-baselines3>=2.3.0" "gymnasium>=0.29.0" shimmy --quiet

echo [6/7] Installing remaining dependencies...
pip install -r requirements_ml.txt --quiet

echo [7/7] Installing data dependencies...
pip install ccxt yfinance aiohttp pandas numpy pyarrow --quiet
pip install google-generativeai --quiet

echo.
echo ====================================================
echo   Verification
echo ====================================================
python -c "
import sys
print(f'Python: {sys.version}')
results = {}

# Test imports
try:
    import tensorflow as tf
    results['TensorFlow'] = tf.__version__
except Exception as e:
    results['TensorFlow'] = f'FAILED: {e}'

try:
    import xgboost
    results['XGBoost'] = xgboost.__version__
except:
    results['XGBoost'] = 'FAILED'

try:
    import stable_baselines3
    results['Stable-Baselines3'] = stable_baselines3.__version__
except:
    results['Stable-Baselines3'] = 'FAILED'

try:
    import gymnasium
    results['Gymnasium'] = gymnasium.__version__
except:
    results['Gymnasium'] = 'FAILED'

try:
    import talib
    results['TA-Lib'] = 'OK'
except:
    try:
        import pandas_ta
        results['TA-Lib'] = 'NOT FOUND (pandas-ta fallback OK)'
    except:
        results['TA-Lib'] = 'NOT FOUND'

try:
    import ccxt
    results['CCXT'] = ccxt.__version__
except:
    results['CCXT'] = 'FAILED'

try:
    import google.generativeai
    results['Gemini SDK'] = 'OK'
except:
    results['Gemini SDK'] = 'FAILED'

try:
    import pandas as pd
    import numpy as np
    results['Pandas/NumPy'] = f'{pd.__version__} / {np.__version__}'
except:
    results['Pandas/NumPy'] = 'FAILED'

print()
for lib, ver in results.items():
    status = '✅' if 'FAIL' not in str(ver) else '❌'
    print(f'  {status} {lib}: {ver}')
"

echo.
echo ====================================================
echo   Next Steps:
echo ====================================================
echo.
echo 1. Bootstrap historical data (BTC/ETH/SOL, 3 years):
echo    python -m ml_engine.data.pipeline bootstrap
echo.
echo 2. Train LSTM model (or use Colab):
echo    python -m ml_engine.models.lstm_trainer --symbol BTC/USDT --timeframe 1h
echo    (Notebook: notebooks/train_lstm_colab.ipynb)
echo.
echo 3. Train XGBoost model:
echo    python -m ml_engine.models.xgb_model
echo.
echo 4. Check data pipeline status:
echo    python -m ml_engine.data.pipeline status
echo.
echo ====================================================
echo   Setup Complete!
echo ====================================================
echo.

pause
