# Build confidence

Which build to trust, and why. Set by testing **in play**, not by measurement.
Newest at the top. `patch/` currently holds **v03**.

What each version changed and discovered is in [`versions/`](versions/README.md).
This page is only about which build to trust.

> **\*** means verified by measurement - against the unpatched 30fps game as its
> own oracle, same save state, same input, same number of vsyncs, or for the
> widescreen group against the arithmetic of the group it is built from - but
> **not yet confirmed in play by the user**. A star is provisional. **Every
> build is starred.**

| Build | Our groups | Confidence | Notes |
|---|---|---|---|
| `v03-movement-physics` | 4: ball physics, `60 FPS - short hop`, `60 FPS - friction`, and the optional 19.5:9 widescreen | **MEASURED, NOT YET PLAYED\*** | Sora's short hops, air-combo lunges and ground combos match 30fps; every group verified to change nothing at 30fps. The juggle still differs - see v03 below |
| `v02-ball-physics` | 2: `60 FPS - ball physics`, and the optional 19.5:9 widescreen | **MEASURED, NOT YET PLAYED\*** | One hit of the Sandlot ball flies as it does at 30fps, at both game-tick phases. Long juggles still differ - see below |
| `v01-widescreen-s24` | 1: `Widescreen 19.5:9 - S24 Ultra` | **ARITHMETIC VERIFIED, NOT SEEN ON SCREEN\*** | Reproduces the 16:9 group's constants bit for bit when fed 16:9 |

None of our groups stands alone. The three physics groups compensate PeterDelta's
`[60 FPS]` from PCSX2's own database: they do nothing useful without it, and each
was run at 30fps to show it changes nothing there. The widescreen group is built
from ElHecht's `[Widescreen 16:9]`, also from that database, which must then be
switched **off**. `tools/install.py --status` shows every one of them.

## v03 - movement physics: MEASURED, NOT YET PLAYED

Two groups on top of v02, from the global audit ([`global-audit.md`](global-audit.md)):

| test (Sora, Twilight Town) | 30fps | 60fps before | 60fps + v03 |
|---|---|---|---|
| tap jump peak | 115.08 | 103.53 | 115.10 |
| air combo travel | 195.02 | 131.43 | 194.68 |
| ground combo travel | 244.46 | 286.61 | 245.03 |
| held jump, run-and-stop | 185.00, 287.63 | 185.00, 287.62 | 185.00, 287.62 |

Every group was run at 30fps too: Sora's object memory through an air combo, a tap
jump and a ground combo was identical with and without them.

**Worth watching in play:**

- short hops and jump height in general;
- how far attacks carry Sora on the ground and in the air, and how quickly he
  stops;
- **enemies and everything else that slides**: `[60 FPS - friction]` changes the
  shared velocity step for all 19 of its call sites. Two are Sora's; the other 17
  are not identified, and enemy states may be among them. No enemy has been
  measured, so this is the least verified part of the build.

**Not fixed:** the Grandstander juggle still stays up longer than at 30fps (contact
resolution, not a rate bug found); effects run at double speed under `[60 FPS]`.

## v02 - ball physics: MEASURED, NOT YET PLAYED

What is verified, all in PCSXROO from the user's own Sandlot save state:

| One hit, same real time | 30fps | 60fps before | 60fps with the group |
|---|---|---|---|
| Peak height | 341.8 | 208.8 | 342.2 (tick phase 0) / 343.5 (phase 1) |
| Pinned under the arch (vsyncs) | 14 | 3 | 14 |
| Airtime (vsyncs) | 88 | 47 | 88 / 89 |
| Fall acceleration (per vsync^2) | 0.1865 | 0.3552 | 0.1887 |

The group is tested as installed: the words in the user's PCSX2 patch file are
byte-identical to the ones that passed, and `tools/install.py --status` checks
that on every run.

**What is not fixed - long juggles.** Mashing Cross, the fixed 60fps ball stays
up longer than the 30fps ball does. Over 4 seconds at four input timings:

| | airborne | landings | mean height | max | sideways travel |
|---|---|---|---|---|---|
| 30fps | 67% | 1 | 277 +/- 1 | 346 | 159 +/- 31 |
| 60fps, no group | 74% | 1 | 158 | 231 | 380 |
| 60fps + group | 100% | 0 | 374 +/- 20 | 561 +/- 32 | 662 +/- 15 |

The ball's own flight still matches. What differs is when Sora's swings reach it:
at 60fps his weak hits (vertical velocity -10) and side swipes land at moments they
do not at 30fps, and two nearby props start sliding 6-8 vsyncs sooner - with or
without this group. That is character and combat timing under `[60 FPS]`, not the
ball, and it is uninvestigated. See [`findings.md`](findings.md), "Mashing".

**Worth watching in play:**

- whether juggling now feels easier than at 30fps (expected, per the table above);
- Sora - what these notes called "the second prop" is Sora, flying through his
  airborne motion (`0017C8F0`), which this group does not touch; v03 measured and
  fixed his movement;
- any other object of the same class (vtable `00363410`) elsewhere in the game;
  the group covers the whole class, and was only measured in the Sandlot.

**Falling back:** switch off `60 FPS - ball physics` for stock 60fps behaviour,
or `60 FPS` too for the original 30fps game. By design the group gates nothing
while the frame limiter is at 30fps (`[00349E1C]` nonzero), so leaving it on with
`60 FPS` off should change nothing - but that case was not measured.

## v01 - widescreen 19.5:9: ARITHMETIC VERIFIED, NOT SEEN ON SCREEN

The 16:9 group's widen factor is `(4/3) / (16/9) = 0.75`, loaded as an
instruction immediate, and its font fix is the same 0.75. Fed 16:9, the model
returns `3F400000`, bit for bit what the 16:9 group ships. For 19.5:9 it is
`12/19.5 = 0.6153846 = 3F1D89D9`, loaded exactly with `lui` + `ori`.

Not verified: how it looks. Nobody has confirmed it on the phone yet. Two known
questions:

- **19.5:9 or 19.3:9.** Samsung lists the S24 Ultra panel as 3088x1440, which is
  19.3:9. This group matches the BT3 patch's 19.5:9 (3120x1440) instead. If the
  picture looks slightly too wide on the device, `tools/ws-math.py --aspect
  3088:1440` gives the words for the other one.
- **Stretch.** PCSX2 has no 19.5:9 display aspect, so the group sets
  `gsaspectratio=Stretch`. It only looks right when PCSX2's output really is
  19.5:9 - fullscreen on the phone, or a stream at that shape.

**Never enable it together with `Widescreen 16:9`.** Both write the same
instruction every frame and the mix loads a wrong float.
