# Agent-8: Trading Bot (Execution Layer) — Implementation Spec

## Overview

Agent-8 is the terminal execution layer of the PixelFirm pipeline. It receives fully
vetted `TradeInstruction` objects from Agent-7 (Risk Manager) and simulates market
execution in paper trading mode. It manages all open positions, monitors live prices
via Binance WebSocket, and triggers SL/TP/trailing stop exits autonomously. All
activity is streamed to Axiom for observability.

**Current mode: PAPER TRADING**
When production is ready, only `_execute_mock()` is replaced with `_execute_jupiter()`.
No other logic changes.

---

## File Location

```
backend/src/agents/agent_8_trading_bot.py
```

---

## Dependencies

```
# requirements.txt additions
websockets>=12.0
aiohttp>=3.9.0
axiom-py>=1.0.0      # Axiom Python client for observability ingestion
```

---

## Data Contracts

### Input: TradeInstruction (received from Agent-7)

```python
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
```

### Internal: ActivePosition (stored in MongoDB + in-memory)

```python
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
```

---

## Class Structure

```python
class TradingBot:
    def __init__(self, db_client, axiom_client):
        self.db = db_client
        self.axiom = axiom_client
        self.active_positions: Dict[str, ActivePosition] = {}  # position_id → position
        self.ws_subscriptions: Dict[str, set] = {}             # token → set of position_ids
        self._ws_task: Optional[asyncio.Task] = None
        self._monitor_task: Optional[asyncio.Task] = None
```

---

## Core Methods

### 1. Startup & Recovery

```python
async def start(self):
    """
    On boot, reload all OPEN positions from MongoDB into memory.
    This ensures positions survive server restarts.
    Re-subscribes to WebSocket feeds for all active tokens.
    """
```

- Query MongoDB `active_positions` collection for all docs with `status: "OPEN"`
- Reconstruct `ActivePosition` objects into `self.active_positions`
- Launch `_run_websocket_monitor()` as an asyncio task
- Launch `_position_heartbeat()` as an asyncio task (logs position count to Axiom every 60s)

---

### 2. Trade Execution Entry Point

```python
async def execute_trade(self, instruction: TradeInstruction) -> dict:
    """
    Primary entry point called by Agent-7.
    Validates instruction, simulates fill, creates ActivePosition,
    persists to DB, and registers WebSocket subscription.
    """
```

**Execution flow:**
1. Validate `instruction` is not None and all required fields are present
2. Check `self.active_positions` — if a position for the same `(user_id, token)` is already OPEN, reject with reason `"DUPLICATE_POSITION"`
3. Call `_execute_mock(instruction)` → returns `fill_price` (current market price from Binance REST snapshot)
4. Calculate initial `trailing_stop_price`:
   - For BUY: `trailing_stop_price = fill_price * (1 - trailing_stop_pct)`
   - For SELL: `trailing_stop_price = fill_price * (1 + trailing_stop_pct)`
5. Construct `ActivePosition` object with `paper_trade=True`, `status="OPEN"`
6. Write to MongoDB `active_positions` collection
7. Add to `self.active_positions` in-memory dict
8. Register token subscription in `self.ws_subscriptions`
9. Ingest trade open event to Axiom dataset `pixelfirm-trades`
10. Return `{"status": "FILLED", "position_id": ..., "fill_price": ..., "paper": True}`

---

### 3. Mock Execution

```python
async def _execute_mock(self, instruction: TradeInstruction) -> float:
    """
    Paper trading fill simulator.
    Fetches current market price from Binance REST for realistic fill.
    Returns fill_price.

    PRODUCTION REPLACEMENT POINT:
    Replace this method body with Jupiter swap transaction logic.
    All caller code remains identical.
    """
```

- Calls `GET https://api.binance.com/api/v3/ticker/price?symbol={token}`
- Bybit fallback if Binance fails (same pattern as Agent-6)
- Returns `float(response["price"])`
- Logs mock fill to Axiom with `execution_type: "paper"`

---

### 4. WebSocket Price Monitor

```python
async def _run_websocket_monitor(self):
    """
    Maintains a single Binance WebSocket connection subscribing to
    all tokens with open positions. Handles reconnection automatically.
    On each price tick, calls _evaluate_position_exits() for all
    matching open positions.
    """
```

**Implementation details:**
- Connect to `wss://stream.binance.com:9443/stream?streams=<stream_list>`
- Stream list is built dynamically from `self.ws_subscriptions` keys
  - Format: `solusdt@ticker` per token (lowercase)
- On each incoming message, extract `symbol` and `c` (current price)
- Look up all position_ids in `self.ws_subscriptions[symbol]`
- Call `await _evaluate_position_exits(position, current_price)` for each
- **Reconnection:** wrap entire loop in `while True` with `try/except`. On disconnect, sleep 2s and reconnect. Log reconnect event to Axiom `pixelfirm-errors`
- **Dynamic resubscription:** when a new position is added or closed, rebuild and reconnect the WebSocket stream list

---

### 5. Position Exit Evaluation (called on every price tick)

```python
async def _evaluate_position_exits(self, position: ActivePosition, current_price: float):
    """
    Core exit logic. Evaluates SL, TP1, TP2, and trailing stop
    conditions on every price tick for a given position.
    Priority order: SL > Trailing Stop > TP2 > TP1
    """
```

**Exit priority order (checked in sequence, first match wins):**

#### Stop Loss Check
```
BUY position:  current_price <= sl_price  → FULL EXIT, reason="STOP_LOSS"
SELL position: current_price >= sl_price  → FULL EXIT, reason="STOP_LOSS"
```

#### Trailing Stop Update + Check
```
BUY position:
  if current_price > position.entry_price:  # Only trail in profit
    new_trail = current_price * (1 - trailing_stop_pct)
    if new_trail > position.trailing_stop_price:
        position.trailing_stop_price = new_trail  # Ratchet up, never down
  if current_price <= position.trailing_stop_price → FULL EXIT, reason="TRAILING_STOP"

SELL position: mirror logic, trail downward
```

#### TP2 Check (full exit)
```
BUY position:  current_price >= tp2_price  → FULL EXIT, reason="TP2"
SELL position: current_price <= tp2_price  → FULL EXIT, reason="TP2"
```

#### TP1 Check (partial exit — only if tp1_hit is False)
```
BUY position:  current_price >= tp1_price AND NOT tp1_hit
  → PARTIAL EXIT of (tp1_exit_pct * remaining_size_usd)
  → Set tp1_hit = True
  → Update remaining_size_usd
  → reason="TP1_PARTIAL"

SELL position: mirror logic
```

**On any exit event:**
1. Calculate `pnl_usd` for the exited portion
2. Update `ActivePosition` in memory and MongoDB
3. If FULL EXIT: set `status="CLOSED"`, `closed_at=now()`, remove from `self.active_positions`, unsubscribe token if no other positions need it
4. If PARTIAL EXIT: set `status="PARTIAL"`, update `remaining_size_usd`
5. Ingest exit event to Axiom `pixelfirm-positions`
6. Send Telegram notification to user (via Agent-9 interface or direct bot message)

---

### 6. Emergency Liquidation (Kill Switch Tier 3)

```python
async def liquidate_all_positions(self, user_id: str) -> dict:
    """
    Called by Agent-7 when Tier 3 kill switch activates for a user.
    Immediately closes ALL open positions for that user at current market price.
    Cancels any pending evaluation logic for those positions.
    Cannot be interrupted or queued — runs synchronously within the async loop.
    """
```

**Flow:**
1. Filter `self.active_positions` for all positions matching `user_id`
2. For each position, fetch current price via Binance REST (NOT WebSocket — need immediate snapshot)
3. Call `_close_position(position, current_price, reason="KILL_SWITCH_TIER3")`
4. Mark all as `status="CLOSED"` in MongoDB with `force_closed=True` flag
5. Ingest each closure to Axiom `pixelfirm-trades` with `exit_reason: "KILL_SWITCH_TIER3"`
6. Return `{"liquidated": N, "total_pnl_usd": X, "user_id": user_id}`

> ⚠️ This method must complete even if individual position closures fail.
> Use `try/except` per position and collect errors — never let one failed
> closure abort the rest of the liquidation loop.

---

## Axiom Observability Integration

### Client Setup

```python
from axiom_py import Client as AxiomClient

axiom_client = AxiomClient(token=os.environ["AXIOM_API_TOKEN"])
```

### Datasets and Event Schemas

#### `pixelfirm-trades` — every entry and exit event

```json
{
  "user_id": "usr_abc123",
  "position_id": "pos_xyz789",
  "signal_id": "sig_111",
  "token": "SOLUSDT",
  "action": "BUY",
  "event_type": "OPEN | CLOSE | PARTIAL_CLOSE",
  "exit_reason": "TP1_PARTIAL | TP2 | STOP_LOSS | TRAILING_STOP | KILL_SWITCH_TIER3 | null",
  "entry_price": 145.30,
  "exit_price": 152.10,
  "position_size_usd": 250.00,
  "exited_size_usd": 125.00,
  "pnl_usd": 5.83,
  "execution_type": "paper",
  "duration_seconds": 3420,
  "_time": "2025-01-15T14:32:00Z"
}
```

#### `pixelfirm-positions` — SL/TP trigger events (position monitor ticks)

```json
{
  "user_id": "usr_abc123",
  "position_id": "pos_xyz789",
  "token": "SOLUSDT",
  "current_price": 152.10,
  "sl_price": 138.50,
  "tp1_price": 150.00,
  "tp2_price": 158.00,
  "trailing_stop_price": 147.60,
  "tp1_hit": true,
  "remaining_size_usd": 125.00,
  "unrealized_pnl_usd": 4.20,
  "trigger": "TP1_PARTIAL",
  "_time": "2025-01-15T14:32:00Z"
}
```

#### `pixelfirm-killswitch` — kill switch events (written by Agent-7, read here for reference)

```json
{
  "user_id": "usr_abc123",
  "event_type": "activated | resumed",
  "tier": 3,
  "triggered_by": "system | user | admin",
  "trigger_reason": "daily_loss_limit_breached",
  "positions_liquidated": 3,
  "_time": "2025-01-15T14:32:00Z"
}
```

#### `pixelfirm-agent-latency` — pipeline timing

```json
{
  "signal_id": "sig_111",
  "agent": "agent_8",
  "event": "trade_executed",
  "latency_ms": 42,
  "upstream_agent": "agent_7",
  "_time": "2025-01-15T14:32:00Z"
}
```

#### `pixelfirm-errors` — exceptions and reconnections

```json
{
  "agent": "agent_8",
  "error_type": "WS_DISCONNECT | EXECUTION_FAILED | PRICE_FETCH_FAILED",
  "token": "SOLUSDT",
  "user_id": "usr_abc123",
  "message": "WebSocket disconnected, reconnecting...",
  "stack_trace": "...",
  "_time": "2025-01-15T14:32:00Z"
}
```

### Ingestion Pattern

```python
async def _ingest_to_axiom(self, dataset: str, event: dict):
    """
    Fire-and-forget Axiom ingestion.
    Never blocks the trade execution path.
    Errors are logged locally but do not propagate.
    """
    try:
        event["_time"] = datetime.utcnow().isoformat() + "Z"
        await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: self.axiom.ingest_events(dataset=dataset, events=[event])
        )
    except Exception as e:
        # Log to local file — never raise, never block trading
        logger.error(f"Axiom ingestion failed for {dataset}: {e}")
```

> ⚠️ Axiom ingestion is ALWAYS fire-and-forget. A failure to log must never
> block, delay, or raise an exception in the trade execution path.

---

## MongoDB Collections

### `active_positions`

```
Index: { user_id: 1, status: 1 }        — for liquidation lookups
Index: { position_id: 1 }               — unique, for direct lookups
Index: { token: 1, status: 1 }          — for WebSocket subscription rebuilds
```

### `closed_positions`

- Move closed `ActivePosition` docs here on full exit (keeps `active_positions` lean)
- Never delete — full audit trail of all paper trades

---

## Verification Plan

### Automated Tests

- Mock `_execute_mock()` to return a fixed fill price. Submit a `TradeInstruction`
  and assert an `ActivePosition` is created in MongoDB with correct field values.
- Feed a sequence of simulated price ticks to `_evaluate_position_exits()` and assert:
  - TP1 fires at the right price, `remaining_size_usd` is reduced by `tp1_exit_pct`
  - TP2 fires only after TP1 has been hit, position status becomes `CLOSED`
  - SL fires before TP1 if price drops below `sl_price`
  - Trailing stop ratchets up correctly and fires when price reverses
- Call `liquidate_all_positions(user_id)` with 3 mock open positions. Assert all 3
  are closed, `force_closed=True`, and `exit_reason="KILL_SWITCH_TIER3"`.
- Assert that a single failed position closure in liquidation does not abort the
  other two (error isolation test).
- Assert that Axiom ingestion failures do not raise exceptions or block execution.

### Manual Verification

- Start the server with 0 open positions. Submit a test `TradeInstruction` via
  Agent-7 and verify the position appears in MongoDB with `status="OPEN"`.
- Observe Axiom dataset `pixelfirm-trades` and confirm the OPEN event was ingested.
- Manually set `current_price` above `tp1_price` in the WebSocket mock and confirm
  a partial exit fires and `remaining_size_usd` is updated correctly.
- Manually trigger a Tier 3 kill switch for the test user and confirm all open
  positions are liquidated and visible in Axiom `pixelfirm-killswitch`.
- Restart the server mid-test with open positions in MongoDB. Confirm Agent-8
  recovers all positions into memory on boot without duplicates.
