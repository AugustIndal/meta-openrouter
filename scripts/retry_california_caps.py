"""Retry the two truncated max-effort scenes with a larger response allowance."""
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import time
import urllib.request
from california_levels import CONFIG

OUT=Path(__file__).resolve().parents[1]/'experiments/california-levels'
SLUGS=['painted-ladies-max','griffith-max']

def retry(slug):
    original=json.loads((OUT/(slug+'.json')).read_text())
    target=slug+'-expanded'
    if (OUT/(target+'.json')).exists():
        raise RuntimeError('Expanded attempt already exists: '+target)
    payload={'model':CONFIG['OPENROUTER_MODEL'],'messages':[{'role':'user','content':original['prompt']}],'max_tokens':128000,'reasoning':{'effort':'max'},'usage':{'include':True}}
    request=urllib.request.Request(CONFIG['OPENROUTER_BASE_URL'].rstrip('/')+'/chat/completions',data=json.dumps(payload).encode(),headers={'Authorization':'Bearer '+CONFIG['OPENROUTER_API_KEY'],'Content-Type':'application/json'})
    started=time.monotonic()
    with urllib.request.urlopen(request,timeout=600) as response:
        result=json.load(response)
    choice=result['choices'][0]
    content=(choice['message'].get('content') or '').strip()
    if content.startswith('```'):content=content.split('\n',1)[1].rsplit('```',1)[0].strip()
    (OUT/(target+'.html')).write_text(content)
    metadata=dict(original,slug=target,max_tokens=128000,effort='max',attempt='expanded-cap',usage=result.get('usage'),finish_reason=choice.get('finish_reason'),generation_id=result.get('id'),elapsed_seconds=round(time.monotonic()-started,3),bytes=len(content.encode()))
    (OUT/(target+'.json')).write_text(json.dumps(metadata,indent=2))
    print(json.dumps({k:metadata[k] for k in ['slug','finish_reason','elapsed_seconds','bytes','usage']}),flush=True)
    return metadata

if __name__=='__main__':
    with ThreadPoolExecutor(max_workers=2) as pool:rows=list(pool.map(retry,SLUGS))
    (OUT/'expanded-cap-summary.json').write_text(json.dumps({'results':rows},indent=2))
