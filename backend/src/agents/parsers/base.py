# backend/src/agents/parsers/base.py

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional

@dataclass
class ParseResult:
    contracts: List[str] = field(default_factory=list)
    wallets: List[str] = field(default_factory=list)
    source_label: str = "unknown"
    is_priority: bool = False
    metadata: dict = field(default_factory=dict)

class BaseParser(ABC):
    """Abstract base class for source-specific Telegram message parsers."""
    
    def __init__(self, label: str):
        self.label = label

    @abstractmethod
    def parse(self, text: str, metadata: Optional[dict] = None) -> ParseResult:
        """Parse raw Telegram message text and return structured signals."""
        pass
