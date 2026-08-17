"""Deterministic article/event deduplication."""

from difflib import SequenceMatcher
import re
from urllib.parse import urlsplit, urlunsplit

from src.models import Article


def _canonical_url(url: str) -> str:
    parts = urlsplit(url)
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path.rstrip("/"), "", ""))


def _title(title: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", title.casefold()))


def _quality(article: Article) -> float:
    return float(article.metadata.get("source_quality", 0))


def deduplicate_articles(articles: list[Article]) -> list[Article]:
    """Keep the first article for each canonical URL or normalized title."""
    unique, _ = deduplicate_with_rejections(articles)
    return unique


def deduplicate_with_rejections(articles: list[Article]) -> tuple[list[Article], list[Article]]:
    """Collapse canonical URLs and highly similar titles, preferring original-quality sources."""
    unique: list[Article] = []
    rejected: list[Article] = []
    # Python's stable sort preserves collector order when quality is equal.
    for article in sorted(articles, key=_quality, reverse=True):
        url_key = _canonical_url(article.url)
        title_key = _title(article.title)
        duplicate = next((kept for kept in unique if _canonical_url(kept.url) == url_key or
                          _title(kept.title) == title_key or
                          (min(len(title_key), len(_title(kept.title))) >= 35 and
                           SequenceMatcher(None, title_key, _title(kept.title)).ratio() >= 0.88)), None)
        if duplicate:
            article.metadata["rejection_reason"] = "duplicate"
            article.metadata["duplicate_of"] = duplicate.url
            rejected.append(article)
            continue
        unique.append(article)
    return unique, rejected
