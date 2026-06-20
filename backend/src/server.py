from fastapi import FastAPI, Depends, HTTPException, Security, Request
from pydantic import BaseModel
from fastapi.security import APIKeyHeader
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import os
import logging
from .database import Database

logger = logging.getLogger("admin_api")

limiter = Limiter(key_func=get_remote_address)
app = FastAPI(title="Crypto Bot Admin API")

# Add CORS middleware
cors_origins = os.getenv(
    "CORS_ORIGINS",
    "http://localhost:3000,http://localhost:5173"
).split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

API_KEY_NAME = "X-Admin-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

def get_admin_key(api_key: str = Security(api_key_header)):
    expected_key = os.environ.get("ADMIN_API_KEY")
    if not expected_key:
        logger.error("ADMIN_API_KEY environment variable is not set")
        raise HTTPException(status_code=500, detail="Admin API key not configured on server")
    if api_key != expected_key:
        logger.warning("Failed admin authentication attempt")
        raise HTTPException(status_code=403, detail="Could not validate credentials")
    return api_key

@app.post("/admin/resume-killswitch/{user_id}")
@limiter.limit("5/minute")
async def resume_killswitch(user_id: str, request: Request, api_key: str = Depends(get_admin_key)):
    """
    Protected admin endpoint to manually override and clear a Tier 3 Kill Switch.
    """
    try:
        db = Database()
        ks_state = db.get_kill_switch(user_id)
        
        if ks_state.get('tier') == 3:
            db.clear_kill_switch(user_id, "admin")
            logger.info(f"[ADMIN API] Successfully cleared Tier 3 kill switch for user {user_id}")
            return {"status": "success", "message": f"Kill switch cleared for {user_id}"}
        else:
            logger.info(f"[ADMIN API] Attempted to clear kill switch for {user_id}, but they are in Tier {ks_state.get('tier')}")
            return {"status": "ignored", "message": f"User {user_id} is not in Tier 3 (Current tier: {ks_state.get('tier', 0)})"}
    except Exception as e:
        logger.error(f"[ADMIN API] Error clearing kill switch for {user_id}: {e}")
@app.get("/api/trades/history/{user_id}")
@limiter.limit("20/minute")
async def get_trade_history(user_id: str, request: Request, api_key: str = Depends(get_admin_key)):
    """
    Protected admin endpoint to fetch all active and closed trade history.
    """
    try:
        db = Database()
        positions = db.get_all_positions(user_id)
        
        # Serialize datetime objects if present. BSON from MongoDB handles dates itself but for JSON responses:
        def serialize_pos(p):
            for k, v in p.items():
                if isinstance(v, datetime):
                    p[k] = v.isoformat()
            return p
            
        active = [serialize_pos(p) for p in positions.get("active", [])]
        closed = [serialize_pos(p) for p in positions.get("closed", [])]
        
        return {
            "status": "success", 
            "data": {
                "active": active,
                "closed": closed
            }
        }
    except Exception as e:
        logger.error(f"[ADMIN API] Error fetching trade history for {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.post("/api/system/pause")
@limiter.limit("5/minute")
async def pause_system(request: Request, api_key: str = Depends(get_admin_key)):
    """Globally pause all agent scheduled tasks."""
    try:
        db = Database()
        db.set_system_state('is_paused', 'true')
        return {"status": "success", "message": "System globally paused"}
    except Exception as e:
        logger.error(f"[ADMIN API] Error pausing system: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/system/resume")
@limiter.limit("5/minute")
async def resume_system(request: Request, api_key: str = Depends(get_admin_key)):
    """Resume all agent scheduled tasks."""
    try:
        db = Database()
        db.set_system_state('is_paused', 'false')
        return {"status": "success", "message": "System globally resumed"}
    except Exception as e:
        logger.error(f"[ADMIN API] Error resuming system: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/system/status")
@limiter.limit("10/minute")
async def get_system_status(request: Request):
    """Check if system is currently paused (Public endpoint for UI status)"""
    try:
        db = Database()
        is_paused = db.get_system_state('is_paused') == 'true'
        return {"status": "success", "is_paused": is_paused}
    except Exception as e:
        return {"status": "error", "message": str(e)}
@app.get("/api/portfolio/balance")
@limiter.limit("20/minute")
async def get_portfolio_balance(request: Request):
    """
    Public endpoint for UI to fetch initial capital for balance calculation.
    """
    try:
        from .config import Config
        config = Config()
        initial_capital = float(config.get_optional_secret('INITIAL_CAPITAL') or '10.0')
        return {
            "status": "success",
            "initial_capital": initial_capital
        }
    except Exception as e:
        logger.error(f"[ADMIN API] Error fetching balance: {e}")
        return {"status": "error", "message": str(e)}

# --- LIVE TRADING ENDPOINTS ---
trader_instance = None

@app.on_event("startup")
async def startup_event():
    global trader_instance
    import sys
    import asyncio
    from pathlib import Path
    
    # Add project root to sys.path so we can import ml_engine
    project_root = Path(__file__).parent.parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
        
    from ml_engine.data.mongo_store import MongoStore
    db = MongoStore()
    state = db.load_gamification_state()
    
    api_key = state.get("binance_api_key")
    api_secret = state.get("binance_api_secret")
    testnet = state.get("binance_testnet", True)
    
    if api_key and api_secret:
        from ml_engine.execution.live_trader import LiveTrader
        trader_instance = LiveTrader(api_key=api_key, api_secret=api_secret, testnet=testnet)
        logger.info("Live Binance Trader started in background!")
    else:
        logger.info("No Binance credentials found. Waiting for UI connection.")
    
    async def trading_loop():
        import time
        last_eval_time = 0
        while True:
            try:
                if trader_instance and not getattr(app.state, 'is_paused', False):
                    current_time = time.time()
                    
                    # 1. Light Risk Monitor: Check PnL on active positions
                    await trader_instance.monitor_open_positions()
                    
                    # 2. Heavy ML Evaluation: Run every 60 minutes
                    if current_time - last_eval_time >= 3600:
                        await trader_instance.evaluate_market()
                        last_eval_time = current_time
                        
            except Exception as e:
                logger.error(f"Error in Trading loop: {e}")
            await asyncio.sleep(5 * 60) # Run every 5 minutes
            
    asyncio.create_task(trading_loop())


class ConnectExchangeRequest(BaseModel):
    api_key: str
    api_secret: str
    testnet: bool = True

@app.post("/api/exchange/connect")
@limiter.limit("10/minute")
async def connect_exchange(req: ConnectExchangeRequest, request: Request):
    global trader_instance
    try:
        from ml_engine.execution.live_trader import LiveTrader
        from ml_engine.data.mongo_store import MongoStore
        
        # Save credentials to Mongo
        db = MongoStore()
        db.save_gamification_state({
            "binance_api_key": req.api_key,
            "binance_api_secret": req.api_secret,
            "binance_testnet": req.testnet
        })
        
        # Initialize
        trader_instance = LiveTrader(api_key=req.api_key, api_secret=req.api_secret, testnet=req.testnet)
        
        # Trigger an immediate background evaluation
        import asyncio
        asyncio.create_task(trader_instance.evaluate_market())
        
        return {"status": "success", "message": "Exchange connected successfully!"}
    except Exception as e:
        logger.error(f"Error connecting exchange: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/exchange/disconnect")
@limiter.limit("10/minute")
async def disconnect_exchange(request: Request):
    global trader_instance
    try:
        from ml_engine.data.mongo_store import MongoStore
        db = MongoStore()
        # Save empty credentials
        db.save_gamification_state({
            "binance_api_key": "",
            "binance_api_secret": "",
            "binance_testnet": True
        })
        
        # Stop trader instance
        if trader_instance:
            trader_instance = None
            
        return {"status": "success", "message": "Exchange disconnected"}
    except Exception as e:
        logger.error(f"Error disconnecting exchange: {e}")
        raise HTTPException(status_code=500, detail=str(e))



@app.get("/api/agent/status")
@limiter.limit("60/minute")
async def get_agent_status(request: Request):
    if trader_instance is None:
        return {"status": "WAITING_FOR_CREDENTIALS"}
    return await trader_instance.get_status()

@app.get("/api/agent/history")
@limiter.limit("60/minute")
async def get_agent_history(request: Request):
    if trader_instance is None:
        raise HTTPException(status_code=503, detail="Trader not initialized")
        
    # PyMongo mutates dicts to add an ObjectId _id, which breaks FastAPI serialization.
    # Sanitize the history list before returning.
    sanitized_history = [
        {k: str(v) if k == "_id" else v for k, v in trade.items() if k != "_id"} 
        for trade in trader_instance.trade_history
    ]
    return {"status": "success", "history": sanitized_history}

@app.get("/api/agent/explain/{symbol:path}")
@limiter.limit("60/minute")
async def get_agent_explain(symbol: str, request: Request):
    if trader_instance is None:
        raise HTTPException(status_code=503, detail="Trader not initialized")
    
    sym = symbol.replace("-", "/").replace("_", "/")
    data = trader_instance.explainability_data.get(sym)
    if not data:
        data = trader_instance.explainability_data.get(symbol)
        
    if not data:
        raise HTTPException(status_code=404, detail=f"No explainability data found for {symbol}")
        
    return {"status": "success", "data": data}

@app.get("/api/agent/news")
@limiter.limit("60/minute")
async def get_agent_news(request: Request):
    if trader_instance is None:
        raise HTTPException(status_code=503, detail="Trader not initialized")
    
    sentiment = trader_instance.sentiment_engine.get_sentiment()
    return {"status": "success", "data": sentiment}
