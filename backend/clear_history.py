
import os
import asyncio
from src.database import Database
from src.config import Config

async def clear_history():
    config = Config()
    os.environ["CONVEX_URL"] = config.get_secret("CONVEX_URL")
    os.environ["CONVEX_DEPLOYMENT"] = config.get_optional_secret("CONVEX_DEPLOYMENT") or ""
    
    db = Database()
    user_id = "1391287205"
    await db.clear_chat_history(user_id)
    print(f"✅ History cleared for {user_id}")
    await db.close()

if __name__ == "__main__":
    asyncio.run(clear_history())
