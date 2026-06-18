#!/usr/bin/env python3
"""
LEARNING LOOP: Continuous Trade Performance Analysis

Role: The firm's Memory and Adaptation layer.
Analyzes every closed trade to find 'Learned Traits'.
"""

import json
import logging
from datetime import datetime
from typing import Dict, Optional
from src.utils.llm_client import LLMClient

logger = logging.getLogger(__name__)

class LearningLoop:
    def __init__(self, db_client):
        self.db = db_client
        self.llm = LLMClient()
        self.model_type = "sonnet"
        
        logger.info("[LEARNING_LOOP] Feedback loop initialized.")

    async def analyze_trade_outcome(self, trade_data: Dict) -> Dict:
        """
        Analyze a single closed trade to extract lessons.
        """
        try:
            token = trade_data.get("token", "UNKNOWN")
            pnl = trade_data.get("pnl_usd", 0.0)
            outcome = "WIN" if pnl > 0 else "LOSS"
            
            # 1. Prepare Intelligence Context
            # We want to know why we entered and how it went
            context = {
                "token": token,
                "entry_price": trade_data.get("entry_price"),
                "exit_price": trade_data.get("current_price"),
                "pnl_usd": pnl,
                "exit_reason": trade_data.get("exit_reason", "unknown"),
                "agent_scores": trade_data.get("agent_analysis", {}),
                "refined_by": trade_data.get("refined_by"),
                "refinement_reason": trade_data.get("refinement_reason")
            }

            # 2. Consult Sonnet for Lessons
            system_prompt = """You are a machine learning feedback analyzer for a crypto trading bot.
Your goal is to identify WHY a trade succeeded or failed and store 'Lessons' that can be used to tune the system."""

            prompt = f"""ANALYZE TRADE OUTCOME.

TRADE DATA:
{json.dumps(context, indent=2)}

TASK:
- Identify if the 'refined' parameters (TP/SL) were too tight or too loose.
- Determine if an agent's score was misleading (e.g. Agent 4 hyped a rug).
- Extract a 'Learned Trait' as a short string (e.g. "OVERHYPE_ON_TWITTER", "PERFECT_SNIPE_A3").

RESPOND WITH JSON ONLY:
{{
  "outcome_analysis": "string",
  "learned_trait": "string",
  "confidence_in_lesson": float,
  "suggested_weight_adjustment": {{ "agent": "string", "delta": float }},
  "should_blacklist_token": bool
}}"""

            messages = [{"role": "user", "content": prompt}]
            
            response = await self.llm.create_message_async(
                model_type=self.model_type,
                system_prompt=system_prompt,
                messages=messages,
                max_tokens=300,
                temperature=0.1
            )
            
            lesson = json.loads(response.get("text", "{}"))
            
            # 3. Store Lesson in DB (Audit Log for Commander)
            await self._store_lesson(token, lesson)
            
            logger.info(f"[LEARNING_LOOP] 🧠 LESSON LEARNED for {token}: {lesson.get('learned_trait')}")
            return lesson

        except Exception as e:
            logger.error(f"[LEARNING_LOOP] Analysis failed: {e}")
            return {"error": str(e)}

    async def _store_lesson(self, token: str, lesson: Dict):
        """Append lesson to system_events as a 'LEARNING' event."""
        event = {
            "event_type": "LEARNING",
            "severity": "INFO",
            "description": f"Trade analysis for {token}: {lesson.get('learned_trait')}",
            "diagnostic_data": lesson,
            "resolved": True
        }
        if self.db:
            await self.db.log_event(event)
