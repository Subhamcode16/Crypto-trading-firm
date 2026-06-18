Bybit Testnet — But Correctly This Time
You already dismissed Bybit Testnet early in this conversation — and you were right to dismiss it for backtesting. But for paper trading, it's exactly the right tool, for the opposite reason.
Paper trading requires:

Real live market data feed ✓
Real API call/response cycle ✓
Real order book mechanics ✓
Real rate limits hitting your code ✓
Zero real money at risk ✓

Bybit Testnet gives you all five. The ISP block you hit earlier is now a solved problem — you have your proxy relay architecture. Route your testnet traffic through it exactly the same way you'll route your production traffic. That's actually an additional validation benefit: you're testing your network infrastructure at the same time.

The Exact Setup
Step 1 — Two environment configs, one codebase
python# config.py
ENVIRONMENTS = {
    "testnet": {
        "exchange_id": "bybit",
        "api_key": "YOUR_TESTNET_KEY",
        "secret": "YOUR_TESTNET_SECRET",
        "sandbox": True,                    # ccxt sandbox flag
        "base_url": "https://api-testnet.bybit.com",
        "position_size_pct": 0.10,
        "mode": "PAPER"
    },
    "live": {
        "exchange_id": "bybit",
        "api_key": "YOUR_LIVE_KEY", 
        "secret": "YOUR_LIVE_SECRET",
        "sandbox": False,
        "base_url": "https://api.bybit.com",
        "position_size_pct": 0.01,          # Start at 1% when you go live
        "mode": "LIVE"
    }
}

ACTIVE_ENV = "testnet"                      # Single flag to flip when ready
One flag. ACTIVE_ENV = "live". That's the only change between paper and live. If your codebase requires anything more than that single change, your environment separation is broken.
Step 2 — Tag every MongoDB log entry with environment
pythonlog_entry = {
    "timestamp": datetime.utcnow(),
    "environment": config.ACTIVE_ENV,       # "testnet" or "live"
    "regime": regime_result,
    "consensus": consensus_result,
    "llm_decision": llm_result,
    "order": order_result,
    "kill_switch_status": ks_status,
    "pnl": pnl,
}
This lets you query paper vs live performance separately in the same database without ever mixing the datasets.
Step 3 — Get testnet perpetual funds
Go to testnet.bybit.com → deposit page → request testnet USDT. They give you 10,000 USDT testnet balance on demand. Reset it whenever you need to.
Step 4 — Validate the proxy relay first
bash# From your EC2/Hetzner server, through your Singapore relay
curl -x http://your-relay-server:port \
  "https://api-testnet.bybit.com/v5/market/time"

# Expected response
{"retCode":0,"retMsg":"OK","result":{"timeSecond":"...","timeNano":"..."}
If that returns clean, your full production network path is validated before a single bot cycle runs.

What To Watch During the 4 Weeks
You have MongoDB logging every decision. Build one simple weekly query and run it every Sunday:
python# Weekly review query
pipeline = [
    {"$match": {
        "environment": "testnet",
        "timestamp": {"$gte": week_start, "$lte": week_end}
    }},
    {"$group": {
        "_id": "$regime",
        "total_signals": {"$sum": 1},
        "trades_executed": {"$sum": {"$cond": [{"$ne": ["$order", None]}, 1, 0]}},
        "total_pnl": {"$sum": "$pnl"},
        "llm_vetoes": {"$sum": {"$cond": [{"$eq": ["$llm_decision.veto", True]}, 1, 0]}}
    }}
]
This gives you PnL broken down by regime every week. You're looking for one thing: are you profitable in TRENDING and flat/slightly negative in everything else? That's the system working correctly. The regime gate should make your losses boring and infrequent, not zero.

The Decision Criteria to Go Live
After 4 weeks, run this checklist. Every item must be green:
□ Zero unhandled exceptions in 4 weeks of continuous operation
□ Kill switch fired and recovered correctly at least once (trigger it manually)
□ LLM veto rate between 10-25% (if 0% still, the prompt needs more work)
□ Regime detector blocked > 40% of evaluation cycles
□ Kronos MC spread correctly predicted low-quality trades (validate this)
□ Positive EV in TRENDING regime (doesn't need to be large, just positive)
□ Max testnet drawdown stayed within L2 kill switch threshold (< 5%)
□ Proxy relay had zero downtime events
□ MongoDB has clean, queryable logs for every single decision
□ Single config flag switches testnet → live cleanly
If any item is red, you don't go live yet. You fix that item. The checklist is not a formality — it's the contract you're making with yourself to not blow a real account on a preventable failure.