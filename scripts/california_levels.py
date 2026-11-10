"""Compare six reasoning levels on six description-only California locations."""
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from pathlib import Path
import time
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'experiments/california-levels'
CONFIG = dict(line.split('=', 1) for line in (ROOT / '.env').read_text().splitlines() if line and not line.startswith('#'))
LEVELS = ['minimal', 'low', 'medium', 'high', 'xhigh', 'max']
LOCATIONS = [
 {'id':'golden-gate','name':'Golden Gate Bridge','region':'San Francisco','description':'A long vermilion suspension bridge crossing a wide ocean strait. Two tall rectangular steel towers have large openings and cross-braces. A straight road deck hangs from two sweeping main cables and many thin vertical hangers. Rocky green headlands sit at the ends, with cool blue water below and a little coastal haze.'},
 {'id':'painted-ladies','name':'Painted Ladies','region':'San Francisco','description':'A row of seven narrow ornate Victorian houses on a sloping city street. Each house has a different pastel color, steep gabled roof, tall bay windows, front steps and elaborate white wood trim. A grassy hillside is in the foreground. A distant cluster of modern high-rise buildings rises behind the rooftops.'},
 {'id':'transamerica','name':'Transamerica Pyramid','region':'San Francisco','description':'A very tall pale stone office tower shaped like a slender four-sided pyramid with a pointed spire. Dense horizontal rows of dark windows cover its tapering faces. Two narrow vertical fins project from opposite upper sides. Exposed triangular supports form a broad base, surrounded by much shorter city blocks and small trees.'},
 {'id':'griffith','name':'Griffith Observatory','region':'Los Angeles','description':'A symmetrical pale cream observatory on a green-brown hill above a city. It has one large central dark copper dome and two smaller matching domes on the left and right wings. A broad terrace, balustrades and wide steps face the viewer. The building has low geometric walls and a small obelisk-like monument on the front lawn.'},
 {'id':'half-dome','name':'Half Dome','region':'Yosemite','description':'A monumental pale granite mountain shaped like a dome sliced vertically in half. One face is a huge sheer smooth cliff, while the back is a rounded sloping shoulder. Dark vertical weathering streaks mark the rock. Smaller granite ridges and a forest of tiny evergreen trees surround it, beneath clear blue mountain sky.'},
 {'id':'santa-monica','name':'Santa Monica Pier','region':'Santa Monica','description':'A wooden amusement pier extending from a broad sandy beach into the blue ocean. A large colorful Ferris wheel rises above the pier near a compact roller coaster with bright yellow track and blue supports. Include simple low buildings, railings, timber support piles, foamy waves, and a few palm trees near the shore. There are no written signs.'},
]
CONTRACT = '''Create a polished 3D illustration solely from this visual description. The private location name is deliberately withheld. Return only a complete HTML document without Markdown fences. Use real procedural Three.js geometry, import * as THREE from './three.module.js', and use no other imports or external assets, images, fonts, network calls or text labels. Do not put any landmark name or place name in the HTML title or visible scene. Use deterministic geometry. Render initially at 1200x800, responsive to window resizing, with device pixel ratio at most 1.5. Include native pointer drag orbit and wheel zoom; update projection, size and rendered frame on resize. Frame the whole subject with generous margins around top, sides and base. Use attractive coherent lighting and clear recognizable silhouettes. Render immediately and set window.sceneReady=true after the first rendered frame. Keep geometry efficient; avoid a continuous animation loop. No transparent flat fog planes.'''


def request_generation(location, level):
    slug = location['id'] + '-' + level
    target = OUT / (slug + '.json')
    if target.exists():
        raise RuntimeError('Refusing to replace existing result ' + slug)
    prompt = location['description'] + '\n\n' + CONTRACT
    payload = {'model': CONFIG['OPENROUTER_MODEL'], 'messages':[{'role':'user','content':prompt}], 'max_tokens':32000, 'reasoning':{'effort':level}, 'usage':{'include':True}}
    request = urllib.request.Request(CONFIG['OPENROUTER_BASE_URL'].rstrip('/')+'/chat/completions',data=json.dumps(payload).encode(),headers={'Authorization':'Bearer '+CONFIG['OPENROUTER_API_KEY'],'Content-Type':'application/json'})
    metadata = dict(location, slug=slug, effort=level, prompt=prompt, max_tokens=32000)
    started = time.monotonic()
    try:
        with urllib.request.urlopen(request,timeout=300) as response:
            result=json.load(response)
        if 'error' in result:
            raise RuntimeError(json.dumps(result['error']))
        choice=result['choices'][0]
        content=(choice['message'].get('content') or '').strip()
        if content.startswith('```'):
            content=content.split('\n',1)[1].rsplit('```',1)[0].strip()
        (OUT/(slug+'.html')).write_text(content)
        metadata.update(model=result.get('model'),provider=result.get('provider'),usage=result.get('usage'),finish_reason=choice.get('finish_reason'),bytes=len(content.encode()),generation_id=result.get('id'))
    except urllib.error.HTTPError as error:
        metadata['error']=f'HTTP {error.code}: {error.read().decode()}'
    except Exception as error:
        metadata['error']=str(error)
    metadata['elapsed_seconds']=round(time.monotonic()-started,3)
    target.write_text(json.dumps(metadata,indent=2))
    usage=metadata.get('usage',{})
    print(json.dumps({'slug':slug,'seconds':metadata['elapsed_seconds'],'cost':usage.get('cost'),'reasoning_tokens':usage.get('completion_tokens_details',{}).get('reasoning_tokens'),'finish_reason':metadata.get('finish_reason'),'error':metadata.get('error')}),flush=True)
    return metadata


if __name__=='__main__':
    started=time.monotonic()
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures=[executor.submit(request_generation, location, level) for location in LOCATIONS for level in LEVELS]
        rows=[future.result() for future in as_completed(futures)]
    summary={'levels':LEVELS,'locations':LOCATIONS,'max_concurrency':10,'max_tokens':32000,'wall_seconds':round(time.monotonic()-started,3),'results':sorted(rows,key=lambda row:(row['id'],LEVELS.index(row['effort'])))}
    (OUT/'generation-summary.json').write_text(json.dumps(summary,indent=2))
