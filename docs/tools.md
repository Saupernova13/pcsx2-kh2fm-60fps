# Tools index

All 31 command-line tools in this repo. Every one has a real module docstring -
`python tools/<tool>.py --help` is the reference, and most docstrings end with what
the tool found when it ran. Setting them up is in the README's
[Getting started](../README.md#getting-started).

The tools import game knowledge from `tools/game/` and the generic `ps2ee`
library (PCSXROO client, PINE client, save-state reader, disassembler, pnach
parser) from a [PCSXROO](https://github.com/Saupernova13/pcsxroo) checkout - a
sibling `pcsxroo` folder, or wherever `PCSXROO_REPO` points. PCSXROO's own generic
EE tools (`pcsxroo/tools/`) work on this game too.

Transport column: **PCSXROO** = needs the PCSXROO debug server (port 28110) running
KH2FM with the Sandlot state in slot 1 and `[60 FPS]` not enabled in its own ini
(see [method.md](method.md)); **PINE** = a stock PCSX2 with PINE enabled;
**offline** = no emulator, usually the ELF in `work/`.

## Install and release

| Tool | Transport | What it does |
|---|---|---|
| `install.py` | offline | Add this project's groups to PCSX2's own KH2FM patch and enable them, leaving every other author's group untouched. `--widescreen`, `--enable-60fps`, `--status`, `--dry-run`, `--remove` |
| `export.py` | offline | Cut `patch/kh2fm-60fps.pnach` from `wip/working.pnach` minus the never-ship groups. `--check`, `--release NAME` |
| `mkballfix.py` | offline | Generate both ball-physics candidates from the ELF, print a decoded listing, and `--check` them against `patch/` and `wip/` |
| `ws-math.py` | offline / PINE | The widescreen arithmetic for any `--aspect`, checked against the 16:9 group and the JSON; `--live` disassembles the projection routine from a running PCSX2 |

## Setting up

| Tool | Transport | What it does |
|---|---|---|
| `extract-elf.py` | offline | Extract `SLPM_666.75` from the disc image into `work/`, expanding a CHD with chdman |
| `transplant.py` | PCSXROO | Carry a save state from a PCSX2 build PCSXROO refuses, as raw memory; `--save-slot` keeps it |
| `tickrate.py` | PCSXROO | Prove each arm's rate by the game tick counter, and sample delta free-running |

## The acceptance test

| Tool | Transport | What it does |
|---|---|---|
| `balltest.py` | PCSXROO | Does the ball fly the same at 60fps as at 30fps? One hit (peak, arch contact, airtime, fall) or `--mash N` seconds (airborne share, landings, height, travel). `--fix`, `--offset`, `--pnach/--group`. Exit 0 on a match |
| `mashdist.py` | PCSXROO | The mash as distributions: four arms at several hit timings |

## Finding things

| Tool | Transport | What it does |
|---|---|---|
| `capture.py` | PCSXROO | Full EE RAM snapshots around one hit, for offline search |
| `arcs.py` | offline | Search a capture for words that fly: excursion in flight against wobble at rest, parabola fit |
| `track.py` | PCSXROO | Follow a capture's candidate words every vsync and rank the arcs; `--vec4` keeps world positions |
| `ballobj.py` | PCSXROO | Trace the ball object's region in both arms, correlate every word with height change per tick, and `--watch` its height's writers |
| `objects.py` | PCSXROO | List every object through the displacement builder, with class, vtable and motion routine, and trace them all through the mash |
| `props.py` | PCSXROO | The ball and the second prop through the mash: class switches, velocity, impulses |
| `mashtrace.py` | PCSXROO | Trace the ball through a mash in three arms, check determinism, and split its sideways travel by source |
| `pushtest.py` | PCSXROO | Walk Sora through the resting ball: does anything push it? |
| `watch.py` | PCSXROO | Watchpoints and breakpoints in the Sandlot scene, collected by (pc, ra) with registers and a listing |
| `divergence.py` | offline | Where 60fps stops matching 30fps, on saved traces: `objects` and `mash` |

## Static analysis

| Tool | Transport | What it does |
|---|---|---|
| `frame-timing.py` | offline | How the game times a frame and what `[60 FPS]` changes: stock values, every reference, the setters and their arguments, the vsync callback |
| `elfscan.py` | offline | `refs`, `float`, `offsets`, `callers`, `into`, `range`, `dis` - every static question the findings asked |
| `simfix.py` | offline | Simulate the ball at 30Hz and 60Hz with each candidate fix, with the arch and in free flight |

## The global audit

| Tool | Transport | What it does |
|---|---|---|
| `ratediff.py` | PCSXROO / offline | Snapshot RAM three times per frame-rate arm (30, `[60 FPS]`, `[60 FPS]` with the stock accumulator threshold or delta cap) and flag words that move twice as far in the same real time; `classify` names the lever |
| `ratesweep.py` | PCSXROO / offline | Sample RAM every 2 vsyncs per arm and flag words whose total variation or reversals double - catches oscillators the three-snapshot diff misses |
| `findplayer.py` | PCSXROO | Walk away and back from a state and look for the vec4 that follows - how Sora was found at `01A94440 + 0x540` |
| `movetest.py` | PCSXROO | The movement acceptance test for any position vector: scripted input, 30fps against 60fps against 60fps + groups; peak, airtime, fall, horizontal path |
| `objtrace.py` | PCSXROO / offline | Dump an object's memory every vsync through scripted input per arm (30, 60, 60fix/60w, 30fix/30w); `fields` ranks lanes by variation ratio, `classes` lists class switches |
| `integrators.py` | offline | Every `field = field op constant` float update in the ELF, with the constant direct or through a data pointer |
| `mkjumpfix.py` | offline | Generate `[60 FPS - short hop]` from the ELF, decode it, write it into `wip/`, `--check` |
| `mkfrictionfix.py` | offline | Generate `[60 FPS - friction]` from the ELF (R5900 SQRT encoding), decode it, write it into `wip/`, `--check` |
| `memcard.py` | offline | List and extract saves from a PS2 memory card image |

## `tools/game/` - what the tools know about the game

| Module | What it holds |
|---|---|
| `identity.py` | serial, CRC, ELF layout, the safe zone, and patch policy: which groups never ship, which are optional, which database groups each of ours needs |
| `config.py` | path discovery: PCSX2, its `patches/`, gamesettings ini and `patches.zip`, the ELF, the disc image; `local.json` overrides |
| `timing.py` | the frame-timing addresses and the two arms' words |
| `physics.py` | the prop classes, the integrator's constants and object offsets, the hit, and the fix's addresses |
| `sandlot.py` | the Sandlot save state: object addresses, the input schedule, and arm setup with its tick proof |
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

**Re-derive the fix offline**

    python tools/frame-timing.py
    python tools/elfscan.py float 0.408163
    python tools/simfix.py
    python tools/mkballfix.py --check
    python tools/export.py --check

**Pick up the open mashing problem**

    python tools/mashdist.py
    python tools/mashtrace.py && python tools/divergence.py mash
    python tools/objects.py && python tools/divergence.py objects
    python tools/watch.py --write 01ADD9F4:4 --fps 60 --fix --mash-to 64

## What the session scripts became

`wip/session-2026-09-15/scripts/` holds the scripts as they ran, for the record.
Each has a maintained port:

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

## What they write

Everything goes to `work/`, which is gitignored: the ELF, `cap-<fps>.npz` captures,
`track-<fps>.npz`, `ballobj-<fps>.npz`, `objtrace.npz`, `mashtrace.npz`,
`props.npz`, `pushtest.npz`, screenshots, and `install-backups/`.
