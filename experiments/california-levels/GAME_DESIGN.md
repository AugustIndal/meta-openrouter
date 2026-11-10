# California Landmark Drawing Game — Proposed Design

**Status:** Concept proposal for discussion. This describes a small playable MVP; it is not an implementation or a claim that multiplayer support exists.

## Game loop

One player, the **drawer**, privately receives a California landmark. They describe what it physically looks like to Muse Ember, which creates a Three.js scene. Everyone else submits a guess without seeing the answer. The group scores, reveals the landmark, and rotates the drawer.

### Round stages

1. **Assign (private):** Select a landmark and give its canonical name and accepted aliases only to the drawer and the trusted game service that validates guesses. Do not show it to guessers.
2. **Describe (45 seconds):** The drawer gives Muse Ember a description. They may describe visible physical traits, including shape, size, material, color, silhouette, structure, and the arrangement of parts. A recognizable physical description is allowed—even if it makes the answer easy to guess.
3. **Render:** Freeze the approved description and generate the image. The image-generation request receives only that description and neutral rendering instructions, never the target name or other answer-bearing context. Show the resulting scene to guessers.
4. **Guess (45 seconds):** Guessers privately submit one answer each. Guesses stay hidden until the timer ends; then reveal the guesses together. This prevents speaking order and loudness from determining who gets credit.
5. **Reveal and score:** Reveal the landmark and award points. Start the next round with a new drawer and target.

## Clue and answer rules

The drawer describes the scene, not the answer’s name. Do not say or type the landmark’s name or alias; initials or acronyms; coordinates or street addresses; spelling, letter, or wordplay clues; phonetic clues; or another verbal encoding of the answer. Neutral physical traits remain valid even when distinctive. Geography or nearby landmarks should be allowed only if the group explicitly chooses to permit them; for the MVP, ask drawers to focus on what the scene itself looks like.

The game cannot guarantee that a description contains no indirect hint or that a rendering will not make the landmark obvious. Treat the forbidden list as a clear norm, not a promise of perfect automated policing. A host can review a disputed clue or guess and override an ambiguous automated decision.

## Scoring

- Each guesser whose submitted answer matches the target earns **2 points**. Multiple correct guessers can all earn points.
- The drawer earns **2 points if at least one guess is correct**, and **0 if none are correct**. This avoids giving the drawer a reward for making the landmark obscure.
- No penalty is assessed for how closely the generated scene resembles the target; the drawer is scored on whether the group can identify the intended landmark.

Use a curated answer list with a canonical name and accepted aliases for each target. Normalize capitalization, whitespace, punctuation, and diacritics before comparison. Keep the target and alias list on the trusted game-service side; do not send them to public clients. If a guess is plausibly equivalent but not covered by the alias list, defer to a host override rather than silently accepting an uncertain model judgment.

## Rendering failure

If rendering is broken or unusable, the host may request **one retry** with the same approved description. The retry does not change the timer outcome or score. If it also fails, skip the round without awarding points and continue. Do not let retries become a way to probe for the hidden target.

## State and information boundaries

Suggested round phases are `assignment → describing → rendering → guessing → reveal → complete`. The trusted game service owns the current target, its aliases, phase, and score validation. A drawer client receives the target privately; guesser clients receive only public phase/timer updates and the rendered scene. Guess submissions are associated with a player and checked server-side against the current target, but other players do not see submissions before reveal.

The image generator receives only the approved description, style/render settings, and needed technical context. It must not receive the target name, aliases, guess list, API key, or private answer-bearing reasoning. Keep credentials server-side. Public clients should not receive the target, alias list, answer-validation rationale, or other secret fields in round state or errors.

## MVP format and fairness

**Recommendation:** start with one shared-screen pass-and-play prototype for a small group. It has the least joining and synchronization work, but requires a private drawer handoff and care that the target is not visible to guessers. Have every guesser submit privately on their own turn or slip of paper, then reveal together. Avoid spoken first-to-answer scoring.

Move to multi-device play when private assignment and simultaneous guesses are central to the experience. It improves secrecy and makes locking guesses natural, but adds room joining, network coordination, and device-state failure modes. The rules and server-side answer boundary should remain the same in either format.

## Concrete next steps for an MVP

1. Curate a small, varied California landmark set with canonical names and reviewed aliases.
2. Prototype one round with private target handoff, a 45-second description phase, one generated scene, a 45-second anonymous guess window, and the scoring above.
3. Add the single host-controlled rendering retry and manual overrides for ambiguous guesses or disputed clues.
4. Run a short play session to learn whether physical descriptions are satisfying, the timers fit, and the no-name rule feels understandable before expanding the landmark pool or adding multi-device play.

## Open choices

- Should the MVP stay pass-and-play, or is private multi-device guessing a launch requirement?
- Should geographic context remain out of bounds, or may drawers mention a city or neighborhood?
- Who acts as host and decides ambiguous clue/guess disputes in a small group?

## Public image delivery

For the first version, render Three.js privately and send only the resulting PNG to guessers. Raw generated HTML can contain an answer-like phrase in comments, variable names or the page title even when the input withheld the answer. One of the current scenes contains “half dome” in a geometry comment. Keep the editable or orbitable scene on the drawer/host side, and publish pixels with an opaque round ID.

## Optional hard mode

If direct physical descriptions make rounds too easy, give each assignment two or three curated taboo descriptors in addition to its forbidden names. For example, a bridge round could prohibit the words “orange” and “suspension” while permitting descriptions of the towers, roadway and hanging lines. The validator can check these explicit restrictions. Do not ask it to decide an undefined level of obviousness. Taboo lists and their difficulty still need human playtesting.
