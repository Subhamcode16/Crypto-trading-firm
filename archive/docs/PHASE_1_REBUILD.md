# PHASE 1 REBUILD - FOUNDATION

**Objective:** Rebuild the project foundation from scratch with clean architecture, proper config management, and Telegram integration.

**Timeline:** 1 week (5-7 days of focused work)  
**Scope:** Project setup, database schema, config system, Telegram bot, scheduler framework  
**Output:** Ready-to-extend codebase for Phase 2

---

## PROJECT STRUCTURE

```
crypto-trading-system/
├── config/
│   ├── config.yaml (environment config)
│   └── secrets.env (API keys - GITIGNORE)
├── src/
│   ├── __init__.py
│   ├── main.py (entry point)
│   ├── config.py (config loader)
│   ├── database.py (SQLite setup)
│   ├── telegram_bot.py (Telegram interface)
│   ├── scheduler.py (APScheduler setup)
│   ├── logger.py (logging setup)
│   └── utils.py (helpers)
├── data/
│   ├── database.db (SQLite - generated)
│   └── logs/ (daily logs)
├── tests/
│   ├── __init__.py
│   ├── test_config.py
│   └── test_database.py
├── requirements.txt
├── .gitignore
├── README.md
└── DEPLOY.md (AWS setup guide)
```

---

## TASK BREAKDOWN

### TASK 1: Project Setup & Dependencies
**Objective:** Initialize Python project with all required packages  
**Time:** 30 minutes

**Checklist:**
- [ ] Create virtual environment: `python3 -m venv venv`
- [ ] Activate venv: `source venv/bin/activate`
- [ ] Create requirements.txt with all dependencies:
  ```
  python-telegram-bot==20.3
  apscheduler==3.10.4
  requests==2.31.0
  pyyaml==6.0
  python-dotenv==1.0.0
  ```
- [ ] Install: `pip install -r requirements.txt`
- [ ] Test import: `python -c "import telegram; import apscheduler; print('OK')"`

**Acceptance Criteria:**
- ✅ Virtual environment created and active
- ✅ All packages installable without errors
- ✅ All imports work in Python REPL

---

### TASK 2: Configuration Management
**Objective:** Set up environment-based config system  
**Time:** 1 hour

**Checklist:**
- [ ] Create `config/config.yaml`:
  ```yaml
  system:
    name: "Solana Memecoin Trading Bot"
    version: "1.0.0"
    environment: "staging"  # or "production"
  
  trading:
    starting_capital: 10.0
    daily_loss_limit: 3.0
    portfolio_max_exposure: 0.30
    position_size:
      confidence_8_10: 2.0
      confidence_6_7: 1.0
      confidence_min: 6
  
  risk:
    stop_loss_percent: 20
    take_profit_tier1: 2.0  # 2x entry
    take_profit_tier1_sell: 0.40
    take_profit_tier2: 4.0  # 4x entry
    take_profit_tier2_sell: 0.40
    trailing_stop_percent: 50
  
  telegram:
    enabled: true
    message_format: "json"  # structured alerts
  
  scheduler:
    researcher_interval_minutes: 15
    position_monitor_interval_seconds: 60
  
  logging:
    level: "INFO"
    format: "json"  # easy parsing
  ```

- [ ] Create `secrets.env` (NEVER commit this):
  ```
  TELEGRAM_BOT_TOKEN=your_token_here
  ANTHROPIC_API_KEY=your_key_here
  SOLANA_RPC_URL=https://api.mainnet-beta.solana.com
  ```

- [ ] Create `src/config.py`:
  ```python
  import os
  import yaml
  from pathlib import Path
  from dotenv import load_dotenv
  
  class Config:
      def __init__(self):
          load_dotenv('secrets.env')
          config_path = Path(__file__).parent.parent / 'config' / 'config.yaml'
          with open(config_path) as f:
              self.data = yaml.safe_load(f)
      
      def get(self, key_path: str, default=None):
          """Get nested config value: 'trading.position_size.confidence_8_10'"""
          keys = key_path.split('.')
          value = self.data
          for key in keys:
              if isinstance(value, dict):
                  value = value.get(key)
              else:
                  return default
          return value if value is not None else default
      
      def get_secret(self, key: str):
          """Get environment variable (API keys, tokens)"""
          return os.getenv(key)
  ```

- [ ] Create `.gitignore`:
  ```
  venv/
  __pycache__/
  .env
  secrets.env
  *.db
  logs/
  .DS_Store
  ```

**Acceptance Criteria:**
- ✅ config.yaml loads without errors
- ✅ Config class retrieves nested values correctly
- ✅ secrets.env is in .gitignore
- ✅ All API keys come from environment, not hardcoded

---

### TASK 3: Database Schema Setup
**Objective:** Design and implement SQLite database for tracking signals and trades  
**Time:** 1.5 hours

**Checklist:**
- [ ] Create `src/database.py` with schema:

```python
import sqlite3
from pathlib import Path
from datetime import datetime

class Database:
    def __init__(self, db_path='data/database.db'):
        self.db_path = db_path
        self.init_schema()
    
    def init_schema(self):
        """Create all tables on first run"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        # Signals table
        c.execute('''CREATE TABLE IF NOT EXISTS signals (
            signal_id TEXT PRIMARY KEY,
            timestamp TEXT,
            token_address TEXT,
            token_name TEXT,
            token_symbol TEXT,
            entry_price REAL,
            position_size_usd REAL,
            confidence_score INTEGER,
            reason TEXT,
            status TEXT,  # 'sent', 'executed', 'dropped', 'expired'
            telegram_sent BOOLEAN,
            created_at TEXT
        )''')
        
        # Trades table
        c.execute('''CREATE TABLE IF NOT EXISTS trades (
            trade_id TEXT PRIMARY KEY,
            signal_id TEXT,
            token_address TEXT,
            entry_price REAL,
            entry_time TEXT,
            entry_tx_hash TEXT,
            position_size_usd REAL,
            status TEXT,  # 'open', 'closed', 'partial'
            stop_loss_price REAL,
            stop_loss_triggered BOOLEAN,
            
            tp1_price REAL,
            tp1_triggered BOOLEAN,
            tp1_exit_price REAL,
            tp1_profit_usd REAL,
            
            tp2_price REAL,
            tp2_triggered BOOLEAN,
            tp2_exit_price REAL,
            tp2_profit_usd REAL,
            
            tp3_type TEXT,  # 'trailing_stop'
            tp3_triggered BOOLEAN,
            tp3_exit_price REAL,
            tp3_profit_usd REAL,
            
            total_profit_usd REAL,
            total_profit_percent REAL,
            exit_time TEXT,
            exit_tx_hash TEXT,
            created_at TEXT
        )''')
        
        # Daily summary table
        c.execute('''CREATE TABLE IF NOT EXISTS daily_summary (
            date TEXT PRIMARY KEY,
            signals_sent INTEGER,
            signals_dropped INTEGER,
            trades_executed INTEGER,
            wins INTEGER,
            losses INTEGER,
            total_profit_usd REAL,
            daily_loss_limit REAL,
            loss_limit_hit BOOLEAN,
            capital_start REAL,
            capital_end REAL,
            hit_rate_percent REAL,
            created_at TEXT
        )''')
        
        # System events table (errors, kills, etc)
        c.execute('''CREATE TABLE IF NOT EXISTS system_events (
            event_id TEXT PRIMARY KEY,
            event_type TEXT,  # 'soft_pause', 'hard_stop', 'emergency_kill', 'api_error'
            severity TEXT,  # 'info', 'warning', 'error', 'critical'
            description TEXT,
            diagnostic_data TEXT,  # JSON
            resolved BOOLEAN,
            created_at TEXT
        )''')
        
        conn.commit()
        conn.close()
    
    def log_signal(self, signal_dict):
        """Log a signal to database"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('''INSERT INTO signals 
                     (signal_id, timestamp, token_address, token_name, token_symbol,
                      entry_price, position_size_usd, confidence_score, reason,
                      status, telegram_sent, created_at)
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                  (signal_dict['signal_id'], signal_dict['timestamp'],
                   signal_dict['token_address'], signal_dict['token_name'],
                   signal_dict['token_symbol'], signal_dict['entry_price'],
                   signal_dict['position_size'], signal_dict['confidence'],
                   signal_dict['reason'], 'sent', True, datetime.utcnow().isoformat()))
        conn.commit()
        conn.close()
    
    def log_trade(self, trade_dict):
        """Log a trade execution"""
        # Similar structure
        pass
    
    def get_daily_pnl(self, date: str):
        """Get daily profit/loss"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('SELECT * FROM daily_summary WHERE date=?', (date,))
        result = c.fetchone()
        conn.close()
        return result
```

- [ ] Test database creation: `python -c "from src.database import Database; Database(); print('OK')"`

**Acceptance Criteria:**
- ✅ Database.db created on first run
- ✅ All 4 tables exist with correct schema
- ✅ No errors on subsequent runs
- ✅ Can insert test data without errors

---

### TASK 4: Telegram Bot Setup
**Objective:** Create Telegram interface for alerts and status commands  
**Time:** 1.5 hours

**Checklist:**
- [ ] Create `src/telegram_bot.py`:

```python
from telegram import Bot
from telegram.error import TelegramError
import json
from datetime import datetime

class TelegramBot:
    def __init__(self, token: str, chat_id: str):
        self.bot = Bot(token=token)
        self.chat_id = chat_id
    
    def send_signal_alert(self, signal_dict):
        """Send structured signal alert to Telegram"""
        message = self._format_signal(signal_dict)
        try:
            self.bot.send_message(chat_id=self.chat_id, text=message, parse_mode='HTML')
            return True
        except TelegramError as e:
            print(f"Telegram error: {e}")
            return False
    
    def _format_signal(self, signal):
        """Format signal for readable Telegram display"""
        return f"""
🚀 SIGNAL #{signal['signal_id']} (Confidence: {signal['confidence']}/10)

Token: {signal['token_name']} ({signal['token_symbol']})
Entry Price: ${signal['entry_price']:.6f}
Position: ${signal['position_size']:.2f}

📊 Risk/Reward: 1:2
Stop Loss: ${signal['stop_loss_price']:.6f}
Take Profit Targets:
  TP1 (40%): ${signal['tp1_price']:.6f} (2x)
  TP2 (40%): ${signal['tp2_price']:.6f} (4x)
  TP3 (20%): Trailing stop at {signal['tp3_trailing']}

🔍 Why This Signal:
{signal['reason']}

🎯 Execution: AUTOMATIC
        """
    
    def send_kill_switch_alert(self, tier: str, diagnostic_data: dict):
        """Send critical kill switch alert"""
        message = f"""
🛑 KILL SWITCH - TIER {tier}

{diagnostic_data['message']}

Details:
{json.dumps(diagnostic_data, indent=2)}

Timestamp: {datetime.utcnow().isoformat()}
        """
        try:
            self.bot.send_message(chat_id=self.chat_id, text=message, parse_mode='HTML')
            return True
        except TelegramError as e:
            print(f"Telegram error: {e}")
            return False
    
    def send_daily_summary(self, daily_stats: dict):
        """Send end-of-day summary"""
        message = f"""
📊 DAILY SUMMARY

Signals Sent: {daily_stats['signals_sent']}
Trades Executed: {daily_stats['trades_executed']}
Hit Rate: {daily_stats['hit_rate']}%
Daily P&L: ${daily_stats['daily_pnl']:.2f}
Capital: ${daily_stats['capital_start']:.2f} → ${daily_stats['capital_end']:.2f}
        """
        try:
            self.bot.send_message(chat_id=self.chat_id, text=message, parse_mode='HTML')
            return True
        except TelegramError as e:
            print(f"Telegram error: {e}")
            return False
```

- [ ] Get your Telegram chat ID:
  - Start bot, send `/status` command
  - Log the chat_id from the bot's logs
  - Add to secrets.env: `TELEGRAM_CHAT_ID=your_id`

- [ ] Test: `python -c "from src.telegram_bot import TelegramBot; print('OK')"`

**Acceptance Criteria:**
- ✅ Bot class initializes without errors
- ✅ Message formatting works
- ✅ Can import all Telegram libraries
- ✅ Chat ID configured in secrets

---

### TASK 5: Scheduler Framework
**Objective:** Set up APScheduler for periodic tasks  
**Time:** 1 hour

**Checklist:**
- [ ] Create `src/scheduler.py`:

```python
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
import logging

class TaskScheduler:
    def __init__(self):
        self.scheduler = BackgroundScheduler()
        self.logger = logging.getLogger('scheduler')
    
    def add_researcher_job(self, callback, interval_minutes=15):
        """Schedule researcher bot to run every N minutes"""
        self.scheduler.add_job(
            callback,
            trigger=IntervalTrigger(minutes=interval_minutes),
            id='researcher_bot',
            name='Researcher Bot',
            replace_existing=True
        )
        self.logger.info(f'Added researcher job: every {interval_minutes} minutes')
    
    def add_position_monitor_job(self, callback, interval_seconds=60):
        """Schedule position monitor to run every N seconds"""
        self.scheduler.add_job(
            callback,
            trigger=IntervalTrigger(seconds=interval_seconds),
            id='position_monitor',
            name='Position Monitor',
            replace_existing=True
        )
        self.logger.info(f'Added position monitor job: every {interval_seconds} seconds')
    
    def add_daily_summary_job(self, callback, hour=23, minute=55):
        """Schedule daily summary at specific time"""
        from apscheduler.triggers.cron import CronTrigger
        self.scheduler.add_job(
            callback,
            trigger=CronTrigger(hour=hour, minute=minute),
            id='daily_summary',
            name='Daily Summary',
            replace_existing=True
        )
        self.logger.info(f'Added daily summary job: {hour}:{minute} UTC')
    
    def start(self):
        """Start the scheduler"""
        self.scheduler.start()
        self.logger.info('Scheduler started')
    
    def stop(self):
        """Stop the scheduler"""
        self.scheduler.shutdown(wait=True)
        self.logger.info('Scheduler stopped')
```

- [ ] Test: `python -c "from src.scheduler import TaskScheduler; TaskScheduler(); print('OK')"`

**Acceptance Criteria:**
- ✅ Scheduler class initializes
- ✅ Can add jobs without errors
- ✅ Scheduler can start/stop

---

### TASK 6: Logging Setup
**Objective:** Structured logging for debugging and audit trail  
**Time:** 45 minutes

**Checklist:**
- [ ] Create `src/logger.py`:

```python
import logging
import json
from datetime import datetime
from pathlib import Path

class JSONFormatter(logging.Formatter):
    def format(self, record):
        log_entry = {
            'timestamp': datetime.utcnow().isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage()
        }
        if record.exc_info:
            log_entry['exception'] = self.formatException(record.exc_info)
        return json.dumps(log_entry)

def setup_logger(name: str, log_level=logging.INFO):
    """Create a JSON logger for the application"""
    logger = logging.getLogger(name)
    logger.setLevel(log_level)
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(JSONFormatter())
    logger.addHandler(console_handler)
    
    # File handler
    Path('data/logs').mkdir(exist_ok=True)
    file_handler = logging.FileHandler(f'data/logs/{datetime.utcnow().strftime("%Y-%m-%d")}.log')
    file_handler.setFormatter(JSONFormatter())
    logger.addHandler(file_handler)
    
    return logger
```

- [ ] Test logger: `python -c "from src.logger import setup_logger; log = setup_logger('test'); log.info('test'); print('OK')"`

**Acceptance Criteria:**
- ✅ Logs directory created
- ✅ Daily log file created with JSON format
- ✅ Console and file logging both work

---

### TASK 7: Main Entry Point
**Objective:** Create main.py that ties everything together  
**Time:** 1 hour

**Checklist:**
- [ ] Create `src/main.py`:

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from config import Config
from database import Database
from telegram_bot import TelegramBot
from scheduler import TaskScheduler
from logger import setup_logger

logger = setup_logger('main')

class TradingBotApp:
    def __init__(self):
        logger.info('Initializing Trading Bot...')
        self.config = Config()
        self.db = Database()
        
        # Get secrets
        telegram_token = self.config.get_secret('TELEGRAM_BOT_TOKEN')
        chat_id = self.config.get_secret('TELEGRAM_CHAT_ID')
        
        if not telegram_token or not chat_id:
            raise ValueError('TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID required in secrets.env')
        
        self.telegram = TelegramBot(telegram_token, chat_id)
        self.scheduler = TaskScheduler()
        
        logger.info('Bot initialized successfully')
    
    def researcher_job(self):
        """Called every N minutes - placeholder for Phase 2"""
        logger.info('Researcher job running...')
        # Phase 2: Will implement signal discovery here
        pass
    
    def position_monitor_job(self):
        """Called every N seconds - placeholder for Phase 4"""
        logger.info('Position monitor running...')
        # Phase 4: Will implement position management here
        pass
    
    def daily_summary_job(self):
        """Called daily - generates summary"""
        logger.info('Daily summary job running...')
        # Query DB and send telegram alert
        pass
    
    def start(self):
        """Start the trading bot"""
        logger.info('Starting Trading Bot...')
        
        # Add scheduled jobs
        researcher_interval = self.config.get('scheduler.researcher_interval_minutes', 15)
        position_interval = self.config.get('scheduler.position_monitor_interval_seconds', 60)
        
        self.scheduler.add_researcher_job(self.researcher_job, researcher_interval)
        self.scheduler.add_position_monitor_job(self.position_monitor_job, position_interval)
        self.scheduler.add_daily_summary_job(self.daily_summary_job)
        
        self.scheduler.start()
        
        # Send startup notification
        self.telegram.bot.send_message(
            chat_id=self.config.get_secret('TELEGRAM_CHAT_ID'),
            text='✅ Trading Bot started and monitoring'
        )
        
        # Keep running
        try:
            logger.info('Bot running. Press Ctrl+C to stop.')
            import time
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            self.stop()
    
    def stop(self):
        """Stop the trading bot"""
        logger.info('Stopping Trading Bot...')
        self.scheduler.stop()
        self.telegram.bot.send_message(
            chat_id=self.config.get_secret('TELEGRAM_CHAT_ID'),
            text='❌ Trading Bot stopped'
        )

if __name__ == '__main__':
    app = TradingBotApp()
    app.start()
```

- [ ] Test: `python src/main.py` (should start and send Telegram message)

**Acceptance Criteria:**
- ✅ main.py runs without errors
- ✅ Startup Telegram notification received
- ✅ Scheduler starts and stops cleanly

---

### TASK 8: AWS Deployment Guide
**Objective:** Document AWS setup for production deployment  
**Time:** 30 minutes

**Checklist:**
- [ ] Create `DEPLOY.md`:

```markdown
# AWS EC2 Deployment Guide

## 1. Launch EC2 Instance
- AMI: Ubuntu 22.04 LTS
- Instance: t3.micro (free tier eligible)
- Storage: 20GB gp2
- Security group: Allow SSH (22) and HTTP (80)

## 2. SSH into instance
\`\`\`bash
ssh -i your-key.pem ubuntu@your-instance-ip
\`\`\`

## 3. Install dependencies
\`\`\`bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3 python3-pip git

# Clone your repo
git clone https://github.com/your-repo/crypto-trading-bot.git
cd crypto-trading-bot

# Install Python deps
pip3 install -r requirements.txt
\`\`\`

## 4. Set environment variables
\`\`\`bash
echo 'export TELEGRAM_BOT_TOKEN="..."' >> ~/.bashrc
echo 'export TELEGRAM_CHAT_ID="..."' >> ~/.bashrc
source ~/.bashrc
\`\`\`

## 5. Run as systemd service
Create `/etc/systemd/system/trading-bot.service`:

\`\`\`ini
[Unit]
Description=Solana Trading Bot
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/crypto-trading-bot
ExecStart=/usr/bin/python3 src/main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
\`\`\`

Then:
\`\`\`bash
sudo systemctl enable trading-bot
sudo systemctl start trading-bot
sudo systemctl status trading-bot
\`\`\`

## 6. Monitor logs
\`\`\`bash
tail -f data/logs/$(date +%Y-%m-%d).log
\`\`\`
```

**Acceptance Criteria:**
- ✅ Deployment guide is complete and clear
- ✅ All commands tested locally first

---

## FINAL CHECKLIST - PHASE 1 COMPLETE

- [ ] All 7 tasks completed
- [ ] Project structure matches specification
- [ ] Virtual environment working
- [ ] Config system tested
- [ ] Database schema created
- [ ] Telegram bot initialized
- [ ] Scheduler framework ready
- [ ] Logger set up
- [ ] main.py runs without errors
- [ ] AWS deployment guide written
- [ ] Code committed to git
- [ ] README.md written with setup instructions

---

## SUCCESS CRITERIA FOR PHASE 1

✅ Clean, modular codebase ready for Phase 2  
✅ All configuration external (config.yaml, secrets.env)  
✅ Database logging framework in place  
✅ Telegram alerts working  
✅ Scheduler framework ready for researcher/monitor jobs  
✅ Logging to JSON files for debugging  
✅ Deployable to AWS with systemd  
✅ Zero hardcoded secrets or API keys  

---

## NEXT: PHASE 2

Once Phase 1 is complete, Phase 2 will add:
- Dexscreener API integration
- 6-point rug detection filters
- Claude Haiku confidence scoring
- Signal generation and formatting
- Database logging of signals

**Estimated Phase 2 time:** 7-10 days (most complex phase)
