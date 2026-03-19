import logging
import os
import asyncio
from datetime import datetime, timezone
from typing import Dict, Optional, List

from telegram import Update, Bot
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)
from telegram.constants import ChatAction, ParseMode

from src.agents.agent_0_commander import Agent0Commander

logger = logging.getLogger('telegram')

# Onboarding States
ASK_NAME, ASK_BOT_NAME = range(2)

class TelegramBot:
    """Advanced Telegram Bot using Application framework with personalized AI assistant."""
    
    def __init__(self, token: str, chat_id: str, db=None):
        self.token = token
        self.chat_id = chat_id
        self.db = db
        self.commander: Optional[Agent0Commander] = None
        self.app = Application.builder().token(token).build()
        self._init_done = asyncio.Event()
        
        # Register handlers
        self._setup_handlers()
        logger.info(f'Telegram bot application initialized for chat {chat_id}')

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

        # --- Free Text (AI Chat) ---
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))

    # --- Onboarding Handlers ---
    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        user_id = str(update.effective_user.id)
        profile = await self.db.get_user_profile(user_id)

        if profile and profile.get("onboarded"):
            bot_name = profile.get("botName", "Assistant")
            user_name = profile.get("userName", "Trader")
            await update.message.reply_text(
                f"Welcome back, {user_name}! I'm {bot_name} and I'm online.\n\n"
                f"PixelFirm is monitoring the markets. Type anything to chat."
            )
            return ConversationHandler.END

        await update.message.reply_text(
            "👋 Welcome to PixelFirm!\n\n"
            "I'm your autonomous trading assistant. Let's get you set up.\n\n"
            "First — what should I call you?",
            parse_mode=ParseMode.MARKDOWN
        )
        return ASK_NAME

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

    async def onboarding_cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        await update.message.reply_text("Setup cancelled. Run /start when ready.")
        return ConversationHandler.END

    # --- AI Chat / Command Routing ---
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

    # --- Slash Commands ---
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

    async def cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = str(update.effective_user.id)
        reply = await self.commander._get_status_report(user_id)
        await update.message.reply_text(reply, parse_mode=ParseMode.HTML)

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

    async def cmd_reset(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = str(update.effective_user.id)
        await self.db.clear_chat_history(user_id)
        await update.message.reply_text("🔄 Chat history cleared. Fresh start!")

    async def cmd_pause(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        reply = await self.commander.execute_pause()
        await update.message.reply_text(reply, parse_mode=ParseMode.HTML)

    async def cmd_resume(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = str(update.effective_user.id)
        reply = await self.commander.execute_resume(user_id)
        await update.message.reply_text(reply, parse_mode=ParseMode.HTML)

    async def cmd_approve(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not context.args:
            await update.message.reply_text("Usage: /approve <id>")
            return
        user_id = str(update.effective_user.id)
        reply = await self.commander.resolve_approval(context.args[0], approved=True, user_id=user_id)
        await update.message.reply_text(reply, parse_mode=ParseMode.HTML)

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
            result = await self.db.convex.query("functions:getUserProfiles", {"onboardedOnly": True})
            profiles = []
            if isinstance(result, dict) and result.get("success"):
                profiles = result.get("data", [])
            elif isinstance(result, list):
                profiles = result # Fallback for flat response
            
            sent_count = 0
            for profile in profiles:
                try:
                    await self.app.bot.send_message(
                        chat_id=profile["userId"],
                        text=message,
                        parse_mode=ParseMode.HTML
                    )
                    sent_count += 1
                except Exception as e:
                    logger.warning(f"Failed to send status to {profile['userId']}: {e}")
            
            # Also send to master chat_id if set
            if self.chat_id:
                await self.app.bot.send_message(chat_id=self.chat_id, text=message, parse_mode=ParseMode.HTML)
            
            return sent_count > 0
        except Exception as e:
            logger.error(f'Error broadcasting status update: {e}')
            return False

    async def send_kill_switch_alert(self, tier: str, status_dict: dict) -> bool:
        """Send emergency kill switch alert."""
        reason = status_dict.get("message", "No reason provided.")
        message = f"🚨 <b>KILL SWITCH TRIGGERED: TIER {tier}</b> 🚨\n\nReason: {reason}"
        return await self.send_status_update({"message": message})

    def poll_commands(self, user_id: str):
        """Legacy compatibility method. Commands are now handled via callbacks."""
        pass

    async def send_signal_alert(self, signal_dict: dict) -> bool:
        """Send signal alert to the configured master chat_id."""
        await self._init_done.wait()
        message = self._format_signal(signal_dict)
        try:
            await self.app.bot.send_message(chat_id=self.chat_id, text=message, parse_mode=ParseMode.HTML)
            return True
        except Exception as e:
            logger.error(f'Error sending alert: {e}')
            return False

    def _format_signal(self, signal: dict) -> str:
        token = signal.get('token_name', 'Unknown')
        addr = signal.get('token_address', 'N/A')
        return f"""🚀 <b>SIGNAL DETECTED</b>
Token: {token}
Price: ${signal.get('entry_price', 0):.8f}
Reason: {signal.get('reason', 'N/A')}

<code>{addr}</code>"""

    async def run(self):
        """Start the bot in polling mode."""
        logger.info("Starting Telegram bot polling...")
        try:
            await self.app.initialize()
            await self.app.start()
            self._init_done.set()
            
            # Broadcast system online message
            await self.send_status_update({"message": "🟢 <b>Trading Bot System Online</b>\nAll agents are at their desks and monitoring the Solana tape."})
            
            await self.app.updater.start_polling(drop_pending_updates=True)
            
        except Exception as e:
            logger.error(f"Telegram bot failed to start: {e}")
