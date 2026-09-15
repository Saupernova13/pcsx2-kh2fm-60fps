"""Mash outcomes as distributions: every arm at several hit timings, so chaos is averaged out.

    python tools/mashdist.py                   # offsets 0..3, 4 s each, four arms
    python tools/mashdist.py --offsets 0,1 --seconds 6

Arms: 30fps, 60fps unpatched, 60fps + the constant-scaling experiment, 60fps +
[60 FPS - ball physics]. Metrics as in tools/balltest.py --mash.

2026-09-15 (offsets 0..3, 4 s): the mash failure is systematic, not noise.
  30fps           airborne 67%   landings 1  mean height 277  max 346  travel 159
  60fps           airborne 74%   landings 1  mean height 158  max 231  travel 380
  60fps + scaling airborne 100%  landings 0  mean height 377  max 556  travel 490
  60fps + gate    airborne 100%  landings 0  mean height 374  max 561  travel 662
The arch caps the ball at ~346 at 30fps; with either fix it is knocked out from
under it. The same run's attempt to find Sora's position by RAM diff found only
copies of what was then called the second prop, and concluded Sora is not a plain
vec4 near the ball. Wrong: that object is Sora, so the copies were his
(tools/findplayer.py).
"""

from __future__ import annotations

import argparse
import sys

import numpy as np

import _bootstrap  # noqa: F401

import balltest
from game import config, sandlot
from game.pnachtext import group_words

KEYS = ("airborne", "landings", "mean_height", "max_height", "travel")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--offsets", default="0,1,2,3")
    ap.add_argument("--seconds", type=float, default=4.0)
    args = ap.parse_args()
    offsets = [int(o) for o in args.offsets.split(",")]

    arms = (("30fps", 30, None), ("60 unpatched", 60, None),
            ("60+scaling", 60, group_words(config.WIP / "working.pnach", "EXPERIMENT ball physics constant scaling")),
            ("60+gate", 60, group_words(config.PATCHES / "kh2fm-60fps.pnach", "60 FPS - ball physics")))
    roo = sandlot.connect()
    summary = {}
    for name, fps, fix in arms:
        runs = []
        for off in offsets:
            m = balltest.mash_metrics(balltest.mash(roo, fps, fix, off, args.seconds))
            runs.append(m)
            if m["hit"]:
                print(f"  {name:13s} off {off}: airborne {m['airborne']:5.1%} landings {m['landings']} "
                      f"mean h {m['mean_height']:6.1f} max {m['max_height']:6.1f} travel {m['travel']:6.1f}")
            else:
                print(f"  {name:13s} off {off}: no hit")
        summary[name] = [r for r in runs if r["hit"]]
    print("== mean (sd) per arm")
    for name, runs in summary.items():
        cells = []
        for k in KEYS:
            v = np.array([r[k] for r in runs], dtype=float)
            cells.append(f"{k} {v.mean():7.2f} ({v.std():6.2f})" if len(v) else f"{k} -")
        print(f"  {name:13s} " + "  ".join(cells))
    return 0


if __name__ == "__main__":
    sys.exit(main())
