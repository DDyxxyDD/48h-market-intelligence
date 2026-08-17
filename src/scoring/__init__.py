"""Reproducible section-aware 0-10 relevance scoring."""

from datetime import datetime, timezone
from typing import Any

from src.models import Article


MATERIALITY = {
    "ai": {"major": ["launch", "release", "acquisition", "merger", "billion", "funding", "partnership", "regulation", "capex"], "minor": ["opinion", "review", "rumor"]},
    "macro_rates_fx": {"major": ["rate decision", "raises rates", "cuts rates", "inflation", "payroll", "employment", "gdp", "intervention", "policy decision"], "minor": ["opinion", "preview"]},
    "us_healthcare_equities": {"major": ["fda approves", "fda approval", "rejection", "phase 3", "pivotal", "acquisition", "guidance", "reimbursement", "safety warning"], "minor": ["form 8-k", "form 10-q", "routine filing", "opinion"]},
}


def score_articles(articles: list[Article], sections: dict[str, Any], now: datetime | None = None) -> list[Article]:
    """Score interest fit, materiality, source, recency and novelty (total 10)."""
    now = now or datetime.now(timezone.utc)
    for article in articles:
        section = sections.get(article.section, {})
        text = f"{article.title} {article.summary}".casefold()
        topic_words = {word for topic in section.get("topics", []) for word in topic.casefold().split() if len(word) > 3}
        config_matches = sorted(word for word in topic_words if word in text)
        classification_matches = article.metadata.get("classification_matches", [])
        fit = min(3.0, 0.7 * len(classification_matches) + 0.25 * len(config_matches))
        rules = MATERIALITY.get(article.section, {"major": [], "minor": []})
        major = [term for term in rules["major"] if term in text]
        minor = [term for term in rules["minor"] if term in text]
        healthcare_major = article.metadata.get("healthcare_materiality_matches", [])
        healthcare_noise = article.metadata.get("healthcare_noise_matches", [])
        materiality = max(0.0, min(3.0, 0.7 + 1.0 * len(major) + 0.45 * len(healthcare_major)
                                    - 0.8 * len(minor) - 1.0 * len(healthcare_noise)))
        source_quality = min(2.0, float(article.metadata.get("source_quality", 1.0)) * 2 / 3)
        age = max(0.0, (now - article.published_at).total_seconds() / 3600)
        recency = max(0.0, 1.5 * (1 - age / 60))
        novelty = 0.5
        breakdown = {"interest_fit": round(fit, 2), "materiality": round(materiality, 2),
                     "source_quality": round(source_quality, 2), "recency": round(recency, 2),
                     "novelty": novelty}
        # Relevance gate: source prestige cannot compensate for no topical fit.
        article.relevance_score = round(min(10.0, sum(breakdown.values())) if fit else 0.0, 1)
        article.metadata.update({"topic_matches": config_matches, "materiality_matches": major,
                                 "negative_materiality_matches": minor, "score_breakdown": breakdown})
    return articles
