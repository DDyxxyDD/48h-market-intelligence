# 48-Hour Market Intelligence Briefing

A local, modular market-intelligence pipeline. Phase 2 adds optional real public-news collection while preserving the Phase 1 offline demonstration.

## Quick start

Python 3.11 or newer is recommended.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python main.py             # offline mock data -> data/output/sample_briefing.html
python main.py --live      # real public data -> data/output/live_briefing.html
pytest
```

Live mode also writes `data/output/candidates.json` and prints candidate/selection counts. It continues when an individual source fails.

## Sections

1. AI (global)
2. Macro / Rates / FX (global)
3. U.S. Healthcare Equities
4. Corporate Strategy Case (an intentional Phase 2 placeholder; it requires historical research)

Configuration in `config/preferences.yaml` controls the UTC lookback (48 hours), topics, score threshold, scope and quotas.

## Public data sources

Live mode uses the free public GDELT DOC 2.0 discovery endpoint for broad AI, macro and healthcare coverage. It separately polls curated official feeds from the Federal Reserve, European Central Bank, Bank of England and U.S. FDA. Official releases receive higher source-quality weight. Sources are declarative in `src/collectors/official_sources.py`, making additions straightforward.

The collectors use headlines, canonical links, timestamps and source-provided descriptions. They do not scrape article bodies, bypass paywalls, authentication, CAPTCHAs or robots controls. Every request has a User-Agent, bounded timeout, one modest retry and endpoint-level error isolation.

## Scoring and selection

Each candidate receives a reproducible 0–10 score. Its components appear in `metadata.score_breakdown` and diagnostics:

* **Interest fit (0–3):** classification and configured-topic evidence.
* **Materiality (0–3):** section-specific major-event phrases and noise penalties.
* **Source quality (0–2):** official regulators/central banks outrank generic discovery.
* **Recency (0–1.5):** declines with age.
* **Novelty (0–0.5):** a retained unique event.

Zero interest fit forces a zero final score, so prestige cannot make irrelevant news rank highly. Canonical URLs, normalized titles and strong title similarity collapse duplicates while preferring the stronger source. Selection then applies the configured threshold and section quota.

## Candidate diagnostics

`data/output/candidates.json` records endpoint successes/failures and **every** candidate's title, URL, source, UTC time, section, final score, breakdown, selection flag and rejection reason. Review the `sources` array if counts are low. Typical causes include endpoint rate limiting or URL changes, DNS/network restrictions, malformed feeds, missing timestamps, and no matching news inside the window. An endpoint failure is never reported as success.

## Folder structure

```text
config/preferences.yaml     Topics, quotas, lookback and threshold
data/output/                Generated briefings and diagnostics (ignored)
src/collectors/             Mock, RSS/Atom, official-feed and GDELT collectors
src/classification.py       Section keyword evidence
src/deduplication/          URL and event-title duplicate handling
src/scoring/                Explainable section-aware rules
src/selection/              Threshold, ranking and quotas
src/briefing/               Escaped standalone HTML rendering
tests/                      Offline and mocked collector tests
main.py                     Offline/live entry point and diagnostics
```

## Security and limitations

No credentials or secrets are required. Fetched content is untrusted display data: HTML escapes it, XML parsing does not execute it, and the program never obeys embedded instructions. Never add paywall or access-control bypasses.

Public discovery can be noisy or incomplete. Timestamp-less items are skipped; feed descriptions can be absent; keyword classification/scoring can miss nuance; title similarity cannot perfectly identify events; and endpoint availability changes. Phase 2 still has **no LLM/OpenAI analysis, email delivery, or automatic/GitHub Actions scheduling**. Live HTML explicitly says “AI analysis not enabled yet” rather than fabricating analysis.
