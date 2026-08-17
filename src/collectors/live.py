"""Fault-tolerant orchestration and normalization of all live sources."""

from datetime import datetime, timedelta, timezone

from src.collectors.base import CollectionResult
from src.collectors.gdelt import collect_gdelt
from src.collectors.official_sources import collect_official_sources
from src.collectors.rss import collect_rss

GDELT_QUERIES = {
    "AI": '(OpenAI OR Anthropic OR DeepMind OR NVIDIA OR AMD OR "artificial intelligence" OR "AI model")',
    "Macro": '(Federal Reserve OR ECB OR "Bank of England" OR "Bank of Japan" OR inflation OR employment OR "interest rates" OR forex)',
    "Healthcare": '(FDA OR "clinical trial" OR biotech OR pharma OR Medicare) (approval OR results OR acquisition OR guidance OR safety)',
}

PUBLIC_DISCOVERY_FEEDS = [
    ("Google News: AI", "https://news.google.com/rss/search?q=%28OpenAI+OR+Anthropic+OR+DeepMind+OR+NVIDIA+OR+%22AI+model%22%29+when%3A2d&hl=en-US&gl=US&ceid=US%3Aen"),
    ("Google News: Macro", "https://news.google.com/rss/search?q=%28%22Federal+Reserve%22+OR+ECB+OR+inflation+OR+%22interest+rates%22+OR+forex%29+when%3A2d&hl=en-US&gl=US&ceid=US%3Aen"),
    ("Google News: Healthcare", "https://news.google.com/rss/search?q=%28FDA+OR+%22clinical+trial%22+OR+biotech+OR+pharma%29+%28approval+OR+acquisition+OR+guidance+OR+safety%29+when%3A2d&hl=en-US&gl=US&ceid=US%3Aen"),
]


def filter_by_lookback(articles, hours: int, now: datetime | None = None):
    """Return (recent, rejected) using an inclusive timezone-aware UTC window."""
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    cutoff = now - timedelta(hours=hours)
    recent, rejected = [], []
    for article in articles:
        published = article.published_at.astimezone(timezone.utc)
        if cutoff <= published <= now + timedelta(minutes=10):
            recent.append(article)
        else:
            article.metadata["rejection_reason"] = "outside_lookback_window"
            rejected.append(article)
    return recent, rejected


def collect_live_articles(lookback_hours: int, now: datetime | None = None) -> tuple[list, list, list[dict]]:
    """Collect independently so one unavailable public endpoint cannot abort a run."""
    results: list[CollectionResult] = collect_official_sources()
    results.extend(collect_gdelt(query, label) for label, query in GDELT_QUERIES.items())
    results.extend(collect_rss(name, url, "news_discovery", 1.2) for name, url in PUBLIC_DISCOVERY_FEEDS)
    articles = [article for result in results for article in result.articles]
    statuses = [status for result in results for status in result.statuses]
    recent, stale = filter_by_lookback(articles, lookback_hours, now)
    return recent, stale, statuses
