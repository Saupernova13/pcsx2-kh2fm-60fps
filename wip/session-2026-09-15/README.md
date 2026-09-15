# Session 2026-09-15 - ball physics

The session that produced v02. The user's report: "Look at save state 1. Load it
in pcsxroo. Keep mashing x to keep the ball in the air. It works well in 30fps
mode. The 60fps patch breaks things though. Please assess and fix the gravity and
physics in the 60fps version." The full account is in
[`docs/findings.md`](../../docs/findings.md), "2026-09-15".

Everything here is archived as it ran. User-profile paths are replaced with
`%USERPROFILE%`, the session's scratch folder with `<session scratchpad>`, and
lines from other authors' patches with a `redacted` marker. Nothing else is
edited, including output that turned out to be wrong - the notes below say which.

## scripts/

The session's scratch scripts. They import `kh2lab` from the scratch folder and
will not run from here; every one has a maintained port in `tools/`, listed in
[`docs/tools.md`](../../docs/tools.md).

| Script | What it did |
|---|---|
| `kh2lab.py` | shared helpers: connect, arm switching (first by renaming the `[60 FPS]` group in PCSXROO's patch file, which did not work - see log 11) |
| `kh2_refs.py` | code in the save state's RAM that loads the `[60 FPS]` addresses |
| `kh2_accum.py` | the fixed-step accumulator and the delta globals |
| `kh2_transplant.py` | the save-state memory transplant |
| `kh2_findball.py` | first search for the ball's height by its gravity signature - defeated by `mem.search`'s cap and by the ball bobbing at rest |
| `kh2_capture.py`, `kh2_arcs.py` | full-RAM snapshots and the offline arc search |
| `kh2_tickrate.py` | the tick counter hunt and the free-running delta |
| `kh2_track.py` | dense tracking of the capture's survivors |
| `kh2_balltrack.py` | tracked `0037EC34` - the stack slot, not the ball |
| `kh2_balltest.py` | the acceptance test |
| `kh2_ws_probe.py`, `kh2_ws_values.py` | the previous day's widescreen scripts |

## logs/

Logs 01-05 are the session's background runs; 06-27 are foreground runs, taken
from the session transcript with the command that produced each. The numbering is
by source, not time. In the order they ran:

| Log | What it shows |
|---|---|
| `06` | 7 code references to the vsync wait `00349E1C`, 12 to game mode `0032BA24`, the frame routine's reads of `0036B0F4`/`0036B0F8`, and `001E6280`'s two of `0036EF20` |
| `01` | the CHD expanded to an ISO to get the ELF |
| `07` | the ELF's segments and the stock timing values |
| `08` | the transplant: EE 32 MB written in 7.8 s, timing words at their 60fps values |
| `09` | **the arm that did not switch**: captures and arc rankings identical at "60fps" and "30fps", delta 1.0 in both |
| `10` | why: `patches.zip` carries the same `[60 FPS]` for three CRCs (patch lines redacted) |
| `11` | the 30fps words written directly, and the vsync wait back at 0 on the next vsync |
| `12` | `Enable = 60 FPS` removed from PCSXROO's KH2 ini - after a reboot the arms work |
| `13` | the frame routine, the vsync wait loop and the vsync counter's writers, disassembled from the ELF |
| `14` | `0032B920` - the only counter stepping 20 at 60fps and 10 at 30fps; delta free-running reads 1.0 and 2.0 equally at 30fps |
| `15` | the vsync callback `0014CF18` registered at `0014D028` |
| `16` | the capture filters: 17817 candidates, 8741 of plausible size, 6109 with a vec4 w, 2480 that go up and come back - led by `0037EC34` |
| `17` | the fields around `0037EC34` and the copies at `0037EEB4..` - the AABB corners; really a stack slot |
| `18` | the real ball object: both arms per vsync, the velocity words at `+0x854`/`+0x864`, and the height's writer `0018A924` |
| `19` | the object's class and vtable, the constants in RAM, and the displacement builder and airborne integrator disassembled. Its read watchpoint found nothing in 5 s - an instrument failure, not a result. `gp 00000000` here is a thread outside the game loop |
| `20` | the live code cave survey (the `Swap X and O` words redacted) and the rest of the integrator |
| `21` | the same cave in the save state, and the gate's odd-phase simulation |
| `22` | the ELF words at the hook sites and both candidate groups, encoded and decoded back |
| `02` | acceptance: both candidates pass one hit at the other tick phase; unpatched and both candidates fail the 6 s mash |
| `03` | the mash trace: deterministic within a process, zero raw pushes, and the writers of the ball's velocity |
| `04` | a breakpoint firing under resume/wait, the 11 physics objects, `0019FBC4` disassembled, and every object traced through the mash |
| `23` | the code around the other five readers of 0.408163 - closed-form solves |
| `24` | their neighbouring constants and how each is reached |
| `05` | the search for Sora's position (35 copies of "the second prop" - which is Sora, so they were his; see [the audit session](../session-2026-09-15-audit/README.md)), then the mash as distributions over four hit timings |
| `25` | walking through the resting ball moves it 0.0 in every arm; the displacement contributor and collision resolver disassembled |
| `26` | the weak hits' writer is the hit handler; the three prop class vtables; what pushes the ground props (Donald and Goofy) |
| `27` | the install into the user's PCSX2, with backups, and the installed words compared with the tested ones |

Not archived, because nothing kept its output: the first `mem.search` attempts,
the velocity writer watch that named `00183384`/`0018342C`, the offline
first-divergence analysis (rerun it with `tools/divergence.py`), the props trace
(`tools/props.py`), and the acceptance run against the installed file. Their
results are recorded in the findings as reported at the time.
