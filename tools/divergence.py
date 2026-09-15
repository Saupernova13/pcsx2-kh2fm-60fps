"""Where does 60fps stop matching 30fps in the mash? Offline, on saved traces.

    python tools/divergence.py objects [work/objtrace.npz]   # first real divergence per object
    python tools/divergence.py mash [work/mashtrace.npz]     # ball trajectory, side-swipe decay, pushes, impulses

objects: compares each object's position at 60fps against 30fps only at the
vsyncs where the 30fps position actually updated (30fps moves every other
vsync), and accepts the 60fps value one vsync either side, so sampling phase
cannot pass for a difference.

mash: the ball's height and position against 30fps up to 60fps's second hit;
horizontal speed after a side swipe, per vsync (the fix decays 0.8 every other
vsync, like 30fps; unpatched decays 0.8 every vsync); sideways motion not
explained by velocity; and every impulse in each arm.

2026-09-15: two objects then called ground props - Donald and Goofy, it turned
out - start sliding at vsync 36-37 at 60fps, fixed or not, against 43-45 at 30fps:
something pushes them sooner. The ball matched to within
a tick's phase until its arch slide, offset only ~5 units in z from its launch.
"""

from __future__ import annotations

import argparse
import sys

import numpy as np

import _bootstrap  # noqa: F401

from game import config


def objects(path: str) -> None:
    z = np.load(path)
    objs = [int(o) for o in z["objs"]]
    ref = z["30fps"]
    for key in ("60_unpatched", "60pFIX-D"):
        other = z[key]
        print(f"===== 30fps vs {key}")
        for k, o in enumerate(objs):
            r, q = ref[:, k, :], other[:, k, :]
            if np.all(r == r[0]) and np.all(q == q[0]):
                continue
            first = None
            for t in (t for t in range(1, len(r)) if np.any(r[t] != r[t - 1])):
                step = np.linalg.norm(r[t] - r[t - 1])
                if min(np.linalg.norm(q[t] - r[t]), np.linalg.norm(q[t - 1] - r[t])) > max(3.0, 1.1 * step):
                    first = t
                    break
            if first is None:
                print(f"  {o:08X}: no divergence beyond one tick of phase")
                continue
            print(f"  {o:08X}: first divergence at vsync {first}")
            for t in range(max(1, first - 6), min(len(r), first + 7)):
                print(f"     {t:3d}  30fps h {r[0, 1] - r[t, 1]:7.1f} xz ({r[t, 0]:7.1f},{r[t, 2]:8.1f})   "
                      f"{key} h {q[0, 1] - q[t, 1]:7.1f} xz ({q[t, 0]:7.1f},{q[t, 2]:8.1f})")


def mash(path: str) -> None:
    z = np.load(path)
    cols = [str(c) for c in z["cols"]]
    C = {n: i for i, n in enumerate(cols)}
    arms = {"30fps": z["o30"], "60 unpatched": z["p60"], "60+fix": z["f60"]}
    ref = arms["30fps"]

    def h(a: np.ndarray) -> np.ndarray:
        return a[0, C["by"]] - a[:, C["by"]]

    def hits(a: np.ndarray) -> list[int]:
        vy = a[:, C["+024"]]
        return [i for i in range(1, len(vy)) if vy[i] < -20 <= vy[i - 1]]

    fix_second = (hits(arms["60+fix"])[1:] or [len(ref)])[0]
    print(f"===== trajectory vs 30fps over vsyncs 0..{fix_second - 1} (before 60+fix's second hit)")
    for name in ("60 unpatched", "60+fix"):
        a = arms[name]
        dh = np.abs(h(a)[:fix_second] - h(ref)[:fix_second])
        dxz = np.hypot(a[:fix_second, C["bx"]] - ref[:fix_second, C["bx"]],
                       a[:fix_second, C["bz"]] - ref[:fix_second, C["bz"]])
        print(f"  {name:13s} height diff max {dh.max():7.1f} (at {int(dh.argmax())}), mean {dh.mean():6.1f};  "
              f"horizontal diff max {dxz.max():7.1f} (at {int(dxz.argmax())})")
    print("  height every 8 vsyncs:")
    for name, a in arms.items():
        print(f"   {name:13s} " + " ".join(f"{v:5.0f}" for v in h(a)[:128:8]))

    print("===== horizontal speed after side swipes")
    for name, a in arms.items():
        v = np.hypot(a[:, C["+020"]], a[:, C["+028"]])
        swipes = [i for i in range(1, len(v)) if v[i] > 20 >= v[i - 1]]
        for s in swipes[:1]:
            end = min(s + 16, len(v))
            print(f"  {name}: |v xz| from vsync {s}: " + " ".join(f"{v[i]:6.2f}" for i in range(s, end)))
            print("  " + " " * len(name) + "  ratio per vsync:        "
                  + " ".join(f"{v[i] / v[i - 1]:.3f}" if v[i - 1] > 1e-3 else "  -  " for i in range(s + 1, end)))

    print("===== sideways motion not from velocity (collision pushes), before any side swipe")
    for name, a in arms.items():
        v = np.hypot(a[:, C["+020"]], a[:, C["+028"]])
        stop = next((i for i in range(1, len(v)) if v[i] > 20), len(v))
        disp = np.hypot(a[:stop, C["+860"]], a[:stop, C["+868"]]).sum()
        vel = v[:stop].sum()
        print(f"  {name:13s} {stop:3d} vsyncs: resolved {disp:7.1f}  velocity {vel:7.1f}  "
              f"push-only {max(disp - vel, 0):7.1f} ({max(disp - vel, 0) / stop:.3f}/vsync)")

    print("===== impulses (vy up by >5, or horizontal speed up by >5)")
    for name, a in arms.items():
        vy, vx, vz = a[:, C["+024"]], a[:, C["+020"]], a[:, C["+028"]]
        ev = [f"{t}(h{h(a)[t]:.0f} v {vy[t - 1]:.1f}->{vy[t]:.1f} xz {np.hypot(vx[t], vz[t]):.1f})"
              for t in range(1, len(vy))
              if vy[t] < vy[t - 1] - 5 or abs(vx[t]) + abs(vz[t]) > abs(vx[t - 1]) + abs(vz[t - 1]) + 5]
        print(f"  {name:13s} " + "  ".join(ev))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("objects")
    p.add_argument("npz", nargs="?", default=str(config.WORK / "objtrace.npz"))
    p = sub.add_parser("mash")
    p.add_argument("npz", nargs="?", default=str(config.WORK / "mashtrace.npz"))
    args = ap.parse_args()
    (objects if args.cmd == "objects" else mash)(args.npz)
    return 0


if __name__ == "__main__":
    sys.exit(main())
