"""Ask every word in RAM whether it moves at a different real-time rate at 60fps than at 30fps.

    python tools/ratediff.py capture work/rd-sandlot.npz                      # arms 30, 60, 60t2 from slot 1
    python tools/ratediff.py capture work/rd-walk.npz --hold LUp --vsyncs 180
    python tools/ratediff.py report work/rd-sandlot.npz                       # 30 vs every other arm
    python tools/ratediff.py report work/rd-sandlot.npz --ints --cmp 60
    python tools/ratediff.py classify work/rd-sandlot.npz                     # 2x under [60 FPS]: which lever

Same save state, same input, the same number of vsyncs - the same real time - in
each arm. A quantity that is right at 60fps covers the same distance in that
window as it does at 30fps; one that runs per tick without compensation covers
twice as much. Ported from the BT3 repo's ratediff.py, with KH2FM's arms:

    30     the stock limiter: vsync wait 1, delta cap 6.0, accumulator threshold 2.0
    60     [60 FPS] as PeterDelta ships it: wait 0, cap 1.0, threshold 1.0
    60t2   [60 FPS] with the accumulator threshold left at its stock 2.0
    60c6   [60 FPS] with the delta cap left at its stock 6.0

Three snapshots per arm, so a word that jumped once (a pool refilled) is told
apart from one that advances steadily: both halves of the window must agree.
Floats and int32 are both judged - integer counters vanish from a float scan.

`classify` answers the question the 60t2 arm exists for. The per-object fixed-step
accumulator in 001E6280 adds delta each frame and steps each time the sum reaches
the threshold - 30 steps a second at either rate with the stock 2.0. [60 FPS] sets
1.0, which would double whatever that step drives. A word that is 2x in `60` and
1x in `60t2` is driven by the threshold; 2x in both is some other per-tick code.
"""

from __future__ import annotations

import argparse
import collections
import sys

import numpy as np

import _bootstrap  # noqa: F401

from game import config, sandlot, timing

LO, HI = 0x00340000, 0x02000000
CHUNK = 8 << 20

ARMS = {
    "30": dict(timing.STOCK),
    "60": dict(timing.PATCHED),
    "60t2": {**timing.PATCHED, timing.ACCUM_THRESHOLD: timing.STOCK[timing.ACCUM_THRESHOLD]},
    "60c6": {**timing.PATCHED, timing.DELTA_CAP: timing.STOCK[timing.DELTA_CAP]},
}
TICKS_PER_20 = {"30": 10, "60": 20, "60t2": 20, "60c6": 20}


def snapshot(roo) -> np.ndarray:
    return np.concatenate([np.frombuffer(roo.read_bytes(a, min(CHUNK, HI - a)), dtype="<u4")
                           for a in range(LO, HI, CHUNK)])


def start_arm(roo, name: str, slot: int) -> None:
    if not roo.paused():
        roo.pause()
    roo.loadstate(slot)
    if not roo.paused():
        roo.pause()
    for addr, value in ARMS[name].items():
        if not roo.write(addr, value):
            raise RuntimeError(f"arm {name}: write did not stick at {addr:08X}")
    roo.frame_advance(2)
    t0 = roo.read(timing.TICKS)
    roo.frame_advance(20)
    ticks = roo.read(timing.TICKS) - t0
    if ticks != TICKS_PER_20[name]:
        raise RuntimeError(f"arm {name} not in effect: {ticks} ticks in 20 vsyncs, want {TICKS_PER_20[name]}")


def capture(args) -> int:
    roo = sandlot.connect(args.port)
    hold = [b for b in args.hold.split(",") if b]
    out = {"lo": np.array([LO]), "arms": np.array(args.arms.split(",")), "vsyncs": np.array([args.vsyncs])}
    for name in args.arms.split(","):
        start_arm(roo, name, args.slot)
        if hold:
            roo.input_set(*hold)
        if args.lead:
            roo.frame_advance(args.lead)
        t0 = roo.read(timing.TICKS)
        out[f"{name}_a"] = snapshot(roo)
        roo.frame_advance(args.vsyncs // 2)
        out[f"{name}_m"] = snapshot(roo)
        roo.frame_advance(args.vsyncs - args.vsyncs // 2)
        out[f"{name}_b"] = snapshot(roo)
        out[f"{name}_ticks"] = np.array([roo.read(timing.TICKS) - t0])
        if hold:
            roo.input_release()
        print(f"  arm {name}: {args.vsyncs} vsyncs = {int(out[name + '_ticks'][0])} ticks")
    config.WORK.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(args.out, **out)
    print(f"saved {args.out}")
    return 0


def rates(z, name: str, ints: bool):
    """Per-word total change over the window, with the masks that make it trustworthy."""
    raw = [z[f"{name}_{k}"] for k in "amb"]
    if ints:
        a, m, b = (r.view(np.int32).astype(np.int64) for r in raw)
        ok = np.abs(b - a) < (1 << 24)
        steady = (m - a) == (b - m)
        moved = b != a
    else:
        with np.errstate(invalid="ignore", over="ignore"):
            a, m, b = (r.view("<f4").astype(np.float64) for r in raw)
        plausible = lambda x: np.isfinite(x) & (np.abs(x) < 1e6) & ((x == 0) | (np.abs(x) > 1e-12))  # noqa: E731
        ok = plausible(a) & plausible(m) & plausible(b)
        h1, h2 = m - a, b - m
        steady = np.abs(h1 - h2) <= 0.15 * np.maximum(np.abs(h1), 1e-9)
        moved = np.abs(b - a) > 1e-4
    return b - a, ok & steady & moved, a


def compare(z, ref: str, cmp: str, ints: bool):
    dr, okr, start = rates(z, ref, ints)
    dc, okc, _ = rates(z, cmp, ints)
    base = okr & okc
    with np.errstate(invalid="ignore", divide="ignore"):
        ratio = dc / np.where(dr == 0, np.nan, dr)
    if ints:
        two = base & (dc == 2 * dr)
        one = base & (dc == dr)
    else:
        two = base & (ratio > 1.75) & (ratio < 2.3)
        one = base & (ratio > 0.87) & (ratio < 1.15)
    return base, two, one, dr, dc, start


def runs_of(idx: np.ndarray) -> list[np.ndarray]:
    if idx.size == 0:
        return []
    runs = np.split(idx, np.flatnonzero(np.diff(idx) != 1) + 1)
    runs.sort(key=lambda r: -r.size)
    return runs


def print_runs(lo: int, idx: np.ndarray, dr, dc, start, ints: bool, top: int) -> None:
    runs = runs_of(idx)
    print(f"  {len(runs)} contiguous runs, largest first:")
    fmt = "{:>12d}" if ints else "{:>12.4f}"
    for run in runs[:top]:
        i = run[0]
        print(f"    {lo + 4 * i:08X} x{run.size:<3d} start=" + fmt.format(start[i])
              + "  d30=" + fmt.format(dr[i]) + "  dcmp=" + fmt.format(dc[i]))
    pages = collections.Counter((lo + 4 * int(i)) >> 16 for i in idx)
    print("  by 64K page: " + "  ".join(f"{p << 16:08X}:{n}" for p, n in pages.most_common(10)))


def report(args) -> int:
    z = np.load(args.npz)
    lo = int(z["lo"][0])
    arms = [str(a) for a in z["arms"]]
    for name in arms:
        print(f"arm {name}: {int(z[name + '_ticks'][0])} ticks in {int(z['vsyncs'][0])} vsyncs")
    for cmp in ([args.cmp] if args.cmp else [a for a in arms if a != args.ref]):
        base, two, one, dr, dc, start = compare(z, args.ref, cmp, args.ints)
        kind = "int32" if args.ints else "float"
        print(f"\n===== {args.ref} vs {cmp} ({kind}): {int(base.sum())} steady movers in both, "
              f"{int(two.sum())} at 2x, {int(one.sum())} at 1x")
        print_runs(lo, np.flatnonzero(two), dr, dc, start, args.ints, args.top)
    return 0


def classify(args) -> int:
    z = np.load(args.npz)
    lo = int(z["lo"][0])
    for ints in (False, True):
        kind = "int32" if ints else "float"
        _, two60, _, dr, dc60, start = compare(z, "30", "60", ints)
        _, two_t2, one_t2, _, dct2, _ = compare(z, "30", "60t2", ints)
        by_threshold = two60 & one_t2
        other = two60 & two_t2
        print(f"\n===== {kind}: {int(two60.sum())} words at 2x under [60 FPS]")
        print(f"  {int(by_threshold.sum())} back to 1x with the stock accumulator threshold (threshold-driven)")
        print_runs(lo, np.flatnonzero(by_threshold), dr, dc60, start, ints, args.top)
        print(f"  {int(other.sum())} still 2x with the stock threshold (other per-tick code)")
        print_runs(lo, np.flatnonzero(other), dr, dc60, start, ints, args.top)
        if args.save:
            path = config.WORK / f"{args.save}-{kind}.txt"
            with open(path, "w", encoding="utf-8") as fh:
                for label, mask in (("threshold", by_threshold), ("other", other)):
                    for i in np.flatnonzero(mask):
                        fh.write(f"{label} {lo + 4 * int(i):08X} {dr[i]} {dc60[i]}\n")
            print(f"  wrote {path}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("capture")
    c.add_argument("out")
    c.add_argument("--slot", type=int, default=sandlot.SLOT)
    c.add_argument("--arms", default="30,60,60t2")
    c.add_argument("--vsyncs", type=int, default=120)
    c.add_argument("--lead", type=int, default=0, help="vsyncs after the tick proof before the first snapshot")
    c.add_argument("--hold", default="", help="buttons held through the window, e.g. LUp or Cross")
    c.add_argument("--port", type=int, default=28110)
    r = sub.add_parser("report")
    r.add_argument("npz")
    r.add_argument("--ref", default="30")
    r.add_argument("--cmp", default="")
    r.add_argument("--ints", action="store_true")
    r.add_argument("--top", type=int, default=30)
    k = sub.add_parser("classify")
    k.add_argument("npz")
    k.add_argument("--top", type=int, default=25)
    k.add_argument("--save", default="", help="write the classified addresses to work/<save>-<kind>.txt")
    args = ap.parse_args()
    return {"capture": capture, "report": report, "classify": classify}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
