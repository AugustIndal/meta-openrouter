# California landmarks across six reasoning levels

36 original Three.js generations used only physical descriptions, with 6 locations × 6 effort levels and a shared 32,000-token response cap. Calls ran at concurrency 10. All prompts and outputs are saved.

| Effort | Rendered | Mean subjective score | Median sec | Generation cost (6) | Reasoning tokens | Clue matches |
|---|---:|---:|---:|---:|---:|---:|
| minimal | 6/6 | 4.58 | 6.23 | $0.01125 | 1,390 | 12/12 |
| low | 6/6 | 6.08 | 11.85 | $0.01883 | 9,767 | 12/12 |
| medium | 6/6 | 6.58 | 12.69 | $0.02703 | 27,460 | 12/12 |
| high | 6/6 | 7.58 | 18.66 | $0.03371 | 37,333 | 12/12 |
| xhigh | 6/6 | 7.83 | 32.3 | $0.05275 | 71,311 | 12/12 |
| max | 4/6 | 5.0 | 50.49 | $0.08250 | 136,761 | 12/12 |

Scores combine recognizable shape, description fidelity and composition, using one unblinded sample per cell. They are exploratory. Rendered means browser execution and controls worked; it does not guarantee the subject was visible. Griffith minimal scored1 because terrain obstructed the initial camera. Painted Ladies max consumed almost all 32k tokens in reasoning; Griffith max emitted truncated code. No originals were repaired.

Total generation cost $0.2260796; total clue-validation cost $0.0172677.

## Suggested game configuration

Use high for generating a live round and minimal for clue validation as a provisional latency/quality choice. Use xhigh when visual polish is more important than waiting time. These recommendations are based on this small set, not a production acceptance test.

Every effort matched all 12 expected clue decisions (6 physical descriptions, 6 forbidden direct/encoded/injection clues). Raw responses were checked for schema shape and known answer/alias leakage. This cannot establish general cheat resistance.

See GAME_DESIGN.md for proposed 45-second private description, validation, rendering, 45-second simultaneous guessing, reveal and scoring. The drawer earns 2 points if someone is correct; each correct guesser earns 2. The landmark name stays out of the generator context.


## Expanded-cap retries

The two capped max-effort cases were retried with the same prompts and a 128,000-token output ceiling. Both rendered successfully and passed orbit, zoom and resize checks. Painted Ladies used 30,790 completion tokens (23,569 reasoning), took 53.79s and cost $0.015421. Griffith used 29,695 completion tokens (22,744 reasoning), took 50.98s and cost $0.014874. Both original failures remain in the main comparison; retry links are available on their cards.

The retries actually finished below 32,000 tokens. This demonstrates successful new attempts, not that raising the ceiling alone caused success; generation length varies between attempts. The output cap includes reasoning and returned code. Expanded retries cost $0.030295, bringing California generation plus validation to $0.2736423.
