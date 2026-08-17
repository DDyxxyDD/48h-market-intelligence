"""GDELT DOC 2.0 public news-discovery collector."""

import json
from urllib.parse import urlencode

from src.collectors.base import CollectionResult, fetch_bytes, parse_timestamp
from src.models import Article


def collect_gdelt(query: str, label: str) -> CollectionResult:
    params = urlencode({"query": query, "mode": "ArtList", "maxrecords": 75,
                        "format": "json", "sort": "DateDesc", "timespan": "48h"})
    url = f"https://api.gdeltproject.org/api/v2/doc/doc?{params}"
    result = CollectionResult()
    try:
        payload = json.loads(fetch_bytes(url, timeout=20).decode("utf-8"))
        for item in payload.get("articles", []):
            published = parse_timestamp(item.get("seendate"))
            if item.get("title") and item.get("url") and published:
                result.articles.append(Article(item["title"], item["url"], item.get("domain") or "GDELT discovery",
                    published, metadata={"source_type": "news_discovery", "source_quality": 1.2,
                                         "collector": "gdelt", "query": label, "language": item.get("language")}))
        result.statuses.append({"source": f"GDELT: {label}", "url": url, "success": True, "articles": len(result.articles)})
    except Exception as exc:
        result.statuses.append({"source": f"GDELT: {label}", "url": url, "success": False, "articles": 0,
                                "error": f"{type(exc).__name__}: {exc}"[:300]})
    return result

