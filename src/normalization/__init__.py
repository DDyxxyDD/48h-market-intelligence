"""Article normalization helpers."""

from src.models import Article


def normalize_articles(articles: list[Article]) -> list[Article]:
    """Trim common text fields and normalize ticker symbols."""
    for article in articles:
        article.title = " ".join(article.title.split())
        article.summary = " ".join(article.summary.split())
        article.source = article.source.strip()
        article.tickers = sorted({ticker.strip().upper() for ticker in article.tickers if ticker.strip()})
    return articles

