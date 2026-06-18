import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

if __name__ == '__main__':
    print("Testing main.py initialization...")
    try:
        from src.main import TradingBotApp
        app = TradingBotApp()
        print("SUCCESS: TradingBotApp initialized without errors.")
    except Exception as e:
        print(f"FAILED: Initialization caught an error: {e}")
        import traceback
        traceback.print_exc()
