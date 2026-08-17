"""Deterministic article deduplication."""

from urllib.parse import urlsplit, urlunsplit

from src.models import Article


def _canonical_url(url: str) -> str:
    parts = urlsplit(url)
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path.rstrip("/"), "", ""))


def deduplicate_articles(articles: list[Article]) -> list[Article]:
    """Keep the first article for each canonical URL or normalized title."""
    unique: list[Article] = []
    seen_urls: set[str] = set()
    seen_titles: set[str] = set()
    for article in articles:
        url_key = _canonical_url(article.url)
        title_key = " ".join(article.title.casefold().split())
        if url_key in seen_urls or title_key in seen_titles:
            continue
        seen_urls.add(url_key)
        seen_titles.add(title_key)
        unique.append(article)
    return unique

