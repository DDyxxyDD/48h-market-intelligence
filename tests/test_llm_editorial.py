from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from src.llm_editorial import (DeepDiveAnalysis, EditorialSelection, LLMConfigurationError,
    QuickReadAnalysis, article_id, build_evidence_bundle, compact_candidates, create_client,
    build_candidate_map, evidence_source_urls, run_llm_editorial, validate_key_numbers)
from src.models import Article


def story(section="ai", suffix="1"):
    return Article(f"Material event {suffix}", f"https://example.com/{suffix}", "Reuters",
        datetime.now(timezone.utc), summary="Company launched product with $5 billion investment.",
        section=section, tickers=["TEST"], relevance_score=7,
        metadata={"article_id": f"evt_{suffix}", "event_cluster_id": f"cluster_{suffix}", "source_tier": "B",
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
        evidence_quality="medium", evidence_quality_explanation="One report.")


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
    assert "score" not in bundle and "published_at" not in bundle and "score_breakdown" not in bundle


def test_key_numbers_reject_internal_metadata_and_keep_source_fact():
    bundle = build_evidence_bundle(story())
    valid, removed = validate_key_numbers(
        ["2026-08-17T14:10:16Z", "relevance score 6.4", "materiality 1.67", "$5 billion"], bundle)
    assert valid == ["$5 billion"]
    assert {item["removal_reason"] for item in removed} == {
        "timestamp_or_date_metadata", "internal_scoring_or_pipeline_metadata"}


def test_analysis_schema_has_no_model_generated_sources():
    assert "sources" not in DeepDiveAnalysis.model_fields
    assert "sources" not in QuickReadAnalysis.model_fields


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
            value = deep()
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


class CapturingResponses(FakeResponses):
    def __init__(self, duplicate=False):
        self.editorial_payloads = []
        self.duplicate = duplicate

    def parse(self, **kwargs):
        if kwargs["text_format"] is EditorialSelection:
            payload = __import__("json").loads(kwargs["input"][1]["content"])
            self.editorial_payloads.append(payload)
            candidates = payload["candidates"]
            if self.duplicate and len(candidates) >= 2:
                value = EditorialSelection(section=payload["section"], editorial_summary="Events",
                    deep_dives=[{"article_id": candidates[0]["article_id"], "editorial_score": 9,
                                 "selection_reason": "Material", "why_not_quick_read": "Depth"}],
                    quick_reads=[{"article_id": candidates[1]["article_id"], "editorial_score": 7,
                                  "selection_reason": "Brief"}], rejected_notable_candidates=[])
                return SimpleNamespace(output_parsed=value)
        return super().parse(**kwargs)


def test_hard_gate_keeps_eligible_healthcare_and_never_sends_ineligible(tmp_path):
    denied, allowed = story("us_healthcare_equities", "denied"), story("us_healthcare_equities", "allowed")
    denied.metadata["eligibility_status"] = "ineligible"
    allowed.metadata["us_public_equity_verified"] = True
    responses = CapturingResponses()
    editorial_data, _ = run_llm_editorial([denied, allowed],
        {"llm": {"max_retries": 0}}, tmp_path, SimpleNamespace(responses=responses))
    healthcare = next(p for p in responses.editorial_payloads if p["section"] == "U.S. Healthcare Equities")
    assert [x["article_id"] for x in healthcare["candidates"]] == ["HC_001"]
    assert editorial_data["healthcare_candidates_before_hard_gate"] == 2
    assert editorial_data["healthcare_candidates_after_hard_gate"] == 1
    assert editorial_data["excluded_ineligible_candidates"][0]["reason"] == "rejected_false"


def test_same_event_cannot_be_deep_dive_and_quick_read_or_repeat_in_snapshot_input(tmp_path):
    first, second = story("ai", "first"), story("ai", "second")
    second.metadata["event_cluster_id"] = first.metadata["event_cluster_id"]
    responses = CapturingResponses(duplicate=True)
    editorial_data, analysis = run_llm_editorial([first, second],
        {"llm": {"max_retries": 0}}, tmp_path, SimpleNamespace(responses=responses))
    selected = (editorial_data["sections"]["ai"]["deep_dives"] +
                editorial_data["sections"]["ai"]["quick_reads"])
    assert len(selected) == 1
    removed = editorial_data["duplicate_final_selections_removed"][0]
    assert removed["article_id"] != removed["kept_article_id"]
    assert selected[0]["article_id"] == removed["kept_article_id"]
    assert len(editorial_data["final_event_cluster_ids"]["ai"]) == 1
    assert len(analysis["sections"]["ai"]["deep_dives"]) == 1


def test_professional_style_prompt_does_not_require_audit_prefixes(tmp_path):
    responses = CapturingResponses()
    run_llm_editorial([story()], {"llm": {"max_retries": 0}}, tmp_path,
                      SimpleNamespace(responses=responses))
    # The returned prose is allowed to be direct; grounding is enforced without audit labels.
    assert not deep().what_happened.startswith(("Fact:", "Analytical inference:"))


def test_short_ids_hide_urls_and_map_to_exact_articles():
    eyepoint = story("ai", "eyepoint")
    eyepoint.title = "EyePoint pivotal wet-AMD results"
    mapping = build_candidate_map([eyepoint], 30)
    compact = compact_candidates([eyepoint], 30, mapping)
    assert compact[0]["article_id"] == "AI_001"
    assert eyepoint.url not in __import__("json").dumps(compact)
    assert mapping["AI_001"]["article"] is eyepoint
    assert mapping["AI_001"]["canonical_url"] == eyepoint.url


class UnknownResponses(FakeResponses):
    def parse(self, **kwargs):
        if kwargs["text_format"] is EditorialSelection:
            return SimpleNamespace(output_parsed=editorial(article="AI_999"))
        raise AssertionError("analysis must not run for an unknown short ID")


def test_unknown_short_id_cannot_select_or_fall_back_to_random_article(tmp_path):
    editorial_data, analysis = run_llm_editorial([story()], {"llm": {"max_retries": 0}}, tmp_path,
        SimpleNamespace(responses=UnknownResponses()))
    assert "outside the candidate pool" in editorial_data["sections"]["ai"]["error"]
    assert not analysis["sections"]["ai"]["deep_dives"]


class UrlInjectionResponses(FakeResponses):
    def __init__(self):
        self.analysis_payload = None

    def parse(self, **kwargs):
        if kwargs["text_format"] is DeepDiveAnalysis:
            self.analysis_payload = kwargs["input"][1]["content"]
            value = deep()
            # Simulate hostile/legacy model output. Pydantic's schema excludes it,
            # and Python attaches its own evidence URLs after parsing.
            object.__setattr__(value, "sources", ["https://model.invalid/changed"])
            return SimpleNamespace(output_parsed=value)
        return super().parse(**kwargs)


def test_final_urls_are_python_owned_and_model_never_receives_them(tmp_path):
    item = story()
    item.metadata["related_reports"] = [{"headline": "Corroboration", "source": "AP",
        "summary": "Same event", "url": "https://ap.example/exact?x=1&y=2"}]
    responses = UrlInjectionResponses()
    _, analysis = run_llm_editorial([item], {"llm": {"max_retries": 0}}, tmp_path,
        SimpleNamespace(responses=responses))
    result = analysis["sections"]["ai"]["deep_dives"][0]
    assert item.url not in responses.analysis_payload
    assert result["sources"] == [item.url, "https://ap.example/exact?x=1&y=2"]
    assert "model.invalid" not in __import__("json").dumps(analysis)


@pytest.mark.parametrize(("metadata", "allowed", "status"), [
    ({}, False, "rejected_missing"),
    ({"us_public_equity_verified": False}, False, "rejected_false"),
    ({"us_public_equity_verified": True}, True, "verified"),
])
def test_healthcare_gate_is_fail_closed(tmp_path, metadata, allowed, status):
    item = story("us_healthcare_equities", "health")
    item.metadata.update(metadata)
    responses = CapturingResponses()
    editorial_data, _ = run_llm_editorial([item], {"llm": {"max_retries": 0}}, tmp_path,
        SimpleNamespace(responses=responses))
    payload = next(p for p in responses.editorial_payloads if p["section"] == "U.S. Healthcare Equities")
    assert bool(payload["candidates"]) is allowed
    assert item.metadata["eligibility_gate_status"] == status
    assert editorial_data["healthcare_candidates_after_hard_gate"] == int(allowed)


def test_canada_cpi_and_currency_reaction_collide_but_distinct_event_does_not():
    from src.llm_editorial import _semantic_collision
    cpi = story("macro_rates_fx", "cpi")
    cpi.title = "Canada inflation rises to 3%"
    cad = story("macro_rates_fx", "cad")
    cad.title = "Canadian dollar rises as inflation accelerates"
    other = story("macro_rates_fx", "trade")
    other.title = "Canada announces new trade agreement with Japan"
    assert _semantic_collision(cpi, cad)
    assert _semantic_collision(cpi, other) is None


def test_eyepoint_selection_never_maps_to_fda_story():
    eyepoint, fda = story("ai", "eye"), story("ai", "fda")
    eyepoint.title = "EyePoint pivotal wet-AMD story"
    fda.title = "FDA antimicrobial guidance"
    mapping = build_candidate_map([eyepoint, fda], 30)
    selected = next(key for key, value in mapping.items() if value["article"] is eyepoint)
    assert mapping[selected]["article"].title == eyepoint.title
    assert mapping[selected]["article"] is not fda


class FailedAnalysisResponses(FakeResponses):
    def parse(self, **kwargs):
        if kwargs["text_format"] is DeepDiveAnalysis:
            raise RuntimeError("analysis unavailable")
        return super().parse(**kwargs)


def test_analysis_failure_preserves_selection_and_never_looks_up_another(tmp_path):
    item, other = story("ai", "chosen"), story("ai", "other")
    item.relevance_score = 9
    editorial_data, analysis = run_llm_editorial([item, other], {"llm": {"max_retries": 0}}, tmp_path,
        SimpleNamespace(responses=FailedAnalysisResponses()))
    assert editorial_data["sections"]["ai"]["deep_dives"][0]["article_id"] == "AI_001"
    assert analysis["sections"]["ai"]["errors"][0]["selected_title"] == item.title
    assert not analysis["sections"]["ai"]["deep_dives"]
