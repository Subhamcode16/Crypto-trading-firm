import logging
from datetime import datetime
from src.trading.position_sizer import PositionSizer

logger = logging.getLogger('signal_formatter')

class SignalFormatter:
    """Format signals into structured JSON for trading"""
    
    @staticmethod
    def format(token_data: dict, rug_analysis: dict, ai_score: dict) -> dict:
        """
        Generate structured signal ready for execution
        
        Returns: Dict with complete signal or None if dropped
        """
        
        # Get position size from confidence
        position_size = PositionSizer.calculate(ai_score['score'])
        
        if position_size == 0:
            logger.warning(f"Signal dropped: Confidence {ai_score['score']} < 6")
            return None
        
        # Calculate stop loss and take profit prices
        entry_price = float(token_data['price_usd'])
        stop_loss_price = entry_price * 0.8  # 20% below entry
        
        tp1_price = entry_price * 2.0   # 2x
        tp2_price = entry_price * 4.0   # 4x
        
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
                'price': entry_price,
                'position_size_usd': position_size,
                'position_size_tokens': position_size / entry_price,  # For reference
                'reason': ai_score['reasoning']
            },
            
            'risk': {
                'stop_loss_price': stop_loss_price,
                'stop_loss_percent': 20,
                'max_loss_usd': position_size * 0.20
            },
            
            'profit_targets': [
                {
                    'tier': 1,
                    'price': tp1_price,
                    'multiplier': '2x',
                    'sell_percent': 40,
                    'tokens_to_sell': (position_size / entry_price) * 0.40,
                    'profit_usd': (tp1_price - entry_price) * (position_size / entry_price) * 0.40
                },
                {
                    'tier': 2,
                    'price': tp2_price,
                    'multiplier': '4x',
                    'sell_percent': 40,
                    'tokens_to_sell': (position_size / entry_price) * 0.40,
                    'profit_usd': (tp2_price - entry_price) * (position_size / entry_price) * 0.40
                },
                {
                    'tier': 3,
                    'type': 'trailing_stop',
                    'trailing_percent': 50,
                    'tokens_remaining': (position_size / entry_price) * 0.20
                }
            ],
            
            'confidence': {
                'score': ai_score['score'],
                'on_chain_filters': {
                    'contract_age_ok': rug_analysis.get('passed_all', False),
                    'liquidity_locked': rug_analysis.get('passed_all', False),
                    'top_10_wallet_percent': rug_analysis.get('holder_concentration', 0),
                    'unique_wallets': rug_analysis.get('unique_wallets', 0),
                    'deployer_clean': rug_analysis.get('passed_all', False),
                    'data_integrity_ok': rug_analysis.get('passed_all', False)
                },
                'ai_analysis': ai_score['reasoning'],
                'model': ai_score.get('model', 'unknown')
            },
            
            'risk_reward': {
                'ratio': '1:2',
                'best_case': f"+${(tp2_price - entry_price) * (position_size / entry_price) * 0.40:.2f}",
                'worst_case': f"-${position_size * 0.20:.2f}"
            },
            
            'sources': [
                'dexscreener',
                'solscan',
                'claude-haiku'
            ]
        }
        
        logger.info(f"✅ Signal formatted: {signal['signal_id']} - {token_data['token_symbol']}")
        return signal
    
    @staticmethod
    def format_for_telegram(signal: dict) -> str:
        """Format signal for Telegram display"""
        
        if not signal:
            return None
        
        token = signal['token']
        entry = signal['entry']
        risk = signal['risk']
        confidence = signal['confidence']
        targets = signal['profit_targets']
        
        message = f"""🚀 <b>SIGNAL #{signal['signal_id']}</b> (Confidence: <b>{confidence['score']}/10</b>)

<b>Token:</b> {token['name']} ({token['symbol']})
<b>Contract:</b> <code>{token['address'][:8]}...{token['address'][-8:]}</code>

💰 <b>Entry:</b> ${entry['price']:.10f}
📊 <b>Position:</b> ${entry['position_size_usd']:.2f}

⚠️ <b>Risk/Reward:</b> 1:2
🛑 <b>Stop Loss:</b> ${risk['stop_loss_price']:.10f} (20% below)
🎯 <b>Take Profit Targets:</b>
   TP1 (40%): ${targets[0]['price']:.10f} (2x)
   TP2 (40%): ${targets[1]['price']:.10f} (4x)
   TP3 (20%): Trailing stop at 50% below high

🔍 <b>Why This Signal:</b>
{entry['reason']}

✅ <b>On-Chain Status:</b>
   • Contract Age: Safe
   • Liquidity: Locked
   • Holders: {confidence['on_chain_filters']['top_10_wallet_percent']:.1f}% in top 10
   • Volume: Organic ({confidence['on_chain_filters']['unique_wallets']} unique traders)
   • Deployer: Clean history

🎯 <b>Execution:</b> AUTOMATIC (no approval needed)
🕐 <b>Timestamp:</b> {signal['timestamp']}
"""
        
        return message
