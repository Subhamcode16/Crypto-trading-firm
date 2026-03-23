"""
PixelFirm Telegram Bot
======================
Full-stack bot with:
  - LLM-powered free-text chat (Claude Haiku)
  - Agent command control (/start /pause /resume /mode /status)
  - Proactive push alerts via Redis pub/sub
  - Conversation history (MongoDB)
  - Auth guard (allowlist of Telegram user IDs)

Requirements:
  pip install python-telegram-bot anthropic redis motor pymongo python-dotenv

Environment variables (.env):
  BOT_TOKEN            - Telegram bot token
  ANTHROPIC_API_KEY    - Anthropic API key
  ALLOWED_USER_IDS     - Comma-separated Telegram user IDs (e.g. 123456,789012)
  MONGO_URI            - MongoDB connection string (default: mongodb://localhost:27017)
  REDIS_URL            - Redis URL (default: redis://localhost:6379)
  YOUR_CHAT_ID         - Your personal Telegram chat ID for proactive alerts
"""

import os
import json
import asyncio
import logging
import threading
from datetime import datetime
from functools import wraps
from dotenv import load_dotenv

import redis
import anthropic
import motor.motor_asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

# ─────────────────────────────────────────────
# Config
# ─────────────────────────────────────────────

load_dotenv()

BOT_TOKEN         = os.environ["BOT_TOKEN"]
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
MONGO_URI         = os.getenv("MONGO_URI", "mongodb://localhost:27017")
REDIS_URL         = os.getenv("REDIS_URL", "redis://localhost:6379")
YOUR_CHAT_ID      = int(os.environ["YOUR_CHAT_ID"])

ALLOWED_USER_IDS  = set(
    int(uid.strip())
    for uid in os.getenv("ALLOWED_USER_IDS", "").split(",")
    if uid.strip()
)

MAX_HISTORY       = 12   # messages kept in context per user
HAIKU_MODEL       = "claude-haiku-4-5-20251001"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
log = logging.getLogger("pixelfirm-bot")

# ─────────────────────────────────────────────
# Clients
# ─────────────────────────────────────────────

r          = redis.from_url(REDIS_URL, decode_responses=True)
mongo      = motor.motor_asyncio.AsyncIOMotorClient(MONGO_URI)
db         = mongo["pixelfirm"]
ai_client  = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

# ─────────────────────────────────────────────
# System Prompt
# ─────────────────────────────────────────────

SYSTEM_PROMPT = """You are PixelFirm's onboard trading intelligence assistant — the human-facing layer of a 9-agent autonomous Solana memecoin trading system.

Your personality: direct, sharp, technical. You know the pipeline inside out. You speak like a senior quant who also knows how to explain things clearly.

The 9-agent pipeline you oversee:
- Agent-1 (Data Collector): Pulls real-time token data from Helius, DexScreener, Birdeye
- Agent-2 (Researcher): Discovers new/trending tokens, scores them, filters rugs
- Agent-3 (On-chain Analyzer): Deep-dives wallet activity, holder distribution
- Agent-4 (Telegram Intel): Monitors alpha channels via Telethon (Lookonchain, Whale Alert, KOLs)
- Agent-5 (Social Sentiment): Cross-references CT sentiment
- Agent-6 (Macro Sentinel): Composite BTC/SOL downtrend detection via Binance/Bybit
- Agent-7 (Risk Manager): 3-tier kill switch, position limits, DB-persistent state
- Agent-8 (Trading Bot): Paper/live trading, 2-stage TP, Axiom observability, Parabolic SAR trailing stops
- Agent-9 (Reporter): Aggregates P&L, win rate, drawdown reports

When the user asks questions:
- Answer concisely — this is Telegram, not a dashboard
- If they ask about signal flow, explain which agents are involved
- If they ask why tokens are being dropped, help them diagnose (thresholds, filters, source quality)
- If they give a command, confirm it and explain what will happen

Current pipeline state (injected live):
{pipeline_state}

Today's date: {date}
"""

# ─────────────────────────────────────────────
# Pipeline State (from Redis)
# ─────────────────────────────────────────────

def get_pipeline_state() -> dict:
    """Pull current agent states from Redis. Returns defaults if keys missing."""
    keys = [
        "pixelfirm:researcher:stats",
        "pixelfirm:macro:state",
        "pixelfirm:risk:state",
        "pixelfirm:trading:state",
        "pixelfirm:mode",
    ]
    values = r.mget(keys)

    def safe_parse(v):
        try:
            return json.loads(v) if v else {}
        except Exception:
            return {}

    return {
        "researcher": safe_parse(values[0]) or {
            "tokens_scanned": 0, "passed": 0, "dropped": 0, "last_signal": "none"
        },
        "macro": safe_parse(values[1]) or {
            "market_condition": "unknown", "btc_trend": "neutral", "sol_trend": "neutral"
        },
        "risk": safe_parse(values[2]) or {
            "kill_switch_level": 0, "active_positions": 0, "daily_pnl": 0.0
        },
        "trading": safe_parse(values[3]) or {
            "mode": "paper", "open_trades": 0, "win_rate": "N/A"
        },
        "mode": values[4] or "paper",
    }

def format_state_for_llm(state: dict) -> str:
    return json.dumps(state, indent=2)

# ─────────────────────────────────────────────
# MongoDB — Conversation History
# ─────────────────────────────────────────────

async def get_history(user_id: int) -> list[dict]:
    doc = await db.conversations.find_one({"user_id": user_id})
    if not doc:
        return []
    return doc.get("messages", [])[-MAX_HISTORY:]

async def save_history(user_id: int, messages: list[dict]):
    await db.conversations.update_one(
        {"user_id": user_id},
        {"$set": {"messages": messages[-MAX_HISTORY:], "updated_at": datetime.utcnow()}},
        upsert=True,
    )

async def clear_history(user_id: int):
    await db.conversations.delete_one({"user_id": user_id})

# ─────────────────────────────────────────────
# Auth Decorator
# ─────────────────────────────────────────────

def auth_required(func):
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        uid = update.effective_user.id
        if ALLOWED_USER_IDS and uid not in ALLOWED_USER_IDS:
            log.warning(f"Blocked unauthorized user {uid}")
            await update.message.reply_text("⛔ Unauthorized.")
            return
        return await func(update, context)
    return wrapper

# ─────────────────────────────────────────────
# Command Handlers
# ─────────────────────────────────────────────

@auth_required
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send welcome message with inline keyboard."""
    keyboard = [
        [
            InlineKeyboardButton("▶ Resume Pipeline", callback_data="action:resume"),
            InlineKeyboardButton("⏸ Pause Pipeline",  callback_data="action:pause"),
        ],
        [
            InlineKeyboardButton("📊 Status",          callback_data="action:status"),
            InlineKeyboardButton("📄 Reset Chat",      callback_data="action:reset_chat"),
        ],
        [
            InlineKeyboardButton("🔄 Switch → Live",   callback_data="action:mode:live"),
            InlineKeyboardButton("🧪 Switch → Paper",  callback_data="action:mode:paper"),
        ],
    ]
    markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "👋 *PixelFirm Online*\n\n"
        "I'm your autonomous trading assistant. You can:\n"
        "• Ask me anything about the pipeline in plain English\n"
        "• Use commands below to control agents\n"
        "• I'll push alerts to you when signals fire\n\n"
        "Type a question or tap a button to get started.",
        parse_mode="Markdown",
        reply_markup=markup,
    )

@auth_required
async def cmd_pause(update: Update, context: ContextTypes.DEFAULT_TYPE):
    r.publish("pixelfirm:commands", json.dumps({"action": "pause_all", "source": "telegram"}))
    r.set("pixelfirm:mode", "paused")
    await update.message.reply_text(
        "⏸ *Pipeline paused.*\n\nAll agents are standing by. No new trades will be opened.\nSend /resume to restart.",
        parse_mode="Markdown",
    )

@auth_required
async def cmd_resume(update: Update, context: ContextTypes.DEFAULT_TYPE):
    r.publish("pixelfirm:commands", json.dumps({"action": "resume_all", "source": "telegram"}))
    r.set("pixelfirm:mode", "running")
    await update.message.reply_text(
        "▶ *Pipeline resumed.*\n\nAgents are back online and scanning.",
        parse_mode="Markdown",
    )

@auth_required
async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    state = get_pipeline_state()
    r = state["researcher"]
    m = state["macro"]
    rk = state["risk"]
    t = state["trading"]

    status_emoji = {"running": "🟢", "paused": "🟡", "paper": "🧪", "live": "🔴"}.get
    mode = state["mode"]

    msg = (
        f"📊 *PixelFirm Status*\n"
        f"Mode: {status_emoji(mode, '⚪')} `{mode.upper()}`\n\n"
        f"*Researcher*\n"
        f"  Scanned: `{r.get('tokens_scanned', 0)}`  Passed: `{r.get('passed', 0)}`  Dropped: `{r.get('dropped', 0)}`\n"
        f"  Last signal: `{r.get('last_signal', 'none')}`\n\n"
        f"*Macro Sentinel*\n"
        f"  Condition: `{m.get('market_condition', 'unknown')}`\n"
        f"  BTC: `{m.get('btc_trend', '?')}` | SOL: `{m.get('sol_trend', '?')}`\n\n"
        f"*Risk Manager*\n"
        f"  Kill switch level: `{rk.get('kill_switch_level', 0)}`\n"
        f"  Open positions: `{rk.get('active_positions', 0)}`\n"
        f"  Daily P&L: `${rk.get('daily_pnl', 0.0):.2f}`\n\n"
        f"*Trading Bot*\n"
        f"  Open trades: `{t.get('open_trades', 0)}`\n"
        f"  Win rate: `{t.get('win_rate', 'N/A')}`"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")

@auth_required
async def cmd_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if not args or args[0].lower() not in ("paper", "live"):
        await update.message.reply_text(
            "Usage: `/mode paper` or `/mode live`", parse_mode="Markdown"
        )
        return
    new_mode = args[0].lower()
    r.set("pixelfirm:mode", new_mode)
    r.publish("pixelfirm:commands", json.dumps({"action": "set_mode", "mode": new_mode, "source": "telegram"}))
    emoji = "🧪" if new_mode == "paper" else "🔴"
    await update.message.reply_text(
        f"{emoji} Mode switched to *{new_mode.upper()}*.", parse_mode="Markdown"
    )

@auth_required
async def cmd_reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await clear_history(update.effective_user.id)
    await update.message.reply_text("🗑 Chat history cleared. Fresh context loaded.")

@auth_required
async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "*PixelFirm Bot Commands*\n\n"
        "/start — Show control panel\n"
        "/status — Live pipeline snapshot\n"
        "/pause — Pause all agents\n"
        "/resume — Resume all agents\n"
        "/mode paper|live — Switch trading mode\n"
        "/reset — Clear conversation history\n"
        "/help — Show this message\n\n"
        "Or just type anything — I'll answer in plain English.",
        parse_mode="Markdown",
    )

# ─────────────────────────────────────────────
# Inline Button Callbacks
# ─────────────────────────────────────────────

@auth_required
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data  # e.g. "action:pause" or "action:mode:live"

    parts = data.split(":")
    action = parts[1] if len(parts) > 1 else ""

    if action == "pause":
        await cmd_pause.__wrapped__(update, context)
    elif action == "resume":
        await cmd_resume.__wrapped__(update, context)
    elif action == "status":
        await cmd_status.__wrapped__(update, context)
    elif action == "reset_chat":
        await clear_history(update.effective_user.id)
        await query.edit_message_text("🗑 Chat history cleared.")
    elif action == "mode" and len(parts) > 2:
        context.args = [parts[2]]
        await cmd_mode.__wrapped__(update, context)
    else:
        await query.edit_message_text("Unknown action.")

# ─────────────────────────────────────────────
# LLM Chat Handler
# ─────────────────────────────────────────────

@auth_required
async def llm_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id   = update.effective_user.id
    user_text = update.message.text.strip()

    if not user_text:
        return

    # Show typing indicator
    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id, action="typing"
    )

    # Load history + add new user message
    history = await get_history(user_id)
    history.append({"role": "user", "content": user_text})

    # Build system prompt with live state
    state = get_pipeline_state()
    system = SYSTEM_PROMPT.format(
        pipeline_state=format_state_for_llm(state),
        date=datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
    )

    try:
        response = ai_client.messages.create(
            model=HAIKU_MODEL,
            max_tokens=600,
            system=system,
            messages=history,
        )
        reply = response.content[0].text.strip()
    except anthropic.APIError as e:
        log.error(f"Anthropic API error: {e}")
        reply = "⚠️ LLM unavailable right now. Try again in a moment."

    # Save updated history
    history.append({"role": "assistant", "content": reply})
    await save_history(user_id, history)

    await update.message.reply_text(reply, parse_mode="Markdown")

# ─────────────────────────────────────────────
# Proactive Alert Pusher (Redis pub/sub thread)
# ─────────────────────────────────────────────

def start_alert_listener(app):
    """
    Runs in a background daemon thread.
    Agents publish to pixelfirm:alerts channel like:
    {
        "type": "signal",
        "token": "BONK",
        "mint": "DezXAZ...",
        "score": 8.4,
        "reason": "Whale accumulation + KOL mention",
        "dex_url": "https://dexscreener.com/solana/..."
    }
    """
    log.info("Alert listener started — subscribed to pixelfirm:alerts")
    pubsub = r.pubsub()
    pubsub.subscribe("pixelfirm:alerts")

    loop = asyncio.new_event_loop()

    for message in pubsub.listen():
        if message["type"] != "message":
            continue
        try:
            alert = json.loads(message["data"])
            alert_type = alert.get("type", "signal")

            if alert_type == "signal":
                text = (
                    f"🚨 *New Signal Fired*\n\n"
                    f"Token: `{alert.get('token', '?')}`\n"
                    f"Mint: `{alert.get('mint', '?')[:12]}...`\n"
                    f"Score: `{alert.get('score', 0):.1f} / 10`\n"
                    f"Reason: {alert.get('reason', 'N/A')}\n\n"
                    f"[View on DexScreener]({alert.get('dex_url', '#')})"
                )
            elif alert_type == "trade_open":
                text = (
                    f"📈 *Trade Opened*\n\n"
                    f"Token: `{alert.get('token', '?')}`\n"
                    f"Entry: `${alert.get('entry_price', 0):.6f}`\n"
                    f"Size: `{alert.get('size_sol', 0):.2f} SOL`\n"
                    f"TP1: `{alert.get('tp1_pct', 0)}%` | TP2: `{alert.get('tp2_pct', 0)}%`\n"
                    f"Stop: `{alert.get('stop_pct', 0)}%`"
                )
            elif alert_type == "trade_close":
                pnl = alert.get("pnl_pct", 0)
                emoji = "✅" if pnl >= 0 else "❌"
                text = (
                    f"{emoji} *Trade Closed*\n\n"
                    f"Token: `{alert.get('token', '?')}`\n"
                    f"P&L: `{pnl:+.1f}%`\n"
                    f"Reason: {alert.get('close_reason', 'N/A')}"
                )
            elif alert_type == "kill_switch":
                text = (
                    f"🛑 *Kill Switch Triggered — Level {alert.get('level', '?')}*\n\n"
                    f"Reason: {alert.get('reason', 'N/A')}\n"
                    f"Action: {alert.get('action', 'N/A')}"
                )
            else:
                text = f"📬 *Alert*\n{json.dumps(alert, indent=2)}"

            # Push to Telegram (thread-safe via asyncio)
            future = asyncio.run_coroutine_threadsafe(
                app.bot.send_message(
                    chat_id=YOUR_CHAT_ID,
                    text=text,
                    parse_mode="Markdown",
                    disable_web_page_preview=False,
                ),
                loop,
            )
            future.result(timeout=10)

        except Exception as e:
            log.error(f"Alert listener error: {e}")

# ─────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────

async def post_init(app):
    """Called after the app is initialized — clear any stale webhook."""
    await app.bot.delete_webhook(drop_pending_updates=True)
    log.info("Webhook cleared — polling mode active")

def main():
    log.info("Starting PixelFirm Telegram bot...")

    app = (
        ApplicationBuilder()
        .token(BOT_TOKEN)
        .post_init(post_init)
        .build()
    )

    # Register handlers
    app.add_handler(CommandHandler("start",  cmd_start))
    app.add_handler(CommandHandler("pause",  cmd_pause))
    app.add_handler(CommandHandler("resume", cmd_resume))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("mode",   cmd_mode))
    app.add_handler(CommandHandler("reset",  cmd_reset))
    app.add_handler(CommandHandler("help",   cmd_help))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, llm_chat))

    # Start alert listener in background thread
    alert_thread = threading.Thread(
        target=start_alert_listener, args=(app,), daemon=True
    )
    alert_thread.start()

    log.info("Bot is running. Polling for messages...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
