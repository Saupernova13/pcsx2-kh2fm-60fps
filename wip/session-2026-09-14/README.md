# Session 2026-09-14 - widescreen 19.5:9

The session that produced v01. The user asked, with the BT3 repo as the
reference, for their KH2FM 16:9 patch to be switched off and a patch rendering at
the Galaxy S24 Ultra's aspect added and enabled. The full account is in
[`docs/findings.md`](../../docs/findings.md), "2026-09-14".

    logs/01-compute-float-hex-and-verify-instruction-encodings.txt
        12/19.5 as a float word, the 16:9 check, and the three instructions encoded
        and decoded back
    logs/02-parse-patch-file-and-list-its-groups.txt
        the installed patch file parsed back: every group and its line count
    logs/03-show-final-kh2fm-game-settings.txt
        the per-game ini after the change

The scripts behind them, `kh2_ws_probe.py` (disassembles the projection routine
from the running game over PINE) and `kh2_ws_values.py`, are archived with the
next session's in `../session-2026-09-15/scripts/`; their maintained port is
`tools/ws-math.py`.

Not archived: the probe's own output, because it is a live-RAM listing of the
routine with ElHecht's 16:9 words applied - his patch, not this project's. Run
`python tools/ws-math.py --live` against your own game to see it.
