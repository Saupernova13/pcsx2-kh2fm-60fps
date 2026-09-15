# Global audit - making 60fps behave like 30fps everywhere

The goal, from the user: "60fps should behave the same as 30, just look better",
for as many areas of the game as possible. The user does not know the game's
systems, so this project finds what to test as well as how.

This is a living document: the plan, what is known, and the state of every system.
Detailed derivations go to [`findings.md`](findings.md) as each one lands.

## How the engine keeps time (established)

- **Delta is vsyncs per frame, in 60 Hz units.** The frame routine `0014D060` waits
  until at least `[00349E1C] + 1` vsyncs have passed and stores the count as delta
  (`00349E10`), capped at `[0036B0F8]`. Stock: wait 1, so delta = 2 (30fps).
  `[60 FPS]`: wait 0, delta = 1. So the engine was written in 60 Hz units and code
  that scales by delta is already correct at 60fps. Delta has 211 readers.
- **The bugs are code that runs once per frame without delta** - as the ball's
  drag and gravity did - authored for 30 Hz.
- **`[60 FPS]` changes two more words, and one of them is suspect.**
  - `0036EF20`, stock 2.0, `[60 FPS]` 1.0: the threshold of a fixed-step
    accumulator in `001E6280` (`partMng.c` / `pppPart.c` - the particle and effect
    system). Each frame it adds delta (set through `001E7008` from `001DD43C`) to a
    per-object accumulator and steps the object each time the sum reaches the
    threshold. With the stock 2.0 that is 30 steps a real second at either rate -
    already correct at 60fps. At 1.0 it is 60 a second: **every effect stepped this
    way runs at double speed under `[60 FPS]`**. Hypothesis; the `60t2` arm tests it.
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
| Grandstander ball rises half as high | Twilight Town Sandlot minigame | **one hit fixed (v02)**; mashing still differs |
| Gravity slightly increased | everywhere | open - Sora and enemies not yet measured |
| Saix data battle reaction command impossible "due to the gravity thing" | Data Saix | open |
| Reaction commands broken against bosses | combat | open |
| Quick Run distance halved | Sora's ability | open |
| Timers fill twice as fast: lantern lighting, Solar Sailer fight | Beast's Castle, Space Paranoids | open |
| Atlantica music minigame timing off | Atlantica | open |
| Bosses harder; Larxene's final move rotates twice as fast; Sephiroth | combat | open |
| Cavern of Remembrance harder | Hollow Bastion | open |
| Voice cues in cutscenes at the wrong time | cutscenes | open |
| Effects and gummy ship at double speed | effects, gummy ship | open - matches the accumulator hypothesis |
| World ring display in the world map | gummy map | open |
| FMVs twice as fast | FMVs | `[60 FPS]` restores 30fps in game mode 5 |

## What this project can reach

- **The user's saves** (memory card 2, read with `tools/memcard.py`): three KH2FM
  slots, all written 2026-09-13 - `[01]` LV02 1:57, `[02]` LV05 2:59, `[03]` LV06
  3:26. The save header's world byte (+0x0C) is 02, Twilight Town, in all three
  (rooms 0B, 12, 02): Roxas's prologue. That covers field movement, the Struggle
  fights and tournament, the part-time job minigames (Grandstander is the Sandlot
  juggle), Dusk fights, cutscenes and menus.
- **PCSXROO save states**: slot 1, the Sandlot (Grandstander). More are cut from
  the memory card saves as they are needed.
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

## Method

1. **Global RAM rate audit, per scene.** `tools/ratesweep.py` samples RAM every 2
   vsyncs in the 30fps arm, the `[60 FPS]` arm and the stock-threshold arm, and flags
   every word whose variation or reversals double. `tools/ratediff.py` does the same
   for steady ramps and integer clocks. Each flagged word is then traced to its
   writer (`tools/watch.py`), grouped by function, and fixed once per function - a
   code-level fix, so it covers every object and scene that runs that code.
2. **Scenes.** Every scene the user's saves can reach is swept idle and with input:
   field (idle, walking, running, jumping), combat, minigames, cutscenes, menus.
3. **Acceptance per system**, against the 30fps oracle, as `tools/balltest.py` does
   for the ball.
4. **No regressions**: every fix is re-checked against the earlier acceptance tests.

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

The player's and enemies' gravity do not appear, so they come through object or
move-set pointers the static scan cannot follow. They are found live.

## Systems

| System | Evidence so far | Status |
|---|---|---|
| Sora's jump: short hops and released jumps (`0017C690` cuts the rise when the clock passes 6.0; 60fps cut one unit early) | tap peak 103.5 vs 115.1; odd releases 144.4 vs 152.3, 159.3 vs 165.4 | **fixed, `[60 FPS - short hop]`**: 115.10, 152.34, 165.39; held jump unchanged at 185.00 |
| Shared velocity step `00184540` (friction k2 and input blend k1, per frame, 19 callers: Sora ground/air, objects, enemies) | air-combo lunge 131.4 vs 195.0; ground combo 286.6 vs 244.5 | **fixed, `[60 FPS - friction]`** (k^(1/2) at 60fps): 194.7, 245.0; run-and-stop unchanged |
| Ball / prop airborne integrator `002EA450` | measured | fixed (v02) |
| Mashing the Sandlot ball with every fix on | 30 taps: airtime 214 vs 125-142 at both input phases. Clean hits (bp `002E7EE8` on the ball): 30fps 2 pop-ups; 60fps a pop-up, weak hits at Sora clock 16, 16, 12, 16 and a side swipe at 17 | open - not a sampling grid alone (even clocks hit too); the arms part at launch by 5.3 units in z from contact push-out, and a swing's push-outs total 39.5 (30fps) vs 33 (60fps): collision resolution at a finer step, no rate term found |
| Particle/effect step: `[60 FPS]` sets the accumulator threshold 2.0 -> 1.0 | int state 2x under `[60 FPS]`, 1x with 2.0 restored | open - effects, not physics |
| Particle/effect fixed step `001E6280` (`[60 FPS]` threshold) | static; int sweep: 4 words 2x under `[60 FPS]`, 1x with the stock threshold | testing |
| Sibling integrator `0019FBC4` | static | open |
| Second prop motion `0017C8F0` | static | open |
| Sora movement, jump, gravity | - | open |
| Enemy movement, attacks, rotations | - | open |
| Reaction command windows | - | open |
| Ability timers (Quick Run etc.) | - | open |
| Minigame and event timers | - | open |
| Cutscene voice cue timing | - | open |
| Camera | - | open |
| Menus and HUD animation | - | open |
