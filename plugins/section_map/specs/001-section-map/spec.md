# Feature Specification: Section Map

**Plugin id**: `section_map` (`plugin.json:2`)
**Nav**: none — auto-injects on player
**Status**: Shipped (v1.0.0)

## Summary

A 20px-tall color-coded minimap pinned to the top of the player
showing every named section of the current song. Click to seek;
mouse-wheel scrubs ±1s (or ±0.1s with Ctrl). The active section
opacity-highlights as playback progresses.

## User Stories

### US-1 — Visual song structure overview
**As** a user practicing a song
**I want** to see every section labeled and color-coded at a glance
**So that** I know what part is coming up.

- **Given** a song is loaded and `highway.getSections()` returns
  non-empty data
- **When** the 200ms poller runs (`screen.js:181`) and detects the
  sections changed (`sections !== _smSections`, line 114)
- **Then** `_smRender()` builds one absolutely-positioned `<div>` per
  section, sized by `(nextTime - sec.time) / duration` percentage
  (`screen.js:142-158`).
- **And** colors are picked by substring match: intro=blue,
  verse=green, chorus=yellow, bridge=purple, solo=red,
  breakdown=orange, riff=cyan, pre=lime, noguitar=dark gray,
  outro=gray, default=mid gray (`SM_COLORS`).

### US-2 — Click to seek
**As** the same user
**I want** to click any section to jump there
**So that** I don't have to drag the seek bar.

- **Given** the section bar is visible and `_smDuration > 0`
- **When** the user clicks at x position
- **Then** `_smOnClick` (`screen.js:53-74`) computes
  `time = (clientX - rect.left) / rect.width * duration`,
  updates `lastAudioTime` (if defined),
  pauses (if playing), seeks `audio.currentTime`, and resumes on
  `seeked`.

### US-3 — Wheel-scrub
**As** a user fine-tuning a section start
**I want** to scroll the wheel to nudge time
**So that** I can dial it in without clicking.

- **Given** the user wheels over the section bar
- **When** `_smOnWheel` (`screen.js:76-101`) runs
- **Then** `deltaY < 0` advances time, `deltaY > 0` rewinds.
- **And** `Ctrl + wheel` switches granularity from 1s to 0.1s.
- **And** time is clamped to `[0, duration]`.

### US-4 — Live playhead and active section
**As** the same user
**I want** the active section highlighted and a playhead marker
**So that** my position is obvious.

- **Given** playback is progressing
- **When** the poller calls `_smUpdate` every 200ms
- **Then** `#sm-marker` is positioned at `(t/duration) * 100%`
  (`screen.js:121-124`).
- **And** all section blocks have `opacity: 0.5` except the active one
  at `opacity: 1` (`screen.js:127-135`).

### US-5 — Auto-show / auto-hide
**As** the same user
**I want** the bar to appear when I open a song and disappear when I
leave the player
**So that** I never see it on other screens.

- **Given** any song
- **When** `playSong(filename, arrangement)` runs (wrapped by us)
- **Then** the previous bar is removed, state cleared, original
  `playSong` awaited, then `_smCreate()` re-mounts the bar
  (`screen.js:184-191`).
- **And When** `showScreen(id)` runs with `id !== 'player'`
- **Then** `_smRemove()` is called before delegating
  (`screen.js:194-198`).

## Functional Requirements

- **FR-1** Single 200ms poller drives all updates (`setInterval(_smUpdate, 200)`).
- **FR-2** Bar mounted as `#section-map`, position absolute
  top:0/left:0/right:0, z-index:5, height 20px, semi-transparent
  background.
- **FR-3** Clickability and wheel-scrub require `_smDuration > 0`.
- **FR-4** Section name display strips trailing digits and
  Title-cases the first letter (`screen.js:151-152`).
- **FR-5** All side effects (poller + wrappers) installed under one
  idempotency guard.
- **FR-6** Pause-then-seek-then-resume pattern used in both click and
  wheel handlers to avoid unbuffered-region failures.

## Non-Functional Requirements

- **NFR-1** No blocking work; all logic runs synchronously in the
  poller tick or in the user-input handler.
- **NFR-2** No memory growth across song changes — `_smRemove()`
  detaches the DOM and `_smSections = []` resets state.

## Out of Scope

- Editing section boundaries [NEEDS CLARIFICATION: should the user
  be able to drag the boundaries of detected sections? Currently
  read-only].
- Saving custom section labels per user.
- Touch (long-press) gestures for mobile [NEEDS CLARIFICATION].

## Key Entities

- **Section**: `{ time: number, name: string }` from
  `highway.getSections()`. The plugin treats its identity as the
  array reference itself (`!==` change detection).
- **Bar**: a single DOM node owned by this plugin.
