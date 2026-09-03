"""Professional, escaped rendering for completed Phase 3 analyses."""

from datetime import datetime, timezone
from html import escape
from pathlib import Path
from typing import Any


def _sources(urls: list[str]) -> str:
    return "".join(f'<li><a href="{escape(url, quote=True)}">{escape(url)}</a></li>' for url in urls)


def _strategy_case(payload: dict[str, Any] | None) -> str:
    if not payload or payload.get("status") != "available":
        detail = "; ".join(payload.get("diagnostics", [])) if payload else "Research was not run."
        return (f'<section class="strategy"><h1>IV. Corporate Strategy Case</h1><div class="notice">'
                f'<strong>Strategy Case unavailable.</strong> No case was invented. '
                f'<span class="diagnostic">{escape(detail)}</span></div></section>')
    case = payload["final_case"]
    options = "".join(
        f'<div class="option"><h3>{escape(item["option"])}</h3><div class="option-grid">'
        f'<div><strong>Pros</strong><ul>{"".join(f"<li>{escape(x)}</li>" for x in item["pros"])}</ul></div>'
        f'<div><strong>Cons</strong><ul>{"".join(f"<li>{escape(x)}</li>" for x in item["cons"])}</ul></div></div></div>'
        for item in case["options"])
    def listing(name: str) -> str:
        values = case.get(name, [])
        return "".join(f"<li>{escape(str(value))}</li>" for value in values) or "<li>None established.</li>"
    source_html = "".join(f'<li><a href="{escape(x["url"], quote=True)}">'
                          f'{escape(x.get("title") or x["url"])}</a></li>' for x in case["sources"])
    return f'''<section class="strategy"><h1>IV. Corporate Strategy Case</h1><article class="case">
<div class="tag">Long-form strategy analysis</div><h2>{escape(case['company'])} / {escape(case['case_title'])}</h2>
<div class="case-meta"><span><strong>Region</strong>{escape(case['region'].replace('_', '-').title())}</span><span><strong>Decision Period</strong>{escape(case['decision_period'])}</span></div>
<p class="thesis"><strong>One-Line Thesis</strong><br>{escape(case['one_line_thesis'])}</p>
<h3>Situation</h3><p>{escape(case['situation'])}</p><h3>Strategic Problem</h3><p>{escape(case['strategic_problem'])}</p>
<h3>Options</h3>{options}<h3>Decision</h3><p>{escape(case['decision'])}</p>
<h3>Why This Choice</h3><p>{escape(case['why_this_choice'])}</p><h3>Execution</h3><ul>{listing('execution')}</ul>
<h3>Result</h3><p>{escape(case['result'])}</p><div class="option-grid"><div><h3>What Worked</h3><ul>{listing('what_worked')}</ul></div><div><h3>What Failed</h3><ul>{listing('what_failed')}</ul></div></div>
<h3>What I Would Do</h3><p>{escape(case['what_i_would_do'])}</p><h3>Transferable Lessons</h3><ul>{listing('transferable_lessons')}</ul>
<h3>Key Numbers</h3><ul>{listing('key_numbers')}</ul><h3>Evidence Quality</h3><p>{escape(case['evidence_quality'].title())}</p>
<h3>Sources</h3><ul>{source_html}</ul></article></section>'''


def generate_llm_briefing(data: dict[str, Any], sections: dict[str, Any], output_path: Path,
                          strategy_case: dict[str, Any] | None = None) -> Path:
    blocks = []
    numerals = {"ai": "I", "macro_rates_fx": "II", "us_healthcare_equities": "III"}
    for key, numeral in numerals.items():
        section = data.get("sections", {}).get(key, {})
        cards = []
        for item in section.get("deep_dives", []):
            watches = "".join(f"<li>{escape(x)}</li>" for x in item["things_to_watch"])
            numbers = "".join(f"<li>{escape(x)}</li>" for x in item["key_numbers"]) or "<li>None established from the available source material.</li>"
            cards.append(f'''<article class="card"><div class="tag">Deep Dive · Editorial score {item['editorial_score']:.1f}/10</div><h2>{escape(item['headline'])}</h2>
<h3>What Happened</h3><p>{escape(item['what_happened'])}</p><h3>Key Numbers</h3><ul>{numbers}</ul>
<h3>Why It Matters</h3><p>{escape(item['why_it_matters'])}</p><h3>Strategic Read</h3><p>{escape(item['strategic_read'])}</p>
<h3>Market Implication</h3><p>{escape(item['market_implication'])}</p><h3>Things to Watch</h3><ul>{watches}</ul>
<h3>Evidence Quality</h3><p>{escape(item['evidence_quality'].title())} — {escape(item['evidence_quality_explanation'])}</p><h3>Sources</h3><ul>{_sources(item['sources'])}</ul></article>''')
        for item in section.get("quick_reads", []):
            cards.append(f'''<article class="card quick"><div class="tag">Quick Read · Editorial score {item['editorial_score']:.1f}/10</div><h2>{escape(item['headline'])}</h2><p>{escape(item['what_happened'])}</p><p><strong>Why it matters:</strong> {escape(item['why_it_matters'])}</p><p><strong>Watch:</strong> {escape(item['one_thing_to_watch'])}</p><h3>Sources</h3><ul>{_sources(item['sources'])}</ul></article>''')
        if section.get("errors"):
            failures = "".join(f"<li>{escape(error.get('selected_title') or error.get('article_id') or error.get('short_id', 'Unknown selection'))}: could not be analyzed</li>"
                               for error in section["errors"])
            cards.append(f'<div class="notice"><strong>Selected-story analysis unavailable</strong><ul>{failures}</ul><p>The editorial selection was preserved; no substitute article was used. Details are in llm_analysis.json.</p></div>')
        if not cards:
            cards.append('<p class="notice">No qualifying story was selected, or LLM selection was unavailable for this section.</p>')
        blocks.append(f'<section><h1>{numeral}. {escape(sections[key]["name"])}</h1>{"".join(cards)}</section>')
    bullets = "".join(f"<li>{escape(x)}</li>" for x in data.get("executive_snapshot", []))
    if not bullets:
        bullets = "<li>Executive Snapshot unavailable; no independent summary was fabricated.</li>"
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    html = f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>48-Hour Market Intelligence Briefing</title><style>
body{{margin:0;background:#edf1f5;color:#172033;font:16px/1.6 Arial,sans-serif}}main{{max-width:940px;margin:auto;padding:40px 20px}}header{{background:#10213f;color:white;padding:36px;border-radius:12px}}header h1{{margin:0}}header p{{color:#cbd5e1}}section>h1{{margin-top:42px;border-bottom:3px solid #2563eb;padding-bottom:8px}}.snapshot,.card{{background:white;padding:24px;margin:18px 0;border-radius:10px;box-shadow:0 2px 9px #0001}}.card h2{{line-height:1.25}}.tag{{font-size:.78rem;text-transform:uppercase;letter-spacing:.08em;color:#2563eb;font-weight:bold}}h3{{font-size:1rem;margin-bottom:0}}p{{margin-top:.25rem}}a{{color:#1454a3;overflow-wrap:anywhere}}.quick{{border-left:4px solid #60a5fa}}.notice{{background:#fff7ed;padding:14px;border-radius:8px;color:#9a3412}}.case{{background:#fff;padding:30px;border-radius:12px;border-top:6px solid #7c3aed;box-shadow:0 3px 14px #0002}}.strategy>h1{{border-color:#7c3aed}}.case-meta,.option-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:18px}}.case-meta span{{background:#f5f3ff;padding:12px;border-radius:7px}}.case-meta strong{{display:block;color:#6d28d9;font-size:.75rem;text-transform:uppercase}}.thesis{{font-size:1.12rem;background:#f5f3ff;padding:18px;border-left:4px solid #7c3aed}}.option{{border:1px solid #ddd6fe;padding:0 18px;margin:12px 0;border-radius:8px}}.diagnostic{{display:block;font-size:.8rem;margin-top:5px}}</style></head><body><main><header><h1>48-Hour Market Intelligence Briefing</h1><p>LLM editorial edition · {generated}</p></header><section><h1>Executive Snapshot</h1><div class="snapshot"><ul>{bullets}</ul></div></section>{''.join(blocks)}{_strategy_case(strategy_case)}</main></body></html>'''
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
    return output_path
