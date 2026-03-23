import logging
import os
from datetime import datetime
from typing import Optional
from src.apis.dexscreener_client import DexscreenerClient
from src.apis.solscan_client import SolscanClient
from src.apis.helius_rpc import HeliusRPCClient
from src.analysis.rug_detector import RugDetector
from src.analysis.ai_scorer import AIScorer
from src.signals.signal_formatter import SignalFormatter
from src.config import Config
from src.cost_tracker import CostTracker
from src.risk_manager import RiskManager
from src.rules.trading_rules_engine import TradingRulesEngine
from src.agents.agent_1_discovery import Agent1Discovery
from src.agents.agent_5_signal_aggregator import Agent5SignalAggregator
from src.apis.rugcheck_client import RugcheckClient
from src.apis.birdeye_client import BirdeyeClient
from src.scoring.safety_score_calculator import SafetyScorer
import json
import asyncio
import httpx
import websockets

logger = logging.getLogger('researcher')

class ResearcherBot:
    """Discover high-confidence trading signals on Solana"""
    
    def __init__(self, database, telegram_bot):
        self.db = database
        self.telegram = telegram_bot
        self.config = Config()
        
        # Initialize Core API clients (shared)
        self.dexscreener = DexscreenerClient()
        self.solscan     = SolscanClient()
        self.helius      = HeliusRPCClient()
        self.birdeye     = BirdeyeClient()
        
        # Initialize Agent 1 (Discovery Division)
        self.agent_1 = Agent1Discovery(
            config=self.config,
            db=database,
            dexscreener=self.dexscreener,
            solscan=self.solscan,
            birdeye=self.birdeye,
            helius=self.helius
        )
        logger.info('🕵️ Agent 1 (Discovery) initialized and injected')
        
        # Initialize analyzers
        self.rug_detector = RugDetector(self.solscan, self.helius)
        self.ai_scorer    = AIScorer()
        
        # Initialize cost tracking
        self.cost_tracker = CostTracker()
        
        # Division Agents (Injected by main.py)
        self.agent_2_safety = None
        self.agent_3_tracker = None
        self.agent_4_intel = None
        self.agent_5_aggregator = None
        self.macro_sentinel  = None
        self.risk_manager_a7 = None
        self.trading_bot     = None
        self.agent_9         = None
        
        # Tracking
        self.signals_sent_today = 0
        self.signals_dropped_today = 0
        self.tokens_found_today = 0
        self.market_regime = 'mixed'
        
        # WebSocket Client for UI signaling
        self.ws_url = os.getenv("WS_SERVER_URL", "ws://localhost:8080")
        
        logger.info('🔬 Researcher Bot initialized with Nine-Agent Firm capability')
    
    async def _send_agent_event(self, agent_id: int, status: str, payload: dict = None):
        """Send a real-time status update to the frontend via node server (Async)"""
        try:
            async with websockets.connect(self.ws_url) as ws:
                msg = {
                    "event": "agent_status_changed",
                    "agent_id": agent_id,
                    "payload": {
                        "new_status": status,
                        **(payload or {})
                    }
                }
                await ws.send(json.dumps(msg))
        except Exception as e:
            logger.debug(f"WebSocket signaling failed: {e}")
    
    async def _send_news_event(self, type: str, source: str, title: str, importance: str = 'MEDIUM'):
        """Send a news item to the frontend news panel (Async)"""
        try:
            async with websockets.connect(self.ws_url) as ws:
                msg = {
                    "event": "NEWS_FEED_UPDATE",
                    "payload": {
                        "type": type,
                        "source": source,
                        "title": title,
                        "timestamp": datetime.now().strftime("%H:%M"),
                        "importance": importance
                    }
                }
                await ws.send(json.dumps(msg))
        except:
            pass

    async def _send_pipeline_update(self):
        """Update discovery pipeline stats on the dashboard (Async)"""
        try:
            async with websockets.connect(self.ws_url) as ws:
                conv_rate = (self.signals_sent_today / self.tokens_found_today * 100) if self.tokens_found_today > 0 else 0
                msg = {
                    "event": "PIPELINE_STATS_UPDATE",
                    "payload": {
                        "found": self.tokens_found_today,
                        "dropped": self.signals_dropped_today,
                        "passed": self.signals_sent_today,
                        "conversion_rate": f"{conv_rate:.1f}%"
                    }
                }
                await ws.send(json.dumps(msg))
        except:
            pass
    
    def detect_market_regime(self) -> str:
        """
        Detect current market regime based on:
        - Recent volume trends
        - Volatility
        - Community activity
        
        Returns: 'bullish' | 'mixed' | 'choppy' | 'flat'
        """
        # For now, use config default or 'mixed' (conservative)
        regime = self.config.get_optional_config('MARKET_REGIME', 'mixed').lower()
        
        if regime not in ['bullish', 'mixed', 'choppy', 'flat']:
            regime = 'mixed'
        
        logger.debug(f'📊 Market regime: {regime.upper()}')
        return regime
    
    async def process_with_agent_2(self, candidates):
        """Process candidates through Agent 2 safety analysis"""
        from src.agents.agent_2_on_chain_analyst import OnChainAnalyst
        from src.apis.rugcheck_client import RugcheckClient
        from src.scoring.safety_score_calculator import SafetyScorer
        
        analyst = OnChainAnalyst(self.config)
        analyst.rugcheck = RugcheckClient()
        analyst.scorer = SafetyScorer()
        analyst.db = self.db
        
        cleared_tokens = []
        killed_tokens = []
        
        for candidate in candidates:
            token_address = candidate.get('baseToken', {}).get('address') or candidate.get('pairAddress')
            result = await analyst.analyze_token(token_address)
            
            if result['status'] == 'CLEARED':
                cleared_tokens.append(result)
                logger.info(f"[AGENT_2] CLEARED: {token_address[:8]}... score {result.get('safety_score', 0):.1f}/10")
            else:
                killed_tokens.append(result)
                logger.warning(f"[AGENT_2] KILLED: {token_address[:8]}... reason: {result.get('failure_reason')}")
            
            await analyst.log_to_database(result)
        
        return {
            'cleared': cleared_tokens,
            'killed': killed_tokens,
            'total_processed': len(candidates)
        }
    
    async def process_with_agents_2_3_4_5(self, candidates):
        """
        Full Intelligence Division pipeline: Agent 2 → Agent 3 → Agent 4 → Agent 5.
        Uses injected agents (Decoupled Injection Pattern).
        """
        results = {
            'agent_2_killed': [],
            'agent_5_cleared': [],
            'agent_5_killed': [],
            'total_processed': len(candidates)
        }

        results = {
            'agent_2_killed': [],
            'agent_5_cleared': [],
            'agent_5_killed': [],
            'total_processed': len(candidates)
        }

        for candidate in candidates:
            try:
                token_address = (
                    candidate.get('baseToken', {}).get('address') or 
                    candidate.get('pairAddress') or
                    candidate.get('address') or
                    candidate.get('token_address')
                )
                
                if not token_address:
                    logger.warning("[RESEARCHER] Skipping candidate with missing address")
                    continue
                    
                token_symbol = candidate.get('baseToken', {}).get('symbol', 'UNKNOWN')
                token_name   = candidate.get('baseToken', {}).get('name', token_symbol)
                discovered_at = candidate.get('pairCreatedAt') or datetime.utcnow().isoformat()
    
                # ── AGENT 2: On-chain safety ──────────────────────────────
                self._send_agent_event(2, "ANALYZING", {"token": token_symbol})
                result_2 = await self.agent_2_safety.analyze_token(token_address)
                await self.agent_2_safety.log_to_database(result_2)
    
                if result_2['status'] == 'KILLED':
                    self._send_agent_event(2, "HOLD_SIGNAL", {"reason": result_2.get('failure_reason')})
                    results['agent_2_killed'].append(result_2)
                    self.signals_dropped_today += 1
                    self._send_pipeline_update()
                    logger.warning(f"[AGENT_2] KILLED: {token_symbol} | {result_2.get('failure_reason')}")
                    continue
                
                self._send_agent_event(2, "CLEAR", {"score": result_2.get('safety_score')})
                logger.info(f"[AGENT_2] CLEARED: {token_symbol} | score {result_2.get('safety_score', 0):.1f}/10")
    
                # ── AGENT 3: Wallet Tracker ───────────────────────────────
                self._send_agent_event(3, "ANALYZING", {"token": token_symbol})
                result_3 = await self.agent_3_tracker.analyze_token(token_address)
                await self.agent_3_tracker.log_to_database(result_3)
                self._send_agent_event(3, "CLEAR" if result_3['status'] == 'CLEARED' else "HOLD_SIGNAL")
                logger.info(f"[AGENT_3] {result_3['status']}: {token_symbol} | score {result_3.get('score', 0):.1f}/10")
    
                # ── AGENT 4: Intel / Community Sentiment ─────────────────
                self._send_agent_event(4, "ANALYZING", {"token": token_symbol})
                result_4 = await self.agent_4_intel.analyze_token(
                    token_address,
                    token_symbol,
                    token_name,
                    candidate.get('baseToken', {}).get('description', '')
                )
                await self.agent_4_intel.log_to_database(result_4)
                self._send_agent_event(4, "CLEAR" if result_4['status'] == 'CLEARED' else "HOLD_SIGNAL")
                logger.info(f"[AGENT_4] {result_4['status']}: {token_symbol} | score {result_4.get('score', 0):.1f}/10")
    
                # ── AGENT 5: Signal Aggregator ────────────────────────────
                signals = {
                    'agent_1': {'cleared': True, 'score': 6.0, 'analysis_timestamp': datetime.utcnow().isoformat()},
                    'agent_2': {
                        'cleared': result_2['status'] == 'CLEARED',
                        'score': result_2.get('safety_score', 0),
                        'analysis_timestamp': result_2.get('analysis_timestamp', datetime.utcnow().isoformat()),
                        'discovery_source': 'onchain'
                    },
                    'agent_3': {
                        'cleared': result_3.get('status') == 'CLEARED',
                        'score': result_3.get('score', 0),
                        'analysis_timestamp': result_3.get('analysis_timestamp', datetime.utcnow().isoformat())
                    },
                    'agent_4': {
                        'cleared': result_4.get('status') == 'CLEARED',
                        'score': result_4.get('score', 0),
                        'analysis_timestamp': result_4.get('analysis_timestamp', datetime.utcnow().isoformat()),
                        'community': result_4.get('community', {})
                    },
                    'token_data': candidate
                }
    
                result_5 = await self.agent_5_aggregator.aggregate_signal(
                    token_address, token_symbol, signals,
                    discovered_at, self.market_regime
                )
    
                if result_5 and result_5['status'] == 'CLEARED':
                    self._send_agent_event(5, "CLEAR", {"score": result_5['composite_score']})
                    result_5['raw_candidate'] = candidate
                    # Store detailed intel for Sonnet refinement
                    result_5['agent_analysis'] = {
                        "agent_2_safety": result_2,
                        "agent_3_wallets": result_3,
                        "agent_4_intel": result_4
                    }
                    results['agent_5_cleared'].append(result_5)
                    logger.info(f"[AGENT_5] ✅ CLEARED: {token_symbol} | composite {result_5['composite_score']:.2f}/10")
                else:
                    self._send_agent_event(5, "HOLD_SIGNAL")
                    results['agent_5_killed'].append(result_5)
                    self.signals_dropped_today += 1
                    self._send_pipeline_update()
                    reason = result_5.get('failure_reason', 'No result') if result_5 else 'Aggregation failed'
                    logger.warning(f"[AGENT_5] ❌ KILLED: {token_symbol} | {reason}")
            except Exception as e:
                logger.error(f"[RESEARCHER] Error in processing loop for candidate: {e}")
                continue

        return results

    async def _resolve_candidate_address(self, candidate: dict) -> Optional[str]:
        """Try to find a Solana contract address for a candidate (e.g. from news or trending) (Async)"""
        addr = candidate.get('address') or candidate.get('token_address')
        if addr: return addr
        
        symbol = candidate.get('symbol')
        if not symbol: return None
        
        # Lookup symbol on DexScreener to find the most likely SOL address
        try:
            results = await self.dexscreener.search_pairs(symbol)
            for pair in results:
                if pair.get('chainId') == 'solana':
                    return pair.get('baseToken', {}).get('address')
        except:
            pass
        return None

    async def scan(self):
        """Run a complete multi-source Intelligence Division scan for new tokens"""
        logger.info('='*60)
        logger.info('🏛️ [FIRM MANAGER] STARTING DISCOVERY CYCLE')
        logger.info('='*60)
        
        try:
            self.market_regime = self.detect_market_regime()
            scan_stats = {
                'total_found': 0, 'total_processed': 0,
                'agent_2_cleared': 0, 'agent_2_killed': 0,
                'agent_5_cleared': 0, 'agent_5_killed': 0,
                'agent_6_passed': 0, 'agent_6_held': 0,
                'agent_7_passed': 0, 'agent_7_blocked': 0,
                'agent_8_executed': 0, 'agent_8_rejected': 0,
                'kill_reasons': [],
                'cleared_tokens': [],
                'executed_tokens': []
            }
            
            # ── DISCOVERY (Delegated to Agent 1) ─────────────────
            leads = await self.agent_1.discover_new_leads()
            self.tokens_found_today += len(leads)
            scan_stats['total_found'] = len(leads)
            self._send_pipeline_update()
            
            if not leads:
                logger.info("ℹ️ No new leads found this cycle.")
                return

            # ── PROCESSING PIPELINE (Agents 2-5) ─────────────────
            cleared_signals = []
            for lead in leads[:15]:  # Safety cap per cycle
                # Normalize candidate data for processing
                if lead['source'] != 'dexscreener':
                    full_data = await self.dexscreener.get_token_pairs(lead['address'])
                    if not full_data: continue
                    candidate = full_data[0]
                else:
                    candidate = lead.get('raw') or lead

                # Run Intelligence Div gates (Agent 2 -> 3 -> 4 -> 5)
                intel_results = await self.process_with_agents_2_3_4_5([candidate])
                
                # Track per-agent stats from intelligence division
                a2_killed_count = len(intel_results.get('agent_2_killed', []))
                a5_cleared_list = intel_results.get('agent_5_cleared', [])
                a5_killed_count = len(intel_results.get('agent_5_killed', []))
                a2_cleared_count = len(a5_cleared_list) + a5_killed_count  # survived Agent 2
                
                scan_stats['agent_2_cleared'] += a2_cleared_count
                scan_stats['agent_2_killed'] += a2_killed_count
                scan_stats['agent_5_cleared'] += len(a5_cleared_list)
                scan_stats['agent_5_killed'] += a5_killed_count
                
                cleared_signals.extend(a5_cleared_list)

            # ── COMMAND DIVISION (Agents 6-7) ────────────────────
            for signal in cleared_signals:
                scan_stats['total_processed'] += 1
                await self._process_command_division(signal, scan_stats)
            
            # Notify performance analyst (Agent 9)
            if hasattr(self, 'agent_9') and self.agent_9:
                await self.agent_9.notify_pipeline_summary(scan_stats)
            
            logger.info(f'✅ [FIRM MANAGER] Cycle complete: {len(cleared_signals)} signals cleared intelligence gates.')
            
        except Exception as e:
            logger.error(f'❌ [FIRM MANAGER] Scan cycle failed: {e}')
            
            # Summary
            logger.info('='*60)
            logger.info(f'📊 Full Scan Complete:')
            logger.info(f'   Signals sent: {self.signals_sent_today}')
            logger.info(f'   Signals dropped: {self.signals_dropped_today}')
            
            cost_summary = self.cost_tracker.get_cost_summary()
            logger.info(f'💰 Cost: ${cost_summary["daily_cost"]:.2f} today / ${cost_summary["monthly_cost"]:.2f} month')
            logger.info('='*60)
            
        except Exception as e:
            logger.error(f'❌ Scan failed: {e}')
    
    async def _process_command_division(self, agent_5_signal: dict, scan_stats: dict = None):
        """
        Pass an Agent-5 cleared signal through Command Division:
        Agent 6 (Macro Sentinel) → Agent 7 (Risk Manager).
        If both approve, formats and sends signal.
        """
        if scan_stats is None: scan_stats = {}
        try:
            candidate = agent_5_signal.get('raw_candidate', {})
            parsed = self.dexscreener.parse_pair(candidate)
            if not parsed:
                return

            token_address = parsed['token_address']
            token_symbol = parsed.get('token_symbol', 'UNKNOWN')
            composite_score = agent_5_signal.get('composite_score', 0)

            logger.info(f'🏛️ [COMMAND] Processing: {token_symbol} (composite {composite_score:.2f}/10)')

            # Step 1: Agent 6 Macro Sentinel
            if hasattr(self, 'macro_sentinel') and self.macro_sentinel:
                await self._send_agent_event(6, "WATCHING", {"token": token_symbol})
                agent_6_result = await self.macro_sentinel.analyze(agent_5_signal)
                if agent_6_result.get('status') == 'MACRO_HOLD':
                    await self._send_agent_event(6, "HOLD_SIGNAL", {"reason": agent_6_result.get('failure_reason')})
                    logger.warning(f"   [MACRO] KILLED: {token_symbol} | {agent_6_result.get('failure_reason')}")
                    self.signals_dropped_today += 1
                    scan_stats['agent_6_held'] = scan_stats.get('agent_6_held', 0) + 1
                    scan_stats['kill_reasons'].append(f"{token_symbol}: Macro Hold - {agent_6_result.get('failure_reason', 'unknown')}")
                    await self._send_pipeline_update()
                    return
                await self._send_agent_event(6, "CLEAR")
                scan_stats['agent_6_passed'] = scan_stats.get('agent_6_passed', 0) + 1
            else:
                logger.warning("   [MACRO] Agent-6 not found. Bypassing macro checks.")
                agent_6_result = {"market_regime": self.market_regime}

            # Step 2: Rug detection (legacy filter still applied)
            passed, rug_analysis = await self.rug_detector.analyze(parsed)
            if not passed:
                self.signals_dropped_today += 1
                await self._send_pipeline_update()
                logger.warning(f'   [RUG] KILLED: {token_symbol}')
                return

            # Use composite score from Agent 5 as AI score proxy
            ai_score = {
                'score': composite_score,
                'reasoning': f'Composite score from independent agents',
                'tokens_used': 0
            }

            if composite_score < 6:
                self.signals_dropped_today += 1
                await self._send_pipeline_update()
                return

            # Format signal base
            signal = SignalFormatter.format(parsed, rug_analysis, ai_score)
            if not signal:
                self.signals_dropped_today += 1
                return

            # Step 3: Agent 7 Risk Manager validation
            entry_price = float(signal['entry']['price'])

            if hasattr(self, 'risk_manager_a7') and self.risk_manager_a7:
                await self._send_agent_event(7, "ANALYZING", {"token": token_symbol})
                approved, instruction, risk_reason = await self.risk_manager_a7.validate_and_size(
                    agent_5_signal, 
                    agent_6_result, 
                    entry_price, 
                    user_id="default_user",
                    agent_analysis=agent_5_signal.get('agent_analysis')
                )
                
                if not approved:
                    await self._send_agent_event(7, "HOLD_SIGNAL", {"reason": risk_reason})
                    logger.warning(f'   [RISK] KILLED: {token_symbol} | {risk_reason}')
                    self.signals_dropped_today += 1
                    scan_stats['agent_7_blocked'] = scan_stats.get('agent_7_blocked', 0) + 1
                    scan_stats['kill_reasons'].append(f"{token_symbol}: Risk Block - {risk_reason}")
                    await self._send_pipeline_update()
                    return
                
                await self._send_agent_event(7, "CLEAR", {"size": instruction.position_size_usd})
                scan_stats['agent_7_passed'] = scan_stats.get('agent_7_passed', 0) + 1
                logger.info(f'   ✅ [RISK] APPROVED: {token_symbol} | Size: ${instruction.position_size_usd:.2f}')
                
                # Step 4: Agent 8 Execution
                if hasattr(self, 'trading_bot') and self.trading_bot:
                    await self._send_agent_event(8, "ORDER_PENDING", {"token": token_symbol})
                    logger.info(f'   🤖 [EXECUTION] Handing off to Agent 8 Trading Bot...')
                    try:
                        # Use execute_trade (Async) if available, otherwise to_thread
                        if hasattr(self.trading_bot, 'execute_trade'):
                            exec_result = await self.trading_bot.execute_trade(instruction)
                        else:
                            exec_result = await asyncio.to_thread(self.trading_bot.execute_trade_sync, instruction)
                            
                        if exec_result.get('status') == 'FILLED':
                            scan_stats['agent_8_executed'] = scan_stats.get('agent_8_executed', 0) + 1
                            scan_stats['executed_tokens'].append({
                                'symbol': token_symbol,
                                'price': exec_result.get('fill_price', entry_price),
                                'size_usd': instruction.position_size_usd,
                                'sl_pct': instruction.stop_loss_pct,
                                'tp1_mult': instruction.take_profit_1_pct,
                                'tp2_mult': instruction.take_profit_2_pct,
                                'rationale': instruction.sl_tp_rationale or 'Standard entry'
                            })
                            await self._send_agent_event(8, "POSITION_OPEN", {"price": exec_result.get('fill_price')})
                            logger.info(f"   💸 [FILLED] Pos ID: {exec_result.get('position_id')} @ ${exec_result.get('fill_price')}")
                        else:
                            scan_stats['agent_8_rejected'] = scan_stats.get('agent_8_rejected', 0) + 1
                            await self._send_agent_event(8, "STANDBY", {"reason": exec_result.get('reason')})
                            logger.warning(f"   ❌ [EXECUTION REJECTED] {exec_result.get('reason')}")
                    except Exception as e:
                        await self._send_agent_event(8, "STANDBY", {"error": str(e)})
                        logger.error(f"   ❌ [CRITICAL] Agent 8 Execution Failed: {e}")
                else:
                    logger.warning("   [EXECUTION] Agent 8 not found! Trade approved but not executed.")

                # Keep signal properties updated for backward compatibility (optional but safe)
                signal['entry']['position_size_usd'] = instruction.position_size_usd
                signal['risk']['stop_loss_price'] = instruction.stop_loss_price
                signal['profit_targets'][0]['price'] = instruction.take_profit_1_price
                signal['profit_targets'][1]['price'] = instruction.take_profit_2_price

            else:
                logger.warning("   [RISK] Agent-7 not found! Defaulting to legacy RiskManager.")
                stop_loss_price = float(signal['risk']['stop_loss_price'])
                take_profit_price = float(signal['profit_targets'][1]['price'])
                position_usd = signal['entry']['position_size_usd']
                from src.risk_manager import MarketRegime
                regime_map = {'bullish': MarketRegime.BULLISH, 'mixed': MarketRegime.MIXED, 
                              'choppy': MarketRegime.CHOPPY, 'flat': MarketRegime.FLAT}
                validation = await self.risk_manager.validate_trade(
                    entry_price, stop_loss_price, take_profit_price, position_usd,
                    regime_map.get(self.market_regime, MarketRegime.MIXED)
                )

                if not validation.passed:
                    logger.warning(f'   [RISK] KILLED: {token_symbol} | {validation.summary()}')
                    self.signals_dropped_today += 1
                    return

            # Send to Telegram
            self.telegram.send_signal_alert(signal)

            # Log to DB
            await self.db.log_signal({
                'signal_id': signal['signal_id'],
                'timestamp': signal['timestamp'],
                'token_address': token_address,
                'token_name': parsed.get('token_name'),
                'token_symbol': token_symbol,
                'entry_price': signal['entry']['price'],
                'position_size_usd': signal['entry']['position_size_usd'],
                'confidence_score': composite_score,
                'reason': ai_score['reasoning'],
                'status': 'sent'
            })

            logger.info(f'   📲 SIGNAL SENT: {token_symbol} (Composite {composite_score:.2f}/10)')
            self.signals_sent_today += 1
            await self._send_pipeline_update()

        except Exception as e:
            logger.error(f'Command Division error for token: {e}')
    
    async def _process_token(self, pair_data: dict):
        """Process a single token through the full pipeline"""
        try:
            # Parse pair data
            parsed = self.dexscreener.parse_pair(pair_data)
            
            if not parsed or not parsed.get('token_address'):
                logger.debug('Skipping invalid pair')
                return
            
            token_address = parsed['token_address']
            token_symbol = parsed.get('token_symbol', 'UNKNOWN')
            
            logger.info(f'\n🔍 Processing: {token_symbol} ({token_address[:8]}...)')
            
            # Step 1: Check if already analyzed
            if await self.db.token_exists(token_address):
                logger.debug(f'   Already analyzed')
                return
            
            # Step 2: Run 6-point rug detection filter
            logger.info(f'   Running rug detection filters...')
            passed, rug_analysis = await self.rug_detector.analyze(parsed)
            
            if not passed:
                self.signals_dropped_today += 1
                await self._send_pipeline_update()
                await self.db.log_signal({
                    'signal_id': f"DROPPED_{datetime.utcnow().timestamp()}",
                    'timestamp': datetime.utcnow().isoformat(),
                    'token_address': token_address,
                    'token_name': parsed.get('token_name'),
                    'token_symbol': token_symbol,
                    'entry_price': parsed.get('price_usd'),
                    'position_size_usd': 0,
                    'confidence_score': 0,
                    'reason': rug_analysis.get('reason', 'Filter failed'),
                    'status': 'dropped'
                })
                return
            
            logger.info(f'   ✅ Passed all rug filters')
            
            # Step 3: Apply Master Rules - Narrative Bonus (RULE 7: Narrative Detection)
            narrative_result = self.rules_engine.get_narrative_bonus(
                parsed.get('token_name', ''),
                parsed.get('description', ''),
                parsed.get('social_data', '')
            )
            narrative_bonus = narrative_result['bonus']
            
            logger.info(f'   Running AI confidence scoring...')
            ai_score = await self.ai_scorer.score_token(parsed, rug_analysis)
            
            # Apply narrative bonus to confidence score
            if narrative_bonus > 0:
                original_score = ai_score['score']
                ai_score['score'] = min(10, ai_score['score'] + narrative_bonus)
                logger.info(f'   📈 Narrative bonus: +{narrative_bonus} ({original_score} → {ai_score["score"]})')
            
            # Log token usage cost
            if ai_score.get('tokens_used', 0) > 0:
                self.cost_tracker.log_haiku_call(
                    input_tokens=int(ai_score.get('tokens_used', 0) * 0.65),  # ~65% input
                    output_tokens=int(ai_score.get('tokens_used', 0) * 0.35),  # ~35% output
                    token_symbol=token_symbol
                )
                # Check budget alerts
                alert = self.cost_tracker.check_and_alert()
                if alert:
                    logger.warning(alert)
            
            # Step 4: Check if confidence >= 6
            if ai_score['score'] < 6:
                logger.info(f'   🛑 Confidence {ai_score["score"]}/10 < 6 threshold → Dropped')
                self.signals_dropped_today += 1
                await self.db.log_signal({
                    'signal_id': f"DROPPED_{datetime.utcnow().timestamp()}",
                    'timestamp': datetime.utcnow().isoformat(),
                    'token_address': token_address,
                    'token_name': parsed.get('token_name'),
                    'token_symbol': token_symbol,
                    'entry_price': parsed.get('price_usd'),
                    'position_size_usd': 0,
                    'confidence_score': ai_score['score'],
                    'reason': f'Low confidence: {ai_score["reasoning"]}',
                    'status': 'dropped'
                })
                return
            
            # Step 5: Format signal
            logger.info(f'   Formatting signal...')
            signal = SignalFormatter.format(parsed, rug_analysis, ai_score)
            
            if not signal:
                logger.warning(f'   Signal formatting failed')
                self.signals_dropped_today += 1
                return
            
            # Step 5.4: Apply Master Rules - Position Size Multiplier (RULE 1B: Market Cap Tiers)
            cap_multiplier = self.rules_engine.get_position_size_multiplier(parsed['market_cap'])
            adjusted_position_size = signal['entry']['position_size_usd'] * cap_multiplier
            if cap_multiplier != 1.0:
                logger.info(f'   📊 Market cap multiplier: {cap_multiplier}x (${signal["entry"]["position_size_usd"]} → ${adjusted_position_size})')
            
            # Update signal with adjusted position size
            signal['entry']['position_size_usd'] = adjusted_position_size
            
            # Step 5.5: Validate risk (Sync fallback wrapped in thread)
            logger.info(f'   Validating trade risk (5-point check)...')
            
            # Calculate entry/stop/profit
            entry_price = float(signal['entry']['price'])
            stop_loss_price = float(signal['risk']['stop_loss_price'])
            take_profit_price = float(signal['profit_targets'][1]['price'])
            position_usd = adjusted_position_size
            
            from src.risk_manager import MarketRegime
            regime_map = {'bullish': MarketRegime.BULLISH, 'mixed': MarketRegime.MIXED, 'choppy': MarketRegime.CHOPPY, 'flat': MarketRegime.FLAT}
            market_regime_enum = regime_map.get(self.market_regime, MarketRegime.MIXED)
            
            validation = await self.risk_manager.validate_trade(
                entry_price=entry_price,
                stop_loss_price=stop_loss_price,
                take_profit_price=take_profit_price,
                position_size_usd=position_usd,
                market_regime=market_regime_enum
            )
            
            if not validation.passed:
                logger.warning(f'   ❌ Risk validation failed')
                logger.warning(f'      {validation.summary()}')
                self.signals_dropped_today += 1
                await self.db.log_signal({
                    'signal_id': f"RISK_DROPPED_{datetime.utcnow().timestamp()}",
                    'timestamp': datetime.utcnow().isoformat(),
                    'token_address': token_address,
                    'token_name': parsed.get('token_name'),
                    'token_symbol': token_symbol,
                    'entry_price': entry_price,
                    'position_size_usd': 0,
                    'confidence_score': ai_score['score'],
                    'reason': f'Risk validation failed: {" | ".join(validation.reasons)}',
                    'status': 'risk_dropped'
                })
                return
            
            logger.info(f'   ✅ Risk validation passed')
            logger.info(f'      {validation.summary()}')
            
            # Step 6: Send to Telegram
            logger.info(f'   📲 Sending to Telegram...')
            telegram_message = SignalFormatter.format_for_telegram(signal)
            
            if telegram_message:
                self.telegram.send_signal_alert(signal)
            
            # Step 7: Log to database
            await self.db.log_signal({
                'signal_id': signal['signal_id'],
                'timestamp': signal['timestamp'],
                'token_address': token_address,
                'token_name': parsed.get('token_name'),
                'token_symbol': token_symbol,
                'entry_price': signal['entry']['price'],
                'position_size_usd': signal['entry']['position_size_usd'],
                'confidence_score': ai_score['score'],
                'reason': ai_score['reasoning'],
                'status': 'sent'
            })
            
            logger.info(f'   ✅ SIGNAL SENT: {token_symbol} (Confidence {ai_score["score"]}/10)')
            self.signals_sent_today += 1
            
        except Exception as e:
            logger.error(f'Error processing token: {e}')
    
    async def _token_analyzed_recently(self, token_address: str, hours: int = 24) -> bool:
        """Check if token was analyzed in the last N hours (Async)"""
        try:
            from datetime import datetime, timedelta
            cutoff_time = (datetime.utcnow() - timedelta(hours=hours)).isoformat()
            
            # Use await for DB call
            analyzed = await self.db.get_recent_analysis(token_address, cutoff_time)
            return analyzed is not None
        except Exception as e:
            logger.debug(f'Error checking recent analysis: {e}')
            return False
    
    async def reset_daily_counters(self):
        """Reset daily tracking counters (Async)"""
        self.signals_sent_today = 0
        self.signals_dropped_today = 0
        self.tokens_found_today = 0
        logger.info('🔄 Daily counters reset')
        await self._send_pipeline_update()

    async def close(self):
        """Properly close all asynchronous clients"""
        logger.info("🛑 Closing ResearcherBot all async clients...")
        tasks = []
        clients = [
            self.dexscreener, self.solscan, self.helius, self.birdeye,
            self.coingecko, self.rss, self.reddit, self.twitter, self.pumpfun,
            self.macro_sentinel
        ]
        
        for client in clients:
            if client and hasattr(client, 'close'):
                if asyncio.iscoroutinefunction(client.close):
                    tasks.append(client.close())
                else:
                    client.close()
        
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        logger.info("✅ All clients closed.")
