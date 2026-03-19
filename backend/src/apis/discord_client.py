#!/usr/bin/env python3
"""
Discord API Client for Agent 4 (Intel Agent)
Monitors Discord communities for token projects
"""

import discord
from discord.ext import commands
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from collections import defaultdict
import asyncio

logger = logging.getLogger('discord')

class DiscordClient:
    """
    Connects to Discord servers to analyze token communities
    
    Monitors:
    - Server size (member count)
    - Activity level (messages per hour)
    - Growth rate (new members per hour)
    - Sentiment (positive/negative/neutral messages)
    - Key topics (what people are discussing)
    - Community health (organized or pump-and-dump)
    """
    
    def __init__(self, token: str):
        """
        Initialize Discord client
        
        Args:
            token: Discord bot token (get from Discord Developer Portal)
        """
        self.token = token
        self.bot = commands.Bot(command_prefix="!", intents=discord.Intents.default())
        self.bot.intents.message_content = True
        
        # Track servers we're monitoring
        self.servers_monitoring = {}
        self.message_cache = defaultdict(list)
        self.member_cache = defaultdict(dict)
        
        logger.info(f"[DISCORD] Client initialized with token")
        
        # Register event handlers
        @self.bot.event
        async def on_ready():
            logger.info(f"[DISCORD] Connected as {self.bot.user}")
        
        @self.bot.event
        async def on_message(message):
            if message.author == self.bot.user:
                return
            await self._cache_message(message)
    
    async def _cache_message(self, message: discord.Message):
        """Cache message for sentiment analysis"""
        server_id = message.guild.id if message.guild else None
        if server_id:
            self.message_cache[server_id].append({
                'author': str(message.author),
                'content': message.content,
                'timestamp': message.created_at,
                'reactions': len(message.reactions)
            })
            # Keep only last 1000 messages per server
            if len(self.message_cache[server_id]) > 1000:
                self.message_cache[server_id] = self.message_cache[server_id][-1000:]
    
    async def connect(self) -> bool:
        """
        Connect to Discord
        
        Returns:
            True if connection successful
        """
        try:
            logger.info("[DISCORD] Connecting...")
            # Run bot in background
            asyncio.create_task(self.bot.start(self.token))
            await asyncio.sleep(2)  # Wait for connection
            
            if self.bot.user:
                logger.info(f"[DISCORD] Connected as {self.bot.user}")
                return True
            return False
            
        except Exception as e:
            logger.error(f"[DISCORD] Connection failed: {e}")
            return False
    
    async def disconnect(self):
        """Disconnect from Discord"""
        try:
            await self.bot.close()
            logger.info("[DISCORD] Disconnected")
        except Exception as e:
            logger.error(f"[DISCORD] Disconnect error: {e}")
    
    async def find_server_by_name(self, server_name: str) -> Optional[discord.Guild]:
        """
        Find a Discord server by name
        
        Args:
            server_name: Name of the server to find
        
        Returns:
            Discord Guild object or None
        """
        try:
            for guild in self.bot.guilds:
                if guild.name.lower() == server_name.lower():
                    logger.info(f"[DISCORD] Found server: {guild.name}")
                    return guild
            
            logger.warning(f"[DISCORD] Server not found: {server_name}")
            return None
            
        except Exception as e:
            logger.error(f"[DISCORD] Error finding server: {e}")
            return None
    
    async def get_server_metrics(self, guild: discord.Guild) -> Dict:
        """
        Get metrics for a Discord server
        
        Args:
            guild: Discord Guild object
        
        Returns:
            Dict with:
            - server_name
            - member_count
            - online_count
            - channel_count
            - message_activity (messages/hour estimate)
            - growth_rate (new members/hour estimate)
        """
        try:
            members = await guild.fetch_members(limit=None).flatten()
            online_count = sum(1 for m in members if m.status != discord.Status.offline)
            
            # Get recent messages to estimate activity
            messages_1h = 0
            cutoff_time = datetime.utcnow() - timedelta(hours=1)
            
            for channel in guild.text_channels:
                try:
                    async for message in channel.history(limit=100, after=cutoff_time):
                        messages_1h += 1
                except:
                    pass
            
            metrics = {
                'server_name': guild.name,
                'server_id': guild.id,
                'member_count': len(members),
                'online_count': online_count,
                'channel_count': len(guild.text_channels),
                'messages_1h': messages_1h,
                'created_at': guild.created_at.isoformat()
            }
            
            logger.info(f"[DISCORD] {guild.name}: {len(members)} members, {messages_1h} msgs/1h")
            return metrics
            
        except Exception as e:
            logger.error(f"[DISCORD] Error getting metrics: {e}")
            return {}
    
    async def get_recent_messages(self, guild: discord.Guild, limit: int = 100) -> List[Dict]:
        """
        Get recent messages from a server for sentiment analysis
        
        Args:
            guild: Discord Guild object
            limit: Max messages to retrieve
        
        Returns:
            List of message dicts with content, author, timestamp
        """
        messages = []
        try:
            for channel in guild.text_channels:
                if not channel.permissions_for(guild.me).read_messages:
                    continue
                
                try:
                    async for message in channel.history(limit=limit):
                        if not message.author.bot:  # Skip bot messages
                            messages.append({
                                'content': message.content,
                                'author': str(message.author),
                                'channel': channel.name,
                                'timestamp': message.created_at.isoformat(),
                                'reactions': len(message.reactions)
                            })
                except:
                    pass
            
            logger.info(f"[DISCORD] Retrieved {len(messages)} recent messages")
            return messages
            
        except Exception as e:
            logger.error(f"[DISCORD] Error getting messages: {e}")
            return []
    
    async def analyze_server(self, guild: discord.Guild, 
                            sentiment_analyzer=None) -> Dict:
        """
        Comprehensive analysis of a Discord server
        
        Args:
            guild: Discord Guild object
            sentiment_analyzer: Optional sentiment analyzer function
        
        Returns:
            Analysis dict with:
            - server_metrics
            - message_sentiment (positive/negative/neutral %)
            - activity_level (low/moderate/high)
            - growth_pattern (organic/spike/declining)
            - score (0-10)
            - verdict (healthy/suspicious/inactive)
        """
        try:
            # Get server metrics
            metrics = await self.get_server_metrics(guild)
            
            # Get recent messages
            messages = await self.get_recent_messages(guild, limit=200)
            
            # Analyze sentiment if analyzer provided
            sentiment = {'positive': 0.0, 'neutral': 0.0, 'negative': 0.0}
            if sentiment_analyzer and messages:
                sentiments = [sentiment_analyzer(msg['content']) for msg in messages]
                total = len(sentiments)
                sentiment['positive'] = sum(1 for s in sentiments if s == 'positive') / total
                sentiment['neutral'] = sum(1 for s in sentiments if s == 'neutral') / total
                sentiment['negative'] = sum(1 for s in sentiments if s == 'negative') / total
            
            # Determine activity level
            messages_1h = metrics.get('messages_1h', 0)
            if messages_1h > 50:
                activity_level = 'high'
                activity_score = 2.0
            elif messages_1h > 10:
                activity_level = 'moderate'
                activity_score = 1.0
            else:
                activity_level = 'low'
                activity_score = 0.0
            
            # Detect growth pattern
            member_count = metrics.get('member_count', 0)
            online_count = metrics.get('online_count', 0)
            online_ratio = online_count / member_count if member_count > 0 else 0
            
            if online_ratio > 0.5:
                growth_pattern = 'organic'
                growth_score = 1.0
            elif online_ratio > 0.2:
                growth_pattern = 'stable'
                growth_score = 0.5
            else:
                growth_pattern = 'declining'
                growth_score = 0.0
            
            # Calculate overall score (0-10)
            score = 0
            score += min(2, member_count / 500)  # More members = better
            score += activity_score  # Activity
            score += growth_score  # Growth pattern
            score += sentiment['positive'] * 3  # Positive sentiment boost
            score -= sentiment['negative'] * 1.5  # Negative sentiment penalty
            score = max(0, min(10, score))
            
            # Determine verdict
            if score >= 7 and activity_level in ['moderate', 'high']:
                verdict = 'HEALTHY COMMUNITY'
            elif score >= 5:
                verdict = 'DEVELOPING'
            elif activity_level == 'low':
                verdict = 'INACTIVE'
            else:
                verdict = 'SUSPICIOUS'
            
            analysis = {
                'server_name': metrics.get('server_name'),
                'server_id': metrics.get('server_id'),
                'member_count': metrics.get('member_count'),
                'online_count': metrics.get('online_count'),
                'online_ratio': round(online_ratio, 2),
                'messages_1h': metrics.get('messages_1h'),
                'activity_level': activity_level,
                'sentiment': sentiment,
                'growth_pattern': growth_pattern,
                'score': round(score, 1),
                'confidence': round(min(1.0, len(messages) / 100), 2),
                'verdict': verdict,
                'analyzed_at': datetime.utcnow().isoformat()
            }
            
            logger.info(f"[DISCORD] Analysis complete: {verdict} (score: {score:.1f})")
            return analysis
            
        except Exception as e:
            logger.error(f"[DISCORD] Error analyzing server: {e}")
            return {
                'error': str(e),
                'verdict': 'ERROR'
            }


class AsyncDiscordClient:
    """
    Async wrapper for Discord client suitable for use in async pipelines
    """
    
    def __init__(self, token: str):
        self.client = DiscordClient(token)
        self.connected = False
    
    async def initialize(self) -> bool:
        """Initialize and connect to Discord"""
        self.connected = await self.client.connect()
        return self.connected
    
    async def analyze_by_name(self, server_name: str, sentiment_analyzer=None) -> Dict:
        """
        Analyze a server by name
        
        Args:
            server_name: Discord server name
            sentiment_analyzer: Sentiment analysis function
        
        Returns:
            Analysis results
        """
        if not self.connected:
            logger.warning("[DISCORD] Not connected, cannot analyze")
            return {'error': 'Not connected', 'verdict': 'ERROR'}
        
        guild = await self.client.find_server_by_name(server_name)
        if not guild:
            return {'error': f'Server not found: {server_name}', 'verdict': 'ERROR'}
        
        return await self.client.analyze_server(guild, sentiment_analyzer)
    
    async def cleanup(self):
        """Cleanup and disconnect"""
        await self.client.disconnect()


if __name__ == '__main__':
    # Test the client
    import os
    from dotenv import load_dotenv
    
    load_dotenv()
    token = os.getenv('DISCORD_BOT_TOKEN')
    
    if token:
        async def test():
            client = AsyncDiscordClient(token)
            if await client.initialize():
                # Test analyzing a server (replace with actual server name)
                result = await client.analyze_by_name('Test Server')
                print(f"Analysis: {result}")
                await client.cleanup()
        
        asyncio.run(test())
    else:
        print("Error: DISCORD_BOT_TOKEN not set in .env")
