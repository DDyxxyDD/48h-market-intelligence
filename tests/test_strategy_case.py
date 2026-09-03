from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from src.briefing.llm_html import generate_llm_briefing
from src.strategy_case import (CandidateDiscovery, StrategyCandidate, StrategyCase,
    StrategyCaseDraft, determine_strategy_region, run_strategy_case, select_candidate)


def candidate(region="china", company="Example", title="Integration", score=8, evidence=True):
    return StrategyCandidate(company=company, country_region="China" if region == "china" else "USA",
        region=region, case_title=title, decision_period="2020", strategic_decision="Integrate supply",
        why_interesting="Control versus fixed cost", reliable_evidence_available=evidence,
        results_evaluable=evidence, preliminary_source_ids=["source_1", "source_2"], rank_score=score)


def draft(region="china", company="Example", title="Integration"):
    return StrategyCaseDraft(region=region, company=company, case_title=title,
        one_line_thesis="Control justified investment.", decision_period="2020", situation="Supply changed.",
        strategic_problem="Build or buy?", options=[
            {"option": "Build", "pros": ["Control"], "cons": ["Cost"]},
            {"option": "Partner", "pros": ["Flexible"], "cons": ["Dependence"]}],
        decision="Build", why_this_choice="Management stated that control mattered; analytically, it reduced dependency.",
        execution=["Built capacity"], result="Revenue reached $2 billion.", what_worked=["Control"],
        what_failed=["High cost"], what_i_would_do="Stage the investment.",
        transferable_lessons=["Integrate when control value exceeds fixed-cost risk."], key_numbers=["$2 billion"],
        evidence_quality="high", source_ids=["source_1", "source_2"])


def test_deterministic_region_alternation_and_override():
    anchor = "2026-01-01T00:00:00+00:00"
    assert determine_strategy_region(datetime(2026, 1, 1, tzinfo=timezone.utc), anchor) == "china"
    assert determine_strategy_region(datetime(2026, 1, 3, tzinfo=timezone.utc), anchor) == "non_china"
    assert determine_strategy_region(datetime(2026, 1, 5, tzinfo=timezone.utc), anchor) == "china"
    assert determine_strategy_region(override="non_china") == "non_china"


def test_selection_rejects_wrong_region_duplicates_and_weak_evidence():
    chosen, rejected, _ = select_candidate([
        candidate("non_china", "Wrong", score=10), candidate(company="Used", title="Old", score=9),
        candidate(company="Weak", score=10, evidence=False), candidate(company="Winner", score=7)],
        "china", {"used|old"})
    assert chosen.company == "Winner"
    assert {x["rejection_reason"] for x in rejected} >= {
        "wrong_region", "previously_used_exact_case", "insufficient_evidence_or_results"}


def test_strategy_case_structured_validation_and_exact_sources():
    item = draft().model_dump()
    case = StrategyCase(**item, sources=[
        {"source_id": "source_1", "title": "Annual report", "url": "https://company.test/report"},
        {"source_id": "source_2", "title": "Regulator", "url": "https://regulator.test/filing"}])
    assert [x.url for x in case.sources] == ["https://company.test/report", "https://regulator.test/filing"]
    item["source_ids"] = ["source_2", "source_1"]
    with pytest.raises(ValidationError, match="exactly match"):
        StrategyCase(**item, sources=[x.model_dump() for x in case.sources])


class Responses:
    def __init__(self, fail_research=False): self.calls = 0; self.fail_research = fail_research
    def parse(self, **kwargs):
        self.calls += 1
        if kwargs["text_format"] is CandidateDiscovery:
            parsed = CandidateDiscovery(candidates=[candidate()])
        else:
            if self.fail_research: raise RuntimeError("web unavailable")
            parsed = draft()
        output = [{"content": [{"annotations": [
            {"type": "url_citation", "url": "https://company.test/report", "title": "Annual report"},
            {"type": "url_citation", "url": "https://regulator.test/filing", "title": "Regulator"}]}]}]
        return SimpleNamespace(output_parsed=parsed, output=output)


def test_bounded_research_writes_bundle_and_uses_web_search(tmp_path):
    responses = Responses()
    result = run_strategy_case({"llm": {"model": "test", "max_retries": 0}}, tmp_path / "case.json",
                               "china", SimpleNamespace(responses=responses))
    assert result["status"] == "available" and responses.calls == 2
    assert result["source_list"][0]["url"] == "https://company.test/report"
    assert (tmp_path / "case.json").exists()


def test_insufficient_research_failure_is_retained_and_html_still_renders(tmp_path):
    result = run_strategy_case({"llm": {"max_retries": 0}}, tmp_path / "case.json", "china",
                               SimpleNamespace(responses=Responses(fail_research=True)))
    assert result["status"] == "unavailable" and "web unavailable" in result["diagnostics"][0]
    page = generate_llm_briefing({"sections": {}, "executive_snapshot": []},
        {key: {"name": name} for key, name in (("ai", "AI"), ("macro_rates_fx", "Macro"),
         ("us_healthcare_equities", "Healthcare"))}, tmp_path / "briefing.html", result)
    text = page.read_text()
    assert "Strategy Case unavailable" in text and "I. AI" in text


def test_strategy_html_contains_full_long_form_case(tmp_path):
    case = StrategyCase(**draft().model_dump(), sources=[
        {"source_id": "source_1", "title": "Annual report", "url": "https://company.test/report"},
        {"source_id": "source_2", "title": "Regulator", "url": "https://regulator.test/filing"}])
    payload = {"status": "available", "final_case": case.model_dump()}
    page = generate_llm_briefing({"sections": {}}, {key: {"name": key} for key in
        ("ai", "macro_rates_fx", "us_healthcare_equities")}, tmp_path / "briefing.html", payload)
    text = page.read_text()
    for heading in ("IV. Corporate Strategy Case", "Strategic Problem", "Why This Choice",
                    "What I Would Do", "Transferable Lessons", "Sources"):
        assert heading in text
    assert 'href="https://company.test/report"' in text
