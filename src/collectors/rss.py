"""Generic, defensive RSS/Atom collector."""

from __future__ import annotations

from html import unescape
import re
from urllib.parse import urljoin
from xml.etree import ElementTree

from src.collectors.base import CollectionResult, fetch_bytes, parse_timestamp
from src.models import Article

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
        root = ElementTree.fromstring(fetch_bytes(url))
        nodes = [node for node in root.iter() if node.tag.rsplit("}", 1)[-1] in {"item", "entry"}]
        for node in nodes:
            title, link = _text(node, ("title",)), _link(node)
            published = parse_timestamp(_text(node, ("pubDate", "published", "updated", "date")))
            if not title or not link or not published:
                continue
            description = unescape(_TAGS.sub(" ", _text(node, ("description", "summary", "content"))))
            result.articles.append(Article(title=unescape(title), url=urljoin(url, link), source=name,
                published_at=published, summary=" ".join(description.split())[:1200],
                metadata={"source_type": source_type, "source_quality": quality, "collector": "rss"}))
        result.statuses.append({"source": name, "url": url, "success": True, "articles": len(result.articles)})
    except Exception as exc:
        result.statuses.append({"source": name, "url": url, "success": False, "articles": 0,
                                "error": f"{type(exc).__name__}: {exc}"[:300]})
    return result

