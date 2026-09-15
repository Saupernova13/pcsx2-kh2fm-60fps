"""Search saved RAM snapshots for a thrown object's height.

Keeps float words whose excursion during the flight is far larger than their
wobble while idle, then fits a parabola to the flight up to the landing.
Works whichever way the vertical axis points.

    python kh2_arcs.py cap-60.npz [--top 40]
"""
import argparse
import struct

import numpy as np


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("npz")
    ap.add_argument("--top", type=int, default=40)
    ap.add_argument("--min-excursion", type=float, default=1.0)
    args = ap.parse_args()

    z = np.load(args.npz)
    lo = int(z["lo"])
    labels = z["labels"].astype(np.float64)
    snaps = z["snaps"]
    f = snaps.view(np.float32).astype(np.float64)
    idle, fly = f[:3], f[3:]
    t = labels[3:]

    ok = np.all(np.isfinite(f), axis=0) & np.all(np.abs(f) < 1e6, axis=0)
    idle_range = idle.max(axis=0) - idle.min(axis=0)
    ground = idle.mean(axis=0)
    excursion = np.abs(fly - ground).max(axis=0)
    keep = ok & (excursion > args.min_excursion) & (excursion > 20 * (idle_range + 1e-3))
    cand = np.nonzero(keep)[0]
    print(f"{len(cand)} words move far more in flight than at rest")

    rows = []
    for i in cand:
        y = fly[:, i] - ground[i]
        peak = int(np.argmax(np.abs(y)))
        if peak == 0 or peak == len(y) - 1:
            continue
        # flight window: from the last sample still at rest (the hit lands a
        # while after the press), through the peak, until it is back near the
        # ground
        begin = 0
        for j in range(peak, -1, -1):
            if abs(y[j]) < 0.05 * abs(y[peak]):
                begin = j
                break
        end = len(y)
        for j in range(peak + 1, len(y)):
            if abs(y[j]) < 0.1 * abs(y[peak]):
                end = j + 1
                break
        tt, yy = t[begin:end], y[begin:end]
        if len(tt) < 4:
            continue
        coef, res, *_ = np.polyfit(tt, yy, 2, full=True)
        ss = float(np.sum((yy - yy.mean()) ** 2)) or 1e-9
        r2 = 1 - (float(res[0]) if len(res) else 0.0) / ss
        a = int(lo + 4 * i)
        rows.append((r2, a, coef[0], abs(y[peak]), labels[3 + peak], end))

    rows.sort(key=lambda r: (-r[0], -r[3]))
    last = snaps[-1]
    print("r2      addr      accel/vsync^2   peak   at vsync  pts   neighbours (f32 at -8..+12)")
    for r2, a, acc, pk, at, n in rows[: args.top]:
        k = (a - lo) // 4
        nb = " ".join(f"{struct.unpack('<f', struct.pack('<I', int(last[k + d])))[0]:9.3f}"
                      for d in range(-2, 4) if 0 <= k + d < len(last))
        print(f"{r2:.4f}  {a:08X}  {acc * 2:+12.5f}  {pk:8.2f}  {int(at):5d}  {n:3d}   {nb}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
