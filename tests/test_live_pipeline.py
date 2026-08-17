import json
from datetime import datetime, timedelta, timezone

from src.classification import classify_articles
from src.collectors.base import parse_timestamp
from src.collectors.live import filter_by_lookback
from src.collectors.rss import collect_rss
from src.deduplication import deduplicate_with_rejections
from src.models import Article
from src.scoring import score_articles


def make(title="OpenAI launches major AI model", age=2, source_quality=1.0):
    return Article(title, "https://example.com/story", "Example", datetime.now(timezone.utc) - timedelta(hours=age),
                   summary="New artificial intelligence product", metadata={"source_quality": source_quality})


def test_timestamp_parsing_and_lookback():
    assert parse_timestamp("Mon, 17 Aug 2026 10:00:00 GMT") == datetime(2026, 8, 17, 10, tzinfo=timezone.utc)
    assert parse_timestamp("2026-08-17T10:00:00Z") == datetime(2026, 8, 17, 10, tzinfo=timezone.utc)
    assert parse_timestamp("not a date") is None
    now = datetime.now(timezone.utc)
    recent, stale = filter_by_lookback([make(age=47), make("old", age=49)], 48, now)
    assert len(recent) == len(stale) == 1


def test_collector_failure_is_reported_not_raised(monkeypatch):
    monkeypatch.setattr("src.collectors.rss.fetch_bytes", lambda *args, **kwargs: (_ for _ in ()).throw(TimeoutError("offline")))
    result = collect_rss("Broken", "https://example.invalid/feed")
    assert result.articles == [] and result.statuses[0]["success"] is False


def test_classification_and_explainable_scoring():
    article = classify_articles([make()])[0]
    assert article.section == "ai"
    score_articles([article], {"ai": {"topics": ["model launches", "AI products"]}})
    assert 0 < article.relevance_score <= 10
    assert set(article.metadata["score_breakdown"]) == {"interest_fit", "materiality", "source_quality", "recency", "novelty"}


def test_deduplication_prefers_stronger_source():
    weak, strong = make(source_quality=1), make(source_quality=3)
    strong.url = "https://official.example/release"
    unique, rejected = deduplicate_with_rejections([weak, strong])
    assert unique == [strong] and rejected[0].metadata["rejection_reason"] == "duplicate"


def test_diagnostics_shape(tmp_path, monkeypatch):
    from main import run_live_pipeline
    monkeypatch.setattr("main.collect_live_articles", lambda hours: ([make()], [], [{"source": "mock", "success": True}]))
    output, diagnostics = run_live_pipeline(tmp_path / "live.html", tmp_path / "candidates.json")
    stored = json.loads((tmp_path / "candidates.json").read_text())
    assert output.exists() and diagnostics == stored
    assert {"title", "url", "source", "published_at", "section", "relevance_score", "score_breakdown", "selected"} <= stored["candidates"][0].keys()
