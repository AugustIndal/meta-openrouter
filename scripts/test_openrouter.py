"""Run one small OpenRouter request using the project's local .env."""
import json
import os
from pathlib import Path
import time
import urllib.error
import urllib.request

root = Path(__file__).resolve().parents[1]
for line in (root / '.env').read_text().splitlines():
    if line.strip() and not line.lstrip().startswith('#'):
        name, value = line.split('=', 1)
        os.environ.setdefault(name.strip(), value.strip())

base = os.environ.get('OPENROUTER_BASE_URL', 'https://openrouter.ai/api/v1').rstrip('/')
payload = {
    'model': os.environ.get('OPENROUTER_MODEL', 'meta/muse-ember'),
    'messages': [{'role': 'user', 'content': 'hi world'}],
    'max_tokens': 128,
    'reasoning': {'effort': 'minimal'},
    'usage': {'include': True},
}
request = urllib.request.Request(
    base + '/chat/completions',
    data=json.dumps(payload).encode(),
    headers={'Authorization': 'Bearer ' + os.environ['OPENROUTER_API_KEY'],
             'Content-Type': 'application/json'},
)
start = time.monotonic()
try:
    with urllib.request.urlopen(request, timeout=90) as response:
        result = json.load(response)
except urllib.error.HTTPError as exc:
    raise SystemExit(f'OpenRouter HTTP {exc.code}: {exc.read().decode()}') from None
print(json.dumps({
    'id': result.get('id'),
    'model': result.get('model'),
    'provider': result.get('provider'),
    'prompt': 'hi world',
    'reply': result['choices'][0]['message'].get('content'),
    'finish_reason': result['choices'][0].get('finish_reason'),
    'elapsed_seconds': round(time.monotonic() - start, 3),
    'usage': result.get('usage'),
}, indent=2))
