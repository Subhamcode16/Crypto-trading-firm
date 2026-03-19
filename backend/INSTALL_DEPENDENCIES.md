# Installing Dependencies

## Problem
```
ModuleNotFoundError: No module named 'telegram'
```

The required Python packages are not installed. This environment has restricted permissions.

---

## Solution Options

### Option A: Install with pip (Local User)
**Recommended if you have your own machine**

```bash
cd /home/node/.openclaw/workspace/projects/crypto-trading-system

# Install all dependencies locally (doesn't require sudo)
pip3 install --user -r requirements.txt

# Verify installation
python3 -c "import telegram; print('✅ telegram installed')"

# Start bot
python3 src/main.py
```

**Packages needed:**
- `python-telegram-bot==20.3` (Telegram bot API)
- `apscheduler==3.10.4` (Job scheduling)
- `requests==2.31.0` (HTTP requests)
- `python-dotenv==1.0.0` (Environment variables)
- `base58==2.1.1` (Solana address encoding)
- `anthropic==0.7.1` (Claude API)

### Option B: Use Docker (If Available)
```bash
docker run -v /path/to/project:/app python:3.11 bash -c "cd /app && pip install -r requirements.txt && python3 src/main.py"
```

### Option C: Virtual Environment (Isolated)
```bash
# Create virtual environment
python3 -m venv venv

# Activate it
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run bot
python3 src/main.py
```

### Option D: Use Conda (If Installed)
```bash
conda create -n solana-bot python=3.11
conda activate solana-bot
pip install -r requirements.txt
python3 src/main.py
```

---

## Cloud Deployment (AWS/GCP/Azure)

If running on cloud VM:

```bash
# SSH into machine
ssh -i your-key.pem ubuntu@your-instance-ip

# Update system (requires sudo)
sudo apt-get update
sudo apt-get install -y python3-pip python3-venv

# Install Python packages
pip3 install -r requirements.txt

# Run bot as background service
nohup python3 src/main.py > researcher_bot.log 2>&1 &
```

Or use **systemd** for production (see `src/main.py` for config):

```bash
sudo systemctl start researcher-bot
sudo journalctl -u researcher-bot -f  # View logs
```

---

## If Installation Blocked

If you're in a restricted environment where you can't install packages:

### Workaround: Mock Testing Mode
See `MOCK_TESTING_MODE.md` for how to test the pipeline without external dependencies.

---

## Troubleshooting

### Error: `Permission denied`
→ Try `pip install --user` instead of `sudo pip install`

### Error: `No module named 'pip'`
→ Use `python3 -m pip` instead of `pip3`

### Error: `ModuleNotFoundError` after install
→ Make sure virtual environment is activated (if using one)

### Some packages fail to install
→ Try installing one at a time:
```bash
pip install python-telegram-bot
pip install apscheduler
pip install requests
# etc.
```

---

## Verify Installation

```bash
python3 -c "
import telegram
import apscheduler
import requests
import dotenv
import base58
import anthropic
print('✅ All dependencies installed successfully!')
"
```

---

## Next Steps

Once dependencies are installed:

```bash
# 1. Verify APIs
python3 check_apis_simple.py

# 2. Add Birdeye key (optional but recommended)
echo "BIRDEYE_API_KEY=<your-key>" >> secrets.env

# 3. Start bot
python3 src/main.py

# 4. Monitor logs
tail -f data/logs/researcher.log
```

---

**Status:** System ready to run once dependencies installed ✅
