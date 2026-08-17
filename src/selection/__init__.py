"""Select the strongest articles within configured section quotas."""

from collections import defaultdict
from typing import Any

from src.models import Article


def select_articles(
    articles: list[Article], sections: dict[str, Any], threshold: float
) -> dict[str, list[Article]]:
    """Filter, rank, and limit articles for each briefing section."""
    grouped: dict[str, list[Article]] = defaultdict(list)
    for article in articles:
        if article.relevance_score >= threshold and article.section in sections:
            grouped[article.section].append(article)

    selected: dict[str, list[Article]] = {}
    for key, settings in sections.items():
        limit = settings.get("case_count", 0) or (
            settings.get("deep_dive_count", 0) + settings.get("quick_read_count", 0)
        )
        selected[key] = sorted(
            grouped[key], key=lambda item: (item.relevance_score, item.published_at), reverse=True
        )[:limit]
    return selected

