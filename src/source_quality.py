"""Config-driven source tiers shared by every collector and scorer."""

from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlsplit

from src.models import Article

DEFAULT_CONFIG = Path(__file__).resolve().parents[1] / "config" / "source_quality.json"


def load_source_rules(path: Path = DEFAULT_CONFIG) -> dict:
    with path.open(encoding="utf-8") as source_file:
        return json.load(source_file)


def classify_source(publisher: str, url: str = "", rules: dict | None = None) -> tuple[str, float]:
    """Return a transparent tier and numeric score; unknown publishers remain usable."""
    rules = rules or load_source_rules()
    publisher_key = publisher.casefold().strip()
    domain = (urlsplit(url).hostname or "").casefold().removeprefix("www.")
    if any(domain == item or domain.endswith(f".{item}") for item in rules.get("official_domains", [])):
        tier = "A"
    else:
        tier = "D"
        for candidate in ("blocked", "A", "B", "C"):
            if any(name.casefold() == publisher_key or name.casefold() in publisher_key
                   for name in rules.get("publishers", {}).get(candidate, [])):
                tier = candidate
                break
    return tier, float(rules["tiers"][tier]["score"])


def apply_source_quality(article: Article, underlying_publisher: str | None = None) -> Article:
    publisher = (underlying_publisher or article.source).strip()
    tier, score = classify_source(publisher, article.url)
    article.source = publisher
    article.metadata.update({"underlying_publisher": publisher, "source_tier": tier,
                             "source_quality": score})
    return article
