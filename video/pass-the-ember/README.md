# Pass the Ember competition video

`Pass-the-Ember.mp4` is a 58-second 1920×1080 H.264/AAC video at 24fps. `Poster.png` is the opening title frame.

The edit uses the three actual game rounds recorded in `assets/live-rounds.json` and the corresponding browser capture. Each chapter shows a six-second compressed screen recording, a labeled replay of the exact submitted prompt, the generated drawing, and excerpts from each guesser's final explanation. The video retains incorrect guesses. The final progression is 2/3, 1/3, then 0/3 correct guesses.

The narration was generated locally with the macOS Samantha voice. No music is used. Full model explanations, prompts and game timings remain in the source JSON. The typing animation is a replay and the video labels it accordingly.

Editable composition lives in `studio/index.html`. `build.mjs` rebuilds it from the actual result JSON, and `encode-clips.py` compresses the recorded browser frames using their timestamps.

Rebuild with Node and FFmpeg installed:

```sh
python3 video/pass-the-ember/encode-clips.py
node video/pass-the-ember/build.mjs
HYPERFRAMES_BROWSER_PATH='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' npx --yes hyperframes@0.9.28 render video/pass-the-ember/studio --output video/pass-the-ember/Pass-the-Ember.mp4 --fps 24 --quality standard --workers 4
```

Final HyperFrames check passed. Its warnings concern intentionally accelerated prompt replay and small secondary labels. Opening, middle and closing frames were visually reviewed.
