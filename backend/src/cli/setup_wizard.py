# backend/src/cli/setup_wizard.py

import os
import asyncio
import logging
from telethon import TelegramClient
from dotenv import load_dotenv

# Set up logging to both file and console
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("setup_wizard.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('setup_wizard')

# Path to .env and session
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
ENV_PATH = os.path.join(BASE_DIR, '.env')
SESSION_PATH = os.path.join(BASE_DIR, 'config', 'pixelfirm_reader')

async def main():
    print("\n" + "="*50)
    print("      🚀 PIXELFIRM TELEGRAM SETUP WIZARD 🚀")
    print("="*50 + "\n")
    
    # 1. Load existing .env
    load_dotenv(ENV_PATH)
    api_id = os.getenv('TELEGRAM_API_ID')
    api_hash = os.getenv('TELEGRAM_API_HASH')
    phone = os.getenv('TELEGRAM_READER_PHONE')

    if not api_id or not api_hash:
        print("❌ Error: TELEGRAM_API_ID or TELEGRAM_API_HASH not found in .env")
        print("Please get them from https://my.telegram.org and add to .env first.\n")
        return

    print(f"🔹 Using API_ID: {api_id}")
    print(f"🔹 Using Session: {SESSION_PATH}.session\n")

    # 2. Ensure config directory exists
    os.makedirs(os.path.join(BASE_DIR, 'config'), exist_ok=True)

    # 3. Initialize Client
    client = TelegramClient(SESSION_PATH, int(api_id), api_hash)
    
    print("Connecting to Telegram...")
    await client.connect()

    if not await client.is_user_authorized():
        print("🔑 Not authorized. Starting authentication...")
        if not phone:
            phone = input("Enter your phone number (with country code, e.g. +1...): ")
        
        try:
            await client.send_code_request(phone)
            code = input(f"Enter the code sent to {phone}: ")
            await client.sign_in(phone, code)
        except Exception as e:
            if 'password' in str(e).lower():
                password = input("2-factor authentication enabled. Enter your password: ")
                await client.sign_in(password=password)
            else:
                print(f"❌ Failed to sign in: {e}")
                return

    me = await client.get_me()
    print(f"\n✅ SUCCESS! Authenticated as: {me.first_name} (@{me.username})")
    print(f"Session file saved at: {SESSION_PATH}.session")
    print("\nYou can now start the bot, and Agent 4 will monitor Telegram alpha.\n")

    await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
