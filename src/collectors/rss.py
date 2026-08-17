"""Generic, defensive RSS/Atom collector."""

from __future__ import annotations

from html import unescape
import re
from urllib.parse import urljoin
from xml.etree import ElementTree

from src.collectors.base import CollectionResult, fetch_with_attempts, parse_timestamp
from src.models import Article
from src.source_quality import apply_source_quality

_TAGS = re.compile(r"<[^>]+>")


def _text(node: ElementTree.Element, names: tuple[str, ...]) -> str:
    for child in node.iter():
        if child.tag.rsplit("}", 1)[-1] in names and child.text:
            return child.text.strip()
    return ""


def _link(node: ElementTree.Element) -> str:
    for child in node.iter():
        if child.tag.rsplit("}", 1)[-1] == "link":
            return (child.get("href") or child.text or "").strip()
    return ""


def collect_rss(name: str, url: str, source_type: str = "rss", quality: float = 2.0) -> CollectionResult:
    result = CollectionResult()
    try:
        raw, attempts = fetch_with_attempts(url)
        root = ElementTree.fromstring(raw)
        nodes = [node for node in root.iter() if node.tag.rsplit("}", 1)[-1] in {"item", "entry"}]
        for node in nodes:
            title, link = _text(node, ("title",)), _link(node)
            published = parse_timestamp(_text(node, ("pubDate", "published", "updated", "date")))
            if not title or not link or not published:
                continue
            description = unescape(_TAGS.sub(" ", _text(node, ("description", "summary", "content"))))
            underlying = _text(node, ("source",)) if source_type == "news_discovery" else name
            clean_title = unescape(title)
            # Google appends " - Publisher" even though it also supplies a source element.
            if underlying and clean_title.casefold().endswith(f" - {underlying}".casefold()):
                clean_title = clean_title[:-(len(underlying) + 3)].strip()
            article = Article(title=clean_title, url=urljoin(url, link), source=underlying or name,
                published_at=published, summary=" ".join(description.split())[:1200],
                metadata={"source_type": source_type, "collector": "google_news" if name.startswith("Google News") else "rss",
                          "discovery_source": name})
            result.articles.append(apply_source_quality(article, underlying or name))
        result.statuses.append({"source": name, "url": url, "success": True, "articles": len(result.articles),
                                "attempts": attempts, "retries": attempts - 1})
    except Exception as exc:
        result.statuses.append({"source": name, "url": url, "success": False, "articles": 0,
                                "attempts": getattr(exc, "attempts", 1),
                                "retries": max(0, getattr(exc, "attempts", 1) - 1),
                                "error": f"{type(exc).__name__}: {exc}"[:300]})
    return result
