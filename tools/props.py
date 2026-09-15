"""The ball and Sora through the mash: class switches, velocity and impulses, per vsync.

    python tools/props.py

Records, for the ball (01ADD9D0) and Sora (01A94440), the class pointer (+0x0C),
velocity (+0x20..+0x2C), position (+0x540..) and +0x120..+0x124, through 130
vsyncs of the mash at 30fps and at 60fps + [60 FPS - ball physics]. Prints every
class change and every impulse (vy jumping up by more than 5, or horizontal speed
jumping by more than 5). Writes work/props.npz.

2026-09-15: both launch at the same vsync in both arms (the ball at 26/27 into
class 01C60340, 01A94440 at 51 into class 01C60040), but at 60fps the ball took
weak -10 hits at vsyncs 67 and 91 and a side swipe at 116 that 30fps never got.
01A94440 was reported then as "prop 2". Walking it away and back later showed it
is Sora, and 01C60040 is the class characters fly in (tools/findplayer.py); the
tool keeps its name.
"""

from __future__ import annotations

import argparse
import struct
import sys

import numpy as np

import _bootstrap  # noqa: F401

from game import config, physics, sandlot
from game.pnachtext import group_words

N = 130


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", type=int, default=28110)
    args = ap.parse_args()
    roo = sandlot.connect(args.port)
    fix = group_words(config.PATCHES / "kh2fm-60fps.pnach", "60 FPS - ball physics")
    saved = {}
    for key, fps, words in (("o30", 30, None), ("f60", 60, fix)):
        sandlot.prepare(roo, fps, words)
        rows = np.zeros((N, 2, 10))
        cls = np.zeros((N, 2), dtype=np.uint32)
        ticks = np.zeros(N, dtype=np.int64)
        for t in range(N):
            sandlot.mash_step(roo, t)
            ticks[t] = roo.read(0x0032B920)
            for k, obj in enumerate((sandlot.BALL, sandlot.SORA)):
                cls[t, k] = roo.read(obj + physics.OFF_CLASS)
                rows[t, k, 0:4] = struct.unpack("<4f", roo.read_bytes(obj + physics.OFF_VELOCITY, 16))
                rows[t, k, 4:8] = struct.unpack("<4f", roo.read_bytes(obj + physics.OFF_POSITION, 16))
                rows[t, k, 8:10] = struct.unpack("<2f", roo.read_bytes(obj + physics.OFF_TERMINAL, 8))
            roo.frame_advance(1)
        roo.input_release()
        saved.update({f"{key}_rows": rows, f"{key}_cls": cls, f"{key}_ticks": ticks})
        print(f"== {key}: class pointer changes")
        for k, label in enumerate(("ball", "sora")):
            changes = [f"{t}:{cls[t - 1, k]:08X}->{cls[t, k]:08X}" for t in range(1, N) if cls[t, k] != cls[t - 1, k]]
            print(f"   {label}: " + " ".join(changes))
            impulses = [f"{t}(v {rows[t - 1, k, 1]:.1f}->{rows[t, k, 1]:.1f}, xz {np.hypot(rows[t, k, 0], rows[t, k, 2]):.1f})"
                        for t in range(1, N)
                        if rows[t, k, 1] < rows[t - 1, k, 1] - 5
                        or np.hypot(rows[t, k, 0], rows[t, k, 2]) > np.hypot(rows[t - 1, k, 0], rows[t - 1, k, 2]) + 5]
            print(f"   {label} impulses: " + " ".join(impulses))
    config.WORK.mkdir(parents=True, exist_ok=True)
    np.savez(config.WORK / "props.npz", **saved)
    print(f"saved {config.WORK / 'props.npz'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
