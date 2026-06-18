# Systemd Service Quick Start
**Get the trading bot running 24/7 with auto-restart**

---

## 🚀 One-Command Setup (Recommended)

```bash
cd /home/node/.openclaw/workspace/projects/crypto-trading-system
sudo bash setup-systemd-oneshot.sh
```

That's it! Service will start immediately and auto-restart on reboot.

---

## 📊 Check Status

```bash
# View service status
sudo systemctl status researcher-bot

# View live logs
journalctl -u researcher-bot -f
```

Expected output:
```
● researcher-bot.service - Solana Memecoin Autonomous Trading Bot
     Loaded: loaded (/etc/systemd/system/researcher-bot.service; enabled)
     Active: active (running) since 2026-03-06 21:35:00 UTC
     
Mar 06 21:35:00 server systemd[1]: Started Solana Memecoin Autonomous Trading Bot.
Mar 06 21:35:05 server researcher-bot[1234]: [INFO] Bot initialized successfully
Mar 06 21:35:05 server researcher-bot[1234]: [INFO] STARTING TRADING BOT
```

---

## 🎮 Common Commands

| Command | What It Does |
|---------|--------------|
| `sudo systemctl start researcher-bot` | Start the service |
| `sudo systemctl stop researcher-bot` | Stop the service |
| `sudo systemctl restart researcher-bot` | Restart the service |
| `sudo systemctl status researcher-bot` | Show current status |
| `journalctl -u researcher-bot -f` | Live log stream |
| `journalctl -u researcher-bot -n 50` | Last 50 log lines |
| `sudo systemctl enable researcher-bot` | Auto-start on boot |
| `sudo systemctl disable researcher-bot` | Disable auto-start |

---

## 📈 Monitor Performance

### View Last 100 Lines
```bash
journalctl -u researcher-bot -n 100
```

### Watch Scans in Real-Time
```bash
journalctl -u researcher-bot -f | grep "RESEARCHER SCAN\|Fetched\|CLEARED\|KILLED"
```

### Check CPU/Memory
```bash
ps aux | grep researcher-bot
```

### View Errors Only
```bash
journalctl -u researcher-bot -p err
```

---

## 🆘 Troubleshooting

### Service Won't Start
```bash
# Check error messages
journalctl -u researcher-bot -n 50 -p err
```

### Service Keeps Crashing
```bash
# View detailed logs
journalctl -u researcher-bot -n 100

# Reset and restart
sudo systemctl reset-failed researcher-bot
sudo systemctl restart researcher-bot
```

### Can't See Logs
```bash
# Make sure you have permission
journalctl -u researcher-bot --no-pager | tail -20
```

---

## 📝 Service Configuration

The service file is at:
```
/etc/systemd/system/researcher-bot.service
```

Key settings:
- **Restart:** Always (if it crashes, auto-restart)
- **RestartSec:** 10 seconds (wait before restarting)
- **Memory Limit:** 512MB
- **CPU Limit:** 50%
- **Auto-start:** Yes (boots with system)

To edit:
```bash
sudo nano /etc/systemd/system/researcher-bot.service
sudo systemctl daemon-reload
sudo systemctl restart researcher-bot
```

---

## ✅ Verify Setup

After running setup, verify with:

```bash
# 1. Check service is enabled
sudo systemctl is-enabled researcher-bot
# Should output: enabled

# 2. Check service is running
sudo systemctl is-active researcher-bot
# Should output: active

# 3. View status
sudo systemctl status researcher-bot
# Should show: active (running)

# 4. Check logs
journalctl -u researcher-bot -n 20
# Should show initialization messages
```

---

## 🔄 What Happens When It Restarts

**On System Boot:**
- Service auto-starts (if enabled)
- Loads env variables from secrets.env
- Initializes all components (database, APIs, etc.)
- Begins scanning for tokens every 15 minutes

**On Crash:**
- Service detects exit
- Waits 10 seconds
- Automatically restarts
- Maximum 3 restarts per minute (prevents loops)

**On Manual Restart:**
```bash
sudo systemctl restart researcher-bot
```

---

## 📊 Example Log Output (What to Expect)

### Startup
```
researcher-bot[1234]: [INFO] Initializing Trading Bot...
researcher-bot[1234]: [INFO] ✅ Config loaded
researcher-bot[1234]: [INFO] ✅ Database initialized
researcher-bot[1234]: [INFO] ✅ Telegram bot initialized
researcher-bot[1234]: [INFO] Bot initialized successfully
researcher-bot[1234]: [INFO] STARTING TRADING BOT
researcher-bot[1234]: [INFO] Added researcher job: every 15 minutes
```

### Running (Every 15 Minutes)
```
researcher-bot[1234]: [INFO] 🔬 RESEARCHER SCAN STARTING
researcher-bot[1234]: [INFO] Fetched 8 fresh Solana pairs
researcher-bot[1234]: [INFO] [AGENT_2] Processed 8 tokens: 2 cleared, 6 killed
researcher-bot[1234]: [INFO] Scan Complete: 1 signal sent to Telegram
```

### Error (Auto-Restarts)
```
researcher-bot[1234]: [ERROR] ❌ Network timeout
systemd[1]: researcher-bot.service: Main process exited, code=1/FAILURE
systemd[1]: researcher-bot.service: Scheduled restart job, restart counter: 1/3
systemd[1]: researcher-bot.service: Restarted due to: unit-restart-triggered
researcher-bot[5678]: [INFO] Initializing Trading Bot...
researcher-bot[5678]: [INFO] ✅ Bot recovered from crash
```

---

## 🔐 Security Notes

- Service runs as `node` user (non-root)
- Secrets file is protected (600 permissions)
- Temporary files isolated (PrivateTmp=yes)
- Home directory protected
- System directories read-only

---

## 📞 Support

For detailed documentation:
```bash
# Read full setup guide
cat SETUP_SYSTEMD_SERVICE.md

# View service file
cat /etc/systemd/system/researcher-bot.service

# View project structure
ls -la
```

---

**Ready to deploy?** Run the one-command setup above! 🚀
