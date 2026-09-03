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
from src.email import DEFAULT_BRIEFING, deliver_briefing_locally, send_briefing
from src.normalization import normalize_articles
from src.quality_gates import apply_healthcare_gate
from src.scoring import score_articles
from src.selection import select_articles
from src.llm_editorial import LLMConfigurationError, create_client, run_llm_editorial
from src.briefing.llm_html import generate_llm_briefing
from src.strategy_case import run_strategy_case

_LAST_LIVE_CANDIDATES = []


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
            "collector": article.metadata.get("collector"),
            "underlying_publisher": article.metadata.get("underlying_publisher", article.source),
            "source_tier": article.metadata.get("source_tier", "D"),
            "source_quality_score": article.metadata.get("source_quality", 1.0),
            "classification_matches": article.metadata.get("classification_matches", []),
            "score_breakdown": article.metadata.get("score_breakdown", {}),
            "event_cluster_id": article.metadata.get("event_cluster_id"),
            "duplicate_of": article.metadata.get("duplicate_of"),
            "alternate_sources": article.metadata.get("alternate_sources", []),
            "alternate_urls": article.metadata.get("alternate_urls", []),
            "selection_reason": article.metadata.get("selection_reason"), "selected": selected,
            **({"rejection_reason": reason or article.metadata.get("rejection_reason") or "below_threshold_or_quota"} if not selected else {})}


def run_live_pipeline(output_path: Path = Path("data/output/live_briefing.html"),
                      diagnostics_path: Path = Path("data/output/candidates.json")) -> tuple[Path, dict[str, Any]]:
    """Collect, filter, classify, rank and render public news without LLM analysis."""
    preferences = load_preferences()
    recent, stale, statuses = collect_live_articles(int(preferences["briefing"]["lookback_hours"]))
    classify_articles(recent)
    relevant = [article for article in recent if article.section in preferences["sections"] and
                article.section != "corporate_strategy_case" and article.metadata.get("source_tier") != "blocked"]
    unclassified = [article for article in recent if article not in relevant]
    for article in unclassified:
        article.metadata["rejection_reason"] = "blocked_source" if article.metadata.get("source_tier") == "blocked" else "unclassified"
    gated, healthcare_noise = apply_healthcare_gate(relevant)
    unique, duplicates = deduplicate_with_rejections(gated)
    global _LAST_LIVE_CANDIDATES
    _LAST_LIVE_CANDIDATES = unique
    score_articles(unique, preferences["sections"])
    selected = select_articles(unique, preferences["sections"], float(preferences["briefing"]["relevance_threshold"]))
    # Phase 2 explicitly retains the historical-context placeholder rather than live automation.
    selected["corporate_strategy_case"] = []
    selected_urls = {article.url for items in selected.values() for article in items}
    threshold = float(preferences["briefing"]["relevance_threshold"])
    for article in unique:
        if article.url in selected_urls:
            continue
        if article.relevance_score < threshold:
            article.metadata["rejection_reason"] = "below_relevance_threshold"
            article.metadata.setdefault("selection_reason", "score_below_configured_threshold")
        else:
            article.metadata["rejection_reason"] = "section_quota_or_source_diversity"
            article.metadata.setdefault("selection_reason", "ranked_below_section_quota")
    candidates = [_diagnostic(article, selected_urls) for article in unique]
    candidates += [_diagnostic(article, selected_urls) for article in duplicates + healthcare_noise + stale + unclassified]
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


def run_llm_pipeline(output_path: Path = Path("data/output/llm_briefing.html"),
                     strategy_region: str | None = None) -> Path:
    """Run frozen Phase 2 collection, then the opt-in Phase 3 editorial layer."""
    # Validate configuration before making the user wait for network collection.
    client = create_client()
    # This intentionally invokes the same public-news pipeline used by --live.
    run_live_pipeline()
    preferences = load_preferences()
    _, analyses = run_llm_editorial(_LAST_LIVE_CANDIDATES, preferences, Path("data/output"), client)
    strategy = run_strategy_case(preferences, region_override=strategy_region, client=client)
    return generate_llm_briefing(analyses, preferences["sections"], output_path, strategy)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true", help="collect real public news from the last configured window")
    parser.add_argument("--llm", action="store_true", help="use OpenAI as the final editor (requires --live)")
    parser.add_argument("--strategy-case", action="store_true", help="run only web-grounded strategy research")
    parser.add_argument("--strategy-region", choices=("china", "non_china"), help="override deterministic strategy region")
    parser.add_argument("--send-email", action="store_true", help="send the newly generated LLM briefing")
    parser.add_argument("--email-existing-briefing", action="store_true", help="send the existing LLM briefing without running pipelines")
    parser.add_argument("--email-to", help="comma-separated recipients for this run (overrides EMAIL_TO)")
    args = parser.parse_args(argv)
    if args.email_existing_briefing:
        if args.live or args.llm or args.strategy_case or args.strategy_region or args.send_email:
            parser.error("--email-existing-briefing cannot be combined with pipeline options")
        sent = (send_briefing(DEFAULT_BRIEFING) if args.email_to is None else
                send_briefing(DEFAULT_BRIEFING, recipient_override=args.email_to))
        return 0 if sent else 1
    if args.send_email and (not (args.live and args.llm) or args.strategy_case):
        parser.error("--send-email requires --live --llm")
    if args.llm and not args.live and not args.strategy_case:
        parser.error("--llm must be used with --live")
    if args.strategy_region and not (args.strategy_case or args.llm):
        parser.error("--strategy-region requires --strategy-case or --llm")
    try:
        if args.strategy_case:
            client = create_client()
            preferences = load_preferences()
            strategy = run_strategy_case(preferences, region_override=args.strategy_region, client=client)
            result = generate_llm_briefing({"sections": {}, "executive_snapshot": []},
                                           preferences["sections"], Path("data/output/strategy_briefing.html"), strategy)
        else:
            result = run_llm_pipeline(strategy_region=args.strategy_region) if args.llm else (run_live_pipeline()[0] if args.live else run_pipeline())
    except LLMConfigurationError as exc:
        parser.exit(2, f"LLM mode could not start: {exc}\n")
    print(deliver_briefing_locally(result))
    if args.send_email:
        sent = (send_briefing(result) if args.email_to is None else
                send_briefing(result, recipient_override=args.email_to))
        return 0 if sent else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
