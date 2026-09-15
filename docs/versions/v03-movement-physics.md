# v03 - movement physics

| | |
|---|---|
| Tag | `v03-movement-physics` - to be cut on the commit that merges it |
| Date | 2026-09-15 |
| Built on | [v02](v02-ball-physics.md) |
| Groups | 4 of ours: `[60 FPS - ball physics]` (18 patch lines), `[60 FPS - short hop]` (15), `[60 FPS - friction]` (16), and the optional widescreen group |
| Confidence | **Measured against the 30fps oracle; not yet played\***. The Grandstander juggle still differs - see "Still open" |

## What it changed over v02

The user asked for a global fix: "60fps should behave the same as 30, just look
better", across as much of the game as possible. v03 adds the two physics groups
that measurement found in the character and object movement code every scene uses.

| group | what it does |
|---|---|
| `60 FPS - short hop` | A released jump is cut into its apex arc once the jump clock (`+0xD0`) passes 6.0 (`0017C690`). The clock steps by 2 at 30fps and 1 at 60fps, so 60fps cut one unit early. The cut now happens only on an even clock: the 30fps grid at 60fps, a no-op at 30fps |
| `60 FPS - friction` | `00184540`, the shared velocity step behind 19 motion routines, blends velocity toward the input target by k1 and decays it by k2 once per frame, with no delta. At 60fps both factors now take their square root - the same decay per real second, with the blend still settling on the target |

Both hook into the safe zone after the ball physics cave: `000FE040..000FE070` and
`000FE080..000FE0B8`.

## What was discovered

- **The engine counts time in 60 Hz units.** Delta is the number of vsyncs a frame
  took (`0014D060`), capped; at stock 30fps it is 2. Code that scales by delta was
  written for 60 Hz and is already right under `[60 FPS]`; the defects are the
  places that step once per frame.
- **`[60 FPS]` also doubles the particle and effect step.** It sets the fixed-step
  accumulator threshold `0036EF20` (`partMng.c` / `pppPart.c`) from 2.0 to 1.0. The
  accumulator adds delta and steps at the threshold, so the stock 2.0 was already 30
  steps a real second at 60fps; 1.0 is 60. A RAM sweep found int state 2x under
  `[60 FPS]` and 1x with 2.0 restored. Not changed in v03: it is effects, not physics.
- **The "second prop" was Sora, and the two "ground props" were Donald and Goofy.**
  Found by walking Sora away and back and finding his position vector at
  `01A94440 + 0x540`. Every earlier note that said Sora is not a physics object was
  wrong: he is class `01C60030` on the ground and `01C60040` in the air.
- **A jump is a closed-form arc** on a clock advancing by delta - rise over a duration,
  then a short apex arc (5.0 long, 5.102 high) and a fall under 0.408163 - so a held
  jump already matched (peak 185.00 at both rates). Only the cut point of a released
  jump was on the wrong grid.
- **The shared velocity step is VU code** (`00184540`): `v = v*k1 + dir*speed*(1-k1)`
  with input, `v = v*k2` without, then `v*delta`. Its resting value is the target, so
  `sqrt(k)` changes how fast velocity gets there, never where it ends.
- **The R5900 FPU's SQRT reads its operand from ft**, not fs as standard MIPS has it.
  The first friction group computed `sqrt(f0)` - zero - and deleted every lunge.
  Capstone decodes SQRT the standard way; the game's own SQRT words hide it.
- **A static scan finds very few direct per-frame integrators.** Of every
  `field = field op constant` float update, only the ball's gravity uses a data
  constant; 14 more read tuning through the parameter table `[00352130]`, and 11 of
  those are the ability tuning switch `001C31E8`, not per-frame at all.
- **A pad release sent while paused only queues.** Without a flush before each state
  load the previous run's button leaked into the next arm, and the unpatched 60fps arm
  varied between runs. Every arm now flushes first.

## Evidence

All from the user's Twilight Town save state, same input in every arm, 30fps as oracle:

| test | 30fps | 60fps | 60fps + v03 |
|---|---|---|---|
| tap jump peak | 115.08 | 103.53 | 115.10 |
| 15-vsync hold peak | 152.32 | 144.43 | 152.34 |
| 17-vsync hold peak | 165.38 | 159.31 | 165.39 |
| held jump peak | 185.00 | 185.00 | 185.00 |
| air combo forward travel | 195.02 | 131.43 | 194.68 |
| ground combo travel | 244.46 | 286.61 | 245.03 |
| run 40 vsyncs then stop | 287.63 | 287.62 | 287.62 |
| ball, one hit: peak / airtime | 341.85 / 88 | 208.82 / 47 | 342.24 / 88 |

On the attack frame, the friction step's factors read 0.9487 and 0.9747 (the square
roots of 0.9 and 0.95) and the lunge velocity decays 5.235, 5.102, 4.973, 4.847 -
through the 30fps values every second frame.

## Still open after this build

- **The Grandstander juggle.** With every group, mashing still keeps the ball up far
  longer than at 30fps (30 taps: airtime 214 against 125-142). Clean hit counts: two
  pop-ups at 30fps; at 60fps a pop-up and then weak hits and a side swipe that 30fps
  never lands. The extra hits come at Sora's attack clock 12, 16 and 17 - not only on
  frames 30fps skips - so it is not a sampling grid alone. The arms part at the ball's
  launch: rising through Sora's swing, it is pushed out of contact 5.3 units further
  over in z, and a swing's contact push-outs total 39.5 units at 30fps against 33 at
  60fps. That is collision resolution sampled at a finer step, and no per-frame rate
  term has been found in it yet.
- **Effects at double speed** from `[60 FPS]`'s accumulator threshold.
- **Enemies**: nothing reachable in the user's saves has combat yet; the friction group
  covers the enemy states that call `00184540`, unmeasured.
- The sibling integrator `0019FBC4`; Quick Run and other abilities; reaction commands.

## Get this version

    git show v03-movement-physics:patch/kh2fm-60fps.pnach
    python tools/install.py --widescreen
