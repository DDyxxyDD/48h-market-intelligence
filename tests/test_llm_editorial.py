from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from src.llm_editorial import (DeepDiveAnalysis, EditorialSelection, LLMConfigurationError,
    QuickReadAnalysis, article_id, build_evidence_bundle, compact_candidates, create_client,
    run_llm_editorial, validate_source_urls)
from src.models import Article


def story(section="ai", suffix="1"):
    return Article(f"Material event {suffix}", f"https://example.com/{suffix}", "Reuters",
        datetime.now(timezone.utc), summary="Company launched product with $5 billion investment.",
        section=section, tickers=["TEST"], relevance_score=7,
        metadata={"event_cluster_id": f"evt_{suffix}", "source_tier": "B",
                  "score_breakdown": {"materiality": 2}})


def editorial(section="AI", article="evt_1"):
    return EditorialSelection(section=section, editorial_summary="One material event.",
        deep_dives=[{"article_id": article, "editorial_score": 8,
                     "selection_reason": "Material", "why_not_quick_read": "Strategic depth"}],
        quick_reads=[], rejected_notable_candidates=[])


def deep(url="https://example.com/1"):
    return DeepDiveAnalysis(headline="Launch", relevance_score=8, what_happened="A launch occurred.",
        key_numbers=["$5 billion"], why_it_matters="Material scale.",
        strategic_read="Inference: investment may affect positioning.",
        market_implication="Inference: competitors may respond.", things_to_watch=["Adoption", "Spending"],
        evidence_quality="medium", evidence_quality_explanation="One report.", sources=[url])


def test_missing_api_key_is_beginner_friendly(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(LLMConfigurationError, match="Set the OPENAI_API_KEY"):
        create_client()


def test_editorial_parsing_constraints_and_duplicate_prevention():
    parsed = EditorialSelection.model_validate(editorial().model_dump())
    assert parsed.deep_dives[0].editorial_score == 8
    duplicate = editorial().model_dump()
    duplicate["quick_reads"] = [{"article_id": "evt_1", "editorial_score": 7, "selection_reason": "Short"}]
    with pytest.raises(ValidationError, match="only once"):
        EditorialSelection.model_validate(duplicate)
    too_many = editorial().model_dump()
    too_many["deep_dives"] *= 3
    with pytest.raises(ValidationError):
        EditorialSelection.model_validate(too_many)


def test_candidate_compaction_limit_fields_and_hard_rejection():
    items = [story(suffix=str(i)) for i in range(4)]
    items[0].metadata["rejection_reason"] = "healthcare_noise_gate"
    compact = compact_candidates(items, 2)
    assert len(compact) == 2 and "url" not in compact[0]
    assert {x["article_id"] for x in compact}.isdisjoint({"evt_0"})


def test_evidence_bundle_preserves_related_reports():
    item = story()
    item.metadata["related_reports"] = [{"headline": "Also reported", "source": "AP",
        "published_at": item.published_at.isoformat(), "summary": "Same event", "url": "https://ap.example/event"}]
    bundle = build_evidence_bundle(item)
    assert bundle["tickers"] == ["TEST"] and bundle["related_reports"][0]["source"] == "AP"


def test_grounded_url_validation_and_analysis_structures():
    item = story()
    validate_source_urls(deep(), build_evidence_bundle(item))
    with pytest.raises(ValueError, match="outside evidence"):
        validate_source_urls(deep("https://invented.example"), build_evidence_bundle(item))
    quick = QuickReadAnalysis(headline="Launch", what_happened="Launched.",
        why_it_matters="Material.", one_thing_to_watch="Adoption.", sources=[item.url])
    validate_source_urls(quick, build_evidence_bundle(item))


class FakeResponses:
    def parse(self, **kwargs):
        section = kwargs["input"][1]["content"]
        schema = kwargs["text_format"]
        if schema is EditorialSelection:
            if "Macro / Rates / FX" in section:
                raise RuntimeError("section unavailable")
            candidates = __import__("json").loads(section)["candidates"]
            value = editorial(article=candidates[0]["article_id"]) if candidates else EditorialSelection(
                section="empty", editorial_summary="None", deep_dives=[], quick_reads=[], rejected_notable_candidates=[])
        elif schema is DeepDiveAnalysis:
            evidence = __import__("json").loads(section)
            value = deep(evidence["canonical_url"])
        else:
            value = schema(bullets=["A", "B", "C"])
        return SimpleNamespace(output_parsed=value)


def test_one_section_failure_does_not_abort_pipeline(tmp_path):
    client = SimpleNamespace(responses=FakeResponses())
    articles = [story("ai", "1"), story("macro_rates_fx", "2"), story("us_healthcare_equities", "3")]
    editorial_data, analysis = run_llm_editorial(articles,
        {"llm": {"max_candidates_per_section": 30, "max_retries": 0}}, tmp_path, client)
    assert "error" in editorial_data["sections"]["macro_rates_fx"]
    assert analysis["sections"]["ai"]["deep_dives"]
    assert (tmp_path / "llm_editorial.json").exists() and (tmp_path / "llm_analysis.json").exists()
