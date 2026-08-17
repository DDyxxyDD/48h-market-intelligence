"""Run the offline sample market-intelligence pipeline."""

import json
from pathlib import Path
from typing import Any

from src.briefing import generate_html_briefing
from src.collectors import collect_sample_articles
from src.deduplication import deduplicate_articles
from src.email import deliver_briefing_locally
from src.normalization import normalize_articles
from src.scoring import score_articles
from src.selection import select_articles


def load_preferences(path: Path = Path("config/preferences.yaml")) -> dict[str, Any]:
    """Load briefing preferences from YAML."""
    with path.open(encoding="utf-8") as config_file:
        return json.load(config_file)


def run_pipeline(output_path: Path = Path("data/output/sample_briefing.html")) -> Path:
    """Run every offline pipeline stage and write the sample briefing."""
    preferences = load_preferences()
    articles = collect_sample_articles()
    articles = normalize_articles(articles)
    articles = deduplicate_articles(articles)
    articles = score_articles(articles, preferences["sections"])
    selected = select_articles(
        articles,
        preferences["sections"],
        float(preferences["briefing"]["relevance_threshold"]),
    )
    return generate_html_briefing(selected, preferences["sections"], output_path)


if __name__ == "__main__":
    result = run_pipeline()
    print(deliver_briefing_locally(result))
