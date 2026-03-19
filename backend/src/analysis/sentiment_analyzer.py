#!/usr/bin/env python3
"""
Sentiment Analyzer for Discord Messages
Uses Haiku LLM for accurate sentiment classification
"""

import logging
import json
import asyncio
from typing import Dict, List
from src.utils.llm_client import LLMClient

logger = logging.getLogger('sentiment')

class SentimentAnalyzer:
    """
    Analyzes sentiment of messages using Claude Haiku LLM
    Cost: ~$0.01 per 100 messages (Reduced with Prompt Caching)
    """
    
    def __init__(self, api_key: str = None):
        """
        Initialize sentiment analyzer
        """
        self.llm = LLMClient(api_key=api_key)
        self.model_type = "haiku"
        
        logger.info("[SENTIMENT] Analyzer initialized with LLMClient (Haiku + Caching)")
    
    async def analyze_single(self, text: str) -> Dict:
        """
        Analyze sentiment of a single message
        """
        if not text or len(text) < 3:
            return {
                'sentiment': 'neutral',
                'confidence': 0.0,
                'reasoning': 'Empty or too short'
            }
        
        try:
            # Truncate very long messages
            text = text[:500]
            
            system_prompt = "You are a cryptocurrency sentiment analyst. Analyze Discord messages for Bullish/Bearish sentiment."
            
            prompt = f"""Analyze the sentiment of this Discord message in the context of cryptocurrency trading.

Message: "{text}"

Respond with a JSON object containing:
- sentiment: "positive", "negative", or "neutral"
- confidence: a number from 0 to 1
- reasoning: one sentence explaining your decision

Consider:
- Positive: enthusiasm about token, bullish language, confidence in project
- Negative: FUD, concerns about rug, warnings, criticism
- Neutral: factual statements, questions, technical discussion

Respond ONLY with the JSON object, no other text."""

            messages = [{"role": "user", "content": prompt}]
            
            # Use high-performance client with caching enabled
            response = await self.llm.create_message(
                model_type=self.model_type,
                system_prompt=system_prompt,
                messages=messages,
                max_tokens=200,
                use_caching=True
            )
            
            response_text = response.get("text", "").strip()
            
            if not response_text:
                return {'sentiment': 'neutral', 'confidence': 0.0, 'reasoning': 'Empty response'}

            # Try to extract JSON
            try:
                result = json.loads(response_text)
                result['sentiment'] = result.get('sentiment', 'neutral').lower()
                
                # Validate sentiment value
                if result['sentiment'] not in ['positive', 'negative', 'neutral']:
                    result['sentiment'] = 'neutral'
                
                return result
                
            except json.JSONDecodeError:
                logger.warning(f"[SENTIMENT] Failed to parse response: {response_text}")
                return {
                    'sentiment': 'neutral',
                    'confidence': 0.0,
                    'reasoning': 'Parse error'
                }
            
        except Exception as e:
            logger.error(f"[SENTIMENT] Analysis error: {e}")
            return {
                'sentiment': 'neutral',
                'confidence': 0.0,
                'reasoning': f'Error: {str(e)}'
            }
    
    async def analyze_batch(self, messages: List[str], batch_size: int = 10) -> List[Dict]:
        """
        Analyze sentiment of multiple messages
        Batches requests for efficiency
        
        Args:
            messages: List of message texts
            batch_size: How many to analyze together (max 10)
        
        Returns:
            List of sentiment dicts
        """
        results = []
        
        for i in range(0, len(messages), batch_size):
            batch = messages[i:i+batch_size]
            logger.info(f"[SENTIMENT] Analyzing batch {i//batch_size + 1}: {len(batch)} messages")
            
            # Use asyncio.gather for parallel analysis within a batch
            tasks = [self.analyze_single(msg) for msg in batch]
            batch_results = await asyncio.gather(*tasks)
            results.extend(batch_results)
        
        return results
    
    def aggregate_sentiment(self, analyses: List[Dict]) -> Dict:
        """
        Aggregate sentiment analysis results
        
        Args:
            analyses: List of sentiment analysis results
        
        Returns:
            Aggregated sentiment dict with:
            - positive: percentage of positive messages
            - neutral: percentage of neutral messages
            - negative: percentage of negative messages
            - avg_confidence: average confidence score
            - verdict: overall community sentiment
        """
        if not analyses:
            return {
                'positive': 0.0,
                'neutral': 0.0,
                'negative': 0.0,
                'avg_confidence': 0.0,
                'verdict': 'NEUTRAL'
            }
        
        sentiments = [a.get('sentiment', 'neutral') for a in analyses]
        confidences = [a.get('confidence', 0) for a in analyses]
        
        total = len(sentiments)
        positive = sentiments.count('positive') / total
        negative = sentiments.count('negative') / total
        neutral = sentiments.count('neutral') / total
        avg_confidence = sum(confidences) / total if confidences else 0
        
        # Determine overall verdict
        if positive > 0.6 and avg_confidence > 0.7:
            verdict = 'BULLISH'
        elif negative > 0.5:
            verdict = 'BEARISH'
        elif positive > negative:
            verdict = 'POSITIVE'
        elif negative > positive:
            verdict = 'NEGATIVE'
        else:
            verdict = 'NEUTRAL'
        
        result = {
            'positive': round(positive, 2),
            'neutral': round(neutral, 2),
            'negative': round(negative, 2),
            'avg_confidence': round(avg_confidence, 2),
            'verdict': verdict,
            'message_count': total
        }
        
        logger.info(f"[SENTIMENT] Aggregated: {verdict} (P:{positive:.0%} N:{negative:.0%})")
        return result
    
    async def analyze_discord_messages(self, messages: List[Dict]) -> Dict:
        """
        Analyze a batch of Discord messages
        
        Args:
            messages: List of Discord message dicts with 'content' key
        
        Returns:
            Aggregated sentiment analysis
        """
        # Extract content from message dicts
        texts = [msg.get('content', '') for msg in messages if msg.get('content')]
        
        if not texts:
            logger.warning("[SENTIMENT] No valid messages to analyze")
            return {
                'positive': 0.0,
                'neutral': 1.0,
                'negative': 0.0,
                'avg_confidence': 0.0,
                'verdict': 'NEUTRAL'
            }
        
        logger.info(f"[SENTIMENT] Analyzing {len(texts)} Discord messages")
        
        # Analyze each message
        analyses = await self.analyze_batch(texts, batch_size=10)
        
        # Aggregate results
        aggregated = self.aggregate_sentiment(analyses)
        aggregated['analyzed_messages'] = len(texts)
        
        return aggregated


class SimpleRegexSentiment:
    """
    Fallback sentiment analyzer using regex patterns
    Much faster and cheaper than LLM, but less accurate
    Use when LLM is unavailable or for quick analysis
    """
    
    def __init__(self):
        """Initialize regex-based sentiment analyzer"""
        
        # Positive keywords
        self.positive_words = {
            'moon', 'rocket', 'bullish', 'lambo', 'hodl', 'diamond', 'hands',
            'pump', 'green', 'win', 'profit', 'gains', 'rich', 'wealthy',
            'love', 'awesome', 'great', 'excellent', 'good', 'best', 'strong',
            'surge', 'rally', 'bullrun', 'to the moon', 'mooning', 'trending',
            'hype', 'early', 'opportunity', 'gem', 'potential', 'undervalued'
        }
        
        # Negative keywords
        self.negative_words = {
            'rug', 'pull', 'scam', 'bearish', 'dump', 'crash', 'lose', 'loss',
            'red', 'fail', 'down', 'down', 'bad', 'worse', 'worst', 'terrible',
            'hate', 'avoid', 'warning', 'caution', 'risk', 'doubt', 'suspicious',
            'dead', 'dying', 'collapse', 'fake', 'dishonest', 'untrustworthy'
        }
        
        logger.info("[SENTIMENT] Regex analyzer initialized (fallback)")
    
    def analyze_single(self, text: str) -> Dict:
        """Simple regex-based sentiment analysis"""
        text_lower = text.lower()
        
        positive_count = sum(1 for word in self.positive_words if word in text_lower)
        negative_count = sum(1 for word in self.negative_words if word in text_lower)
        
        if positive_count > negative_count:
            sentiment = 'positive'
            confidence = min(1.0, positive_count / 5)
        elif negative_count > positive_count:
            sentiment = 'negative'
            confidence = min(1.0, negative_count / 5)
        else:
            sentiment = 'neutral'
            confidence = 0.3
        
        return {
            'sentiment': sentiment,
            'confidence': confidence,
            'reasoning': f'{positive_count} positive, {negative_count} negative keywords'
        }
    
    def analyze_batch(self, messages: List[str]) -> List[Dict]:
        """Analyze multiple messages"""
        return [self.analyze_single(msg) for msg in messages]


if __name__ == '__main__':
    # Test the analyzer
    import os
    
    async def main():
        # Try LLM first
        api_key = os.getenv('ANTHROPIC_API_KEY')
        if api_key:
            analyzer = SentimentAnalyzer(api_key)
            
            test_messages = [
                "This token is going to the moon! 🚀🚀🚀",
                "This looks like a rug pull, be careful",
                "Just made my first trade, still learning"
            ]
            
            results = await analyzer.analyze_batch(test_messages)
            aggregated = analyzer.aggregate_sentiment(results)
            
            print(f"Results: {aggregated}")
        else:
            # Use fallback
            print("No API key, using regex fallback")
            analyzer = SimpleRegexSentiment()
            
            result = analyzer.analyze_single("This token is going to moon! Bullish!")
            print(f"Sentiment: {result['sentiment']}")

    asyncio.run(main())
