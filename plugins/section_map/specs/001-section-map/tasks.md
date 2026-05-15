# Tasks — Section Map

## US-1: Section bar render

- [x] **DONE** Color palette (`SM_COLORS`).
- [x] **DONE** Substring-match color picker (`_smGetColor`).
- [x] **DONE** Per-section absolutely-positioned blocks
  (`_smRender`).
- [x] **DONE** Tooltip with section name + start time.
- [x] **DONE** Title-case + trailing-digit stripping for labels
  (`screen.js:151-152`).
- [ ] **OPEN [P]** Order `SM_COLORS` keys most-specific-first
  (clarify Q6).
- [ ] **OPEN [P]** Display ordinal suffix (e.g. "Verse 2") on hover.

## US-2: Click-to-seek

- [x] **DONE** `_smOnClick` computes time + seeks.
- [x] **DONE** Pause→seek→resume on `seeked` event.
- [x] **DONE** `lastAudioTime` synced if defined.

## US-3: Wheel-scrub

- [x] **DONE** `_smOnWheel` handler (non-passive, `preventDefault`).
- [x] **DONE** Ctrl-fine 0.1s granularity.
- [x] **DONE** Time clamped to `[0, duration]`.

## US-4: Live updates

- [x] **DONE** 200ms poller calls `_smUpdate`.
- [x] **DONE** Active-section opacity highlight.
- [x] **DONE** Playhead marker position update.

## US-5: Auto show/hide

- [x] **DONE** `playSong` wrapper rebuilds bar.
- [x] **DONE** `showScreen` wrapper removes bar on non-player nav.
- [x] **DONE** Single idempotency guard for poller + both wrappers.

## Robustness / housekeeping

- [x] **DONE** Bar removed on song change.
- [x] **DONE** State cleared on song change.
- [ ] **OPEN [P]** Replace 200ms polling with an event listener once
  highway emits a sections-changed event.
- [ ] **OPEN [P]** Touch / long-press support (clarify).

## Spec-kit hygiene

- [x] **DONE** Constitution.
- [x] **DONE** Spec / clarify / plan / tasks / analyze.
