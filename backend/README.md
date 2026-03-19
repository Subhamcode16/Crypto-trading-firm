# Solana Memecoin Autonomous Trading System

A fully autonomous trading system for discovering and trading Solana memecoin opportunities with strict risk controls.

**Status:** Phase 1 - Foundation Complete ✅

---

## Quick Start (Phase 1)

### Prerequisites
- Python 3.9+
- Git
- Telegram account (for alerts)

### Step 1: Clone & Setup

```bash
cd /home/node/.openclaw/workspace/projects/crypto-trading-system

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Step 2: Configure Telegram

1. **Create bot token:**
   - Open Telegram, message @BotFather
   - Send `/newbot`
   - Follow prompts to create a bot
   - Get your token (already provided: `8714510154:AAGRCQxfyibP1lhV0S0HsVfyJWVp08zLaOM`)

2. **Get your chat ID:**
   - In Telegram, message your bot (say "hello")
   - Run: `python3 src/main.py`
   - Bot will try to extract chat ID from message
   - OR check logs for the chat ID

### Step 3: Set Up Environment Variables

```bash
# Copy template
cp secrets.env.template secrets.env

# Edit secrets.env and add:
TELEGRAM_BOT_TOKEN=8714510154:AAGRCQxfyibP1lhV0S0HsVfyJWVp08zLaOM
TELEGRAM_CHAT_ID=your_chat_id_here
ANTHROPIC_API_KEY=your_api_key_here
```

### Step 4: Run Locally

```bash
# Make sure venv is active
source venv/bin/activate

# Run the bot
python3 src/main.py
```

**Expected output:**
```
✅ Config loaded
✅ Database initialized
✅ Telegram bot initialized
✅ Scheduler initialized
Bot initialized successfully
Bot running. Press Ctrl+C to stop.
```

---

## Project Structure

```
crypto-trading-system/
├── config/
│   └── config.yaml              # System configuration
├── src/
│   ├── __init__.py
│   ├── main.py                  # Entry point
│   ├── config.py                # Config loader
│   ├── database.py              # SQLite interface
│   ├── telegram_bot.py          # Telegram alerts
│   ├── scheduler.py             # APScheduler setup
│   └── logger.py                # JSON logging
├── data/
│   ├── database.db              # SQLite (created on first run)
│   └── logs/                    # Daily JSON logs
├── requirements.txt             # Python dependencies
├── secrets.env                  # API keys (DO NOT COMMIT)
├── secrets.env.template         # Template for secrets
├── .gitignore                   # Git ignore rules
└── README.md                    # This file
```

---

## Configuration (config.yaml)

All settings can be edited in `config/config.yaml`:

**Trading Parameters:**
- `starting_capital`: $10.0 (don't change during Phase 1)
- `daily_loss_limit`: $3.0 (30% of capital)
- `portfolio_max_exposure`: 30% (max open position exposure)

**Risk Management:**
- `stop_loss_percent`: 20% (below entry)
- `take_profit_tier1`: 2.0x (2x entry price)
- `take_profit_tier2`: 4.0x (4x entry price)
- `trailing_stop_percent`: 50% (trailing stop for remaining 20%)

**Scheduler:**
- `researcher_interval_minutes`: 15 (run researcher every 15 min)
- `position_monitor_interval_seconds`: 60 (monitor positions every 60 sec)

---

## Database

SQLite database automatically created at `data/database.db` on first run.

**Tables:**
- `signals` - All signals (sent/dropped)
- `trades` - Trade executions and P&L
- `daily_summary` - Daily stats
- `system_events` - Errors, kills, alerts

---

## Logging

JSON logs written to `data/logs/YYYY-MM-DD.log`

Each entry contains:
- `timestamp` (UTC)
- `level` (INFO, WARNING, ERROR, CRITICAL)
- `logger` (module name)
- `message` (log message)

---

## Getting Your Telegram Chat ID

If you don't have your chat ID yet:

1. **Message your bot in Telegram**
   - Send any message (e.g., "hello")

2. **Run the bot:**
   ```bash
   python3 src/main.py
   ```

3. **Check the logs:**
   - Look in `data/logs/YYYY-MM-DD.log`
   - Find your chat ID

4. **Update secrets.env:**
   ```
   TELEGRAM_CHAT_ID=your_chat_id_here
   ```

5. **Restart the bot:**
   ```bash
   python3 src/main.py
   ```

---

## Phase 1 Completion Checklist

- [x] Project structure created
- [x] Config system working
- [x] Database initialized
- [x] Telegram bot setup
- [x] Scheduler framework ready
- [x] Logging system working
- [x] Main entry point ready

**Next:** Phase 2 - On-Chain Intelligence (Dexscreener, rug detection, AI scoring)

---

## Troubleshooting

### "TELEGRAM_BOT_TOKEN required"
- Check `secrets.env` file exists
- Make sure `TELEGRAM_BOT_TOKEN` is set correctly

### "TELEGRAM_CHAT_ID not set"
- This is normal on first run
- Message your bot and restart
- Chat ID will be extracted from message

### "Config file not found"
- Make sure `config/config.yaml` exists
- Run from project root directory

### Port already in use
- Check if another bot instance is running
- Kill with: `pkill -f "python3 src/main.py"`

---

## Next Steps (Phase 2)

Phase 2 adds on-chain intelligence:
- Dexscreener API integration
- 6-point rug detection filter
- Claude Haiku confidence scoring
- Real signal generation

**Timeline:** 2-3 weeks

---

## Support

If you hit issues during Phase 1, check:
1. All dependencies installed: `pip install -r requirements.txt`
2. Python version: `python3 --version` (need 3.9+)
3. secrets.env configured with your keys
4. Telegram bot token valid (get from @BotFather)

---

## License

Proprietary - Subham Rath

---

**Built with:** Python 3.9+ | SQLite | APScheduler | python-telegram-bot | PyYAML

**Version:** 1.0.0 - Phase 1 Foundation
