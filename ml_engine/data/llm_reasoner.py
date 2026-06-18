import os
import logging
from dotenv import load_dotenv
from pathlib import Path
from google import genai
from google.genai.errors import APIError

env_path = Path(__file__).parent.parent.parent / "backend" / "secrets.env"
load_dotenv(env_path)
logger = logging.getLogger(__name__)

class GemmaReasoner:
    def __init__(self):
        self.api_key = os.environ.get("GEMINI_API_KEY")
        self.client = None
        if self.api_key:
            self.client = genai.Client(api_key=self.api_key)
        self.memory = {}  # Format: { "BTC/USDT": ["user prompt 1", "assistant response 1", ...] }
        self.max_history = 6  # Keep last 3 turns

    def _trim_memory(self, symbol: str):
        if symbol in self.memory and len(self.memory[symbol]) > self.max_history:
            self.memory[symbol] = self.memory[symbol][-self.max_history:]

    def evaluate_trade_proposal(self, symbol: str, action: str, confidence: float, price: float, top_features: dict, macro_context: dict, headlines: list) -> dict:
        """
        Calls Gemini with the live context. Returns a dict:
        {
            "decision": "APPROVE" | "VETO" | "ERROR",
            "rationale": "..."
        }
        """
        if not self.client:
            logger.warning("[GemmaReasoner] GEMINI_API_KEY not found. Skipping LLM synthesis.")
            return {"decision": "ERROR", "rationale": "LLM Reasoner Offline: Missing API Key"}

        if symbol not in self.memory:
            self.memory[symbol] = []

        news_text = "\n".join([f"- {h.get('title')} (Score: {h.get('score', 0):.2f})" for h in headlines[:5]])
        macro_text = ", ".join([f"{k}: {v}" for k, v in macro_context.items() if isinstance(v, (int, float))])
        features_text = ", ".join([f"{k}: {v:.4f}" for k, v in top_features.items()])

        prompt = f"""
You are the Senior Risk Manager for an AI Quantitative Crypto Fund.
The algorithmic engine (Junior Analyst) is proposing to execute a {action} on {symbol} at a price of ${price:.2f} with {confidence*100:.1f}% mathematical confidence.

Top Technical Features driving this: {features_text}
Current Macro Environment: {macro_text}
Top Recent News:
{news_text if news_text else 'No significant news recently.'}

You must review this proposal. If the news and macro context severely contradict the algorithmic signal (e.g., massive bearish news during a BUY signal), you must VETO the trade. Otherwise, APPROVE it.

CRITICAL INSTRUCTION: You MUST start your response with exactly [APPROVE] or [VETO] on the very first line. 
Then, on the next line, provide a clear, professional, 2-3 sentence synthesis explaining your decision. Do not use filler introductions.
"""
        
        models = [
            "gemini-2.5-flash",
            "gemini-1.5-pro",
            "gemini-1.5-flash"
        ]

        # Prepare context by concatenating history into the prompt
        context_prompt = ""
        if self.memory[symbol]:
            context_prompt = "Previous Conversation Context:\n" + "\n---\n".join(self.memory[symbol]) + "\n\n=== CURRENT REQUEST ===\n"
            
        full_prompt = context_prompt + prompt

        for model in models:
            try:
                logger.info(f"[GemmaReasoner] Sending request for {symbol} using {model}...")
                response = self.client.models.generate_content(
                    model=model,
                    contents=full_prompt
                )
                
                content = response.text
                if not content:
                    raise ValueError("Empty response from model")

                # Save assistant response to memory
                self.memory[symbol].append(f"USER: {prompt}")
                self.memory[symbol].append(f"ASSISTANT: {content}")
                self._trim_memory(symbol)
                
                decision = "APPROVE"
                if "[VETO]" in content.upper()[:20]:
                    decision = "VETO"
                    
                clean_rationale = content.replace("[APPROVE]", "").replace("[VETO]", "").replace("[approve]", "").replace("[veto]", "").strip()

                return {
                    "decision": decision,
                    "rationale": clean_rationale
                }

            except APIError as e:
                status_code = getattr(e, 'code', getattr(e, 'status_code', 500))
                # string matching if code is not properly exposed
                error_str = str(e)
                if '429' in error_str or '503' in error_str or '404' in error_str:
                    logger.warning(f"[GemmaReasoner] Model {model} failed with Rate Limit/Not Found. Falling back to next model. Error: {e}")
                    continue
                else:
                    logger.error(f"[GemmaReasoner] Model {model} failed with non-fallback error: {e}")
                    break
            except Exception as e:
                logger.error(f"[GemmaReasoner] Error calling Gemini with {model}: {e}")
                continue

        return {"decision": "ERROR", "rationale": "All LLM models in the waterfall failed or encountered errors."}

if __name__ == "__main__":
    import dotenv
    env_path = Path(__file__).parent.parent.parent / "backend" / "secrets.env"
    dotenv.load_dotenv(env_path)
    reasoner = GemmaReasoner()
    res = reasoner.evaluate_trade_proposal("BTC/USDT", "BUY", 0.85, 65000, {"vix": 0.05, "dxy": 0.04}, {"vix": 14.5, "dxy": 104.2}, [{"title": "Bitcoin surges!", "score": 0.5}])
    print("Testing Reasoner:", res)
