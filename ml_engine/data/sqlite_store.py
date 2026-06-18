import sqlite3
import json
import logging
from typing import Dict, List, Any

logger = logging.getLogger(__name__)

class SQLiteStore:
    def __init__(self, db_path: str = "paper_trades.db"):
        self.db_path = db_path
        self._init_db()

    def _get_conn(self):
        return sqlite3.connect(self.db_path)

    def _init_db(self):
        with self._get_conn() as conn:
            cursor = conn.cursor()
            
            # Gamification State
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS gamification_state (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            """)
            
            # Trades Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT,
                    type TEXT,
                    price REAL,
                    time TEXT,
                    confidence REAL,
                    pnl REAL,
                    pnl_pct REAL
                )
            """)
            
            # AI Decision Logs
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS ai_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT,
                    action_proposed TEXT,
                    llm_decision TEXT,
                    rationale TEXT,
                    time TEXT
                )
            """)
            conn.commit()

    def load_gamification_state(self) -> Dict[str, Any]:
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT key, value FROM gamification_state")
            rows = cursor.fetchall()
            
            if not rows:
                return {}
                
            state = {}
            for key, val_str in rows:
                try:
                    state[key] = json.loads(val_str)
                except json.JSONDecodeError:
                    state[key] = val_str
            return state

    def save_gamification_state(self, state: Dict[str, Any]):
        with self._get_conn() as conn:
            cursor = conn.cursor()
            for key, value in state.items():
                val_str = json.dumps(value)
                cursor.execute(
                    "INSERT INTO gamification_state (key, value) VALUES (?, ?) "
                    "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                    (key, val_str)
                )
            conn.commit()

    def append_trade(self, trade: Dict[str, Any]):
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO trades (symbol, type, price, time, confidence, pnl, pnl_pct)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                trade.get("symbol"),
                trade.get("type"),
                trade.get("price"),
                trade.get("time"),
                trade.get("confidence"),
                trade.get("pnl"),
                trade.get("pnl_pct")
            ))
            conn.commit()

    def append_ai_log(self, log: Dict[str, Any]):
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO ai_logs (symbol, action_proposed, llm_decision, rationale, time)
                VALUES (?, ?, ?, ?, ?)
            """, (
                log.get("symbol"),
                log.get("action_proposed"),
                log.get("llm_decision"),
                log.get("rationale"),
                log.get("time")
            ))
            conn.commit()

    def get_all_trades(self) -> List[Dict[str, Any]]:
        with self._get_conn() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM trades ORDER BY id ASC")
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
            
    def clear_all(self):
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM trades")
            cursor.execute("DELETE FROM gamification_state")
            conn.commit()
