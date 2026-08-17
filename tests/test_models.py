from datetime import datetime, timezone

import pytest

from src.models import Article


def test_article_stores_defaults() -> None:
    article = Article("A title", "https://example.com/a", "Example", datetime.now(timezone.utc))
    assert article.tickers == []
    assert article.metadata == {}
    assert article.relevance_score == 0.0


def test_article_rejects_invalid_score() -> None:
    with pytest.raises(ValueError, match="between 0 and 10"):
        Article("A title", "https://example.com/a", "Example", datetime.now(timezone.utc), relevance_score=11)

