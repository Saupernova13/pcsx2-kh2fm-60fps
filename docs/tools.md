# Tools index

All 44 tools: the 31 in this repo that know this game, and PCSXROO's 13 generic EE
tools. Every one here has a real module docstring - `python tools/<tool>.py --help`
is the reference, and most docstrings end with what the tool found when it ran.
Setting them up is in the README's [Getting started](../README.md#getting-started).

The tools import game knowledge from `tools/game/` and the generic `ps2ee`
library (PCSXROO client, PINE client, save-state reader, disassembler, pnach
parser) from a [PCSXROO](https://github.com/Saupernova13/pcsxroo) checkout - a
sibling `pcsxroo` folder, or wherever `PCSXROO_REPO` points.

Transport column: **PCSXROO** = needs the PCSXROO debug server (port 28110) running
KH2FM with the Sandlot state in slot 1 and `[60 FPS]` not enabled in its own ini
(see [method.md](method.md)); **PINE** = a stock PCSX2 with PINE enabled;
**offline** = no emulator, usually the ELF in `work/`.

## In this repo (31)

### Install and release

| Tool | Transport | What it does |
|---|---|---|
| `install.py` | offline | Add this project's groups to PCSX2's own KH2FM patch and enable them, leaving every other author's group untouched. `--widescreen`, `--enable-60fps`, `--status`, `--dry-run`, `--remove` |
| `export.py` | offline | Cut `patch/kh2fm-60fps.pnach` from `wip/working.pnach` minus the never-ship groups. `--check`, `--release NAME` |
| `mkballfix.py` | offline | Generate both ball-physics candidates from the ELF, print a decoded listing, and `--check` them against `patch/` and `wip/` |
| `mkjumpfix.py` | offline | Generate `[60 FPS - short hop]` from the ELF, decode it, `--write` it into `wip/`, `--check` it |
| `mkfrictionfix.py` | offline | Generate `[60 FPS - friction]` from the ELF (with the R5900 SQRT encoding), decode it, `--write` it into `wip/`, `--check` it |
| `ws-math.py` | offline / PINE | The widescreen arithmetic for any `--aspect`, checked against the 16:9 group and the JSON; `--live` disassembles the projection routine from a running PCSX2 |

### Setting up

| Tool | Transport | What it does |
|---|---|---|
| `extract-elf.py` | offline | Extract `SLPM_666.75` from the disc image into `work/`, expanding a CHD with chdman |
| `transplant.py` | PCSXROO | Carry a save state from a PCSX2 build PCSXROO refuses, as raw memory; `--save-slot` keeps it |
| `tickrate.py` | PCSXROO | Prove each arm's rate by the game tick counter, and sample delta free-running |
| `memcard.py` | offline | List and extract saves from a PS2 memory card image |

### Acceptance tests

| Tool | Transport | What it does |
|---|---|---|
| `movetest.py` | PCSXROO | Anything that moves: scripted input from one state, a position vector at 30fps, 60fps and 60fps + groups (`--fix`, or `--pnach`/`--group`); peak, airtime, fall, horizontal path. Exit 0 on a match |
| `balltest.py` | PCSXROO | Does the ball fly the same at 60fps as at 30fps? One hit (peak, arch contact, airtime, fall) or `--mash N` seconds (airborne share, landings, height, travel). `--fix`, `--offset`, `--pnach/--group`. Exit 0 on a match |
| `mashdist.py` | PCSXROO | The mash as distributions: four arms at several hit timings |

### Finding things

| Tool | Transport | What it does |
|---|---|---|
| `findplayer.py` | PCSXROO / offline | Walk away and back from a state and name the objects whose own position followed, by their class word - how Sora, Donald and Goofy were identified. `--load` re-ranks a saved walk |
| `objtrace.py` | PCSXROO / offline | Dump an object's memory every vsync through scripted input per arm (30, 60, 60fix/30fix, 60w/30w); `fields` ranks lanes by variation ratio, `classes` lists class switches, `compare` counts differing words - the no-op check at 30fps |
| `objects.py` | PCSXROO | List every object the displacement builder moves, with class, vtable and motion routine, and trace them all through the mash |
| `props.py` | PCSXROO | The ball and Sora through the mash: class switches, velocity, impulses |
| `capture.py` | PCSXROO | Full EE RAM snapshots around one hit, for offline search |
| `arcs.py` | offline | Search a capture for words that fly: excursion in flight against wobble at rest, parabola fit |
| `track.py` | PCSXROO | Follow a capture's candidate words every vsync and rank the arcs; `--vec4` keeps world positions |
| `ballobj.py` | PCSXROO | Trace the ball object's region in both arms, correlate every word with height change per tick, and `--watch` its height's writers |
| `mashtrace.py` | PCSXROO | Trace the ball through a mash in three arms, check determinism, and split its sideways travel by source |
| `pushtest.py` | PCSXROO | Walk Sora through the resting ball: does anything push it? |
| `watch.py` | PCSXROO | Watchpoints and breakpoints during the Sandlot schedule, collected by (pc, ra) with registers and a listing |
| `divergence.py` | offline | Where 60fps stops matching 30fps, on saved traces: `objects` and `mash` |

### Rate audits

| Tool | Transport | What it does |
|---|---|---|
| `ratesweep.py` | PCSXROO / offline | Sample RAM every 2 vsyncs per arm (30, `[60 FPS]`, `[60 FPS]` with the stock threshold) and flag words whose total variation or reversals double - catches oscillators the three-snapshot diff misses. `ratediff.start_arm()`, which every audit tool uses, flushes the pad and proves the arm |
| `ratediff.py` | PCSXROO / offline | Snapshot RAM three times per arm and flag words that move twice as far in the same real time; `classify` names the lever |

### Static analysis

| Tool | Transport | What it does |
|---|---|---|
| `frame-timing.py` | offline | How the game times a frame and what `[60 FPS]` changes: stock values, every reference, the setters and their arguments, the vsync callback |
| `elfscan.py` | offline | `refs`, `float`, `offsets`, `callers`, `into`, `range`, `dis` - every static question the findings asked |
| `integrators.py` | offline | Every `field = field op constant` float update in the ELF, with the constant direct or through a data pointer |
| `simfix.py` | offline | Simulate the ball at 30Hz and 60Hz with each candidate fix, with the arch and in free flight |

## In PCSXROO (13)

Generic EE tools in `pcsxroo/tools/`, written for the BT3 project and kept game-free.
They read the game identity and ELF from PCSXROO's own `pcsxroo/local.json`; point
it at this repo's `work/` to use them here. None has been needed for KH2FM yet. For
VU0 code, PCSXROO's live disassembler (`Roo.dis`) is the one that decodes it.

| Tool | Transport | What it does |
|---|---|---|
| `countdown.py` | offline | Find countdown timers in a saved trace, at byte granularity |
| `dataxref.py` | offline | Find the code that touches a global, by address rather than by call graph |
| `disas.py` | offline | Disassemble EE code around one or more addresses |
| `looptree.py` | offline | Walk the call tree under a loop, then scan only that code for step constants |
| `mkhalf.py` | offline | Turn `field += 1.0` sites into `field += 0.5`, one trampoline each |
| `phasetimer.py` | offline | Find a state machine's phase timers |
| `probe-loop.py` | PINE | Disable one call in a loop at a time, live, to see what it drives |
| `radar.py` | offline | Static scan for frame-pacing constants - a fast standalone pass |
| `ramdiff.py` | offline | Differential memory search across save states |
| `setup-pcsx2.py` | PINE | Inspect and adjust the PCSX2 settings this workflow depends on |
| `tickcount.py` | offline | Find every integer `field = field + 1` in the binary - the frame counters |
| `tickstep.py` | offline | Find every `field += 1.0` in the binary, including the hoisted ones |
| `xref.py` | offline | Find who calls a function, and where its address is stored |

## `tools/game/` - what the tools know about the game

| Module | What it holds |
|---|---|
| `identity.py` | serial, CRC, ELF layout, the safe zone, and patch policy: which groups never ship, which are optional, which database groups each of ours needs |
| `config.py` | path discovery: PCSX2, its `patches/`, gamesettings ini and `patches.zip`, the ELF, the disc image; `local.json` overrides |
| `timing.py` | the frame-timing addresses and the arms' words |
| `physics.py` | the object classes, the prop integrator's constants and offsets, the hit, a character's jump arc, the shared velocity step and its call sites, and the ball fix's addresses |
| `sandlot.py` | the Sandlot save state: the ball, Sora and the party, the input schedule, and arm setup with its tick proof |
| `world.py` | game-state addresses published by the community for this disc - location, save, party, reaction command, battle status, cutscene timer, Atlantica, gummi - recorded as facts with their source |
| `elf.py` | the unpatched ELF by address: words, floats, function bounds, references, callers |
| `pnachtext.py` | text-level pnach editing that leaves other authors' blocks byte for byte |

## Common workflows

**Install or check an install**

    python tools/install.py --status
    python tools/install.py --dry-run --widescreen
    python tools/install.py --widescreen

**Rebuild the A/B loop from nothing**

    python tools/extract-elf.py
    python tools/transplant.py "<PCSX2>/sstates/SLPM-66675 (FAF99301).01.p2s" --save-slot 1
    python tools/tickrate.py
    python tools/balltest.py            # must FAIL
    python tools/balltest.py --fix      # must PASS
    python tools/movetest.py --pos 01A94980 --script "wait:6,hold:Circle:6,wait:110"         # tap jump: must FAIL
    python tools/movetest.py --pos 01A94980 --script "wait:6,hold:Circle:6,wait:110" --fix   # must PASS

**Re-derive the fixes offline**

    python tools/frame-timing.py
    python tools/elfscan.py float 0.408163
    python tools/simfix.py
    python tools/mkballfix.py --check
    python tools/mkjumpfix.py --check
    python tools/mkfrictionfix.py --check
    python tools/export.py --check

**Audit a system** - the global audit's loop ([global-audit.md](global-audit.md))

    python tools/ratesweep.py capture work/rs-<scene>.npz              # idle, from slot 1
    python tools/ratesweep.py report work/rs-<scene>.npz
    python tools/findplayer.py                                          # who is who in the state
    python tools/movetest.py --pos <object+540> --script "<script>"     # the system in motion
    python tools/objtrace.py capture work/ot-<test>.npz --obj <object> --script "<script>" --arms 30,60
    python tools/objtrace.py fields work/ot-<test>.npz                  # which field runs per frame

**Check a group changes nothing at 30fps**

    python tools/objtrace.py capture work/ot-noop.npz --obj 01A94440 --script "wait:6,hold:Circle:6,wait:110" --arms 30,30fix
    python tools/objtrace.py compare work/ot-noop.npz 30 30fix         # must report 0 differing words

**Pick up the open juggling problem**

    python tools/movetest.py --pos 01ADDF10 --script "wait:6,hold:LLeft+LDown:8,tap:Cross,wait:6,..." --fix
    python tools/mashdist.py
    python tools/mashtrace.py && python tools/divergence.py mash
    python tools/watch.py --bp 002E7EE8 --fps 60 --hit-then 0

## What the session scripts became

The session folders under `wip/` hold the scripts as they ran, for the record.

**`wip/session-2026-09-15/scripts/`** (the ball physics session). Each has a
maintained port:

| Session script | Port |
|---|---|
| `kh2lab.py` | `game/sandlot.py`, `game/timing.py` |
| `kh2_transplant.py` | `transplant.py` |
| `kh2_tickrate.py` | `tickrate.py` |
| `kh2_findball.py`, `kh2_capture.py` | `capture.py` |
| `kh2_arcs.py` | `arcs.py` |
| `kh2_track.py` | `track.py` |
| `kh2_balltrack.py` | `ballobj.py` (the original tracked the stack slot, not the object) |
| `kh2_balltest.py` | `balltest.py` |
| `kh2_refs.py`, `kh2_accum.py` | `frame-timing.py`, `elfscan.py refs` |
| `kh2_ws_probe.py`, `kh2_ws_values.py` | `ws-math.py --live`, `ws-math.py` |
| inline runs in the logs | `ballobj.py`, `objects.py`, `props.py`, `pushtest.py`, `watch.py`, `mashtrace.py`, `mashdist.py`, `divergence.py`, `simfix.py`, `mkballfix.py` |

**`wip/session-2026-09-15-audit/scripts/`** (the global audit). Most were one-off
analysis around the maintained tools; the ones that grew into a tool:

| Session script | Port |
|---|---|
| `kh2_arm_check.py` | `ratediff.start_arm()` |
| `kh2_rs_strict.py` | `ratesweep.py report` |
| `kh2_saves.py` | `memcard.py` |
| `kh2_setter_calls.py` | `elfscan.py callers` |
| `kh2_fp_diag.py`, `kh2_fp_save.py`, `kh2_fp_heap.py` | `findplayer.py` |
| `kh2_jump_rows.py` | `movetest.py --save` |
| `kh2_jump_fields.py`, `kh2_aircombo_rows.py`, `kh2_aircombo_fix_rows.py`, `kh2_swing_rows.py` | `objtrace.py fields` |
| `kh2_noop_check.py` | `objtrace.py compare` |
| the breakpoint and watchpoint scripts (`kh2_jump_writer.py`, `kh2_jump_caller.py`, `kh2_friction_bp.py`, `kh2_mash_hits.py`, `kh2_ball_hits.py`), `kh2_mash_align.py` | not ported - their technique is in [method.md](method.md), rules 8, 18 and 19 |

The session README lists all 24 with what each found.

## What they write

Everything goes to `work/`, which is gitignored: the ELF, `cap-<fps>.npz` captures,
`track-<fps>.npz`, `ballobj-<fps>.npz`, `objtrace.npz`, `mashtrace.npz`,
`props.npz`, `pushtest.npz`, the audit's `rd-*.npz` and `rs-*.npz` sweeps,
`ot-*.npz` object traces, `movetest.py --save` traces, `findplayer.npz`, extracted
saves in `saves/`, screenshots, and `install-backups/`.
