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
python main.py --live --llm # Phase 2 candidates -> grounded LLM briefing
python main.py --live --llm --send-email # generate and explicitly email that briefing
python main.py --email-existing-briefing # send the existing briefing without rerunning pipelines
python main.py --email-existing-briefing --email-to "a@example.com,b@example.com" # one-run override
pytest
```

Live mode also writes `data/output/candidates.json` and prints candidate/selection counts. It continues when an individual source fails.

## Sections

1. AI (global)
2. Macro / Rates / FX (global)
3. U.S. Healthcare Equities
4. Corporate Strategy Case (a placeholder in Phase 2-only output; Phase 4 research populates the LLM briefing)

Configuration in `config/preferences.yaml` controls the UTC lookback (48 hours), topics, score threshold, scope and quotas.

Phase 3 is explicitly opt-in. Set `OPENAI_API_KEY`; optionally set `OPENAI_MODEL` (the configured default is `gpt-5.4-mini`). It uses the official OpenAI Responses API with strict structured outputs and analyzes only LLM-selected events using evidence already collected by Phase 2. Phase 4 independently uses the Responses API built-in `web_search` tool for a bounded Corporate Strategy Case workflow; web search is never used by the Phase 2/3 news pipeline. `python main.py --live --llm` writes `llm_editorial.json`, `llm_analysis.json`, `strategy_case.json`, and the integrated `llm_briefing.html`.

For a lower-cost manual strategy-only run, use `python main.py --strategy-case --strategy-region china` (or `non_china`). Without an override, Python alternates regions deterministically in 48-hour cycles from `corporate_strategy.cycle_anchor`; cycle zero is China. An optional `data/strategy_case_history.json` may contain a JSON list (or `{\"cases\": [...]}`) of objects with `company` and `case_title`; exact prior cases are excluded. The history file is read-only in this phase.

## Email delivery

Email is never sent by ordinary commands. Phase 5 uses standard-library SMTP with STARTTLS and
reads `SMTP_HOST`, `SMTP_PORT` (default `587`), `SMTP_USERNAME`, `SMTP_PASSWORD`, `EMAIL_FROM`,
and comma-separated `EMAIL_TO` from the environment. `--email-to` supplies a validated,
comma-separated recipient override for one run without changing `EMAIL_TO`; whitespace is trimmed
and exact duplicates are removed. A blank override falls back to `EMAIL_TO`, and delivery fails if
neither supplies a recipient. `EMAIL_FROM_NAME` is optional.
For servers with different TLS requirements, `SMTP_USE_STARTTLS` and `SMTP_USE_SSL` can override
the defaults. Every attempted delivery writes sanitized status to `data/output/email_delivery.json`;
an SMTP failure never changes or removes the generated briefing and analysis files.

The manual GitHub Actions workflow is a manual-only recipient control panel. Choose
`generate_and_send` for the existing news → LLM → strategy → HTML → email pipeline, or
`send_existing_briefing` to send `data/output/llm_briefing.html` without collection or OpenAI calls.
Its recipient field takes precedence over the saved `EMAIL_TO`. The saved default may be an Actions
variable (`vars.EMAIL_TO`) or, for backward compatibility, the existing `EMAIL_TO` secret.

## Public data sources

Live mode uses the free public GDELT DOC 2.0 discovery endpoint for broad AI, macro and healthcare coverage, with modest retries for transient HTTP failures. Google News RSS remains the fallback discovery layer. It separately polls official feeds from the Federal Reserve, European Central Bank and Bank of England. FDA coverage uses the functioning official openFDA Drug Enforcement API for recalls and also attempts the public FDA press-announcement listing; either FDA path can fail independently.

The collectors use headlines, canonical links, timestamps and source-provided descriptions. They do not scrape article bodies, bypass paywalls, authentication, CAPTCHAs or robots controls. Every request has a User-Agent, bounded timeout, one modest retry and endpoint-level error isolation.

## Scoring and selection

Each candidate receives a reproducible 0–10 score. Its components appear in `metadata.score_breakdown` and diagnostics:

* **Interest fit (0–3):** classification and configured-topic evidence.
* **Materiality (0–3):** section-specific major-event phrases and noise penalties.
* **Source quality (0–2):** configuration-driven Tier A official/original, Tier B major news, Tier C specialist/trade, Tier D unknown, and blocked-source rules.
* **Recency (0–1.5):** declines with age.
* **Novelty (0–0.5):** a retained unique event.

Source rules and the configurable per-publisher selection cap live in `config/source_quality.json`; Google News is treated only as discovery and its RSS `<source>` publisher is preserved and tiered. Zero interest fit forces a zero final score, so prestige cannot make irrelevant news rank highly. Canonical URLs, normalized titles, event tokens/entities/actions/numbers, and publication-time proximity collapse duplicate events while preferring the stronger source. Representatives retain alternate publishers and URLs. Selection applies the threshold and section quota while normally limiting one publisher to two selected stories per section.

## Candidate diagnostics

`data/output/candidates.json` records endpoint successes/failures, attempt/retry counts, and **every** candidate's collector, underlying publisher, source tier/score, classification evidence, UTC time, final score/breakdown, cluster/alternate-source data, selection reason and rejection reason. Review the `sources` array if counts are low. Typical causes include endpoint rate limiting or URL changes, DNS/network restrictions, malformed feeds, missing timestamps, and no matching news inside the window. An endpoint failure is never reported as success.

## Folder structure

```text
config/preferences.yaml     Topics, quotas, lookback and threshold
data/output/                Generated briefings and diagnostics (ignored)
src/collectors/             Mock, RSS/Atom, official-feed and GDELT collectors
src/classification.py       Section keyword evidence
src/source_quality.py       Config-driven publisher tiers
src/quality_gates.py        Healthcare noise/materiality gate
src/deduplication/          URL and event-title duplicate handling
src/scoring/                Explainable section-aware rules
src/selection/              Threshold, ranking and quotas
src/briefing/               Escaped standalone HTML rendering
tests/                      Offline and mocked collector tests
main.py                     Offline/live entry point and diagnostics
```

## Security and limitations

No credentials or secrets are required. Fetched content is untrusted display data: HTML escapes it, XML parsing does not execute it, and the program never obeys embedded instructions. Never add paywall or access-control bypasses.

Public discovery can be noisy or incomplete. Timestamp-less items are skipped; feed descriptions can be absent; publisher names vary; keyword classification/scoring and deterministic event clustering can miss nuance or merge closely related events; and endpoint availability changes. The healthcare gate removes obvious lifestyle/promotional noise but does not prove U.S. public-equity exposure. Phase 2.1 still has **no LLM/OpenAI analysis, email delivery, or automatic/GitHub Actions scheduling**. Live HTML explicitly says “AI analysis not enabled yet” rather than fabricating analysis.
