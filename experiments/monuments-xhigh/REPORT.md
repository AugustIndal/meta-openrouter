# Medium versus xhigh reasoning

Identical saved prompts, one sample per effort per monument. Same model and provider, no reference images or repairs to xhigh outputs. Response cap increased from 11,000 to 32,000 tokens; all generations in both rounds ended with stop. Scores are subjective, using 40% recognizability, 30% visual finish, 20% framing and 10% working interaction. These paired samples suggest differences but do not establish statistical significance or isolate effort from the larger token cap.

| Metric | Medium | Xhigh |
|---|---:|---:|
| cost_usd | 0.0395529 | 0.0678194 |
| wall_seconds | 19.096 | 33.336 |
| median_request_seconds | 14.4215 | 25.929499999999997 |
| reasoning_tokens | 40721 | 95028 |
| total_tokens | 81409 | 137942 |
| mean_score | 6.25 | 7.39 |
| render_successes | 9 | 10 |

| Monument | Medium | Xhigh | Delta |
|---|---:|---:|---:|
| Golden Gate Bridge | 6.8 | 7.1 | +0.3 |
| Eiffel Tower | 7.3 | 8.3 | +1.0 |
| Taj Mahal | 7.4 | 7.1 | -0.3 |
| Colosseum | 0.0 | 7.9 | +7.9 |
| Statue of Liberty | 7.0 | 7.4 | +0.4 |
| Sydney Opera House | 5.3 | 5.2 | -0.1 |
| Pyramids of Giza | 6.9 | 7.9 | +1.0 |
| Elizabeth Tower / Big Ben | 7.7 | 8.1 | +0.4 |
| Christ the Redeemer | 6.0 | 6.3 | +0.3 |
| Tower Bridge | 8.1 | 8.6 | +0.5 |

Medium Colosseum received 0 because the original failed to parse. Its one-line repaired variant previously scored 7.7. All ten xhigh outputs render without repairs and pass orbit, zoom and resize checks.

- **Golden Gate Bridge** — The whole bridge fits and cables attach more coherently. The span is compressed, towers are broad and side approaches are simplified.
- **Eiffel Tower** — The open base arches and dense lattice improve the silhouette. The spire fits, though the circular base still touches the lower edge.
- **Taj Mahal** — The front portal is stronger, but the oversized central dome and narrow facade weaken proportions. The garden remains cropped.
- **Colosseum** — Renders on the first attempt with repeated open arches and clear stepped seating. The camera is close and the ruin treatment is simplified.
- **Statue of Liberty** — Larger figure, clearer flame and blue harbor improve readability. The anatomy and tablet position are still blocky, with the island close to the frame edge.
- **Sydney Opera House** — Cleaner background and framing, but the roofs look like upright cones. The landmark silhouette is less convincing than medium.
- **Pyramids of Giza** — All three pyramids fit and the scene has clear depth. It is sparse, with sharp shadows and limited stone detail.
- **Elizabeth Tower / Big Ben** — Stronger golden illumination, readable clocks and more detail. The full spire fits, although some building proportions are simplified.
- **Christ the Redeemer** — Smoother robe and a clearer arm silhouette improve the figure slightly. The head remains doll-like and contrast is low.
- **Tower Bridge** — Complete diorama fits comfortably with richer tower detail and clear blue structural elements. Some suspension geometry is schematic.
