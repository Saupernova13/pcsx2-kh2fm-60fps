"""Trace the ball through 4 s of mashing in three arms, and split its sideways travel by source.

    python tools/mashtrace.py

First traces unpatched 60fps twice from the same state and reports any difference
(determinism: on 2026-09-15 there was none within one process). Then traces
30fps, 60fps and 60fps + [60 FPS - ball physics], recording per vsync the tick
counter, the collision-shape position, velocity (+0x20), the raw pushes the
displacement builder adds without delta (+0x560, +0x870), +0x880/+0x88C and the
displacement vectors (+0x850, +0x860). Writes work/mashtrace.npz (keys: cols,
o30, p60, p60b, f60), which tools/divergence.py mash reads.

What it showed: no raw pushes at all; hits set an absolute velocity - a pop-up
(0, -60, 0) or a side swipe (~51 horizontal, -42) - and the 60fps runs took side
swipes the 30fps run never did. Follow a writer with tools/watch.py.
"""

from __future__ import annotations

import argparse
import struct
import sys

import numpy as np

import _bootstrap  # noqa: F401

from game import config, sandlot, timing
from game.pnachtext import group_words

N = 240
SPANS = [(0x020, 16), (0x540, 48), (0x840, 96)]


def columns() -> list[str]:
    cols = ["ticks", "bx", "by", "bz"]
    for off, size in SPANS:
        cols += [f"+{off + 4 * k:03X}" for k in range(size // 4)]
    return cols


def trace(roo, fps: int, fix) -> np.ndarray:
    sandlot.prepare(roo, fps, fix)
    rows = []
    for t in range(N):
        sandlot.mash_step(roo, t)
        rec = [float(roo.read(timing.TICKS))]
        rec += list(struct.unpack("<3f", roo.read_bytes(sandlot.BALL_COLLISION, 12)))
        for off, size in SPANS:
            rec += list(struct.unpack(f"<{size // 4}f", roo.read_bytes(sandlot.BALL + off, size)))
        rows.append(rec)
        roo.frame_advance(1)
    roo.input_release()
    return np.array(rows)


def summary(name: str, a: np.ndarray, C: dict) -> None:
    def xz(x: str, z: str) -> np.ndarray:
        return np.hypot(a[:, C[x]], a[:, C[z]])

    ticks = a[:, 0]
    tick_rows = np.nonzero(np.diff(ticks) > 0)[0] + 1
    vy = a[:, C["+024"]]
    hits = [i for i in range(1, len(vy)) if vy[i] < -20 <= vy[i - 1]]
    print(f"===== {name}: ticks/vsync {(ticks[-1] - ticks[0]) / (len(ticks) - 1):.3f}  hits (vy<-20) at {hits}")
    print(f"  ball horizontal path             {float(np.sum(np.hypot(np.diff(a[:, 1]), np.diff(a[:, 3])))):8.1f}")
    print(f"  sum|v xz| per vsync (+020/+028)  {float(np.sum(xz('+020', '+028'))):8.1f}")
    print(f"  sum|disp/delta| +850 xz          {float(np.sum(xz('+850', '+858'))):8.1f}")
    print(f"  sum|disp/delta| +860 xz          {float(np.sum(xz('+860', '+868'))):8.1f}")
    for f0, f2 in (("+560", "+568"), ("+870", "+878"), ("+880", "+888")):
        per_tick = xz(f0, f2)[tick_rows]
        print(f"  sum|{f0} xz| over ticks (raw add) {float(np.sum(per_tick)):8.1f}   nonzero ticks {int(np.sum(per_tick > 1e-4))}")
    for h in hits[:6]:
        row = a[h]
        print(f"   hit @{h:3d}: v=({row[C['+020']]:7.2f},{row[C['+024']]:7.2f},{row[C['+028']]:7.2f})")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", type=int, default=28110)
    args = ap.parse_args()
    roo = sandlot.connect(args.port)
    fix = group_words(config.PATCHES / "kh2fm-60fps.pnach", "60 FPS - ball physics")
    cols = columns()
    C = {name: i for i, name in enumerate(cols)}

    print("##### determinism: 60fps unpatched mash traced twice")
    a1 = trace(roo, 60, None)
    a2 = trace(roo, 60, None)
    diff = np.abs(a1[:, 1:4] - a2[:, 1:4]).max(axis=1)
    first = next((i for i in range(N) if diff[i] > 1e-3), None)
    print(f"  max ball position difference {diff.max():.4f}; first divergence at vsync {first}")

    o30 = trace(roo, 30, None)
    f60 = trace(roo, 60, fix)
    config.WORK.mkdir(parents=True, exist_ok=True)
    np.savez(config.WORK / "mashtrace.npz", cols=np.array(cols), o30=o30, p60=a1, p60b=a2, f60=f60)
    for name, arr in (("30fps oracle", o30), ("60fps unpatched", a1), ("60fps + ball physics", f60)):
        summary(name, arr, C)
    return 0


if __name__ == "__main__":
    sys.exit(main())
