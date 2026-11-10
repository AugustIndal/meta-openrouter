"""Build the California reasoning gallery from saved experiment artifacts.

Usage: python scripts/build_california_gallery.py [--root PATH]
The generation summary is required. Checks, ratings and clue checks are optional.
"""

import argparse
import html
import json
from pathlib import Path
import statistics


DEFAULT_ROOT = Path(__file__).resolve().parents[1] / "experiments" / "california-levels"
LEVELS = ["minimal", "low", "medium", "high", "xhigh", "max"]


def read_json(path, default):
    return json.loads(path.read_text()) if path.exists() else default


def esc(value):
    return html.escape(str(value), quote=True)


def number(value, digits=1, suffix=""):
    return f"{value:,.{digits}f}{suffix}" if isinstance(value, (int, float)) else "—"


def reasoning(row):
    return (row.get("usage") or {}).get("completion_tokens_details", {}).get("reasoning_tokens")


def total_known(rows, getter, digits=0, prefix=""):
    values = [getter(row) for row in rows]
    known = [value for value in values if isinstance(value, (int, float))]
    if not known:
        return "—"
    return prefix + number(sum(known), digits) + ("*" if len(known) != len(values) else "")


STYLE = """
:root{color-scheme:dark;font-family:Inter,ui-sans-serif,system-ui,sans-serif;background:#10151a;color:#eef2f3}*{box-sizing:border-box}body{margin:0}main{max-width:1660px;margin:auto;padding:40px 30px}.kicker{color:#a8d5bb;font-size:11px;letter-spacing:.18em;font-weight:700}h1{font-size:clamp(32px,4vw,54px);letter-spacing:-.045em;line-height:1.08;margin:13px 0}header p{max-width:960px;color:#b3bdc6;line-height:1.65;font-size:14px}.stats{display:flex;gap:34px;flex-wrap:wrap;margin:24px 0 30px}.stats strong{font-size:25px;display:block}.stats span{color:#9aa9b4;font-size:12px}.toolbar{display:flex;justify-content:space-between;gap:20px;align-items:center;border-top:1px solid #303b43;padding:20px 0}.toolbar p{margin:0;color:#aab7c1;font-size:13px}select,button{font:inherit;color:#edf7f1;background:#233c32;border:1px solid #456254;border-radius:7px;padding:9px 12px;cursor:pointer}select{background:#1e272e;margin-left:8px;max-width:100%}button:hover{background:#315341}button:focus-visible,select:focus-visible,a:focus-visible,summary:focus-visible{outline:2px solid #a9d6e7;outline-offset:4px}.grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:18px}.card{background:#1a2229;border:1px solid #303b43;border-radius:10px;overflow:hidden;min-width:0}.thumbnail{position:relative;background:#131b22}.thumbnail img{width:100%;aspect-ratio:3/2;object-fit:contain;display:block}.badge{position:absolute;top:12px;right:12px;background:#10191ee8;border:1px solid #5b736b;color:#e1f6e9;padding:7px 10px;border-radius:7px;font-weight:700;font-size:20px}.badge small{font-size:11px;color:#b1c4b8}.body{padding:17px}.eyebrow{font-size:10px;letter-spacing:.14em;color:#a8d5bb;font-weight:700}h2{font-size:21px;letter-spacing:-.025em;margin:7px 0}.note{color:#b8c4cd;line-height:1.55;font-size:13px;min-height:60px;margin:12px 0}.metrics{display:flex;gap:6px 13px;flex-wrap:wrap;color:#9fafba;font-size:11px;border-top:1px solid #35404a;padding-top:12px;font-variant-numeric:tabular-nums}.check{font-size:11px;color:#adc2cd;margin:10px 0 0}.error{color:#ffc1a7}.actions{display:flex;gap:12px;flex-wrap:wrap;align-items:center;margin:15px 0}a{color:#a9d6e7;font-size:13px}details{border-top:1px solid #35404a;padding-top:11px}summary{font-size:12px;color:#aebec7;cursor:pointer}pre{white-space:pre-wrap;overflow-wrap:anywhere;color:#b6c3cc;line-height:1.6;font:11px ui-monospace,monospace;background:#131a20;padding:12px;border-radius:6px;max-height:300px;overflow:auto}.location-copy{color:#b3bdc6;line-height:1.65;font-size:13px;margin:0 0 20px;max-width:1050px}.table-wrap{overflow:auto;border:1px solid #303b43;border-radius:10px;margin-top:14px}table{width:100%;border-collapse:collapse;font-size:12px;text-align:left;white-space:nowrap}th,td{padding:13px 15px;border-bottom:1px solid #303b43}th{color:#a7b7c1;font-weight:500;background:#172027}td{font-variant-numeric:tabular-nums}tr:last-child td{border:0}.section-title{margin-top:32px;font-size:22px}footer,.method{color:#95a6b2;font-size:12px;line-height:1.75;margin-top:18px}.links{display:flex;gap:16px;flex-wrap:wrap;margin-top:12px}dialog{width:min(1450px,96vw);height:91vh;max-width:none;max-height:none;padding:0;border:1px solid #546a70;border-radius:12px;background:#111b22;color:white}dialog::backdrop{background:#050a10df}dialog .bar{min-height:64px;display:flex;align-items:center;gap:16px;padding:12px 18px}dialog .bar strong{flex:1}dialog .bar span{font-size:12px;color:#b3bdc6}dialog iframe{border:0;width:100%;height:calc(100% - 64px);background:#172129}[hidden]{display:none!important}@media(max-width:1000px){.grid{grid-template-columns:repeat(2,minmax(0,1fr))}}@media(max-width:650px){main{padding:26px 15px}.grid{grid-template-columns:1fr}.toolbar{align-items:flex-start;flex-direction:column}.stats{gap:22px}.note{min-height:0}dialog .bar span{display:none}}
"""


def card(row, checks, rating, expanded=None):
    slug = row["slug"]
    check = checks.get(slug, {})
    score = rating.get("score")
    status = "Render not checked"
    if check.get("rendered") is True:
        status = "Rendered"
    elif check.get("rendered") is False or check.get("failure") or row.get("error"):
        status = "Render failed"
    interaction = []
    for key, label in [("orbitChangesImage", "orbit"), ("zoomChangesImage", "zoom"), ("resizedCanvas", "resize")]:
        if key in check:
            interaction.append(f"{label} {'✓' if check[key] else '✕'}")
    errors = check.get("errors") or []
    failure = check.get("failure") or row.get("error")
    diagnostic = ""
    if errors or failure:
        diagnostic = f'<pre class="error">{esc(json.dumps({"failure": failure, "errors": errors}, indent=2))}</pre>'
    expanded_action = ""
    if expanded:
        expanded_slug = expanded["slug"]
        expanded_action = (
            f'<p class="check">128,000-token retry · {number(expanded.get("elapsed_seconds"), 2, "s")} · '
            f'${number((expanded.get("usage") or {}).get("cost"), 6)}</p>'
            f'<button data-scene="{esc(expanded_slug)}" data-title="{esc(row["name"])} · max · 128k retry">Explore expanded-cap retry</button>'
            f'<a href="{esc(expanded_slug)}.png" target="_blank">Retry preview</a>'
        )
    usage = row.get("usage") or {}
    badge = f'<span class="badge">{number(score)}<small> /10</small></span>' if score is not None else ""
    return f'''<article class="card"><div class="thumbnail"><img src="{esc(slug)}.png" alt="{esc(row['name'])}, {esc(row['effort'])} effort, initial camera" loading="lazy">{badge}</div>
<div class="body"><div class="eyebrow">REASONING EFFORT</div><h2>{esc(row['effort']).upper()}</h2><p class="note">{esc(rating.get('note') or 'Visual review pending.')}</p>
<div class="metrics"><span>{number(row.get('elapsed_seconds'), 2, 's')} generation</span><span>{('$' + number(usage.get('cost'), 6)) if usage.get('cost') is not None else '—'} API cost</span><span>{number(reasoning(row), 0)} reasoning tokens</span></div>
<p class="check {'error' if status == 'Render failed' else ''}">{esc(status)}{' · ' + esc(' · '.join(interaction)) if interaction else ''}</p>
<div class="actions"><button data-scene="{esc(slug)}" data-title="{esc(row['name'])} · {esc(row['effort'])}">Explore in 3D</button><a href="{esc(slug)}.html" target="_blank" rel="noopener">Scene ↗</a></div>
{expanded_action}<details><summary>Exact prompt &amp; metadata</summary><pre>{esc(row.get('prompt', 'Prompt unavailable.'))}</pre><a href="{esc(slug)}.json">Saved generation metadata</a>{diagnostic}</details></div></article>'''


def clue_cell(rows):
    if not rows:
        return "—"
    matched = sum(row.get("correct") is True for row in rows)
    return f"{matched}/{len(rows)} matched"


def build(root):
    summary = read_json(root / "generation-summary.json", None)
    if summary is None:
        raise SystemExit(f"Required generation summary missing: {root / 'generation-summary.json'}")
    rows = summary["results"]
    levels = summary.get("levels") or LEVELS
    locations = summary["locations"]
    checks = {row["slug"]: row for row in read_json(root / "render-results.json", [])}
    ratings = read_json(root / "ratings.json", {})
    clue_data = read_json(root / "clue-check-summary.json", {})
    clue_rows = clue_data.get("results", [])
    groups = []
    for index, location in enumerate(locations):
        location_rows = {row["effort"]: row for row in rows if row["id"] == location["id"]}
        cards = "".join(card(location_rows[level], checks, ratings.get(location_rows[level]["slug"], {}), read_json(root / (location_rows[level]["slug"] + "-expanded.json"), None)) for level in levels if level in location_rows)
        groups.append(f'''<section class="location" id="location-{esc(location['id'])}" {'hidden' if index else ''}><p class="location-copy"><strong>{esc(location['region'])}</strong> · {esc(location['description'])} <a href="contact-{esc(location['id'])}.html">Six-image contact sheet ↗</a></p><div class="grid">{cards}</div></section>''')
        build_contact(root, location, [location_rows[level] for level in levels if level in location_rows], ratings)

    aggregate_rows = []
    for level in levels:
        selected = [row for row in rows if row["effort"] == level]
        scores = [ratings.get(row["slug"], {}).get("score") for row in selected]
        scores = [score for score in scores if isinstance(score, (int, float))]
        times = [row["elapsed_seconds"] for row in selected if isinstance(row.get("elapsed_seconds"), (int, float))]
        rendered = sum(checks.get(row["slug"], {}).get("rendered") is True for row in selected)
        checked = sum(row["slug"] in checks for row in selected)
        clues = [row for row in clue_rows if row.get("effort") == level]
        score_text = number(statistics.mean(scores)) + f" ({len(scores)}/{len(selected)})" if scores else "—"
        aggregate_rows.append(f'''<tr><td><strong>{esc(level)}</strong></td><td>{rendered}/{len(selected)} <span title="Number of saved render checks">({checked} checked)</span></td><td>{score_text}</td><td>{number(statistics.median(times) if times else None, 2, 's')}</td><td>{total_known(selected, lambda row: (row.get('usage') or {}).get('cost'), 6, '$')}</td><td>{total_known(selected, reasoning)}</td><td>{clue_cell(clues)}</td></tr>''')

    success_count = sum(check.get("rendered") is True for check in checks.values())
    options = "".join(f'<option value="{esc(location["id"])}">{esc(location["name"])}</option>' for location in locations)
    clue_details = ""
    if clue_rows:
        clue_details = f'''<details class="method"><summary>Clue-check responses and validation</summary><p>These separate structured-answer checks are reported alongside the rendering experiment. Their costs and tokens are excluded from the rendering totals above.</p><pre>{esc(json.dumps(clue_rows, indent=2, ensure_ascii=False))}</pre><a href="clue-check-summary.json">Clue-check data</a></details>'''
    page = f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>California · Six reasoning levels</title><style>{STYLE}</style></head><body><main>
<header><div class="kicker">MUSE EMBER · CALIFORNIA · THREE.JS EXPERIMENT</div><h1>Six places. Six reasoning levels.</h1><p>The same visual description was rendered once at each reasoning level. No named landmark was sent to the rendering model. Compare initial camera views, inspect the exact prompts and explore the saved 3D outputs.</p></header>
<section class="stats" aria-label="Experiment totals"><div><strong>{success_count} / {len(rows)}</strong><span>saved render successes</span></div><div><strong>{total_known(rows, lambda row: (row.get('usage') or {}).get('cost'), 4, '$')}</strong><span>rendering API-reported cost</span></div><div><strong>{number(summary.get('wall_seconds'), 1, 's')}</strong><span>generation wall time</span></div><div><strong>{total_known(rows, reasoning)}</strong><span>rendering reasoning tokens</span></div></section>
<div class="toolbar"><label for="location">Location <select id="location">{options}</select></label><p>Original outputs · drag to orbit · scroll to zoom</p></div>{''.join(groups)}
<h2 class="section-title">Across all six locations</h2><div class="table-wrap"><table><thead><tr><th scope="col">Effort</th><th scope="col">Render success</th><th scope="col">Mean score /10 (rated)</th><th scope="col">Median generation</th><th scope="col">Total API cost</th><th scope="col">Reasoning tokens</th><th scope="col">Clue checks</th></tr></thead><tbody>{''.join(aggregate_rows)}</tbody></table></div>
<p class="method">One sample per location and reasoning level. Visual scores are subjective judgments of these saved outputs, with no replication or blinded adjudication. This small experiment is not a definitive benchmark. Latency is per generation request. Costs and reasoning counts come from API usage metadata. A dash means unavailable, and * marks a partial total. Render and interaction results come from saved browser checks.</p>{clue_details}
<footer><div class="links"><a href="GAME_DESIGN.md">Game design brief</a><a href="generation-summary.json">Generation data</a><a href="render-results.json">Browser checks</a><a href="ratings.json">Visual ratings</a></div><p>Location names are gallery labels added after generation. Each rendering prompt contains a visual description and the shared rendering contract. The interactive scene loads only when you select Explore.</p></footer>
</main><dialog id="viewer"><div class="bar"><strong id="viewer-title"></strong><span>Drag to orbit · scroll to zoom</span><button id="close" aria-label="Close 3D scene">Close ✕</button></div><iframe id="scene" title="Interactive generated California scene" sandbox="allow-scripts allow-same-origin"></iframe></dialog>
<script>
const viewer = document.getElementById('viewer');
const frame = document.getElementById('scene');
document.getElementById('location').addEventListener('change', event => {{
  for (const section of document.querySelectorAll('.location')) section.hidden = section.id !== 'location-' + event.target.value;
}});
for (const button of document.querySelectorAll('[data-scene]')) {{
  button.addEventListener('click', () => {{
    document.getElementById('viewer-title').textContent = button.dataset.title;
    frame.src = button.dataset.scene + '.html';
    viewer.showModal();
  }});
}}
function closeScene() {{ frame.removeAttribute('src'); viewer.close(); }}
document.getElementById('close').addEventListener('click', closeScene);
viewer.addEventListener('cancel', event => {{ event.preventDefault(); closeScene(); }});
</script></body></html>'''
    (root / "index.html").write_text(page)
    print(f"Built {root / 'index.html'} and {len(locations)} contact sheets")


def build_contact(root, location, rows, ratings):
    cards = []
    for row in rows:
        rating = ratings.get(row["slug"], {})
        score = number(rating.get("score")) + "/10" if rating.get("score") is not None else "Review pending"
        cards.append(f'''<article><img src="{esc(row['slug'])}.png" alt="{esc(row['name'])}, {esc(row['effort'])} effort"><div class="caption"><strong>{esc(row['effort']).upper()}</strong><span>{score} · {number(row.get('elapsed_seconds'), 2, 's')}</span></div><p>{esc(rating.get('note', 'Visual review pending.'))}</p></article>''')
    page = f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>{esc(location['name'])} · Six reasoning levels</title><style>
*{{box-sizing:border-box}}body{{margin:0;padding:24px 26px;background:#10151a;color:#e7eff3;font:14px system-ui}}header{{display:flex;justify-content:space-between;align-items:baseline;margin-bottom:16px}}h1{{margin:0;font-size:29px;letter-spacing:-.035em}}header p{{margin:0;color:#a9bac5;font-size:12px}}.grid{{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:16px}}article{{background:#1a2229;border:1px solid #303b43;border-radius:9px;overflow:hidden;min-width:0}}img{{display:block;width:100%;height:380px;object-fit:contain;background:#131b22}}.caption{{display:flex;justify-content:space-between;gap:10px;padding:12px 14px 0}}strong{{color:#b8e0c8;letter-spacing:.08em;font-size:12px}}span{{color:#c0d0d8;font-size:12px}}article p{{font-size:12px;line-height:1.45;color:#aebfc9;margin:8px 14px 13px;min-height:35px}}footer{{font-size:11px;color:#91a5b2;margin-top:14px}}a{{color:#a9d6e7}}@media(max-width:900px){{.grid{{grid-template-columns:repeat(2,minmax(0,1fr))}}img{{height:auto;aspect-ratio:3/2}}header{{display:block}}}}@media(max-width:550px){{.grid{{grid-template-columns:1fr}}}}
</style></head><body><header><h1>{esc(location['name'])}</h1><p>{esc(location['region'])} · Muse Ember · one original output per effort level</p></header><div class="grid">{''.join(cards)}</div><footer>Descriptions only were supplied to the rendering model. Subjective visual scores. No scene iframes are loaded here. <a href="index.html">Interactive comparison</a></footer></body></html>'''
    (root / f"contact-{location['id']}.html").write_text(page)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    build(parser.parse_args().root)
