"""Official FDA collection via openFDA plus respectful announcement-list parsing."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
import json
from urllib.parse import urlencode, urljoin

from src.collectors.base import CollectionResult, fetch_with_attempts, parse_timestamp
from src.models import Article
from src.source_quality import apply_source_quality

FDA_PUBLISHER = "U.S. Food and Drug Administration"
FDA_ANNOUNCEMENTS = "https://www.fda.gov/news-events/fda-newsroom/press-announcements"


class _FDAListingParser(HTMLParser):
    """Parse links and adjacent HTML5 time elements without executing page content."""

    def __init__(self):
        super().__init__()
        self.items: list[dict[str, str]] = []
        self._link: dict[str, str] | None = None
        self._in_time = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "a" and attrs.get("href", "").startswith("/"):
            self._link = {"url": attrs["href"], "title": "", "date": ""}
        elif tag == "time" and self._link is not None:
            self._in_time = True
            self._link["date"] = attrs.get("datetime", "")

    def handle_data(self, data):
        if self._link is not None:
            if self._in_time and not self._link["date"]:
                self._link["date"] += data.strip()
            elif not self._in_time:
                self._link["title"] += data.strip()

    def handle_endtag(self, tag):
        if tag == "time":
            self._in_time = False
        elif tag == "a" and self._link is not None:
            if self._link["title"] and any(term in self._link["url"] for term in ("press-announcements", "safety-communication", "recall")):
                self.items.append(self._link)
            self._link = None


def parse_fda_listing(html: str, base_url: str = FDA_ANNOUNCEMENTS) -> list[Article]:
    parser = _FDAListingParser()
    parser.feed(html)
    articles = []
    for item in parser.items:
        published = parse_timestamp(item["date"])
        if published:
            articles.append(apply_source_quality(Article(item["title"], urljoin(base_url, item["url"]),
                FDA_PUBLISHER, published, metadata={"collector": "fda_html", "source_type": "official_regulator"})))
    return articles


def collect_openfda(now: datetime | None = None, fetcher=fetch_with_attempts) -> CollectionResult:
    """Collect market-relevant official drug-enforcement/recall records."""
    now = now or datetime.now(timezone.utc)
    # Enforcement reports can be posted with reporting lag. Fetch a modest 30-day API
    # window and let the shared briefing lookback reject stale records transparently.
    start = now - timedelta(days=30)
    params = urlencode({"search": f"report_date:[{start:%Y%m%d} TO {now:%Y%m%d}]", "limit": 100})
    url = f"https://api.fda.gov/drug/enforcement.json?{params}"
    result = CollectionResult()
    try:
        raw, attempts = fetcher(url, timeout=20, retries=1, backoff=0.75)
        for item in json.loads(raw).get("results", []):
            published = parse_timestamp(item.get("report_date"))
            product = " ".join((item.get("product_description") or "FDA drug recall").split())
            reason = " ".join((item.get("reason_for_recall") or "").split())
            if not published:
                continue
            title = f"FDA {item.get('classification', 'recall')}: {product[:180]}"
            article = Article(title, url, FDA_PUBLISHER, published, summary=reason[:1200],
                metadata={"collector": "openfda", "source_type": "official_regulator",
                          "recall_number": item.get("recall_number"), "event_id": item.get("event_id")})
            result.articles.append(apply_source_quality(article))
        result.statuses.append({"source": "openFDA Drug Enforcement", "url": url, "success": True,
                                "articles": len(result.articles), "attempts": attempts, "retries": attempts - 1})
    except Exception as exc:
        result.statuses.append({"source": "openFDA Drug Enforcement", "url": url, "success": False,
                                "articles": 0, "attempts": getattr(exc, "attempts", 1),
                                "retries": max(0, getattr(exc, "attempts", 1) - 1),
                                "error": f"{type(exc).__name__}: {exc}"[:300]})
    return result


def collect_fda_announcements(fetcher=fetch_with_attempts) -> CollectionResult:
    result = CollectionResult()
    try:
        raw, attempts = fetcher(FDA_ANNOUNCEMENTS, timeout=15, retries=1, backoff=0.75)
        result.articles = parse_fda_listing(raw.decode("utf-8", errors="replace"))
        result.statuses.append({"source": "FDA Press Announcements", "url": FDA_ANNOUNCEMENTS,
                                "success": True, "articles": len(result.articles), "attempts": attempts,
                                "retries": attempts - 1})
    except Exception as exc:
        result.statuses.append({"source": "FDA Press Announcements", "url": FDA_ANNOUNCEMENTS,
                                "success": False, "articles": 0, "attempts": getattr(exc, "attempts", 1),
                                "retries": max(0, getattr(exc, "attempts", 1) - 1),
                                "error": f"{type(exc).__name__}: {exc}"[:300]})
    return result
