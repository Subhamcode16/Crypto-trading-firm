import logging
import asyncio
import os
import uuid
import json
import traceback
from datetime import datetime
from typing import Dict, Optional, Set, List
from dataclasses import dataclass, asdict, field

import aiohttp
import websockets
import yfinance as yf
from axiom_py import Client as AxiomClient

logger = logging.getLogger(__name__)

# ── DATA CONTRACTS ─────────────────────────────────────────────────────────

@dataclass
class TradeInstruction:
    user_id: str
    token: str                  # e.g. "SOLUSDT"
    action: str                 # "BUY" | "SELL"
    position_size_usd: float    # Already sized and approved by Agent-7
    entry_price: float          # Expected entry (from signal)
    sl_price: float             # Stop Loss price
    tp1_price: float            # Take Profit 1 — partial exit
    tp1_exit_pct: float         # % of position to close at TP1 (e.g. 0.50)
    tp2_price: float            # Take Profit 2 — full exit
    trailing_stop_pct: float    # e.g. 0.03 = 3% trailing stop
    signal_id: str              # Trace ID from upstream agents
    timestamp: datetime
    strategy_breakdown: List[str] = field(default_factory=list)
    sl_tp_rationale: Optional[str] = None
    asset_type: str = 'solana_meme'


@dataclass
class ActivePosition:
    position_id: str            # UUID generated at entry
    user_id: str
    token: str
    action: str
    entry_price: float
    current_price: float
    position_size_usd: float
    remaining_size_usd: float   # Decreases after TP1 partial exit
    sl_price: float
    tp1_price: float
    tp1_hit: bool               # True after TP1 partial exit fires
    tp2_price: float
    trailing_stop_pct: float
    trailing_stop_price: float  # Dynamically updated as price moves favorably
    paper_trade: bool           # Always True in current phase
    status: str                 # "OPEN" | "CLOSED" | "PARTIAL"
    opened_at: datetime
    closed_at: Optional[datetime]
    pnl_usd: float              # Realized PnL, updated on each exit
    signal_id: str              # Trace ID — links back to Agent-5 signal origin
    asset_type: str = 'solana_meme'
    strategy_breakdown: List[str] = field(default_factory=list)
    sl_tp_rationale: Optional[str] = None

    def to_dict(self):
        d = asdict(self)
        if isinstance(d.get('opened_at'), datetime): d['opened_at'] = d['opened_at'].isoformat()
        if isinstance(d.get('closed_at'), datetime): d['closed_at'] = d['closed_at'].isoformat()
        return d


# ── CORE AGENT-8 CLASS ───────────────────────────────────────────────────
import threading

class TradingBot:
    """
    Agent-8: The Execution Engine (Paper Trading Mode).
    Receives vetted TradeInstruction objects and simulates market execution.
    Manages all open positions via Binance WebSocket price monitoring.
    """

    def __init__(self, db_client, agent_9=None):
        self.db = db_client
        self.agent_9 = agent_9
        
        # Load Paper Trading setting
        self.paper_trade_enabled = os.getenv("PAPER_TRADING", "true").lower() == "true"
        mode_str = "PAPER TRADING" if self.paper_trade_enabled else "LIVE TRADING"
        logger.info(f"[AGENT_8] {mode_str} mode active (configured via PAPER_TRADING env var).")

        # Initialize Axiom if token is present, otherwise use a local mock
        axiom_token = os.environ.get("AXIOM_API_TOKEN")
        if axiom_token:
            try:
                self.axiom = AxiomClient(token=axiom_token)
                self.axiom_enabled = True
                logger.info("[AGENT_8] Axiom observability initialized successfully.")
            except Exception as e:
                logger.warning(f"[AGENT_8] Axiom initialization failed: {e}. Falling back to local logging.")
                self.axiom = None
                self.axiom_enabled = False
        else:
            logger.warning("[AGENT_8] AXIOM_API_TOKEN not found. Axiom observability disabled.")
            self.axiom = None
            self.axiom_enabled = False

        # In-memory position management
        self.active_positions: Dict[str, ActivePosition] = {}  # position_id → ActivePosition
        self.ws_subscriptions: Dict[str, Set[str]] = {}        # token → set of position_ids
        
        # ── Async tasks (managed by main loop) ──
        self._ws_task: Optional[asyncio.Task] = None
        self._monitor_task: Optional[asyncio.Task] = None

    # Remove the dedicated event loop thread logic as we now run in the main async loop

    # Remove sync wrappers as we are moving to full async

    # ── STARTUP & RECOVERY ─────────────────────────────────────────────────

    async def start(self):
        """
        On boot, reload all OPEN positions from Convex into memory.
        Re-subscribes to WebSocket feeds for all active tokens.
        """
        logger.info("[AGENT_8] Starting Trading Engine and recovering open positions...")
        
        try:
            # Query Convex for all positions
            positions_data = await self.db.get_all_positions()
            open_docs = positions_data.get("open", [])
            
            recovered_count = 0
            for doc in open_docs:
                opened_at = doc.get("openedAt") # Convex uses camelCase
                if isinstance(opened_at, str):
                    try:
                        opened_at = datetime.fromisoformat(opened_at.replace('Z', '+00:00'))
                    except ValueError:
                        opened_at = datetime.utcnow()

                pos = ActivePosition(
                    position_id=doc["positionId"],
                    user_id=doc["userId"],
                    token=doc["token"],
                    action=doc["action"],
                    entry_price=float(doc["entryPrice"]),
                    current_price=float(doc.get("currentPrice", doc["entryPrice"])),
                    position_size_usd=float(doc["positionSizeUsd"]),
                    remaining_size_usd=float(doc.get("remainingSizeUsd", doc["positionSizeUsd"])),
                    sl_price=float(doc["stopLossPrice"]),
                    tp1_price=float(doc["tp1Price"]),
                    tp1_hit=bool(doc.get("tp1Hit", False)),
                    tp2_price=float(doc["tp2Price"]),
                    trailing_stop_pct=float(doc.get("trailingStopPct", 0.03)),
                    trailing_stop_price=float(doc.get("trailingStopPrice", 0)),
                    paper_trade=self.paper_trade_enabled,
                    status="OPEN",
                    opened_at=opened_at,
                    closed_at=None,
                    pnl_usd=float(doc.get("pnlUsd", 0.0)),
                    signal_id=doc.get("signalId", "unknown"),
                    strategy_breakdown=doc.get("strategyBreakdown", []),
                    sl_tp_rationale=doc.get("slTpRationale")
                )
                
                self.active_positions[pos.position_id] = pos
                
                if pos.token not in self.ws_subscriptions:
                    self.ws_subscriptions[pos.token] = set()
                self.ws_subscriptions[pos.token].add(pos.position_id)
                
                recovered_count += 1
            
            logger.info(f"[AGENT_8] Recovered {recovered_count} OPEN positions from database.")
            
            # Start WebSocket task
            if self._ws_task is None or self._ws_task.done():
                self._ws_task = asyncio.create_task(self._run_websocket_monitor())
                
            # Start Heartbeat task
            if self._monitor_task is None or self._monitor_task.done():
                self._monitor_task = asyncio.create_task(self._position_heartbeat())
                
        except Exception as e:
            logger.error(f"[AGENT_8] Error recovering open positions: {e}")
            await self._ingest_to_axiom("pixelfirm-errors", {
                "agent": "agent_8",
                "error_type": "RECOVERY_FAILED",
                "message": str(e),
                "stack_trace": traceback.format_exc()
            })

    # ── AXIOM OBSERVABILITY ────────────────────────────────────────────────

    async def _ingest_to_axiom(self, dataset: str, event: dict):
        """
        Fire-and-forget Axiom ingestion.
        Never blocks the trade execution path.
        Errors are logged locally but do not propagate.
        """
        if not self.axiom_enabled:
            logger.debug(f"[AXIOM MOCK] {dataset}: {json.dumps(event)}")
            return

        try:
            event["_time"] = datetime.utcnow().isoformat() + "Z"
            # Axiom-py is synchronous right now, wrap in thread executor
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: self.axiom.ingest_events(dataset=dataset, events=[event])
            )
        except Exception as e:
            # Log to local file — never raise, never block trading
            logger.error(f"Axiom ingestion failed for {dataset}: {e}")

    # ── MOCK EXECUTION ─────────────────────────────────────────────────────

    async def _execute_stock_mock(self, instruction: TradeInstruction) -> Dict:
        """Simulate stock execution using real-time Yahoo Finance data."""
        ticker = instruction.token
        logger.info(f"🤖 [AGENT_8] Executing MOCK STOCK order for {ticker}...")
        
        try:
            stock = yf.Ticker(ticker)
            history = stock.history(period="1d", interval="1m")
            if history.empty:
                return {"status": "REJECTED", "reason": "No market data available for stock"}
            
            fill_price = float(history.iloc[-1]['Close'])
            position_id = f"pos_stock_{int(datetime.utcnow().timestamp())}"
            
            # Create internal position object
            new_pos = ActivePosition(
                position_id=position_id,
                user_id=instruction.user_id,
                token=ticker,
                action=instruction.action,
                entry_price=fill_price,
                current_price=fill_price,
                position_size_usd=instruction.position_size_usd,
                remaining_size_usd=instruction.position_size_usd,
                sl_price=instruction.sl_price,
                tp1_price=instruction.tp1_price,
                tp1_hit=False,
                tp2_price=instruction.tp2_price,
                trailing_stop_pct=instruction.trailing_stop_pct,
                trailing_stop_price=fill_price * (1.0 - instruction.trailing_stop_pct) if instruction.action.upper() == "BUY" else fill_price * (1.0 + instruction.trailing_stop_pct),
                paper_trade=True,
                status="OPEN",
                opened_at=datetime.utcnow(),
                closed_at=None,
                pnl_usd=0.0,
                signal_id=instruction.signal_id,
                asset_type="stock",
                strategy_breakdown=instruction.strategy_breakdown,
                sl_tp_rationale=instruction.sl_tp_rationale
            )
            
            self.active_positions[position_id] = new_pos
            
            # Log to DB
            await self.db.log_trade({
                "trade_id": position_id,
                "token_symbol": ticker,
                "entry_price": fill_price,
                "status": "open",
                "asset_type": "stock",
                "paper_trade": True,
                "signal_id": instruction.signal_id
            })
            
            return {
                "status": "FILLED",
                "position_id": position_id,
                "fill_price": fill_price,
                "asset_type": "stock"
            }
            
        except Exception as e:
            logger.error(f"Stock mock execution failed: {e}")
            return {"status": "REJECTED", "reason": str(e)}

    async def _execute_mock(self, instruction: TradeInstruction) -> float:
        """
        Paper trading fill simulator.
        Fetches current market price from Binance REST for realistic fill.
        Returns fill_price.
        """
        token = instruction.token
        url = f"https://api.binance.com/api/v3/ticker/price?symbol={token.upper()}"
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=5) as response:
                    if response.status == 200:
                        data = await response.json()
                        return float(data["price"])
                    else:
                        raise ValueError(f"Binance return status {response.status}")
        except Exception as e:
            logger.warning(f"[AGENT_8] Binance price fetch failed for {token}: {e}. Trying Bybit fallback.")
            try:
                # Bybit Fallback
                bybit_url = f"https://api.bybit.com/v5/market/tickers?category=spot&symbol={token.upper()}"
                async with aiohttp.ClientSession() as session:
                    async with session.get(bybit_url, timeout=5) as response:
                        if response.status == 200:
                            data = await response.json()
                            if data.get("retCode") == 0 and len(data.get("result", {}).get("list", [])) > 0:
                                return float(data["result"]["list"][0]["lastPrice"])
            except Exception as e2:
                logger.error(f"[AGENT_8] Bybit fallback failed for {token}: {e2}.")
        
        # Absolute fallback if all REST fails is just the instruction price
        logger.warning(f"[AGENT_8] Mock execution totally failed. Falling back to instruction entry price: {instruction.entry_price}")
        return float(instruction.entry_price)

    # ── MAIN TRADE EXECUTION ───────────────────────────────────────────────

    async def execute_trade(self, instruction: TradeInstruction) -> dict:
        """
        Primary entry point called by Agent-7.
        Validates instruction, simulates fill, creates ActivePosition,
        persists to DB, and registers WebSocket subscription.
        """
        start_time = datetime.utcnow()
        
        # 1. Validation check
        if instruction is None or not instruction.token or instruction.position_size_usd <= 0:
            return {"status": "REJECTED", "reason": "INVALID_INSTRUCTION"}
            
        # 2. Check for single position limitation
        for pos in self.active_positions.values():
            if pos.user_id == instruction.user_id and pos.token == instruction.token and pos.status == "OPEN":
                return {"status": "REJECTED", "reason": "DUPLICATE_POSITION"}

        try:
            # 3. Branching based on asset type
            asset_type = getattr(instruction, 'asset_type', 'solana_meme')
            if asset_type == 'stock':
                return await self._execute_stock_mock(instruction)

            # 4. Paper trading fill simulation
            fill_price = await self._execute_mock(instruction)
            
            # 4. Calculate initial trailing stop
            if instruction.action.upper() == "BUY":
                initial_trailing_stop = fill_price * (1.0 - instruction.trailing_stop_pct)
            else: # SELL
                initial_trailing_stop = fill_price * (1.0 + instruction.trailing_stop_pct)

            # 5. Construct ActivePosition
            position_id = f"pos_{uuid.uuid4().hex[:8]}"
            pos = ActivePosition(
                position_id=position_id,
                user_id=instruction.user_id,
                token=instruction.token,
                action=instruction.action,
                entry_price=fill_price,
                current_price=fill_price,
                position_size_usd=instruction.position_size_usd,
                remaining_size_usd=instruction.position_size_usd,
                sl_price=instruction.sl_price,
                tp1_price=instruction.tp1_price,
                tp1_hit=False,
                tp2_price=instruction.tp2_price,
                trailing_stop_pct=instruction.trailing_stop_pct,
                trailing_stop_price=initial_trailing_stop,
                paper_trade=self.paper_trade_enabled,
                status="OPEN",
                opened_at=datetime.utcnow(),
                closed_at=None,
                pnl_usd=0.0,
                signal_id=instruction.signal_id,
                strategy_breakdown=instruction.strategy_breakdown,
                sl_tp_rationale=instruction.sl_tp_rationale,
                asset_type=asset_type
            )


            # 6. Write to Convex
            await self.db.log_trade({
                "trade_id": position_id,
                "signal_id": instruction.signal_id,
                "token_address": instruction.token, # Mapping token symbol to address for now if address missing
                "entry_price": fill_price,
                "entry_time": pos.opened_at.isoformat(),
                "position_size_usd": instruction.position_size_usd,
                "status": "open",
                "stop_loss_price": instruction.sl_price,
                "tp1_price": instruction.tp1_price,
                "tp2_price": instruction.tp2_price,
                "paper_trade": self.paper_trade_enabled
            })

            # 6b. Notify Telegram
            if self.agent_9:
                try:
                    await self.agent_9.notify_trade_opened(pos)
                except Exception as eval_err:
                    logger.error(f"[AGENT_8] Could not notify Agent 9 of entry: {eval_err}")

            # 7. Add to memory and 8. Register WS Sub
            self.active_positions[position_id] = pos
            if pos.token not in self.ws_subscriptions:
                self.ws_subscriptions[pos.token] = set()
                # Need to trigger a reconnect to pick up the new stream
                if self._ws_task and not self._ws_task.done():
                    self._ws_task.cancel() # Handled properly in the loop
            
            self.ws_subscriptions[pos.token].add(position_id)

            # 9. Ingest events
            await self._ingest_to_axiom("pixelfirm-trades", {
                "user_id": pos.user_id,
                "position_id": pos.position_id,
                "signal_id": pos.signal_id,
                "token": pos.token,
                "action": pos.action,
                "event_type": "OPEN",
                "exit_reason": None,
                "entry_price": pos.entry_price,
                "exit_price": None,
                "position_size_usd": pos.position_size_usd,
                "exited_size_usd": 0.0,
                "pnl_usd": 0.0,
                "execution_type": "paper",
                "duration_seconds": 0
            })
            
            latency_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            await self._ingest_to_axiom("pixelfirm-agent-latency", {
                "signal_id": pos.signal_id,
                "agent": "agent_8",
                "event": "trade_executed",
                "latency_ms": latency_ms,
                "upstream_agent": "agent_7"
            })
            
            logger.info(f"[AGENT_8] 🚀 TRADE EXECUTED: Added {pos.action} {pos.token} @ ${fill_price:.4f} for user {pos.user_id}")
            return {"status": "FILLED", "position_id": position_id, "fill_price": fill_price, "paper": True}
            
        except Exception as e:
            logger.error(f"[AGENT_8] Trade execution failed: {e}")
            await self._ingest_to_axiom("pixelfirm-errors", {
                "agent": "agent_8",
                "error_type": "EXECUTION_FAILED",
                "token": instruction.token,
                "user_id": instruction.user_id,
                "message": str(e),
                "stack_trace": traceback.format_exc()
            })
            return {"status": "FAILED", "reason": str(e)}

    # ── PLACEHOLDERS FOR WEBSOCKET AND EXITS (Coming next) ─────────────────
    
    async def _run_websocket_monitor(self):
        """
        Maintains a single Binance WebSocket connection subscribing to
        all tokens with open positions. Handles reconnection automatically.
        """
        logger.info("[AGENT_8] Starting Binance WebSocket monitor...")
        
        while True:
            # If no subscriptions, ping gently and wait
            if not self.ws_subscriptions:
                await asyncio.sleep(5)
                continue
                
            streams = "/".join([f"{token.lower()}@ticker" for token in self.ws_subscriptions.keys()])
            url = f"wss://stream.binance.com:9443/stream?streams={streams}"
            
            try:
                async with websockets.connect(url, ping_interval=20, ping_timeout=20) as ws:
                    logger.info(f"[AGENT_8] Connected to WS streams: {streams}")
                    
                    while True:
                        msg = await ws.recv()
                        data = json.loads(msg)
                        
                        if "data" in data and "s" in data["data"] and "c" in data["data"]:
                            symbol = data["data"]["s"]
                            current_price = float(data["data"]["c"])
                            
                            # Protect dictionary iteration
                            pos_ids_to_eval = set(self.ws_subscriptions.get(symbol, []))
                            for pos_id in pos_ids_to_eval:
                                if pos_id in self.active_positions:
                                    pos = self.active_positions[pos_id]
                                    await self._evaluate_position_exits(pos, current_price)
                                    
            except asyncio.CancelledError:
                logger.info("[AGENT_8] WebSocket monitor cancelled (likely reconnecting due to sub change).")
                break
            except websockets.exceptions.ConnectionClosed as e:
                logger.warning(f"[AGENT_8] WebSocket disconnected: {e}. Reconnecting in 2s...")
                await asyncio.sleep(2)
            except Exception as e:
                logger.error(f"[AGENT_8] WebSocket error: {e}")
                await self._ingest_to_axiom("pixelfirm-errors", {
                    "agent": "agent_8",
                    "error_type": "WS_DISCONNECT",
                    "message": str(e),
                    "stack_trace": traceback.format_exc()
                })
                await asyncio.sleep(2)
        
    async def _evaluate_position_exits(self, position: ActivePosition, current_price: float):
        """
        Evaluates SL, TP1, TP2, and trailing stop conditions on price ticks.
        Priority order: SL > Trailing Stop > TP2 > TP1
        """
        position.current_price = current_price
        
        exit_triggered = False
        exit_reason = None
        is_full_exit = False
        exit_pct = 0.0

        is_buy = position.action.upper() == "BUY"

        # 1. STOP LOSS CHECK
        if is_buy and current_price <= position.sl_price:
            exit_triggered, is_full_exit, exit_reason, exit_pct = True, True, "STOP_LOSS", 1.0
        elif not is_buy and current_price >= position.sl_price:
            exit_triggered, is_full_exit, exit_reason, exit_pct = True, True, "STOP_LOSS", 1.0

        # 2. TRAILING STOP CHECK
        if not exit_triggered:
            if is_buy:
                if current_price > position.entry_price:
                    new_trail = current_price * (1.0 - position.trailing_stop_pct)
                    if new_trail > position.trailing_stop_price:
                        position.trailing_stop_price = new_trail
                
                if current_price <= position.trailing_stop_price:
                    exit_triggered, is_full_exit, exit_reason, exit_pct = True, True, "TRAILING_STOP", 1.0
            else: # SELL
                if current_price < position.entry_price:
                    new_trail = current_price * (1.0 + position.trailing_stop_pct)
                    if new_trail < position.trailing_stop_price:
                        position.trailing_stop_price = new_trail
                        
                if current_price >= position.trailing_stop_price:
                    exit_triggered, is_full_exit, exit_reason, exit_pct = True, True, "TRAILING_STOP", 1.0

        # 3. TAKE PROFIT 2 CHECK (Full Exit)
        if not exit_triggered:
            if is_buy and current_price >= position.tp2_price:
                exit_triggered, is_full_exit, exit_reason, exit_pct = True, True, "TP2", 1.0
            elif not is_buy and current_price <= position.tp2_price:
                exit_triggered, is_full_exit, exit_reason, exit_pct = True, True, "TP2", 1.0

        # 4. TAKE PROFIT 1 CHECK (Partial Exit)
        if not exit_triggered and not position.tp1_hit:
            trigger_tp1 = False
            if is_buy and current_price >= position.tp1_price: trigger_tp1 = True
            elif not is_buy and current_price <= position.tp1_price: trigger_tp1 = True
            
            if trigger_tp1:
                exit_triggered, is_full_exit, exit_reason = True, False, "TP1_PARTIAL"
                exit_pct = 0.50 # Assuming 50% exit at TP1 per spec if not explicitly passed

        # 0. DYNAMIC STOP ADJUSTMENT (NEW)
        # --------------------------------
        # Phase 1: At +20% profit, move SL to entry + 1%
        # Phase 2: At +50% profit, move SL to +30%
        if not exit_triggered:
            price_change_pct = (current_price / position.entry_price - 1.0) if is_buy else (1.0 - current_price / position.entry_price)
            
            if price_change_pct >= 0.50:
                new_sl = position.entry_price * 1.30 if is_buy else position.entry_price * 0.70
                if (is_buy and new_sl > position.sl_price) or (not is_buy and new_sl < position.sl_price):
                    position.sl_price = new_sl
                    logger.info(f"[AGENT_8] 🛡️ Dynamic SL Phase 2: Moved to +30% for {position.token}")
            elif price_change_pct >= 0.20:
                new_sl = position.entry_price * 1.01 if is_buy else position.entry_price * 0.99
                if (is_buy and new_sl > position.sl_price) or (not is_buy and new_sl < position.sl_price):
                    position.sl_price = new_sl
                    logger.info(f"[AGENT_8] 🛡️ Dynamic SL Phase 1: Moved to Breakeven (+1%) for {position.token}")

        if not exit_triggered:
            return  # Price tick evaluated, no action

        # ── EXECUTE EXIT LOGIC ──

        exited_size_usd = position.remaining_size_usd * exit_pct
        
        pnl_multiplier = current_price / position.entry_price if position.entry_price > 0 else 1.0
        if not is_buy: pnl_multiplier = 2.0 - pnl_multiplier  # invert for shorts
        
        realized_pnl_usd = exited_size_usd * (pnl_multiplier - 1.0)
        position.pnl_usd += realized_pnl_usd

        if is_full_exit:
            position.status = "CLOSED"
            position.closed_at = datetime.utcnow()
            position.remaining_size_usd = 0.0
            
            # Remove from active lists
            if position.position_id in self.active_positions:
                del self.active_positions[position.position_id]
                
            if position.token in self.ws_subscriptions and position.position_id in self.ws_subscriptions[position.token]:
                self.ws_subscriptions[position.token].remove(position.position_id)
                # If no more subs for this token, trigger WS reconnect to drop the stream
                if not self.ws_subscriptions[position.token]:
                    del self.ws_subscriptions[position.token]
                    if self._ws_task and not self._ws_task.done():
                        self._ws_task.cancel()
            
            # Update in Convex
            await self.db.update_trade(position.position_id, {
                "status": "closed",
                "exitPrice": current_price,
                "exitTime": position.closed_at.isoformat(),
                "pnlUsd": position.pnl_usd
            })
                
            logger.info(f"[AGENT_8] 🔴 FULL EXIT ({exit_reason}): {position.token} PnL: ${realized_pnl_usd:.2f}")

            if self.agent_9:
                try:
                    await self.agent_9.notify_trade_closed(position, exit_reason)
                except Exception as eval_err:
                    logger.error(f"[AGENT_8] Could not notify Agent 9 of exit: {eval_err}")

        else: # Partial TP1
            position.tp1_hit = True
            position.remaining_size_usd -= exited_size_usd
            position.status = "PARTIAL"
            
            # Update in Convex
            await self.db.update_trade(position.position_id, {
                "status": "partial",
                "remainingSizeUsd": position.remaining_size_usd,
                "tp1Hit": True,
                "pnlUsd": position.pnl_usd
            })
            logger.info(f"[AGENT_8] 🟡 PARTIAL EXIT ({exit_reason}): {position.token} PnL: ${realized_pnl_usd:.2f}")

            if self.agent_9:
                try:
                    await self.agent_9.notify_trade_closed(position, "TP1_PARTIAL")
                except Exception as eval_err:
                    logger.error(f"[AGENT_8] Could not notify Agent 9 of partial exit: {eval_err}")

        # Axiom logging
        await self._ingest_to_axiom("pixelfirm-trades", {
            "user_id": position.user_id,
            "position_id": position.position_id,
            "signal_id": position.signal_id,
            "token": position.token,
            "action": position.action,
            "event_type": "CLOSE" if is_full_exit else "PARTIAL_CLOSE",
            "exit_reason": exit_reason,
            "entry_price": position.entry_price,
            "exit_price": current_price,
            "position_size_usd": position.position_size_usd,
            "exited_size_usd": exited_size_usd,
            "pnl_usd": realized_pnl_usd,
            "execution_type": "paper",
            "duration_seconds": int((datetime.utcnow() - position.opened_at).total_seconds())
        })

    async def liquidate_all_positions(self, user_id: str, execution_type: str = "market") -> dict:
        """
        Called by Agent-7 when Tier 3 kill switch activates.
        Force closes all open positions for that user at market or via priority limit.
        """
        logger.warning(f"[AGENT_8] 🚨 EMERGENCY LIQUIDATION TRIGGERED: mode={execution_type} user={user_id}")
        
        liquidated_count = 0
        total_pnl = 0.0
        
        positions_to_close = [pos for pos in self.active_positions.values() if pos.user_id == user_id]
        
        for position in positions_to_close:
            try:
                # 1. Fetch live REST snapshot
                url = f"https://api.binance.com/api/v3/ticker/price?symbol={position.token.upper()}"
                exit_price = position.entry_price # Fallback
                
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, timeout=3) as response:
                        if response.status == 200:
                            data = await response.json()
                            exit_price = float(data["price"])

                # 2. Calculate PnL
                exited_size_usd = position.remaining_size_usd
                pnl_multiplier = exit_price / position.entry_price if position.entry_price > 0 else 1.0
                if position.action.upper() != "BUY": pnl_multiplier = 2.0 - pnl_multiplier
                
                realized_pnl_usd = exited_size_usd * (pnl_multiplier - 1.0)
                position.pnl_usd += realized_pnl_usd
                total_pnl += realized_pnl_usd
                
                # 3. Update State
                position.status = "CLOSED"
                position.closed_at = datetime.utcnow()
                position.remaining_size_usd = 0.0
                
                if position.position_id in self.active_positions:
                    del self.active_positions[position.position_id]
                    
                if position.token in self.ws_subscriptions and position.position_id in self.ws_subscriptions[position.token]:
                    self.ws_subscriptions[position.token].remove(position.position_id)
                    # Note: We do NOT trigger a WS reconnect inside this loop. 
                    # We'll let it cleanly disconnect/reconnect on the next tick to avoid spam.
                
                # 4. Write to Convex
                await self.db.update_trade(position.position_id, {
                    "status": "closed",
                    "exitPrice": exit_price,
                    "exitTime": position.closed_at.isoformat(),
                    "pnlUsd": position.pnl_usd,
                    "forceClosed": True
                })

                # 5. Axiom Log
                await self._ingest_to_axiom("pixelfirm-trades", {
                    "user_id": position.user_id,
                    "position_id": position.position_id,
                    "signal_id": position.signal_id,
                    "token": position.token,
                    "action": position.action,
                    "event_type": "CLOSE",
                    "exit_reason": "KILL_SWITCH_TIER3",
                    "entry_price": position.entry_price,
                    "exit_price": exit_price,
                    "position_size_usd": position.position_size_usd,
                    "exited_size_usd": exited_size_usd,
                    "pnl_usd": realized_pnl_usd,
                    "execution_type": "paper",
                    "duration_seconds": int((datetime.utcnow() - position.opened_at).total_seconds())
                })
                
                liquidated_count += 1
                
            except Exception as e:
                # Catch per-position failure to ensure the rest still liquidate
                logger.error(f"[AGENT_8] Liquidation failed for pos {position.position_id}: {e}")
                
        return {"liquidated": liquidated_count, "total_pnl_usd": total_pnl, "user_id": user_id}

    async def _position_heartbeat(self):
        """
        Logs position status to Axiom every 60 seconds
        """
        while True:
            try:
                await asyncio.sleep(60)
                
                for pos_id, pos in list(self.active_positions.items()):
                    await self._ingest_to_axiom("pixelfirm-positions", {
                        "user_id": pos.user_id,
                        "position_id": pos.position_id,
                        "token": pos.token,
                        "current_price": pos.current_price,
                        "sl_price": pos.sl_price,
                        "tp1_price": pos.tp1_price,
                        "tp2_price": pos.tp2_price,
                        "trailing_stop_price": pos.trailing_stop_price,
                        "tp1_hit": pos.tp1_hit,
                        "remaining_size_usd": pos.remaining_size_usd,
                        "unrealized_pnl_usd": pos.pnl_usd,  # Current realized + paper unrealized approx
                        "trigger": "HEARTBEAT"
                    })
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[AGENT_8] Heartbeat log error: {e}")
