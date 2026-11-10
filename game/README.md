# Pass the Ember

Run from the repository root:

```sh
npm --prefix game install
npm --prefix game run build
python3 game/server.py
```

Open http://127.0.0.1:8770. The server only listens on loopback.

## Prerequisites

- Python 3.9+, Node.js, Playwright and local Google Chrome. Install the game package dependencies; the renderer also recognizes the existing `/tmp/openrouter-draw-preview` Playwright installation. Set `CHROME_PATH` if Chrome is elsewhere.
- `codex` CLI logged into ChatGPT, with access to `gpt-6-luna` and `gpt-6.1-terra`.
- The existing project `.env` with `OPENROUTER_API_KEY`. Muse uses `meta/muse-ember`, Sonnet uses `anthropic/claude-sonnet-5.5`, and Haiku uses `anthropic/claude-haiku-5.5`. The browser receives no provider credential.
- The existing local Three.js modules in `experiments/california-levels`.

## Rules and controls

One player supplies the draw prompt in each round. Muse Ember checks that prompt and draws the image. Human describers get 60 seconds of editing time, paused while prompt checks and rendering run. They can revise the drawing and finish early; otherwise the latest usable image locks when editing time expires. Blocked revisions preserve the last usable drawing. The default contestants are Luna, Terra, Sonnet and Haiku. The host can select two to six AI or human seats and one to eight rounds. The default round count gives each player one turn as describer.

The private landmark pool covers California, Norway and Nepal. Four-round matches progress through difficulty tiers 1, 2, 3 and 4, and the first three rounds cover all three pools. A one-round quick match uses tier 1. A round begins with a private physical description from its assigned AI or human describer. Muse validates the clue, allowing visible recognizable features while blocking names, locations, coordinates, coded names and non-visual trivia. A human can revise a rejected description. AI descriptions receive up to two revisions.

Muse produces a Three.js scene with high effort and a 128,000-token output ceiling, then checks the screenshot for a visible, unobstructed subject. A failed execution or visibility check receives one new generation attempt with stronger camera instructions. Generated code remains private. The describer and spectators can see the current drawing during DRAW; guesses start only when the final version locks. The accepted PNG is the only input given to AI guessers, alongside the same generic pool-wide guessing prompt. The website’s drawing-prompt log is visible live, including rejected prompt text and Muse Ember’s reasons; this is useful for the hackathon demo but can reveal the answer to human viewers when a prompt names it.

Every other player submits one locked guess. The describer already knows the assignment and does not guess. Scoring compares each guess to the saved landmark name and curated aliases with Unicode-aware normalization. Muse judges only the draw prompt. Each correct guesser receives 2 points. The describer receives 2 points when at least one guess is correct. The host UI automatically reveals scores once every guess is locked; Next round advances explicitly. Ties share the win.

Stopping a match prevents dependent work. An in-flight provider call may finish and remain billable. Errors stop the round before scoring. Private tokens and match state persist under `game/data`. Restarting the server restores views without replaying calls automatically.

## API

- `GET /api/health`: configured/installed capability hints. These are not guarantees of account/model access.
- `GET /api/games/latest`: `{game: null | state}`.
- `POST /api/games` with `{"rounds":1,"players":[{"id":"luna","type":"human","name":"Alice"},{"id":"terra","type":"ai","name":"Terra"},{"id":"sonnet","type":"ai","name":"Sonnet"},{"id":"haiku","type":"ai","name":"Haiku"}]}` starts a match and returns `{game, hostToken, invitations}`. Omit players for the four-AI default. Extra human seats use `person-1` and `person-2`.
- Add `Authorization: Bearer <token>` on subsequent requests. The host token reveals human-seat invitation tokens and authorizes reveal, next and cancel. A seat token grants only that human seat its private assignment and input actions.
- Optional `customGoals` on match creation supplies up to one private goal per round. Blank entries use the landmark pool. Goals are limited to 120 characters.
- `POST /api/games/{id}/goal` with `{"goal":"..."}` lets the current human describer or host choose a private goal before the first description is submitted. Goal changes are locked once any description is submitted.
- `POST /api/games/{id}/clue` with `{"clue":"..."}` submits a human drawer description. Rejected clues return to the awaiting-clue state with feedback visible only to the drawer.
- `POST /api/games/{id}/finish-drawing` locks the latest usable drawing; only the host or current describer may do this.
- `POST /api/games/{id}/guess` with `{"guess":"..."}` locks one human guess. Public state exposes submission status, and answer text appears at reveal.
- `GET /api/games/{id}`: public state. Poll while running.
- `POST /api/games/{id}/reveal`, `/next`, `/cancel` with `{}`: explicit transitions.
- `GET /api/games/{id}/rounds/{number}/image`: PNG, available once a usable drawing exists, including during DRAW.

POST requests require JSON, a local Host header, and a matching Origin when present. No CORS is enabled. Private state and generated source are never served from the static directory. This runs locally and supports separate host and player views. The current loopback URL works on this computer; no public deployment has been made.

## Accounting and model isolation

OpenRouter actual response usage/cost and generation IDs are recorded. Codex input/output/cache counts are recorded, but its subscription debit is unavailable and shown as unknown. The Codex model name is the CLI's explicit selection; JSONL output does not independently return model identity. Codex turns run in fresh temporary directories with shell/apps/browser/computer-use tools disabled, provider secrets removed from their environment, and no prior turns. The renderer uses an independent temporary loopback origin serving only the generated document and two Three.js modules; other network requests are blocked. No hidden reasoning text is retained. AI guessers return a brief explanation of visible evidence with their answer; explanations appear only after SCORE.

## Checks

```sh
python3 -m unittest discover -s game -p 'test_game.py' -v
```

Offline tests cover pre-reveal redaction, independent image-only prompts, atomic scoring, duplicate transitions, clue revision, cancellation, restart behavior, strict matching, human seat authorization, private assignments, rejected clue resubmission, and waking human waits after cancellation or another player failure. Full live matches require the configured provider accounts and incur their ordinary usage.

## Competition demo

The lobby’s Competition demo runs three curated rounds: Painted Ladies (San Francisco, level 2), Borgund Stave Church (Norway, level 3), and Rani Mahal (Nepal, level 4). All guesses and explanations come from actual model calls. The 58-second competition video and source live-run evidence are under `video/pass-the-ember`.
