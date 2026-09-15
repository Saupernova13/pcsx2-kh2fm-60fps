"""Acceptance test for anything that moves: same state, same scripted input, 30fps against 60fps.

    python tools/movetest.py --pos 01C12340 --script "wait:6,hold:Circle:6,wait:120"         # a jump
    python tools/movetest.py --pos 01C12340 --script "wait:6,hold:LUp:90" --what walk        # walk speed
    python tools/movetest.py --pos 01C12340 --script "..." --fix                             # 60fps + our groups
    python tools/movetest.py --pos 01C12340 --script "..." --pnach FILE --group NAME --save work/jump.npz

Generalises tools/balltest.py from the Sandlot ball to any position vector - the
player, an enemy, a prop. The 30fps arm is the oracle: same save state, same input
schedule in vsyncs, so both arms cover the same real time. A fix is applied as the
group's word writes after the state loads, as PCSX2 does every frame.

Script: comma-separated steps, each run in order:
    wait:N              advance N vsyncs with nothing held
    hold:BTN[+BTN]:N    hold the buttons for N vsyncs, then release
    tap:BTN[+BTN]       hold for 2 vsyncs, then release
The trace covers every vsync of the script. KH2's y axis is negative-up; height is
reported as start y - y.

Metrics: peak height and when, airtime (vsyncs above --air height), the fall's
acceleration (quadratic fit from the peak to landing), and horizontal path length
and net displacement. Exit 0 when 60fps(+fix) matches within tolerance, 1 otherwise.
"""

from __future__ import annotations

import argparse
import struct
import sys

import numpy as np

import _bootstrap  # noqa: F401

import ratediff
from game import config, sandlot
from game.pnachtext import group_words

TOL_PEAK = 0.04
TOL_AIR = 3
TOL_FALL = 0.10
TOL_PATH = 0.08


def parse(script: str) -> list[tuple[str, list[str], int]]:
    steps = []
    for tok in (t.strip() for t in script.split(",") if t.strip()):
        parts = tok.split(":")
        if parts[0] == "wait":
            steps.append(("wait", [], int(parts[1])))
        elif parts[0] == "hold":
            steps.append(("hold", parts[1].split("+"), int(parts[2])))
        elif parts[0] == "tap":
            steps.append(("hold", parts[1].split("+"), 2))
        else:
            raise SystemExit(f"bad script step {tok!r}")
    return steps


def trace(roo, arm: str, slot: int, pos: int, steps, fix) -> np.ndarray:
    ratediff.start_arm(roo, arm, slot)
    sandlot.apply_words(roo, fix)
    rows = []
    for kind, buttons, n in steps:
        if kind == "hold":
            roo.input_set(*buttons)
        for _ in range(n):
            rows.append(struct.unpack("<3f", roo.read_bytes(pos, 12)))
            roo.frame_advance(1)
        if kind == "hold":
            roo.input_release()
    rows.append(struct.unpack("<3f", roo.read_bytes(pos, 12)))
    return np.array(rows)


def metrics(xyz: np.ndarray, air: float) -> dict:
    h = xyz[0, 1] - xyz[:, 1]
    peak_t = int(np.argmax(h))
    up = h > air
    airtime = int(up.sum())
    land = next((t for t in range(peak_t + 1, len(h)) if h[t] <= air), None)
    fall = None
    if land is not None and land - peak_t >= 6:
        t = np.arange(peak_t, land, dtype=float)
        fall = -2 * np.polyfit(t, h[peak_t:land], 2)[0]
    xz = xyz[:, [0, 2]]
    return {"peak": float(h.max()), "peak_t": peak_t, "air": airtime, "fall": fall,
            "path": float(np.sum(np.linalg.norm(np.diff(xz, axis=0), axis=1))),
            "net": float(np.linalg.norm(xz[-1] - xz[0]))}


def show(name: str, m: dict) -> None:
    fall = "-" if m["fall"] is None else f"{m['fall']:.4f}"
    print(f"  {name:16s} peak {m['peak']:8.2f} at {m['peak_t']:3d}  air {m['air']:3d}  fall {fall:>8}  "
          f"path {m['path']:8.2f}  net {m['net']:8.2f}")


def compare(ref: dict, got: dict, what: str) -> list[str]:
    bad = []
    if what in ("jump", "all"):
        if ref["peak"] > 1 and abs(got["peak"] - ref["peak"]) > TOL_PEAK * ref["peak"]:
            bad.append(f"peak {got['peak']:.2f} vs {ref['peak']:.2f}")
        if abs(got["air"] - ref["air"]) > TOL_AIR:
            bad.append(f"airtime {got['air']} vs {ref['air']}")
        if ref["fall"] and got["fall"] and abs(got["fall"] / ref["fall"] - 1) > TOL_FALL:
            bad.append(f"fall {got['fall']:.4f} vs {ref['fall']:.4f}")
    if what in ("walk", "all"):
        if ref["path"] > 1 and abs(got["path"] / ref["path"] - 1) > TOL_PATH:
            bad.append(f"path {got['path']:.2f} vs {ref['path']:.2f}")
    return bad


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pos", required=True, type=lambda s: int(s, 16), help="address of the x, y, z floats")
    ap.add_argument("--script", required=True)
    ap.add_argument("--slot", type=int, default=sandlot.SLOT)
    ap.add_argument("--what", default="all", choices=("jump", "walk", "all"))
    ap.add_argument("--air", type=float, default=1.0, help="height that counts as airborne")
    ap.add_argument("--fix", action="store_true", help="apply every group in patch/kh2fm-60fps.pnach")
    ap.add_argument("--pnach")
    ap.add_argument("--group", action="append", default=[])
    ap.add_argument("--save")
    ap.add_argument("--port", type=int, default=28110)
    args = ap.parse_args()

    fix = []
    if args.fix:
        from game.pnachtext import headers
        path = config.PATCHES / "kh2fm-60fps.pnach"
        for _, name in headers(path.read_text(encoding="utf-8").splitlines()):
            fix += group_words(path, name)
    for name in args.group:
        fix += group_words(args.pnach or config.WIP / "working.pnach", name)

    steps = parse(args.script)
    roo = sandlot.connect(args.port)
    ref_xyz = trace(roo, "30", args.slot, args.pos, steps, None)
    plain_xyz = trace(roo, "60", args.slot, args.pos, steps, None)
    ref, plain = metrics(ref_xyz, args.air), metrics(plain_xyz, args.air)
    show("30fps oracle", ref)
    show("60fps", plain)
    saved = {"ref": ref_xyz, "plain": plain_xyz}
    verdict, got = "60fps unpatched", plain
    if fix:
        fixed_xyz = trace(roo, "60", args.slot, args.pos, steps, fix)
        got = metrics(fixed_xyz, args.air)
        show("60fps + fix", got)
        saved["fixed"] = fixed_xyz
        verdict = "60fps + fix"
    if args.save:
        np.savez(args.save, **saved)
    bad = compare(ref, got, args.what)
    if bad:
        print(f"FAIL: {verdict} differs from 30fps: " + "; ".join(bad))
        return 1
    print(f"PASS: {verdict} matches 30fps within tolerance")
    return 0


if __name__ == "__main__":
    sys.exit(main())
