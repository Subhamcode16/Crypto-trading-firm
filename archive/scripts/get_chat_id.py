import requests
import json

TOKEN = "8714510154:AAGRCQxfyibP1lhV0S0HsVfyJWVp08zLaOM"

# Get updates from Telegram API directly (synchronous)
url = f"https://api.telegram.org/bot{TOKEN}/getUpdates"

try:
    response = requests.get(url)
    data = response.json()
    
    if data.get('ok'):
        updates = data.get('result', [])
        
        if updates:
            # Get the last message
            last_update = updates[-1]
            if 'message' in last_update:
                chat_id = last_update['message']['chat']['id']
                username = last_update['message']['chat'].get('username', 'N/A')
                text = last_update['message'].get('text', 'N/A')
                
                print(f"✅ Chat ID: {chat_id}")
                print(f"   Username: {username}")
                print(f"   Message: {text}")
        else:
            print("❌ No messages yet. Message your bot on Telegram and try again.")
    else:
        print(f"❌ Error from Telegram: {data.get('description')}")
        
except Exception as e:
    print(f"❌ Error: {e}")
