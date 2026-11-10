"""Compare the saved medium and xhigh outputs without changing generated art."""
import html
import json
from pathlib import Path
import shutil
import statistics

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'experiments/monuments-xhigh'
BASE = ROOT / 'experiments/monuments'
xsummary = json.loads((OUT/'generation-summary.json').read_text())
medium = json.loads((BASE/'ratings.json').read_text())
prior = {row['slug']:row for row in medium['results']}
checks = {row['slug']:row for row in json.loads((OUT/'render-results.json').read_text())}
ratings = {
 '01-golden-gate':([6.5,6,8.5,10], 'The whole bridge fits and cables attach more coherently. The span is compressed, towers are broad and side approaches are simplified.'),
 '02-eiffel':([8.5,8,7.5,10], 'The open base arches and dense lattice improve the silhouette. The spire fits, though the circular base still touches the lower edge.'),
 '03-taj-mahal':([7,7,6,10], 'The front portal is stronger, but the oversized central dome and narrow facade weaken proportions. The garden remains cropped.'),
 '04-colosseum':([8,7.5,7,10], 'Renders on the first attempt with repeated open arches and clear stepped seating. The camera is close and the ruin treatment is simplified.'),
 '05-liberty':([7,6.5,8,10], 'Larger figure, clearer flame and blue harbor improve readability. The anatomy and tablet position are still blocky, with the island close to the frame edge.'),
 '06-opera-house':([3,4.5,8,10], 'Cleaner background and framing, but the roofs look like upright cones. The landmark silhouette is less convincing than medium.'),
 '07-pyramids':([8,6.5,8.5,10], 'All three pyramids fit and the scene has clear depth. It is sparse, with sharp shadows and limited stone detail.'),
 '08-big-ben':([8,8,7.5,10], 'Stronger golden illumination, readable clocks and more detail. The full spire fits, although some building proportions are simplified.'),
 '09-christ':([5.5,5,8,10], 'Smoother robe and a clearer arm silhouette improve the figure slightly. The head remains doll-like and contrast is low.'),
 '10-tower-bridge':([8.5,8,9,10], 'Complete diorama fits comfortably with richer tower detail and clear blue structural elements. Some suspension geometry is schematic.'),
}
rows=[]
for item in xsummary['results']:
    row=dict(item)
    old=prior[row['slug']]
    assert row['prompt']==old['prompt'], row['slug']
    row['dimensions'],row['assessment']=ratings[row['slug']]
    row['score']=round(sum(value*weight for value,weight in zip(row['dimensions'],[.4,.3,.2,.1]))+1e-8,1)
    row['medium_score']=old['score']
    row['delta']=round(row['score']-old['score'],1)
    row['checks']=checks[row['slug']]
    row['medium_usage']=old['usage']
    row['medium_seconds']=old['elapsed_seconds']
    rows.append(row)
    for suffix in ['.png','.html']:
        shutil.copy2(BASE/(row['slug']+suffix),OUT/(row['slug']+'-medium'+suffix))
ranked=sorted(rows,key=lambda row:row['score'],reverse=True)
for rank,row in enumerate(ranked,1):row['rank']=rank
xstats={
 'cost_usd':sum(row['usage']['cost'] for row in rows),
 'wall_seconds':xsummary['wall_seconds'],
 'median_request_seconds':statistics.median(row['elapsed_seconds'] for row in rows),
 'reasoning_tokens':sum(row['usage']['completion_tokens_details']['reasoning_tokens'] for row in rows),
 'total_tokens':sum(row['usage']['total_tokens'] for row in rows),
 'mean_score':statistics.mean(row['score'] for row in rows),
 'render_successes':sum(row['checks'].get('rendered',False) for row in rows),
 'improved':sum(row['delta']>0 for row in rows),
 'worse':sum(row['delta']<0 for row in rows),
}
mstats={
 'cost_usd':medium['stats']['total_cost_usd'],
 'wall_seconds':medium['stats']['generation_wall_seconds'],
 'median_request_seconds':medium['stats']['median_generation_seconds'],
 'reasoning_tokens':medium['stats']['reasoning_tokens'],
 'total_tokens':medium['stats']['total_tokens'],
 'mean_score':statistics.mean(row['medium_score'] for row in rows),
 'render_successes':medium['stats']['original_render_successes'],
}
notes='Identical saved prompts, one sample per effort per monument. Same model and provider, no reference images or repairs to xhigh outputs. Response cap increased from 11,000 to 32,000 tokens; all generations in both rounds ended with stop. Scores are subjective, using 40% recognizability, 30% visual finish, 20% framing and 10% working interaction. These paired samples suggest differences but do not establish statistical significance or isolate effort from the larger token cap.'
result={'method':notes,'medium':mstats,'xhigh':xstats,'results':rows}
(OUT/'comparison.json').write_text(json.dumps(result,indent=2))
esc=html.escape
base_html=(BASE/'index.html').read_text()
css=base_html.split('<style>',1)[1].split('</style>',1)[0]
css+='''\n.grid{grid-template-columns:1fr}.pair{display:grid;grid-template-columns:1fr 1fr;gap:1px;background:#34424d}.variant{background:#1a2229}.variant-label{padding:12px 18px;display:flex;justify-content:space-between;color:#c6d3dc;font-size:13px}.body p{min-height:0}.delta{float:right;color:#b6dfc3;font-size:18px}.comparison-table{border-collapse:collapse;width:min(760px,100%);font-size:14px;margin:25px 0}.comparison-table th,.comparison-table td{text-align:left;border-bottom:1px solid #34424d;padding:12px 15px}.comparison-table th{color:#b5c8d4}.note{color:#a5b6c2;font-size:13px;line-height:1.6}button.secondary{background:#293943;border-color:#4a616e}@media(max-width:700px){.pair{grid-template-columns:1fr}}'''
parts=[f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Muse Ember · medium vs xhigh</title><style>{css}</style></head><body><main><header><div class="kicker">MUSE EMBER · PAIRED THREE.JS EXPERIMENT</div><h1>Medium vs xhigh.</h1><p>Ten identical prompts replayed with more reasoning. Every image below is an original first attempt. Open either scene to orbit, zoom and compare the geometry.</p></header>''']
parts.append('<table class="comparison-table"><thead><tr><th>Observed metric</th><th>Medium</th><th>Xhigh</th></tr></thead><tbody>')
for label,mvalue,xvalue in [
 ('First-attempt render success',f"{mstats['render_successes']}/10",f"{xstats['render_successes']}/10"),
 ('Total API cost',f"${mstats['cost_usd']:.5f}",f"${xstats['cost_usd']:.5f}"),
 ('Parallel generation wall time',f"{mstats['wall_seconds']:.1f}s",f"{xstats['wall_seconds']:.1f}s"),
 ('Median request time',f"{mstats['median_request_seconds']:.1f}s",f"{xstats['median_request_seconds']:.1f}s"),
 ('Reasoning tokens',f"{mstats['reasoning_tokens']:,}",f"{xstats['reasoning_tokens']:,}"),
 ('Mean subjective score',f"{mstats['mean_score']:.2f}/10",f"{xstats['mean_score']:.2f}/10"),
]:parts.append(f'<tr><td>{label}</td><td>{mvalue}</td><td>{xvalue}</td></tr>')
parts.append(f'''</tbody></table><p class="note">{esc(notes)}</p><div class="toolbar"><p>{xstats['improved']} outputs scored higher · {xstats['worse']} scored lower</p><label>Order <select id="sort"><option value="order">Monument order</option><option value="rank">Highest xhigh score</option><option value="gain">Largest improvement</option></select></label></div><section class="grid" id="grid">''')
for row in rows:
    slug=row['slug']
    parts.append(f'''<article class="card" data-order="{slug[:2]}" data-rank="{row['rank']}" data-gain="{-row['delta']}"><div class="body"><span class="delta">{row['delta']:+.1f}</span><div class="eyebrow">EXPERIMENT {slug[:2]} · {esc(row['approach'])}</div><h2>{esc(row['name'])}</h2></div><div class="pair">''')
    for effort,score,seconds,cost,file in [
        ('medium',row['medium_score'],row['medium_seconds'],row['medium_usage']['cost'],slug+'-medium'),
        ('xhigh',row['score'],row['elapsed_seconds'],row['usage']['cost'],slug),
    ]:
        parts.append(f'''<div class="variant"><div class="variant-label"><strong>{effort.upper()} · {score:.1f}/10</strong><span>{seconds:.1f}s · ${cost:.5f}</span></div><div class="thumbnail"><img src="{file}.png" alt="{esc(row['name'])}, {effort}" loading="lazy"></div><div class="body"><button data-scene="{file}" data-title="{esc(row['name'])} · {effort}">Explore {effort}</button></div></div>''')
    parts.append(f'''</div><div class="body"><p>{esc(row['assessment'])}</p><details><summary>Prompt and scores</summary><dl><dt>Recognizability</dt><dd>{row['dimensions'][0]}/10</dd><dt>Visual finish</dt><dd>{row['dimensions'][1]}/10</dd><dt>Framing</dt><dd>{row['dimensions'][2]}/10</dd><dt>Working interaction</dt><dd>{row['dimensions'][3]}/10</dd></dl><pre>{esc(row['prompt'])}</pre><a href="{slug}.json">Xhigh request metadata</a></details></div></article>''')
parts.append('''</section><footer>Medium Colosseum is shown as its failed original and scored 0. Its separately repaired version previously scored 7.7. All ten xhigh scenes passed rendering, orbit, zoom and resize checks. One image was inspected for every original output. <a href="comparison.json">Comparison data</a> · <a href="contact-sheet.html">Xhigh preview sheet</a></footer></main><dialog id="viewer"><div class="bar"><strong id="viewer-title"></strong><span>Drag to orbit · scroll to zoom</span><button id="close">Close ✕</button></div><iframe id="scene" title="Interactive monument" sandbox="allow-scripts allow-same-origin"></iframe></dialog><script>
const viewer=document.getElementById('viewer');
const frame=document.getElementById('scene');
for(const button of document.querySelectorAll('[data-scene]')){
  button.addEventListener('click',()=>{
    document.getElementById('viewer-title').textContent=button.dataset.title;
    frame.src=button.dataset.scene+'.html';
    viewer.showModal();
  });
}
function closeScene(){frame.removeAttribute('src');viewer.close();}
document.getElementById('close').addEventListener('click',closeScene);
viewer.addEventListener('cancel',event=>{event.preventDefault();closeScene();});
document.getElementById('sort').addEventListener('change',event=>{
  const key=event.target.value;
  const grid=document.getElementById('grid');
  const cards=Array.from(grid.children);
  cards.sort((a,b)=>Number(a.dataset[key])-Number(b.dataset[key]));
  for(const card of cards)grid.appendChild(card);
});
</script></body></html>''')
(OUT/'index.html').write_text(''.join(parts))
contact_source=(BASE/'contact-sheet.html').read_text()
contact_css=contact_source.split('<style>',1)[1].split('</style>',1)[0]
contact=[f'''<!doctype html><meta charset="utf-8"><title>Xhigh monument previews</title><style>{contact_css}</style><header><h1>Muse Ember · xhigh reasoning</h1><p>Ten parallel first attempts · all 10 rendered · total ${xstats['cost_usd']:.4f} · medium → xhigh scores</p></header><div class="grid">''']
for row in rows:
    contact.append(f'''<article><img src="{row['slug']}.png"><section><h2>{row['slug'][:2]} · {esc(row['name'])}<span class="score">{row['medium_score']:.1f} → {row['score']:.1f}</span></h2><p>{esc(row['approach'])}</p></section></article>''')
contact.append('</div><footer>Identical prompts. One sample per setting. Xhigh cap 32,000 tokens vs medium 11,000. Scores are subjective. No xhigh repairs.</footer>')
(OUT/'contact-sheet.html').write_text(''.join(contact))
report=['# Medium versus xhigh reasoning','',notes,'','| Metric | Medium | Xhigh |','|---|---:|---:|']
for key in ['cost_usd','wall_seconds','median_request_seconds','reasoning_tokens','total_tokens','mean_score','render_successes']:
    report.append(f"| {key} | {mstats[key]} | {xstats[key]} |")
report+=['','| Monument | Medium | Xhigh | Delta |','|---|---:|---:|---:|']
for row in rows:report.append(f"| {row['name']} | {row['medium_score']:.1f} | {row['score']:.1f} | {row['delta']:+.1f} |")
report+=['','Medium Colosseum received 0 because the original failed to parse. Its one-line repaired variant previously scored 7.7. All ten xhigh outputs render without repairs and pass orbit, zoom and resize checks.','']
for row in rows:report.append(f"- **{row['name']}** — {row['assessment']}")
(OUT/'REPORT.md').write_text('\n'.join(report)+'\n')
print(json.dumps({'medium':mstats,'xhigh':xstats,'cost_ratio':xstats['cost_usd']/mstats['cost_usd'],'reasoning_ratio':xstats['reasoning_tokens']/mstats['reasoning_tokens']},indent=2))
