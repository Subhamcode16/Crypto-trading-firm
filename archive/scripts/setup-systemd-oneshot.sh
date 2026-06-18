#!/bin/bash
# One-shot setup script for systemd service
# Run this with: bash setup-systemd-oneshot.sh

set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_FILE="$PROJECT_DIR/researcher-bot.service"
SYSTEMD_PATH="/etc/systemd/system/researcher-bot.service"

echo "╔════════════════════════════════════════════════════════════╗"
echo "║  Setting up Systemd Service for Trading Bot               ║"
echo "║  Project: $PROJECT_DIR"
echo "╚════════════════════════════════════════════════════════════╝"

# Check if running with sudo
if [ "$EUID" -ne 0 ]; then 
    echo "❌ This script requires sudo. Run with:"
    echo "   sudo bash setup-systemd-oneshot.sh"
    exit 1
fi

echo ""
echo "📋 Step 1: Copying service file..."
cp "$SERVICE_FILE" "$SYSTEMD_PATH"
chmod 644 "$SYSTEMD_PATH"
echo "✅ Service file installed to $SYSTEMD_PATH"

echo ""
echo "🔄 Step 2: Reloading systemd daemon..."
systemctl daemon-reload
echo "✅ Daemon reloaded"

echo ""
echo "⚙️  Step 3: Enabling service (auto-start on boot)..."
systemctl enable researcher-bot
echo "✅ Service enabled"

echo ""
echo "🚀 Step 4: Starting service..."
systemctl start researcher-bot
echo "✅ Service started"

echo ""
echo "📊 Step 5: Checking status..."
systemctl status researcher-bot --no-pager
echo ""

echo "╔════════════════════════════════════════════════════════════╗"
echo "║  ✨ Setup Complete!                                        ║"
echo "╚════════════════════════════════════════════════════════════╝"

echo ""
echo "📝 Useful Commands:"
echo "  View status:        sudo systemctl status researcher-bot"
echo "  View logs:          journalctl -u researcher-bot -f"
echo "  Stop service:       sudo systemctl stop researcher-bot"
echo "  Restart service:    sudo systemctl restart researcher-bot"
echo "  View last 50 logs:  journalctl -u researcher-bot -n 50"
echo ""
echo "📚 Full documentation: SETUP_SYSTEMD_SERVICE.md"
echo ""
