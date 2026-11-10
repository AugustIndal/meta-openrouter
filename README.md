# Pass the Ember

A local multiplayer game with people and AI. Default contestants: **Luna, Terra, Sonnet and Haiku**. Muse always draws and checks the one prompt submitted per round. Everyone else guesses from the image. The UI moves through **DRAW → GUESS → SCORE**, followed by **Next round**. A 24-place pool spans California, Norway and Nepal with four increasing difficulty tiers.

```sh
npm --prefix game install
npm --prefix game run build
python3 game/server.py
```

Open **http://127.0.0.1:8770/**. The game uses this project's `.env` for Muse, Sonnet and Haiku via OpenRouter, plus the existing Codex login for Luna and Terra. People join from private seat links. No key is sent to the browser. See [game/README.md](game/README.md) for setup, rules, model isolation and cost accounting.

For frontend development, run `npm --prefix game run dev` alongside the Python server. The backend remains on port 8770.

## Earlier experiments

- [California reasoning levels](experiments/california-levels/REPORT.md)
- [Canvas vs SVG vs Three.js](experiments/web2d-comparison/REPORT.md)
- [Proposed game rules](experiments/california-levels/GAME_DESIGN.md)

All saved experiments are preserved. Runtime matches are private local files under `game/data/`, excluded from Git.
