#!/bin/bash
# Setup environment for mock testing (without real package dependencies)

echo "🚀 Setting up mock testing environment..."

# Create stubs directory (already done, but ensure it exists)
mkdir -p stubs

# Load minimal environment variables from secrets.env
export $(cat secrets.env | xargs)
export $(cat .env | xargs)

# Verify
echo "✅ Environment variables loaded:"
echo "   TELEGRAM_BOT_TOKEN: ${TELEGRAM_BOT_TOKEN:0:20}..."
echo "   TELEGRAM_CHAT_ID: $TELEGRAM_CHAT_ID"
echo "   ANTHROPIC_API_KEY: ${ANTHROPIC_API_KEY:0:20}..."

# Run the bot
echo ""
echo "🎯 Starting bot in MOCK MODE (without real package dependencies)"
echo "   Telegram messages will print to console instead"
echo "   Scheduling will not repeat (test mode)"
echo ""

python3 src/main.py
