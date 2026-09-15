# Releases

**There is no complete patch file in this repository, by design.** To install:

    python tools/install.py --widescreen      # or without --widescreen

That is the release. Everything else here is what it is built from.

    patch/kh2fm-60fps.pnach          this project's groups - not a complete patch file
    patch/widescreen-19.5x9-s24.json the widescreen change set, applied at install time
    git tags vNN-name                every version, tagged on main when it merges
    docs/versions/                   what every version changed and discovered
    wip/working.pnach                the working pnach - NOT for sharing

## Why no complete patch file

KH2FM's 60fps and widescreen patches are other people's work: PeterDelta's
`[60 FPS]` and ElHecht's `[Widescreen 16:9]`, both in PCSX2's own database. This
project only compensates the first and retargets the second. Those groups are
not this project's to redistribute, so the repo keeps only what it wrote, and
the installer adds that to the copy of the database patch the user already has.

- `[60 FPS - ball physics]`, `[60 FPS - short hop]` and `[60 FPS - friction]` are
  entirely this project's and ship as groups. Each hooks the game with the standard
  trampoline pattern, so a few of their words are the game's own instructions,
  relocated into the cave - three of the ball group's eighteen, for example.
- `[Widescreen 19.5:9 - S24 Ultra]` is ElHecht's group with five words changed and
  one added. Only those six words ship. `install.py --widescreen` builds the rest
  from the user's own `[Widescreen 16:9]`, after checking its 14 lines and every
  word it replaces, so a different database version cannot produce a bad group.

## Installing

`tools/install.py` does all of it:

1. Takes the patch PCSX2 already has for the game:
   `patches/SLPM-66675_FAF99301.pnach` if it exists, otherwise the
   `SLPM-66675_FAF99301.pnach` entry in PCSX2's `resources/patches.zip`, written out
   to `patches/`.
2. Removes any earlier copy of this project's groups, inserts every group in
   `patch/kh2fm-60fps.pnach` as one block after `[60 FPS]`, and with `--widescreen`
   builds the 19.5:9 group after `[Widescreen 16:9]`. Every other block stays byte
   for byte.
3. Validates each group it builds, backs up both files to `work/install-backups/`,
   and writes an enable line for each of our groups to
   `gamesettings/SLPM-66675_FAF99301.ini` - disabling `Widescreen 16:9` when the
   19.5:9 group is enabled.

`--status` shows each group, whether it is enabled, and whether the installed words
match this repo; `--dry-run` shows what would change; `--remove` takes our groups
back out.

**PCSX2 reads patch files and the ini at boot.** Quit and relaunch it - a reset or
save-state load is not enough - and don't change the game's settings in PCSX2's
menus while it is running with a hand-edited ini.

By hand, for anyone not running Python: copy the group blocks from
`patch/kh2fm-60fps.pnach` into PCSX2's `patches/SLPM-66675_FAF99301.pnach`
(extracting it from `patches.zip` first if there is none), after `[60 FPS]`, and
add one line per group under `[Patches]` in the game's ini, next to
`Enable = 60 FPS`:

    Enable = 60 FPS - ball physics
    Enable = 60 FPS - short hop
    Enable = 60 FPS - friction

## Why not share `wip/working.pnach`

It carries `[EXPERIMENT ball physics constant scaling]`, the withdrawn
alternative. Enabled with `[60 FPS - ball physics]` it compensates the ball twice,
and on its own it halves the ball's physics at 30fps. A pnach shows up as a list
of checkboxes, and a file that punishes ticking every box is a trap.
`tools/export.py` strips it.

## Cutting a new one

1. Generate or edit the group in `wip/working.pnach` (`mk*fix.py --write`), and run
   its `--check`.
2. Write `docs/versions/v04-something.md`: what it changes over v03 and what was
   discovered on the way. Add its row to [`versions/README.md`](versions/README.md)
   and update [`status.md`](status.md).
3. Export:

       python tools/export.py --release v04-something

4. Once its pull request is merged, tag the merge commit on main:

       git tag -a v04-something -m "v04-something: <one line from the note>"
       git push origin v04-something

`--release` refuses to run without the note, and refreshes `patch/`. If a change
touches the widescreen group, edit the JSON and check it with `tools/ws-math.py`.

## History

Every version, what it changed and what it discovered, is in
**[`versions/`](versions/README.md)**: v01 (widescreen, 2026-09-14), v02 (ball
physics, 2026-09-15) and v03 (movement physics, 2026-09-15). v01 and v02 predate
this repo; v03 is the first version built in it.

**No tag exists yet.** The versions arrive on main through pull requests #1 (v01 and
v02) and #2 (v03), and each is tagged as it merges: `v02-ball-physics` on #1's merge
commit, `v03-movement-physics` on #2's. v01 has no tag of its own - its only
artifact, the widescreen change set, is identical in v02. Until then, the `git show
vNN-name:...` lines at the bottom of each version note do not resolve.
