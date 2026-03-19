# backend/src/agents/agent_4_intel_agent.py

import os
import json
import logging
import asyncio
from typing import Dict, List, Optional
from telethon import TelegramClient, events
from src.config import Config
from src.database import Database
from src.config.default_channels import DEFAULT_CHANNELS

# Parsers
from src.agents.parsers.generic import GenericParser
from src.agents.parsers.lookonchain import LookonchainParser
from src.agents.parsers.whale_alert import WhaleAlertParser

logger = logging.getLogger('intel_agent')

SESSION_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'config', 'pixelfirm_reader')

class Agent4IntelAgent:
    """
    AGENT 4: Telegram Intel (Telethon)
    Role: Monitors Telegram alpha channels in real-time, extracts CAs and wallets.
    Discovery only — emits signals to Aggragator (A5) and Tracker (A3).
    """
    
    def __init__(self, config: Config, db: Database):
        self.config = config
        self.db = db
        self.client: Optional[TelegramClient] = None
        self.channels: List[Dict] = []
        
        # Initialize Parsers
        self.parsers = {
            "generic": GenericParser(),
            "lookonchain": LookonchainParser(),
            "whale_alert": WhaleAlertParser()
        }
        
        # Signal targets (will be wired by main.py)
        self.agent_3 = None  # Wallet Tracker
        self.agent_5 = None  # Signal Aggregator

        logger.info("[AGENT_4] Telegram Intel Agent initialized")

    async def start(self):
        """Start the Telethon client and subscribe to channels."""
        try:
            # 1. Load credentials
            api_id = self.config.get_optional_secret('TELEGRAM_API_ID')
            api_hash = self.config.get_optional_secret('TELEGRAM_API_HASH')
            
            if not api_id or not api_hash:
                logger.warning("[AGENT_4] TELEGRAM_API_ID/HASH missing. Intel Agent disabled.")
                return

            # 2. Check for session file
            if not os.path.exists(SESSION_PATH + '.session'):
                logger.warning(f"[AGENT_4] No Telethon session found at {SESSION_PATH}. Run setup_wizard.py first.")
                return

            # 3. Initialize Telethon Client
            self.client = TelegramClient(SESSION_PATH, int(api_id), api_hash)
            await self.client.start()
            
            me = await self.client.get_me()
            logger.info(f"✅ [AGENT_4] Telethon authenticated as: {me.first_name} (@{me.username})")

            # 4. Load Channels from DB or Default
            await self._load_channels()
            
            # 5. Subscribe to Events
            enabled_ids = [ch['id'] for ch in self.channels if ch.get('enabled', True)]
            if not enabled_ids:
                logger.warning("[AGENT_4] No channels enabled for monitoring.")
                return
                
            logger.info(f"[AGENT_4] Monitoring {len(enabled_ids)} channels: {enabled_ids}")

            @self.client.on(events.NewMessage(chats=enabled_ids))
            async def handler(event):
                await self._process_message(event)

            logger.info("[AGENT_4] Listening for real-time messages...")
            # Note: We don't use run_until_disconnected() here because 
            # this agent runs as a task within the main loop.
            
        except Exception as e:
            logger.error(f"[AGENT_4] Start failed: {e}")

    async def _load_channels(self):
        """Load channel configuration from Convex via Database system_state."""
        raw_channels = await self.db.get_system_state("intel_channels")
        if not raw_channels:
            # First run seed
            self.channels = DEFAULT_CHANNELS
            await self.db.set_system_state("intel_channels", json.dumps(DEFAULT_CHANNELS))
            logger.info("[AGENT_4] Seeded default channels to database")
        else:
            self.channels = json.loads(raw_channels)

    async def _process_message(self, event):
        """Parse incoming message and emit signals."""
        try:
            text = event.message.text or ""
            if not text:
                return

            # Find which channel this came from
            chat = await event.get_chat()
            chat_id = getattr(chat, 'username', None) or str(event.chat_id)
            if not chat_id.startswith('@') and not chat_id.startswith('-'):
                chat_id = f"@{chat_id}" if getattr(chat, 'username', None) else chat_id

            # Find matching configuration
            channel_cfg = next((c for c in self.channels if c['id'] == chat_id or c['id'] == f"@{chat_id}"), None)
            if not channel_cfg:
                # Fallback search by peer ID
                peer_id = event.message.peer_id
                logger.debug(f"[AGENT_4] Message from unknown chat ID: {chat_id} (peer: {peer_id})")
                parser_name = "generic"
            else:
                parser_name = channel_cfg.get('parser', 'generic')

            # Parse
            parser = self.parsers.get(parser_name, self.parsers["generic"])
            result = parser.parse(text, metadata={"channel": chat_id, "timestamp": str(event.message.date)})

            if result.contracts or result.wallets:
                logger.info(f"🔍 [AGENT_4] Signal detected in {chat_id}: {len(result.contracts)} CAs, {len(result.wallets)} Wallets")
                await self._emit_signals(result)

        except Exception as e:
            logger.error(f"[AGENT_4] Message processing error: {e}")

    async def _emit_signals(self, result):
        """Route signals to appropriate agents."""
        # 1. Emit Contracts to Agent 5 (Signal Aggregator)
        if result.contracts and self.agent_5:
            for ca in result.contracts:
                logger.info(f"📡 [AGENT_4] Emitting token signal -> A5: {ca[:8]}")
                # In wait mode: Agent 5 usually aggregates. For discovery, 
                # we might need to trigger Agent 1 (Researcher) or check if it's new.
                # The PixelFirm spec says "Emits contract signals -> Agent 5".
                # We'll simulate a discovery pulse.
                asyncio.create_task(self._pulse_agent_5(ca, result))

        # 2. Emit Wallets to Agent 3 (Wallet Tracker)
        if result.wallets and self.agent_3:
            for wallet in result.wallets:
                logger.info(f"🕵️ [AGENT_4] Emitting wallet signal -> A3: {wallet[:8]}")
                asyncio.create_task(self.agent_3.process_priority_signal({
                    "address": result.contracts[0] if result.contracts else "unknown",
                    "wallet": wallet,
                    "source": f"telegram_{result.source_label}"
                }))

    async def _pulse_agent_5(self, ca: str, result):
        """
        Notify Agent 5 of a new discovery.
        Since Agent 5 usually cross-references, we might need to 
        kick off Agent 1 (Researcher) if the token isn't known.
        """
        # Placeholder for A5 integration
        pass

    async def stop(self):
        if self.client:
            await self.client.disconnect()
            logger.info("[AGENT_4] Telethon client disconnected")

if __name__ == '__main__':
    # Mock run for testing
    import sys
    from src.logger import setup_logger
    setup_logger('intel_agent')
    logger.info("Agent 4 module loaded. Ready for integration.")
