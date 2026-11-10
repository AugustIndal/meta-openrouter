"""Generate comparable SVG and Three.js drawings with Muse Ember."""
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'experiments' / 'golden-gate'
CONFIG = dict(line.split('=', 1) for line in (ROOT / '.env').read_text().splitlines() if line and not line.startswith('#'))
BRIEF = '''Draw the Golden Gate Bridge in San Francisco at golden hour, viewed from Battery Spencer in the Marin Headlands. Include recognizable International Orange towers with openings and cross-bracing, sweeping suspension cables and many vertical hangers, a road deck spanning the water, blue-green ocean, layered distant hills, warm sunset sky, and subtle low fog. Compose a beautiful detailed landscape at 1200 by 800. Prioritize recognizable bridge geometry, depth and polished visual composition. Do not include text labels. Use no external images, fonts, data, or assets.'''
FORMATS = {
    'svg': 'Return only a complete standalone SVG, no markdown fences. Set width="1200" height="800" viewBox="0 0 1200 800". Use SVG shapes, paths, gradients and filters. No scripts.',
    'three': '''Return only a complete HTML document, no markdown fences. Use Three.js to build a true 3D scene out of geometry, not a flat canvas drawing. Import * as THREE from './three.module.js' inside a module script. No other imports or external resources. Set up camera, scene, lights and WebGLRenderer. Render at 1200 by 800, fit the viewport responsively. Provide drag-to-orbit and wheel zoom using native pointer listeners if useful. Use a pleasing perspective camera with the entire bridge visible. Render immediately without animation delays, no randomness unless deterministic. Set window.sceneReady = true after the first rendered frame.''',
}

def generate(kind):
    prompt = BRIEF + '\n\n' + FORMATS[kind]
    payload = {'model': CONFIG['OPENROUTER_MODEL'], 'messages': [{'role': 'user', 'content': prompt}], 'max_tokens': 12000, 'reasoning': {'effort': 'medium'}, 'usage': {'include': True}}
    request = urllib.request.Request(CONFIG['OPENROUTER_BASE_URL'].rstrip('/') + '/chat/completions', data=json.dumps(payload).encode(), headers={'Authorization': 'Bearer ' + CONFIG['OPENROUTER_API_KEY'], 'Content-Type': 'application/json'})
    start = time.monotonic()
    with urllib.request.urlopen(request, timeout=240) as response:
        result = json.load(response)
    elapsed = round(time.monotonic() - start, 3)
    choice = result['choices'][0]
    content = choice['message']['content'].strip()
    if content.startswith('```'):
        content = content.split('\n', 1)[1].rsplit('```', 1)[0].strip()
    filename = 'bridge.svg' if kind == 'svg' else 'bridge-three.html'
    (OUTPUT / filename).write_text(content)
    metadata = {'format': kind, 'model': result.get('model'), 'provider': result.get('provider'), 'elapsed_seconds': elapsed, 'finish_reason': choice.get('finish_reason'), 'usage': result.get('usage'), 'prompt': prompt, 'file': filename}
    (OUTPUT / (kind + '-metadata.json')).write_text(json.dumps(metadata, indent=2))
    print(json.dumps(metadata), flush=True)

if __name__ == '__main__':
    with ThreadPoolExecutor(max_workers=2) as executor:
        list(executor.map(generate, FORMATS))
