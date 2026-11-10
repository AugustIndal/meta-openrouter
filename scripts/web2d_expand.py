from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import json,time,urllib.request
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'experiments/web2d-comparison'
config=dict(line.split('=',1) for line in (ROOT/'.env').read_text().splitlines() if line and not line.startswith('#'))
def run(stem):
 original=json.loads((OUT/(stem+'.json')).read_text());d={k:original[k] for k in ['slug','name','approach','format','prompt','scene_brief']};d.update(requested_model=config['OPENROUTER_MODEL'],requested_effort='xhigh',max_tokens=128000,variant='expanded-cap',original_stem=stem)
 payload={'model':config['OPENROUTER_MODEL'],'messages':[{'role':'user','content':d['prompt']}],'max_tokens':128000,'reasoning':{'effort':'xhigh'},'usage':{'include':True}}
 request=urllib.request.Request(config['OPENROUTER_BASE_URL'].rstrip('/')+'/chat/completions',data=json.dumps(payload).encode(),headers={'Authorization':'Bearer '+config['OPENROUTER_API_KEY'],'Content-Type':'application/json'})
 start=time.monotonic()
 try:
  with urllib.request.urlopen(request,timeout=600) as response:r=json.load(response)
  c=r['choices'][0];content=(c['message'].get('content') or '').strip()
  if content.startswith('```'):content=content.split('\n',1)[1].rsplit('```',1)[0].strip()
  filename=stem+'-expanded.'+('html' if d['format']=='canvas' else 'svg');(OUT/filename).write_text(content)
  d.update(model=r.get('model'),provider=r.get('provider'),usage=r.get('usage'),finish_reason=c.get('finish_reason'),bytes=len(content.encode()),generation_id=r.get('id'),file=filename)
 except Exception as e:d['error']=str(e)
 d['elapsed_seconds']=round(time.monotonic()-start,3);(OUT/(stem+'-expanded.json')).write_text(json.dumps(d,indent=2));print(stem,d['elapsed_seconds'],d.get('finish_reason'),flush=True);return d
with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(run,['01-golden-gate-canvas','04-colosseum-svg']))
(OUT/'expanded-summary.json').write_text(json.dumps({'max_tokens':128000,'results':results},indent=2))
