"""Capture full EE RAM snapshots around one hit of the Sandlot ball.

Saves every snapshot so arcs can be searched offline with any filter, instead
of re-running the game for each idea. Times are vsyncs after the Cross press
starts; the same vsync schedule is used in both arms so they cover the same
real time.

    python kh2_capture.py --fps 60 [--hold 2] [--times 4,8,12,16,24,32,44,60]
"""
import argparse
import struct

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
    ap.add_argument("--hold", type=int, default=2)
    ap.add_argument("--times", default="4,8,12,16,24,32,44,60")
    ap.add_argument("--shot-at", type=int, default=12)
    ap.add_argument("--walk-button", default="LLeft", help="stick half-axis to hold before the hit")
    ap.add_argument("--walk", type=int, default=0, help="vsyncs to walk before the hit")
    args = ap.parse_args()
    times = [int(t) for t in args.times.split(",")]

    roo = kh2lab.connect()
    kh2lab.start(roo, args.fps)
    print(f"arm {args.fps}fps  delta {struct.unpack('<f', roo.read_bytes(kh2lab.DELTA, 4))[0]}")

    snaps, labels = [], []
    for k in range(3):
        if k:
            roo.frame_advance(3)
        snaps.append(dump(roo))
        labels.append(-3 * (2 - k) - 1)

    if args.walk:
        roo.input_set(*args.walk_button.split(","))
        roo.frame_advance(args.walk)
        roo.input_release()

    now = 0
    roo.input_set("Cross")
    roo.frame_advance(args.hold)
    roo.input_release()
    now += args.hold
    for t in times:
        if t > now:
            if now < args.shot_at <= t:
                roo.frame_advance(args.shot_at - now)
                now = args.shot_at
                kh2lab.shot(roo, f"cap-{args.fps}-t{args.shot_at}.png")
                now += 1
            if t > now:
                roo.frame_advance(t - now)
                now = t
        snaps.append(dump(roo))
        labels.append(now)
        print(f"  snapshot at vsync {now}")

    out = kh2lab.SCRATCH / f"cap-{args.fps}.npz"
    np.savez(out, lo=LO, labels=np.array(labels), snaps=np.stack(snaps))
    print(f"saved {out}  ({len(snaps)} snapshots)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
