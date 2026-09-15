# Version history

Every version of this project's groups: what it changed over the one before it,
and what was discovered on the way.

**To install, run [`tools/install.py`](../../tools/install.py).** It adds this
project's groups to the database patch PCSX2 already has for the game; nothing in
this repo is a complete patch file. See [`releases.md`](../releases.md).

| version | date | our groups | what it did | confidence |
|---|---|---|---|---|
| [`v01`](v01-widescreen-s24.md) | 2026-09-14 | 1 | 19.5:9 widescreen for the Galaxy S24 Ultra, built from the database's 16:9 group | arithmetic verified, not seen on screen\* |
| [`v02`](v02-ball-physics.md) | 2026-09-15 | 2 | the Sandlot ball's drag and gravity at real speed under `[60 FPS]` | single hit measured, not played\*; long juggles not fixed |
| [`v03`](v03-movement-physics.md) | 2026-09-15 | 4 | short hops at full height; friction, lunges and acceleration at real speed for everything that uses the shared velocity step | measured, not played\*; juggle still differs |

A \* marks a build verified by measurement but not yet confirmed in play. Per-build
confidence is kept current in [`status.md`](../status.md), and the full record is
in [`findings.md`](../findings.md).

## Reading the lineage

- **v01 and v02 predate the repo.** They were built and installed straight into
  the user's PCSX2 on 2026-09-14 and 2026-09-15, and the repo was assembled from
  that work afterwards. v03 is the first version built in the repo. v01 has no tag of its own: its only artifact, the
  widescreen change set, is identical in v02.
- **v01 is not a file.** The widescreen group is five changed words and one added
  word on ElHecht's 16:9 group, so the repo keeps the change set as JSON and the
  installer builds the group on the user's machine.

## Adding a version

`tools/export.py --release NAME` refuses to run until `docs/versions/NAME.md`
exists. Write the note first - what the version changes over the last one, and
what was discovered - add its row here, then cut the release and tag it. See
[`releases.md`](../releases.md).
