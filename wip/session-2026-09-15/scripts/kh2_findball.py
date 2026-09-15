"""Find the Sandlot ball's height in RAM by its gravity signature.

Full EE RAM snapshots diffed in numpy (mem.search caps a session at 100000
values, far below the ~8M floats in RAM). Snapshots while idle mark noise;
snapshots after hitting the ball with Cross keep what moves in flight. The
survivors are tracked every vsync and ranked by how parabolic they are:
rising then falling with a steady second difference.

    python kh2_findball.py [--fps 60] [--track 150]
"""
import argparse
import struct
import time

import numpy as np

import kh2lab

LO, HI = 0x00100000, 0x02000000
CHUNK = 4 * 1024 * 1024


def dump(roo) -> np.ndarray:
    parts = [roo.read_bytes(a, min(CHUNK, HI - a)) for a in range(LO, HI, CHUNK)]
    return np.frombuffer(b"".join(parts), dtype=np.uint32).copy()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fps", type=int, default=60)
    ap.add_argument("--track", type=int, default=150)
    args = ap.parse_args()

    roo = kh2lab.connect()
    kh2lab.start(roo, args.fps)
    print(f"arm {args.fps}fps  delta {struct.unpack('<f', roo.read_bytes(kh2lab.DELTA, 4))[0]}")

    t0 = time.time()
    idle = [dump(roo)]
    print(f"  dump took {time.time() - t0:.1f}s")
    for _ in range(2):
        roo.frame_advance(3)
        idle.append(dump(roo))
    noise = (idle[0] != idle[1]) | (idle[1] != idle[2])
    print(f"  idle-changing words: {int(noise.sum())}")

    roo.input_set("Cross")
    roo.frame_advance(2)
    roo.input_release()
    roo.frame_advance(10)
    fly = [dump(roo)]
    for _ in range(2):
        roo.frame_advance(3)
        fly.append(dump(roo))
    kh2lab.shot(roo, f"ball-flight-{args.fps}.png")

    moving = (fly[0] != fly[1]) & (fly[1] != fly[2]) & ~noise
    as_f = fly[2].view(np.float32)
    plausible = np.isfinite(as_f) & (np.abs(as_f) < 1e5)
    cand = np.nonzero(moving & plausible)[0]
    addrs = [LO + 4 * int(i) for i in cand]
    print(f"  candidates moving in flight only: {len(addrs)}")
    if not addrs:
        return 1
    if len(addrs) > 20000:
        print("  too many to track per vsync; keeping the first 20000")
        addrs = addrs[:20000]

    blocks = kh2lab.spans(addrs)
    idx = {a: i for i, a in enumerate(addrs)}
    print(f"tracking {len(addrs)} addresses in {len(blocks)} spans for {args.track} vsyncs")
    series = np.zeros((args.track, len(addrs)), dtype=np.float32)
    for t in range(args.track):
        for lo, hi in blocks:
            vals = struct.unpack(f"<{(hi - lo) // 4}f", roo.read_bytes(lo, hi - lo))
            for k, v in enumerate(vals):
                i = idx.get(lo + 4 * k)
                if i is not None:
                    series[t, i] = v
        roo.frame_advance(1)

    out = kh2lab.SCRATCH / f"ball-candidates-{args.fps}.npz"
    np.savez(out, addrs=np.array(addrs, dtype=np.uint32), series=series)
    print(f"saved {out}")

    scored = []
    for i, a in enumerate(addrs):
        y = series[:, i].astype(np.float64)
        d1 = np.diff(y)
        mov = np.abs(d1) > 1e-4
        if mov.sum() < 8:
            continue
        d2 = np.diff(d1)[mov[1:] & mov[:-1]]
        if len(d2) < 6:
            continue
        med = np.median(d2)
        if med >= 0:
            continue
        spread = np.median(np.abs(d2 - med)) / (abs(med) + 1e-9)
        rise = int((d1 > 1e-4).sum())
        fall = int((d1 < -1e-4).sum())
        if rise == 0 or fall == 0:
            continue
        scored.append((spread, a, med, y.min(), y.max(), rise, fall))
    scored.sort()
    print("best gravity-shaped candidates (spread, addr, d2, min, max, rise, fall):")
    for s in scored[:30]:
        print(f"  {s[0]:.3f}  {s[1]:08X}  d2={s[2]:+.5f}  y {s[3]:.3f}..{s[4]:.3f}  up {s[5]} down {s[6]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
