"""Transparent keyword classification into briefing sections."""

from src.models import Article

KEYWORDS = {
    "us_healthcare_equities": ["fda", "drug", "biotech", "pharma", "clinical trial", "medicare", "medicaid", "healthcare", "therapeutic", "patient", "vaccine"],
    "macro_rates_fx": ["federal reserve", "ecb", "central bank", "bank of england", "bank of japan", "pboc", "inflation", "employment", "gdp", "interest rate", "bond", "treasury", "forex", "currency", "dollar", " euro", "yen", "fiscal"],
    "ai": ["artificial intelligence", " ai ", "openai", "anthropic", "deepmind", "nvidia", " amd", "xai", "model", "semiconductor", "chip", "data center", "hyperscaler", "machine learning"],
}


def classify_articles(articles: list[Article]) -> list[Article]:
    """Assign the section with the most explicit keyword evidence."""
    for article in articles:
        text = f" {article.title} {article.summary} ".casefold()
        evidence = {section: [word for word in words if word in text] for section, words in KEYWORDS.items()}
        counts = {section: len(matches) for section, matches in evidence.items()}
        winner = max(counts, key=counts.get)
        article.section = winner if counts[winner] else "unclassified"
        article.metadata["classification_matches"] = evidence.get(article.section, [])
    return articles

