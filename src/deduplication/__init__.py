"""Deterministic article/event deduplication."""

from difflib import SequenceMatcher
import hashlib
import re
from urllib.parse import urlsplit, urlunsplit

from src.models import Article


def _canonical_url(url: str) -> str:
    parts = urlsplit(url)
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path.rstrip("/"), "", ""))


def _title(title: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", title.casefold()))


def _quality(article: Article) -> float:
    return float(article.metadata.get("source_quality", 0))


STOPWORDS = {"a", "an", "and", "as", "at", "by", "for", "from", "in", "into", "is", "of", "on", "the", "to", "with", "after", "amid", "new", "says"}
ACTIONS = {"acquire", "acquires", "acquisition", "approve", "approves", "approval", "reject", "rejects",
           "launch", "launches", "release", "releases", "raise", "raises", "cut", "cuts", "hold", "holds",
           "recall", "warning", "partner", "partnership", "funding", "trial", "results", "guidance", "invest"}


def _event_features(article: Article) -> tuple[set[str], set[str], set[str], set[str]]:
    raw = re.findall(r"[A-Za-z0-9.$%]+", article.title)
    tokens = {token.casefold().strip(".$%") for token in raw if len(token.strip(".$%")) >= 3}
    tokens -= STOPWORDS
    entities = {token.casefold() for token in raw if token[:1].isupper() and len(token) >= 3} - STOPWORDS
    numbers = {token.casefold() for token in raw if any(char.isdigit() for char in token)}
    actions = tokens & ACTIONS
    return tokens, entities, numbers, actions


def _same_event(left: Article, right: Article) -> bool:
    if left.section != right.section or abs((left.published_at - right.published_at).total_seconds()) > 36 * 3600:
        return False
    lt, le, ln, la = _event_features(left)
    rt, re_, rn, ra = _event_features(right)
    union = lt | rt
    jaccard = len(lt & rt) / len(union) if union else 0
    entity_overlap = len(le & re_)
    action_overlap = bool(la & ra)
    number_overlap = bool(ln & rn)
    # High token overlap stands alone; lower overlap needs corroborating entities/actions/numbers.
    return (jaccard >= 0.52 or
            (jaccard >= 0.30 and entity_overlap >= 1 and (action_overlap or number_overlap)) or
            (jaccard >= 0.22 and entity_overlap >= 2 and action_overlap))


def _cluster_id(article: Article) -> str:
    tokens, _, _, actions = _event_features(article)
    signature = " ".join(sorted(tokens | actions))
    return "evt_" + hashlib.sha1(signature.encode()).hexdigest()[:12]


def deduplicate_articles(articles: list[Article]) -> list[Article]:
    """Keep the first article for each canonical URL or normalized title."""
    unique, _ = deduplicate_with_rejections(articles)
    return unique


def deduplicate_with_rejections(articles: list[Article]) -> tuple[list[Article], list[Article]]:
    """Collapse canonical URLs and highly similar titles, preferring original-quality sources."""
    unique: list[Article] = []
    rejected: list[Article] = []
    # Python's stable sort preserves collector order when quality is equal.
    for article in sorted(articles, key=_quality, reverse=True):
        url_key = _canonical_url(article.url)
        title_key = _title(article.title)
        duplicate = next((kept for kept in unique if _canonical_url(kept.url) == url_key or
                          _title(kept.title) == title_key or
                          (min(len(title_key), len(_title(kept.title))) >= 35 and
                           SequenceMatcher(None, title_key, _title(kept.title)).ratio() >= 0.88) or
                          _same_event(article, kept)), None)
        if duplicate:
            cluster_id = duplicate.metadata.setdefault("event_cluster_id", _cluster_id(duplicate))
            duplicate.metadata.setdefault("alternate_sources", []).append(article.source)
            duplicate.metadata.setdefault("alternate_urls", []).append(article.url)
            article.metadata["rejection_reason"] = "duplicate_event"
            article.metadata["duplicate_of"] = duplicate.url
            article.metadata["event_cluster_id"] = cluster_id
            article.metadata["alternate_sources"] = [duplicate.source]
            article.metadata["alternate_urls"] = [duplicate.url]
            rejected.append(article)
            continue
        article.metadata.setdefault("event_cluster_id", _cluster_id(article))
        article.metadata.setdefault("alternate_sources", [])
        article.metadata.setdefault("alternate_urls", [])
        unique.append(article)
    return unique, rejected
