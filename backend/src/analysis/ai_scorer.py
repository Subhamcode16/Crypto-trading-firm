import logging
from src.utils.llm_client import LLMClient

logger = logging.getLogger('ai_scorer')

class AIScorer:
    """Score tokens 6-10 using Claude Haiku"""
    
    def __init__(self, api_key: str = None):
        self.llm = LLMClient(api_key=api_key)
        self.model_type = "haiku"
    
    async def score_token(self, token_data: dict, rug_analysis: dict) -> dict:
        """
        Score token 6-10 using Claude Haiku (Async)
        
        Only called after token passes all 6 rug filters
        """
        try:
            system_prompt = "You are a Solana memecoin analyst rated for viral/growth potential analysis."
            prompt = self._build_prompt(token_data, rug_analysis)
            
            messages = [{"role": "user", "content": prompt}]
            
            # Use high-performance client with caching enabled (Async)
            response = await self.llm.create_message(
                model_type=self.model_type,
                system_prompt=system_prompt,
                messages=messages,
                max_tokens=100,
                use_caching=True
            )
            
            response_text = response.get("text", "").strip()
            
            if not response_text:
                return {'score': 6, 'reasoning': 'Empty response', 'model': self.model_type}

            # Parse response
            score = self._extract_score(response_text)
            reasoning = self._extract_reasoning(response_text)
            
            logger.info(f"🧠 AI Score: {score}/10 - {reasoning}")
            
            return {
                'score': score,
                'reasoning': reasoning,
                'model': response.get('metrics', {}).get('model', self.model_type),
                'metrics': response.get('metrics', {})
            }
            
        except Exception as e:
            logger.error(f'❌ AI scoring error: {e}')
            # Return default safe score on error
            return {
                'score': 6,
                'reasoning': f'Error during scoring: {e}',
                'model': self.model_type,
                'metrics': {}
            }
    
    def _build_prompt(self, token_data: dict, rug_analysis: dict) -> str:
        """Build scoring prompt for Claude"""
        
        token = token_data.get('token_name', 'Unknown')
        symbol = token_data.get('token_symbol', 'N/A')
        price = token_data.get('price_usd', 0)
        liquidity = token_data.get('liquidity_usd', 0)
        volume = token_data.get('volume_24h', 0)
        
        return f"""You are a Solana memecoin analyst. A token has passed all security checks. Now rate its viral/growth potential.

Token: {token} ({symbol})
Price: ${price:.10f}
Liquidity: ${liquidity:.2f}
24h Volume: ${volume:.2f}

On-Chain Health (already verified):
- Contract age: Safe
- Liquidity: Locked
- Holders: Well-distributed
- Volume: Organic
- Deployer: Clean history
- Data: Valid

Rate this token's potential for 10x-100x returns (6-10 scale):
- 6: Risky, low narrative appeal
- 7: Decent narrative, some interest
- 8: Strong narrative, growing momentum
- 9: Very strong, clear viral path
- 10: Exceptional, strong momentum

RESPOND WITH ONLY: [NUMBER] - [One sentence reason]
Example: "8 - Strong dog-gaming narrative with community momentum"
"""
    
    def _extract_score(self, response: str) -> int:
        """Extract numeric score from Claude response"""
        try:
            # Look for first digit in response
            for char in response:
                if char.isdigit():
                    score = int(char)
                    if 6 <= score <= 10:
                        return score
            
            # Default to 7 if no valid score found
            logger.warning(f'Could not extract score from: {response}')
            return 7
        except Exception as e:
            logger.error(f'Error extracting score: {e}')
            return 7
    
    def _extract_reasoning(self, response: str) -> str:
        """Extract reasoning from Claude response"""
        try:
            if '-' in response:
                parts = response.split('-', 1)
                if len(parts) > 1:
                    return parts[1].strip()
            
            return response.strip()
        except:
            return response.strip()
