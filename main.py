"""Run either the offline sample or fault-tolerant live public-news pipeline."""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from src.briefing import generate_html_briefing
from src.collectors import collect_sample_articles
from src.classification import classify_articles
from src.collectors.live import collect_live_articles
from src.deduplication import deduplicate_articles, deduplicate_with_rejections
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


def _diagnostic(article, selected_urls: set[str], reason: str | None = None) -> dict[str, Any]:
    selected = article.url in selected_urls
    return {"title": article.title, "url": article.url, "source": article.source,
            "published_at": article.published_at.isoformat(), "section": article.section,
            "relevance_score": article.relevance_score,
            "score_breakdown": article.metadata.get("score_breakdown", {}), "selected": selected,
            **({"rejection_reason": reason or article.metadata.get("rejection_reason") or "below_threshold_or_quota"} if not selected else {})}


def run_live_pipeline(output_path: Path = Path("data/output/live_briefing.html"),
                      diagnostics_path: Path = Path("data/output/candidates.json")) -> tuple[Path, dict[str, Any]]:
    """Collect, filter, classify, rank and render public news without LLM analysis."""
    preferences = load_preferences()
    recent, stale, statuses = collect_live_articles(int(preferences["briefing"]["lookback_hours"]))
    classify_articles(recent)
    relevant = [article for article in recent if article.section in preferences["sections"] and article.section != "corporate_strategy_case"]
    unclassified = [article for article in recent if article not in relevant]
    for article in unclassified:
        article.metadata["rejection_reason"] = "unclassified"
    unique, duplicates = deduplicate_with_rejections(relevant)
    score_articles(unique, preferences["sections"])
    selected = select_articles(unique, preferences["sections"], float(preferences["briefing"]["relevance_threshold"]))
    # Phase 2 explicitly retains the historical-context placeholder rather than live automation.
    selected["corporate_strategy_case"] = []
    selected_urls = {article.url for items in selected.values() for article in items}
    candidates = [_diagnostic(article, selected_urls) for article in unique]
    candidates += [_diagnostic(article, selected_urls) for article in duplicates + stale + unclassified]
    payload = {"generated_at": datetime.now(timezone.utc).isoformat(),
               "lookback_hours": preferences["briefing"]["lookback_hours"], "sources": statuses,
               "candidates": candidates}
    diagnostics_path.parent.mkdir(parents=True, exist_ok=True)
    diagnostics_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    result = generate_html_briefing(selected, preferences["sections"], output_path, live=True)
    for key, settings in preferences["sections"].items():
        if key == "corporate_strategy_case":
            continue
        count = sum(1 for item in candidates if item["section"] == key)
        print(f'{settings["name"]}: {count} candidates, {len(selected.get(key, []))} selected')
    return result, payload


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true", help="collect real public news from the last configured window")
    args = parser.parse_args()
    result = run_live_pipeline()[0] if args.live else run_pipeline()
    print(deliver_briefing_locally(result))
