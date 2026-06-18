# backend/src/agents/parsers/generic.py

from typing import List, Optional
from src.agents.parsers.base import BaseParser, ParseResult
from src.extractors.contracts import extract_contracts
from src.extractors.wallets import extract_wallets

class GenericParser(BaseParser):
    """Generic extractor for all Telegram channels."""
    
    def __init__(self):
        super().__init__(label="generic")

    def parse(self, text: str, metadata: Optional[dict] = None) -> ParseResult:
        contracts = extract_contracts(text)
        wallets = extract_wallets(text)
        
        return ParseResult(
            contracts=contracts,
            wallets=wallets,
            source_label=self.label,
            metadata=metadata or {}
        )
