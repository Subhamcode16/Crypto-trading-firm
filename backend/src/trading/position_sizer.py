import logging

logger = logging.getLogger('position_sizer')

class PositionSizer:
    """Deterministic position sizing based on confidence score"""
    
    # Hard caps - non-negotiable
    STARTING_CAPITAL = 10.0
    POSITION_SIZE_HIGH = 2.0      # Confidence 8-10: $2
    POSITION_SIZE_MID = 1.0       # Confidence 6-7: $1
    CONFIDENCE_MIN = 6             # Below 6: dropped entirely
    
    @staticmethod
    def calculate(confidence_score: int) -> float:
        """
        Deterministic position sizing based on confidence
        
        8-10: $2 (20% of capital)
        6-7: $1 (10% of capital)
        <6: Dropped (no position)
        """
        
        if confidence_score >= 8:
            logger.info(f"💰 Position sizing: Confidence {confidence_score} → ${PositionSizer.POSITION_SIZE_HIGH}")
            return PositionSizer.POSITION_SIZE_HIGH
        
        elif confidence_score >= 6:
            logger.info(f"💰 Position sizing: Confidence {confidence_score} → ${PositionSizer.POSITION_SIZE_MID}")
            return PositionSizer.POSITION_SIZE_MID
        
        else:
            logger.warning(f"🛑 Position sizing: Confidence {confidence_score} < 6 → DROPPED")
            return 0.0
