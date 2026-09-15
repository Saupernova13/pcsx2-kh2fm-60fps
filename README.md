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
ground and in the air and 17 other call sites not yet identified, applies friction
and acceleration once per frame. At 60fps an air-combo lunge travelled 131 instead
of 195 and a ground combo 287 instead of 244. The factors now take their square root
at 60fps: 194.7 and 245.0, with top speeds unchanged.

| Sora, same input and real time | 30fps | 60fps before | 60fps with every group |
|---|---|---|---|
| Tap jump peak | 115.08 | 103.53 | 115.10 |
| Air combo travel | 195.02 | 131.43 | 194.68 |
| Ground combo travel | 244.46 | 286.61 | 245.03 |
| Held jump peak, run then stop | 185.00, 287.63 | 185.00, 287.62 | 185.00, 287.62 |

All three are verified to change nothing at 30fps: Sora's object memory is
byte-identical with and without them.

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

## Why the obvious patch does not work

`[60 FPS]` is three words:

| Word | Stock | `[60 FPS]` | What it is |
|---|---|---|---|
| `00349E1C` | 1 | 0 | extra vsyncs the frame routine waits for |
| `0036B0F8` | 6.0 | 1.0 | the cap on delta; at 1.0 a slow frame slows the game instead of catching up |
| `0036EF20` | 2.0 | 1.0 | the particle and effect system's fixed-step threshold |

KH2's engine keeps time in 60 Hz units: delta is the number of vsyncs a frame took,
2 at stock 30fps. So removing the wait is most of a correct patch - everything that
moves by velocity x delta, and every timer that adds delta, is already right at
60fps. What breaks is code that steps once per frame or per game tick without delta,
because it was tuned at 30 Hz and now runs twice as often:

- **the Sandlot ball's drag and gravity**, per tick - it rose half as high;
- **the jump controller's cut**, compared against a clock that now counts by 1
  instead of 2 - short hops came out low;
- **the shared velocity step's friction and blend**, per frame - lunges fell short
  and ground combos overshot.

The third word makes a right thing wrong: the particle accumulator already adds
delta, so the stock 2.0 was 30 steps a real second at 60fps, and 1.0 makes effects
step twice as fast. No global constant fixes any of this. Each per-frame step is
found by measuring a system against 30fps and fixed where it runs, which covers every
object and scene that runs that code. The state of every system is in
[`docs/global-audit.md`](docs/global-audit.md).

## What this repo does not contain

**Other people's patches.** `[60 FPS]`, `[Widescreen 16:9]` and every other group in
PCSX2's database belong to their authors. This repo keeps only what this project
wrote:

- `patch/kh2fm-60fps.pnach` - the groups that are entirely ours. A few of their
  words are the game's own instructions, relocated by their hooks.
- `patch/widescreen-19.5x9-s24.json` - the widescreen group is ElHecht's with five
  words changed and one added, so only those six words are here. The installer
  builds the group from your own copy of his 16:9 group, after checking that every
  word it replaces is the word it expects.
- The session logs under `wip/` have other authors' patch lines redacted, and runs
  that printed other people's scripts are left out.

**Other people's scripts.** The community's KH2 address maps are credited below;
`tools/game/world.py` records only the addresses they publish.

**Game or console data.** No disc image, ELF, save state, memory card or BIOS. The
tools extract the ELF from your own disc into the gitignored `work/`, and you make
your own save states.

## Repository layout

    patch/        this project's groups, and the widescreen change set
    tools/        the command line tools; the game knowledge is in tools/game/
    docs/         status, the global audit, findings, method, addresses, tool index,
                  releases, versions
    wip/          the working pnach, the tested candidates, and the session archives -
                  NOT for install

`work/` (the extracted ELF, RAM captures, traces, install backups) is gitignored.
Released versions become git tags as they merge - see
[`docs/releases.md`](docs/releases.md).

## Getting started

Everything here is what it takes to pick the work up and keep developing it. You
need your own copy of the game and a BIOS dumped from your own console.

**1. Clone both repos side by side.** The generic half of the tooling - the `ps2ee`
library (PCSXROO and PINE clients, save-state reader, disassembler, pnach parser)
and 13 EE analysis tools - lives in [PCSXROO](https://github.com/Saupernova13/pcsxroo),
a PCSX2 fork with a debug server (memory, breakpoints, watchpoints, save states, pad
injection, screenshots) that most of the tools here drive.

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
heap addresses from the original state; a state of your own may put them elsewhere.
`tools/objects.py` lists every object the displacement builder moves, and
`tools/findplayer.py` walks Sora away and back to say which of them are Sora,
Donald and Goofy.

**7. Run the A/B loop.** Every measurement compares the unpatched 30fps game with
60fps from the same state, same input, same number of vsyncs; the rules are under
[Testing loop](#testing-loop):

    python tools/tickrate.py            # proves both arms tick at their rate
    python tools/balltest.py            # the ball, 30fps vs unpatched 60fps: must FAIL
    python tools/balltest.py --fix      # 30fps vs 60fps + the ball group: must PASS
    python tools/movetest.py --pos 01A94980 --script "wait:6,hold:Circle:6,wait:110"         # Sora's tap jump: must FAIL
    python tools/movetest.py --pos 01A94980 --script "wait:6,hold:Circle:6,wait:110" --fix   # must PASS

**8. Read what is already known** before changing anything:
[`docs/status.md`](docs/status.md) for which build to trust,
[`docs/global-audit.md`](docs/global-audit.md) for the state of every system and
what to take next, [`docs/findings.md`](docs/findings.md) for the full record,
[`docs/method.md`](docs/method.md) for the rules that each cost a wrong result,
[`docs/addresses.md`](docs/addresses.md), and [`docs/tools.md`](docs/tools.md) for
every tool.

## Tools

All 44 tools are indexed in **[docs/tools.md](docs/tools.md)** with what each needs
(PCSXROO, PINE, or offline). Two homes:

- **`tools/` here** - the 31 that know this game: they read its objects, write its
  arms, or edit its patch. `install.py`, `movetest.py`, `objtrace.py` and the
  `mk*fix.py` generators are the ones you will use the most.
- **PCSXROO's `pcsxroo/ps2ee/` and `pcsxroo/tools/`** - the generic ps2ee library and
  13 EE analysis tools that would work on any game: disassembly, xrefs, RAM diffing,
  tick counting.

## How a patch gets written

Groups are generated, not typed. Each generator - `tools/mkballfix.py`,
`tools/mkjumpfix.py`, `tools/mkfrictionfix.py` - encodes every instruction itself,
checks the words its hook displaces against the ELF, copies any it relocates
straight out of the ELF, decodes every word back, and `--check`s the result against
`patch/` and `wip/`; the last two `--write` their group into `wip/working.pnach`.
Encoding by hand is deliberate: the R5900 is not plain MIPS where it matters.
Capstone cannot decode `lq`/`sq` or VU0 code, and the FPU's SQRT takes its operand
from a different field than MIPS - the first friction group, encoded the standard
way, took the square root of zero and deleted every lunge.

Candidates are simulated first where the model is small (`tools/simfix.py` for the
ball), scored by `balltest.py` or `movetest.py` against 30fps, then run in the 30fps
arm to show they change nothing there.

`wip/working.pnach` is the source; `tools/export.py --release vNN-name` cuts `patch/`
from it without the groups that must never ship, and refuses to run without a
version note.

## Testing loop

Every measurement is an A/B against the unpatched 30fps game from the same save
state, with the same scripted input over the same number of vsyncs. The arm is set
by writing `[60 FPS]`'s three words after the state loads, and a group under test by
writing its words, as PCSX2 does every frame:

    python tools/movetest.py --pos <object+540> --script "<script>"          # 30 vs 60
    python tools/movetest.py --pos <object+540> --script "<script>" --fix    # 30 vs 60 + every group
    python tools/objtrace.py capture work/t.npz --obj <object> --script "<script>" --arms 30,60,60fix,30fix
    python tools/objtrace.py fields work/t.npz                                # which fields run per frame
    python tools/objtrace.py compare work/t.npz 30 30fix                      # must be 0 words

Five rules, each learned by getting it wrong (all 21 are in
[`docs/method.md`](docs/method.md)):

- **Switch `[60 FPS]` off by its enable line, not by renaming it.** PCSX2's
  `patches.zip` carries the same group under three CRCs, so a renamed group goes on
  applying; the first "30fps" arm ran at 60fps. Remove `Enable = 60 FPS` from
  PCSXROO's own ini and reboot.
- **Prove the arm by the game tick counter** `0032B920` - 2 ticks per 4 vsyncs at
  30fps, 4 at 60fps - never by the delta word, which a paused VM reads mid-wait.
- **Flush the pad before loading a state.** A release sent while paused only
  queues, and the last button of one arm leaks into the next.
- **Numbers in PCSXROO breakpoint conditions are hex.** `t5 == 28170704` means
  `0x28170704`. Write `0x` every time, and put a condition on the object when
  breaking in shared code.
- **Run every group at 30fps, and every earlier test again.** A fix must be a no-op
  at 30fps, and a fix for one system can break another: the first friction group
  passed the ground combo and deleted the air lunge.

When a change is ready to hand over:

    python tools/export.py --release vNN-name

and tag its merge commit once the pull request lands ([`docs/releases.md`](docs/releases.md)).

## Notes

- PCSX2's `patches.zip` carries the same `[60 FPS]` under three CRCs, so renaming
  the group in a local patch file does not switch it off. Remove its enable line.
- The ELF loads as one RWX segment at `0x00100000`, code and data together; code
  scans here stop at `0x00340000`. The caves live in the zero run from `0x000FE000`.
- Capstone has no R5900 mode, so `ps2ee.disasm` will not decode MMI or VU0
  macro-mode instructions. Use PCSXROO's live disassembler (`Roo.dis`) in VU code,
  such as the shared velocity step `00184540`.
- Bare numbers in PCSXROO breakpoint conditions are hex.
- Three PCSXROO fixes met here are on open PRs: shutting down a paused VM hung, an
  interrupted frame-advance could pause a later run by itself, and the hex rule was
  undocumented. Until they merge, resume before `shutdown`.
- The addresses in `tools/game/sandlot.py` are heap addresses in the user's Sandlot
  state, not constants of the game.

## Credits

`[60 FPS]` in PCSX2's patch database: PeterDelta. `[Widescreen 16:9]`: ElHecht, whose
hack the 19.5:9 group is built on. PCSX2's patch database and its contributors.

The players' list of 60fps defects the global audit started from: Devina, in the
[Kingdom Hearts 2 Final Mix 60fps hack](https://forums.pcsx2.net/Thread-Kingdom-Hearts-2-Final-Mix-60fps-hack)
thread on the PCSX2 forums (2015), and 王别情's 2017
[follow-up thread](https://forums.pcsx2.net/Thread-Kingdom-Hearts-2-Final-Mix-60fps-hack%EF%BC%88solve-some-problems-including-the-gravity%EF%BC%89).

Game-state addresses for this disc (`tools/game/world.py`): the Garden of Assemblage
ROM Edition's PCSX2-EX Lua script
([KH2FM-Mods-Num/GoA-ROM-Edition](https://github.com/KH2FM-Mods-Num/GoA-ROM-Edition)),
cross-checked against the [KH2 Lua Library](https://github.com/aliosgaming/KH2-Lua-Library).
Neither script is included here.

Workflow: Red-tv141's
[AI-Assisted 60fps Patch Development guide](https://forums.pcsx2.net/Thread-GUIDE-AI-Assisted-60fps-Patch-Development-for-PS2-Games-%E2%80%94-Full-Workflow),
by way of the sibling [pcsx2-bt3-60fps](https://github.com/Saupernova13/pcsx2-bt3-60fps).

## Licence

Code (`tools/`): **MIT**, see [`LICENSE`](LICENSE).
Docs, findings and this project's groups: **CC BY 4.0**, see
[`LICENSE-docs`](LICENSE-docs).
Neither covers the PCSX2 database groups these build on, or the community address
maps credited above, which belong to their authors.
