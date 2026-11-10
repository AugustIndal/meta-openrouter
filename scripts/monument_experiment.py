"""Ten parallel Muse Ember monument generations with distinct art directions."""
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from pathlib import Path
import time
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'experiments' / 'monuments'
CONFIG = dict(line.split('=', 1) for line in (ROOT / '.env').read_text().splitlines() if line and not line.startswith('#'))
CASES = [
('01-golden-gate', 'Golden Gate Bridge', 'Geometry-first', 'Build the Golden Gate Bridge with accurate structural hierarchy: two International Orange open-frame towers, a continuous road deck, paired sagging main cables and evenly spaced vertical hangers attached at both ends. Use a wide three-quarter viewpoint, cool ocean, distant hills and warm afternoon sun. Prioritize structural correctness over decoration.'),
('02-eiffel', 'Eiffel Tower', 'Miniature diorama', 'Create a collectible miniature diorama of the Eiffel Tower on a circular landscaped base. Emphasize four splayed lattice legs, the wide arch at the base, two observation platforms and a tapering open lattice spire. Tiny paths and trees establish scale. Refined warm brass and iron materials, soft studio lighting, lovely three-quarter composition.'),
('03-taj-mahal', 'Taj Mahal', 'Symmetry and reflection', 'Render the Taj Mahal as a serene architectural scene: central ivory onion dome with finial above a symmetrical building with a tall central pointed portal, smaller domed kiosks and four slender corner minarets. A long foreground reflecting pool and flanking formal gardens guide the eye to the facade. Symmetry, soft dawn light, pale pink sky, polished proportions.'),
('04-colosseum', 'Colosseum', 'Architectural cutaway', 'Build a recognizable Colosseum as a detailed architectural cutaway: elliptical amphitheater, three stacked rings of repeated open arches, a partially broken upper wall and visible stepped seating surrounding the exposed arena. Warm travertine stone, sparse Roman ground context, elevated three-quarter view. Make openings genuine empty spaces between columns and arch segments.'),
('05-liberty', 'Statue of Liberty', 'Faceted low-poly', 'Create a refined low-poly Statue of Liberty: oxidized copper robed standing figure on a stepped stone pedestal, seven-point crown, right arm raised high with a gold flame torch, left arm holding a tablet. Build a readable human silhouette with deliberate geometry, distinguish arms and head, include the star-shaped island foundation and blue harbor. Strong side lighting.'),
('06-opera-house', 'Sydney Opera House', 'Paper sculpture', 'Create a sculptural paper-craft Sydney Opera House beside a deep blue harbor. Arrange multiple groups of overlapping tall pointed white sail-shell roofs of different sizes on a terracotta podium, each shell curved and sharply peaked. Show the interleaved roof silhouette from a three-quarter harbor viewpoint. Crisp ivory material, soft ambient shadows, restrained surrounding details.'),
('07-pyramids', 'Pyramids of Giza', 'Cinematic landscape', 'Create a cinematic desert scene featuring the three Pyramids of Giza at distinct realistic relative scales. Use square-based pyramids with clean triangular faces and subtle horizontal stone courses, sandy ground with gentle dune variation, low warm sun, long soft shadows and atmospheric depth. The great pyramid is the focal point. Elegant restrained composition from a low elevated camera.'),
('08-big-ben', 'Elizabeth Tower / Big Ben', 'Night illumination', 'Create a recognizable Elizabeth Tower (Big Ben) at blue hour. Model the tall square tan Gothic clock tower, large luminous round clock faces on all four sides, decorative vertical buttresses, belfry and steep dark pyramidal spire with finial. Add a modest Westminster wing, warm ground lights and dark blue sky. The clock hands and hour marks should be clearly visible.'),
('09-christ', 'Christ the Redeemer', 'Clay maquette', 'Sculpt Christ the Redeemer as a sophisticated monochrome clay architectural maquette on Corcovado mountain. A readable robed human figure stands upright with both arms fully outstretched horizontally, a small defined head, hands and flowing vertical robe folds, on its pedestal. Use soft off-white clay for statue, muted green-gray mountain layers, museum lighting and a clear frontal three-quarter camera.'),
('10-tower-bridge', 'Tower Bridge', 'Isometric precision', 'Create a precise isometric-style Tower Bridge scene over the Thames: two matching stone Gothic towers capped by blue-gray pointed roofs, two high-level walkways joining the towers, a lower road deck with the two bascule leaves closed, blue suspension elements extending toward both shores. Include tower arches, warm stone masonry hints and calm water. Use an orthographic camera and clean detailed miniature style.'),
]
CONTRACT = '''Return only a complete HTML document, without Markdown fences. Build actual 3D geometry with Three.js 0.180.0. Import * as THREE from './three.module.js'; use no other imports, external assets, images, fonts, network calls or textures. Use procedural geometry and materials. Render into a responsive full-window canvas, initially 1200x800. Set renderer pixel ratio to at most 1.5. Build native pointer drag orbit and wheel zoom controls. On resize update renderer size, camera projection and rerender. Use a carefully framed default camera with the whole monument and its top and base visible, at least 10% margin around it. Avoid obstructing the landmark with foreground objects. Use deterministic geometry. Render the finished scene immediately, then set window.sceneReady=true. No text overlays. Prioritize the visual result and working code. Keep geometry efficient. Use no animation loop unless needed for a specific effect. Avoid transparent flat fog planes. Use no more than 9000 output tokens including reasoning.'''

def generate(case):
    slug, name, approach, brief = case
    prompt = brief + '\n\n' + CONTRACT
    request = urllib.request.Request(CONFIG['OPENROUTER_BASE_URL'].rstrip('/') + '/chat/completions', data=json.dumps({'model': CONFIG['OPENROUTER_MODEL'], 'messages': [{'role': 'user', 'content': prompt}], 'max_tokens': 11000, 'reasoning': {'effort': 'medium'}, 'usage': {'include': True}}).encode(), headers={'Authorization': 'Bearer ' + CONFIG['OPENROUTER_API_KEY'], 'Content-Type': 'application/json'})
    started = time.monotonic()
    metadata = {'slug': slug, 'name': name, 'approach': approach, 'prompt': prompt}
    try:
        with urllib.request.urlopen(request, timeout=240) as response:
            result = json.load(response)
        choice = result['choices'][0]
        content = choice['message']['content'].strip()
        if content.startswith('```'):
            content = content.split('\n', 1)[1].rsplit('```', 1)[0].strip()
        (OUT / (slug + '.html')).write_text(content)
        metadata.update(model=result.get('model'), provider=result.get('provider'), usage=result.get('usage'), finish_reason=choice.get('finish_reason'), bytes=len(content.encode()))
    except Exception as error:
        metadata['error'] = str(error)
    metadata['elapsed_seconds'] = round(time.monotonic() - started, 3)
    (OUT / (slug + '.json')).write_text(json.dumps(metadata, indent=2))
    print(json.dumps({key: value for key, value in metadata.items() if key != 'prompt'}), flush=True)
    return metadata

if __name__ == '__main__':
    start = time.monotonic()
    with ThreadPoolExecutor(max_workers=10) as pool:
        results = [future.result() for future in as_completed([pool.submit(generate, case) for case in CASES])]
    (OUT / 'generation-summary.json').write_text(json.dumps({'wall_seconds': round(time.monotonic()-start, 3), 'results': sorted(results, key=lambda item: item['slug'])}, indent=2))
