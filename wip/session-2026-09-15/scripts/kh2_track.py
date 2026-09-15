"""Track the words that moved in a sparse capture, every vsync, and rank arcs.

Replays exactly the input schedule kh2_capture.py used (6 idle vsyncs, walk,
Cross), then reads only the candidate words each vsync. Dense samples make a
parabola fit meaningful: the ball's height should show a long run of moving
samples with a steady second difference of one sign.

    python kh2_track.py --from cap-60.npz --fps 60 [--walk 8] [--vsyncs 120]
"""
import argparse
import struct

import numpy as np

import kh2lab


def candidates(npz: str, vec4: bool) -> list[int]:
    z = np.load(npz)
    lo = int(z["lo"])
    snaps = z["snaps"]
    f = snaps.view(np.float32).astype(np.float64)
    idle, fly = f[:3], f[3:]
    with np.errstate(invalid="ignore", over="ignore"):
        ok = np.all(np.isfinite(f), axis=0) & np.all(np.abs(f) < 1e5, axis=0)
        ok &= np.all((np.abs(f) > 1e-6) | (f == 0), axis=0)   # drop pointers read as denormals
        idle_range = idle.max(axis=0) - idle.min(axis=0)
        excursion = np.abs(fly - idle.mean(axis=0)).max(axis=0)
    keep = ok & (excursion > 1.0) & (excursion > 20 * (idle_range + 1e-3))
    if vec4:
        # a world position is a vec4 with w = 1.0 within the next three words
        one = snaps[2] == 0x3F800000
        near = np.zeros_like(one)
        for k in (1, 2, 3):
            near[:-k] |= one[k:]
        keep &= near & (excursion >= 5) & (excursion <= 2000)
    return [lo + 4 * int(i) for i in np.nonzero(keep)[0]]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="src", required=True)
    ap.add_argument("--fps", type=int, default=60)
    ap.add_argument("--walk-button", default="LLeft,LDown")
    ap.add_argument("--walk", type=int, default=8)
    ap.add_argument("--vsyncs", type=int, default=120)
    ap.add_argument("--top", type=int, default=30)
    args = ap.parse_args()

    addrs = candidates(args.src)
    blocks = kh2lab.spans(addrs, gap=64)
    idx = {a: i for i, a in enumerate(addrs)}
    print(f"{len(addrs)} candidates in {len(blocks)} spans")

    roo = kh2lab.connect()
    kh2lab.start(roo, args.fps)
    print(f"arm {args.fps}fps  delta {struct.unpack('<f', roo.read_bytes(kh2lab.DELTA, 4))[0]}")
    roo.frame_advance(6)
    roo.input_set(*args.walk_button.split(","))
    roo.frame_advance(args.walk)
    roo.input_release()
    roo.input_set("Cross")
    roo.frame_advance(2)
    roo.input_release()

    series = np.zeros((args.vsyncs, len(addrs)), dtype=np.float64)
    for t in range(args.vsyncs):
        for lo, hi in blocks:
            vals = struct.unpack(f"<{(hi - lo) // 4}f", roo.read_bytes(lo, hi - lo))
            for k, v in enumerate(vals):
                i = idx.get(lo + 4 * k)
                if i is not None:
                    series[t, i] = v
        roo.frame_advance(1)

    out = kh2lab.SCRATCH / f"track-{args.fps}.npz"
    np.savez(out, addrs=np.array(addrs, dtype=np.uint32), series=series)
    print(f"saved {out}")

    rows = []
    for i, a in enumerate(addrs):
        y = series[:, i]
        d1 = np.diff(y)
        moving = np.abs(d1) > 1e-3
        n_moving = int(moving.sum())
        if n_moving < 20:
            continue
        # longest run of consecutive moving samples
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
        sign_consistency = abs(np.sign(d2).sum()) / max(len(d2), 1)
        span = float(seg.max() - seg.min())
        rows.append((r2 * sign_consistency, r2, sign_consistency, a, 2 * coef[0], span, s, len(seg)))

    rows.sort(key=lambda r: -r[0])
    print("score   r2      sign   addr      accel/vsync^2  span     start  len   w-check")
    for sc, r2, sg, a, acc, span, s, n in rows[: args.top]:
        w = []
        for off in (-8, -4, 4, 8, 12):
            try:
                w.append(struct.unpack("<f", roo.read_bytes(a + off, 4))[0])
            except Exception:
                w.append(float("nan"))
        wflag = "vec4" if any(abs(x - 1.0) < 1e-6 for x in w) else ""
        print(f"{sc:.4f}  {r2:.4f}  {sg:.2f}  {a:08X}  {acc:+13.5f}  {span:8.2f}  {s:5d}  {n:3d}   {wflag}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
