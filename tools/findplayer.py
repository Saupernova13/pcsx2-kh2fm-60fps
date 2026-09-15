"""Find the player's position in RAM by walking one way and back. PCSXROO.

    python tools/findplayer.py                       # Sandlot state, LLeft then LRight
    python tools/findplayer.py --there LUp --back LDown --vsyncs 40

The first attempt to find the player (2026-09-15) looked for words that rose
during the juggle and found only copies of the second prop. Walking is a cleaner
signature: from one state, hold a direction for N vsyncs, then the opposite for
N, then let go. The player's position moves one way and back and then holds
still; an idle run from the same state, with no input, must show it not moving.
A world position is a vec4, so a w of 1.0 within the next three words is
required too.

Candidates are grouped into vec4s and reported with their lane (x, y or z by the
distance to w), their three deltas, and how many identical copies exist - the
camera target, the render matrix and stack slots all copy the player's position,
so the report lists every copy and the heap objects first.
"""

from __future__ import annotations

import argparse
import collections
import sys

import numpy as np

import _bootstrap  # noqa: F401

import ratediff
from game import sandlot

LO, HI = 0x00340000, 0x02000000


def floats(roo) -> np.ndarray:
    raw = ratediff.snapshot(roo)
    with np.errstate(invalid="ignore", over="ignore"):
        f = raw.view("<f4").astype(np.float64)
    return f, raw


def run(roo, args, walk: bool):
    ratediff.start_arm(roo, args.arm, args.slot)
    roo.frame_advance(args.lead)
    s0, raw0 = floats(roo)
    if walk:
        roo.input_set(args.there)
    roo.frame_advance(args.vsyncs)
    s1, _ = floats(roo)
    if walk:
        roo.input_set(args.back)
    roo.frame_advance(args.vsyncs)
    roo.input_release()
    s2, _ = floats(roo)
    roo.frame_advance(args.settle)
    s3, _ = floats(roo)
    return s0, s1, s2, s3, raw0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--slot", type=int, default=sandlot.SLOT)
    ap.add_argument("--arm", default="60", choices=list(ratediff.ARMS))
    ap.add_argument("--there", default="LLeft")
    ap.add_argument("--back", default="LRight")
    ap.add_argument("--vsyncs", type=int, default=40)
    ap.add_argument("--lead", type=int, default=10)
    ap.add_argument("--settle", type=int, default=20)
    ap.add_argument("--min-step", type=float, default=15.0)
    ap.add_argument("--top", type=int, default=40)
    ap.add_argument("--port", type=int, default=28110)
    args = ap.parse_args()

    roo = sandlot.connect(args.port)
    w0, w1, w2, w3, raw = run(roo, args, walk=True)
    i0, _, i2, i3, _ = run(roo, args, walk=False)

    with np.errstate(invalid="ignore"):
        ok = np.ones(w0.size, dtype=bool)
        for s in (w0, w1, w2, w3, i0, i2, i3):
            ok &= np.isfinite(s) & (np.abs(s) < 1e5)
        d1, d2, d3 = w1 - w0, w2 - w1, w3 - w2
        idle = np.maximum(np.abs(i2 - i0), np.abs(i3 - i2))
        cand = ok & (np.abs(d1) >= args.min_step) & (np.abs(d2) >= args.min_step) \
            & (np.sign(d1) != np.sign(d2)) & (np.abs(d3) < 2.0) & (idle < 1.0)
    one = raw == 0x3F800000
    lane = np.full(w0.size, -1)
    for k, name in ((1, 2), (2, 1), (3, 0)):     # w at +4 -> z lane, +8 -> y, +12 -> x
        hit = np.zeros(w0.size, dtype=bool)
        hit[:-k] = one[k:]
        lane[hit & (lane < 0)] = name
    idx = np.flatnonzero(cand & (lane >= 0))
    print(f"{int(cand.sum())} words walk there and back and hold still idle; {idx.size} sit in a vec4")

    # Collapse each hit to its vec4 base and count identical copies of the xyz triple.
    bases = sorted({int(i) - int(lane[i]) for i in idx})
    triples = {b: tuple(np.round(w2[b:b + 3], 3)) for b in bases if b + 3 <= w2.size}
    copies = collections.defaultdict(list)
    for b, t in triples.items():
        copies[t].append(b)
    print(f"{len(bases)} vec4s, {len(copies)} distinct positions")
    print(f"{'vec4':>10}  {'x':>10} {'y':>10} {'z':>10}   {'d there':>28}   {'d back':>28}  copies")
    shown = 0
    for t, group in sorted(copies.items(), key=lambda kv: -len(kv[1])):
        for b in group:
            a = LO + 4 * b
            dt = " ".join(f"{v:9.2f}" for v in (w1[b:b + 3] - w0[b:b + 3]))
            db = " ".join(f"{v:9.2f}" for v in (w2[b:b + 3] - w1[b:b + 3]))
            where = "heap" if a >= 0x01000000 else "data/stack"
            print(f"  {a:08X}  {w2[b]:10.2f} {w2[b + 1]:10.2f} {w2[b + 2]:10.2f}   {dt}   {db}  {len(group)} {where}")
            shown += 1
        if shown >= args.top:
            break
    return 0


if __name__ == "__main__":
    sys.exit(main())
