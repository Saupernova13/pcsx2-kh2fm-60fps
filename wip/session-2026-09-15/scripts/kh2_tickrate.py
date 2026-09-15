"""Does the 30fps arm really tick half as often? And what does delta read free-running?

Per arm: load slot 1 paused, write the arm's three words, then
  - three EE RAM dumps 20 vsyncs apart; integer words that step by the same
    amount twice are counters, and a game-tick counter steps 20 at 60fps and
    10 at 30fps
  - free-run for a few seconds, sampling the frame delta while running
"""
import struct
import sys
import time
from collections import Counter
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path.home() / "Documents" / "GitHub" / "pcsxroo" / "pcsxroo"))

from ps2ee.roo import Roo  # noqa: E402

LO, HI = 0x00100000, 0x02000000
CHUNK = 4 * 1024 * 1024
ARMS = {
    60: {0x00349E1C: 0, 0x0036B0F8: 0x3F800000, 0x0036EF20: 0x3F800000},
    30: {0x00349E1C: 1, 0x0036B0F8: 0x40C00000, 0x0036EF20: 0x40000000},
}
STEP = 20


def dump(roo) -> np.ndarray:
    parts = [roo.read_bytes(a, min(CHUNK, HI - a)) for a in range(LO, HI, CHUNK)]
    return np.frombuffer(b"".join(parts), dtype=np.uint32).astype(np.int64)


def f32(roo, a):
    return struct.unpack("<f", roo.read_bytes(a, 4))[0]


def main() -> int:
    roo = Roo(28110).connect()
    steps = {}
    for fps, words in ARMS.items():
        print(f"===== {fps}fps arm")
        roo.loadstate(1)
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
        hist = Counter(int(x) for x in d1[steady])
        print(f"  steady counters by step per {STEP} vsyncs: {dict(sorted(hist.items()))}")

        roo.resume()
        seen = Counter()
        counts = Counter()
        t_end = time.time() + 4.0
        while time.time() < t_end:
            seen[round(f32(roo, 0x00349E10), 3)] += 1
            counts[roo.read(0x00349E08)] += 1
            time.sleep(0.02)
        roo.pause()
        print(f"  free-run delta samples: {dict(seen)}")
        print(f"  free-run vsync-count samples: {dict(counts)}")
        print(f"  words still at arm values: " + ", ".join(
            f"{a:08X}={roo.read(a):08X}" for a in words))

    s60, s30 = steps[60], steps[30]
    tick = np.nonzero((s60 == STEP) & (s30 == STEP // 2))[0]
    same = np.nonzero((s60 == STEP) & (s30 == STEP))[0]
    print(f"===== counters stepping {STEP} at 60fps and {STEP // 2} at 30fps: {len(tick)}")
    for i in tick[:12]:
        print(f"  {LO + 4 * int(i):08X}")
    print(f"===== counters stepping {STEP} in BOTH arms (per-vsync clocks): {len(same)}")
    for i in same[:6]:
        print(f"  {LO + 4 * int(i):08X}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
