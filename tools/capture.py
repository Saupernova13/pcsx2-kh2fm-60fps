"""Capture full EE RAM snapshots around one hit of the Sandlot ball, for offline arc search.

    python tools/capture.py --fps 60
    python tools/capture.py --fps 60 --times 4,8,12,16,24,32,44,60 --walk 8

Three snapshots while idle, then Sora walks to the ball and presses Cross, then a
snapshot at each listed vsync after the press (the same schedule in every arm).
Writes work/cap-<fps>.npz (14 x 7.9 M words, ~430 MB) and a screenshot at
--shot-at. tools/arcs.py searches it; tools/track.py follows the survivors.

History: mem.search caps a session at 100000 values, far below the ~8 M floats in
RAM, and an idle-change filter threw the ball away because the orb bobs at rest.
Diffing whole-RAM dumps in numpy was the version that worked (2026-09-15).
"""

from __future__ import annotations

import argparse
import struct
import sys

import numpy as np

import _bootstrap  # noqa: F401

from game import config, sandlot, timing

LO, HI = 0x00100000, 0x02000000
CHUNK = 4 * 1024 * 1024


def dump(roo) -> np.ndarray:
    parts = [roo.read_bytes(a, min(CHUNK, HI - a)) for a in range(LO, HI, CHUNK)]
    return np.frombuffer(b"".join(parts), dtype=np.uint32).copy()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--fps", type=int, default=60, choices=(30, 60))
    ap.add_argument("--times", default="16,24,28,32,36,40,48,56,64,80,100")
    ap.add_argument("--shot-at", type=int, default=30)
    ap.add_argument("--walk", type=int, default=sandlot.WALK_VSYNCS)
    args = ap.parse_args()
    times = [int(t) for t in args.times.split(",")]

    roo = sandlot.connect()
    sandlot.start(roo, args.fps)
    print(f"arm {args.fps}fps  delta {struct.unpack('<f', roo.read_bytes(timing.DELTA, 4))[0]}")

    snaps, labels = [], []
    for k in range(3):
        if k:
            roo.frame_advance(3)
        snaps.append(dump(roo))
        labels.append(-3 * (2 - k) - 1)

    if args.walk:
        roo.input_set(*sandlot.WALK_BUTTONS)
        roo.frame_advance(args.walk)
        roo.input_release()

    now = 0
    roo.input_set("Cross")
    roo.frame_advance(sandlot.PRESS_VSYNCS)
    roo.input_release()
    now += sandlot.PRESS_VSYNCS
    for t in times:
        if now < args.shot_at <= t:
            roo.frame_advance(args.shot_at - now)
            now = args.shot_at
            sandlot.shot(roo, f"cap-{args.fps}-t{args.shot_at}.png")
            now += 1
        if t > now:
            roo.frame_advance(t - now)
            now = t
        snaps.append(dump(roo))
        labels.append(now)
        print(f"  snapshot at vsync {now}")

    config.WORK.mkdir(parents=True, exist_ok=True)
    out = config.WORK / f"cap-{args.fps}.npz"
    np.savez(out, lo=LO, labels=np.array(labels), snaps=np.stack(snaps))
    print(f"saved {out} ({len(snaps)} snapshots)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
