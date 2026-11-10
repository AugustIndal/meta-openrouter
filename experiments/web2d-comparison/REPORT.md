# Native Canvas and SVG monument comparison

## Findings

The same ten scene briefs produce attractive 2D illustrations with stronger surface detailing and atmosphere than many saved Three.js defaults. The advantage varies by subject. Three.js gives real spatial structure and interactive orbiting, while the native 2D outputs often flatten the requested three-quarter or isometric composition. The Three.js Eiffel Tower, Colosseum and Big Ben remain strong. Canvas and SVG work especially well for Taj Mahal facades, desert lighting and stylized human silhouettes.

All 20 first-pass outputs were opened in local Chrome and visually inspected as full 1200×800 screenshots and two five-row contact sheets. Seventeen rendered cleanly. Golden Gate Canvas returned no visible content at the 32k completion limit. Colosseum SVG hit that limit and returned truncated XML with a browser error banner. Opera House Canvas stopped during drawing with `ReferenceError: baseY864 is not defined`.

The two cap-limited cases were generated again with a 128,000-token API ceiling, preserving the same prompts and xhigh effort. Both new outputs completed and rendered cleanly. They consumed 15,665 and 30,819 completion tokens respectively, so this pair alone does not establish that a larger ceiling caused the successful reruns. They are separate samples. The original prompt's prose still requests at most 32,000 tokens. The Opera House was separately repaired by replacing the invalid identifier `baseY864` with `baseY`. That one-token local repair completes the shell drawing and incurs no inference cost. Originals remain untouched.

## Subjective scores

Scores assess the default image's recognizability, requested structure, composition, detailing and finish on a 0–10 scale. They include visible failures and are a single reviewer's judgments. They do not measure general model capability or interactive 3D behavior.

| Format | First-pass mean | Mean generation | Ten-call API cost |
| --- | ---: | ---: | ---: |
| Three.js saved baseline | 7.25 | 25.49s | $0.06781940 |
| Native Canvas | 6.50 | 39.42s | $0.09905640 |
| Standalone SVG | 7.00 | 34.74s | $0.09246840 |

Separate follow-up scores are Golden Gate Canvas expanded 7.5, Colosseum SVG expanded 8.0, and Opera House Canvas repaired 6.5. Substituting those reviewed variants would yield Canvas 7.70 and SVG 7.60. Those are selected follow-up scores and must not replace the first-pass results.

## Cost and token accounting

The original 20 calls cost $0.19152480 as reported by OpenRouter, with 5-way maximum concurrency and 177.383 seconds total generation wall time. Canvas used 2,639 prompt tokens, 197,585 completion tokens, of which 149,197 were reported reasoning tokens. SVG used 2,739 prompt tokens, 184,389 completion tokens, of which 130,524 were reported reasoning tokens. Completion totals include reasoning. This first-pass batch reported zero cache-read and cache-write tokens.

The two expanded-cap calls cost another $0.02327232. Golden Gate Canvas cost $0.00783582 and took 30.601 seconds, with 254 prompt tokens, 230 cached prompt tokens, 15,665 completion tokens and 10,312 reasoning tokens. Colosseum SVG cost $0.01543650 and took 59.875 seconds, with 270 prompt tokens, zero cached tokens, 30,819 completion tokens and 24,732 reasoning tokens. Total new inference cost is $0.21479712. These are API-reported costs, not independently reconciled billing.

## Controls and limitations

- Actual returned model was `meta/muse-ember`, provider Meta, with requested xhigh reasoning for every call. Every exact prompt and usage record is saved alongside its source. No private key or hidden reasoning payload is retained.
- Each scene brief is byte-for-byte identical to the text before `\n\nReturn only` in the saved original ten-monument baseline. Representation instructions necessarily differ. Both 2D formats require native paths/shapes/gradients, 1200×800 framing, complete monuments and no external assets. Canvas is complete responsive HTML with `window.sceneReady`; SVG is a standalone document without scripts.
- The baseline and first-pass 2D calls share a 32,000-token API ceiling. The old Three.js prompt additionally asks for 9,000 tokens in prose. New first-pass 2D prompts ask for 32,000. This is an exploratory comparison with that prompt difference. The baseline ran with ten concurrent calls in a separate batch, so generation-time differences are descriptive rather than controlled speed measurements.
- Native Canvas and standalone SVG were empirically tested. Paper.js, Fabric.js, D3 and server-side/headless Canvas were not tested as drawing frameworks. Chrome was headless only for screenshot automation.
- Outgoing page requests were restricted to the local experiment server. No blocked requests appeared. SVG XML validity was checked separately because an XML-error page can still contain a partial `svg` node.
- Scores use the fixed original views and existing baseline screenshots. No claim of photographic fidelity, geometric accuracy or general benchmark performance is made. One sample per original subject and format limits inference.

## Artifacts

Open `index.html` at http://127.0.0.1:8769/ for source-linked side-by-side previews. `contact-sheet.png` contains all original comparisons; `contact-sheet-1.png` and `contact-sheet-2.png` provide larger five-row views. `variants-contact-sheet.png` contains the two expanded samples and repaired Opera House. `generation-summary.json`, `expanded-summary.json`, `render-results.json`, `variant-render-results.json` and `scores.json` preserve the evidence. Baseline sources and their Three.js modules are copied into `baseline/` for self-contained viewing.
