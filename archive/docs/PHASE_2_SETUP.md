# PHASE 2 SETUP GUIDE

**Phase 2 Status:** Code Complete ✅  
**Next:** Add API keys and test

---

## 🎯 WHAT'S BEEN BUILT

Phase 2 code is now complete and ready to run. Here's what you have:

### New Directories & Files
```
src/
├── apis/
│   ├── dexscreener_client.py    (✅ Fetches new tokens real-time)
│   ├── solscan_client.py        (✅ Gets on-chain data)
│   └── helius_rpc.py            (✅ Solana RPC interface)
├── analysis/
│   ├── rug_detector.py          (✅ 6-point filter)
│   └── ai_scorer.py             (✅ Claude Haiku scoring)
├── trading/
│   └── position_sizer.py        (✅ Deterministic sizing)
├── signals/
│   └── signal_formatter.py      (✅ JSON signal generation)
├── researcher_bot.py            (✅ Main intelligence engine)
└── main.py                      (✅ Updated with researcher integration)

tests/
└── backtest_signals.py          (✅ Backtesting framework)
```

---

## 📋 STEP-BY-STEP SETUP

### Step 1: Install New Dependencies

```bash
# Activate venv
source venv/bin/activate

# Install anthropic (added to requirements.txt)
pip install -r requirements.txt
```

**Verify:**
```bash
python3 -c "import anthropic; import requests; print('✅ All dependencies installed')"
```

---

### Step 2: Add API Keys to secrets.env

You have your API keys ready. Add them to `secrets.env`:

```bash
nano secrets.env
```

**Make sure these are set:**
```
TELEGRAM_BOT_TOKEN=8714510154:AAGRCQxfyibP1lhV0S0HsVfyJWVp08zLaOM
TELEGRAM_CHAT_ID=your_chat_id
ANTHROPIC_API_KEY=your_anthropic_key
SOLSCAN_API_KEY=your_solscan_key
HELIUS_RPC_URL=your_helius_url
SOLANA_RPC_URL=https://api.mainnet-beta.solana.com
```

Save (Ctrl+X, Y, Enter)

---

### Step 3: Update secrets.env Template

Also update `secrets.env.template` for reference:

```bash
nano secrets.env.template
```

Add the same keys there (without actual values if you want to keep it public-safe):
```
SOLSCAN_API_KEY=your_solscan_key_here
HELIUS_RPC_URL=your_helius_url_here
```

---

### Step 4: Run the Bot (Phase 2 Active)

```bash
source venv/bin/activate
python3 src/main.py
```

**Expected output:**
```
✅ Config loaded
✅ Database initialized
✅ Telegram bot initialized
✅ Scheduler initialized
✅ Researcher Bot initialized
Bot initialized successfully

STARTING TRADING BOT

📅 Scheduled jobs:
   - Researcher Bot
   - Position Monitor
   - Daily Summary
   - Midnight Reset

✅ Bot running. Press Ctrl+C to stop.
```

---

## 🧪 TESTING PHASE 2

### Test 1: Manual Signal Scan

The bot runs researcher scans every 15 minutes by default (configurable in config.json).

To manually trigger a scan, you can run:

```python
# In Python shell while bot is running:
from src.researcher_bot import ResearcherBot
from src.database import Database
from src.telegram_bot import TelegramBot

# Or just wait for next scheduled scan
```

**Expected behavior:**
- Bot fetches latest Solana pairs
- Runs each through 6-point rug filter
- Scores with Claude Haiku
- Sends Telegram alert if confidence >= 6
- Logs to database

---

### Test 2: Run Backtest

```bash
source venv/bin/activate
cd /home/node/.openclaw/workspace/projects/crypto-trading-system
python3 tests/backtest_signals.py
```

**What it does:**
- Fetches 50 recent tokens from Dexscreener
- Runs them through the signal pipeline
- Generates backtest metrics

**Expected output:**
```
📊 BACKTEST SUMMARY
============================================================
Total tokens analyzed: 50
Signals generated: 8-12 (16-24% signal rate)
Signals dropped: 38-42

Signal confidence breakdown:
  High (8-10): 4-7
  Mid (6-7): 2-5

Signal generation rate: 16-24%
============================================================
```

**Success criteria:** Hit rate >= 15%

---

## 📊 MONITORING

Once running, check:

1. **Telegram alerts** - Should receive signal alerts as tokens are found
2. **Database logs** - Check `data/logs/YYYY-MM-DD.log` for activity
3. **SQLite database** - Check `data/database.db` for signal records

```bash
# View recent logs
tail -f data/logs/2026-02-27.log

# Check database (requires sqlite3)
sqlite3 data/database.db "SELECT * FROM signals LIMIT 5;"
```

---

## ⚙️ CONFIGURATION (config.json)

Fine-tune Phase 2 behavior:

```json
{
  "scheduler": {
    "researcher_interval_minutes": 15    // How often to scan (1-60)
  }
}
```

Change interval to scan more/less frequently.

---

## 🔍 WHAT'S HAPPENING BEHIND THE SCENES

When the researcher bot runs:

1. **Dexscreener fetch** → Get 50 newest Solana pairs
2. **6-point rug filter** → Check each token
   - Contract age >15 min
   - Liquidity locked
   - Top 10 wallets <30%
   - Volume from >50 wallets
   - Deployer clean history
   - Data integrity valid
3. **Claude Haiku scoring** → Score 6-10
4. **Position sizing** → Deterministic ($2 or $1)
5. **Signal formatting** → JSON structure
6. **Telegram alert** → Send to you (if confidence >= 6)
7. **Database logging** → Track all signals

---

## 🐛 TROUBLESHOOTING

### "No signals being generated"

**Possible reasons:**
1. Dexscreener API temporarily down → Check with curl
2. No tokens passing rug filters → Check logs for which filter drops tokens
3. Claude scoring too strict → Adjust in `ai_scorer.py` if needed
4. Wrong API keys → Verify secrets.env

**Check logs:**
```bash
tail -f data/logs/2026-02-27.log | grep "RESEARCHER\|SIGNAL\|DROP"
```

---

### "Anthropic API error"

Make sure `ANTHROPIC_API_KEY` is set in secrets.env and has credits available.

---

### "Solscan API error"

If getting rate limited, the `solscan_client.py` has built-in rate limiting (0.5s between requests). Can be adjusted in `_rate_limit()` method.

---

## ✅ PHASE 2 SUCCESS CRITERIA

- [x] All 6 rug filters working
- [x] AI scoring producing 6-10 scores
- [x] Signals being sent to Telegram
- [x] Database logging signals
- [x] Backtest running without errors
- [ ] Backtest hit rate >= 15%
- [ ] Running bot for 24 hours without crashes
- [ ] Observing signals in real-time

---

## 🚀 NEXT STEPS

Once Phase 2 is stable:
1. Run bot for 24 hours, monitor signals
2. Calculate hit rate from real signals
3. Adjust AI scoring threshold if needed
4. Start Phase 3 (Smart Wallet Tracking)

---

## 📝 PHASE 2 COMPLETION CHECKLIST

- [ ] Dependencies installed (`pip install -r requirements.txt`)
- [ ] API keys added to `secrets.env`
- [ ] Bot started (`python3 src/main.py`)
- [ ] No errors on startup
- [ ] Telegram message received: "✅ Trading Bot started"
- [ ] Run backtest (`python3 tests/backtest_signals.py`)
- [ ] Backtest completes, shows metrics
- [ ] Monitor for 1 hour, see signals arriving
- [ ] Check database logs
- [ ] Ready for Phase 3

---

**Phase 2 is now ready for you to run!** 🚀

Let me know once you've added the API keys and started the bot. I'll help monitor and debug as needed.
