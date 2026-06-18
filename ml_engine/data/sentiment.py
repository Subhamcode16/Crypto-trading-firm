import logging
import feedparser
from datetime import datetime
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

logger = logging.getLogger(__name__)

class SentimentEngine:
    def __init__(self):
        self.analyzer = SentimentIntensityAnalyzer()
        
        self.rss_feeds = [
            "https://decrypt.co/feed"
        ]
        
        import requests
        self.http_client = requests.Session()
        self.http_client.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"})

    def get_sentiment(self) -> dict:
        """
        Fetches headlines from RSS feeds, scores them using VADER,
        and returns a dict with aggregated score and parsed headlines.
        """
        scores = []
        headlines = []
        for url in self.rss_feeds:
            try:
                resp = self.http_client.get(url)
                feed = feedparser.parse(resp.content)
                for entry in feed.entries[:5]: # Top 5 recent headlines per feed
                    title = entry.title
                    score = self.analyzer.polarity_scores(title)["compound"]
                    scores.append(score)
                    headlines.append({
                        "title": title,
                        "score": score,
                        "source": url.split("//")[1].split("/")[0],
                        "time": entry.published if hasattr(entry, "published") else datetime.now().isoformat()
                    })
            except Exception as e:
                logger.error(f"[Sentiment] Error parsing feed {url}: {e}")
        
        if not scores:
            return {"score": 0.0, "headlines": []}
        
        avg_score = sum(scores) / len(scores)
        # Sort headlines by absolute score to show most impactful news first
        headlines.sort(key=lambda x: abs(x["score"]), reverse=True)
        
        logger.info(f"[Sentiment] Computed Score: {avg_score:.2f} across {len(scores)} articles")
        return {"score": avg_score, "headlines": headlines}

if __name__ == "__main__":
    engine = SentimentEngine()
    print("Live Sentiment Score:", engine.get_sentiment())
