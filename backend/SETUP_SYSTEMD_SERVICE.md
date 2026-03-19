# Setup Systemd Service for Trading Bot
**For 24/7 automated operation with auto-restart**

---

## 🎯 What This Does

- Runs the trading bot as a background service
- Auto-restarts if it crashes
- Logs all output to systemd journal
- Limits resources (512MB RAM, 50% CPU)
- Loads environment variables automatically
- Survives system reboot

---

## 📋 Installation Steps

### Step 1: Copy Service File to systemd
```bash
# Need sudo for this
sudo cp /home/node/.openclaw/workspace/projects/crypto-trading-system/researcher-bot.service /etc/systemd/system/

# Make sure it's readable
sudo chmod 644 /etc/systemd/system/researcher-bot.service
```

### Step 2: Reload Systemd Daemon
```bash
sudo systemctl daemon-reload
```

### Step 3: Enable Service (Auto-start on boot)
```bash
sudo systemctl enable researcher-bot
```

### Step 4: Start the Service
```bash
sudo systemctl start researcher-bot
```

### Step 5: Verify It's Running
```bash
sudo systemctl status researcher-bot
```

Expected output:
```
● researcher-bot.service - Solana Memecoin Autonomous Trading Bot
     Loaded: loaded (/etc/systemd/system/researcher-bot.service; enabled)
     Active: active (running) since ...
```

---

## 📊 Monitor Logs

### View Recent Logs
```bash
journalctl -u researcher-bot -n 50
```

### Follow Logs in Real-Time (Like `tail -f`)
```bash
journalctl -u researcher-bot -f
```

### View Last Hour of Logs
```bash
journalctl -u researcher-bot --since "1 hour ago"
```

### View Errors Only
```bash
journalctl -u researcher-bot -p err
```

### View JSON-formatted Logs
```bash
journalctl -u researcher-bot -o json | jq
```

---

## 🎮 Control Commands

### Start Service
```bash
sudo systemctl start researcher-bot
```

### Stop Service
```bash
sudo systemctl stop researcher-bot
```

### Restart Service
```bash
sudo systemctl restart researcher-bot
```

### Check Status
```bash
sudo systemctl status researcher-bot
```

### View Last 100 Lines of Logs
```bash
journalctl -u researcher-bot -n 100
```

### Check if Service is Enabled (Auto-start)
```bash
sudo systemctl is-enabled researcher-bot
```

---

## 🔍 Troubleshooting

### Service Won't Start
```bash
# Check what the error is
journalctl -u researcher-bot -n 50
```

### Permission Denied Errors
```bash
# Check file permissions
ls -la /home/node/.openclaw/workspace/projects/crypto-trading-system/
ls -la /home/node/.openclaw/workspace/projects/crypto-trading-system/secrets.env

# Make sure node user can read secrets
sudo chown node:node /home/node/.openclaw/workspace/projects/crypto-trading-system/secrets.env
sudo chmod 600 /home/node/.openclaw/workspace/projects/crypto-trading-system/secrets.env
```

### Service Crashes Repeatedly
```bash
# Check logs for errors
journalctl -u researcher-bot -n 100 -p err

# Increase restart delay (edit service file)
# Change RestartSec=10 to RestartSec=30
sudo nano /etc/systemd/system/researcher-bot.service
sudo systemctl daemon-reload
```

### High Memory Usage
```bash
# Check memory stats
journalctl -u researcher-bot --no-pager | grep Memory

# Edit service file to increase limit
sudo nano /etc/systemd/system/researcher-bot.service
# Change MemoryMax=512M to MemoryMax=1G
sudo systemctl daemon-reload
sudo systemctl restart researcher-bot
```

---

## 📈 Resource Monitoring

### CPU & Memory Usage
```bash
ps aux | grep researcher-bot

# Or use systemctl
systemctl status researcher-bot
```

### Disk Usage by Service
```bash
du -sh /home/node/.openclaw/workspace/projects/crypto-trading-system/data/
```

---

## 🔄 Auto-Restart Behavior

Current configuration:
- **Restart:** Always restart on failure
- **RestartSec:** Wait 10 seconds before restarting
- **StartLimitBurst:** Max 3 restarts per minute (prevents restart loops)

If service crashes more than 3 times in 60 seconds, it will stop trying.

To reset:
```bash
sudo systemctl reset-failed researcher-bot
sudo systemctl start researcher-bot
```

---

## 📝 Log Examples

### Successful Startup
```
researcher-bot[1234]: [INFO] Initializing Trading Bot...
researcher-bot[1234]: [INFO] ✅ Config loaded
researcher-bot[1234]: [INFO] ✅ Database initialized
researcher-bot[1234]: [INFO] ✅ Telegram bot initialized
researcher-bot[1234]: [INFO] Bot initialized successfully
researcher-bot[1234]: [INFO] STARTING TRADING BOT
```

### Running Normally
```
researcher-bot[1234]: [INFO] 🔬 RESEARCHER SCAN STARTING
researcher-bot[1234]: [INFO] Fetched 8 fresh Solana pairs
researcher-bot[1234]: [INFO] [AGENT_2] Processing 8 tokens...
researcher-bot[1234]: [INFO] ✓ Scan Complete
```

### Error (Will Auto-Restart)
```
researcher-bot[1234]: [ERROR] ❌ Scan failed: Network timeout
researcher-bot[1234]: [ERROR] Fatal error: Connection refused
systemd[1]: researcher-bot.service: Main process exited, code=1/FAILURE
systemd[1]: researcher-bot.service: Scheduled restart job, restart counter: 1/3
systemd[1]: researcher-bot.service: Restart job queued for execution
```

---

## 💾 Backup & Restore

### Backup Service Configuration
```bash
sudo cp /etc/systemd/system/researcher-bot.service ~/researcher-bot.service.backup
```

### Restore Service Configuration
```bash
sudo cp ~/researcher-bot.service.backup /etc/systemd/system/researcher-bot.service
sudo systemctl daemon-reload
```

---

## 🚀 Complete Setup Script

If you have sudo access, run this all-in-one:

```bash
#!/bin/bash

PROJECT_DIR="/home/node/.openclaw/workspace/projects/crypto-trading-system"
SERVICE_FILE="$PROJECT_DIR/researcher-bot.service"
SYSTEMD_PATH="/etc/systemd/system/researcher-bot.service"

echo "🚀 Setting up systemd service for Trading Bot..."

# Copy service file
sudo cp "$SERVICE_FILE" "$SYSTEMD_PATH"
echo "✅ Service file copied"

# Set permissions
sudo chmod 644 "$SYSTEMD_PATH"
echo "✅ Permissions set"

# Reload daemon
sudo systemctl daemon-reload
echo "✅ Systemd daemon reloaded"

# Enable service
sudo systemctl enable researcher-bot
echo "✅ Service enabled (auto-start on boot)"

# Start service
sudo systemctl start researcher-bot
echo "✅ Service started"

# Show status
sudo systemctl status researcher-bot

echo ""
echo "✨ Service setup complete!"
echo ""
echo "Monitor logs with:"
echo "  journalctl -u researcher-bot -f"
echo ""
echo "Stop service with:"
echo "  sudo systemctl stop researcher-bot"
```

Save as `setup-systemd.sh` and run:
```bash
chmod +x setup-systemd.sh
./setup-systemd.sh
```

---

## ✅ Verification Checklist

After setup:

- [ ] Service file copied to `/etc/systemd/system/`
- [ ] `systemctl status researcher-bot` shows "active (running)"
- [ ] `journalctl -u researcher-bot -f` shows logs updating
- [ ] Service stays running for >5 minutes without crashing
- [ ] Logs show periodic scans (every 15 minutes)
- [ ] Database file is being updated: `ls -la data/database.db`
- [ ] Telegram alerts (or mock messages) appearing

---

**Status:** Ready for deployment ✅
