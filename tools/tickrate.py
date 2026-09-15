"""Prove each A/B arm really runs at its rate: game-tick counters, and the delta free-running.

    python tools/tickrate.py

Per arm: load the Sandlot state paused, write the arm's three words, then
  - three EE RAM dumps 20 vsyncs apart: integer words that step by the same
    amount twice are counters, and a game-tick counter steps 20 at 60fps and 10 at 30fps
  - a few seconds free-running, sampling the frame delta while it runs

This is how 0032B920 was found (2026-09-15), and how the "30fps arm reads delta
1.0" scare was settled: free-running, the 30fps arm reads 1.0 and 2.0 in equal
numbers, because a paused VM sits inside the frame routine's vsync wait, between
the pre-wait write (1.0) and the post-wait write (2.0).
"""

from __future__ import annotations

import argparse
import struct
import sys
import time
from collections import Counter

import numpy as np

import _bootstrap  # noqa: F401

from game import sandlot, timing

LO, HI = 0x00100000, 0x02000000
CHUNK = 4 * 1024 * 1024
STEP = 20


def dump(roo) -> np.ndarray:
    parts = [roo.read_bytes(a, min(CHUNK, HI - a)) for a in range(LO, HI, CHUNK)]
    return np.frombuffer(b"".join(parts), dtype=np.uint32).astype(np.int64)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", type=int, default=28110)
    args = ap.parse_args()
    roo = sandlot.connect(args.port)
    steps = {}
    for fps, words in ((60, timing.PATCHED), (30, timing.STOCK)):
        print(f"===== {fps}fps arm")
        if not roo.paused():
            roo.pause()
        roo.loadstate(sandlot.SLOT)
        for a, v in words.items():
            roo.write(a, v)
        roo.frame_advance(2)
        a0 = dump(roo)
        roo.frame_advance(STEP)
        a1 = dump(roo)
        roo.frame_advance(STEP)
        a2 = dump(roo)
        d1, d2 = a1 - a0, a2 - a1
        steady = (d1 == d2) & (d1 > 0) & (d1 <= 4 * STEP)
        steps[fps] = np.where(steady, d1, 0)
        print(f"  steady counters by step per {STEP} vsyncs: {dict(sorted(Counter(int(x) for x in d1[steady]).items()))}")

        roo.resume()
        deltas, counts = Counter(), Counter()
        t_end = time.time() + 4.0
        while time.time() < t_end:
            deltas[round(struct.unpack('<f', roo.read_bytes(timing.DELTA, 4))[0], 3)] += 1
            counts[roo.read(timing.VSYNC_COUNT)] += 1
            time.sleep(0.02)
        roo.pause()
        print(f"  free-run delta samples: {dict(deltas)}")
        print(f"  free-run vsync-count samples: {dict(counts)}")
        print("  words still at arm values: " + ", ".join(f"{a:08X}={roo.read(a):08X}" for a in words))

    tick = np.nonzero((steps[60] == STEP) & (steps[30] == STEP // 2))[0]
    clocks = np.nonzero((steps[60] == STEP) & (steps[30] == STEP))[0]
    print(f"===== counters stepping {STEP} at 60fps and {STEP // 2} at 30fps: {len(tick)}")
    for i in tick[:12]:
        print(f"  {LO + 4 * int(i):08X}")
    print(f"===== counters stepping {STEP} in BOTH arms (per-vsync clocks): {len(clocks)}")
    for i in clocks[:6]:
        print(f"  {LO + 4 * int(i):08X}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
