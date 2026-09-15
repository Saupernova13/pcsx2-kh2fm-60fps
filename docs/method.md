# Method

How the patch was made, and how to make more of it. This repo follows the method
of its sibling, [pcsx2-bt3-60fps](https://github.com/Saupernova13/pcsx2-bt3-60fps),
which in turn follows Red-tv141's PCSX2 forums guide,
[AI-Assisted 60fps Patch Development for PS2 Games](https://forums.pcsx2.net/Thread-GUIDE-AI-Assisted-60fps-Patch-Development-for-PS2-Games-%E2%80%94-Full-Workflow).
The guide is not reproduced here.

## The difference from BT3

BT3 had no 60fps patch; that project wrote one. KH2FM already has one -
PeterDelta's `[60 FPS]` in PCSX2's own database - and this project compensates
what it misses. So the unpatched game is still the oracle, but "unpatched" means
the stock frame limiter, and the thing under test is always a group layered on
someone else's.

That also sets the ownership rule. Nothing written by someone else is kept in
this repo: not the database groups, not their lines in a log. `tools/install.py`
edits the user's existing database patch and adds only this project's groups.

## The oracle A/B

Every candidate is scored against the unpatched 30fps game from the same save
state, with the same input, over the same number of vsyncs - so both arms cover
the same real time. The acceptance test is `tools/balltest.py`.

### The arms

PCSXROO boots KH2FM with **`[60 FPS]` not enabled** in its own gamesettings ini
(`<pcsxroo>/bin/gamesettings/SLPM-66675_FAF99301.ini`). The arm is set by writing
the three words that group owns, after the state loads:

| | `00349E1C` vsync wait | `0036B0F8` delta cap | `0036EF20` accumulator |
|---|---|---|---|
| 60fps | 0 | 1.0 | 1.0 |
| 30fps | 1 | 6.0 | 2.0 |

A fix under test is a pnach group whose word writes are applied the same way.
For code and single-reader data words that is what PCSX2 does every frame.

### Prove the arm, every time

`sandlot.start()` advances 2 vsyncs, then reads the game tick counter `0032B920`
across 4 more. It must step 4 at 60fps and 2 at 30fps, or the run stops. Never
trust the delta word for this - see "the delta scare" below.

### The schedule

From save state 1: 6 idle vsyncs, walk `LLeft+LDown` for 8, then `Cross` for 2.
Plain `LLeft` swings past the ball. Mashing is `Cross` 2 vsyncs on, 6 off. An
`--offset` adds idle vsyncs before the walk, which moves the hit onto the other
game-tick phase at 60fps.

## Getting the user's state into PCSXROO

The user plays on PCSX2 v2.5.274, and PCSXROO (a PCSX2 v2.9.x core) refuses that
save-state version. `tools/transplant.py` carries the state across as memory.
With PCSXROO already running KH2FM in a gameplay field - on 2026-09-15, save 03 on
Memory Card 2, "The Usual Spot" in Twilight Town - it pauses at a frame boundary,
overwrites EE main RAM from `0x80000` and the 16 KB scratchpad with the state's,
and resumes. The Sandlot came up intact on the first try. `--save-slot 1` then
keeps it in PCSXROO's own format, so the transplant is needed once. It prints the
timing words afterwards; the source was saved with `[60 FPS]` on, so they read
the 60fps values until an arm is written. The user's memory cards were copied
into PCSXROO for this, with PCSXROO's old ones kept in `memcards\bak-20260915`.

## Rules learned, each by getting it wrong

1. **PCSX2's `patches.zip` carries the same `[60 FPS]` group under three CRCs**
   (`E6FB8E10`, `F266B00B`, `FAF99301`). Renaming the group in the local patch
   file does not switch it off: the enable line still names `60 FPS`, the
   database still has one, and it goes on writing the 60fps words every frame.
   The first 30fps arm ran at 60fps and every "difference" between the arms was
   zero. Remove the enable line from PCSXROO's ini and reboot.
2. **The delta scare.** With the 30fps arm proven by ticks, delta still read 1.0.
   A paused VM sits inside the frame routine's vsync wait, between the pre-wait
   write (1.0, while the measured-delta flag `00349E20` is set) and the post-wait
   write (2.0). Free-running, the 30fps arm reads 1.0 and 2.0 in equal numbers.
3. **`mem.search` caps a session at 100000 values.** A float search over EE RAM
   silently stops. Read the whole of RAM in 4 MB chunks and diff it in numpy
   (`tools/capture.py`).
4. **An idle filter throws away things that move at rest.** The Sandlot ball
   bobs. Capture first, filter offline with any rule (`tools/arcs.py`).
5. **A stack slot can impersonate an object.** `0037EC30..38` rose 506 -> 295 ->
   507 exactly like the ball at 60fps. It is the AABB centre every object's
   collision computes on the stack, and at 30fps it showed another object between
   ticks. Match its x/z/y against the heap to find the real object.
6. **A write memcheck is not observed on every write path.** The watch on the
   ball's height saw `0018A924` only. A trace of the whole object region is the
   reliable instrument; watchpoints name writers.
7. **Bare numbers in PCSXROO expressions are hex.** `--cond "t5 == 28170704"`
   compares against `0x28170704` and never fires. The first hit-handler
   breakpoint logged nothing, and that was misread as "breakpoints don't stop
   during frame-advance". They do. Write `0x` everywhere.
8. **Stops fire under `resume` + `wait`.** Watchpoint and breakpoint tools here
   resume and wait for a stop rather than frame-advancing into one.
9. **A paused VM queues screenshots.** `screenshot()` while paused writes nothing
   until `frame_advance(1)` flushes it - one vsync per frame of film.
10. **Shutting down a paused PCSXROO hung in "stopping"**, and an interrupted
    frame-advance left frames queued that paused a later `run` by themselves.
    Both are fixed on PCSXROO branches (PRs #1 and #2); until those are merged and
    rebuilt, resume before `shutdown`.
11. **PCSXROO reads real controllers.** One oracle run missed the hit and the
    rerun passed with identical numbers - most likely a pad was touched. A run
    where the oracle never lifts the ball is reported as a broken test, not a
    result.
12. **Mash runs are deterministic within a process, not always across
    processes.** Two traces in one process were identical to 0.0000; one of three
    separate runs of the unpatched 60fps mash gave travel 566 instead of 630. So
    mash results are compared as distributions over hit timings
    (`tools/mashdist.py`), never single runs.

## Choosing between fixes

Simulate before patching. `tools/simfix.py` replays the measured velocity model
(-47.59 launch, 0.8 rising drag, 0.408163 gravity, cap 10, the arch at 341.8)
at 30Hz and at 60Hz with each candidate. That picked the tick gate (FIX-D) over
constant scaling (FIX-B) before either was written as a patch: the gate reduces
exactly to the 30Hz step, and scaling does not. Both were then built by
`tools/mkballfix.py`, which copies the displaced instructions out of the ELF and
decodes every word back, and both went through the acceptance test.

A hook's displaced words must match the game. `mkballfix.py --check` regenerates
the group from the ELF and compares it with `patch/` and `wip/`.

## What shipped

Per-build confidence: [`status.md`](status.md).
The full record: [`findings.md`](findings.md).
Every address: [`addresses.md`](addresses.md).
