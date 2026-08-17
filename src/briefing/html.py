"""Render selected articles as a standalone HTML briefing."""

from datetime import datetime, timezone
from html import escape
from pathlib import Path
from typing import Any

from src.analysis import analyze_article
from src.models import Article


def generate_html_briefing(
    selected: dict[str, list[Article]], sections: dict[str, Any], output_path: Path
) -> Path:
    """Write a readable local HTML briefing and return its path."""
    blocks: list[str] = []
    for key, settings in sections.items():
        cards = []
        for index, article in enumerate(selected.get(key, [])):
            analysis = analyze_article(article)
            deep_dive_count = settings.get("deep_dive_count", 1)
            story_type = "Case Study" if settings.get("case_count") else ("Deep Dive" if index < deep_dive_count else "Quick Read")
            cards.append(f"""
              <article class="card">
                <div class="label">{escape(story_type)} · {article.relevance_score:.1f}/10</div>
                <h2><a href="{escape(article.url)}">{escape(article.title)}</a></h2>
                <p class="source">{escape(article.source)} · {article.published_at:%Y-%m-%d %H:%M UTC}</p>
                <h3>What happened</h3><p>{escape(analysis['what_happened'])}</p>
                <h3>Why it matters</h3><p>{escape(analysis['why_it_matters'])}</p>
                <h3>Things to watch</h3><p>{escape(analysis['things_to_watch'])}</p>
              </article>""")
        content = "".join(cards) or '<p class="empty">No sample stories met the relevance threshold.</p>'
        blocks.append(f'<section><h1>{escape(settings["name"])}</h1>{content}</section>')

    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    html = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>48-Hour Market Intelligence Briefing</title>
<style>
body{{margin:0;background:#f3f5f7;color:#172033;font:16px/1.6 Arial,sans-serif}}main{{max-width:860px;margin:auto;padding:40px 20px}}header{{background:#13213c;color:white;padding:32px;border-radius:12px}}header h1{{margin:0}}header p{{margin-bottom:0;color:#cbd5e1}}section>h1{{margin-top:38px;border-bottom:3px solid #3b82f6;padding-bottom:8px}}.card{{background:white;padding:24px;margin:18px 0;border-radius:10px;box-shadow:0 2px 8px #00000012}}.card h2{{line-height:1.25;margin:.4rem 0}}a{{color:#1756a9}}.label{{color:#2563eb;font-size:.78rem;font-weight:bold;text-transform:uppercase;letter-spacing:.08em}}.source{{color:#64748b;font-size:.9rem}}h3{{font-size:1rem;margin-bottom:0}}.card p{{margin-top:.2rem}}.empty{{color:#64748b}}
</style></head><body><main><header><h1>48-Hour Market Intelligence</h1><p>Sample briefing generated {generated} · Offline demonstration</p></header>{''.join(blocks)}</main></body></html>"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
    return output_path

