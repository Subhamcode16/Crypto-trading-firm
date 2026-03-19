#!/usr/bin/env python3
"""
Simple API Configuration Check (No Dependencies)
================================================

Check all configured APIs without requiring additional packages.
"""

import json
from pathlib import Path


def load_env_file(path):
    """Load .env-style file into dict"""
    data = {}
    env_file = Path(path)
    
    if not env_file.exists():
        return data
    
    with open(env_file, 'r') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            
            if '=' in line:
                key, value = line.split('=', 1)
                data[key.strip()] = value.strip()
    
    return data


def check_apis():
    """Check all API configurations"""
    print("\n" + "=" * 70)
    print("🔍 API CONFIGURATION CHECK")
    print("=" * 70)
    
    # Load configs
    secrets = load_env_file('secrets.env')
    env = load_env_file('.env')
    
    with open('config/config.json', 'r') as f:
        config_json = json.load(f)
    
    results = {}
    
    # 1. Dexscreener (Public API, no key needed)
    print("\n📊 Dexscreener (Token Discovery)")
    print("  Status: ✅ PUBLIC API (no key needed)")
    print("  Endpoint: api.dexscreener.com/latest/dex/pairs/solana")
    results['dexscreener'] = 'OK'
    
    # 2. Solscan
    print("\n🔗 Solscan (On-Chain Analysis)")
    solscan_key = secrets.get('SOLSCAN_API_KEY')
    if solscan_key:
        print(f"  Status: ✅ CONFIGURED")
        print(f"  Key: {solscan_key[:20]}..." if len(solscan_key) > 20 else f"  Key: {solscan_key}")
        results['solscan'] = 'CONFIGURED'
    else:
        print(f"  Status: ❌ NOT CONFIGURED")
        results['solscan'] = 'MISSING'
    
    # 3. Helius
    print("\n🔗 Helius RPC (Blockchain Data)")
    helius_key = secrets.get('HELIUS_API_KEY')
    helius_url = secrets.get('HELIUS_RPC_URL')
    if helius_key and helius_url:
        print(f"  Status: ✅ CONFIGURED")
        print(f"  API Key: {helius_key[:20]}...")
        print(f"  RPC URL: {helius_url[:50]}...")
        results['helius'] = 'CONFIGURED'
    else:
        print(f"  Status: ❌ NOT CONFIGURED")
        print(f"    - API Key: {'✅' if helius_key else '❌'}")
        print(f"    - RPC URL: {'✅' if helius_url else '❌'}")
        results['helius'] = 'MISSING'
    
    # 4. Birdeye
    print("\n🦅 Birdeye (Smart Wallet Tracking)")
    birdeye_key = secrets.get('BIRDEYE_API_KEY')
    if birdeye_key:
        print(f"  Status: ✅ CONFIGURED")
        print(f"  Key: {birdeye_key[:20]}...")
        results['birdeye'] = 'CONFIGURED'
    else:
        print(f"  Status: ❌ NOT CONFIGURED")
        print(f"  ACTION NEEDED: Add BIRDEYE_API_KEY to secrets.env")
        print(f"  IMPACT: Agent 3 will return mock wallet data (6.5/10 instead of real)")
        results['birdeye'] = 'MISSING'
    
    # 5. Anthropic Claude
    print("\n🤖 Anthropic Claude (LLM)")
    anthropic_key = secrets.get('ANTHROPIC_API_KEY')
    if anthropic_key:
        print(f"  Status: ✅ CONFIGURED")
        print(f"  Key: {anthropic_key[:20]}...")
        results['anthropic'] = 'CONFIGURED'
    else:
        print(f"  Status: ❌ NOT CONFIGURED")
        results['anthropic'] = 'MISSING'
    
    # 6. Discord
    print("\n🎮 Discord Bot")
    discord_token = config_json.get('discord', {}).get('bot_token')
    if discord_token:
        print(f"  Status: ✅ CONFIGURED")
        print(f"  Token: {discord_token[:20]}...")
        results['discord'] = 'CONFIGURED'
    else:
        print(f"  Status: ❌ NOT CONFIGURED")
        results['discord'] = 'MISSING'
    
    # 7. Telegram
    print("\n📱 Telegram Bot")
    telegram_token = secrets.get('TELEGRAM_BOT_TOKEN')
    telegram_chat = secrets.get('TELEGRAM_CHAT_ID')
    if telegram_token and telegram_chat:
        print(f"  Status: ✅ CONFIGURED")
        print(f"  Bot Token: {telegram_token[:20]}...")
        print(f"  Chat ID: {telegram_chat}")
        results['telegram'] = 'CONFIGURED'
    else:
        print(f"  Status: ⚠️  PARTIALLY CONFIGURED")
        print(f"    - Bot Token: {'✅' if telegram_token else '❌'}")
        print(f"    - Chat ID: {'✅' if telegram_chat else '❌'}")
        results['telegram'] = 'INCOMPLETE'
    
    # 8. Solana RPC
    print("\n⛓️  Solana RPC")
    solana_rpc = secrets.get('SOLANA_RPC_URL')
    if solana_rpc:
        print(f"  Status: ✅ CONFIGURED")
        print(f"  URL: {solana_rpc[:50]}...")
        results['solana_rpc'] = 'CONFIGURED'
    else:
        print(f"  Status: ⚠️  NOT CONFIGURED (fallback: mainnet-beta)")
        results['solana_rpc'] = 'USING_DEFAULT'
    
    # Summary
    print("\n" + "=" * 70)
    print("📊 SUMMARY")
    print("=" * 70)
    
    configured = [k for k, v in results.items() if v == 'CONFIGURED']
    missing = [k for k, v in results.items() if v == 'MISSING']
    partial = [k for k, v in results.items() if v in ['INCOMPLETE', 'USING_DEFAULT']]
    
    print(f"\n✅ Configured: {len(configured)}")
    for item in configured:
        print(f"   • {item}")
    
    if missing:
        print(f"\n❌ Missing ({len(missing)}):")
        for item in missing:
            print(f"   • {item}")
    
    if partial:
        print(f"\n⚠️  Partial ({len(partial)}):")
        for item in partial:
            print(f"   • {item}")
    
    print("\n" + "=" * 70)
    print("🚀 DEPLOYMENT STATUS")
    print("=" * 70)
    
    critical = ['solscan', 'helius', 'anthropic', 'discord']
    
    critical_ok = all(results.get(api, 'MISSING') == 'CONFIGURED' for api in critical if api != 'discord')
    
    if results['birdeye'] == 'MISSING':
        print("\n⚠️  ACTION REQUIRED: Add Birdeye API Key")
        print("   This will enable real wallet tracking in Agent 3")
        print("   Without it: Agent 3 returns mock data (6.5/10 score)")
    
    if critical_ok:
        print("\n✅ READY TO DEPLOY")
        print("   • All critical APIs configured")
        print("   • Can start researcher bot with: python3 src/main.py")
    else:
        print("\n❌ NOT READY")
        print("   • Missing critical API keys")
        print("   • Add missing keys to secrets.env and try again")
    
    print("=" * 70 + "\n")


if __name__ == '__main__':
    check_apis()
