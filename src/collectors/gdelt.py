"""GDELT DOC 2.0 public news-discovery collector."""

import json
from urllib.parse import urlencode

from src.collectors.base import CollectionResult, fetch_with_attempts, parse_timestamp
from src.models import Article
from src.source_quality import apply_source_quality


def collect_gdelt(query: str, label: str, fetcher=fetch_with_attempts) -> CollectionResult:
    params = urlencode({"query": query, "mode": "ArtList", "maxrecords": 75,
                        "format": "json", "sort": "DateDesc", "timespan": "48h"})
    url = f"https://api.gdeltproject.org/api/v2/doc/doc?{params}"
    result = CollectionResult()
    try:
        raw, attempts = fetcher(url, timeout=20, retries=2, backoff=0.75)
        payload = json.loads(raw.decode("utf-8"))
        for item in payload.get("articles", []):
            published = parse_timestamp(item.get("seendate"))
            if item.get("title") and item.get("url") and published:
                publisher = item.get("domain") or "Unknown publisher"
                article = Article(item["title"], item["url"], publisher, published,
                    metadata={"source_type": "news_discovery", "collector": "gdelt",
                              "query": label, "language": item.get("language")})
                result.articles.append(apply_source_quality(article, publisher))
        result.statuses.append({"source": f"GDELT: {label}", "url": url, "success": True,
                                "articles": len(result.articles), "attempts": attempts, "retries": attempts - 1})
    except Exception as exc:
        result.statuses.append({"source": f"GDELT: {label}", "url": url, "success": False, "articles": 0,
                                "attempts": getattr(exc, "attempts", 1),
                                "retries": max(0, getattr(exc, "attempts", 1) - 1),
                                "error": f"{type(exc).__name__}: {exc}"[:300]})
    return result
