"""Acceptance test: does the Sandlot ball fly the same at 60fps as at 30fps?

    python tools/balltest.py                    # 30fps vs unpatched 60fps: must FAIL
    python tools/balltest.py --fix              # 30fps vs 60fps + [60 FPS - ball physics]: must PASS
    python tools/balltest.py --fix --offset 1   # the same with the hit on the other game-tick phase
    python tools/balltest.py --fix --mash 6     # mash Cross for 6 s instead of one hit
    python tools/balltest.py --pnach FILE --group NAME

Same save state, same vsync input schedule, so every arm covers the same real
time, and the 30fps arm is the oracle. A fix is a pnach group whose word writes
are applied live after the state loads - for code and single-reader data words
that is what PCSX2 does every frame. Needs PCSXROO running KH2FM with the
Sandlot state in slot 1 and [60 FPS] NOT enabled in its own ini (see method.md).

Results 2026-09-15 (docs/findings.md):
  single hit, offsets 0 and 1       unpatched FAIL, FIX-B PASS, FIX-D PASS
  mash 6 s                          unpatched FAIL, FIX-B FAIL, FIX-D FAIL
The mash failure is Sora's hit timing, not the ball: see findings, "Mashing".

Exit 0 when 60fps(+fix) matches the oracle within tolerance, 1 otherwise.
"""

from __future__ import annotations

import argparse
import struct
import sys

import numpy as np

import _bootstrap  # noqa: F401

from game import config, sandlot
from game.pnachtext import group_words

VSYNCS = 180
BALL_Y = sandlot.BALL_COLLISION + 4

TOL_PEAK = 0.03            # fraction of the oracle's peak height
TOL_AIR = 3                # vsyncs
TOL_CONTACT = 4            # vsyncs pinned against the arch
TOL_FALL = 0.10            # fraction of the oracle's fall acceleration

AIRBORNE = 5.0             # height above rest that counts as in the air
TOL_MASH_AIR = 0.10        # absolute fraction of time airborne
TOL_MASH_LANDINGS = 2
TOL_MASH_HEIGHT = 0.15     # fraction of the oracle's mean airborne height
TOL_MASH_DRIFT = 0.30      # fraction of the oracle's horizontal travel


def sample(roo) -> tuple[float, float, float]:
    return struct.unpack("<3f", roo.read_bytes(sandlot.BALL_COLLISION, 12))


def fly(roo, fps: int, fix, offset: int) -> np.ndarray:
    sandlot.prepare(roo, fps, fix, offset)
    sandlot.press_cross(roo)
    y = np.zeros(VSYNCS)
    for t in range(VSYNCS):
        y[t] = sample(roo)[1]
        roo.frame_advance(1)
    return y[0] - y


def mash(roo, fps: int, fix, offset: int, seconds: float) -> np.ndarray:
    sandlot.prepare(roo, fps, fix, offset)
    n = int(seconds * 60)
    xyz = np.zeros((n, 3))
    for t in range(n):
        sandlot.mash_step(roo, t)
        xyz[t] = sample(roo)
        roo.frame_advance(1)
    roo.input_release()
    return xyz


def metrics(h: np.ndarray) -> dict:
    lift = next((t for t in range(len(h)) if h[t] > 0.5), None)
    if lift is None:
        return {"hit": False}
    peak = float(h.max())
    tpeak = int(np.argmax(h))
    land = next((t for t in range(tpeak + 1, len(h)) if h[t] <= 0.5), None)
    contact = int(np.sum(h >= peak - 0.5))
    fall = None
    if land is not None:
        start = tpeak + contact  # leave the plateau before fitting
        if land - start >= 6:
            fall = -2 * np.polyfit(np.arange(start, land, dtype=float), h[start:land], 2)[0]
    return {"hit": True, "peak": peak, "rise": tpeak - lift, "contact": contact,
            "air": None if land is None else land - lift, "fall_accel": fall}


def mash_metrics(xyz: np.ndarray) -> dict:
    h = xyz[0, 1] - xyz[:, 1]
    air = h > AIRBORNE
    first = next((t for t in range(len(h)) if air[t]), None)
    if first is None:
        return {"hit": False}
    span = air[first:]
    xz = xyz[:, [0, 2]]
    return {"hit": True, "airborne": float(span.mean()), "landings": int(np.sum(span[:-1] & ~span[1:])),
            "mean_height": float(h[first:][span].mean()) if span.any() else 0.0,
            "max_height": float(h.max()),
            "travel": float(np.sum(np.linalg.norm(np.diff(xz, axis=0), axis=1))),
            "end_offset": float(np.linalg.norm(xz[-1] - xz[0]))}


def show(name: str, m: dict) -> None:
    if not m["hit"]:
        print(f"  {name:14s} ball never lifted")
        return
    fa = "-" if m["fall_accel"] is None else f"{m['fall_accel']:.4f}"
    print(f"  {name:14s} peak {m['peak']:6.1f}  rise {m['rise']:3d}  contact {m['contact']:3d}  "
          f"air {m['air']}  fall accel/vsync^2 {fa}")


def show_mash(name: str, m: dict) -> None:
    if not m["hit"]:
        print(f"  {name:14s} ball never lifted")
        return
    print(f"  {name:14s} airborne {m['airborne']:5.1%}  landings {m['landings']:2d}  "
          f"mean height {m['mean_height']:6.1f}  max {m['max_height']:6.1f}  "
          f"horizontal travel {m['travel']:7.1f}  end offset {m['end_offset']:6.1f}")


def compare(ref: dict, got: dict) -> list[str]:
    if not got["hit"]:
        return ["ball never lifted"]
    bad = []
    if abs(got["peak"] - ref["peak"]) > TOL_PEAK * ref["peak"]:
        bad.append(f"peak {got['peak']:.1f} vs {ref['peak']:.1f}")
    if got["air"] is None or ref["air"] is None or abs(got["air"] - ref["air"]) > TOL_AIR:
        bad.append(f"airtime {got['air']} vs {ref['air']}")
    if abs(got["contact"] - ref["contact"]) > TOL_CONTACT:
        bad.append(f"arch contact {got['contact']} vs {ref['contact']}")
    if ref["fall_accel"] and got["fall_accel"] and abs(got["fall_accel"] / ref["fall_accel"] - 1) > TOL_FALL:
        bad.append(f"fall accel {got['fall_accel']:.4f} vs {ref['fall_accel']:.4f}")
    return bad


def compare_mash(ref: dict, got: dict) -> list[str]:
    if not got["hit"]:
        return ["ball never lifted"]
    bad = []
    if abs(got["airborne"] - ref["airborne"]) > TOL_MASH_AIR:
        bad.append(f"airborne {got['airborne']:.1%} vs {ref['airborne']:.1%}")
    if abs(got["landings"] - ref["landings"]) > TOL_MASH_LANDINGS:
        bad.append(f"landings {got['landings']} vs {ref['landings']}")
    if abs(got["mean_height"] - ref["mean_height"]) > TOL_MASH_HEIGHT * ref["mean_height"]:
        bad.append(f"mean height {got['mean_height']:.1f} vs {ref['mean_height']:.1f}")
    if ref["travel"] > 1 and abs(got["travel"] - ref["travel"]) > TOL_MASH_DRIFT * ref["travel"]:
        bad.append(f"horizontal travel {got['travel']:.1f} vs {ref['travel']:.1f}")
    return bad


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--fix", action="store_true", help="use [60 FPS - ball physics] from patch/")
    ap.add_argument("--pnach")
    ap.add_argument("--group")
    ap.add_argument("--offset", type=int, default=0, help="extra idle vsyncs before the walk")
    ap.add_argument("--mash", type=float, default=0.0, help="seconds of mashing instead of one hit")
    ap.add_argument("--port", type=int, default=28110)
    args = ap.parse_args()

    if args.fix:
        args.pnach, args.group = str(config.PATCHES / "kh2fm-60fps.pnach"), "60 FPS - ball physics"
    fix = group_words(args.pnach, args.group) if args.pnach and args.group else None

    roo = sandlot.connect(args.port)
    if args.mash:
        run = lambda fps, f: mash_metrics(mash(roo, fps, f, args.offset, args.mash))  # noqa: E731
        shower, comparer, label = show_mash, compare_mash, f"mash {args.mash:g}s"
    else:
        run = lambda fps, f: metrics(fly(roo, fps, f, args.offset))  # noqa: E731
        shower, comparer, label = show, compare, "single hit"
    print(f"scenario: {label}, offset {args.offset}")

    ref = run(30, None)
    shower("30fps oracle", ref)
    if not ref["hit"]:
        print("FAIL: the oracle run did not hit the ball; the test itself is broken (rerun once - see method.md)")
        return 1
    plain = run(60, None)
    shower("60fps", plain)
    if fix is None:
        bad, verdict = comparer(ref, plain), "60fps unpatched"
    else:
        fixed = run(60, fix)
        shower("60fps + fix", fixed)
        bad, verdict = comparer(ref, fixed), f"60fps + [{args.group}]"
    if bad:
        print(f"FAIL: {verdict} differs from 30fps: " + "; ".join(bad))
        return 1
    print(f"PASS: {verdict} matches 30fps within tolerance")
    return 0


if __name__ == "__main__":
    sys.exit(main())
