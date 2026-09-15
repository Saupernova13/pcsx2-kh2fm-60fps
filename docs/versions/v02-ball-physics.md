# v02 - ball physics

| | |
|---|---|
| Tag | `v02-ball-physics` - to be cut on the commit that merges this repo's first PR |
| Date | 2026-09-15 |
| Built on | [v01](v01-widescreen-s24.md) |
| Groups | 2 of ours: `[60 FPS - ball physics]` (18 patch lines) and v01's optional widescreen group |
| Confidence | Single hit **measured against the 30fps oracle at both tick phases; not yet played\***. Long juggles known not fixed |

## What it changed over v01

Added `[60 FPS - ball physics]`, enabled next to `[60 FPS]`.

The Sandlot ball's airborne motion routine, `002EA450` (class vtable `00363410`),
updates velocity once per game tick with no delta term - horizontal speed x 0.8,
rising vy x 0.8, vy + 0.408163, capped at 10 - and then moves the ball by
velocity x delta. `[60 FPS]` doubles the ticks and halves delta, so position steps
are right but drag and gravity act twice per real second.

The group hooks `002EA498` into a cave at `000FE000`. While the frame limiter is at
60fps (`[00349E1C] == 0`) and the game tick counter `[0032B920]` is odd, it jumps
over the velocity block to `002EA574`; otherwise it replays the three
instructions the hook displaced and resumes at `002EA4AC`. Two 60 Hz ticks then do
exactly what one 30 Hz tick did, horizontally and vertically.

Installed in the user's PCSX2 on 2026-09-15, inserted after `[60 FPS]` with its
derivation as comments, backups `*.bak-20260915-ballfix`.

## What was discovered

- **The 30fps "hang" is the arch.** At 30fps the ball climbs to ~342 and presses
  against the stone arch over the Sandlot; its resolved displacement drops to ~0
  while the requested one keeps decaying, so it sits pinned until gravity wins.
  At 60fps it peaked at 209 and never reached the arch, so there was nothing to
  hang on. That is why mashing worked at 30fps and not at 60.
- **Velocity is stored per 60 Hz frame and position is already right.** Words at
  `obj+0x854` and `+0x864` equal the height change per tick x 1.0 at 60fps and x
  0.5 at 30fps. So the bug had to be the velocity update, not the position step.
- **The model, exactly:** launch -47.59; rising `v = 0.8v + 0.408`; falling
  `v = v + 0.408`, cap 10; `pos += v x delta`. Checked: -47.592 x 0.8 + 0.408 =
  -37.666, read back -37.665.
- **Constants cannot simply be halved in data.** Gravity `00363404` has one
  reader, but the 0.8s live in a heap parameter block (`[00352130]` +0x18, +0x20)
  that `0019FBC4` also reads. Only one vtable points at `002EA450`, so a code hook
  there affects exactly this class.
- **The tick gate beats constant scaling, in simulation and in the game.**
  Against 30fps's peak 341.8 / 18 vsyncs at the arch / land 88 (free flight 417.6
  / land 94):

  | candidate | with the arch | free flight |
  |---|---|---|
  | unpatched 60fps | 208.8 / 0 / 47 | 208.8 / 47 |
  | B: drag sqrt(0.8), gravity / 2 | 341.8 / 17 / 88 | 394.6 / 93 |
  | C: exact per branch | 341.8 / 16 / 87 | 392.4 / 92 |
  | D: tick gate, hit on an even tick | 341.8 / 18 / 88 | 417.6 / 95 |
  | D: tick gate, hit on an odd tick | 341.8 / 13 / 87 | 370.0 / 90 |

  B also leaves the horizontal decay uncompensated and would halve the physics at
  30fps. D was chosen; B is kept in `wip/working.pnach` as a never-ship group.
- **The simulation's odd-tick worst case did not appear in the game.** Moving
  the hit by one tick phase (`--offset 1`) moved D's peak 342.2 -> 343.5 and it
  still passed.
- **The cave is free.** `000FD094..00100000` is zero in live RAM and in the save
  state; `Swap X and O` occupies `000FD050..000FD090`. Nothing in the game
  branches into the skipped block.
- **Seven data words hold 0.408163.** One is this integrator's; five feed
  closed-form ballistic solves (apex time, launch speed, fall time) in
  `0016A99C`, `0017C42C`, `0017CA50`, `0017D130`, `001846F4`; the seventh is the
  sibling integrator `0019FBC4`, not fixed.
- **The second prop is a different class when airborne** (`01C60040`, motion
  `0017C8F0`), untouched by this group. It launches at the same vsync in both
  arms, and with the group its early flight matches 30fps (144 -> 223) where
  unpatched 60fps did not (104 -> 143) - how, given it does not go through the
  gated routine, was not established.

  > **Corrected in [v03](v03-movement-physics.md):** `01A94440` is **Sora**, not a
  > prop, and the two "ground props" below are Donald and Goofy. `01C60040` is the
  > class characters fly in, and `0017C8F0` is Sora's airborne motion - the jump
  > arc and the shared velocity step `00184540`. The notes on this page are kept
  > as they were written.

### Mashing - found, not fixed

- Unpatched 60fps mashing averages 40% lower than 30fps and slides the ball 3.3x
  as far sideways. **Both candidate fixes keep the ball up far longer instead** -
  100% airborne, no landings - because it is knocked out from under the arch into
  open sky.
- **Not chaos.** Four hit timings per arm give tight distributions (table in
  [`status.md`](../status.md)).
- **No raw pushes.** The displacement builder's delta-free fields (`+0x560`,
  `+0x870`, `+0x880`) are zero on every tick in every arm, and walking Sora
  straight through the resting ball moves it 0.0 at both rates.
- **Hits set an absolute velocity** through `002E7E48` (called from `001DAE88`):
  pop-up (0, -60, 0), side swipe (~51 horizontal, -42) and a weak hit with vy -10.
  At 60fps + the group the ball took weak hits at vsyncs 67 and 91 and a side
  swipe at 116 that 30fps never gave it; the only writer of its vy at that moment,
  other than its own integrator, was the hit handler.
- **Two ground props start sliding at vsync 36-37 at 60fps**, fixed or not,
  against 43-45 at 30fps, from a stored vector copied into velocity at
  `001114F8`. Something pushes them sooner.
- Sora is not one of the 11 physics objects, and a RAM search for his position
  found only copies of the second prop. His timing was not investigated.
  **Wrong, see the correction above:** the second prop is Sora, so those copies
  were his, and the two ground props are Donald and Goofy.

## Evidence

- Single hit (`tools/balltest.py --fix`, `--offset 0` and `1`):

  | | 30fps | 60fps | 60fps + group |
  |---|---|---|---|
  | peak | 341.8 | 208.8 | 342.2 / 343.5 |
  | rise (vsyncs) | 28 | 14 | 30 |
  | arch contact | 14 | 3 | 14 |
  | airtime | 88 | 47 | 88 / 89 |
  | fall accel | 0.1865 | 0.3552 | 0.1887 |

- Mash 6 s, one timing: 30fps airborne 74%, 2 landings, mean height 262, travel
  191; 60fps 83%, 2, 158, 630; + group 100%, 0, 367, 1150; + constant scaling
  100%, 0, 411, 832.
- Side-hit horizontal decay with the group: 0.8 every other vsync, as at 30fps.
- Installed words byte-identical to the tested group; the acceptance test passed
  against the installed file.

## Still open after this build

- Mashing: Sora's hit timing and the early prop pushes under `[60 FPS]`.
- `0017C8F0` (the second prop's airborne motion) and `0019FBC4` (the sibling
  integrator) are unexamined. *(v03 examined `0017C8F0`: Sora's airborne motion.)*
- The five ballistic solves compute times and speeds in game-tick units; whether
  any of them is used as a countdown at 60fps is unchecked.
- Nothing is confirmed in play.

## Get this version

    git show v02-ball-physics:patch/kh2fm-60fps.pnach
    python tools/install.py --widescreen
