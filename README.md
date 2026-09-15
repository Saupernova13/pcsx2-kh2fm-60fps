# pcsx2-kh2fm-60fps

Additions to the 60fps patch for **Kingdom Hearts II Final Mix+** (SLPM-66675, CRC
FAF99301) on PCSX2: fixes for what the 60fps patch leaves running at double rate,
a 19.5:9 widescreen for the Galaxy S24 Ultra, and the tooling and full record
behind both.

**This is not a complete patch.** KH2FM's 60fps and widescreen patches already
exist in PCSX2's own patch database - PeterDelta's `[60 FPS]` and ElHecht's
`[Widescreen 16:9]` - and they are not in this repository. This project adds its
own groups to the copy of that patch you already have. See
[What this repo does not contain](#what-this-repo-does-not-contain).

## Install

    python tools/install.py                  # add this project's 60fps groups and enable them
    python tools/install.py --widescreen     # also the 19.5:9 widescreen (turns 16:9 off)
    python tools/install.py --enable-60fps   # also switch on [60 FPS], if it is off

Then **quit and relaunch PCSX2** - it reads patches and per-game settings at boot,
so a reset or save-state load is not enough.

The installer finds PCSX2, takes the patch it already has for the game
(`patches/SLPM-66675_FAF99301.pnach`, or the entry inside `resources/patches.zip`),
adds this project's groups next to the ones they depend on, leaves every other
group byte for byte, backs up what it changes, and writes the enable lines.
`--status` shows what is installed and whether it matches this repo, `--dry-run`
shows what would change, `--remove` takes it back out. It needs Python 3.11+ and
a PCSXROO checkout next to this one - see [Getting started](#getting-started),
steps 1 and 3. Installing by hand is in [`docs/releases.md`](docs/releases.md).

Per-build confidence, and what has been confirmed in play rather than only
measured, is in **[`docs/status.md`](docs/status.md)**. Every version, with what it
changed and what was discovered, is in [`docs/versions/`](docs/versions/README.md).

## What it covers

**`[60 FPS - ball physics]`** - the Twilight Town Sandlot juggle. At 30fps you can
keep the glowing ball in the air by mashing Cross; with `[60 FPS]` it barely clears
Sora's head and drops in half the time. The props' airborne motion code applies drag
(x0.8) and gravity (+0.408) once per game tick, but moves them by velocity x frame
delta. `[60 FPS]` doubles the ticks and halves delta, so position steps come out
right while drag and gravity act twice per real second. The group runs that velocity
update on every other game tick while `[60 FPS]` is active.

| One hit, same real time | 30fps | 60fps before | 60fps with the group |
|---|---|---|---|
| Peak height | 341.8 | 208.8 | 342.2 - 343.5 |
| Pinned under the arch (vsyncs) | 14 | 3 | 14 |
| Airtime (vsyncs) | 88 | 47 | 88 - 89 |

**`[60 FPS - short hop]`** - a jump released early is cut into its apex once the
jump clock passes a threshold. At 30fps the clock steps by 2, at 60fps by 1, so 60fps
cut one step early and a tap peaked 103.5 instead of 115.1. The cut now waits for an
even clock: 115.10 at 60fps, and nothing changes at 30fps.

**`[60 FPS - friction]`** - the game's shared velocity step, behind Sora on the
ground and in the air and many object and enemy states, applies friction and
acceleration once per frame. At 60fps an air-combo lunge travelled 131 instead of
195 and a ground combo 287 instead of 244. The factors now take their square root at
60fps: 194.7 and 245.0, with top speeds unchanged.

All of these groups are verified to change nothing at 30fps.

**`[Widescreen 19.5:9 - S24 Ultra]`** - ElHecht's 16:9 hack retargeted to 19.5:9
(3120x1440): the widen factor `12/19.5` loaded exactly, and the font scale to
match. Uses Stretch, so it wants a 19.5:9 output.

**Known not fixed:** a long juggle still stays up longer than it does at 30fps, even
with every group on. The ball's flight, Sora's jumps and his lunges all match; what
differs is contact - Sora's swings land weak hits and side swipes the 30fps game does
not, after collision push-outs leave the ball a few units over. Effects also run at
double speed under `[60 FPS]`, and no enemy has been measured yet. None of the groups
has been confirmed in play. The running list is
[`docs/global-audit.md`](docs/global-audit.md).

## What this repo does not contain

**Other people's patches.** `[60 FPS]`, `[Widescreen 16:9]` and every other group in
PCSX2's database belong to their authors. This repo keeps only what this project
wrote:

- `patch/kh2fm-60fps.pnach` - the groups that are entirely ours. Three of the ball
  group's words are the game's own instructions, relocated by its hook.
- `patch/widescreen-19.5x9-s24.json` - the widescreen group is ElHecht's with five
  words changed and one added, so only those six words are here. The installer
  builds the group from your own copy of his 16:9 group, after checking that every
  word it replaces is the word it expects.
- The session logs under `wip/` have other authors' patch lines redacted.

**Game or console data.** No disc image, ELF, save state, memory card or BIOS. The
tools extract the ELF from your own disc into the gitignored `work/`, and you make
your own save states.

## Repository layout

    patch/        this project's groups, and the widescreen change set
    tools/        the command line tools; the game knowledge is in tools/game/
    docs/         status, findings, method, addresses, tool index, releases, versions
    wip/          the working pnach, the tested candidates, and the session archives -
                  NOT for install

`work/` (the extracted ELF, RAM captures, traces, install backups) is gitignored.
Released versions are git tags - see [`docs/releases.md`](docs/releases.md).

## Getting started

Everything here is what it takes to pick the work up and keep developing it. You
need your own copy of the game and a BIOS dumped from your own console.

**1. Clone both repos side by side.** The generic half of the tooling - the `ps2ee`
library (PCSXROO and PINE clients, save-state reader, disassembler, pnach parser) -
lives in [PCSXROO](https://github.com/Saupernova13/pcsxroo), a PCSX2 fork with a
debug server that most of the tools here drive.

    git clone https://github.com/Saupernova13/pcsx2-kh2fm-60fps.git
    git clone https://github.com/Saupernova13/pcsxroo.git

The tools find PCSXROO as that sibling folder, or wherever `PCSXROO_REPO` points (in
the environment or this repo's `local.json`).

**2. Build PCSXROO** by following its
[`pcsxroo/README.md`](https://github.com/Saupernova13/pcsxroo/blob/master/pcsxroo/README.md).
It runs in portable mode, so its `patches/`, `sstates/` and `gamesettings/` sit in
`pcsxroo\bin\`, apart from the PCSX2 you play on. Only the installer and the offline
tools work without it.

**3. Install Python 3.11+ and the packages:**

    pip install numpy capstone zstandard

**4. Tell the tools where things are,** if they cannot find them. Anything can be set
in the environment or in a `local.json` in this repo's root (gitignored):

    {
      "PCSX2_DIR":    "C:/path/to/PCSX2",
      "PCSXROO_DIR":  "C:/path/to/pcsxroo/bin",
      "PCSXROO_REPO": "C:/path/to/pcsxroo",
      "GAME_IMAGE":   "D:/roms/ps2/Kingdom Hearts II - Final Mix+.chd",
      "CHDMAN":       "C:/path/to/chdman.exe"
    }

`PCSX2_DIR` is the PCSX2 you play on, which `install.py` edits. `GAME_IMAGE` falls
back to `ROM_DIRS`, then to the folders in PCSX2's own game list.

**5. Extract the ELF** from your disc image into `work/`. A CHD is expanded with
chdman first:

    python tools/extract-elf.py

**6. Make the reference save state.** Get to the Twilight Town Sandlot with Sora
standing beside the glowing ball, and save. If your PCSX2 is a version PCSXROO
refuses, carry the state across as memory and keep it in PCSXROO's own slot 1 -
PCSXROO must already be running the game in a field:

    python tools/transplant.py "<PCSX2>/sstates/SLPM-66675 (FAF99301).01.p2s" --save-slot 1

Then remove `Enable = 60 FPS` from PCSXROO's `bin/gamesettings/SLPM-66675_FAF99301.ini`
and restart it: the tools switch between 30fps and 60fps themselves, and an enabled
`[60 FPS]` would override them. The object addresses in `tools/game/sandlot.py` are
heap addresses from the original state; a state of your own may put the ball
elsewhere - `tools/objects.py` lists every physics object.

**7. Run the A/B loop.** Every measurement compares the unpatched 30fps game with
60fps from the same state, same input, same number of vsyncs:

    python tools/tickrate.py            # proves both arms tick at their rate
    python tools/balltest.py            # 30fps vs unpatched 60fps: must FAIL
    python tools/balltest.py --fix      # 30fps vs 60fps + the group: must PASS

**8. Read what is already known** before changing anything:
[`docs/status.md`](docs/status.md), [`docs/findings.md`](docs/findings.md) for the
full record, [`docs/method.md`](docs/method.md) for the rules that each cost a wrong
result, [`docs/addresses.md`](docs/addresses.md), and
[`docs/tools.md`](docs/tools.md) for all 22 tools.

## How a patch gets written

The ball group is generated, not typed: `tools/mkballfix.py` hand-encodes every
branch, copies the instructions the hook displaces straight out of the ELF (capstone
cannot decode `lq`/`sq`, so they are the one place a typo would go unseen), decodes
every word back, and `--check`s the result against `patch/` and `wip/`. Candidates
are simulated first (`tools/simfix.py`), then scored by `balltest.py`.

`wip/working.pnach` is the source; `tools/export.py --release vNN-name` cuts `patch/`
from it without the groups that must never ship, and refuses to run without a
version note.

## Notes

- PCSX2's `patches.zip` carries the same `[60 FPS]` under three CRCs, so renaming
  the group in a local patch file does not switch it off. Remove its enable line.
- Bare numbers in PCSXROO breakpoint conditions are hex.
- Two PCSXROO bugs met here are fixed on open PRs: shutting down a paused VM hung,
  and an interrupted frame-advance could pause a later run by itself. Until they
  merge, resume before `shutdown`.

## Credits

`[60 FPS]` in PCSX2's patch database: PeterDelta. `[Widescreen 16:9]`: ElHecht, whose
hack the 19.5:9 group is built on. PCSX2's patch database and its contributors.
Workflow: Red-tv141's
[AI-Assisted 60fps Patch Development guide](https://forums.pcsx2.net/Thread-GUIDE-AI-Assisted-60fps-Patch-Development-for-PS2-Games-%E2%80%94-Full-Workflow),
by way of the sibling [pcsx2-bt3-60fps](https://github.com/Saupernova13/pcsx2-bt3-60fps).

## Licence

Code (`tools/`): **MIT**, see [`LICENSE`](LICENSE).
Docs, findings and this project's groups: **CC BY 4.0**, see
[`LICENSE-docs`](LICENSE-docs).
Neither covers the PCSX2 database groups these build on, which belong to their
authors.
