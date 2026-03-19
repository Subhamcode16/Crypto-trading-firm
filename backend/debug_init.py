import traceback
import sys
import os

# Add src to path
sys.path.append(os.path.join(os.getcwd(), 'src'))

try:
    from src.main import TradingBotApp
    print("Testing TradingBotApp initialization...")
    app = TradingBotApp()
    print("Success!")
except Exception:
    traceback.print_exc()
