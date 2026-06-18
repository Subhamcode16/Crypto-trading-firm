import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from ml_engine.models.xgb_model import XGBModel

def print_feature_importance():
    model_path = os.path.join(os.path.dirname(__file__), '..', 'ml_engine', 'models', 'saved', 'xgb_BTC_USDT_1h.pkl')
    if not os.path.exists(model_path):
        print(f"Model not found at {model_path}")
        return
        
    model = XGBModel.load(model_path)
    importances = model.get_feature_importance(20)
    
    print("\n=== TOP 20 FEATURE IMPORTANCES ===")
    for i, (feat, imp) in enumerate(importances.items()):
        print(f"{i+1:2d}. {feat:<25} : {imp:.4f}")
        
if __name__ == "__main__":
    print_feature_importance()
