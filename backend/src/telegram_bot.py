import logging
import os
import asyncio
import json
import redis
from datetime import datetime, timezone
from typing import Dict, Optional, List
from functools import wraps
from telegram import Update, Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)
from telegram.constants import ChatAction, ParseMode

from src.agents.agent_0_commander import Agent0Commander

logger = logging.getLogger('telegram')

def auth_required(func):
    @wraps(func)
    async def wrapper(self, update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user = update.effective_user
        if not user:
            return
            
        uid = user.id
        if self.allowed_uids and uid not in self.allowed_uids:
            logger.warning(f"Blocked unauthorized access from {uid} ({user.username})")
            await update.message.reply_text("⛔ <b>Unauthorized.</b> Access restricted to PixelFirm operators.", parse_mode=ParseMode.HTML)
            return
        return await func(self, update, context, *args, **kwargs)
    return wrapper

logger = logging.getLogger('telegram')

# Onboarding States
ASK_NAME, ASK_BOT_NAME = range(2)

class TelegramBot:
    """Advanced Telegram Bot using Application framework with proactive alerts and auth guard."""
    
    def __init__(self, token: str, chat_id: str, db=None):
        self.token = token
        self.chat_id = chat_id
        self.db = db
        self.commander: Optional[Agent0Commander] = None
        
        # Load config
        self.allowed_uids = set(
            int(uid.strip()) 
            for uid in os.getenv("ALLOWED_USER_IDS", "").split(",") 
            if uid.strip()
        )
        self.redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
        self.redis = redis.from_url(self.redis_url, decode_responses=True)
        
        self.app = Application.builder().token(token).build()
        self._init_done = asyncio.Event()
        
        # Register handlers
        self._setup_handlers()
        logger.info(f'Telegram bot initialized. Auth guard: {len(self.allowed_uids)} IDs. Redis: {self.redis_url}')

    def _setup_handlers(self):
        """Register all command and message handlers."""
        # --- Onboarding Conversation ---
        onboarding = ConversationHandler(
            entry_points=[CommandHandler("start", self.cmd_start)],
            states={
                ASK_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.onboarding_got_name)],
                ASK_BOT_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.onboarding_got_bot_name)],
            },
            fallbacks=[CommandHandler("cancel", self.onboarding_cancel)],
            allow_reentry=True,
        )
        self.app.add_handler(onboarding)

        # --- Commands ---
        self.app.add_handler(CommandHandler("help", self.cmd_help))
        self.app.add_handler(CommandHandler("status", self.cmd_status))
        self.app.add_handler(CommandHandler("pnl", self.cmd_pnl))
        self.app.add_handler(CommandHandler("trades", self.cmd_trades))
        self.app.add_handler(CommandHandler("reset", self.cmd_reset))
        self.app.add_handler(CommandHandler("pause", self.cmd_pause))
        self.app.add_handler(CommandHandler("resume", self.cmd_resume))
        self.app.add_handler(CommandHandler("approve", self.cmd_approve))
        self.app.add_handler(CommandHandler("reject", self.cmd_reject))

        # --- Callbacks ---
        self.app.add_handler(CallbackQueryHandler(self.button_callback))

        # --- Free Text (AI Chat) ---
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))

    # --- Onboarding Handlers ---
    @auth_required
    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        user_id = str(update.effective_user.id)
        profile = await self.db.get_user_profile(user_id)

        if profile and profile.get("onboarded"):
            bot_name = profile.get("botName", "Assistant")
            user_name = profile.get("userName", "Trader")
            
            keyboard = [
                [
                    InlineKeyboardButton("▶️ Resume Agent", callback_data="action:resume"),
                    InlineKeyboardButton("⏸️ Pause Agent",  callback_data="action:pause"),
                ],
                [
                    InlineKeyboardButton("📊 System Status", callback_data="action:status"),
                    InlineKeyboardButton("💰 Performance",    callback_data="action:pnl"),
                ],
                [
                    InlineKeyboardButton("🔄 Reset Context",  callback_data="action:reset"),
                    InlineKeyboardButton("📋 Recent Trades",  callback_data="action:trades"),
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                f"👋 <b>Welcome back, {user_name}!</b>\n\n"
                f"I'm {bot_name}, your 🏛️ PixelFirm commander.\n"
                f"Use the buttons below for quick control or type normally to chat.",
                parse_mode=ParseMode.HTML,
                reply_markup=reply_markup
            )
            return ConversationHandler.END

        await update.message.reply_text(
            "👋 <b>Welcome to PixelFirm!</b>\n\n"
            "I'm your autonomous trading assistant. Let's get you set up.\n\n"
            "First — what should I call you?",
            parse_mode=ParseMode.HTML
        )
        return ASK_NAME

    @auth_required
    async def onboarding_got_name(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        user_name = update.message.text.strip()
        context.user_data["temp_user_name"] = user_name
        await update.message.reply_text(
            f"Nice to meet you, *{user_name}*! 🤝\n\n"
            f"Now — what do you want to name your trading bot?\n"
            f"_(e.g. Pixel, Max, Sigma, Apex...)_",
            parse_mode=ParseMode.MARKDOWN
        )
        return ASK_BOT_NAME

    @auth_required
    async def onboarding_got_bot_name(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        bot_name = update.message.text.strip()
        user_name = context.user_data.get("temp_user_name", "Trader")
        user_id = str(update.effective_user.id)

        profile = {
            "userId": user_id,
            "userName": user_name,
            "botName": bot_name,
            "onboarded": True,
            "createdAt": datetime.now(timezone.utc).isoformat(),
        }
        await self.db.save_user_profile(profile)

        await update.message.reply_text(
            f"🚀 All set, {user_name}!\n\n"
            f"Your bot is now *{bot_name}* and I'm fully online.\n\n"
            f"Use /help to see what I can do.",
            parse_mode=ParseMode.MARKDOWN
        )
        return ConversationHandler.END

    @auth_required
    async def onboarding_cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        await update.message.reply_text("Setup cancelled. Run /start when ready.")
        return ConversationHandler.END

    # --- AI Chat / Command Routing ---
    @auth_required
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = str(update.effective_user.id)
        profile = await self.db.get_user_profile(user_id)

        if not profile or not profile.get("onboarded"):
            await update.message.reply_text("Please run /start first to set up your profile.")
            return

        # Show typing
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
        
        # Process via Agent 0 (Commander)
        reply = await self.commander.process_telegram_command(update.message.text, user_id, profile)
        
        await update.message.reply_text(reply, parse_mode=ParseMode.HTML)

    # --- Callbacks ---
    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle button clicks from the inline keyboard."""
        query = update.callback_query
        await query.answer()
        
        user_id = str(query.from_user.id)
        if self.allowed_uids and int(user_id) not in self.allowed_uids:
            await query.edit_message_text("⛔ Unauthorized.")
            return

        data = query.data
        profile = await self.db.get_user_profile(user_id)
        
        if data == "action:status":
            reply = await self.commander._get_status_report(user_id)
        elif data == "action:pnl":
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            stats = await self.db.get_daily_portfolio_state(user_id, today)
            realized = stats.get("realized_pnl_usd", 0.0)
            reply = (
                f"💰 <b>PnL Summary — {today}</b>\n\n"
                f"Realized PnL: <b>${realized:+.2f}</b>\n"
                f"Trades Today: {stats.get('trades_executed', 0)}\n\n"
                f"<i>Live data from Agent-7</i>"
            )
        elif data == "action:pause":
            reply = await self.commander.execute_pause()
        elif data == "action:resume":
            reply = await self.commander.execute_resume(user_id)
        elif data == "action:reset":
            await self.db.clear_chat_history(user_id)
            reply = "🔄 Chat history cleared. Fresh start!"
        elif data == "action:trades":
            positions = await self.db.get_all_positions(user_id)
            closed = positions.get("closed", [])[-5:]
            if not closed:
                reply = "No recent trades found."
            else:
                reply = "📋 <b>Recent Trades:</b>\n\n"
                for t in closed:
                    pnl = t.get("pnl_usd", 0.0)
                    reply += f"{'🟢' if pnl > 0 else '🔴'} {t.get('token')} | PnL: ${pnl:.2f}\n"
        else:
            reply = "Unknown command."

        await query.message.reply_text(reply, parse_mode=ParseMode.HTML)

    # --- Slash Commands ---
    @auth_required
    async def cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(
            "📈 <b>PixelFirm Commands</b>\n\n"
            "/status - System snapshot\n"
            "/pnl - Today's performance\n"
            "/trades - Recent activity\n"
            "/pause - Stop all trading\n"
            "/resume - Resume system\n"
            "/reset - Clear chat history\n\n"
            "<i>Or just speak naturally!</i>",
            parse_mode=ParseMode.HTML
        )

    @auth_required
    async def cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = str(update.effective_user.id)
        reply = await self.commander._get_status_report(user_id)
        await update.message.reply_text(reply, parse_mode=ParseMode.HTML)

    @auth_required
    async def cmd_pnl(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = str(update.effective_user.id)
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        stats = await self.db.get_daily_portfolio_state(user_id, today)
        
        realized = stats.get("realized_pnl_usd", 0.0)
        unrealized = 0.0 # Calculate if positions available
        
        msg = (
            f"💰 <b>PnL Summary — {today}</b>\n\n"
            f"Realized PnL: <b>${realized:+.2f}</b>\n"
            f"Trades Today: {stats.get('trades_executed', 0)}\n\n"
            f"<i>Live data from Agent-7</i>"
        )
        await update.message.reply_text(msg, parse_mode=ParseMode.HTML)

    @auth_required
    async def cmd_trades(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = str(update.effective_user.id)
        positions = await self.db.get_all_positions(user_id)
        closed = positions.get("closed", [])[-5:]
        
        if not closed:
            await update.message.reply_text("No recent trades found.")
            return

        msg = "📋 <b>Recent Trades:</b>\n\n"
        for t in closed:
            pnl = t.get("pnl_usd", 0.0)
            msg += f"{'🟢' if pnl > 0 else '🔴'} {t.get('token')} | PnL: ${pnl:.2f}\n"
            
        await update.message.reply_text(msg, parse_mode=ParseMode.HTML)

    @auth_required
    async def cmd_reset(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = str(update.effective_user.id)
        await self.db.clear_chat_history(user_id)
        await update.message.reply_text("🔄 Chat history cleared. Fresh start!")

    @auth_required
    async def cmd_pause(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        reply = await self.commander.execute_pause()
        await update.message.reply_text(reply, parse_mode=ParseMode.HTML)

    @auth_required
    async def cmd_resume(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = str(update.effective_user.id)
        reply = await self.commander.execute_resume(user_id)
        await update.message.reply_text(reply, parse_mode=ParseMode.HTML)

    @auth_required
    async def cmd_approve(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not context.args:
            await update.message.reply_text("Usage: /approve <id>")
            return
        user_id = str(update.effective_user.id)
        reply = await self.commander.resolve_approval(context.args[0], approved=True, user_id=user_id)
        await update.message.reply_text(reply, parse_mode=ParseMode.HTML)

    @auth_required
    async def cmd_reject(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not context.args:
            await update.message.reply_text("Usage: /reject <id>")
            return
        user_id = str(update.effective_user.id)
        reply = await self.commander.resolve_approval(context.args[0], approved=False, user_id=user_id)
        await update.message.reply_text(reply, parse_mode=ParseMode.HTML)

    # --- Push Methods (for Agents) ---
    async def send_status_update(self, status_dict: dict) -> bool:
        """Broadcast a status update to all onboarded users."""
        await self._init_done.wait()
        message = status_dict.get("message", "System update received.")
        try:
            # Fetch all onboarded users from Convex
            # (Keeping your original Convex logic here)
            result = await self.db.convex.query("functions:getUserProfiles", {"onboardedOnly": True})
            profiles = []
            if isinstance(result, dict) and result.get("success"):
                profiles = result.get("data", [])
            elif isinstance(result, list):
                profiles = result
            
            sent_count = 0
            # Also send to allowed_uids if profiles empty
            uids_to_notify = {p["userId"] for p in profiles}
            if self.allowed_uids:
                uids_to_notify.update(str(uid) for uid in self.allowed_uids)
            
            for uid in uids_to_notify:
                try:
                    await self.app.bot.send_message(
                        chat_id=uid,
                        text=message,
                        parse_mode=ParseMode.HTML
                    )
                    sent_count += 1
                except Exception as e:
                    logger.warning(f"Failed to send message to {uid}: {e}")
            
            return sent_count > 0
        except Exception as e:
            logger.error(f'Error broadcasting status update: {e}')
            return False

    async def send_kill_switch_alert(self, tier: str, status_dict: dict) -> bool:
        """Send emergency kill switch alert."""
        reason = status_dict.get("message", "No reason provided.")
        message = f"🚨 <b>KILL SWITCH TRIGGERED: TIER {tier}</b> 🚨\n\nReason: {reason}"
        return await self.send_status_update({"message": message})

    async def send_signal_alert(self, signal_dict: dict) -> bool:
        """Legacy manual signal push."""
        await self._init_done.wait()
        message = self._format_signal(signal_dict)
        return await self.send_status_update({"message": message})
    def _format_signal(self, signal: dict) -> str:
        token = signal.get('token_name', 'Unknown')
        symbol = signal.get('token_symbol', 'TOKEN')
        addr = signal.get('token_address', 'N/A')
        price = signal.get('entry_price', 0)
        market_cap = signal.get('market_cap', 'N/A')
        
        return f"""🚀 <b>SIGNAL DETECTED: {symbol}</b>
<b>Token:</b> {token}
<b>Price:</b> ${price:.8f}
<b>MCap:</b> {market_cap}
<b>Reason:</b> {signal.get('reason', 'N/A')}

<code>{addr}</code>"""

    async def _alert_listener(self):
        """Background task to listen for proactive alerts via Redis Pub/Sub."""
        logger.info(f"📡 Redis Alert Listener attempting connection to {self.redis_url}")
        
        while True:
            pubsub = None
            try:
                pubsub = self.redis.pubsub()
                await asyncio.to_thread(pubsub.subscribe, "pixelfirm:alerts")
                logger.info("✅ Redis Alert Listener connected to 'pixelfirm:alerts'")
                
                while True:
                    try:
                        message = await asyncio.to_thread(pubsub.get_message, ignore_subscribe_messages=True, timeout=1.0)
                        if message and message['type'] == 'message':
                            data = json.loads(message['data'])
                            await self._process_alert(data)
                        await asyncio.sleep(0.1)
                    except (redis.ConnectionError, redis.TimeoutError):
                        logger.warning("📡 Redis connection lost. Retrying...")
                        break
                    except Exception as e:
                        logger.error(f"Error processing alert message: {e}")
                        await asyncio.sleep(1)
            except redis.ConnectionError:
                # Silently wait if Redis isn't running, to avoid spamming logs too much
                await asyncio.sleep(10)
            except Exception as e:
                logger.error(f"📡 Redis listener error: {e}")
                await asyncio.sleep(10)
            finally:
                if pubsub:
                    try:
                        await asyncio.to_thread(pubsub.close)
                    except:
                        pass

    async def _process_alert(self, alert: dict):
        """Route alerts to the correct formatter and send."""
        alert_type = alert.get("type", "status")
        msg = alert.get("message", "")
        
        if alert_type == "signal":
            formatted_msg = self._format_signal(alert.get("data", {}))
        elif alert_type == "trade":
            data = alert.get("data", {})
            action = data.get("action", "UPDATE")
            pnl = data.get("pnl_usd", 0.0)
            formatted_msg = f"⚡ <b>TRADE {action}: {data.get('token')}</b>\nPNL: ${pnl:+.2f}\n{msg}"
        elif alert_type == "kill_switch":
            formatted_msg = f"🚨 <b>KILL SWITCH TRIGGERED: {alert.get('tier', 'ALL')}</b> 🚨\n\n{msg}"
        else:
            formatted_msg = f"ℹ️ <b>System Alert</b>\n{msg}"

        # Send to all allowed IDs or master chat_id
        await self.send_status_update({"message": formatted_msg})

    async def run(self):
        """Start the bot in polling mode."""
        logger.info("Starting Telegram bot polling architecture...")
        try:
            await self.app.initialize()
            await self.app.start()
            self._init_done.set()
            
            # Start Background Alert Listener
            asyncio.create_task(self._alert_listener())
            
            # Broadcast system online message
            await self.send_status_update({"message": "🟢 <b>Trading Bot System Online</b>\nAll agents are at their desks and monitoring the Solana tape."})
            
            await self.app.updater.start_polling(drop_pending_updates=True)
            logger.info("✅ Telegram bot ACTIVE with Redis Proactive Alerts.")
            
            while True:
                await asyncio.sleep(3600)
            
        except Exception as e:
            logger.error(f"Telegram bot failed to start: {e}")
