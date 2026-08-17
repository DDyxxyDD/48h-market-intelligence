"""Offline placeholder analysis for selected articles."""

from src.models import Article


def analyze_article(article: Article) -> dict[str, str]:
    """Create deterministic sample analysis without calling an LLM."""
    return {
        "what_happened": article.summary,
        "why_it_matters": f"This development is relevant to the {article.section.replace('_', ' ')} watchlist.",
        "things_to_watch": "Watch official updates, financial disclosures, and market reaction.",
    }

