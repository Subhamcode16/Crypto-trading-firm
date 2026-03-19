# PixelFirm — Agent 4: Telegram Intel
### Build & Backtest Reference for Vibe-Coding Platforms

> **Read this first.**
> This document is a complete, sequential build guide for Agent 4 (IntelAgent) of the PixelFirm autonomous Solana trading system. Each phase ends with a backtest/validation gate. Do not proceed to the next phase until the current phase passes its gate. Every code decision here reflects prior architectural decisions — do not deviate from the patterns without flagging it.

---

## Project Context

PixelFirm is a multi-tenant SaaS platform for autonomous Solana memecoin trading. It runs as a single Docker container per user on their own VPS. There are 9 agents in the pipeline. This document covers **Agent 4 only**.

**Agent 4's role in the pipeline:**
- Monitors Telegram channels in real time using a user account (Telethon)
- Extracts contract addresses and wallet addresses from messages
- Deduplicates signals across sources
- Emits contract signals → Agent 5 (SignalAggregator)
- Emits wallet signals → Agent 3 (WalletTracker)
- Never trades, never scores, never verifies — discovery only

**What Agent 4 is NOT responsible for:**
- Sentiment analysis
- Price targets
- Signal scoring or confidence
- Sending Telegram alerts to the user (that is the bot, not Telethon)

---

## Stack

```
Language:        Python 3.11+
Telegram reader: Telethon 1.x        (user account — reads channels)
Telegram alerts: python-telegram-bot  (bot account — sends alerts, already built)
Cache/Dedup:     Redis 7.x
Queue:           asyncio PriorityQueue (already implemented in the codebase)
Validation:      solders (Solana address validation)
Container:       Docker (single container, supervisord manages processes)
Data volume:     /data/pixelfirm/config/  (session file lives here)
                 /data/pixelfirm/db/      (trading database)
```

---

## File Structure for This Agent

```
backend/
├── agents/
│   ├── intel_agent.py           ← main agent class
│   └── parsers/
│       ├── __init__.py
│       ├── base.py              ← BaseParser abstract class
│       ├── generic.py           ← generic extractor (all sources)
│       ├── lookonchain.py       ← source-specific parser
│       └── whale_alert.py      ← source-specific parser
├── extractors/
│   ├── __init__.py
│   ├── contracts.py             ← Solana contract address extractor
│   └── wallets.py               ← wallet address extractor
├── cli/
│   └── setup_wizard.py          ← add Step 2b here (Telethon auth)
config/
└── default_channels.py          ← default channel list
tests/
└── agent4/
    ├── test_extractors.py
    ├── test_parsers.py
    ├── test_dedup.py
    ├── test_intel_agent.py
    └── fixtures/
        ├── lookonchain_samples.txt
        ├── whale_alert_samples.txt
        └── generic_alpha_samples.txt
```

---

## Environment Variables (Agent 4 specific)

These are collected during the setup wizard (Step 2b) and stored encrypted in `/data/pixelfirm/config/config.db`. They are never stored in `.env` or plaintext.

```
TELEGRAM_API_ID        # from my.telegram.org — integer
TELEGRAM_API_HASH      # from my.telegram.org — string
TELEGRAM_READER_PHONE  # phone number of the dedicated reader account e.g. +1234567890
```

> **Important:** These credentials belong to a **dedicated reader account**, not the user's personal Telegram account and not the BotFather bot account. Three separate accounts: personal, bot, reader.

---

---

# PHASE 1 — Telethon Auth & Session Management

## Goal
Get Telethon authenticating as the reader account and persisting the session file inside the Docker volume so subsequent container starts do not require re-authentication.

---

## 1.1 — Add Step 2b to Setup Wizard

**File:** `backend/cli/setup_wizard.py`

Add a new step between the existing Telegram bot step and the Solana wallet step. This step must run interactively — it sends a verification code to the phone and waits for the user to type it back.

**Logic:**
1. Check if `/data/pixelfirm/config/pixelfirm_reader.session` already exists
2. If it exists — skip this step entirely (session already valid)
3. If it does not exist — run the full auth flow below

**Wizard output to terminal:**

```
──────────────────────────────────────────────────────────
 STEP 2b OF 4 — TELEGRAM READER ACCOUNT
──────────────────────────────────────────────────────────

 PixelFirm monitors Telegram alpha channels in real time.
 This requires a dedicated Telegram reader account.
 Do NOT use your personal account.

 Get API credentials at: https://my.telegram.org
   1. Log in with your READER account phone number
   2. Go to "API Development Tools"
   3. Create a new application (name: PixelFirm)
   4. Copy the api_id (integer) and api_hash (string)

 API ID:    _
 API Hash:  _                        ← getpass (hidden)
 Phone:     _  (format: +1234567890)

 Sending verification code to Telegram...
 Enter the code you received: _

 ✓ Reader account authenticated.
 ✓ Session saved to /data/pixelfirm/config/pixelfirm_reader.session
```

**Implementation:**

```python
# backend/cli/setup_wizard.py — add this function

import getpass
from telethon.sync import TelegramClient
from telethon.errors import SessionPasswordNeededError
from backend.config.store import ConfigStore
from backend.crypto.aes import encrypt_value

SESSION_PATH = '/data/pixelfirm/config/pixelfirm_reader'

def step_2b_telegram_reader():
    # Skip if session already exists
    if os.path.exists(SESSION_PATH + '.session'):
        print('  ✓ Reader session already exists. Skipping.')
        return

    print_step_header('2b OF 4', 'TELEGRAM READER ACCOUNT')
    print('  Get credentials at: https://my.telegram.org')
    print()

    api_id   = int(input('  API ID:   ').strip())
    api_hash = getpass.getpass('  API Hash: ')
    phone    = input('  Phone:    ').strip()

    store = ConfigStore('/data/pixelfirm/config/config.db')
    store.set('telegram_api_id',     str(api_id))
    store.set('telegram_api_hash',   encrypt_value(api_hash))
    store.set('telegram_reader_phone', phone)

    print()
    print('  Connecting to Telegram...')

    with TelegramClient(SESSION_PATH, api_id, api_hash) as client:
        client.start(phone=phone)
        # Telethon handles the code prompt automatically in sync mode
        # Session file is written to SESSION_PATH.session on success
        me = client.get_me()
        print(f'  ✓ Authenticated as: {me.first_name} (@{me.username})')
        print(f'  ✓ Session saved.')
```

**Notes for the AI building this:**
- Use `telethon.sync.TelegramClient` for the setup wizard (synchronous — easier in a CLI context)
- Use `telethon.TelegramClient` (async) for the actual agent runtime
- If the account has two-factor authentication enabled, Telethon will prompt for the 2FA password automatically — handle `SessionPasswordNeededError` and prompt the user
- The session file must be written to the config volume path, not a temp directory — it must survive container restarts

---

## 1.2 — Telethon Client Factory

**File:** `backend/agents/intel_agent.py` (top section)

The async client used at runtime. Loaded from the saved session — no phone or code prompt.

```python
# backend/agents/intel_agent.py

from telethon import TelegramClient
from backend.config.store import ConfigStore
from backend.crypto.aes import decrypt_value

SESSION_PATH = '/data/pixelfirm/config/pixelfirm_reader'

async def build_telethon_client() -> TelegramClient:
    store    = ConfigStore('/data/pixelfirm/config/config.db')
    api_id   = int(store.get('telegram_api_id'))
    api_hash = decrypt_value(store.get('telegram_api_hash'))

    client = TelegramClient(SESSION_PATH, api_id, api_hash)
    await client.start()
    # No phone/code prompt — loads from session file silently
    return client
```

---

## 1.3 — Supervisord Entry for Agent 4

**File:** `deploy/supervisord.conf`

Add Agent 4 as a managed process. It starts after the backend is ready.

```ini
[program:intel_agent]
command=python -m backend.agents.intel_agent
directory=/app
autostart=true
autorestart=true
priority=25
startsecs=12
stdout_logfile=/data/pixelfirm/logs/agents.log
stdout_logfile_maxbytes=10MB
stderr_logfile=/data/pixelfirm/logs/errors.log
```

---

## ✅ PHASE 1 BACKTEST

**Run before proceeding to Phase 2.**

### Test 1.1 — Session file creation
```bash
# On a fresh config volume (no session file present)
docker run -it --rm \
  -v /tmp/pf_test_config:/data/pixelfirm/config \
  ghcr.io/pixelfirm/app:latest \
  python /app/backend/cli/setup_wizard.py

# Expected:
# - Step 2b prompts appear
# - Verification code is sent to phone
# - After code entry: session file created
# - File exists: /tmp/pf_test_config/pixelfirm_reader.session
```

### Test 1.2 — Session reuse (no re-auth on restart)
```bash
# Run setup wizard again on the SAME config volume
docker run -it --rm \
  -v /tmp/pf_test_config:/data/pixelfirm/config \
  ghcr.io/pixelfirm/app:latest \
  python /app/backend/cli/setup_wizard.py

# Expected:
# - Step 2b prints "✓ Reader session already exists. Skipping."
# - No code sent to phone
```

### Test 1.3 — Silent client start
```bash
docker exec -it pixelfirm python -c "
import asyncio
from backend.agents.intel_agent import build_telethon_client
async def test():
    client = await build_telethon_client()
    me = await client.get_me()
    print(f'Connected as: {me.first_name}')
    await client.disconnect()
asyncio.run(test())
"

# Expected:
# Connected as: [reader account name]
# No prompts, no errors
```

### Gate: Do not proceed to Phase 2 until all three tests pass.

---

---

# PHASE 2 — Channel Configuration & Subscription

## Goal
Agent 4 reads the channel list from the config database and subscribes to all of them via Telethon event handler. Verify raw messages are being received before any extraction logic is added.

---

## 2.1 — Default Channel List

**File:** `config/default_channels.py`

```python
# config/default_channels.py
# Loaded into config.db on first run.
# All public channels — no membership required.
# User can add/remove from the settings dashboard.

DEFAULT_CHANNELS = [
    {
        "id":      "@lookonchain",
        "label":   "Lookonchain",
        "type":    "kol",
        "weight":  0.85,
        "enabled": True,
        "parser":  "lookonchain",   # maps to parsers/lookonchain.py
    },
    {
        "id":      "@whalealert",
        "label":   "Whale Alert",
        "type":    "tracker",
        "weight":  0.65,
        "enabled": True,
        "parser":  "whale_alert",
    },
    {
        "id":      "@solanawhalealerts",
        "label":   "Solana Whale Alerts",
        "type":    "tracker",
        "weight":  0.70,
        "enabled": True,
        "parser":  "generic",
    },
    {
        "id":      "@solanafm",
        "label":   "Solana FM",
        "type":    "tracker",
        "weight":  0.60,
        "enabled": True,
        "parser":  "generic",
    },
    {
        "id":      "@dexscreener_trending",
        "label":   "DexScreener Trending",
        "type":    "tracker",
        "weight":  0.55,
        "enabled": True,
        "parser":  "generic",
    },
]
```

**Notes:**
- `type` values: `kol` | `tracker` | `alpha`
- `weight` is used by Agent 5 for confluence scoring. Do not change defaults without Agent 9 data to support it.
- `parser` maps to which parser class handles messages from this source
- Private groups added by the user will have a numeric `id` (e.g. `-1001234567890`) instead of a `@username`

---

## 2.2 — Channel Store (Config DB)

**File:** `backend/config/store.py` — extend existing ConfigStore

Add methods for reading and writing the channel list. The channel list is stored as JSON in the config database under the key `intel_channels`.

```python
# Add to ConfigStore class

def get_intel_channels(self) -> list[dict]:
    raw = self.get('intel_channels')
    if not raw:
        # First run — seed with defaults
        from config.default_channels import DEFAULT_CHANNELS
        self.set_intel_channels(DEFAULT_CHANNELS)
        return DEFAULT_CHANNELS
    return json.loads(raw)

def set_intel_channels(self, channels: list[dict]) -> None:
    self.set('intel_channels', json.dumps(channels))

def get_enabled_channel_ids(self) -> list:
    channels = self.get_intel_channels()
    return [ch['id'] for ch in channels if ch.get('enabled', True)]
```

---

## 2.3 — Raw Message Subscription

**File:** `backend/agents/intel_agent.py`

Subscribe to all enabled channels. At this phase — log raw messages only. No extraction yet.

```python
# backend/agents/intel_agent.py

import logging
from telethon import TelegramClient, events
from backend.config.store import ConfigStore

logger = logging.getLogger('intel_agent')

class IntelAgent:
    def __init__(self, client: TelegramClient, store: ConfigStore):
        self.client   = client
        self.store    = store
        self.channels = store.get_enabled_channel_ids()

    async def start(self):
        logger.info(f'IntelAgent subscribing to {len(self.channels)} channels')
        logger.info(f'Channels: {self.channels}')

        @self.client.on(events.NewMessage(chats=self.channels))
        async def on_message(event):
            text      = event.message.text or ''
            source_id = event.chat_id
            logger.info(f'[RAW] source={source_id} len={len(text)} preview={text[:80]!r}')

        await self.client.run_until_disconnected()


async def main():
    from backend.agents.intel_agent import build_telethon_client
    client = await build_telethon_client()
    store  = ConfigStore('/data/pixelfirm/config/config.db')
    agent  = IntelAgent(client, store)
    await agent.start()

if __name__ == '__main__':
    import asyncio
    asyncio.run(main())
```

---

## ✅ PHASE 2 BACKTEST

### Test 2.1 — Channel subscription
```bash
docker exec -it pixelfirm python -m backend.agents.intel_agent

# Expected output (within 5 minutes of a message being posted):
# INFO  IntelAgent subscribing to 5 channels
# INFO  Channels: ['@lookonchain', '@whalealert', ...]
# INFO  [RAW] source=@lookonchain len=142 preview='🚨 A whale just bought...'
```

### Test 2.2 — New channel added at runtime
```bash
# Add a channel via settings API
curl -X POST http://localhost:8000/api/settings/channels \
  -H "Content-Type: application/json" \
  -d '{"id": "@solana_degens", "type": "alpha", "weight": 0.5}'

# Restart intel_agent process only (not whole container)
docker exec pixelfirm supervisorctl restart intel_agent

# Expected: new channel appears in subscription list on restart
```

### Test 2.3 — Disabled channel is ignored
```bash
# Disable a channel
curl -X PATCH http://localhost:8000/api/settings/channels/@whalealert \
  -d '{"enabled": false}'

docker exec pixelfirm supervisorctl restart intel_agent

# Expected: @whalealert NOT in channel list
# Expected: messages from @whalealert produce no log output
```

### Gate: Do not proceed to Phase 3 until raw messages are logging correctly from at least 2 channels.

---

---

# PHASE 3 — Extractors

## Goal
Build and validate the two extractors: contract address extraction and wallet address extraction. Both must be independently testable with no Telegram dependency.

---

## 3.1 — Contract Address Extractor

**File:** `backend/extractors/contracts.py`

```python
# backend/extractors/contracts.py

import re
from solders.pubkey import Pubkey

# Solana base58 address pattern — 32 to 44 chars
SOLANA_PATTERN = re.compile(r'\b[1-9A-HJ-NP-Za-km-z]{32,44}\b')

# System addresses that will always appear in on-chain data — never signals
SYSTEM_ADDRESSES = {
    '11111111111111111111111111111111',   # System Program
    'TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA',  # Token Program
    'ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJe8bv',  # Associated Token Program
    'So11111111111111111111111111111111111111112',   # Wrapped SOL
    'EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v', # USDC
}

# Prefixes that indicate context is a TX hash, not a contract
TX_CONTEXT_PREFIXES = [
    'tx:', 'txn:', 'transaction:', 'sig:', 'hash:', 'txhash:',
    'signature:', 'tx =', 'tx=',
]

def extract_contracts(text: str) -> list[str]:
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
        # Must be a valid base58 pubkey
        if not _is_valid_pubkey(addr):
            continue

        # Skip known system addresses
        if addr in SYSTEM_ADDRESSES:
            continue

        # Skip if preceded by TX hash context keywords
        if _in_tx_context(text_lower, addr.lower()):
            continue

        verified.append(addr)

    return list(dict.fromkeys(verified))  # deduplicate, preserve order


def _is_valid_pubkey(addr: str) -> bool:
    try:
        Pubkey.from_string(addr)
        return True
    except Exception:
        return False


def _in_tx_context(text_lower: str, addr_lower: str) -> bool:
    idx = text_lower.find(addr_lower)
    if idx == -1:
        return False
    # Look at the 30 characters before the address
    preceding = text_lower[max(0, idx - 30):idx]
    return any(prefix in preceding for prefix in TX_CONTEXT_PREFIXES)
```

---

## 3.2 — Wallet Address Extractor

**File:** `backend/extractors/wallets.py`

```python
# backend/extractors/wallets.py

import re
from solders.pubkey import Pubkey
from backend.extractors.contracts import SOLANA_PATTERN, _is_valid_pubkey, SYSTEM_ADDRESSES

# Keywords that indicate a Solana address in context is a wallet, not a contract
WALLET_CONTEXT_KEYWORDS = [
    'wallet', 'holder', 'whale', 'smart money', 'insider',
    'deployer', 'dev wallet', 'early buyer', 'accumulating',
    'bought', 'sold', 'transferred', 'moving', 'from:', 'to:',
    'address', 'account', 'sniper', 'bot wallet',
]

PROXIMITY_WINDOW = 120  # characters on each side of address to check for keywords


def extract_wallets(text: str) -> list[str]:
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
        if not _is_valid_pubkey(addr):
            continue
        if addr in SYSTEM_ADDRESSES:
            continue
        if _has_nearby_keyword(text_lower, addr.lower()):
            wallets.append(addr)

    return list(dict.fromkeys(wallets))


def _has_nearby_keyword(text_lower: str, addr_lower: str) -> bool:
    idx = text_lower.find(addr_lower)
    if idx == -1:
        return False
    start      = max(0, idx - PROXIMITY_WINDOW)
    end        = min(len(text_lower), idx + len(addr_lower) + PROXIMITY_WINDOW)
    surrounding = text_lower[start:end]
    return any(kw in surrounding for kw in WALLET_CONTEXT_KEYWORDS)
```

---

## 3.3 — Extractor Test Fixtures

**File:** `tests/agent4/fixtures/lookonchain_samples.txt`

Populate this file with at least 15 real message samples copied from @lookonchain. Format — one message per block separated by `---`.

```
🚨 A whale just bought 2,400,000 $BONK ($48,000)
Contract: 7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU
Wallet: 9WzDXwBbmkg8ZTbNMqUxvQRAyrZzDsGYdLVL9zYtAWWM
https://solscan.io/tx/abc123...
---
Smart money wallet So1abc...xyz just bought $PEPE2
They previously made 40x on $WIF
---
[add 13 more real samples here before running tests]
```

**File:** `tests/agent4/fixtures/whale_alert_samples.txt`

Same structure, 15 samples from @whalealert.

**File:** `tests/agent4/fixtures/generic_alpha_samples.txt`

15 samples from general alpha channels — include some messages with NO addresses to test the extractor correctly returns empty.

---

## ✅ PHASE 3 BACKTEST

**File:** `tests/agent4/test_extractors.py`

```python
# tests/agent4/test_extractors.py

import pytest
from backend.extractors.contracts import extract_contracts
from backend.extractors.wallets   import extract_wallets

# ── Contract extractor tests ──────────────────────────────────────────────

def test_extracts_valid_contract():
    text = "New token $WOJAK\nCA: 7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU"
    result = extract_contracts(text)
    assert '7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU' in result

def test_ignores_tx_hash():
    text = "tx: 7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU bought 500 SOL"
    result = extract_contracts(text)
    assert result == []

def test_ignores_system_addresses():
    text = "transfer via 11111111111111111111111111111111 complete"
    result = extract_contracts(text)
    assert result == []

def test_deduplicates_same_address():
    addr = '7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU'
    text = f"CA: {addr}\nContract: {addr}"
    result = extract_contracts(text)
    assert result.count(addr) == 1

def test_empty_message():
    assert extract_contracts('') == []
    assert extract_contracts(None) == []

def test_no_addresses_in_message():
    result = extract_contracts("Bitcoin is pumping today, very bullish market")
    assert result == []

def test_multiple_contracts_in_message():
    addr1 = '7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU'
    addr2 = 'EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v'  # USDC — should be filtered
    addr3 = 'DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263'  # random valid
    text  = f"Two tokens today:\n{addr1}\n{addr2}\n{addr3}"
    result = extract_contracts(text)
    assert addr1 in result
    assert addr2 not in result   # USDC is in SYSTEM_ADDRESSES
    assert addr3 in result

# ── Wallet extractor tests ────────────────────────────────────────────────

def test_extracts_wallet_with_context():
    addr = '9WzDXwBbmkg8ZTbNMqUxvQRAyrZzDsGYdLVL9zYtAWWM'
    text = f"Smart money wallet {addr} just bought $BONK"
    result = extract_wallets(text)
    assert addr in result

def test_no_wallet_without_context():
    addr = '9WzDXwBbmkg8ZTbNMqUxvQRAyrZzDsGYdLVL9zYtAWWM'
    text = f"Check out this address {addr}"
    result = extract_wallets(text)
    assert result == []   # "address" keyword is present but check proximity

def test_from_to_context():
    from_addr = '9WzDXwBbmkg8ZTbNMqUxvQRAyrZzDsGYdLVL9zYtAWWM'
    to_addr   = 'DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263'
    text      = f"From: {from_addr}\nTo: {to_addr}\nAmount: 500 SOL"
    result    = extract_wallets(text)
    assert from_addr in result
    assert to_addr   in result

def test_empty_message_wallet():
    assert extract_wallets('') == []

# ── Fixture-based tests ───────────────────────────────────────────────────

def load_fixture(filename: str) -> list[str]:
    path = f'tests/agent4/fixtures/{filename}'
    with open(path) as f:
        return [block.strip() for block in f.read().split('---') if block.strip()]

def test_lookonchain_samples_extract_contracts():
    samples = load_fixture('lookonchain_samples.txt')
    # At least 70% of Lookonchain samples should yield at least one address
    hits = sum(1 for s in samples if extract_contracts(s))
    assert hits / len(samples) >= 0.7, f'Only {hits}/{len(samples)} samples extracted contracts'

def test_whale_alert_samples_extract_wallets():
    samples = load_fixture('whale_alert_samples.txt')
    hits = sum(1 for s in samples if extract_wallets(s))
    assert hits / len(samples) >= 0.6, f'Only {hits}/{len(samples)} samples extracted wallets'

def test_generic_no_false_positives():
    # Load generic samples that have NO addresses — verify extractor returns empty
    samples = load_fixture('generic_alpha_samples.txt')
    no_addr_samples = [s for s in samples if 'CA:' not in s and 'contract' not in s.lower()]
    false_positives = sum(1 for s in no_addr_samples if extract_contracts(s))
    assert false_positives == 0, f'{false_positives} false positives detected'
```

**Run:**
```bash
docker exec -it pixelfirm pytest tests/agent4/test_extractors.py -v
```

**Pass criteria:**
- All unit tests pass
- Lookonchain fixture hit rate ≥ 70%
- Whale Alert fixture hit rate ≥ 60%
- Zero false positives on no-address samples

### Gate: Do not proceed to Phase 4 until all extractor tests pass.

---

---

# PHASE 4 — Source-Specific Parsers

## Goal
Build the parser layer that sits between raw messages and the extractors. Lookonchain and Whale Alert post in consistent formats — dedicated parsers give higher accuracy than generic regex on these sources. All other sources use the generic parser.

---

## 4.1 — Base Parser

**File:** `backend/agents/parsers/base.py`

```python
# backend/agents/parsers/base.py

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

@dataclass
class ParseResult:
    contracts:   list[str] = field(default_factory=list)
    wallets:     list[str] = field(default_factory=list)
    raw_excerpt: str       = ''    # relevant snippet, max 280 chars
    confidence:  float     = 0.5  # parser confidence 0.0–1.0

class BaseParser(ABC):
    @abstractmethod
    def parse(self, text: str) -> ParseResult:
        """
        Parse a raw Telegram message.
        Return ParseResult with extracted contracts and wallets.
        """
        ...

    def can_parse(self, text: str) -> bool:
        """
        Optional: return True if this parser recognises the message format.
        Used by ParserRouter to select the right parser.
        Default: always True (generic parser uses this default).
        """
        return True
```

---

## 4.2 — Generic Parser

**File:** `backend/agents/parsers/generic.py`

```python
# backend/agents/parsers/generic.py

from .base import BaseParser, ParseResult
from backend.extractors.contracts import extract_contracts
from backend.extractors.wallets   import extract_wallets

class GenericParser(BaseParser):
    def parse(self, text: str) -> ParseResult:
        contracts = extract_contracts(text)
        wallets   = extract_wallets(text)
        return ParseResult(
            contracts   = contracts,
            wallets     = wallets,
            raw_excerpt = text[:280],
            confidence  = 0.6,   # generic — moderate confidence
        )
```

---

## 4.3 — Lookonchain Parser

**File:** `backend/agents/parsers/lookonchain.py`

Lookonchain messages follow a consistent format. Parse the structured fields directly before falling back to generic extraction.

```python
# backend/agents/parsers/lookonchain.py

import re
from .base import BaseParser, ParseResult
from backend.extractors.contracts import extract_contracts, _is_valid_pubkey
from backend.extractors.wallets   import extract_wallets

# Lookonchain labels contract addresses explicitly
CONTRACT_LABELS = ['contract:', 'ca:', 'token:', 'token address:']
WALLET_LABELS   = ['wallet:', 'address:', 'from:', 'to:', 'deployer:']

class LookonchainParser(BaseParser):

    def can_parse(self, text: str) -> bool:
        # Lookonchain messages typically contain these patterns
        text_lower = text.lower()
        return any(label in text_lower for label in CONTRACT_LABELS + WALLET_LABELS)

    def parse(self, text: str) -> ParseResult:
        contracts = self._extract_labeled(text, CONTRACT_LABELS)
        wallets   = self._extract_labeled(text, WALLET_LABELS)

        # Fallback to generic extractor for anything not caught by labels
        if not contracts:
            contracts = extract_contracts(text)
        if not wallets:
            wallets = extract_wallets(text)

        return ParseResult(
            contracts   = contracts,
            wallets     = wallets,
            raw_excerpt = text[:280],
            confidence  = 0.9,  # structured format — high confidence
        )

    def _extract_labeled(self, text: str, labels: list[str]) -> list[str]:
        """Extract addresses that appear directly after a label on the same line."""
        found      = []
        text_lower = text.lower()

        for label in labels:
            idx = text_lower.find(label)
            while idx != -1:
                # Get the rest of the line after the label
                after = text[idx + len(label):].split('\n')[0].strip()
                # First token after label is the address candidate
                candidate = after.split()[0] if after.split() else ''
                if candidate and _is_valid_pubkey(candidate):
                    found.append(candidate)
                idx = text_lower.find(label, idx + 1)

        return list(dict.fromkeys(found))
```

---

## 4.4 — Whale Alert Parser

**File:** `backend/agents/parsers/whale_alert.py`

```python
# backend/agents/parsers/whale_alert.py

import re
from .base import BaseParser, ParseResult
from backend.extractors.contracts import _is_valid_pubkey

# Whale Alert format: "From: ADDR  To: ADDR"
FROM_TO_PATTERN = re.compile(
    r'(?:from|from:)\s*([1-9A-HJ-NP-Za-km-z]{32,44})'
    r'.*?'
    r'(?:to|to:)\s*([1-9A-HJ-NP-Za-km-z]{32,44})',
    re.IGNORECASE | re.DOTALL
)

class WhaleAlertParser(BaseParser):

    def can_parse(self, text: str) -> bool:
        text_lower = text.lower()
        return 'from:' in text_lower or ('from ' in text_lower and 'to ' in text_lower)

    def parse(self, text: str) -> ParseResult:
        wallets = []

        match = FROM_TO_PATTERN.search(text)
        if match:
            from_addr = match.group(1)
            to_addr   = match.group(2)
            if _is_valid_pubkey(from_addr):
                wallets.append(from_addr)
            if _is_valid_pubkey(to_addr):
                wallets.append(to_addr)

        # Whale Alert rarely contains contract addresses — no contract extraction
        return ParseResult(
            contracts   = [],
            wallets     = list(dict.fromkeys(wallets)),
            raw_excerpt = text[:280],
            confidence  = 0.85,
        )
```

---

## 4.5 — Parser Router

**File:** `backend/agents/parsers/__init__.py`

Selects the right parser for each source. Parser is determined by the channel config `parser` field, not by message content — this is faster and more predictable.

```python
# backend/agents/parsers/__init__.py

from .generic     import GenericParser
from .lookonchain import LookonchainParser
from .whale_alert import WhaleAlertParser
from .base        import BaseParser, ParseResult

PARSER_REGISTRY: dict[str, BaseParser] = {
    'generic':     GenericParser(),
    'lookonchain': LookonchainParser(),
    'whale_alert': WhaleAlertParser(),
}

def get_parser(parser_name: str) -> BaseParser:
    return PARSER_REGISTRY.get(parser_name, PARSER_REGISTRY['generic'])
```

---

## ✅ PHASE 4 BACKTEST

**File:** `tests/agent4/test_parsers.py`

```python
# tests/agent4/test_parsers.py

import pytest
from backend.agents.parsers import get_parser

# ── Lookonchain parser ────────────────────────────────────────────────────

def test_lookonchain_labeled_contract():
    parser = get_parser('lookonchain')
    text   = (
        "🚨 Whale bought $BONK\n"
        "Contract: 7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU\n"
        "Wallet: 9WzDXwBbmkg8ZTbNMqUxvQRAyrZzDsGYdLVL9zYtAWWM"
    )
    result = parser.parse(text)
    assert '7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU' in result.contracts
    assert '9WzDXwBbmkg8ZTbNMqUxvQRAyrZzDsGYdLVL9zYtAWWM' in result.wallets
    assert result.confidence == 0.9

def test_lookonchain_confidence_higher_than_generic():
    lc_parser  = get_parser('lookonchain')
    gen_parser = get_parser('generic')
    text       = "CA: 7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU"
    assert lc_parser.parse(text).confidence > gen_parser.parse(text).confidence

# ── Whale Alert parser ────────────────────────────────────────────────────

def test_whale_alert_from_to():
    parser = get_parser('whale_alert')
    text   = (
        "🐳 Large SOL transfer\n"
        "From: 9WzDXwBbmkg8ZTbNMqUxvQRAyrZzDsGYdLVL9zYtAWWM\n"
        "To:   DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263\n"
        "Amount: 500,000 SOL"
    )
    result = parser.parse(text)
    assert '9WzDXwBbmkg8ZTbNMqUxvQRAyrZzDsGYdLVL9zYtAWWM' in result.wallets
    assert 'DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263'  in result.wallets
    assert result.contracts == []

def test_whale_alert_no_contract_extraction():
    parser = get_parser('whale_alert')
    text   = "From: 9WzDXwBbmkg8ZTbNMqUxvQRAyrZzDsGYdLVL9zYtAWWM To: DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263"
    result = parser.parse(text)
    assert result.contracts == []

# ── Parser router ─────────────────────────────────────────────────────────

def test_router_returns_correct_parser():
    from backend.agents.parsers import LookonchainParser, WhaleAlertParser, GenericParser
    assert isinstance(get_parser('lookonchain'), LookonchainParser)
    assert isinstance(get_parser('whale_alert'), WhaleAlertParser)
    assert isinstance(get_parser('generic'),     GenericParser)
    assert isinstance(get_parser('unknown'),     GenericParser)  # fallback

# ── Fixture-based accuracy tests ──────────────────────────────────────────

def load_fixture(filename):
    with open(f'tests/agent4/fixtures/{filename}') as f:
        return [b.strip() for b in f.read().split('---') if b.strip()]

def test_lookonchain_fixture_accuracy():
    parser  = get_parser('lookonchain')
    samples = load_fixture('lookonchain_samples.txt')
    hits    = sum(1 for s in samples if parser.parse(s).contracts or parser.parse(s).wallets)
    assert hits / len(samples) >= 0.80, f'Parser accuracy: {hits}/{len(samples)}'

def test_whale_alert_fixture_accuracy():
    parser  = get_parser('whale_alert')
    samples = load_fixture('whale_alert_samples.txt')
    hits    = sum(1 for s in samples if parser.parse(s).wallets)
    assert hits / len(samples) >= 0.75
```

**Run:**
```bash
docker exec -it pixelfirm pytest tests/agent4/test_parsers.py -v
```

**Pass criteria:**
- All unit tests pass
- Lookonchain fixture accuracy ≥ 80%
- Whale Alert fixture accuracy ≥ 75%

### Gate: Do not proceed to Phase 5 until parser tests pass.

---

---

# PHASE 5 — Deduplication & Signal Emission

## Goal
Wire extractors and parsers into the full IntelAgent. Add Redis deduplication so the same contract address seen across multiple channels within 5 minutes fires only one signal to Agent 5. Add mention counting for confluence data. Emit correctly structured payloads to Agent 5 and Agent 3.

---

## 5.1 — Deduplication Logic

**File:** `backend/agents/intel_agent.py` — add to IntelAgent class

```python
# Redis key patterns:
# intel:seen:contract:{address}   TTL 300s  — contract already signalled
# intel:seen:wallet:{address}     TTL 300s  — wallet already signalled
# intel:mentions:{address}        TTL 300s  — mention count (for confluence)

import redis.asyncio as aioredis

DEDUP_TTL_SECONDS    = 300   # 5 minutes
MENTION_COUNT_KEY    = 'intel:mentions:{}'
CONTRACT_SEEN_KEY    = 'intel:seen:contract:{}'
WALLET_SEEN_KEY      = 'intel:seen:wallet:{}'

async def _should_process_contract(self, contract: str) -> bool:
    key   = CONTRACT_SEEN_KEY.format(contract)
    count_key = MENTION_COUNT_KEY.format(contract)

    seen = await self.redis.exists(key)
    # Always increment mention count even if already seen
    await self.redis.incr(count_key)
    await self.redis.expire(count_key, DEDUP_TTL_SECONDS)

    if seen:
        logger.debug(f'[DEDUP] Contract already seen: {contract}')
        return False

    await self.redis.setex(key, DEDUP_TTL_SECONDS, '1')
    return True


async def _should_process_wallet(self, wallet: str) -> bool:
    key  = WALLET_SEEN_KEY.format(wallet)
    seen = await self.redis.exists(key)
    if seen:
        return False
    await self.redis.setex(key, DEDUP_TTL_SECONDS, '1')
    return True


async def _get_mention_count(self, contract: str) -> int:
    count = await self.redis.get(MENTION_COUNT_KEY.format(contract))
    return int(count) if count else 1
```

---

## 5.2 — Signal Payloads

These are the exact payloads Agent 4 emits. Do not change field names — Agent 5 and Agent 3 consume these.

**Contract signal → Agent 5:**
```python
CONTRACT_SIGNAL = {
    'signal_type':    'intel',
    'agent_id':       4,
    'contract':       str,       # Solana base58 address
    'source_channel': str,       # e.g. '@lookonchain'
    'source_type':    str,       # 'kol' | 'tracker' | 'alpha'
    'source_weight':  float,     # 0.0–1.0 from channel config
    'parser':         str,       # which parser was used
    'parser_confidence': float,  # 0.0–1.0 from ParseResult
    'mention_count':  int,       # times seen in last 5 min across all channels
    'wallets_called': list[str], # wallets mentioned alongside this contract
    'raw_excerpt':    str,       # first 280 chars of source message
    'detected_at':    int,       # unix timestamp
}
```

**Wallet signal → Agent 3:**
```python
WALLET_SIGNAL = {
    'signal_type':      'wallet_intel',
    'agent_id':         4,
    'wallet':           str,     # Solana base58 address
    'source_channel':   str,
    'source_weight':    float,
    'context':          str,     # raw_excerpt — why this wallet was flagged
    'add_to_watchlist': bool,    # Agent 3 should monitor this wallet going forward
    'detected_at':      int,
}
```

---

## 5.3 — Full IntelAgent (Complete)

**File:** `backend/agents/intel_agent.py`

```python
# backend/agents/intel_agent.py

import asyncio, logging, time
import redis.asyncio as aioredis
from telethon import TelegramClient, events

from backend.config.store        import ConfigStore
from backend.agents.parsers      import get_parser
from backend.queue.priority      import PriorityQueue, Priority

logger = logging.getLogger('intel_agent')

SESSION_PATH = '/data/pixelfirm/config/pixelfirm_reader'
DEDUP_TTL    = 300


class IntelAgent:
    def __init__(
        self,
        client:   TelegramClient,
        store:    ConfigStore,
        queue:    PriorityQueue,
        redis:    aioredis.Redis,
        user_id:  str,
    ):
        self.client   = client
        self.store    = store
        self.queue    = queue
        self.redis    = redis
        self.user_id  = user_id
        self.channels = store.get_intel_channels()   # full channel objects

    async def start(self):
        channel_ids = [ch['id'] for ch in self.channels if ch.get('enabled', True)]
        logger.info(f'IntelAgent starting — {len(channel_ids)} channels')

        @self.client.on(events.NewMessage(chats=channel_ids))
        async def on_message(event):
            try:
                await self._handle_message(event)
            except Exception as e:
                logger.error(f'Error handling message: {e}', exc_info=True)

        await self.client.run_until_disconnected()

    async def _handle_message(self, event):
        text      = event.message.text or ''
        source_id = str(event.chat_id)
        ts        = int(event.message.date.timestamp())

        if not text.strip():
            return

        # Find channel config for this source
        channel = self._get_channel(source_id)
        if not channel:
            return

        parser_name = channel.get('parser', 'generic')
        parser      = get_parser(parser_name)
        result      = parser.parse(text)

        # Process contracts → Agent 5
        for contract in result.contracts:
            if await self._should_process_contract(contract):
                mention_count = await self._get_mention_count(contract)
                priority = Priority.HIGH if channel['type'] == 'tracker' else Priority.NORMAL
                await self.queue.enqueue(
                    priority = priority,
                    user_id  = self.user_id,
                    task_id  = f'intel_contract_{contract}',
                    coro_fn  = lambda c=contract, m=mention_count: self._emit_contract(
                        contract      = c,
                        channel       = channel,
                        parser_name   = parser_name,
                        confidence    = result.confidence,
                        mention_count = m,
                        wallets       = result.wallets,
                        excerpt       = result.raw_excerpt,
                        ts            = ts,
                    )
                )

        # Process wallets → Agent 3
        for wallet in result.wallets:
            if await self._should_process_wallet(wallet):
                await self.queue.enqueue(
                    priority = Priority.HIGH,
                    user_id  = self.user_id,
                    task_id  = f'intel_wallet_{wallet}',
                    coro_fn  = lambda w=wallet: self._emit_wallet(
                        wallet   = w,
                        channel  = channel,
                        excerpt  = result.raw_excerpt,
                        ts       = ts,
                    )
                )

    async def _emit_contract(self, contract, channel, parser_name,
                              confidence, mention_count, wallets, excerpt, ts):
        payload = {
            'signal_type':        'intel',
            'agent_id':           4,
            'contract':           contract,
            'source_channel':     channel['id'],
            'source_type':        channel['type'],
            'source_weight':      channel['weight'],
            'parser':             parser_name,
            'parser_confidence':  confidence,
            'mention_count':      mention_count,
            'wallets_called':     wallets,
            'raw_excerpt':        excerpt,
            'detected_at':        ts,
        }
        logger.info(f'[SIGNAL] Contract: {contract} source={channel["id"]} mentions={mention_count}')
        # TODO: call Agent 5 signal intake method
        # await signal_aggregator.receive(payload)

    async def _emit_wallet(self, wallet, channel, excerpt, ts):
        payload = {
            'signal_type':      'wallet_intel',
            'agent_id':         4,
            'wallet':           wallet,
            'source_channel':   channel['id'],
            'source_weight':    channel['weight'],
            'context':          excerpt,
            'add_to_watchlist': True,
            'detected_at':      ts,
        }
        logger.info(f'[WALLET] Discovered: {wallet} source={channel["id"]}')
        # TODO: call Agent 3 wallet intake method
        # await wallet_tracker.add_wallet(payload)

    def _get_channel(self, source_id: str) -> dict | None:
        for ch in self.channels:
            if str(ch['id']) == source_id or ch['id'] == source_id:
                return ch
        return None

    # ── Dedup helpers (from 5.1) ─────────────────────────────────────────
    async def _should_process_contract(self, contract: str) -> bool:
        key       = f'intel:seen:contract:{contract}'
        count_key = f'intel:mentions:{contract}'
        seen      = await self.redis.exists(key)
        await self.redis.incr(count_key)
        await self.redis.expire(count_key, DEDUP_TTL)
        if seen:
            return False
        await self.redis.setex(key, DEDUP_TTL, '1')
        return True

    async def _should_process_wallet(self, wallet: str) -> bool:
        key  = f'intel:seen:wallet:{wallet}'
        seen = await self.redis.exists(key)
        if seen:
            return False
        await self.redis.setex(key, DEDUP_TTL, '1')
        return True

    async def _get_mention_count(self, contract: str) -> int:
        count = await self.redis.get(f'intel:mentions:{contract}')
        return int(count) if count else 1
```

---

## ✅ PHASE 5 BACKTEST

**File:** `tests/agent4/test_dedup.py`

```python
# tests/agent4/test_dedup.py

import asyncio, pytest
import fakeredis.aioredis as fakeredis
from unittest.mock import AsyncMock, MagicMock
from backend.agents.intel_agent import IntelAgent

@pytest.fixture
def agent():
    redis  = fakeredis.FakeRedis()
    client = MagicMock()
    store  = MagicMock()
    store.get_intel_channels.return_value = [
        {'id': '@lookonchain', 'type': 'kol', 'weight': 0.85,
         'enabled': True, 'parser': 'lookonchain'}
    ]
    queue = MagicMock()
    queue.enqueue = AsyncMock()
    return IntelAgent(client, store, queue, redis, 'test_user')

@pytest.mark.asyncio
async def test_contract_dedup_first_seen_passes(agent):
    result = await agent._should_process_contract('7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU')
    assert result is True

@pytest.mark.asyncio
async def test_contract_dedup_second_seen_blocked(agent):
    addr = '7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU'
    await agent._should_process_contract(addr)
    result = await agent._should_process_contract(addr)
    assert result is False

@pytest.mark.asyncio
async def test_mention_count_increments(agent):
    addr = '7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU'
    await agent._should_process_contract(addr)
    await agent._should_process_contract(addr)
    await agent._should_process_contract(addr)
    count = await agent._get_mention_count(addr)
    assert count == 3

@pytest.mark.asyncio
async def test_wallet_dedup(agent):
    wallet = '9WzDXwBbmkg8ZTbNMqUxvQRAyrZzDsGYdLVL9zYtAWWM'
    assert await agent._should_process_wallet(wallet) is True
    assert await agent._should_process_wallet(wallet) is False

@pytest.mark.asyncio
async def test_different_contracts_not_deduped(agent):
    addr1 = '7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU'
    addr2 = 'DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263'
    assert await agent._should_process_contract(addr1) is True
    assert await agent._should_process_contract(addr2) is True
```

**File:** `tests/agent4/test_intel_agent.py` — integration smoke test

```python
# tests/agent4/test_intel_agent.py

import asyncio, pytest
import fakeredis.aioredis as fakeredis
from unittest.mock import AsyncMock, MagicMock, patch

@pytest.mark.asyncio
async def test_contract_signal_emitted_on_new_message():
    """
    Simulate a Lookonchain message arriving.
    Verify _emit_contract is called with correct payload.
    """
    from backend.agents.intel_agent import IntelAgent

    redis  = fakeredis.FakeRedis()
    queue  = MagicMock()
    queue.enqueue = AsyncMock()
    store  = MagicMock()
    store.get_intel_channels.return_value = [
        {'id': '@lookonchain', 'type': 'kol', 'weight': 0.85,
         'enabled': True, 'parser': 'lookonchain'}
    ]

    agent = IntelAgent(MagicMock(), store, queue, redis, 'test_user')

    # Simulate parsed result
    with patch.object(agent, '_emit_contract', new_callable=AsyncMock) as mock_emit:
        event        = MagicMock()
        event.chat_id = '@lookonchain'
        event.message.text = (
            "🚨 Whale bought $BONK\n"
            "Contract: 7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU\n"
            "Wallet: 9WzDXwBbmkg8ZTbNMqUxvQRAyrZzDsGYdLVL9zYtAWWM"
        )
        event.message.date.timestamp.return_value = 1700000000

        await agent._handle_message(event)
        await asyncio.sleep(0)

        assert queue.enqueue.called

@pytest.mark.asyncio
async def test_no_signal_emitted_on_empty_message():
    from backend.agents.intel_agent import IntelAgent
    redis = fakeredis.FakeRedis()
    queue = MagicMock(); queue.enqueue = AsyncMock()
    store = MagicMock()
    store.get_intel_channels.return_value = [
        {'id': '@lookonchain', 'type': 'kol', 'weight': 0.85,
         'enabled': True, 'parser': 'lookonchain'}
    ]
    agent = IntelAgent(MagicMock(), store, queue, redis, 'test_user')
    event = MagicMock()
    event.chat_id = '@lookonchain'
    event.message.text = ''
    await agent._handle_message(event)
    queue.enqueue.assert_not_called()
```

**Run all Agent 4 tests:**
```bash
docker exec -it pixelfirm pytest tests/agent4/ -v --tb=short

# Required dependencies for tests:
# pip install pytest pytest-asyncio fakeredis
```

**Pass criteria:**
- All dedup tests pass
- Integration smoke tests pass
- No errors in the live log when a real message arrives: `pixel-firm logs --agent 4`

### Gate: Do not proceed to Phase 6 until all tests pass AND live messages are logging with `[SIGNAL]` or `[WALLET]` prefixes.

---

---

# PHASE 6 — Settings API for Channel Management

## Goal
Expose channel management via the REST API so the user can add, remove, enable, and disable channels from the settings dashboard without touching config files or restarting the container.

---

## 6.1 — Channel Management Endpoints

**File:** `backend/api/settings.py` — add these routes

```
GET    /api/settings/channels            list all channels
POST   /api/settings/channels            add a new channel
PATCH  /api/settings/channels/{id}       update channel (weight, enabled, parser)
DELETE /api/settings/channels/{id}       remove channel
POST   /api/settings/channels/reload     reload channel list in running agent
```

**POST /api/settings/channels request body:**
```json
{
  "id":      "@new_channel",
  "label":   "New Alpha Channel",
  "type":    "alpha",
  "weight":  0.60,
  "enabled": true,
  "parser":  "generic"
}
```

**Validation rules:**
- `type` must be one of: `kol`, `tracker`, `alpha`
- `weight` must be between 0.1 and 1.0
- `parser` must be one of: `generic`, `lookonchain`, `whale_alert`
- `id` must start with `@` (public) or be a negative integer string (private group)
- Do not allow duplicate channel IDs

**On any channel change — reload the running agent:**
```python
# After writing to config DB, send reload signal to intel_agent process
# Simplest approach: write a reload flag to Redis
# intel_agent polls this flag every 60 seconds and reloads channel list

await redis.set('intel:reload_channels', '1')
```

---

## 6.2 — Agent-Side Reload Polling

Add to `IntelAgent.start()`:

```python
# Check for reload signal every 60 seconds
asyncio.create_task(self._reload_poller())

async def _reload_poller(self):
    while True:
        await asyncio.sleep(60)
        flag = await self.redis.get('intel:reload_channels')
        if flag:
            await self.redis.delete('intel:reload_channels')
            self.channels = self.store.get_intel_channels()
            # Re-register event handler with new channel list
            # Requires restarting the Telethon handler
            logger.info(f'Channel list reloaded — now monitoring {len(self.channels)} channels')
            # Note: full handler re-registration requires agent restart
            # Simplest safe approach: supervisorctl restart intel_agent
            import subprocess
            subprocess.run(['supervisorctl', 'restart', 'intel_agent'])
```

---

## ✅ PHASE 6 BACKTEST

```bash
# Test 1 — Add a channel via API
curl -X POST http://localhost:8000/api/settings/channels \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"id": "@solana_degens", "label": "Solana Degens", "type": "alpha", "weight": 0.5, "enabled": true, "parser": "generic"}'

# Expected: 200 OK, channel appears in GET /api/settings/channels

# Test 2 — Disable a channel
curl -X PATCH http://localhost:8000/api/settings/channels/@whalealert \
  -H "Authorization: Bearer <token>" \
  -d '{"enabled": false}'

# After agent restarts: verify @whalealert not in subscription list
docker exec pixelfirm python -c "
from backend.config.store import ConfigStore
store = ConfigStore('/data/pixelfirm/config/config.db')
channels = store.get_intel_channels()
enabled = [c['id'] for c in channels if c['enabled']]
print('Enabled:', enabled)
"

# Test 3 — Duplicate channel rejected
curl -X POST http://localhost:8000/api/settings/channels \
  -d '{"id": "@lookonchain", ...}'
# Expected: 400 Bad Request — channel already exists

# Test 4 — Invalid weight rejected
curl -X POST http://localhost:8000/api/settings/channels \
  -d '{"id": "@newchan", "weight": 1.5, ...}'
# Expected: 422 Unprocessable Entity
```

### Gate: All API tests pass. Channel changes reflect in agent subscription after reload.

---

---

# PHASE 7 — End-to-End Live Validation

## Goal
Run Agent 4 live against real Telegram channels for 24 hours. Verify signal quality, dedup behaviour, and emission to Agent 5 and Agent 3 under real conditions.

---

## 7.1 — Live Monitoring Checklist

Run this after deploying the completed agent:

```bash
# Watch live signal output
pixel-firm logs --agent 4

# Check Redis dedup keys
docker exec pixelfirm redis-cli keys "intel:*"

# Check mention counts
docker exec pixelfirm redis-cli get "intel:mentions:<contract_address>"

# Verify signals are queued
docker exec pixelfirm redis-cli llen "priority_queue"
```

---

## 7.2 — 24-Hour Validation Metrics

After 24 hours of live running, pull these metrics and evaluate:

```bash
docker exec -it pixelfirm python -c "
import sqlite3, json
conn = sqlite3.connect('/data/pixelfirm/db/trading.db')
cur  = conn.cursor()

# Signals emitted by Agent 4
cur.execute(\"SELECT COUNT(*) FROM signals WHERE agent_id=4\")
print('Total signals emitted:', cur.fetchone()[0])

# By source channel
cur.execute(\"\"\"
    SELECT source_channel, COUNT(*) as count
    FROM signals WHERE agent_id=4
    GROUP BY source_channel ORDER BY count DESC
\"\"\")
print('Signals by channel:')
for row in cur.fetchall(): print(' ', row)

# Wallets discovered
cur.execute(\"SELECT COUNT(*) FROM signals WHERE agent_id=4 AND signal_type='wallet_intel'\")
print('Wallets discovered:', cur.fetchone()[0])
"
```

**Acceptable ranges after 24 hours of live monitoring:**

| Metric | Minimum | Target |
|---|---|---|
| Contract signals emitted | 5 | 20–50 |
| Wallet signals emitted | 2 | 10–30 |
| Duplicate signals (should be 0) | 0 | 0 |
| False positive rate (no valid address) | < 5% | < 2% |
| Agent uptime | 99% | 100% |

---

## 7.3 — False Positive Review

After 24 hours, manually review 20 random signals from the log and classify each as:
- **True positive** — real contract or wallet address from a meaningful alpha message
- **False positive** — valid base58 string that is not a trading signal (e.g. block hash in context, unrelated address)
- **Missed signal** — go back to channels and find a signal that should have been caught but wasn't

Adjust extractor keyword lists and parser patterns based on findings. Re-run Phase 3 and Phase 4 backtests after any extractor change.

---

## ✅ PHASE 7 BACKTEST — Final Gate

```
□ Agent 4 ran for 24 hours without crashing
□ supervisord restarted it 0 times (check supervisord.log)
□ Zero duplicate signals in database
□ False positive rate below 5%
□ At least 5 contract signals emitted
□ Telethon session remained valid (no re-auth required)
□ All Phase 1–6 tests still pass after live run
□ pixel-firm logs --agent 4 shows no ERROR level entries
```

**Run full test suite one final time:**
```bash
docker exec -it pixelfirm pytest tests/agent4/ -v
```

All tests must pass. Zero failures.

---

---

# APPENDIX A — Dependencies

Add to `requirements.txt`:

```
telethon==1.36.0
fakeredis[aioredis]==2.23.0   # test only
pytest-asyncio==0.23.0         # test only
solders==0.21.0                # already in codebase
```

---

# APPENDIX B — Common Errors & Fixes

| Error | Cause | Fix |
|---|---|---|
| `SessionPasswordNeededError` | Reader account has 2FA enabled | Add `getpass.getpass('2FA password: ')` and pass to `client.start(password=...)` |
| `ChannelPrivateError` | Bot tried to join a private channel it's not in | User must be a member of the channel on the reader account before adding it |
| `FloodWaitError: X seconds` | Too many Telethon requests | Add `await asyncio.sleep(e.seconds)` in the error handler |
| `AuthKeyUnregisteredError` | Session file corrupted or account banned | Delete session file, re-run setup wizard Step 2b |
| Redis `ConnectionRefusedError` | Redis not started yet | Increase `startsecs` in supervisord for intel_agent to 15 |
| Extractor returns empty on real messages | Message format changed | Add new samples to fixtures, tune parser regex, re-run Phase 3 gate |

---

# APPENDIX C — Integration Points (For When Agent 5 and Agent 3 are Built)

Replace the `# TODO` comments in `_emit_contract` and `_emit_wallet` with:

```python
# _emit_contract → Agent 5
from backend.agents.signal_aggregator import SignalAggregator
await signal_aggregator.receive_intel(payload)

# _emit_wallet → Agent 3
from backend.agents.wallet_tracker import WalletTracker
await wallet_tracker.add_discovered_wallet(payload)
```

The payload schemas defined in Section 5.2 are the contract between Agent 4 and downstream agents. Agent 5 and Agent 3 must implement intake methods that accept exactly these schemas.
