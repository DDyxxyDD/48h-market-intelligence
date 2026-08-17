from datetime import datetime, timedelta, timezone

from src.models import Article
from src.selection import select_articles


def make_article(title: str, score: float, age: int = 0) -> Article:
    return Article(
        title, f"https://example.com/{title}", "Example",
        datetime.now(timezone.utc) - timedelta(hours=age), section="ai", relevance_score=score,
    )


def test_selection_applies_threshold_quota_and_ranking() -> None:
    articles = [make_article("low", 4), make_article("second", 8), make_article("best", 9)]
    sections = {"ai": {"deep_dive_count": 1, "quick_read_count": 1}}
    result = select_articles(articles, sections, threshold=5)
    assert [item.title for item in result["ai"]] == ["best", "second"]

