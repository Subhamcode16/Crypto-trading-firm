import os
import logging
from typing import Dict, List, Any
from pymongo import MongoClient

logger = logging.getLogger(__name__)

class MongoStore:
    def __init__(self, db_name: str = "crypto_trading_bot"):
        self.mongo_url = os.environ.get("MONGO_URL")
        
        # Localhost does not exist in the cloud!
        if not self.mongo_url:
            logger.warning("[MongoStore] No MONGO_URL provided. Falling back to local MongoDB, but this will fail in Render.")
            self.mongo_url = "mongodb://127.0.0.1:27017"
            
        try:
            self.client = MongoClient(self.mongo_url, serverSelectionTimeoutMS=5000)
            self.db = self.client[db_name]
            
            # Initialize collections
            self.gamification_state = self.db["gamification_state"]
            self.trades = self.db["trades"]
            self.ai_logs = self.db["ai_logs"]
            self.positions = self.db["positions"]
            
        except Exception as e:
            logger.error(f"[MongoStore] Failed to connect to MongoDB: {e}")
            raise

    def load_gamification_state(self) -> Dict[str, Any]:
        try:
            docs = list(self.gamification_state.find({}))
            if not docs:
                return {}
            
            state = {}
            for doc in docs:
                state[doc["key"]] = doc["value"]
            return state
        except Exception as e:
            logger.error(f"[MongoStore] Error loading gamification state: {e}")
            return {}

    def save_gamification_state(self, state: Dict[str, Any]):
        try:
            for key, value in state.items():
                self.gamification_state.update_one(
                    {"key": key},
                    {"$set": {"key": key, "value": value}},
                    upsert=True
                )
        except Exception as e:
            logger.error(f"[MongoStore] Error saving gamification state: {e}")

    def append_trade(self, trade: Dict[str, Any]):
        try:
            self.trades.insert_one(trade)
        except Exception as e:
            logger.error(f"[MongoStore] Error appending trade: {e}")

    def append_ai_log(self, log: Dict[str, Any]):
        try:
            self.ai_logs.insert_one(log)
        except Exception as e:
            logger.error(f"[MongoStore] Error appending AI log: {e}")

    def insert_position(self, position_doc: Dict[str, Any]):
        try:
            self.db.positions.insert_one(position_doc)
        except Exception as e:
            logger.error(f"[MongoStore] Error inserting position: {e}")

    def get_open_positions(self) -> List[Dict[str, Any]]:
        try:
            positions = list(self.db.positions.find({"status": "OPEN"}).sort("_id", 1))
            # Keep string version of _id for updating later
            for pos in positions:
                pos["_id"] = str(pos["_id"])
            return positions
        except Exception as e:
            logger.error(f"[MongoStore] Error fetching open positions: {e}")
            return []

    def update_position(self, symbol: str, updates: Dict[str, Any]):
        try:
            self.db.positions.update_one(
                {"symbol": symbol, "status": "OPEN"},
                {"$set": updates}
            )
        except Exception as e:
            logger.error(f"[MongoStore] Error updating position {symbol}: {e}")

    def close_position(self, symbol: str):
        try:
            self.db.positions.update_one(
                {"symbol": symbol, "status": "OPEN"},
                {"$set": {"status": "CLOSED"}}
            )
        except Exception as e:
            logger.error(f"[MongoStore] Error closing position {symbol}: {e}")

    def get_all_trades(self) -> List[Dict[str, Any]]:
        try:
            # Return ascending order based on insertion
            trades = list(self.trades.find().sort("_id", 1))
            # Remove MongoDB's _id to maintain compatibility with SQLiteStore format
            for trade in trades:
                trade.pop("_id", None)
            return trades
        except Exception as e:
            logger.error(f"[MongoStore] Error fetching trades: {e}")
            return []

    def clear_all(self):
        try:
            self.trades.delete_many({})
            self.gamification_state.delete_many({})
        except Exception as e:
            logger.error(f"[MongoStore] Error clearing collections: {e}")
