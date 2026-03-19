# backend/src/extractors/wallets.py

import re
import logging
from typing import List
from src.extractors.contracts import SOLANA_PATTERN, _is_valid_pubkey, SYSTEM_ADDRESSES

logger = logging.getLogger(__name__)

# Keywords that indicate a Solana address in context is a wallet, not a contract
WALLET_CONTEXT_KEYWORDS = [
    'wallet', 'holder', 'whale', 'smart money', 'insider',
    'deployer', 'dev wallet', 'early buyer', 'accumulating',
    'bought', 'sold', 'transferred', 'moving', 'from:', 'to:',
    'address', 'account', 'sniper', 'bot wallet', 'portfolio'
]

PROXIMITY_WINDOW = 150  # characters on each side of address to check for keywords

def extract_wallets(text: str) -> List[str]:
    """
    Extract Solana wallet addresses from a message.
    Only extracts addresses when wallet-context keywords appear nearby.
    Returns deduplicated list.
    """
    if not text:
        return []

    text_lower = text.lower()

    # Quick check — if no wallet keywords anywhere in message, skip
    if not any(kw in text_lower for kw in WALLET_CONTEXT_KEYWORDS):
        return []

    candidates = SOLANA_PATTERN.findall(text)
    wallets    = []

    for addr in candidates:
        if addr in SYSTEM_ADDRESSES:
            continue
        if not _is_valid_pubkey(addr):
            continue
        if _has_nearby_keyword(text_lower, addr.lower()):
            wallets.append(addr)

    return list(dict.fromkeys(wallets))


def _has_nearby_keyword(text_lower: str, addr_lower: str) -> bool:
    idx = text_lower.find(addr_lower)
    if idx == -1:
        return False
    # Check a window around the address
    start      = max(0, idx - PROXIMITY_WINDOW)
    end        = min(len(text_lower), idx + len(addr_lower) + PROXIMITY_WINDOW)
    surrounding = text_lower[start:end]
    
    return any(kw in surrounding for kw in WALLET_CONTEXT_KEYWORDS)
