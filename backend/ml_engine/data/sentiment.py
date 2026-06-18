import feedparser
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
import logging

logger = logging.getLogger(__name__)

class SentimentEngine:
    def __init__(self):
        self.analyzer = SentimentIntensityAnalyzer()
        # High quality free RSS feeds for crypto and general markets
        self.rss_feeds = [
            "https://cointelegraph.com/rss",
            "https://www.coindesk.com/arc/outboundfeeds/rss/",
            "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=10000664", # Finance
        ]

    def get_live_sentiment(self) -> float:
        """
        Fetches the latest headlines from multiple RSS feeds, scores them using VADER,
        and returns a normalized average sentiment score between -1.0 and 1.0.
        """
        try:
            total_score = 0.0
            count = 0
            
            for feed_url in self.rss_feeds:
                feed = feedparser.parse(feed_url)
                
                # Analyze top 10 recent headlines per feed
                for entry in feed.entries[:10]:
                    title = entry.title
                    # VADER scores a dictionary: {'neg', 'neu', 'pos', 'compound'}
                    # The compound score is normalized between -1.0 and 1.0
                    score = self.analyzer.polarity_scores(title)['compound']
                    
                    total_score += score
                    count += 1
            
            if count == 0:
                return 0.0
                
            average_sentiment = total_score / count
            logger.info(f"Live Market Sentiment: {average_sentiment:.3f} (Analyzed {count} headlines)")
            return average_sentiment
            
        except Exception as e:
            logger.error(f"Error fetching sentiment: {e}")
            return 0.0 # Return neutral sentiment on failure
