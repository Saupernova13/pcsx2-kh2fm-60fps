# Global audit - making 60fps behave like 30fps everywhere

The goal, from the user: "60fps should behave the same as 30, just look better",
for as many areas of the game as possible. The user does not know the game's
systems, so this project finds what to test as well as how.

This is a living document: the plan, what is known, and the state of every system.
Detailed derivations go to [`findings.md`](findings.md) as each one lands, and the
rules the instruments taught are in [`method.md`](method.md).

Last revised 2026-09-15, at v03.

## Where it stands

| | |
|---|---|
| Fixed and measured | the Sandlot ball's flight (v02); short hops and released jumps; friction, lunges and acceleration through the shared velocity step (v03) |
| Verified to change nothing at 30fps | all three physics groups: Sora's object memory is byte-identical with and without them through an air combo, a tap jump and a ground combo |
| Found, not fixed | the Grandstander juggle still stays up longer; effects step at double speed under `[60 FPS]` |
| Measured and already right | a held jump (185.00 at both rates); running and stopping (287.62 against 287.63) |
| Not measured | enemies, bosses, reaction commands, abilities, minigame and event timers, cutscenes, camera, menus |
| Confirmed in play | nothing yet |

## How the engine keeps time (established)

- **Delta is vsyncs per frame, in 60 Hz units.** The frame routine `0014D060` waits
  until at least `[00349E1C] + 1` vsyncs have passed and stores the count as delta
  (`00349E10`), capped at `[0036B0F8]`. Stock: wait 1, so delta = 2 (30fps).
  `[60 FPS]`: wait 0, delta = 1. So the engine was written in 60 Hz units and code
  that scales by delta is already correct at 60fps. Delta has 211 readers.
- **The bugs are code that runs once per frame without delta** - as the ball's
  drag and gravity did, and the jump cut and velocity step still did in v02 -
  authored for 30 Hz.
- **`[60 FPS]` changes two more words, and one of them doubles the effects.**
  - `0036EF20`, stock 2.0, `[60 FPS]` 1.0: the threshold of a fixed-step
    accumulator in `001E6280` (`partMng.c` / `pppPart.c` - the particle and effect
    system). Each frame it adds delta (set through `001E7008` from `001DD43C`) to a
    per-object accumulator and steps the object each time the sum reaches the
    threshold. With the stock 2.0 that is 30 steps a real second at either rate -
    already correct at 60fps. At 1.0 it is 60 a second. **Confirmed**:
    `tools/ratesweep.py` at Sandlot idle found four integer words stepping twice as
    often under `[60 FPS]` and at the 30fps rate in the `60t2` arm (`[60 FPS]` with
    the stock threshold). Not changed yet - it was outside this round's physics
    goal, and nothing has checked what else that step drives.
  - `0036B0F8`, the delta cap, stock 6.0, `[60 FPS]` 1.0: only matters when a frame
    takes more than one vsync. With 1.0 the game slows down on a lag frame instead
    of catching up - a behaviour difference from 30fps under load, not at speed.

## Known 60fps defects reported by players

From the PCSX2 forum's list of Kingdom Hearts 60 FPS issues (2015, older patch that
only forced the vsync wait; `[60 FPS]` inherits the same core) and a 2017 follow-up
thread. Sources: [original thread](https://forums.pcsx2.net/Thread-Kingdom-Hearts-2-Final-Mix-60fps-hack),
[2017 thread](https://forums.pcsx2.net/Thread-Kingdom-Hearts-2-Final-Mix-60fps-hack%EF%BC%88solve-some-problems-including-the-gravity%EF%BC%89).

| Reported defect | Where | Status here |
|---|---|---|
| Grandstander ball rises half as high | Twilight Town Sandlot minigame | **one hit fixed (v02)**; the juggle with every group still stays up longer - open |
| Gravity slightly increased | everywhere | **for Sora, not gravity**: a held jump peaks at 185.00 at both rates. What came out lower was a released jump, cut one clock step early - **fixed (v03, short hop)**. Enemies not measured |
| Saix data battle reaction command impossible "due to the gravity thing" | Data Saix | open - out of reach of the saves |
| Reaction commands broken against bosses | combat | open |
| Quick Run distance halved | Sora's ability | open - not measured; the ability tuning switch `001C31E8` is the first place to look, and Sora's own motion now runs through the fixed velocity step |
| Timers fill twice as fast: lantern lighting, Solar Sailer fight | Beast's Castle, Space Paranoids | open |
| Atlantica music minigame timing off | Atlantica | open |
| Bosses harder; Larxene's final move rotates twice as fast; Sephiroth | combat | open |
| Cavern of Remembrance harder | Hollow Bastion | open |
| Voice cues in cutscenes at the wrong time | cutscenes | open |
| Effects and gummy ship at double speed | effects, gummy ship | **effects: cause confirmed** - `[60 FPS]`'s particle step threshold, above; not changed. Gummy ship not looked at |
| World ring display in the world map | gummy map | open |
| FMVs twice as fast | FMVs | `[60 FPS]` restores 30fps in game mode 5 |

## What this project can reach

- **The user's saves** (memory card 2, read with `tools/memcard.py`): three KH2FM
  slots, all written 2026-09-13 - `[01]` LV02 1:57, `[02]` LV05 2:59, `[03]` LV06
  3:26. The save header's world byte (+0x0C) is 02, Twilight Town, in all three
  (rooms 0B, 12, 02): Roxas's prologue. That covers field movement, the Struggle
  fights and tournament, the part-time job minigames (Grandstander is the Sandlot
  juggle), Dusk fights, cutscenes and menus - each a play-through away from a save.
- **PCSXROO save states**: slot 1, the Sandlot with Sora, Donald and Goofy
  (Grandstander) - every measurement so far. No state has been cut at a fight yet,
  which is why no enemy has been measured.
- **Later worlds** are out of story reach. The community's warp recipe (write the
  world/room/door/map/battle/event ids to `NOW`, see `tools/game/world.py`) may
  reach their rooms for movement, enemy and timer tests; untested.

## Community address map

`tools/game/world.py` records the PS2 addresses published in the Garden of
Assemblage ROM edition's PCSX2-EX Lua script, whose PCSX2 branch explicitly
covers this disc's CRC (FAF99301): location, save, party pointers, reaction
command, battle status, cutscene timer and length, Atlantica and gummi data. Two
agree with what this project measured on its own: `00349E0C` (their "Game Speed",
this project's delta scale) and `00349DE8` (a per-vsync clock in both arms).
Only the addresses are recorded - the script itself is not this project's.

## Method

1. **RAM rate sweeps, per scene.** `tools/ratesweep.py` samples RAM every 2 vsyncs
   in the 30fps arm, the `[60 FPS]` arm and the stock-threshold arm, and flags every
   word whose total variation or reversals double; `tools/ratediff.py` does the same
   for steady ramps and integer clocks, and `classify` names which of `[60 FPS]`'s
   words drives each one. At Sandlot idle this found the effect step and **no float
   moving twice as far**: physics defects only show in motion.
2. **Motion tests, per system.** `tools/movetest.py` scripts an input from one state
   and compares a position vector at 30fps, 60fps and 60fps + groups: peak and when,
   airtime, fall, horizontal path. The scripts so far: a tap jump, holds of 6, 10, 15
   and 17 vsyncs, a held jump, an air combo (jump, Cross four times), a ground combo,
   running 40 vsyncs then stopping, the ball's single hit and the mash. A metric that
   differs names the system.
3. **Object traces find the field.** `tools/objtrace.py capture` dumps the whole
   object every vsync in each arm, and `fields` ranks every float lane by how far it
   travels at 60fps against 30fps. A lane that matches sample for sample until a
   switch (the jump arc's clock) or decays once per frame (velocity) points at the
   code; a write watchpoint on the field (`tools/watch.py`), or a breakpoint in the
   shared routine with a condition on the object's register, names the writer.
4. **Fix once per function.** Each group is generated from the ELF with its
   displaced words checked and decoded back (`mkballfix.py`, `mkjumpfix.py`,
   `mkfrictionfix.py`). A code-level fix covers every object and scene that runs that
   code, which is the point of a global audit.
5. **Acceptance against the 30fps oracle**, then **every earlier acceptance test
   again** with all groups on.
6. **No-op at 30fps.** Every group also runs in the `30fix` arm; `objtrace` must show
   0 differing words against plain 30fps through the same scripts.

## Static scan for per-frame integrators (`tools/integrators.py`)

Every `field = field {+,-,*} constant` float update whose constant comes from data
or through a data pointer, with the result stored back to the same field:

- 89 sites add or subtract delta itself - timers kept in delta units, correct.
- **Only one direct data constant is an integrator: the ball's gravity** `002EA560`.
  The other four direct hits add run-time variables (the particle step's delta copy
  `00352BE0`, and `0034A3F8`, `0035EB2C`).
- **14 sites read constants through the global parameter table `[00352130]`**
  (`01CE36CC` at run time), which is where the game keeps its tuning:
  - `002EA548` and `0019FC9C`: the prop drag, `[+0x20]` - the ball's, fixed, and the
    sibling integrator's, not fixed.
  - `0017AA2C`: `vy *= [+0x44]`, no delta in the function - candidate.
  - `001D039C`: `+0xB6C += [+0xD4]`, function also reads delta - probably fine.
  - `001C31E8` (11 sites, params `+0x11C..+0x174`): **not** a per-frame update - a
    switch over ability ids 0x186-0x21C that adds or multiplies tuning into a stats
    struct as abilities apply. The table holds ability tuning, which makes it the
    first place to look for Quick Run's distance.
- `001C9EE8`: `+0x18 += [[00351F34]+4]`, a state handler (pointer table
  `00351F58`) - candidate.

Neither of v03's defects appears: the jump cut is a compare, not an update, and the
velocity step is VU0 code taking its factors as arguments. Scans find candidates;
motion tests find defects.

## Systems

| System | Evidence so far | Status |
|---|---|---|
| Ball / prop airborne integrator `002EA450` | one hit: peak 341.8 (30fps), 208.8 (60fps), 342.2 (fixed); airtime 88, 47, 88 | **fixed, `[60 FPS - ball physics]`** (v02) |
| Sora's jump: short hops and released jumps (`0017C690` cuts the rise when the clock passes 6.0; 60fps cut one unit early) | tap peak 103.5 vs 115.1; odd releases 144.4 vs 152.3, 159.3 vs 165.4 | **fixed, `[60 FPS - short hop]`**: 115.10, 152.34, 165.39 |
| Sora's held jump and fall: closed-form arc `0017C930` on a delta clock | held peak 185.00 at both rates | matches - nothing to fix |
| Sora's airborne motion `0017C8F0` (class `01C60040`) | examined: jump clock, velocity step and arc height through `0017C870` | covered by the jump and velocity-step rows |
| Shared velocity step `00184540` (friction k2 and input blend k1, per frame, 19 call sites: Sora ground `0017C2B8` and air `0017C8AC`, 17 unidentified) | air-combo lunge 131.4 vs 195.0; ground combo 286.6 vs 244.5 | **fixed, `[60 FPS - friction]`** (k^(1/2) at 60fps): 194.7, 245.0 |
| Sora walking and running | run 40 vsyncs then stop: 287.62 at 60fps with every group, 287.63 at 30fps | matches |
| Mashing the Sandlot ball with every fix on | 30 taps: airtime 214 vs 125-142 at both input phases. Clean hits (bp `002E7EE8` on the ball): 30fps 2 pop-ups; 60fps a pop-up, weak hits at Sora clock 16, 16, 12, 16 and a side swipe at 17 | open - not a sampling grid alone (even clocks hit too); the arms part at launch by 5.3 units in z from contact push-out, and a swing's push-outs total 39.5 (30fps) vs 33 (60fps): collision resolution at a finer step, no rate term found |
| Donald and Goofy following Sora | in the v02 mash they started sliding 6-8 vsyncs sooner at 60fps (push vector `+0xC20`, copied at `001114F8`); their ground motion calls the velocity step | open - not re-measured with v03 |
| Particle/effect fixed step `001E6280` (`[60 FPS]` threshold 2.0 -> 1.0) | int sweep: 4 words 2x under `[60 FPS]`, 1x with the stock threshold | cause confirmed; not changed |
| Sibling integrator `0019FBC4` | static: the ball's drag and gravity pattern, no callers found | open - no scene known to run it |
| `0017AA2C`: `vy *= [+0x44]`, no delta | static scan | candidate, unmeasured |
| `001C9EE8`: state handler `+0x18 += [[00351F34]+4]` | static scan | candidate, unmeasured |
| Closed-form ballistic solves `0016A99C`, `0017C42C`, `0017CA50`, `0017D130`, `001846F4` | results in 60 Hz units | `0017C42C` sets up the jump arc, which matches; the rest open |
| Enemy movement, attacks, rotations | - | open - no state at a fight yet |
| Reaction command windows | - | open |
| Ability timers (Quick Run etc.) | ability tuning `001C31E8` | open |
| Minigame and event timers | - | open |
| Cutscene voice cue timing | - | open |
| Camera | - | open |
| Menus and HUD animation | - | open |

## Next, in order

1. **Play v03.** Short hops, how far attacks carry Sora and how he stops, and
   anything that slides - nothing here is confirmed in play.
2. **A state at a fight.** Play one of the prologue saves to a Struggle or Dusk
   fight in PCSXROO and save a slot there. Then `movetest.py` and `objtrace.py` on an
   enemy: knockback, lunges, launches - and a breakpoint on `00184540` to name its
   17 unidentified call sites.
3. **The juggle's contact push-out.** Break in the collision resolver `00183918` on
   the ball and on Sora through the launch, both arms, and compare the push-out per
   iteration.
4. **Effects.** Find what else the particle step `001E6280` drives, then decide
   whether a group of ours should put its threshold back to 2.0 after `[60 FPS]`.
5. **The static candidates** `0017AA2C`, `001C9EE8`, `0019FBC4`: a breakpoint on
   each to find a scene that runs it, before measuring anything.
6. **Timers from the players' list** - Quick Run, reaction command windows, the
   minigame timers - as saves reach them.
