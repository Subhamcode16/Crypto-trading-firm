# backend/src/extractors/contracts.py

import re
import logging
from typing import List
try:
    from solders.pubkey import Pubkey
except ImportError:
    # Fallback for environments where solders isn't installed yet
    Pubkey = None

logger = logging.getLogger(__name__)

# Solana base58 address pattern — 32 to 44 chars
SOLANA_PATTERN = re.compile(r'\b[1-9A-HJ-NP-Za-km-z]{32,44}\b')

# System addresses that will always appear in on-chain data — never signals
SYSTEM_ADDRESSES = {
    '11111111111111111111111111111111',   # System Program
    'TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA',  # Token Program
    'ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJe8bv',  # Associated Token Program
    'So11111111111111111111111111111111111111112',   # Wrapped SOL
    'EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v', # USDC
    'Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB', # USDT
}

# Prefixes that indicate context is a TX hash, not a contract
TX_CONTEXT_PREFIXES = [
    'tx:', 'txn:', 'transaction:', 'sig:', 'hash:', 'txhash:',
    'signature:', 'tx =', 'tx=', 'block:', 'slot:'
]

def extract_contracts(text: str) -> List[str]:
    """
    Extract Solana contract addresses from a message.
    Returns deduplicated list of valid base58 pubkeys
    that are not system addresses and not in TX hash context.
    """
    if not text:
        return []

    candidates = SOLANA_PATTERN.findall(text)
    verified   = []
    text_lower = text.lower()

    for addr in candidates:
        # Must be a valid length and not a known system address
        if addr in SYSTEM_ADDRESSES:
            continue
            
        # Must be a valid base58 pubkey
        if not _is_valid_pubkey(addr):
            continue

        # Skip if preceded by TX hash context keywords
        if _in_tx_context(text_lower, addr.lower()):
            continue

        verified.append(addr)

    return list(dict.fromkeys(verified))  # deduplicate, preserve order


def _is_valid_pubkey(addr: str) -> bool:
    if Pubkey:
        try:
            Pubkey.from_string(addr)
            return True
        except Exception:
            return False
    else:
        # Simple length and char set validation if solders is missing
        return 32 <= len(addr) <= 44


def _in_tx_context(text_lower: str, addr_lower: str) -> bool:
    idx = text_lower.find(addr_lower)
    if idx == -1:
        return False
    # Look at the 40 characters before the address
    preceding = text_lower[max(0, idx - 40):idx]
    return any(prefix in preceding for prefix in TX_CONTEXT_PREFIXES)
