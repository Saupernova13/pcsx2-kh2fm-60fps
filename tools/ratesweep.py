"""Sweep RAM densely in each frame-rate arm and flag every word that moves or oscillates twice as fast at 60fps.

    python tools/ratesweep.py capture work/rs-sandlot-idle.npz                   # arms 30,60,60t2, 60 samples every 2 vsyncs
    python tools/ratesweep.py capture work/rs-walk.npz --hold LUp --samples 90
    python tools/ratesweep.py report work/rs-sandlot-idle.npz                    # 30 vs 60, and which lever
    python tools/ratesweep.py report work/rs-sandlot-idle.npz --save rs-idle     # also write the address lists

The companion to tools/ratediff.py. Three snapshots only catch steady ramps, and
an idle KH2 scene is mostly oscillators - bobbing props, idle animations,
effects - whose halves never agree, so ratediff's float pass found nothing. This
reads the region every --stride vsyncs (2 by default: the same real-time grid in
both arms, and exactly one read per tick at 30fps) and keeps, per word:

    total variation   the sum of |change| between samples - a ramp and an
                      oscillator both double it when they run twice as fast
    reversals         how often the direction changes - an animation playing at
                      double speed reverses twice as often, whatever its amplitude

A word is flagged when both arms judge it (plausible floats throughout, or an
integer that never jumps by more than 2^24) and its variation or its reversals
come out 1.75-2.3x at 60fps. With the 60t2 arm present, each flagged word is
classified: back to 1x with the stock accumulator threshold (particle/effect
step, partMng.c) or still 2x (other per-tick code).

Lessons carried over from BT3's oscscan: sample both arms on the same real-time
grid with the same number of samples; filter to plausible floats, or packet data
reads as noise; start from a state that needs no input, or hold the same input
in every arm.
"""

from __future__ import annotations

import argparse
import collections
import sys
import time

import numpy as np

import _bootstrap  # noqa: F401

import ratediff
from game import config, sandlot, timing

CHUNK = 8 << 20
BIG = 1 << 24


def read_region(roo, lo: int, hi: int) -> np.ndarray:
    return np.concatenate([np.frombuffer(roo.read_bytes(a, min(CHUNK, hi - a)), dtype="<u4")
                           for a in range(lo, hi, CHUNK)])


def plausible(f: np.ndarray) -> np.ndarray:
    m = np.abs(f)
    return np.isfinite(f) & ((m == 0) | ((m > 1e-12) & (m < 1e6)))


def measure(roo, arm: str, args) -> dict:
    ratediff.start_arm(roo, arm, args.slot)
    hold = [b for b in args.hold.split(",") if b]
    if hold:
        roo.input_set(*hold)
    if args.lead:
        roo.frame_advance(args.lead)
    raw = read_region(roo, args.lo, args.hi)
    with np.errstate(invalid="ignore", over="ignore"):
        pf = raw.view("<f4").astype(np.float64)
    ok_f = plausible(pf)
    pf = np.nan_to_num(pf, nan=0.0, posinf=0.0, neginf=0.0)
    pi = raw.view("<i4").astype(np.int64)
    ok_i = np.ones(raw.size, dtype=bool)
    tv_f = np.zeros(raw.size)
    tv_i = np.zeros(raw.size)
    sign_f = np.zeros(raw.size, dtype=np.int8)
    rev_f = np.zeros(raw.size, dtype=np.int16)
    sign_i = np.zeros(raw.size, dtype=np.int8)
    rev_i = np.zeros(raw.size, dtype=np.int16)
    t0 = roo.read(timing.TICKS)
    start = time.time()
    for k in range(args.samples):
        roo.frame_advance(args.stride)
        raw = read_region(roo, args.lo, args.hi)
        with np.errstate(invalid="ignore", over="ignore"):
            cf = raw.view("<f4").astype(np.float64)
        ok_f &= plausible(cf)
        cf = np.nan_to_num(cf, nan=0.0, posinf=0.0, neginf=0.0)
        ci = raw.view("<i4").astype(np.int64)
        df = cf - pf
        di = ci - pi
        ok_i &= np.abs(di) < BIG
        tv_f += np.abs(df)
        tv_i += np.abs(di)
        for d, sign, rev in ((df, sign_f, rev_f), (di, sign_i, rev_i)):
            s = np.sign(d).astype(np.int8)
            live = s != 0
            rev += (live & (sign != 0) & (s != sign)).astype(np.int16)
            np.copyto(sign, s, where=live)
        pf, pi = cf, ci
        print(f"    arm {arm} {k + 1}/{args.samples}  {time.time() - start:.0f}s", end="\r", flush=True)
    print()
    ticks = roo.read(timing.TICKS) - t0
    if hold:
        roo.input_release()
    print(f"  arm {arm}: {args.samples * args.stride} vsyncs = {ticks} ticks")
    return {"tv_f": tv_f.astype(np.float32), "tv_i": tv_i.astype(np.float32), "rev_f": rev_f, "rev_i": rev_i,
            "ok_f": ok_f, "ok_i": ok_i, "ticks": np.array([ticks])}


def capture(args) -> int:
    roo = sandlot.connect(args.port)
    arms = args.arms.split(",")
    out = {"lo": np.array([args.lo]), "arms": np.array(arms),
           "grid": np.array([args.samples, args.stride]), "hold": np.array([args.hold])}
    for arm in arms:
        for k, v in measure(roo, arm, args).items():
            out[f"{arm}_{k}"] = v
    config.WORK.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(args.out, **out)
    print(f"saved {args.out}")
    return 0


def judge(z, ref: str, cmp: str, kind: str, min_rev: int, min_tv: float):
    ok = z[f"{ref}_ok_{kind}"] & z[f"{cmp}_ok_{kind}"]
    tr, tc = z[f"{ref}_tv_{kind}"].astype(np.float64), z[f"{cmp}_tv_{kind}"].astype(np.float64)
    rr, rc = z[f"{ref}_rev_{kind}"].astype(np.float64), z[f"{cmp}_rev_{kind}"].astype(np.float64)
    moving = ok & (tr > min_tv)
    with np.errstate(divide="ignore", invalid="ignore"):
        tv_ratio = np.where(tr > 0, tc / tr, np.nan)
        rev_ratio = np.where(rr > 0, rc / rr, np.nan)
    tv2 = moving & (tv_ratio > 1.75) & (tv_ratio < 2.3)
    tv1 = moving & (tv_ratio > 0.87) & (tv_ratio < 1.15)
    rev_ok = moving & (rr >= min_rev) & (rr <= 0.6 * float(z["grid"][0]))
    rev2 = rev_ok & (rev_ratio > 1.7) & (rev_ratio < 2.4)
    rev1 = rev_ok & (rev_ratio > 0.8) & (rev_ratio < 1.25)
    return {"moving": moving, "two": tv2 | rev2, "one": (tv1 & ~rev2) | (rev1 & ~tv2),
            "tv_ratio": tv_ratio, "rev_ratio": rev_ratio, "tr": tr, "tc": tc, "rr": rr, "rc": rc}


def runs(idx: np.ndarray) -> list[np.ndarray]:
    if idx.size == 0:
        return []
    out = np.split(idx, np.flatnonzero(np.diff(idx) > 2) + 1)
    out.sort(key=lambda r: -r.size)
    return out


def show(lo: int, idx: np.ndarray, j: dict, top: int) -> None:
    rs = runs(idx)
    print(f"    {idx.size} words in {len(rs)} clusters (gap <= 8 bytes), largest first:")
    for run in rs[:top]:
        i = run[0]
        print(f"      {lo + 4 * i:08X} x{run.size:<4d} tv {j['tr'][i]:12.4f} -> {j['tc'][i]:12.4f} "
              f"({j['tv_ratio'][i]:.2f})  rev {int(j['rr'][i]):3d} -> {int(j['rc'][i]):3d}")
    pages = collections.Counter((lo + 4 * int(i)) >> 16 for i in idx)
    print("    by 64K page: " + "  ".join(f"{p << 16:08X}:{n}" for p, n in pages.most_common(12)))


def report(args) -> int:
    z = np.load(args.npz)
    lo = int(z["lo"][0])
    arms = [str(a) for a in z["arms"]]
    samples, stride = (int(x) for x in z["grid"])
    print(f"{samples} samples every {stride} vsyncs; hold {str(z['hold'][0])!r}")
    for arm in arms:
        print(f"  arm {arm}: {int(z[arm + '_ticks'][0])} ticks")
    lines = []
    for kind in ("f", "i"):
        name = "float" if kind == "f" else "int32"
        j60 = judge(z, "30", "60", kind, args.min_rev, args.min_tv if kind == "f" else 1.0)
        print(f"\n===== {name}: {int(j60['moving'].sum())} words move in both arms; "
              f"{int(j60['two'].sum())} at 2x, {int(j60['one'].sum())} at 1x under [60 FPS]")
        if "60t2" in arms:
            jt2 = judge(z, "30", "60t2", kind, args.min_rev, args.min_tv if kind == "f" else 1.0)
            by_t = j60["two"] & jt2["one"]
            other = j60["two"] & jt2["two"]
            unclear = j60["two"] & ~jt2["one"] & ~jt2["two"]
            for label, mask in (("threshold-driven (1x with the stock accumulator threshold)", by_t),
                                ("still 2x with the stock threshold (other per-tick code)", other),
                                ("unclassified (60t2 arm neither 1x nor 2x)", unclear)):
                print(f"  -- {label}")
                show(lo, np.flatnonzero(mask), j60, args.top)
                tag = label.split(" ")[0]
                lines += [f"{name} {tag} {lo + 4 * int(i):08X} {j60['tv_ratio'][i]:.3f} {j60['rev_ratio'][i]:.3f}"
                          for i in np.flatnonzero(mask)]
        else:
            show(lo, np.flatnonzero(j60["two"]), j60, args.top)
            lines += [f"{name} 2x {lo + 4 * int(i):08X} {j60['tv_ratio'][i]:.3f} {j60['rev_ratio'][i]:.3f}"
                      for i in np.flatnonzero(j60["two"])]
    if args.save:
        path = config.WORK / f"{args.save}.txt"
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"\nwrote {path} ({len(lines)} lines)")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("capture")
    c.add_argument("out")
    c.add_argument("--slot", type=int, default=sandlot.SLOT)
    c.add_argument("--arms", default="30,60,60t2")
    c.add_argument("--samples", type=int, default=60)
    c.add_argument("--stride", type=int, default=2)
    c.add_argument("--lead", type=int, default=10)
    c.add_argument("--hold", default="")
    c.add_argument("--lo", type=lambda s: int(s, 16), default=ratediff.LO)
    c.add_argument("--hi", type=lambda s: int(s, 16), default=ratediff.HI)
    c.add_argument("--port", type=int, default=28110)
    r = sub.add_parser("report")
    r.add_argument("npz")
    r.add_argument("--min-rev", type=int, default=3)
    r.add_argument("--min-tv", type=float, default=1e-3)
    r.add_argument("--top", type=int, default=25)
    r.add_argument("--save", default="")
    args = ap.parse_args()
    return {"capture": capture, "report": report}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
