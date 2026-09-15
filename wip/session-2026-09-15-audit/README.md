# Session 2026-09-15 - global audit

The session that produced v03. The user's request: "I want a global fix for as many
areas of the game as possible. 60fps should behave the same as 30, just look better.
Unlike BT3 I don't have decades of experience playing this game, knowing the
different systems, what to test specifically, etc. YOu are going to have to drive
this all yourself, with the approaches from BT3 and resources online/what you can do
as your guide". The full account is in
[`docs/findings.md`](../../docs/findings.md), "2026-09-15 - global audit", and the
plan it left is [`docs/global-audit.md`](../../docs/global-audit.md).

Everything here is archived as it ran. User-profile paths are replaced with
`%USERPROFILE%`, the session's scratch folder with `<session scratchpad>`, and lines
from other authors' patches with a `redacted` marker. Nothing else is edited,
including output that turned out to be wrong - the notes below say which.

**Left out, because they are not this project's:** five runs that printed other
people's code or documentation - the Garden of Assemblage ROM edition's Lua script
(fetched, grepped for addresses, and its address usage extracted) and the KH2 Lua
Library's README, file list and address file. Only the addresses they publish are
kept, as facts with their source, in `tools/game/world.py`. The forum threads read
in the browser are not archived either; `docs/global-audit.md` links them.

## scripts/

The session's scratch scripts, run from the repo root with `tools/` on the path.
They were one-offs around the maintained tools; where one grew into a tool, the port
is named.

| Script | What it did | Port |
|---|---|---|
| `kh2_setter_calls.py` | every `jal` to the accumulator increment setter `001E7008`, with context | `elfscan.py callers 001E7008` |
| `kh2_wait_boot.py` | waited for PCSXROO to finish booting the game | - |
| `kh2_strings.py` | the assert strings beside the accumulator's data: `partMng.c`, `pppPart.c` | - |
| `kh2_arm_check.py` | loaded the state and proved the 30, 60 and 60t2 arms by ticks per 20 vsyncs | `ratediff.start_arm()` |
| `kh2_saves.py` | titles and header bytes of the three extracted saves | `memcard.py` |
| `kh2_rs_strict.py` | the idle sweep re-ranked with strict 2x criteria, split by lever | `ratesweep.py report` |
| `kh2_fp_diag.py` | walked the player and listed the floats that moved most | `findplayer.py` |
| `kh2_fp_save.py` | saved walk and idle snapshots (`work/fp-walk.npz`) and counted survivors per filter stage | `findplayer.py` |
| `kh2_fp_heap.py` | vec4s with w = 1.0 near ground height that walked: Sora, Donald, Goofy | `findplayer.py`, which adds the class check |
| `kh2_jump_rows.py` | Sora's height per vsync through a jump, both rates | `movetest.py --save` |
| `kh2_jump_fields.py` | the jump arc fields `+0xD0..+0xDC` per vsync, both rates | `objtrace.py fields` |
| `kh2_jump_writer.py` | a write watchpoint on `+0xD4` during a jump: it stops in the arc setup `0017C42C` | - (`watch.py` drives only the Sandlot schedule) |
| `kh2_arc_consts.py` | the floats around `0036C500`: 6.0, 5.0, 5.102 | - |
| `kh2_jump_caller.py` | the saved return address at that stop: the jump controller `0017C690` | - |
| `kh2_aircombo_rows.py` | Sora's horizontal motion channels per vsync through the air combo | `objtrace.py fields` |
| `kh2_friction_dis.py` | `00184540` through PCSXROO's VU-aware disassembler | `Roo.dis` in PCSXROO |
| `kh2_aircombo_fix_rows.py` | the same with the first friction group on: the lunge gone | `objtrace.py fields` |
| `kh2_friction_bp.py` | a breakpoint after the friction cave conditional on Sora: f20 and f21 at 0.0 with the first group | - (method.md, rules 18 and 19) |
| `kh2_mash_align.py` | Sora and the ball per vsync through the mash, and where the arms first part | - (`divergence.py` covers the ball only) |
| `kh2_swing_rows.py` | Sora's swing channels and the ball's x and z around the launch | `objtrace.py fields` |
| `kh2_mash_hits.py` | a breakpoint on the hit handler `002E7E48` through the mash | - |
| `kh2_ball_hits.py` | a breakpoint on the vy write `002E7EE8` with `t5 == 0x01ADD9D0`: the ball's real hits, with Sora's attack clock | - (method.md, rule 19) |
| `kh2_noop_check.py` | differing words at 30fps with and without the groups: 0 | `objtrace.py compare` |
| `kh2_find_msgs.py` | found the user's messages in the session transcript, to bound this archive | - |

## logs/

`01` is the one background run, the dense idle sweep; `02`-`96` are the foreground
runs, taken from the session transcript with the command that produced each, in the
order they ran.

| Log | What it shows |
|---|---|
| `02` | the BT3 and PCSXROO tools' docstrings, read as the starting kit |
| `03` | the emulators, save states, memory cards and repo at the start |
| `04`-`06`, `08` | the fixed-step accumulator `001E6280`, its caller, the frame routine, and where the accumulator's increment is stored |
| `07`, `09`, `11` | PCSXROO's launch syntax and KH2 patch settings (database lines redacted), the launch, and the wait for boot |
| `10` | the calls to the increment setter `001E7008` |
| `12` | the assert strings naming the accumulator's module: `partMng.c`, `pppPart.c` |
| `13` | the 30, 60 and 60t2 arms proven by ticks per 20 vsyncs |
| `14`, `15` | three-snapshot RAM rate diffs, and each 2x word classified by the lever that drives it |
| `16`, `01` | the dense idle sweep in three arms, started in the background; `01` is its output |
| `17`, `18` | the KH2FM saves on both memory cards, extracted: three, all in Twilight Town |
| `19`, `22`, `25`, `26`, `30`, `32`, `34`, `36`, `37`, `41` | the background sweep's progress |
| `20`, `21`, `23`, `24` | code referencing the community addresses; how the cutscene timer and the playtime clock advance |
| `27`, `29` | code touching the reaction command and battle state, and the command menu structure that holds the reaction command |
| `28` | commit: the audit tools and plan |
| `31` | the new tools compiled, and the pnach header helper |
| `33` | **the first per-tick integrator scan - its operand tracking was wrong**; `35` is the corrected scan, and `38` adds pointer constants and multiplies, which finds the ball's own sites |
| `39`, `40` | the function with eleven parameter updates - the ability tuning switch `001C31E8`, not per frame - and the two smaller candidates |
| `42` | the sweep's report, and **`findplayer.py`'s first filter finding no player** |
| `43` | the sweep re-ranked with strict criteria |
| `44`-`46` | walking the player: the floats that moved; the filter stages; offline, the vec4s that walked - `01A94440 + 0x540` is Sora, and the two "ground props" are Donald and Goofy |
| `47` | Sora's jump at 30fps, 60fps and 60fps + the ball group |
| `48` | Sora's airborne motion `0017C8F0` disassembled |
| `49`, `50` | height per vsync, and the object's arc fields through the jump: the switch to the apex arc a clock step early at 60fps |
| `51`-`56` | the write watch on `+0xD4` stopping in `0017C42C`; the constants; the caller `0017C690` and its `6.0 < clock` cut; the call site; the threshold's readers |
| `57` | a fully held jump: 185.00 at both rates |
| `58` | nothing branches into the short hop's displaced words |
| `59` | the short hop group generated and decoded |
| `60` | **`mkjumpfix.py --write` crashing** (`TypeError`: it assigned the return values of helpers that edit in place); `61` is the rerun - the tap at 115.10 and every hold passing |
| `62` | odd-length holds and an air combo at both rates: the air combo falls short at 60fps |
| `63` | commit: the short hop and the tracing tools |
| `64`-`67` | the air combo traced - horizontal velocity decaying 0.95 a frame at both rates - the decay helper, and the callers of the jump clock and decay helpers |
| `68` | a grounded combo: 286.61 at 60fps against 244.46 |
| `69`, `70` | `00184540` through PCSXROO's VU-aware disassembler, and the factors several call sites pass |
| `71` | nothing branches into the friction hook site |
| `72` | **"generate failed" - a false failure**: `Select-Object -First` truncating the output set `$?`; `73` is the run |
| `73` | **the first friction group: the air combo's path 0.00, the lunge deleted**; the ground combo, run-and-stop and jumps pass |
| `74`, `75` | the lunge traced with every group, then with each group alone - the friction group removes it. `75` also shows the unpatched 60fps arm's peak moving between runs (146.80, then 156.57): the pad leaking between arms |
| `76` | the breakpoint after the cave on Sora: f20 and f21 at 0.0 - the SQRT operand field |
| `77` | the corrected group: air combo 194.68, ground combo 245.03, run-and-stop 287.62, tap 115.10, held 185.00 - every test passes |
| `78` | the ball's single hit with every group (342.24, airtime 88: pass). **Its mash part ran without the groups** - there is no "+ fix" row |
| `79` | commit: friction and the pad flush |
| `80` | the six-second mash with every group: airtime 334 against 246 |
| `81`-`83` | Sora and the ball traced through the mash in three arms, aligned per vsync, and Sora's swing channels: the arms part at the ball's launch |
| `84` | the mash at two input phases: airtime 214 against 142 and 125 over 30 taps, 334 against 246 over 6 s |
| `85` | the code that calls the hit handler |
| `86` | **a breakpoint on the hit handler `002E7E48` - it stops every frame**, so this counts calls, not hits |
| `87` | the vy write `002E7EE8` conditional on the ball: two pop-ups at 30fps; at 60fps a pop-up, weak hits at Sora's attack clock 16, 16, 12, 16 and a side swipe at 17 |
| `88` | every group at 30fps: 0 differing words through an air combo, a tap jump and a ground combo |
| `89`, `90` | the v03 release cut, consistency and installer checks, the leak scan and the link check |
| `91`, `93`, `96` | commits, and the push that opened PR #2 |
| `92` | the install into the user's PCSX2 (database lines redacted), confirmed with `--status` |
| `94`, `95` | which emulators were running, and the installer after its PINE message fix |
