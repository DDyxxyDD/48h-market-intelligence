from datetime import datetime, timezone

from src.deduplication import deduplicate_articles
from src.models import Article


def article(title: str, url: str) -> Article:
    return Article(title, url, "Example", datetime.now(timezone.utc))


def test_deduplicates_tracking_urls_and_normalized_titles() -> None:
    articles = [
        article("Same Story", "https://example.com/story?utm_source=test"),
        article("Other headline", "https://example.com/story/"),
        article("  SAME   STORY ", "https://another.example/story"),
    ]
    assert deduplicate_articles(articles) == [articles[0]]

