# wip/

**Looking for the patch to install? It is not here.**
Run [`tools/install.py`](../tools/install.py); the groups it adds are in
[`patch/`](../patch/).

    working.pnach             the working pnach: our shipped group plus a withdrawn
                              candidate that must never be enabled. The tools read
                              this file; people do not.
    experiments/              numbered candidate files, kept as they were tested
    session-2026-09-14/       the widescreen session's logs
    session-2026-09-15/       the ball physics session's scratch scripts and logs,
                              archived as they ran

`working.pnach` is the source `patch/kh2fm-60fps.pnach` is cut from, not the
release itself. It carries `[EXPERIMENT ball physics constant scaling]` - FIX-B in
[`docs/findings.md`](../docs/findings.md), the alternative the tick gate beat. It
passed the single-hit test, but leaves the horizontal decay uncompensated, peaks
5.5% low in free flight, and would halve the ball's physics at 30fps; enabled with
`[60 FPS - ball physics]` it compensates twice. `tools/export.py` strips it.

To cut a release: `python tools/export.py --release vNN-name`, then tag the
commit. See [`docs/releases.md`](../docs/releases.md).

The session folders are a record, not tools. Their scripts expect a scratch
folder that no longer exists; every one of them has a maintained port in
`tools/` (see [`docs/tools.md`](../docs/tools.md)). User-profile paths in them are
replaced with placeholders, and lines from other authors' patches are redacted.
