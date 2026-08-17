"""Simple, explainable relevance scoring."""

from typing import Any

from src.models import Article


def score_articles(articles: list[Article], sections: dict[str, Any]) -> list[Article]:
    """Score articles from 0 to 10 using configured topic keyword overlap."""
    for article in articles:
        section = sections.get(article.section, {})
        text = f"{article.title} {article.summary}".casefold()
        matches = sum(1 for topic in section.get("topics", []) if any(word in text for word in topic.casefold().split()))
        article.relevance_score = min(10.0, 4.0 + matches * 1.5)
        article.metadata["topic_matches"] = matches
    return articles

