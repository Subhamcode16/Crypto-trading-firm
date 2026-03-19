# backend/src/agents/parsers/lookonchain.py

from typing import List, Optional
from src.agents.parsers.base import BaseParser, ParseResult
from src.extractors.contracts import extract_contracts
from src.extractors.wallets import extract_wallets

class LookonchainParser(BaseParser):
    """
    Source-specific parser for @lookonchain.
    Lookonchain often tags 'Smart Money' and 'Whales' specifically.
    """
    
    def __init__(self):
        super().__init__(label="lookonchain")

    def parse(self, text: str, metadata: Optional[dict] = None) -> ParseResult:
        # Standard extraction first
        contracts = extract_contracts(text)
        wallets = extract_wallets(text)
        
        # Priority logic: Lookonchain "Smart Money" or "Whale" tags are high signal
        is_priority = any(kw in text.lower() for kw in ["smart money", "whale", "insider", "fresh wallet"])
        
        return ParseResult(
            contracts=contracts,
            wallets=wallets,
            source_label=self.label,
            is_priority=is_priority,
            metadata=metadata or {}
        )
