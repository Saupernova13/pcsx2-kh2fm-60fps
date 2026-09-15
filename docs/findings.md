# KH2FM 60fps - findings log

Running record of everything established about Kingdom Hearts II Final Mix+
(SLPM-66675, CRC FAF99301) under PeterDelta's `[60 FPS]`. Newest sections at the
bottom. Log numbers refer to `wip/session-<date>/logs/`; every address is also in
[`addresses.md`](addresses.md).

## STATE OF PLAY - read this first

> **Superseded in part (later on 2026-09-15, v03).** The global audit at the bottom
> of this log found that the "second prop" `01A94440` is **Sora** and the two
> "ground props" are **Donald and Goofy**, so Sora *is* a physics object. It added
> `[60 FPS - short hop]` and `[60 FPS - friction]`, both verified against 30fps and
> verified to change nothing at 30fps. The juggle still differs with every group on.
> Read "2026-09-15 - global audit" below and [`global-audit.md`](global-audit.md)
> before the older sections.

Last revised 2026-09-15. Two groups of ours, both installed and enabled in the
user's PCSX2, **neither yet confirmed in play** - see [`status.md`](status.md).

| group | what it does |
|---|---|
| `Widescreen 19.5:9 - S24 Ultra` | ElHecht's 16:9 hack retargeted to 19.5:9: widen factor 12/19.5 loaded exactly with `lui`+`ori`, font x-scale to match. Built at install time from the database's 16:9 group |
| `60 FPS - ball physics` | gates the airborne prop integrator's per-tick velocity update to every other game tick while `[60 FPS]` is active. One hit of the Sandlot ball flies as at 30fps |

**Known not fixed:** a long juggle. At 60fps Sora's swings reach the ball at
different moments - extra weak hits and earlier side swipes - and two ground props
are pushed 6-8 vsyncs sooner. That is character timing under `[60 FPS]`, not the
ball, and nobody has looked at it. See "Mashing" below.

**Open leads, in the order worth taking them:** Sora's hit timing (the hit handler
`002E7E48` is called from `001DAE88` - start there); the ground props' push
vector (`obj+0xC20`, copied at `001114F8`); the second prop's airborne motion
`0017C8F0`; the sibling integrator `0019FBC4`; whether any closed-form ballistic
solve feeds a countdown.

## Setup

| | |
|---|---|
| Game | Kingdom Hearts II - Final Mix+ (English Undub Patched), CHD. SLPM-66675, CRC FAF99301 |
| Player's emulator | PCSX2 v2.5.274 under EmuDeck on Windows, `EECycleRate = 1` |
| Player's patches | Remove Blackbars, Widescreen 16:9 (then 19.5:9), Remove Blur, Swap X and O, 60 FPS |
| Debug emulator | PCSXROO, a PCSX2 v2.9.x fork with a JSON debug server on 28110 |
| Reference state | the player's save state 1: Sora beside the glowing ball in the Twilight Town Sandlot |
| Oracle | the same state at 30fps: `[60 FPS]`'s three words put back |

The database patch for FAF99301 inside PCSX2's `patches.zip` has `[Widescreen
16:9]` (ElHecht), `[Subtitles off]`, `[Remove Blackbars]` and `[60 FPS]`
(PeterDelta). The player's own `patches/` file also has `[Remove Blur]` and
`[Swap X and O]`.

---

## 2026-09-14 - widescreen retargeted from 16:9 to 19.5:9

The user asked, with the BT3 repo as the reference, for the 16:9 patch to be
disabled and one rendering at the S24 Ultra's aspect added and enabled.

**The 16:9 group is a code hack.** Unlike BT3's stock widescreen - three words, one
of them an immediate holding 1/aspect - ElHecht's rewrites the projection routine
at `00106DE8`. It loads a 4:3 base of 0.8 at `00106E10` / `00106E28`, loads the
widen factor 0.75 as an immediate at `00106E54` and moves it to `$f30`, and at
`00106E70` / `00106E74` multiplies and stores the result in `[cam+0x4C]`. It also sets three "font fix" floats at `0036CE94..9C` from 1.0 to
0.75, a cutscene zoom at `0036A0BC` (stock 416.0), a depth-of-field byte at
`00166DB6` and the subtitle height at `001AC8D8`. Its database entry keeps five
commented-out lines from an older data-only hack and a commented "disable image
map names" block.

**The rule.** 0.75 = `(4/3) / (16/9)`, the horizontal widen factor, and the font
floats carry the same factor to squeeze glyphs back. Fed 16:9 the model returns
`3F400000`, bit for bit what the group ships.

**For 19.5:9** (3120x1440, the BT3 patch's target): `12/19.5 = 0.6153846 =
3F1D89D9` (log 01: back-converted 0.615384638). A `lui` alone keeps the top 16
bits and loads 0.6132812, 0.34% narrow. The routine has two stock `nop`s at
`00106E60..64`, so `00106E58` becomes `ori $k1, $k1, 0x89D9` and the `mtc1` moves
into `00106E60`. The three font floats become `3F1D89D9`. The 0.8 base, zoom,
depth of field and subtitle height do not depend on aspect and are kept.

**Installed** in the player's `patches\SLPM-66675_FAF99301.pnach` as
`[Widescreen 19.5:9 - S24 Ultra]`, 15 lines, `gsaspectratio=Stretch`, with the
16:9 group left in the file; the ini's `Enable = Widescreen 16:9` replaced (logs 02,
03). Backups `*.bak-20260914`.

**Notes that still stand:**

- PCSX2 has no 19.5:9 display aspect: Stretch, against a 19.5:9 output only.
- Both widescreen groups write `00106E54/58` every frame; never enable both.
- Samsung lists the panel as 3088x1440 (19.3:9). This matches BT3's 19.5:9 on
  purpose; `tools/ws-math.py --aspect 3088:1440` has the other words.
- Editing the ini by hand while the game runs is fragile: changing the game's
  settings in PCSX2's menus can write the old list back.
- Not verified on screen.

---

## 2026-09-15 - the Sandlot ball at 60fps

The user's report: "Look at save state 1. Load it in pcsxroo. Keep mashing x to
keep the ball in the air. It works well in 30fps mode. The 60fps patch breaks
things though. Please assess and fix the gravity and physics in the 60fps
version."

### What `[60 FPS]` touches

Scanning the save state's RAM for code that loads its addresses (log 06):

- `00349E1C`: 7 references. `0014CE3C` stores it (the setter `0014CE30`); the frame
  routine reads it at `0014D0A4` and `0014D19C`; `0023D25C` and `0023D320` read it.
- `0032BA24`: 12 references in `001035D0..00103D54` - a game mode word. The group's
  E-code keeps the 30fps wait while it reads 5.
- `0036B0F4`: one, `0014D0A0`. `0036B0F8`: one, `0014D0F8`. `0036EF20`: two, both in
  `001E6280`.

The group writes 0 to the vsync wait, 1.0 to the delta cap and 1.0 to the
accumulator threshold.

The ELF was extracted from the CHD (log 01) and its stock values read (log 07):
delta `00349E10` 1.0, vsync wait `00349E1C` 0 (the init sets 1), measured-delta flag
`00349E20` 1, `0036B0F4` 2.0, cap `0036B0F8` 6.0, threshold `0036EF20` 2.0, zoom
`0036A0BC` 416.0. One RWX load segment at `00100000`, file size `0027A800`.

### Getting the state into PCSXROO

PCSXROO refuses the player's v2.5.274 state. The EE RAM and scratchpad were written
into a running PCSXROO at a frame boundary - 32 MB in 7.8 s - over a Twilight Town
field loaded from the player's memory card (log 08). The Sandlot came up intact,
and was saved as PCSXROO slot 1. The timing words read `[60 FPS]`'s values, as the
state was saved with it on.

### The first A/B was not an A/B

Full-RAM snapshots around one hit, at "60fps" and "30fps", ranked the same 21004
moving words identically in both arms - and delta read 1.0 in both (log 09). The
30fps arm was not running.

`patches.zip` in both PCSX2 and PCSXROO carries `[60 FPS]` under three CRCs -
`E6FB8E10`, `F266B00B`, `FAF99301` (log 10). The arm switch had renamed the group in
PCSXROO's own patch file, but the ini still said `Enable = 60 FPS` and the database
still had one. Writing the 30fps words directly lasted one vsync: the vsync wait
read 0 again on the next (log 11). Removing `Enable = 60 FPS` from PCSXROO's KH2 ini
(log 12) and rebooting fixed it for good. From then on, arms are the three words
written after the state loads.

### Frame timing, and the tick counter

From the ELF (logs 13, 15; `tools/frame-timing.py` reproduces it):

- The frame routine starts at `0014D060`. Its vsync wait loop, `0014D1CC..0014D1FC`,
  counts vsyncs (`[00349E08]`, converted to a float and stored into the delta
  accumulator at `0014D200`) until the count reaches `[00349E1C]`.
- `0014CF18` is the vsync callback, registered at `0014D028` during init
  (`0014D004`): it increments `00349E04` and `00349E08`.
- The delta path at `0014CEA8..0014CF14` adds, scales by `[00349E0C]`, stores delta
  `00349E10`, delta-before-cap `00349E14`, and `1 / delta` into `00349E18`.
- The vsync wait setter `0014CE30` is called with 1 at `0014CFD8`, and from
  `0023D320` with a stored value; the measured-delta flag setter `0014CE20` is set
  to 1 at `0014CFD0` / `0023D350` and 0 at `00224D64` / `0023D388`.
- Delta has 211 readers in 172 functions. `0036EF20` is read by a fixed-step
  accumulator in `001E6280`, called from `001DD4E0`.

Three RAM dumps 20 vsyncs apart per arm (log 14): exactly one word steps 20 at 60fps
and 10 at 30fps - **`0032B920`, the game tick counter**. Ten more step 20 in both
(per-vsync clocks: `0032DF74`, `0032DF84`, `00349DE8`, `00349E04`, `0034D4BC`,
`0034D53C`, ...).

**The delta scare.** Free-running, the 60fps arm read delta 1.0 in 80 of 80 samples;
the 30fps arm read 2.0 in 40 and 1.0 in 40. A paused VM stops inside the vsync
wait, after the pre-wait write (1.0) and before the post-wait one (2.0), so a paused
read of delta proves nothing. Every arm since is proven by `0032B920`.

### Finding the ball

- `mem.search` stops at 100000 values in a session; a float search for the ball's
  height silently truncated. Whole-RAM reads diffed in numpy replaced it.
- An idle filter excluded the ball, because the orb bobs at rest.
- Walking `LLeft` did not reach the ball; `LLeft+LDown` for 8 vsyncs, then `Cross`
  for 2, does - that is the schedule every run since uses.

From a 14-snapshot capture (log 16): 17817 words move far more in flight than at
rest; 8741 have a plausible excursion (5..2000); 6109 have a vec4 w of 1.0 within 12
bytes; 2480 go up and come back. At the top, `0037EC34`: 506 at rest, 295 at the
peak, back to 507 - and a family of copies at `0037EEB4..0037EF24` offset by +/-40
and +/-60, the corners of a box (log 17).

It is not the ball. `0037EC30` is a stack slot - the AABB centre every object's
collision computes - so it follows whichever object ran last, and at 30fps it
showed another object between ticks. Its x/z/y (704.82, -2646.31, 506.22) matched
against the heap found the ball object at **`01ADD9D0`**, with its collision-shape
centre at `01ADEAC0`.

### The ball, per vsync (log 18)

Collision-shape y at rest 526.22, KH2 negative-up; height = rest - y.

| | lift | peak | at | land | airtime | fall accel |
|---|---|---|---|---|---|---|
| 60fps | 25 | 208.8 | 39 | 72 | 47 | 0.3666 |
| 30fps | 27 | 341.8 | 55 | 115 | 88 | 0.1953 |

At 30fps the height changes every other vsync (95 95 171 171 230 230 ...) and then
holds at 340-342 for about 18 vsyncs: the ball is pinned against the stone arch
over the Sandlot. At 60fps it stops at 209, well short of the arch.

Correlating every word of the object's 4 KB region with height change per game
tick found `01ADE224` and `01ADE234` (`obj+0x854`, `obj+0x864`) at corr 1.0000, with
**value / dy-per-tick = 1.0 at 60fps and 0.5 at 30fps**. Velocity is stored per 60
Hz frame and position moves by velocity x delta. So position steps are correct at
both rates, and the bug is in how velocity changes.

A write watch on the collision y found `0018A90C` / `0018A924` - a copy out of a
transformed vector, not physics.

### The velocity model, and the "hang"

Sampled per tick at 60fps and 30fps, identical per tick in both:

- the hit leaves vy = -47.59 after one update (the hit sets -60);
- rising: `v = 0.8 v + 0.408` (checked: -47.592 x 0.8 + 0.408 = -37.666, read -37.665);
- falling: `v = v + 0.408`, capped at 10.0;
- position: `pos += v x delta`.

The velocity update has no delta term, so at 60fps drag bleeds the launch off twice
as fast per real second and gravity doubles. **The 30fps hang is the arch**: the
resolved displacement (`+0x860`) drops to ~0 at the ceiling while the requested one
(`+0x850`) keeps decaying, so the ball sits there until gravity wins. At 60fps it
never gets high enough to hang.

The velocity writers into those fields are `00183384` and `0018342C`, both
displacement x `[00349E18]` (1/delta) - so the 0.8 and 0.408 had to be applied
earlier, before the displacement is built.

### The code (log 19)

Mid-flight the object's class `[obj+0x0C]` is `01C60340`, vtable `00363410`, and
vtable +0x1C is **`002EA450`**, the airborne motion routine:

    002EA494  s6 = obj + 0x20                       velocity
    002EA498  beql sp, s6 / lq / sq / sw            copy to the stack
    002EA4AC  normalise horizontal; |v| in f01
    002EA4E4  horizontal speed x [[00352130]+0x18] (0.8), against [003760C8] (1.0)
    002EA524  sw +0x28, +0x20
    002EA534  if vy >= 0 skip the drag
    002EA548  vy *= [[00352130]+0x20] (0.8)
    002EA55C  vy += [00363404] (0.408163)
    002EA570  vy = min(vy, [obj+0x120] = 10.0)
    002EA574  displacement = velocity x [00349E10]  ...

RAM holds 19 words near 0.40817; 7 are in the ELF's data. The launch speed 47.59 is
not a constant anywhere - it is -60 after one drag step. `+0x120` = 10.0 on the
object. The displacement builder `00183088` (a0 = object) copies `+0x540` to
`+0x840` and clears `+0x860`, `+0x870`, `+0x880`.

A read watchpoint on `obj+0x850..0x870` mid-fall saw nothing in 5 s: an instrument
limit, not a result. `$gp` read `00000000` on that stop, from a thread outside the
game loop; `.reginfo` puts it at `0037A800`.

### Why not just halve the constants

- Gravity `00363404` has exactly one reader, `002EA55C`.
- The two 0.8s come from a heap parameter block (`[00352130]` -> `01CE36CC`).
  `+0x20` is also read by `0019FBC4`; `+0x18` by two functions. They cannot be
  changed in data without changing other objects.
- Only one vtable, `00363410`, points at `002EA450`: a code change there reaches this
  class and nothing else.

### Simulated candidates

`tools/simfix.py` replays the model at 30Hz and 60Hz. 30fps reference: with the arch,
peak 341.8 / 18 vsyncs at the arch / land 88; free flight 417.6 / land 94.

| candidate | with the arch | free flight |
|---|---|---|
| A unpatched 60fps | 208.8 / 0 / 47 | 208.8 / 47 |
| B drag sqrt(0.8), gravity / 2 | 341.8 / 17 / 88 | 394.6 / 93 |
| C sqrt(0.8), gravity / (1 + sqrt(0.8)) rising, / 2 falling | 341.8 / 16 / 87 | 392.4 / 92 |
| D the velocity block every other tick, hit on an even tick | 341.8 / 18 / 88 | 417.6 / 95 |
| D, hit on an odd tick | 341.8 / 13 / 87 | 370.0 / 90 |

Every row's worst height error includes 47.6 at the first tick: 30fps moves 2 x v0
at once, 60fps v0 per vsync. D reduces exactly to the 30Hz step and covers the
horizontal decay in the same hook. B and C do not, because a semi-implicit step
with the constants changed is not two 30Hz steps. D was the pick, with the tick
phase as its known risk (log 21 repeats the odd-phase case).

### The cave and the hook

- `00080000..00100000` in live RAM (log 20) and in the save state (log 21) have the
  same zero runs; `000FD094..00100000` is 3035 zero words. `000FD050..000FD090` is
  `Swap X and O`'s code. The cave goes at `000FE000`.
- The rest of `002EA450` (log 20) has nothing else per-tick in the velocity: it
  sums displacement, probes collision (`001A7588`), reflects on the ground with
  -0.8 at `002EA8C0`, and multiplies by delta again at `002EAA08`.
- Nothing in the game branches into `002EA49C..002EA574` (`tools/elfscan.py into`).

Both candidates were encoded by hand and decoded back (log 22). The hook site in
the ELF is `53B60004 beql sp, s6, 002EA4AC` / `AFA00004 sw zero, 4(sp)`, followed by
`7AC80000` / `7FA80000` - `lq t0, 0(s6)` / `sq t0, 0(sp)`, which capstone decodes as
MSA ops. They are copied out of the ELF rather than typed. Gravity in the ELF is
exactly `3ED0FAC6` (0.4081632); B's half is `3E50FAC6`.

FIX-D, as shipped:

    000FE000  lui  t0, 0x35
    000FE004  lw   t0, -0x61E4(t0)       [00349E1C]: 0 means [60 FPS] is active
    000FE008  bnez t0, 000FE028          30fps: never gate
    000FE00C  lui  t1, 0x33
    000FE010  lw   t1, -0x46E0(t1)       [0032B920] game tick counter
    000FE014  andi t1, t1, 1
    000FE018  beqz t1, 000FE028          even tick: update as normal
    000FE01C  nop
    000FE020  j    002EA574              odd tick: keep last velocity
    000FE024  nop
    000FE028  beq  sp, s6, 000FE038      the displaced beql, replayed
    000FE02C  nop
    000FE030  lq   t0, 0(s6)             copied from 002EA4A0
    000FE034  sq   t0, 0(sp)             copied from 002EA4A4
    000FE038  j    002EA4AC
    000FE03C  sw   zero, 4(sp)           copied from 002EA4A8; both paths end with it
    002EA498  j    000FE000
    002EA49C  nop

### Acceptance: one hit

`tools/balltest.py`: same state, same schedule, 180 vsyncs, tolerances peak 3%,
airtime 3 vsyncs, arch contact 4, fall acceleration 10%.

| | peak | rise | contact | air | fall |
|---|---|---|---|---|---|
| 30fps oracle | 341.8 | 28 | 14 | 88 | 0.1865 |
| 60fps unpatched | 208.8 | 14 | 3 | 47 | 0.3552 |
| 60 + FIX-B, offset 1 | 342.9 | 30 | 14 | 89 | 0.1889 - PASS |
| 60 + FIX-D, offset 0 | 342.2 | | 14 | 88 | PASS |
| 60 + FIX-D, offset 1 | 343.5 | 30 | 14 | 89 | 0.1887 - PASS |

(log 02 for offset 1.) FIX-D's peak moved between the offsets, so the hit did change
tick phase, and the simulated odd-phase loss did not appear in the game.

### Mashing: both candidates fail, the other way

6 s of mashing, `Cross` 2 on / 6 off (log 02):

| | airborne | landings | mean height | max | travel |
|---|---|---|---|---|---|
| 30fps oracle | 74.0% | 2 | 262.1 | 345.9 | 190.9 |
| 60fps unpatched | 83.2% | 2 | 158.4 | 403.9 | 629.6 |
| 60 + FIX-B | 100% | 0 | 411.2 | 639.3 | 832.3 |
| 60 + FIX-D | 100% | 0 | 367.3 | 562.4 | 1149.5 |

Unpatched 60fps averages 40% lower and travels 3.3x as far sideways. With either fix
the ball never lands: it drifts out from under the arch that caps it at ~346 and
reaches open sky.

**Run-to-run variation.** In one of three runs the unpatched 60fps arm gave
82.6% / 157.5 / 362.3 / 566.1 instead; the 30fps oracle was identical every time.

### Where the sideways travel comes from (log 03)

- **Deterministic within a process**: two 60fps traces from the same state differ by
  0.0000 at every vsync.
- **No raw pushes**: `+0x560`, `+0x870`, `+0x880` are zero on every tick, `+0x88C`
  always 0, in all three arms.
- 30fps: hits (vy below -20) at vsyncs 27 and 183, horizontal path 127.8, velocity
  xz summing to 0.0 - all of its sideways motion is collision resolution.
- 60fps unpatched: hits at 26, 150, 223; path 380.2, velocity 228.6; the hit at 223
  sets v = (-51, -42, 0).
- 60 + FIX-D: hits at 26, 116; path 647.4, velocity 463.0; the hit at 116 sets
  (49.82, -42, 10.91).
- Writers of `obj+0x20..0x2C` across a hit with FIX-D: the integrator's own
  `002EA524/534/550/570` (ra `002EA498`); the rest class's zeroing at `0017C3F4`
  (ra `00183198`); and **`002E7E48`, the hit handler**, called from `001DAE88`: it
  copies a direction vector into velocity, zeroes its y, normalises, scales by
  `[a0+0xC]`, and writes `vy = -[a0+0x8]` at `002E7EE8`.

`tools/divergence.py mash` on the same trace, before each arm's first side swipe:
sideways motion not explained by velocity runs 0.533 per vsync at 30fps, 0.914
unpatched and 1.324 with FIX-D. After a side swipe, FIX-D decays horizontal speed
x0.8 every other vsync (51.00 40.80 40.80 32.64 32.64 ...), as 30fps does;
unpatched decays x0.8 every vsync.

### The breakpoint that never fired, and the weak hits

A breakpoint on `002E7EE8` with the condition `t5 == 28170704` logged nothing in any
arm. It was first taken for "breakpoints do not stop during frame-advance". The
truth, found while fixing PCSXROO later the same day: **bare numbers in PCSXROO
expressions are hex**, so the condition compared against `0x28170704` and could never
be true. An unconditional breakpoint under resume/wait fired at once (log 04:
`pc 002E7EE8 t5 01ADD9D0 tick 601`).

The trace showed a third kind of hit: **weak hits that set vy to -10**. None at 30fps
in 4 s. With FIX-D, at vsyncs 67 and 91 while the ball is up at the arch (height
329-338), keeping it pinned, then a side swipe at 116. Unpatched 60fps takes them at
62, 166 and 196. Screenshots: at 60fps + FIX-D Sora is up at the arch beside the
ball at vsync 110 and strikes it at 118; at 30fps, at vsync 67, the ball is as high
and Sora does not reach it.

### Every physics object (log 04)

Breaking on the displacement builder `00183088` under resume/wait listed 11 objects:
eight at rest class `01C60030` (vtable `0034EB60`, motion `0017C290`), three of
`01C60060` (vtable `0034EB30`, motion `0017A968`) at the origin. **Sora is not one
of them** - the player moves through another system. The ball at rest is class
`01C60030` like the others; it switches to `01C60340` when hit.

Heights through the 130-vsync mash, every 10 vsyncs:

| object | 30fps | 60fps unpatched | 60 + FIX-D |
|---|---|---|---|
| ball `01ADD9D0` | max 341.8 at 57: 95 340 342 341 326 290 234 158 62 | max 208.8 at 41: 138 209 191 133 141 118 55 | max 486.1 at 129: 171 341 342 340 347 345 339 342 336 363 |
| `01A94440` | max 238.0 at 83: 144 223 238 233 193 112 88 | max 166.1 at 84: 104 143 165 159 115 30 | max 321.2 at 129: 144 223 281 301 304 314 286 |
| `01AC2490` | slides, xz path 84.4 | 142.3 | 102.0 |
| `01AADB90` | slides, xz path 68.7 | 135.8 | 111.9 |

`01A94440` is a second prop, not Sora. With FIX-D its first 20 vsyncs of flight match
30fps (144, 223) where unpatched 60fps does not (104, 143), until the two runs'
interactions diverge around vsync 60-70.

`0019FBC4` disassembled (log 04): the same horizontal factor, rising drag, gravity
(its own copy, `0036D440`) and cap as `002EA450`, plus `obj+0xF8 += delta`. Reached
by fall-through from the function before it; no callers found.

### The other readers of 0.408163 (logs 23, 24)

Seven data words hold `3ED0FAC6`, each read by one function:

| word | function | what it computes |
|---|---|---|
| `00363404` | `002EA450` | the airborne integrator - fixed |
| `0036C1AC` | `0016A99C` | apex time, `+0x864` / g; reached from 11 call sites and 12 data pointers |
| `0036C510` | `0017C42C` | launch speed `sqrt(-2 h / g)`, with -2.0 at `0036C50C`; 10 callers |
| `0036C534` | `0017CA50` | fall time; 15.0 and 0.5 next to it |
| `0036C554` | `0017D130` | `sqrt(2 h / g)`; 5 callers |
| `0036C8AC` | `001846F4` | apex time from `+0x864`; reached by `j` from `00173ECC` |
| `0036D440` | `0019FBC4` | the sibling integrator - not fixed |

The five in the middle are closed-form ballistic solves, not integrators. Their
results are in game-tick units; whether any is used as a tick countdown at 60fps is
unchecked.

### Distributions, and the search for Sora (log 05)

Sora's position was sought as a vec4 near the ball that rises between vsync 0 and
110 of the 30fps mash, when screenshots show him airborne. All 35 candidates
(`00341720..`, `00348710..`, `003A7FD0`, `01A81FE0`, `01AABB50..`) trace heights 144,
223, 238 at 30fps - copies of the second prop. Sora is not a plain vec4 there.

The mash at hit offsets 0-3, 4 s each:

| | airborne | landings | mean height | max | travel |
|---|---|---|---|---|---|
| 30fps | 0.67 | 1 | 276.52 +/- 1.36 | 345.88 | 159.23 +/- 31.39 |
| 60fps unpatched | 0.74 | 1 | 158.20 | 231.38 | 380.15 |
| 60 + FIX-B | 1.00 | 0 | 376.90 | 555.82 | 490.09 |
| 60 + FIX-D | 1.00 | 0 | 373.64 +/- 19.97 | 560.56 +/- 32.17 | 662.37 +/- 15.00 |

**Systematic, not chaos.** At 30fps the arch caps the ball at 346; with either fix it
is pushed out from under the arch, and every 60fps arm travels 2.4-4x further.

### Is it a push-out? No (log 25)

Hypothesis: when Sora overlaps the ball, the push-out is not scaled by delta. Test:
walk Sora through the resting ball for 90 vsyncs, no attack, in all four arms. **The
ball moved 0.0 in every arm**, requested and resolved displacement both 0.0. A
resting ball is not body-pushed. The displacement contributor `001835F8` (non-trivial
path from `00183660`) and the head of the collision resolver `00183918` were
disassembled in the same run.

### Where 60fps first departs (`tools/divergence.py objects`)

Comparing positions only at vsyncs where 30fps moved, accepting 60fps one vsync
either side:

- **The ball with FIX-D matches 30fps within a tick's phase until its arch slide
  begins at vsync 41**, and the slide runs at the same real-time rate (x +3.1, +2.3,
  +2.0 per two vsyncs, against +3.1, +2.2, +1.8). The only offset is about 5 units in
  z, gained in the first ticks after the hit - as it clears Sora's swing.
- **Two ground props, `01AC2490` and `01AADB90`, start sliding at vsync 36-37 at
  60fps**, fixed or not, against 43-45 at 30fps, at the same speed once moving.
  Whatever pushes them arrives 6-8 vsyncs sooner. The ball fix does not touch it.
- **The second prop launches at vsync 51 in both arms**, into class `01C60040` - a
  different airborne class from the ball's.

### The weak hits' writer, the prop classes, the ground props' push (log 26)

From vsync 64 of the FIX-D mash, the only writer of the ball's vy apart from its own
integrator is the hit handler `002E7E48`, ra `001DAE88`, first at tick 642, writing
-10 - **genuine hits**, which connect at 60fps where they do not at 30fps.

Class vtables:

- `01C60030` -> `0034EB60`, +1C `0017C290`
- `01C60040` -> `0034EB90`, +1C `0017C8F0` (the second prop's airborne motion; reads
  none of the gravity copies; **not examined**)
- `01C60340` -> `00363410`, +1C `002EA450`

From vsync 34 of the 60fps mash, the ground prop `01AC2490`'s velocity is written by
`001114F8` (ra `001114CC`), copying `obj+0xC20` - a stored push vector - into
`obj+0x20`; also `0017C3C0` (the rest class, ra `00183198`), `0016A8DC` and the
builder's clear at `0018312C`. The push arrives earlier at 60fps with or without the
ball fix: character-side timing.

### Shipped

FIX-D over FIX-B: it also compensates the horizontal decay, reduces exactly to the
30Hz step, and passed both tick phases. Installed into the player's PCSX2 as `[60 FPS
- ball physics]` after `[60 FPS]` (log 27), with the derivation as comments, backups
`*.bak-20260915-ballfix`, and `Enable = 60 FPS - ball physics` added to the ini. The
file parsed back with 8 groups and the installed words identical to the tested ones.
The acceptance test then passed against the installed file at both tick phases.
One run came back with the oracle never lifting the ball; it passed twice on rerun
with identical numbers - most likely a controller touched, since PCSXROO reads real
pads.

**Conclusion.** The ball's physics bug is found and fixed: every isolated
measurement of its flight matches 30fps. The remaining juggling difference belongs
to Sora's combat and movement timing under `[60 FPS]` - when his swings connect, and
when the props around him are pushed - which is a separate system, not investigated.

Also changed on the player's side of PCSXROO for this work: PCSXROO's KH2 patch file
and ini (with `60 FPS` disabled there), its memory cards replaced by the player's
(old ones in `memcards\bak-20260915`), and slot 1 holding the Sandlot state.

---

## 2026-09-15 - PCSXROO bugs found on the way

Fixed on the PCSXROO fork, one branch and PR each, not merged:

- **PR #1 - shutting down a paused VM hung in "stopping".** `shutdown` set the
  stopping state directly; a paused Qt emulator thread waits in its event loop and
  nothing woke it. It now goes through `Host::RequestVMShutdown(false, false,
  false)`, the path a game's own shutdown request takes. Smoke test 31/31.
- **PR #2 - a stray pause after an interrupted frame-advance.** A breakpoint that
  cut a frame-advance short left the remaining frames queued, so a later `run`
  paused itself about a second later. `VMManager::SetState` now clears the count on
  any pause or stop. Smoke test 30/30.
- **PR #3 - document that expression numbers are hex.** `bp add 1227728` is decimal,
  but `--cond "t5 == 28170704"` means `0x28170704`. Docs only; changing the parser
  would change PCSX2's own debugger.

The "breakpoints do not stop during frame-advance" note was wrong and was corrected.
The PCSXROO build in its `bin\` has PR #2's fix but not PR #1's until both merge.

---

## 2026-09-15 - this repository

Built as the BT3 repo's sibling, with one rule set by the user: "The installation
for the patch and the repo should only modify the existing db patched to be updated
with our stuff. We should not have other people's patches or code kept in our repo,
we don't own it". PCSX2's community patch repository declares no licence either.

- `[60 FPS - ball physics]` ships as a group: all ours, three of its words the game's
  own relocated instructions.
- `[Widescreen 19.5:9 - S24 Ultra]` ships as a change set: 11 of its 15 lines are
  ElHecht's verbatim. `tools/install.py --widescreen` rebuilds it from the user's own
  16:9 group after checking its 14 lines and the five words it replaces.
- The database entry the installer builds from was read out of the player's
  `patches.zip`: ElHecht's 16:9 with exactly the words expected, and PeterDelta's
  `[60 FPS]`. No `Remove Blur` or `Swap X and O` in that entry - those came from the
  player's own file - so the installer starts from whichever file the user already
  has, at the text level, leaving every other block byte for byte.
- ELF layout for `identity.py`: a single RWX `main` section `00100000..0037A4B4`,
  `.ctors`/`.dtors`, `.reginfo` at `0037A800` (so `$gp` = `0037A800`), `.bss` to
  `01E4C868`, entry `0010001C`.
- Every scratch script was ported to a maintained tool (`docs/tools.md`), and the
  session's scripts and run logs were archived under `wip/`, with user paths
  replaced and other authors' patch lines redacted.
- Verified before publishing: every tool compiles and answers `--help`;
  `export.py --check` and `mkballfix.py --check` pass; `install.py --status` finds
  both groups installed with words matching this repo, and `--dry-run --widescreen`
  reports nothing to change on the player's install; the offline tools reproduce
  the numbers above from the saved traces.

---

## 2026-09-15 - global audit: the engine, Sora's jump, and the shared velocity step

The user asked for a global fix - "60fps should behave the same as 30, just look
better" - and for this project to find what to test on its own. The plan, the
players' reported defects and the state of every system are kept in
[`global-audit.md`](global-audit.md).

### How the engine keeps time

The frame routine `0014D060` waits until at least `[00349E1C] + 1` vsyncs have
passed and stores that count, capped by `[0036B0F8]`, as delta. Stock: wait 1, delta
2. `[60 FPS]`: wait 0, delta 1. So the engine counts in 60 Hz units and anything that
scales by delta is already right; the defects are per-frame steps.

`[60 FPS]`'s third word lowers `0036EF20`, the threshold of a fixed-step accumulator
in `001E6280` - assert strings name it `partMng.c` / `pppPart.c`, the particle and
effect system. It adds delta (`001DD43C` -> setter `001E7008`) and steps each time
the sum reaches the threshold: 30 steps a real second at 60fps with the stock 2.0, 60
with 1.0. A RAM sweep (`tools/ratesweep.py`, Sandlot idle) found integer state that
is 2x under `[60 FPS]` and 1x with 2.0 restored. Effects, not physics; not changed.

The same sweep found no float that moves twice as far at idle. Physics defects only
show in motion.

### Community issues and addresses

A 2015 PCSX2 forum list of Kingdom Hearts 60 FPS issues and a 2017 follow-up name:
the Grandstander ball rising half as high, "gravity slightly increased", reaction
commands (the Saix data battle), Quick Run distance halved, timers filling twice as
fast (lanterns, Solar Sailer), the Atlantica music game, bosses, cutscene voice cues,
and effects at double speed. The Garden of Assemblage ROM edition's PCSX2-EX Lua
script publishes this disc's game-state addresses; they are recorded as facts in
`tools/game/world.py`. The user's memory card holds three saves, all in Twilight
Town (`tools/memcard.py`).

### Static scan

`tools/integrators.py` lists every `field = field op constant` float update: 89 add
or subtract delta (correct timers); one uses a direct data constant as an integrator
(the ball's gravity); 14 read the parameter table `[00352130]`, 11 of them the ability
tuning switch `001C31E8`, which is not per-frame. The player's and enemies' motion
does not appear: it comes through pointers the scan cannot follow.

### Sora

`tools/findplayer.py`'s first filter found nothing; offline, walking Sora away and back
from the Twilight Town state showed his position at `01A94440 + 0x540`, with copies at
`+0x70`, `+0x590`, `+0x5C0` and `+0x840`, and cached at `00341720` in data. The
object the ball investigation called "the second prop" was Sora all along; the
"ground props" `01AADB90` and `01AC2490` are Donald and Goofy.

### The short hop

`tools/movetest.py` on Sora's position, jump on Circle (Swap X and O is on):

| hold | 30fps peak | 60fps peak |
|---|---|---|
| tap / 6 / 10 vsyncs | 115.08 | 103.53 |
| 15 vsyncs | 152.32 | 144.43 |
| 17 vsyncs | 165.38 | 159.31 |
| 40 (held) | 185.00 | 185.00 |

A trace of the object (`tools/objtrace.py`) showed a closed-form arc: a rise with
duration `+0xD4` = 30.108 and height `+0xDC` = -185 on a clock `+0xD0` that advances
by delta, then a short apex arc (duration 5.0, height 5.102), then a fall under
0.408163. Heights matched sample for sample - until the switch to the apex arc, which
came at clock 8 at 30fps (y 440.003) and 7 at 60fps (451.575). A write watchpoint on
`+0xD4` stopped in the arc setup `0017C42C`; the saved return address led to the jump
controller `0017C690`, which cuts a released jump once `6.0 < clock`. At 30fps the
clock is 2, 4, 6, 8.

**`[60 FPS - short hop]`** re-does that compare in a cave and lets the cut happen only
when the clock, converted to an integer, is even. Results 115.10, 152.34, 165.39,
185.00. Nothing branches into the displaced words (`0017C798..0017C7A0`).

### The shared velocity step

An air combo (jump, Cross four times) matched in height and fell short in distance:
195.02 at 30fps, 131.43 at 60fps. Sora's horizontal velocity decayed by 0.95 a frame,
the same sequence per frame at both rates. The factor is `[0036C528]`, passed by the
airborne motion `0017C8F0` through `0017C870` to `00184540`. PCSXROO's VU-aware listing
of `00184540`:

    with input speed +0x1C > 0:  v = v*k1 + (facing +0x10 * speed) * (1 - k1)
    without:                     v = v*k2
    displacement = v * delta

Nineteen routines call it. A grounded combo went the other way - 286.61 at 60fps
against 244.46 - because the blend reaches its target twice as fast.

**`[60 FPS - friction]`** takes both factors' square root at 60fps. The first version
zeroed every factor and deleted the lunge (path 0.00): a breakpoint at `00184560`
conditional on Sora showed f20 and f21 = 0. The R5900 FPU's SQRT takes its operand
from **ft**, not fs as standard MIPS has it, so `sqrt.s f20, f20` encoded the MIPS way
computed `sqrt(f0)`. Corrected, the factors read 0.9487 and 0.9747, and the lunge
velocity runs 5.235, 5.102, 4.973, 4.847 - the 30fps values every second frame.
Results: air combo 194.68, ground combo 245.03, run-and-stop 287.62 (287.63 at 30fps),
jumps unchanged, the ball's single hit 342.24 / 88 (341.85 / 88).

**Nothing at 30fps.** The same air combo, tap jump and ground combo with and without
all three groups at 30fps: Sora's object memory identical, 0 differing words.

### Pad input between arms

The unpatched 60fps arm's numbers moved between runs (peak 146.80 against 156.57). A
pad release sent while paused only queues, so the last button of one arm was still
down on the first frame of the next. `start_arm` now flushes the pad before loading.

### The juggle, with every group

Still off: 30 taps give airtime 214 at 60fps against 125-142 at 30fps, at both input
phases, so it is systematic. A breakpoint on the ball's vy write (`002E7EE8`, `t5` =
the ball) counts the hits: at 30fps two pop-ups; at 60fps a pop-up, weak hits (-10)
at Sora's attack clock 16, 16, 12, 16 and a side swipe (-42) at 17. The even clocks
rule out a sampling grid alone. Aligned per vsync, the arms first part at the ball's
launch - it rises through Sora's swing and is pushed out of contact to a z 5.3 units
different - and a later swing's push-outs total 39.5 units at 30fps against 33 at
60fps. Collision resolution evaluated at a finer step; no per-frame rate term in it
has been found.
