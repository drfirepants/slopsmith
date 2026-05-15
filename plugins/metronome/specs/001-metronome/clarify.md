# Clarifications — Metronome Plugin

Retrospective Q&A reconstructed from `screen.js` and `README.md`.

## Q1. Are settings (volume, flash) persisted across browser reloads?

**A.** No, despite the README's "zero setup" framing. `_metSettings`
is held on `window[MET_SETTINGS_KEY]`, which survives plugin re-eval
in the same tab but is wiped on full page reload. There is no
`localStorage.setItem` in `screen.js`. **Drift item**: README implies
defaults persist, but only the runtime defaults do.

## Q2. Why poll at 60 Hz instead of using `requestAnimationFrame` directly?

**A.** A `setInterval(..., 1000/60)` keeps the plugin decoupled from
the highway render lifecycle. `addDrawHook` is used for the visual
flash (which is rendered each frame), but click scheduling has to run
even when the highway tab is backgrounded so audio doesn't drift.
`setInterval` continues firing in background tabs (throttled, but
present), `requestAnimationFrame` does not.

## Q3. What happens on a song with no beat map?

**A.** `_metTick` early-returns when `beats` is `null` or empty.
Slopsmith arrangements without beat data simply produce no clicks; the
button still toggles, the slider still moves.

## Q4. What's the 50 ms tolerance for?

**A.** `Math.abs(t - beatTime) > 0.05` filters out beats the plugin
"missed" because the user seeked past them. Without this, every seek
would fire a burst of clicks for every skipped beat. The tradeoff: if
the renderer lags >50 ms behind real time on one tick, that beat is
silently dropped. Acceptable on a 60 Hz poller — a single dropped beat
is less obnoxious than a burst on every seek.

## Q5. Why is there a `playSong` monkey-patch?

**A.** Two reasons: (1) reset `_metState.lastBeatIdx` to `-1` so
loading a new song doesn't think the playhead has retreated, and (2)
re-inject the toggle button into player controls in case the controls
are torn down between songs. The wrapper is idempotent via
`PLAY_SONG_WRAPPED_TAG` so reloads don't stack wrappers.

## Q6. Why is the click a sine and not a samples-based "click"?

**A.** Zero-cost. A sample-based click would need a network round-trip
to load (or be inlined as base64, bloating `screen.js`). A sine
oscillator is one-line WebAudio and indistinguishable from a sample
metronome at this duration (60 ms).

## Q7. Why does the draw hook flash only the bottom 18 % of the canvas?

**A.** That band is where the play-line / now-line lives. Flashing the
whole canvas is too distracting and competes with the highway's own
visual language. The narrow band is enough to register peripherally
without overwhelming the chart.
