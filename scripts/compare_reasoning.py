"""Replay the ten saved monument prompts with xhigh reasoning in parallel."""
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from pathlib import Path
import time
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'experiments' / 'monuments-xhigh'
BASELINE = json.loads((ROOT / 'experiments/monuments/generation-summary.json').read_text())
CONFIG = dict(line.split('=', 1) for line in (ROOT / '.env').read_text().splitlines() if line and not line.startswith('#'))
EFFORT = 'xhigh'
MAX_TOKENS = 32000


def generate(previous):
    slug = previous['slug']
    target = OUT / (slug + '.json')
    if target.exists():
        raise RuntimeError(f'Refusing to overwrite saved generation: {target.name}')
    payload = {'model': CONFIG['OPENROUTER_MODEL'], 'messages': [{'role': 'user', 'content': previous['prompt']}], 'max_tokens': MAX_TOKENS, 'reasoning': {'effort': EFFORT}, 'usage': {'include': True}}
    request = urllib.request.Request(CONFIG['OPENROUTER_BASE_URL'].rstrip('/') + '/chat/completions', data=json.dumps(payload).encode(), headers={'Authorization': 'Bearer ' + CONFIG['OPENROUTER_API_KEY'], 'Content-Type': 'application/json'})
    metadata = {key: previous[key] for key in ['slug', 'name', 'approach', 'prompt']}
    metadata.update(requested_effort=EFFORT, max_tokens=MAX_TOKENS)
    started = time.monotonic()
    try:
        with urllib.request.urlopen(request, timeout=300) as response:
            result = json.load(response)
        if 'error' in result:
            raise RuntimeError(json.dumps(result['error']))
        choice = result['choices'][0]
        content = (choice['message'].get('content') or '').strip()
        if content.startswith('```'):
            content = content.split('\n', 1)[1].rsplit('```', 1)[0].strip()
        (OUT / (slug + '.html')).write_text(content)
        metadata.update(model=result.get('model'), provider=result.get('provider'), usage=result.get('usage'), finish_reason=choice.get('finish_reason'), bytes=len(content.encode()), generation_id=result.get('id'))
    except urllib.error.HTTPError as error:
        metadata['error'] = f'HTTP {error.code}: {error.read().decode()}'
    except Exception as error:
        metadata['error'] = str(error)
    metadata['elapsed_seconds'] = round(time.monotonic() - started, 3)
    target.write_text(json.dumps(metadata, indent=2))
    print(json.dumps({key: value for key, value in metadata.items() if key != 'prompt'}), flush=True)
    return metadata


if __name__ == '__main__':
    OUT.mkdir(exist_ok=True)
    start = time.monotonic()
    with ThreadPoolExecutor(max_workers=10) as pool:
        results = [future.result() for future in as_completed([pool.submit(generate, previous) for previous in BASELINE['results']])]
    summary = {'requested_effort': EFFORT, 'max_tokens': MAX_TOKENS, 'baseline_max_tokens': 11000, 'wall_seconds': round(time.monotonic()-start, 3), 'results': sorted(results, key=lambda item: item['slug'])}
    (OUT / 'generation-summary.json').write_text(json.dumps(summary, indent=2))
