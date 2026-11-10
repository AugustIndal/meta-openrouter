"""Generate matched native Canvas/SVG monument outputs, preserving metadata only."""
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import json,time,urllib.request,urllib.error
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'experiments/web2d-comparison'
BASE=json.loads((ROOT/'experiments/monuments-xhigh/generation-summary.json').read_text())
CONFIG=dict(line.split('=',1) for line in (ROOT/'.env').read_text().splitlines() if line and not line.startswith('#'))
COMMON=' Use only native 2D drawing primitives. No WebGL, Three.js, 3D engine, external assets, images, fonts, imports or network calls. Depict the requested perspective using 2D shapes, paths and gradients. Create polished lighting, shadows and material variation with gradients and layered shapes. Frame the complete monument with its top and base visible and at least 10% margin. Do not obstruct it with foreground objects. No text overlays. Deterministic artwork, 1200x800 composition. Prioritize the visual result and working code. Use no more than 32000 output tokens including reasoning.'
CONTRACTS={
'canvas':'Return only a complete HTML document without Markdown fences. Draw the entire artwork using the native HTML5 Canvas 2D API on a responsive full-window canvas, initially 1200x800. Preserve the composition on resize and redraw. Render the finished scene immediately, then set window.sceneReady=true.'+COMMON,
'svg':'Return only one complete standalone SVG document without Markdown fences. Use xmlns="http://www.w3.org/2000/svg", width="1200", height="800", viewBox="0 0 1200 800". Build the entire artwork with native SVG paths, shapes, gradients, masks and filters. No scripts or embedded HTML.'+COMMON}
def generate(previous,fmt):
 slug=previous['slug'];stem=slug+'-'+fmt; target=OUT/(stem+'.json')
 if target.exists(): return json.loads(target.read_text())
 brief=previous['prompt'].split('\n\nReturn only')[0];prompt=brief+'\n\n'+CONTRACTS[fmt]
 meta={k:previous[k] for k in ['slug','name','approach']};meta.update(format=fmt,prompt=prompt,scene_brief=brief,requested_model=CONFIG['OPENROUTER_MODEL'],requested_effort='xhigh',max_tokens=32000)
 payload={'model':CONFIG['OPENROUTER_MODEL'],'messages':[{'role':'user','content':prompt}],'max_tokens':32000,'reasoning':{'effort':'xhigh'},'usage':{'include':True}}
 request=urllib.request.Request(CONFIG['OPENROUTER_BASE_URL'].rstrip('/')+'/chat/completions',data=json.dumps(payload).encode(),headers={'Authorization':'Bearer '+CONFIG['OPENROUTER_API_KEY'],'Content-Type':'application/json'})
 start=time.monotonic()
 try:
  with urllib.request.urlopen(request,timeout=360) as response: result=json.load(response)
  if 'error' in result: raise RuntimeError(str(result['error']))
  choice=result['choices'][0];content=(choice['message'].get('content') or '').strip()
  if content.startswith('```'): content=content.split('\n',1)[1].rsplit('```',1)[0].strip()
  extension='html' if fmt=='canvas' else 'svg'; (OUT/(stem+'.'+extension)).write_text(content)
  meta.update(model=result.get('model'),provider=result.get('provider'),usage=result.get('usage'),finish_reason=choice.get('finish_reason'),bytes=len(content.encode()),generation_id=result.get('id'),file=stem+'.'+extension)
 except urllib.error.HTTPError as e: meta['error']=f'HTTP {e.code}: '+e.read().decode()
 except Exception as e: meta['error']=str(e)
 meta['elapsed_seconds']=round(time.monotonic()-start,3);target.write_text(json.dumps(meta,indent=2));print(json.dumps({k:v for k,v in meta.items() if k not in ('prompt','scene_brief')}),flush=True);return meta
if __name__=='__main__':
 start=time.monotonic()
 with ThreadPoolExecutor(max_workers=5) as pool: results=[f.result() for f in as_completed([pool.submit(generate,p,fmt) for p in BASE['results'] for fmt in CONTRACTS])]
 (OUT/'generation-summary.json').write_text(json.dumps({'requested_effort':'xhigh','max_tokens':32000,'max_concurrency':5,'wall_seconds':round(time.monotonic()-start,3),'results':sorted(results,key=lambda x:(x['slug'],x['format']))},indent=2))
