"""Professional, escaped rendering for completed Phase 3 analyses."""

from datetime import datetime, timezone
from html import escape
from pathlib import Path
from typing import Any


def _sources(urls: list[str]) -> str:
    return "".join(f'<li><a href="{escape(url, quote=True)}">{escape(url)}</a></li>' for url in urls)


def generate_llm_briefing(data: dict[str, Any], sections: dict[str, Any], output_path: Path) -> Path:
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
body{{margin:0;background:#edf1f5;color:#172033;font:16px/1.6 Arial,sans-serif}}main{{max-width:940px;margin:auto;padding:40px 20px}}header{{background:#10213f;color:white;padding:36px;border-radius:12px}}header h1{{margin:0}}header p{{color:#cbd5e1}}section>h1{{margin-top:42px;border-bottom:3px solid #2563eb;padding-bottom:8px}}.snapshot,.card{{background:white;padding:24px;margin:18px 0;border-radius:10px;box-shadow:0 2px 9px #0001}}.card h2{{line-height:1.25}}.tag{{font-size:.78rem;text-transform:uppercase;letter-spacing:.08em;color:#2563eb;font-weight:bold}}h3{{font-size:1rem;margin-bottom:0}}p{{margin-top:.25rem}}a{{color:#1454a3;overflow-wrap:anywhere}}.quick{{border-left:4px solid #60a5fa}}.notice{{background:#fff7ed;padding:14px;border-radius:8px;color:#9a3412}}</style></head><body><main><header><h1>48-Hour Market Intelligence Briefing</h1><p>LLM editorial edition · {generated}</p></header><section><h1>Executive Snapshot</h1><div class="snapshot"><ul>{bullets}</ul></div></section>{''.join(blocks)}<section><h1>IV. Corporate Strategy Case</h1><p class="notice">Placeholder for a future phase.</p></section></main></body></html>'''
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
    return output_path
