"""Offline sample collector used to demonstrate the pipeline."""

from datetime import datetime, timedelta, timezone

from src.models import Article


def collect_sample_articles() -> list[Article]:
    """Return representative sample articles without network access."""
    now = datetime.now(timezone.utc)
    samples = [
        ("New enterprise AI model targets lower compute costs", "ai", "A model launch promises more efficient AI infrastructure and enterprise adoption.", ["USA"]),
        ("Chipmaker expands capacity for AI accelerators", "ai", "Semiconductor capacity and hyperscaler AI capex remain in focus.", ["USA", "Taiwan"]),
        ("Central bank holds interest rates as inflation cools", "macro_rates_fx", "Bond markets and major FX pairs moved after the central bank decision.", ["United Kingdom"]),
        ("Employment report reshapes rate expectations", "macro_rates_fx", "A major macroeconomic release changed the expected interest-rate path.", ["USA"]),
        ("FDA decision clears new oncology treatment", "us_healthcare_equities", "The FDA decision affects a publicly listed drug developer.", ["USA"]),
        ("Healthcare company raises guidance after trial results", "us_healthcare_equities", "Clinical trial results and updated earnings guidance moved shares.", ["USA"]),
        ("Chinese manufacturer redesigns its global expansion", "corporate_strategy_case", "A China-related company weighs market entry and business model options.", ["China"]),
    ]
    return [
        Article(
            title=title,
            url=f"https://example.com/sample/{index}",
            source="Sample News (mock)",
            published_at=now - timedelta(hours=index * 3),
            summary=summary,
            section=section,
            countries=countries,
            metadata={"mock": True},
        )
        for index, (title, section, summary, countries) in enumerate(samples, start=1)
    ]

