"""Track the words that moved in a sparse capture, every vsync, and rank the arcs.

    python tools/track.py --from work/cap-60.npz --fps 60 --vec4

Replays the capture's input schedule, then reads only the candidate words each
vsync. --vec4 keeps words with a w = 1.0 within the next three words and an
excursion of 5..2000 units - a world position - which cut ~17800 candidates to
~6100 on 2026-09-15. Writes work/track-<fps>.npz.

It was this route that led to 0037EC34 - which then turned out to be a stack
slot (the AABB centre every object's collision computes), not the ball. The real
object came from matching that slot's X/Z/Y against the rest of RAM; see
tools/ballobj.py and docs/findings.md.
"""

from __future__ import annotations

import argparse
import struct
import sys

import numpy as np

import _bootstrap  # noqa: F401

from game import config, sandlot


def candidates(npz: str, vec4: bool) -> list[int]:
    z = np.load(npz)
    lo = int(z["lo"])
    snaps = z["snaps"]
    with np.errstate(invalid="ignore", over="ignore"):
        f = snaps.view(np.float32).astype(np.float64)
        idle, fly = f[:3], f[3:]
        ok = np.all(np.isfinite(f), axis=0) & np.all(np.abs(f) < 1e5, axis=0)
        ok &= np.all((np.abs(f) > 1e-6) | (f == 0), axis=0)   # drop pointers read as denormals
        idle_range = idle.max(axis=0) - idle.min(axis=0)
        excursion = np.abs(fly - idle.mean(axis=0)).max(axis=0)
    keep = ok & (excursion > 1.0) & (excursion > 20 * (idle_range + 1e-3))
    if vec4:
        one = snaps[2] == 0x3F800000
        near = np.zeros_like(one)
        for k in (1, 2, 3):
            near[:-k] |= one[k:]
        keep &= near & (excursion >= 5) & (excursion <= 2000)
    return [lo + 4 * int(i) for i in np.nonzero(keep)[0]]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--from", dest="src", required=True)
    ap.add_argument("--fps", type=int, default=60, choices=(30, 60))
    ap.add_argument("--vec4", action="store_true")
    ap.add_argument("--vsyncs", type=int, default=120)
    ap.add_argument("--top", type=int, default=30)
    args = ap.parse_args()

    addrs = candidates(args.src, args.vec4)
    blocks = sandlot.spans(addrs, gap=64)
    idx = {a: i for i, a in enumerate(addrs)}
    print(f"{len(addrs)} candidates in {len(blocks)} spans")

    roo = sandlot.connect()
    sandlot.prepare(roo, args.fps)
    sandlot.press_cross(roo)

    series = np.zeros((args.vsyncs, len(addrs)), dtype=np.float64)
    for t in range(args.vsyncs):
        for lo, hi in blocks:
            vals = struct.unpack(f"<{(hi - lo) // 4}f", roo.read_bytes(lo, hi - lo))
            for k, v in enumerate(vals):
                i = idx.get(lo + 4 * k)
                if i is not None:
                    series[t, i] = v
        roo.frame_advance(1)

    config.WORK.mkdir(parents=True, exist_ok=True)
    out = config.WORK / f"track-{args.fps}.npz"
    np.savez(out, addrs=np.array(addrs, dtype=np.uint32), series=series)
    print(f"saved {out}")

    rows = []
    for i, a in enumerate(addrs):
        y = series[:, i]
        moving = np.abs(np.diff(y)) > 1e-3
        if int(moving.sum()) < 20:
            continue
        best, run, best_end = 0, 0, 0
        for j, m in enumerate(moving):
            run = run + 1 if m else 0
            if run > best:
                best, best_end = run, j
        s = best_end - best + 1
        seg = y[s:best_end + 2]
        if len(seg) < 12:
            continue
        tt = np.arange(len(seg), dtype=np.float64)
        coef, res, *_ = np.polyfit(tt, seg, 2, full=True)
        ss = float(np.sum((seg - seg.mean()) ** 2)) or 1e-9
        r2 = 1 - (float(res[0]) if len(res) else 0.0) / ss
        d2 = np.diff(seg, 2)
        sign = abs(np.sign(d2).sum()) / max(len(d2), 1)
        rows.append((r2 * sign, r2, sign, a, 2 * coef[0], float(seg.max() - seg.min()), s, len(seg)))

    rows.sort(key=lambda r: -r[0])
    print("score   r2      sign   addr      accel/vsync^2  span     start  len")
    for sc, r2, sg, a, acc, span, s, n in rows[: args.top]:
        print(f"{sc:.4f}  {r2:.4f}  {sg:.2f}  {a:08X}  {acc:+13.5f}  {span:8.2f}  {s:5d}  {n:3d}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
