# backend/src/config/default_channels.py

# Loaded into system_state on first run of Agent 4.
# All public channels — no membership required.
# User can add/remove from the dashboard.

DEFAULT_CHANNELS = [
    {
        "id":      "@lookonchain",
        "label":   "Lookonchain",
        "type":    "kol",
        "weight":  0.85,
        "enabled": True,
        "parser":  "lookonchain",   # maps to LookonchainParser
    },
    {
        "id":      "@whalealert",
        "label":   "Whale Alert",
        "type":    "tracker",
        "weight":  0.65,
        "enabled": True,
        "parser":  "whale_alert",
    },
    {
        "id":      "@solanawhalealerts",
        "label":   "Solana Whale Alerts",
        "type":    "tracker",
        "weight":  0.70,
        "enabled": True,
        "parser":  "generic",
    },
    {
        "id":      "@dexscreener_trending",
        "label":   "DexScreener Trending",
        "type":    "tracker",
        "weight":  0.55,
        "enabled": True,
        "parser":  "generic",
    },
]
