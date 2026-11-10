# Muse Ember monument experiment

Ten API requests launched in parallel. Generation wall time 19.096s. Total API-reported cost $0.0395529. Median request 14.421s. 81,409 total tokens, including 40,721 reasoning tokens.

9/10 original scenes rendered and passed orbit, zoom and resize checks. Colosseum failed with a syntax error. The separately preserved repair substitutes `0xcdb18e` for `0xcdb astray||0xcdb18e`; it rendered and passed the same checks. No geometry was changed.

Scores are subjective: 40% recognizability, 30% visual finish, 20% framing and 10% working interaction. All initial screenshots were inspected. Subjects and prompt styles vary together, so this is an output comparison, not a controlled prompt benchmark.

| Rank | Monument | Prompt approach | Score | Time | Cost |
|---|---|---|---|---|---|
| 1 | Tower Bridge | Isometric precision | 8.1 | 13.59s | $0.0034428 |
| 2 | Elizabeth Tower / Big Ben | Night illumination | 7.7 | 14.37s | $0.0038262 |
| 3 | Taj Mahal | Symmetry and reflection | 7.4 | 9.87s | $0.0029449 |
| 4 | Eiffel Tower | Miniature diorama | 7.3 | 13.28s | $0.0037142 |
| 5 | Statue of Liberty | Faceted low-poly | 7.0 | 14.48s | $0.0040242 |
| 6 | Pyramids of Giza | Cinematic landscape | 6.9 | 16.98s | $0.0042541 |
| 7 | Golden Gate Bridge | Geometry-first | 6.8 | 15.08s | $0.0041103 |
| 8 | Christ the Redeemer | Clay maquette | 6.0 | 13.25s | $0.0036755 |
| 9 | Sydney Opera House | Paper sculpture | 5.3 | 16.98s | $0.0044638 |
| 10 | Colosseum | Architectural cutaway | 0.0 | 19.09s | $0.0050969 |

The repaired Colosseum scores 7.7/10, separately from its failed first attempt.

## Visual observations

- **Golden Gate Bridge** — Recognizable towers, deck and paired cables. The right approach is cropped and the sky occupies too much of the frame.
- **Eiffel Tower** — Strong lattice silhouette and a detailed miniature base. The spire and base are clipped; the lower structure is heavily cross-braced.
- **Taj Mahal** — Readable onion domes, four minarets and warm ivory palette. The garden and pool are cropped; the facade is simplified.
- **Colosseum** — Original fails to parse because of an invalid color expression. A separate one-line syntax repair reveals a detailed arena, but broad ring slabs bridge the intended broken wall.
- **Statue of Liberty** — Clear torch, crown, tablet and island. The figure is small and blocky, the torch resembles a cone, and the harbor reads as solid ground.
- **Sydney Opera House** — Clean ivory forms and terracotta podium, but the tall upright shells miss the broad interlocking Opera House silhouette. Background blocks distract.
- **Pyramids of Giza** — Convincing pyramid shapes and warm desert palette. The nearest pyramid is cropped, the third is mostly hidden and surface banding is visible.
- **Elizabeth Tower / Big Ben** — Readable clock faces and effective night lighting. Simplified Gothic detail, a very tall plain spire and almost no margin above its finial.
- **Christ the Redeemer** — The outstretched-arm silhouette reads, but the anatomy is doll-like, the robe has spiky folds and low contrast weakens the small figure.
- **Tower Bridge** — Strong isometric composition, paired towers, blue walkways and complete river crossing. Roofs and surrounding buildings are simplified.
