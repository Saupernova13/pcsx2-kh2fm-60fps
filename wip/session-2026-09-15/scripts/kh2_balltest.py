"""Acceptance test: does the Sandlot ball fly the same at 60fps as at 30fps?

Same save state, same vsync input schedule (walk to the ball, then Cross), so
every arm covers the same real time. The 30fps arm is the oracle. A fix is a
pnach group: its patch=1 word lines are written live after the state loads,
which for code and single-reader data words is what PCSX2 does every frame.

Two scenarios:
  single hit   one Cross, one flight: peak, rise, arch contact, airtime, fall
  --mash S     Cross 2 vsyncs on / 6 off for S seconds, the way a player keeps
               the ball up: time airborne, landings, heights, horizontal drift

--offset N adds N idle vsyncs before the walk. At 60fps an odd offset moves
the hit to the other game-tick parity, which a tick-gated fix is sensitive to.

    python kh2_balltest.py                               # 30 vs unpatched 60: must FAIL
    python kh2_balltest.py --pnach FILE --group NAME     # 30 vs 60 + fix: must PASS
    python kh2_balltest.py --pnach FILE --group NAME --offset 1
    python kh2_balltest.py --pnach FILE --group NAME --mash 6

Exit 0 when 60fps(+fix) matches the oracle within tolerance, 1 otherwise.
"""
import argparse
import struct
import sys

import numpy as np

import kh2lab

BALL_X, BALL_Y, BALL_Z = 0x01ADEAC0, 0x01ADEAC4, 0x01ADEAC8   # collision shape, Y negative-up
VSYNCS = 180

TOL_PEAK = 0.03            # fraction of the oracle's peak height
TOL_AIR = 3                # vsyncs
TOL_CONTACT = 4            # vsyncs pinned against the arch
TOL_FALL = 0.10            # fraction of the oracle's fall acceleration

AIRBORNE = 5.0             # height above rest that counts as in the air
TOL_MASH_AIR = 0.10        # absolute fraction of time airborne
TOL_MASH_LANDINGS = 2
TOL_MASH_HEIGHT = 0.15     # fraction of the oracle's mean airborne height
TOL_MASH_DRIFT = 0.30      # fraction of the oracle's horizontal travel


def load_group(path: str, group: str) -> list[tuple[int, int]]:
    words, inside = [], False
    for line in open(path, encoding="utf-8", errors="replace"):
        s = line.split("//", 1)[0].strip()
        if s.startswith("["):
            inside = s == f"[{group}]"
            continue
        if not inside or not s.startswith("patch="):
            continue
        parts = [p.strip() for p in s.split(",")]
        if len(parts) < 5 or parts[1].upper() != "EE" or parts[3].lower() != "word":
            raise SystemExit(f"unsupported line in [{group}]: {line.strip()}")
        words.append((int(parts[2], 16) & 0x01FFFFFF, int(parts[4], 16)))
    if not words:
        raise SystemExit(f"group [{group}] not found or empty in {path}")
    return words


def prepare(roo, fps: int, fix, offset: int) -> None:
    kh2lab.start(roo, fps)
    for addr, value in fix or ():
        if not roo.write(addr, value):
            raise SystemExit(f"fix write did not verify at {addr:08X}")
    roo.frame_advance(6 + offset)
    roo.input_set("LLeft", "LDown")
    roo.frame_advance(8)
    roo.input_release()


def sample(roo) -> tuple[float, float, float]:
    return struct.unpack("<3f", roo.read_bytes(BALL_X, 12))


def fly(roo, fps: int, fix, offset: int) -> np.ndarray:
    prepare(roo, fps, fix, offset)
    roo.input_set("Cross")
    roo.frame_advance(2)
    roo.input_release()
    y = np.zeros(VSYNCS)
    for t in range(VSYNCS):
        y[t] = sample(roo)[1]
        roo.frame_advance(1)
    return y[0] - y


def mash(roo, fps: int, fix, offset: int, seconds: float) -> np.ndarray:
    prepare(roo, fps, fix, offset)
    n = int(seconds * 60)
    xyz = np.zeros((n, 3))
    for t in range(n):
        phase = t % 8
        if phase == 0:
            roo.input_set("Cross")
        elif phase == 2:
            roo.input_release()
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
    rest = xyz[0, 1]
    h = rest - xyz[:, 1]
    air = h > AIRBORNE
    first = next((t for t in range(len(h)) if air[t]), None)
    if first is None:
        return {"hit": False}
    span = air[first:]
    landings = int(np.sum(span[:-1] & ~span[1:]))
    xz = xyz[:, [0, 2]]
    travel = float(np.sum(np.linalg.norm(np.diff(xz, axis=0), axis=1)))
    return {"hit": True, "airborne": float(span.mean()), "landings": landings,
            "mean_height": float(h[first:][span].mean()) if span.any() else 0.0,
            "max_height": float(h.max()), "travel": travel,
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
    if ref["fall_accel"] and got["fall_accel"]:
        if abs(got["fall_accel"] / ref["fall_accel"] - 1) > TOL_FALL:
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
    ap.add_argument("--pnach")
    ap.add_argument("--group")
    ap.add_argument("--offset", type=int, default=0, help="extra idle vsyncs before the walk")
    ap.add_argument("--mash", type=float, default=0.0, help="seconds of mashing instead of one hit")
    args = ap.parse_args()
    fix = load_group(args.pnach, args.group) if args.pnach and args.group else None

    roo = kh2lab.connect()
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
        print("FAIL: the oracle run did not hit the ball; the test itself is broken")
        return 1
    plain = run(60, None)
    shower("60fps", plain)
    if fix is None:
        bad = comparer(ref, plain)
        verdict = "60fps unpatched"
    else:
        fixed = run(60, fix)
        shower("60fps + fix", fixed)
        bad = comparer(ref, fixed)
        verdict = f"60fps + [{args.group}]"
    if bad:
        print(f"FAIL: {verdict} differs from 30fps: " + "; ".join(bad))
        return 1
    print(f"PASS: {verdict} matches 30fps within tolerance")
    return 0


if __name__ == "__main__":
    sys.exit(main())
