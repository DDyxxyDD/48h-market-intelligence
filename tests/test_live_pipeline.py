import json
from datetime import datetime, timedelta, timezone
from urllib.error import HTTPError

from src.classification import classify_articles
from src.collectors.base import parse_timestamp
from src.collectors.live import filter_by_lookback
from src.collectors.rss import collect_rss
from src.collectors.base import fetch_with_attempts
from src.collectors.fda import parse_fda_listing
from src.deduplication import deduplicate_with_rejections
from src.models import Article
from src.scoring import score_articles
from src.quality_gates import apply_healthcare_gate
from src.selection import select_articles
from src.source_quality import apply_source_quality, classify_source


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
    monkeypatch.setattr("src.collectors.rss.fetch_with_attempts", lambda *args, **kwargs: (_ for _ in ()).throw(TimeoutError("offline")))
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
    assert unique == [strong] and rejected[0].metadata["rejection_reason"] == "duplicate_event"


def test_diagnostics_shape(tmp_path, monkeypatch):
    from main import run_live_pipeline
    monkeypatch.setattr("main.collect_live_articles", lambda hours: ([make()], [], [{"source": "mock", "success": True}]))
    output, diagnostics = run_live_pipeline(tmp_path / "live.html", tmp_path / "candidates.json")
    stored = json.loads((tmp_path / "candidates.json").read_text())
    assert output.exists() and diagnostics == stored
    assert {"title", "url", "source", "published_at", "section", "relevance_score", "score_breakdown", "selected"} <= stored["candidates"][0].keys()


def test_source_tiers_and_unknown_fallback():
    assert classify_source("Reuters")[0] == "B"
    assert classify_source("Unfamiliar Local Publisher")[0] == "D"
    assert classify_source("Anything", "https://www.fda.gov/example")[0] == "A"


def test_google_rss_preserves_underlying_publisher(monkeypatch):
    feed = b'''<rss><channel><item><title>Material story - Reuters</title>
    <link>https://news.google.com/story</link><pubDate>Mon, 17 Aug 2026 10:00:00 GMT</pubDate>
    <source url="https://reuters.com">Reuters</source></item></channel></rss>'''
    monkeypatch.setattr("src.collectors.rss.fetch_with_attempts", lambda *args, **kwargs: (feed, 1))
    article = collect_rss("Google News: Test", "https://news.google.com/rss", "news_discovery").articles[0]
    assert article.title == "Material story" and article.source == "Reuters"
    assert article.metadata["source_tier"] == "B"


def test_transient_http_retry_records_attempts(monkeypatch):
    calls = []

    class Response:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def read(self, size): return b"ok"

    def flaky(request, timeout):
        calls.append(request.full_url)
        if len(calls) < 3:
            raise HTTPError(request.full_url, 503, "busy", {}, None)
        return Response()

    monkeypatch.setattr("src.collectors.base.urlopen", flaky)
    data, attempts = fetch_with_attempts("https://example.com", retries=2, backoff=0, sleep=lambda _: None)
    assert data == b"ok" and attempts == 3


def test_fda_html_fixture_is_official_tier_a():
    html = '''<div class="view-row"><a href="/news-events/press-announcements/fda-approves-example">
    FDA Approves Example Drug <time datetime="2026-08-17T10:00:00Z"></time></a></div>'''
    articles = parse_fda_listing(html)
    assert len(articles) == 1
    assert articles[0].source == "U.S. Food and Drug Administration"
    assert articles[0].metadata["source_tier"] == "A"


def test_event_clustering_prefers_quality_and_preserves_alternates():
    low = make("Japan 10-year bond yield hits three-decade high as inflation pressures mount", source_quality=1)
    high = make("Japan's 10-year bond yield hits 3-decade high as inflation pressure mounts", source_quality=3)
    low.section = high.section = "macro_rates_fx"
    low.source, high.source = "Unknown", "Reuters"
    high.url = "https://reuters.example/boj"
    unique, duplicates = deduplicate_with_rejections([low, high])
    assert unique == [high] and duplicates == [low]
    assert high.metadata["alternate_sources"] == ["Unknown"]
    assert low.metadata["event_cluster_id"] == high.metadata["event_cluster_id"]

    first = make("OncoSil secures FDA approval for targeted bile duct cancer device")
    second = make("OncoSil Medical secures US FDA approval for OncoSil device, opening market")
    first.section = second.section = "us_healthcare_equities"
    second.url = "https://example.net/oncosil"
    assert len(deduplicate_with_rejections([first, second])[0]) == 1


def test_selection_enforces_source_diversity():
    articles = []
    for index, source in enumerate(["Reuters", "Reuters", "Reuters", "Associated Press"]):
        item = make(f"Distinct material story {index}")
        item.source = source
        item.section = "ai"
        item.relevance_score = 9 - index / 10
        item.metadata["underlying_publisher"] = source
        articles.append(item)
    selected = select_articles(articles, {"ai": {"deep_dive_count": 3}}, 5, max_per_publisher=2)["ai"]
    assert [item.source for item in selected] == ["Reuters", "Reuters", "Associated Press"]


def test_healthcare_noise_gate_keeps_material_news():
    noise = make("Ten wellness and healthy eating tips")
    material = make("FDA approves pivotal Phase 3 oncology drug")
    noise.section = material.section = "us_healthcare_equities"
    accepted, rejected = apply_healthcare_gate([noise, material])
    assert accepted == [material] and rejected == [noise]
    assert noise.metadata["rejection_reason"] == "healthcare_noise_gate"
