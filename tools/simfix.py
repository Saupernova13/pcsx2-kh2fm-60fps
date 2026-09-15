"""Simulate the ball's flight under each candidate fix, against the 30fps game. No emulator.

    python tools/simfix.py

The per-tick model, read off the airborne motion routine and confirmed by the
dense traces (docs/findings.md):
    hit sets vy = -60 (first stored after one update: -47.59)
    rising (vy < 0):  vy = 0.8 * vy + g        falling:  vy = vy + g        vy <= 10
    height -= vy * delta     (delta 2 at 30fps, 1 at 60fps)
    the Sandlot arch pins the ball at height 341.8

Candidates:
    A  unpatched 60fps
    B  drag sqrt(0.8), gravity g/2              (FIX-B, constant scaling)
    C  drag sqrt(0.8), gravity g/(1+k) rising, g/2 falling
    D  update only every other tick             (FIX-D, the tick gate), hit on either tick phase

Output 2026-09-15: with the arch, B, C and D all peak 341.8 and land 87-88 vs 88;
in free flight D-even is exact (417.6), B peaks 394.6, D-odd 370.0. The real game
then showed both D phases matching (tools/balltest.py --offset 0/1): the
simulation's odd-phase loss did not appear.
"""

from __future__ import annotations

import argparse
import math
import sys

G, DRAG, VMAX, V0, CEIL = 0.40817261, 0.8, 10.0, -47.591858, 341.8


def run(dt: int, k: float, g_rise: float, g_fall: float, gate: int | None = None,
        vsyncs: int = 240, ceil: float = CEIL) -> list[float]:
    v, h, hist, tick = V0, 0.0, [], 0
    while len(hist) < vsyncs:
        if tick > 0 and (gate is None or (tick + gate) % 2 == 0):
            v = min((v * k + g_rise) if v < 0 else (v + g_fall), VMAX)
        h = min(h - v * dt, ceil)
        landed = tick > 0 and h <= 0
        if landed:
            h = 0.0
        hist += [h] * dt
        tick += 1
        if landed:
            hist += [0.0] * vsyncs
    return hist[:vsyncs]


def metrics(hh: list[float], ceil: float) -> tuple[float, int, int, int | None]:
    peak = max(hh)
    contact = sum(1 for x in hh if x >= ceil - 1e-6)
    land = next((i for i in range(1, len(hh)) if hh[i] <= 0 < hh[i - 1]), None)
    return peak, hh.index(peak), contact, land


def main() -> int:
    argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter).parse_args()
    k = math.sqrt(DRAG)
    candidates = {
        "A unpatched 60fps": dict(dt=1, k=DRAG, g_rise=G, g_fall=G),
        "B drag sqrt, g/2": dict(dt=1, k=k, g_rise=G / 2, g_fall=G / 2),
        "C exact per branch": dict(dt=1, k=k, g_rise=G / (1 + k), g_fall=G / 2),
        "D gate, hit on even tick": dict(dt=1, k=DRAG, g_rise=G, g_fall=G, gate=0),
        "D gate, hit on odd tick": dict(dt=1, k=DRAG, g_rise=G, g_fall=G, gate=1),
    }
    for ceil, label in ((CEIL, "with the Sandlot arch"), (1e9, "free flight")):
        ref = run(2, DRAG, G, G, ceil=ceil)
        pk, tp, ct, ld = metrics(ref, ceil)
        print(f"== {label}: 30fps reference peak {pk:.1f} at {tp}, arch contact {ct} vsyncs, land {ld}")
        for name, params in candidates.items():
            hh = run(**params, ceil=ceil)
            pk, tp, ct, ld = metrics(hh, ceil)
            err = max(abs(a - b) for a, b in zip(hh, ref))
            print(f"   {name:26s} peak {pk:6.1f} at {tp:3d}  contact {ct:3d}  land {ld}  worst height error {err:6.1f}")
    print("(a worst error of 47.6 in every row is the first tick: 30fps moves 2*v0 at once, 60fps v0 per vsync)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
