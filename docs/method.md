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
this repo: not the database groups, not their lines in a log, not the community
scripts whose addresses `tools/game/world.py` records. `tools/install.py` edits
the user's existing database patch and adds only this project's groups.

And KH2's engine already counts time in 60 Hz units - delta is the number of vsyncs
a frame took, 2 at stock 30fps - so most of the game is right under `[60 FPS]`. The
work is finding the places that step once per frame or per tick anyway, which is
why the global audit ([`global-audit.md`](global-audit.md)) tests systems in motion
rather than reading every timing constant.

## The oracle A/B

Every candidate is scored against the unpatched 30fps game from the same save
state, with the same input, over the same number of vsyncs - so both arms cover
the same real time. The acceptance tests are `tools/balltest.py` for the Sandlot
ball and `tools/movetest.py` for anything else that moves.

### The arms

PCSXROO boots KH2FM with **`[60 FPS]` not enabled** in its own gamesettings ini
(`<pcsxroo>/bin/gamesettings/SLPM-66675_FAF99301.ini`). The arm is set by writing
the three words that group owns, after the state loads:

| arm | `00349E1C` vsync wait | `0036B0F8` delta cap | `0036EF20` accumulator |
|---|---|---|---|
| `60` | 0 | 1.0 | 1.0 |
| `30` | 1 | 6.0 | 2.0 |
| `60t2` | 0 | 1.0 | **2.0** - `[60 FPS]` with the stock particle threshold |
| `60c6` | 0 | **6.0** | 1.0 - `[60 FPS]` with the stock delta cap |

A fix under test is a pnach group whose word writes are applied the same way.
For code and single-reader data words that is what PCSX2 does every frame. The
tracing tools name the combinations: `60fix` and `30fix` apply every group in
`patch/`, and `60w` and `30w` the groups named with `--group` from
`wip/working.pnach`.

### Prove the arm, every time

`sandlot.start()` advances 2 vsyncs, then reads the game tick counter `0032B920`
across 4 more. It must step 4 at 60fps and 2 at 30fps, or the run stops. The audit
tools' `ratediff.start_arm()` flushes the pad, loads, and does the same over 20
vsyncs. Never trust the delta word for this - see "the delta scare" below.

### The schedule

From save state 1: 6 idle vsyncs, walk `LLeft+LDown` for 8, then `Cross` for 2.
Plain `LLeft` swings past the ball. Mashing is `Cross` 2 vsyncs on, 6 off. An
`--offset` adds idle vsyncs before the walk, which moves the hit onto the other
game-tick phase at 60fps.

Everything else is scripted in `movetest.py`'s syntax - `wait:N`,
`hold:BTN[+BTN]:N`, `tap:BTN` - so the same script drives every arm. `Swap X and
O` is on in PCSXROO's patch file as in the user's, so Sora jumps on Circle and
attacks on Cross. The scripts the audit used are listed in
[`global-audit.md`](global-audit.md), "Method".

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
8. **Stops fire under `resume` + `wait`, and under `frame_advance`.** The watchpoint
   and breakpoint tools resume and wait for a stop. The audit's hit counters advance
   one vsync at a time instead; a breakpoint inside that vsync returns a stop whose
   `reason` is `breakpoint`, and the loop reads its registers and advances again.
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
    (`tools/mashdist.py`), never single runs. Rule 13 is the likely reason.
13. **Flush the pad before loading a state.** A button release sent while paused
    only queues, so the last button of one arm was still down on the first frame
    of the next, and the unpatched 60fps arm's jump peaked 146.80 in one run and
    156.57 in another. `ratediff.start_arm()` calls `flush_input()` before every
    load; every audit tool starts its arms through it.
14. **Physics defects do not show at idle.** The Sandlot idle sweep in three arms
    (`tools/ratesweep.py`) found integer effect state stepping twice as often and
    no float moving twice as far. Every physics defect so far came from a scripted
    motion.
15. **Check who an object is before concluding what it is not.** The ball work
    called `01A94440` "the second prop" because it was in the list of objects the
    displacement builder moves, then concluded Sora was not a physics object - and a
    search for Sora's position that turned up "only copies of the second prop" was
    read as confirmation. Those were Sora's own copies. Walking the player away and
    back (`tools/findplayer.py`) takes a minute and names the player; the objects
    that follow are the party.
16. **A walk is diagonal and ends in a slide.** The first player filter wanted every
    word to reverse sign on the way back and hold within 2.0 after release, and
    found nothing. Filter whole vec4s with w = 1.0 by horizontal distance, and tell
    an object's own position from its copies by a known class word at `-0x540 +
    0x0C`: unrelated single copies walked as far as Sora did.
17. **Capstone has no R5900 mode; disassemble VU code through PCSXROO.** The shared
    velocity step `00184540` is VU0 macro-mode code, which `ps2ee.disasm` will not
    decode. PCSXROO's own disassembler (`Roo.dis`) does.
18. **The R5900 FPU's SQRT takes its operand from ft, not fs.** Standard MIPS puts
    the operand of `sqrt.s fd, fs` in bits 15-11; the PS2, and PCSX2, read bits
    20-16. The first friction group was encoded the MIPS way, computed `sqrt(f0)` =
    0, and deleted every lunge (path 0.00). A conditional breakpoint just after the
    cave showed f20 and f21 at zero. Encode `0x46000004 | ft << 16 | fd << 6`
    (`mkfrictionfix.sqrt`), and check any new FPU word by breaking on its result:
    the disassembler decodes it the standard way.
19. **Break in shared code with a condition on the object.** The hit handler
    `002E7E48` stopped every frame. A breakpoint on its vy write `002E7EE8` with
    `t5 == 0x01ADD9D0` gave exactly the ball's hits; the friction step's with
    `a1 == 0x01A94440`, exactly Sora's factors.
20. **Every group runs at 30fps too.** A group for 60fps must be a no-op at 30fps.
    `objtrace.py` in the `30` and `30fix` arms through the same scripts must show 0
    differing words in the object. All three physics groups do - the jump group by
    construction (the clock is always even at 30fps), the friction group because it
    checks the vsync wait, the ball group because it gates on it.
21. **A fix is only as good as every test run against it.** The first friction
    group passed the ground combo, run-and-stop and both jumps; only the air combo -
    path 0.00 - showed it had deleted the lunge. So with every group on, the jumps,
    both combos, run-and-stop and the ball's single hit are all run again.

## Choosing between fixes

Simulate before patching. `tools/simfix.py` replays the measured velocity model
(-47.59 launch, 0.8 rising drag, 0.408163 gravity, cap 10, the arch at 341.8)
at 30Hz and at 60Hz with each candidate. That picked the tick gate (FIX-D) over
constant scaling (FIX-B) before either was written as a patch: the gate reduces
exactly to the 30Hz step, and scaling does not. Both were then built by
`tools/mkballfix.py`, which copies the displaced instructions out of the ELF and
decodes every word back, and both went through the acceptance test.

v03's groups were chosen from what the code computes:

- **The jump cut is a threshold compare** on a clock that steps by delta. Letting
  the cut happen only on even clock values is exactly the 30fps grid at 60fps, and
  never changes 30fps, where the clock is always even.
- **The velocity step multiplies by a factor once per frame.** The factor's square
  root at 60fps is the same decay per real second, and the blend's resting value is
  the target itself, so top speeds cannot change. It is also phase-free, which a
  tick gate would not be with 19 call sites setting velocities at arbitrary moments.
  The ball's integrator uses a gate because its update adds gravity as well.

A hook's displaced words must match the game. Each generator checks the words it
displaces against the ELF, decodes its group back, and `--check`s it against
`patch/` and `wip/`: `mkballfix.py`, `mkjumpfix.py`, `mkfrictionfix.py`. The caves
are packed in the zero run from `000FE000`: `000..03C`, `040..070`, `080..0B8`.

## What shipped

Per-build confidence: [`status.md`](status.md).
The full record: [`findings.md`](findings.md).
The plan for the rest of the game: [`global-audit.md`](global-audit.md).
Every address: [`addresses.md`](addresses.md).
