from pathlib import Path
import json,html,statistics
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'experiments/web2d-comparison'
base=json.loads((ROOT/'experiments/monuments-xhigh/generation-summary.json').read_text())['results']
run=json.loads((OUT/'generation-summary.json').read_text());items=run['results'];scores=json.loads((OUT/'scores.json').read_text())
formats=['three','canvas','svg'];lookup={(x['slug'],x['format']):x for x in items};lookup.update({(x['slug'],'three'):x for x in base})
style='''body{margin:0;background:#10151d;color:#e8eef7;font:15px system-ui}header,main{max-width:1700px;margin:auto;padding:28px}h1{font-size:34px}p{max-width:1100px;line-height:1.6;color:#b9c5d6}.grid{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}article{background:#192330;border-radius:12px;overflow:hidden}img{display:block;width:100%;aspect-ratio:1.5}article div{padding:16px}h2{margin-top:40px}h3{margin:0 0 8px}a{color:#9ad8ff}.score{font-size:20px;font-weight:700}.muted{color:#b9c5d6;font-size:13px}table{border-collapse:collapse}td,th{padding:10px 18px;text-align:left;border-bottom:1px solid #344151}@media(max-width:800px){.grid{grid-template-columns:1fr}}'''
summary=[]
for fmt in formats:
 data=[lookup[(b['slug'],fmt)] for b in base]
 summary.append({'format':fmt,'mean_score':statistics.mean(scores[b['slug']][fmt]['score'] for b in base),'cost':sum(d['usage']['cost'] for d in data),'mean_seconds':statistics.mean(d['elapsed_seconds'] for d in data),'prompt_tokens':sum(d['usage']['prompt_tokens'] for d in data),'completion_tokens':sum(d['usage']['completion_tokens'] for d in data),'reasoning_tokens':sum(d['usage']['completion_tokens_details']['reasoning_tokens'] for d in data)})
(OUT/'comparison-summary.json').write_text(json.dumps(summary,indent=2))
parts=['<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Monuments · Canvas / SVG / Three.js</title><style>'+style+'</style><header><h1>One brief, three renderers</h1><p>The original 10 monuments, Muse Ember at xhigh reasoning. Each format gets the same scene brief. Canvas and SVG use native 2D paths and gradients. The saved Three.js run supplies the baseline. Scores are subjective visual assessments of the default view, not measured model capability.</p><table><tr><th>Format</th><th>Mean score /10</th><th>Mean generation</th><th>10-call cost</th></tr>']
for d in summary: parts.append(f"<tr><td>{d['format']}</td><td>{d['mean_score']:.1f}</td><td>{d['mean_seconds']:.1f}s</td><td>${d['cost']:.5f}</td></tr>")
parts.append('</table><p>All first-pass calls use a 32,000-token API cap, combining reasoning and answer. The historical Three.js prompt additionally requested 9,000 tokens in text, which its outputs sometimes exceeded. The new contracts request 32,000. Baseline latency is from a separate 10-concurrent run; new calls were limited to five concurrent, so latency is descriptive. Native Canvas and SVG were tested. Paper.js, Fabric.js, D3 and headless Canvas were not empirically tested.</p><a href="REPORT.md">Report</a> · <a href="contact-sheet.png">Full contact sheet</a> · <a href="generation-summary.json">Generation metadata</a></header><main>')
for b in base:
 slug=b['slug'];parts.append('<h2>'+html.escape(b['name'])+'</h2><p>'+html.escape(b['prompt'].split('\n\nReturn only')[0])+'</p><div class="grid">')
 for fmt in formats:
  d=lookup[(slug,fmt)];s=scores[slug][fmt];link=('baseline/'+slug+'.html') if fmt=='three' else d['file']
  parts.append(f'<article><a href="{link}"><img loading="lazy" src="{slug}-{fmt}.png"></a><div><h3>{fmt.upper()}</h3><span class="score">{s["score"]}/10</span><p>{html.escape(s["note"])}</p><span class="muted">{d["elapsed_seconds"]:.1f}s · ${d["usage"]["cost"]:.5f} · {d["usage"]["completion_tokens"]:,} completion tokens</span><p><a href="{link}">Open artwork</a></p></div></article>')
 parts.append('</div>')
parts.append('</main>');(OUT/'index.html').write_text(''.join(parts))
