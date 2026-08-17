"""Select the strongest articles within configured section quotas."""

from collections import defaultdict
from typing import Any

from src.models import Article
from src.source_quality import load_source_rules


def select_articles(
    articles: list[Article], sections: dict[str, Any], threshold: float, max_per_publisher: int | None = None
) -> dict[str, list[Article]]:
    """Filter, rank, and limit articles for each briefing section."""
    grouped: dict[str, list[Article]] = defaultdict(list)
    for article in articles:
        if article.relevance_score >= threshold and article.section in sections:
            grouped[article.section].append(article)

    if max_per_publisher is None:
        max_per_publisher = int(load_source_rules().get("selection", {}).get("max_per_publisher_per_section", 2))
    selected: dict[str, list[Article]] = {}
    for key, settings in sections.items():
        limit = settings.get("case_count", 0) or (
            settings.get("deep_dive_count", 0) + settings.get("quick_read_count", 0)
        )
        ranked = sorted(grouped[key], key=lambda item: (item.relevance_score,
                        item.metadata.get("source_quality", 0), item.published_at), reverse=True)
        chosen: list[Article] = []
        publisher_counts: dict[str, int] = defaultdict(int)
        deferred: list[Article] = []
        for article in ranked:
            publisher = article.metadata.get("underlying_publisher", article.source).casefold()
            if publisher_counts[publisher] >= max_per_publisher:
                article.metadata["selection_reason"] = "deferred_by_source_diversity"
                deferred.append(article)
                continue
            article.metadata["selection_reason"] = "selected_by_score_quality_and_diversity"
            chosen.append(article)
            publisher_counts[publisher] += 1
            if len(chosen) == limit:
                break
        # Diversity never leaves an otherwise-fillable quota empty.
        for article in deferred:
            if len(chosen) == limit:
                break
            article.metadata["selection_reason"] = "selected_to_fill_quota_after_diversity"
            chosen.append(article)
        selected[key] = chosen
    return selected
