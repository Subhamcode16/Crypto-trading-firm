
import os
import asyncio
import json
from src.database import Database
from src.config import Config

async def check_history():
    config = Config()
    # Explicitly set env vars for Convex client
    os.environ["CONVEX_URL"] = config.get_secret("CONVEX_URL")
    os.environ["CONVEX_DEPLOYMENT"] = config.get_optional_secret("CONVEX_DEPLOYMENT") or ""
    
    db = Database()
    user_id = "1391287205" # The user's ID
    history = await db.get_chat_history(user_id)
    print(f"HISTORY for {user_id}:")
    print(json.dumps(history, indent=2))
    
    messages = []
    for h in history:
        messages.append({"role": h.get("role"), "content": h.get("content")})
    
    print(f"MESSAGES to be sent: {len(messages)}")
    print(json.dumps(messages, indent=2))
    await db.close()

if __name__ == "__main__":
    asyncio.run(check_history())
