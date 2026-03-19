import os
import logging
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
        "sonnet": "claude-3-5-sonnet-20241022",
        "haiku": "claude-3-haiku-20240307",
        "haiku-strategic": "claude-3-haiku-20240307"
    }

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key:
            logger.error("ANTHROPIC_API_KEY not found in environment")
            raise ValueError("ANTHROPIC_API_KEY required")
        
        self.sync_client = Anthropic(api_key=self.api_key)
        self.async_client = AsyncAnthropic(api_key=self.api_key)
        logger.info("[LLM] Client initialized (Sonnet/Haiku support with Prompt Caching)")

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
        """
        model = self.MODELS.get(model_type, self.MODELS["haiku"])
        
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
            
            logger.debug(f"[LLM] {model_type.upper()} Response received in {latency_ms:.0f}ms. Caching: {use_caching}")
            
            return {
                "text": text,
                "metrics": metrics
            }

        except Exception as e:
            logger.error(f"[LLM] Error in Anthropic request ({model_type}): {e}")
            return {
                "text": "",
                "error": str(e),
                "metrics": {}
            }

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
