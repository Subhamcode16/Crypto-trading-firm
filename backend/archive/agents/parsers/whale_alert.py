# backend/src/agents/parsers/whale_alert.py

from typing import List, Optional
from src.agents.parsers.base import BaseParser, ParseResult
from src.extractors.contracts import extract_contracts
from src.extractors.wallets import extract_wallets

class WhaleAlertParser(BaseParser):
    """
    Source-specific parser for @whalealert.
    Whale Alert captures major movements of SOL, USDC, and tokens.
    """
    
    def __init__(self):
        super().__init__(label="whale_alert")

    def parse(self, text: str, metadata: Optional[dict] = None) -> ParseResult:
        # Standard extraction
        contracts = extract_contracts(text)
        wallets = extract_wallets(text)
        
        # Priority logic: Extremely high value transfers (e.g. > $1M) or USDC moves
        # For now, simply tag as priority if it's a "Whale" alert
        is_priority = any(kw in text.lower() for kw in ["million", "large", "whale"])
        
        return ParseResult(
            contracts=contracts,
            wallets=wallets,
            source_label=self.label,
            is_priority=is_priority,
            metadata=metadata or {}
        )
