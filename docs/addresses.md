# Address map

Everything this project has named in Kingdom Hearts II Final Mix+ (SLPM-66675,
CRC FAF99301), with where it was established. Addresses are pnach addresses
(EE virtual, as the ELF loads them). The same constants live in code under
`tools/game/` - `timing.py`, `physics.py`, `sandlot.py`, `identity.py` - and
that code is the source of truth if the two ever disagree.

## The disc and the ELF

| | |
|---|---|
| Serial | SLPM-66675 |
| CRC | FAF99301 - the English undub patched CHD this was built on |
| Other database entries | PCSX2's `patches.zip` also has `SLPM-66675_F266B00B` and `SLPM-66675_E6FB8E10`; nothing here was tested on them |
| Boot ELF | `SLPM_666.75`, entry `0010001C` |
| Load segment | one RWX segment at `00100000`, file size `0027A800`, memory size to `01E4C868` |
| Sections | `main` (code and data together) `00100000..0037A4B4`, then `.ctors`/`.dtors`, `.reginfo` at `0037A800`, `.bss` to `01E4C868` |
| `$gp` | `0037A800`, from `.reginfo`. A live read of `00000000` came from a thread outside the game loop |
| Code scans | stop at `00340000`; code and data share the section, and every scan here used that bound |

## Frame timing

| Address | Stock | What it is |
|---|---|---|
| `0014D004` | code | timing init: registers the vsync callback `0014CF18` (through `002F33F0`) and `0014CF88` |
| `0014D060` | code | the per-frame routine |
| `0014D1CC..0014D1FC` | code | the vsync wait loop: repeats while the count of waited vsyncs is below `[00349E1C]` |
| `0014CE30` | code | setter for the vsync wait. Called with 1 at `0014CFD8` during init, and from `0023D360` / `0023D394` (function `0023D320`) with a stored value |
| `0014CE20` | code | setter for the measured-delta flag: 1 at `0014CFD0` and `0023D350`, 0 at `00224D64` and `0023D388` |
| `0014CF18` | code | vsync callback: increments `00349E04` and `00349E08` |
| `00349E04` | 0 | per-vsync clock |
| `00349E08` | 0 | vsync count since the last frame (zeroed at `0014CFF8`) |
| `00349E0C` | 1.0 | delta scale |
| `00349E10` | 1.0 | **delta**: 2.0 at 30fps, 1.0 at 60fps. 211 references in 172 functions |
| `00349E14` | 1.0 | delta before the cap |
| `00349E18` | 1.0 | 1/delta - velocity = displacement x this, in the displacement builder |
| `00349E1C` | 0 (1 after init) | **vsync wait count**. 1 at 30fps; `[60 FPS]` writes 0 |
| `00349E20` | 1 | measured-delta flag (byte). While set, a paused VM reads delta as the pre-wait count, 1.0 - see method.md |
| `0036B0F4` | 2.0 | read at `0014D0A0` in the frame routine |
| `0036B0F8` | 6.0 | delta cap, read at `0014D0F8`. `[60 FPS]` writes 1.0 |
| `0036EF20` | 2.0 | fixed-step accumulator threshold, read twice in `001E6280` (called from `001DD4E0`). `[60 FPS]` writes 1.0 |
| `0032BA24` | 0 | game mode. `[60 FPS]` puts the 30fps wait back while it reads 5 |
| `0032B920` | - | **game tick counter**: +20 per 20 vsyncs at 60fps, +10 at 30fps. The only such word in RAM |
| `0032DF74`, `0032DF84`, `00349DE8`, `00349E04`, `0034D4BC`, `0034D53C` | - | per-vsync clocks: +20 per 20 vsyncs at both rates |

The A/B arms write exactly the three words `[60 FPS]` owns - `00349E1C`,
`0036B0F8`, `0036EF20` - see `tools/game/timing.py`.

## Prop classes

A prop's class pointer is `obj+0x0C`. Hitting a prop switches its class.

| Class | Vtable | +0x1C motion | Used by |
|---|---|---|---|
| `01C60030` | `0034EB60` | `0017C290` - writes a zero vector to velocity at `0017C3F4` | every Sandlot prop at rest (8 of the 11 physics objects) |
| `01C60340` | `00363410` | `002EA450` - the airborne integrator below | the ball, airborne. The only vtable pointing at `002EA450` |
| `01C60040` | `0034EB90` | `0017C8F0` - **unexamined**, reads none of the gravity copies | the second prop, airborne |
| `01C60060` | `0034EB30` | `0017A968` | three objects at the origin |

Other vtable `00363410` entries: `+00 002EA338`, `+14 002EAA70`, `+18 002EAA68`,
`+38` = 0.392699 (pi/8), `+3C` = 50.0.

## The airborne integrator, `002EA450`

The function starts at `002EA450` (vtable +0x1C). `elfscan.py` reports
`002EA41C` because the previous function's tail has no `jr ra` in front of it.

| Address | Instruction / meaning |
|---|---|
| `002EA494` | `s6 = obj + 0x20` (velocity) |
| `002EA498` | `beql sp, s6` - copies velocity to the stack. **The hook site** |
| `002EA4AC..002EA4E0` | normalise horizontal velocity; its length in `$f01` |
| `002EA4E4..002EA50C` | horizontal speed x `[[00352130]+0x18]` (0.8), compared against `[003760C8]` (1.0) |
| `002EA524`, `002EA538` | write `obj+0x28` and `obj+0x20` |
| `002EA534` | if `vy >= 0` (falling - negative is up) skip the drag |
| `002EA548` | rising: `vy *= [[00352130]+0x20]` (0.8) |
| `002EA55C` | `vy += [00363404]` (0.408163) - the gravity word's only reader |
| `002EA564..002EA570` | `vy = min(vy, [obj+0x120])` (10.0) and store |
| `002EA574` | first instruction after the velocity block. **The fix's skip target** |
| `002EA57C..002EA590` | displacement = velocity x delta `[00349E10]` |
| `002EA7F8` | collision probe `001A7588` |
| `002EA8C0` | ground bounce: reflect with `-[00363400]` (0.8) |
| `002EA9FC`, `002EAA00` | write the bounced horizontal velocity |
| `002EAA04..002EAA1C` | displacement = velocity x delta again, on the bounce path |

Velocity is stored **per 60 Hz frame**: a trace found `obj+0x854` and `obj+0x864`
equal to height change per game tick x 1.0 at 60fps and x 0.5 at 30fps.

## Other physics code

| Address | What it is |
|---|---|
| `00183088` | displacement builder, `a0` = object. Copies `+0x540` to `+0x840`, zeroes `+0x860`, `+0x870`, `+0x880` |
| `00183384`, `0018342C` | its velocity writers: displacement x `[00349E18]` |
| `001835F8` | a displacement contributor; non-trivial path from `00183660` |
| `00183918` | collision resolver. Copies `+0x540` to `+0x590` |
| `0018A924` | writes the collision shape's Y (`01ADEAC4` for the ball) |
| `002E7E48` | **hit handler**, called from `001DAE88`. Copies a direction into velocity, zeroes its y, normalises, scales by `[a0+0xC]`, then `vy = -[a0+0x8]` at `002E7EE8`, tail-jumps `0016BD60`. Sets an absolute velocity: pop-up (0, -60, 0), side swipe (~51 horizontal, -42), weak hit (vy -10) |
| `001114F8` | copies `obj+0xC20` into velocity (`ra 001114CC`) - how the ground props get their push |
| `0019FBC4` | sibling integrator, reached by fall-through (entry near `0019FBE0`): the same horizontal factor, rising drag, gravity (its own copy `0036D440`) and cap, plus `obj+0xF8 += delta`. **Not fixed, callers unknown** |

## Constants

| Address | Value | Reader(s) |
|---|---|---|
| `00352130` | pointer | the runtime parameter block (`01CE36CC` in the Sandlot state) |
| `[00352130]+0x18` | 0.8 | horizontal decay per tick: `002EA4F8`, `0019FC54` |
| `[00352130]+0x20` | 0.8 | rising drag per tick: `002EA544`, `0019FC98` |
| `00363400` | 0.8 | restitution, negated at `002EA8C0` |
| `00363404` | 0.408163 (`3ED0FAC6`) | gravity, one reader: `002EA55C` |
| `003760C8` | 1.0 | horizontal floor, one reader: `002EA4E8` |
| `0036C1AC` | 0.408163 | `0016A99C` - apex time v/g (reached from 11 call sites and 12 data pointers) |
| `0036C510` | 0.408163 | `0017C42C` - launch speed sqrt(-2h/g) (10 callers) |
| `0036C534` | 0.408163 | `0017CA50` - fall time |
| `0036C554` | 0.408163 | `0017D130` - fall time sqrt(2h/g) (5 callers) |
| `0036C8AC` | 0.408163 | `001846F4` - apex time v/g (reached by `j` from `00173ECC`) |
| `0036D440` | 0.408163 | `0019FBC4` - the sibling integrator |

## Object layout (props)

| Offset | Meaning |
|---|---|
| `+0x0C` | class pointer |
| `+0x20` | velocity vec4, per 60 Hz frame; `+0x24` is vy, negative is up |
| `+0x120` | terminal fall speed, 10.0 |
| `+0x540` | position |
| `+0x560`, `+0x870` | added to the displacement without delta - zero in every trace |
| `+0x590` | previous position, from the collision resolver |
| `+0x840` | position at builder entry |
| `+0x850` | requested displacement / delta, before collision |
| `+0x860` | resolved displacement / delta, after collision |
| `+0xC20` | stored push vector, copied into velocity at `001114F8` |

## The fix, `[60 FPS - ball physics]`

| Address | |
|---|---|
| `002EA498` | `j 000FE000` (was `53B60004 beql sp, s6, 002EA4AC`) |
| `002EA49C` | `nop` (was `AFA00004 sw zero, 4(sp)`) |
| `000FE000..000FE03C` | the cave, 16 words |
| `002EA574` | where an odd tick jumps |
| `002EA4AC` | where an even tick, or 30fps, resumes |

The cave sits in the zero run `000FD094..00100000` (3035 words), zero both in
live RAM and in the user's save state. `000FD050..000FD090` is taken by the
`Swap X and O` group from PCSX2's database.

## Widescreen

| Address | What it is |
|---|---|
| `00106DE8` | the projection routine the 16:9 group rewrites |
| `00106E10`, `00106E28` | the 4:3 base, 0.8, loaded with `lui` / `ori` by the 16:9 group |
| `00106E54` | `lui $k1` - the **widen factor**, 0.75 at 16:9 |
| `00106E58` | `mtc1 $k1, $f30` at 16:9; `ori` in our group |
| `00106E60` | a stock `nop`; our group moves the `mtc1` here |
| `00106E70`, `00106E74` | `f31 *= f30`, stored to `[cam+0x4C]` |
| `0036CE94`, `0036CE98`, `0036CE9C` | font x-scale, stock 1.0, 0.75 at 16:9 |
| `0036A0BC` | cutscene zoom, stock 416.0 - aspect-independent |
| `00166DB6`, `001AC8D8` | depth-of-field byte and subtitle height - aspect-independent |

## Sandlot save state (heap - not constants of the game)

Valid only in the user's save state 1, Twilight Town Sandlot. See
`tools/game/sandlot.py`.

| Address | What it is |
|---|---|
| `01ADD9D0` | the ball |
| `01ADEAC0` | the ball's collision-shape centre x, y, z |
| `01A94440` | the second prop |
| `01AC2490`, `01AADB90` | the two ground props that slide early at 60fps |
| `01CE36CC` | the runtime parameter block |
| `01A8C4F0`, `01AABC30`, `01AC12B0`, `01AD4420`, `01AD86D0`, `01AFD310`, `01B09620` | the other physics objects through the builder |
| `0037EC30` | **not an object**: a stack AABB centre every object's collision computes. It looked exactly like the ball at 60fps |
