# PHASE 2 SPECIFICATION - SOLANA ON-CHAIN INTELLIGENCE

**Objective:** Build the Researcher Bot's on-chain data pipeline and signal generation engine.

**Timeline:** 7-10 days  
**Scope:** Dexscreener API, rug detection, holder analysis, AI scoring, signal formatting  
**Output:** Fully functional signal discovery with 6-point filter + AI confidence scoring

---

## 1. PHASE 2 OVERVIEW

### What Gets Built
Layer 1-3 of the signal pipeline (data collection → mandatory filters → AI scoring)

```
Dexscreener Stream → Rug Detector → Holder Analysis → AI Scorer → Signal Output
```

### What's NOT Included
- Trading execution (Phase 4)
- Smart wallet tracking (Phase 3)
- Social layer (Phase 5)
- Position management (Phase 4)

### Success Criteria
- ✅ Detects new Raydium tokens in <30 seconds
- ✅ All 6 rug filters working (contract age, liquidity, holders, volume, deployer, data)
- ✅ Confidence scores in 6-10 range (no <6 signals sent)
- ✅ Position sizing deterministic ($2 for 8-10, $1 for 6-7)
- ✅ Signals sent to Telegram in correct JSON format
- ✅ Database logging every signal (sent/dropped, why)
- ✅ 10 backtest runs with 60%+ hit rate
- ✅ Zero false signals or corrupted data

---

## 2. DEXSCREENER API INTEGRATION

### What Is Dexscreener?
Real-time DEX trading data aggregator. Tracks new liquidity pools as they're created on Raydium/Jupiter.

**API Endpoint:** `https://api.dexscreener.com/latest/dex/tokens`  
**Authentication:** None required (free tier)  
**Rate Limit:** 60 requests/minute (not an issue for us)

### Implementation: `src/apis/dexscreener_client.py`

```python
import requests
import logging
from datetime import datetime

logger = logging.getLogger('dexscreener')

class DexscreenerClient:
    BASE_URL = 'https://api.dexscreener.com/latest/dex'
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': 'SolanaTraderBot/1.0'})
    
    def get_solana_pairs(self, sort_by='createdAt', order='desc', limit=100):
        """
        Fetch latest Solana pairs from Raydium/Jupiter
        
        Returns list of new token pairs with:
        - Token address
        - Pair address (Raydium pool)
        - Initial price
        - Liquidity
        - Created timestamp
        """
        try:
            url = f'{self.BASE_URL}/tokens'
            params = {
                'chain': 'solana',
                'sort': sort_by,  # createdAt for newest
                'order': order,   # desc for descending
                'limit': limit
            }
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            pairs = data.get('pairs', [])
            
            logger.info(f'Fetched {len(pairs)} Solana pairs')
            return pairs
            
        except requests.RequestException as e:
            logger.error(f'Dexscreener API error: {e}')
            return []
    
    def get_pair_detail(self, pair_address: str):
        """Get detailed info for a specific pair"""
        try:
            url = f'{self.BASE_URL}/pairs/solana/{pair_address}'
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error(f'Error fetching pair {pair_address}: {e}')
            return None
    
    def parse_pair(self, pair_data: dict):
        """Extract relevant fields from Dexscreener pair data"""
        return {
            'pair_address': pair_data.get('pairAddress'),
            'token_address': pair_data.get('baseToken', {}).get('address'),
            'token_name': pair_data.get('baseToken', {}).get('name'),
            'token_symbol': pair_data.get('baseToken', {}).get('symbol'),
            'price_usd': float(pair_data.get('priceUsd', 0)),
            'liquidity_usd': float(pair_data.get('liquidity', {}).get('usd', 0)),
            'volume_24h': float(pair_data.get('volume', {}).get('h24', 0)),
            'price_change_24h': float(pair_data.get('priceChange', {}).get('h24', 0)),
            'created_at': pair_data.get('pairCreatedAt'),
            'dex': pair_data.get('dex'),
            'raw': pair_data  # Keep raw for debugging
        }
```

### Continuous Monitoring Loop

```python
# In scheduler setup:
self.scheduler.add_job(
    self.researcher_bot.scan_dexscreener,
    trigger=IntervalTrigger(minutes=1),  # Check every minute
    id='dexscreener_scan'
)

# In researcher_bot.py:
def scan_dexscreener(self):
    """Check Dexscreener for new tokens every minute"""
    pairs = self.dexscreener_client.get_solana_pairs(limit=50)
    
    for pair in pairs:
        parsed = self.dexscreener_client.parse_pair(pair)
        
        # Check if we've already analyzed this token
        if self.db.token_exists(parsed['token_address']):
            continue
        
        # Run through rug detection filters
        self.process_token(parsed)
```

---

## 3. RUG DETECTION ENGINE - 6-POINT FILTER

### Filter Order (Critical)
Must pass checks in this order. If ANY fail → token dropped immediately.

```
1. Contract Age
2. Liquidity Lock
3. Top 10 Wallet Concentration
4. Organic Volume Check
5. Deployer Wallet History
6. Data Integrity Check

Only if ALL pass → Proceed to AI scoring
```

### Implementation: `src/analysis/rug_detector.py`

#### Filter 1: Contract Age (>15 minutes)

```python
def check_contract_age(self, token_address: str, created_at: datetime) -> tuple:
    """
    Requirement: Contract must be >15 minutes old
    
    Why: Prevents buying tokens literally just deployed
    Benefit: Gives deployer time to rug if they're planning to
    """
    import time
    now = time.time()
    created_timestamp = created_at.timestamp()
    age_minutes = (now - created_timestamp) / 60
    
    if age_minutes < 15:
        return False, f'Contract too new: {age_minutes:.1f} minutes old'
    
    return True, f'Contract age OK: {age_minutes:.1f} minutes'
```

#### Filter 2: Liquidity Lock

```python
def check_liquidity_locked(self, token_address: str) -> tuple:
    """
    Requirement: Liquidity must be locked or burned
    
    Check via:
    1. Solscan contract verification badge
    2. Check if LP tokens are burned (holder check)
    3. Cross-reference with lock contracts (Orca, Raydium lock)
    
    If locked: PASS
    If unlocked: FAIL (dev can drain pool in seconds)
    """
    try:
        # Call Solscan API to get contract info
        contract_info = self.solscan_client.get_token_info(token_address)
        
        # Check for liquidity lock indicator
        metadata = contract_info.get('metadata', {})
        
        # Check if LP tokens holder is a lock contract
        holders = self.solscan_client.get_token_holders(token_address)
        
        for holder in holders[:20]:  # Check top 20 holders
            holder_address = holder['address']
            
            # Known liquidity lock addresses
            if self._is_known_lock_contract(holder_address):
                return True, f'Liquidity locked via {holder_address}'
            
            # Check if holder is a burn address
            if holder_address in ['11111111111111111111111111111111',  # System program
                                   '11111111111111111111111111111112']:  # Rent
                if holder['balance'] > 0:
                    return True, 'LP tokens burned'
        
        return False, 'Liquidity not locked - REJECT'
        
    except Exception as e:
        logger.error(f'Liquidity lock check failed: {e}')
        return False, f'Could not verify lock: {e}'

def _is_known_lock_contract(self, address: str) -> bool:
    """Check against known lock contract addresses"""
    known_locks = [
        'LiquidityLocker111111111111111111111111111',
        'Orca11111111111111111111111111111111111111',
        # Add more as needed
    ]
    return address in known_locks
```

#### Filter 3: Top 10 Wallet Concentration (<30%)

```python
def check_holder_concentration(self, token_address: str) -> tuple:
    """
    Requirement: Top 10 wallets must hold <30% of supply
    
    Why: If top 10 hold 40%+, one whale dump = 40%+ price crash
    Data: From Solscan holder API
    """
    try:
        holders = self.solscan_client.get_token_holders(token_address, limit=100)
        
        if not holders:
            return False, 'Could not fetch holders'
        
        total_supply = float(holders[0].get('supply', 0))
        
        if total_supply == 0:
            return False, 'Invalid total supply'
        
        # Sum top 10 holders
        top_10_sum = 0
        for holder in holders[:10]:
            top_10_sum += float(holder.get('balance', 0))
        
        top_10_percent = (top_10_sum / total_supply) * 100
        
        if top_10_percent > 30:
            return False, f'Top 10 hold {top_10_percent:.1f}% - REJECT'
        
        return True, f'Top 10 hold {top_10_percent:.1f}% - OK'
        
    except Exception as e:
        logger.error(f'Holder concentration check failed: {e}')
        return False, f'Could not analyze holders: {e}'
```

#### Filter 4: Organic Volume (>50 unique wallets)

```python
def check_organic_volume(self, pair_address: str) -> tuple:
    """
    Requirement: Volume must come from >50 unique wallets
    
    Why: Bot-traded tokens show same small cluster of wallets trading
    Real tokens show diverse wallet activity
    
    Check: Analyze transactions in last 1 hour
    """
    try:
        # Get recent transactions for this pair
        txns = self.helius_rpc.get_recent_transactions(pair_address, limit=100)
        
        if not txns or len(txns) < 20:
            return False, 'Insufficient transaction history'
        
        # Extract unique trader wallets
        unique_traders = set()
        for txn in txns:
            # Parse transaction to get trader address
            trader = self._extract_trader_from_txn(txn)
            if trader:
                unique_traders.add(trader)
        
        unique_count = len(unique_traders)
        
        if unique_count < 50:
            return False, f'Low unique traders: {unique_count} < 50 - REJECT'
        
        return True, f'Organic volume: {unique_count} unique traders'
        
    except Exception as e:
        logger.error(f'Volume analysis failed: {e}')
        return False, f'Could not analyze volume: {e}'

def _extract_trader_from_txn(self, txn: dict) -> str:
    """Parse transaction to get who initiated it"""
    # Parse Solana transaction structure
    # Return trader's wallet address
    pass
```

#### Filter 5: Deployer Wallet History (No Rugs)

```python
def check_deployer_history(self, token_address: str) -> tuple:
    """
    Requirement: Token deployer must not have rug history
    
    Check: Does this wallet appear in known rug lists?
    Data sources:
    - Solscan flagged addresses
    - Community rug databases
    - Pattern analysis (rapid token creation + abandonment)
    """
    try:
        # Get token creator address
        contract_info = self.solscan_client.get_token_info(token_address)
        deployer = contract_info.get('creator')
        
        if not deployer:
            return False, 'Could not identify deployer'
        
        # Check against known rug wallets
        if self._is_known_rug_wallet(deployer):
            return False, f'Deployer {deployer} has rug history - REJECT'
        
        # Check deployer's token history
        deployer_tokens = self.solscan_client.get_wallet_created_tokens(deployer)
        
        # Analyze: Are they pumping and dumping repeatedly?
        recent_tokens = [t for t in deployer_tokens if self._is_recent(t)]
        
        if len(recent_tokens) > 5:  # Too many tokens in short period
            return False, f'Deployer created {len(recent_tokens)} tokens recently - SPAM pattern'
        
        # Check historical survival rate
        for token in deployer_tokens[-10:]:  # Last 10 tokens
            if self._is_dead_token(token):
                return False, f'Deployer has history of dead tokens'
        
        return True, f'Deployer {deployer[:8]}... looks clean'
        
    except Exception as e:
        logger.error(f'Deployer check failed: {e}')
        return False, f'Could not verify deployer: {e}'

def _is_known_rug_wallet(self, address: str) -> bool:
    """Check against community rug databases"""
    # This could be fetched from:
    # - Static list in config
    # - External API (RugChecker, TokenSafety, etc)
    pass

def _is_recent(self, token: dict) -> bool:
    """Check if token created in last 7 days"""
    pass

def _is_dead_token(self, token: dict) -> bool:
    """Check if token has 0 holders, 0 value, or abandoned"""
    pass
```

#### Filter 6: Data Integrity

```python
def check_data_integrity(self, token_data: dict) -> tuple:
    """
    Requirement: All required data fields must be valid and present
    
    Checks:
    - No null/NaN prices
    - Token address valid Solana address format
    - Liquidity > $1000 USD
    - Decimals valid (0-8)
    - No API errors or corrupted responses
    """
    
    required_fields = ['token_address', 'token_name', 'token_symbol', 'price_usd', 'liquidity_usd']
    
    for field in required_fields:
        if field not in token_data or token_data[field] is None:
            return False, f'Missing field: {field}'
    
    # Validate Solana address format
    address = token_data['token_address']
    if not self._is_valid_solana_address(address):
        return False, f'Invalid Solana address: {address}'
    
    # Validate price
    price = float(token_data['price_usd'])
    if price <= 0:
        return False, f'Invalid price: {price}'
    
    # Validate liquidity
    liquidity = float(token_data['liquidity_usd'])
    if liquidity < 1000:  # Min $1k liquidity
        return False, f'Insufficient liquidity: ${liquidity:.2f} < $1000'
    
    # Validate decimals
    decimals = token_data.get('decimals', 6)
    if not (0 <= decimals <= 8):
        return False, f'Invalid decimals: {decimals}'
    
    return True, 'Data integrity OK'

def _is_valid_solana_address(self, address: str) -> bool:
    """Solana addresses are base58 encoded, 32 bytes"""
    import base58
    try:
        decoded = base58.b58decode(address)
        return len(decoded) == 32
    except:
        return False
```

### Complete Rug Detector Orchestration

```python
class RugDetector:
    def __init__(self, config, db, solscan, helius, logger):
        self.config = config
        self.db = db
        self.solscan = solscan
        self.helius = helius
        self.logger = logger
    
    def analyze(self, token_data: dict) -> tuple:
        """
        Run all 6 filters in order. Return (passed, details)
        """
        
        # Filter 1: Contract Age
        passed, msg = self.check_contract_age(token_data['token_address'], token_data['created_at'])
        if not passed:
            self.logger.warning(f"DROPPED: {token_data['token_address']} - {msg}")
            return False, {'filter': 1, 'reason': msg}
        
        # Filter 2: Liquidity Lock
        passed, msg = self.check_liquidity_locked(token_data['token_address'])
        if not passed:
            self.logger.warning(f"DROPPED: {token_data['token_address']} - {msg}")
            return False, {'filter': 2, 'reason': msg}
        
        # Filter 3: Holder Concentration
        passed, msg = self.check_holder_concentration(token_data['token_address'])
        if not passed:
            self.logger.warning(f"DROPPED: {token_data['token_address']} - {msg}")
            return False, {'filter': 3, 'reason': msg}
        
        # Filter 4: Organic Volume
        passed, msg = self.check_organic_volume(token_data['pair_address'])
        if not passed:
            self.logger.warning(f"DROPPED: {token_data['token_address']} - {msg}")
            return False, {'filter': 4, 'reason': msg}
        
        # Filter 5: Deployer History
        passed, msg = self.check_deployer_history(token_data['token_address'])
        if not passed:
            self.logger.warning(f"DROPPED: {token_data['token_address']} - {msg}")
            return False, {'filter': 5, 'reason': msg}
        
        # Filter 6: Data Integrity
        passed, msg = self.check_data_integrity(token_data)
        if not passed:
            self.logger.warning(f"DROPPED: {token_data['token_address']} - {msg}")
            return False, {'filter': 6, 'reason': msg}
        
        # All filters passed!
        self.logger.info(f"PASSED all filters: {token_data['token_address']}")
        return True, {'passed_all': True}
```

---

## 4. AI SCORING ENGINE - CLAUDE HAIKU

### When AI Runs
Only after token passes all 6 rug filters. AI doesn't run on garbage tokens.

### What Claude Scores

```python
class AIScorer:
    def score_token(self, token_data: dict, rug_filters: dict) -> int:
        """
        Use Claude Haiku to score 6-10
        
        Input: Token data + on-chain metrics
        Output: Confidence score (integer 6-10)
        
        Scoring factors:
        - Narrative strength (can this meme go viral?)
        - Community sentiment (Discord, Twitter signals)
        - Technical momentum (price action, volume trend)
        - Risk factors (whale concentration, deployer profile)
        """
        
        prompt = f"""
You are a Solana memecoin analyst. Rate this token's potential for 10x-100x returns.

Token: {token_data['token_name']} ({token_data['token_symbol']})
Address: {token_data['token_address']}

ON-CHAIN METRICS (Already verified - no rugs):
- Contract age: {rug_filters['contract_age']} minutes
- Liquidity: ${token_data['liquidity_usd']:.2f} locked
- Volume (24h): ${token_data['volume_24h']:.2f}
- Holders: {token_data['holder_count']} unique
- Top 10 concentration: {rug_filters['top_10_percent']:.1f}%

NARRATIVE:
{token_data.get('description', 'No description available')}

SOCIAL SIGNALS:
- Twitter mentions (1h): {token_data.get('twitter_mentions', 0)}
- Reddit mentions: {token_data.get('reddit_mentions', 0)}
- Discord members: {token_data.get('discord_members', 0)}

Rate this token's viral potential on a scale of 6-10:
- 6: Risky, low narrative appeal
- 7: Decent narrative, some community interest
- 8: Strong narrative, growing momentum
- 9: Very strong narrative, viral indicators
- 10: Exceptional narrative, strong momentum, clear viral path

RESPOND WITH ONLY A NUMBER 6-10 AND ONE SENTENCE REASONING.
Example: "8 - Strong dog-gaming narrative with engaged community"
        """
        
        response = self.client.messages.create(
            model="anthropic/claude-haiku-4-5",
            max_tokens=50,
            messages=[{"role": "user", "content": prompt}]
        )
        
        # Parse response
        text = response.content[0].text
        score = self._extract_score(text)
        reasoning = text.split('-', 1)[1].strip() if '-' in text else text
        
        return {
            'score': score,
            'reasoning': reasoning,
            'model': 'claude-haiku-4-5'
        }
    
    def _extract_score(self, response: str) -> int:
        """Extract number from AI response"""
        for char in response:
            if char.isdigit():
                score = int(char)
                return score if 6 <= score <= 10 else 7  # Default to 7 if invalid
        return 7  # Default
```

---

## 5. POSITION SIZING FROM CONFIDENCE SCORE

```python
class PositionSizer:
    def __init__(self, config):
        self.config = config
    
    def calculate(self, confidence_score: int) -> float:
        """
        Deterministic position sizing based on confidence
        
        8-10: $2
        6-7: $1
        <6: DROPPED (never reaches here)
        """
        
        if confidence_score >= 8:
            return 2.0
        elif confidence_score >= 6:
            return 1.0
        else:
            return 0.0  # Signal dropped entirely
```

---

## 6. SIGNAL JSON OUTPUT FORMAT

See SYSTEM_LOGIC.md section 7 for complete format. Generated by:

```python
class SignalFormatter:
    def format(self, token_data: dict, rug_analysis: dict, ai_score: dict) -> dict:
        """
        Generate structured signal ready for execution
        """
        
        position_size = self.position_sizer.calculate(ai_score['score'])
        
        if position_size == 0:
            return None  # Signal dropped
        
        signal = {
            'signal_id': f"SIG_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
            'timestamp': datetime.utcnow().isoformat(),
            'token': {
                'address': token_data['token_address'],
                'name': token_data['token_name'],
                'symbol': token_data['token_symbol'],
                'decimals': token_data.get('decimals', 6)
            },
            'entry': {
                'price': token_data['price_usd'],
                'position_size_usd': position_size,
                'reason': ai_score['reasoning']
            },
            'risk': {
                'stop_loss_price': token_data['price_usd'] * 0.8,
                'stop_loss_percent': 20
            },
            'profit_targets': [
                {'tier': 1, 'price': token_data['price_usd'] * 2.0, 'multiplier': '2x', 'sell_percent': 40},
                {'tier': 2, 'price': token_data['price_usd'] * 4.0, 'multiplier': '4x', 'sell_percent': 40},
                {'tier': 3, 'type': 'trailing_stop', 'trailing_percent': 50}
            ],
            'confidence': {
                'score': ai_score['score'],
                'on_chain_filters': rug_analysis,
                'ai_analysis': ai_score['reasoning']
            }
        }
        
        return signal
```

---

## 7. DATABASE LOGGING

Track every signal (sent/dropped):

```python
def log_signal(self, signal: dict, status: str, drop_reason: str = None):
    """Log to database"""
    self.db.log_signal({
        'signal_id': signal.get('signal_id'),
        'timestamp': signal.get('timestamp'),
        'token_address': signal['token']['address'],
        'token_name': signal['token']['name'],
        'token_symbol': signal['token']['symbol'],
        'confidence_score': signal['confidence']['score'],
        'position_size_usd': signal['entry'].get('position_size_usd'),
        'status': status,  # 'sent' or 'dropped'
        'drop_reason': drop_reason,  # Why it was dropped
        'created_at': datetime.utcnow().isoformat()
    })
```

---

## 8. TASK BREAKDOWN - PHASE 2 IMPLEMENTATION

### Task 2.1: Solscan API Client
**Time:** 2 hours
- Create Solscan account and get API key
- Build `src/apis/solscan_client.py`
- Implement: `get_token_info()`, `get_token_holders()`, `get_wallet_created_tokens()`

### Task 2.2: Helius RPC Client
**Time:** 1.5 hours
- Create Helius account (free tier)
- Build `src/apis/helius_rpc.py`
- Implement: `get_recent_transactions()`, `get_token_metadata()`

### Task 2.3: Rug Detector Implementation
**Time:** 3 hours
- Build complete `src/analysis/rug_detector.py`
- Implement all 6 filters
- Test each filter independently

### Task 2.4: AI Scorer (Claude Haiku)
**Time:** 1.5 hours
- Build `src/analysis/ai_scorer.py`
- Test prompt engineering (iterate on confidence scores)
- Verify scores in 6-10 range

### Task 2.5: Position Sizer
**Time:** 30 minutes
- Build `src/trading/position_sizer.py`
- Implement deterministic sizing logic

### Task 2.6: Signal Formatter
**Time:** 1 hour
- Build `src/signals/signal_formatter.py`
- Generate correct JSON structure

### Task 2.7: Researcher Bot Integration
**Time:** 2 hours
- Update `src/researcher_bot.py`
- Wire together all components
- Implement main scan loop

### Task 2.8: Backtesting Framework
**Time:** 2 hours
- Build `tests/backtest_signals.py`
- Load historical Dexscreener data
- Calculate hit rate on past tokens

### Task 2.9: Testing & Tuning
**Time:** 3 hours
- Unit tests for each filter
- Integration tests for full pipeline
- Tune AI confidence thresholds
- Verify database logging

### Task 2.10: Documentation & Deployment
**Time:** 1.5 hours
- Document API credentials needed
- Create deployment checklist
- Write runbook for troubleshooting

---

## 9. SUCCESS CRITERIA - PHASE 2 COMPLETE

✅ Dexscreener integration fetches new tokens in real-time  
✅ All 6 rug filters working independently and in sequence  
✅ AI confidence scores in 6-10 range (no sub-6)  
✅ Position sizing deterministic ($2 for 8-10, $1 for 6-7)  
✅ Signals formatted as correct JSON, logged to database  
✅ Telegram alerts sending (test mode)  
✅ Backtest shows 60%+ hit rate on historical data  
✅ Zero false signals or data corruption  
✅ Can handle 50+ new tokens/day without errors  
✅ All API errors logged and non-fatal  

---

## 10. TESTING CHECKLIST

- [ ] Each filter works independently with test data
- [ ] Filters properly reject known rug tokens
- [ ] AI scorer returns 6-10 scores consistently
- [ ] Position sizing matches spec exactly
- [ ] Signal JSON validates against schema
- [ ] Database logs every signal correctly
- [ ] Telegram alerts format properly
- [ ] Backtest on 100 historical tokens
- [ ] Hit rate >= 60%
- [ ] Zero crashes on bad data

---

## 11. NEXT: PHASE 3

Once Phase 2 complete, Phase 3 adds:
- Smart wallet discovery (identify proven winners)
- Real-time wallet tracking
- Wallet-triggered signals

Estimated time: 5-7 days
