"""List every physics object in the Sandlot, and trace them all through the mash in three arms.

    python tools/objects.py

Breaks on the displacement builder (00183088, a0 = object) under run/wait to
collect the objects it moves, prints each one's class, vtable and motion routine
(vtable +0x1C) and position (+0x540), then traces every object's position through
130 vsyncs of the mash schedule at 30fps, 60fps and 60fps + [60 FPS - ball
physics]. Writes work/objtrace.npz, which tools/divergence.py reads.

2026-09-15: eleven objects, eight of class 01C60030 at rest and three of 01C60060
at the origin. The report then said Sora is not among them, and that the only
other object that flew, 01A94440, was a second prop. Both were wrong: 01A94440 is
Sora, and 01AADB90 and 01AC2490 are Donald and Goofy (tools/findplayer.py).
Characters go through the same builder and classes as props.
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


def f3(roo, addr: int) -> tuple[float, float, float]:
    return struct.unpack("<3f", roo.read_bytes(addr, 12))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", type=int, default=28110)
    args = ap.parse_args()
    roo = sandlot.connect(args.port)
    fix = group_words(config.PATCHES / "kh2fm-60fps.pnach", "60 FPS - ball physics")

    print(f"##### physics objects through the displacement builder {physics.DISPLACEMENT_BUILDER:08X}")
    sandlot.prepare(roo, 60)
    roo.bp_clear()
    roo.bp_add(physics.DISPLACEMENT_BUILDER, description="displacement builder entry")
    objs: dict[int, int] = {}
    try:
        for _ in range(60):
            seq = roo.seq()
            roo.resume()
            stop = roo.wait(seq, timeout_ms=5000)
            if stop is None:
                break
            a0 = roo.regs("GPR").get("a0", 0)
            objs[a0] = objs.get(a0, 0) + 1
    finally:
        roo.bp_clear()
        if not roo.paused():
            roo.pause()
    table = sorted(objs)
    for o in table:
        cls = roo.read(o + physics.OFF_CLASS)
        vt = roo.read(cls) if 0x00100000 <= cls < 0x02000000 else 0
        motion = roo.read(vt + 0x1C) if 0x00100000 <= vt < 0x02000000 else 0
        pos = f3(roo, o + physics.OFF_POSITION)
        tag = "BALL" if o == sandlot.BALL else "SORA" if o == sandlot.SORA else "PARTY" if o in sandlot.PARTY else ""
        print(f"  obj {o:08X} calls {objs[o]:2d}  class {cls:08X}  vtable {vt:08X}  motion {motion:08X}  "
              f"pos ({pos[0]:8.1f},{pos[1]:8.1f},{pos[2]:8.1f}) {tag}")

    print("##### every object's height through the mash (height = rest Y - Y; KH2 is negative-up)")
    results = {}
    for name, key, fps, words in (("30fps", "30fps", 30, None), ("60 unpatched", "60_unpatched", 60, None),
                                  ("60+ball physics", "60pFIX-D", 60, fix)):
        sandlot.prepare(roo, fps, words)
        rows = np.zeros((N, len(table), 3))
        for t in range(N):
            sandlot.mash_step(roo, t)
            for k, o in enumerate(table):
                rows[t, k] = f3(roo, o + physics.OFF_POSITION)
            roo.frame_advance(1)
        roo.input_release()
        results[key] = rows
        print(f"== {name}")
        for k, o in enumerate(table):
            h = rows[0, k, 1] - rows[:, k, 1]
            path = float(np.sum(np.hypot(np.diff(rows[:, k, 0]), np.diff(rows[:, k, 2]))))
            print(f"   {o:08X}  max height {h.max():7.1f} at {int(h.argmax()):3d}  xz path {path:7.1f}  /10v: "
                  + " ".join(f"{v:4.0f}" for v in h[::10]))
    config.WORK.mkdir(parents=True, exist_ok=True)
    np.savez(config.WORK / "objtrace.npz", objs=np.array(table, dtype=np.uint32), **results)
    print(f"saved {config.WORK / 'objtrace.npz'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
