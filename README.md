# 48-Hour Market Intelligence Briefing

This repository is the beginner-friendly foundation for an automated market intelligence briefing. The future system will collect recent public business and financial news every 48 hours, rank it, analyze it, build an HTML report, and deliver it by email.

## Current status

This first version is a **local demonstration only**. It uses sample articles bundled in the code, deterministic placeholder analysis, and writes an HTML file to disk. It does **not** fetch live news, call an LLM, send email, or run on a schedule.

The sample covers four sections:

1. AI (global)
2. Macro / Rates / FX (global)
3. U.S. Healthcare Equities
4. Corporate Strategy Case (designed to alternate between China and non-China cases)

## Quick start

Python 3.11 or newer is recommended.

```bash
python -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate
python -m pip install -r requirements.txt  # installs the test runner
python main.py
```

Open `data/output/sample_briefing.html` in a browser after the command finishes.

Run the tests with:

```bash
pytest
```

## Folder structure

```text
config/preferences.yaml     Briefing topics, counts, scope, and thresholds
data/output/                Generated local briefings (ignored by Git)
src/models.py               Shared Article data model
src/collectors/             Sample collection now; public feeds later
src/normalization/          Consistent article cleanup
src/deduplication/          Duplicate removal
src/scoring/                Relevance scoring
src/selection/              Ranking and story selection
src/analysis/               Placeholder story analysis
src/briefing/               HTML rendering
src/email/                  Safe delivery interface (local-only now)
tests/                      Lightweight unit tests
main.py                     Pipeline entry point
```

Each pipeline stage has a small, separate responsibility so live implementations can replace the mock pieces incrementally.

## Configuration

Edit `config/preferences.yaml` to change the 48-hour lookback, section topics, geographic scope, story counts, minimum relevance score, and corporate-case alternation. The file uses JSON syntax, which is valid YAML, so Python can read it without a runtime dependency.

## Mock versus production behavior

| Capability | Current behavior | Future production behavior |
| --- | --- | --- |
| Collection | In-code sample articles | Free/public RSS feeds and official releases |
| Scoring | Simple topic keyword matching | Tuned rules and/or model-assisted scoring |
| Analysis | Deterministic placeholder text | Source-grounded structured analysis |
| Briefing | Local HTML file | Polished email-compatible HTML |
| Email | Disabled; returns a local-only message | Authenticated SMTP or email provider |
| Scheduling | Manual `python main.py` | GitHub Actions every 48 hours |

No paid news API or paywall-bypassing scraper is included.

## Secrets and security

Copy `.env.example` to `.env` only when a future integration needs credentials. **Never commit `.env`, API keys, email passwords, or other secrets.** GitHub Actions should use encrypted repository secrets. The current sample does not read credentials or make external requests.

## Roadmap

- Add free public RSS feeds and official agency/company sources.
- Add robust URL/content deduplication and source attribution.
- Improve relevance scoring, section quotas, and strategy-case alternation state.
- Add source-grounded Deep Dive and Quick Read analysis.
- Add email-compatible templates and an explicitly enabled delivery adapter.
- Add a tested GitHub Actions workflow and observability.
