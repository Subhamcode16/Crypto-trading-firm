import logging
import pandas as pd
from datetime import datetime, timezone
import warnings

# Suppress warnings
warnings.filterwarnings("ignore", category=UserWarning)

# Import from the local Kronos model directory we copied
from .kronos import Kronos, KronosTokenizer, KronosPredictor

logger = logging.getLogger(__name__)

class KronosEngine:
    """
    Wrapper for the Kronos Foundation Model to forecast future candlestick prices.
    """
    def __init__(self, model_name: str = "NeoQuasar/Kronos-small", device: str = "cpu"):
        self.model_name = model_name
        self.device = device
        self.tokenizer = None
        self.model = None
        self.predictor = None
        self.is_loaded = False
        
    def load(self):
        try:
            # Make sure torch is imported only when needed so it doesn't crash lightweight environments
            import torch
            # Fallback to GPU if available and device wasn't explicitly forced
            if self.device == "cpu" and torch.cuda.is_available():
                self.device = "cuda"
                
            logger.info(f"[KronosEngine] Downloading/Loading {self.model_name} from HuggingFace to {self.device}...")
            # Kronos-small uses the base tokenizer
            tokenizer_name = "NeoQuasar/Kronos-Tokenizer-base"
            
            self.tokenizer = KronosTokenizer.from_pretrained(tokenizer_name)
            self.model = Kronos.from_pretrained(self.model_name).to(self.device)
            
            # Context size for small/base is 512
            self.predictor = KronosPredictor(self.model, self.tokenizer, max_context=512)
            self.is_loaded = True
            logger.info("[KronosEngine] ✅ Successfully loaded Kronos Neural Network.")
        except Exception as e:
            logger.error(f"[KronosEngine] Failed to load model: {e}")
            self.is_loaded = False
            
    def predict(self, df: pd.DataFrame, pred_len: int = 16, sample_count: int = 1) -> pd.DataFrame:
        """
        Takes raw OHLCV dataframe, returns forecasted future dataframe.
        pred_len=16 means 4 hours into the future (assuming 15m candles).
        """
        if not self.is_loaded:
            logger.warning("[KronosEngine] Model not loaded. Calling load()...")
            self.load()
            if not self.is_loaded:
                return pd.DataFrame()
                
        try:
            # Take up to max_context (512) bars
            lookback_df = df.tail(512).copy().reset_index(drop=True)
            
            x_df = lookback_df[['open', 'high', 'low', 'close', 'volume']].copy()
            x_timestamp = lookback_df['timestamp']
            
            # Predict into the future
            last_ts = pd.to_datetime(x_timestamp.iloc[-1])
            y_timestamp = pd.Series([last_ts + pd.Timedelta(hours=1 * i) for i in range(1, pred_len + 1)])
            
            pred_df = self.predictor.predict(
                df=x_df,
                x_timestamp=x_timestamp,
                y_timestamp=y_timestamp,
                pred_len=pred_len,
                T=1.0,
                top_p=0.9,
                sample_count=sample_count
            )
            
            return pred_df
        except Exception as e:
            logger.error(f"[KronosEngine] Prediction error: {e}")
            return pd.DataFrame()
