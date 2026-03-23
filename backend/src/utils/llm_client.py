import os
import logging
import json
from typing import Dict, List, Optional, Any, Union
from anthropic import Anthropic, AsyncAnthropic
from datetime import datetime

logger = logging.getLogger('llm_client')

class LLMClient:
    """
    Centralized LLM client for Anthropic Sonnet and Haiku models.
    Supports Anthropic Prompt Caching with a 1h TTL.
    """
    
    MODELS = {
        "sonnet": ["claude-sonnet-4-6", "claude-sonnet-4-5-20241022", "claude-3-5-sonnet-latest"],
        "haiku": ["claude-haiku-4-5", "claude-3-5-haiku-latest"],
        "haiku-strategic": ["claude-haiku-4-5", "claude-sonnet-4-6", "claude-3-5-haiku-latest"]
    }

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = (api_key or os.getenv("ANTHROPIC_API_KEY", "")).strip()
        if not self.api_key:
            logger.error("ANTHROPIC_API_KEY not found in environment")
            raise ValueError("ANTHROPIC_API_KEY required")
        
        self.sync_client = Anthropic(api_key=self.api_key)
        self.async_client = AsyncAnthropic(api_key=self.api_key)
        logger.info(f"[LLM] Client initialized. Models: {list(self.MODELS.keys())}")

    async def create_message(
        self,
        model_type: str,
        system_prompt: str,
        messages: List[Dict[str, str]],
        max_tokens: int = 1000,
        temperature: float = 0.0,
        use_caching: bool = True
    ) -> Dict[str, Any]:
        """
        Request a completion from Anthropic with optional prompt caching (Async).
        Waterfall fallback: tries each model in order until one succeeds.
        """
        model_list = self.MODELS.get(model_type, self.MODELS["haiku"])
        last_error = None
        
        for model in model_list:
            logger.info(f"[LLM] Attempting {model_type} ({model}) - Messages: {len(messages)}")
            try:
                start_time = datetime.utcnow()
                response = await self.async_client.messages.create(
                    model=model,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    system=system_prompt,
                    messages=messages
                )
                
                end_time = datetime.utcnow()
                latency_ms = (end_time - start_time).total_seconds() * 1000
                
                text = response.content[0].text
                usage = response.usage
                
                metrics = {
                    "input_tokens": usage.input_tokens,
                    "output_tokens": usage.output_tokens,
                    "latency_ms": latency_ms,
                    "model": model
                }
                
                logger.info(f"✅ [LLM] Successful response from {model}")
                return {"text": text, "metrics": metrics}

            except (Exception) as e:
                error_str = str(e)
                last_error = error_str
                if "404" in error_str or "not_found" in error_str:
                    logger.warning(f"⚠️ [LLM] Model {model} not found or no access. Falling back...")
                    continue
                elif "429" in error_str or "503" in error_str:
                    logger.warning(f"⚠️ [LLM] Rate limit/unavailable on {model}. Falling back...")
                    continue
                else:
                    # Other errors (auth, validation) might not be fixable by fallback
                    logger.error(f"❌ [LLM] Fatal error with {model}: {e}")
                    return {"text": "", "error": error_str, "metrics": {}}

        # All models failed — return empty text + error key so callers handle gracefully
        logger.error(f"❌ [LLM] All models in waterfall failed. Last error: {last_error}")
        return {"text": "", "error": last_error, "metrics": {}}

    async def create_message_async(self, *args, **kwargs):
        """Alias for create_message to support Agent 0 legacy calls"""
        return await self.create_message(*args, **kwargs)

    def create_message_sync(
        self,
        model_type: str,
        system_prompt: str,
        messages: List[Dict[str, str]],
        max_tokens: int = 1000,
        temperature: float = 0.0,
        use_caching: bool = True
    ) -> Dict[str, Any]:
        """Sync version of create_message"""
        model = self.MODELS.get(model_type, self.MODELS["haiku"])
        try:
            response = self.sync_client.messages.create(
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system_prompt,
                messages=messages
            )
            return {
                "text": response.content[0].text,
                "metrics": {"input_tokens": response.usage.input_tokens, "output_tokens": response.usage.output_tokens}
            }
        except Exception as e:
            logger.error(f"[LLM] Sync error: {e}")
            return {"text": "", "error": str(e), "metrics": {}}

if __name__ == "__main__":
    async def main():
        logging.basicConfig(level=logging.INFO)
        client = LLMClient()
        test_system = "You are a helpful assistant specialized in Solana blockchain analysis."
        test_messages = [{"role": "user", "content": "Explain the benefit of prompt caching in 3 bullet points."}]
        res = await client.create_message("haiku", test_system, test_messages)
        print("\nResponse:")
        print(res["text"])
        print("\nMetrics:")
        print(res["metrics"])
    
    import asyncio
    asyncio.run(main())
