"""Trace an object's memory every vsync through a scripted input, in each frame-rate arm, and find what differs.

    python tools/objtrace.py capture work/ot-jump.npz --obj 01A94440 --script "wait:6,hold:Circle:6,wait:110"
    python tools/objtrace.py capture work/ot-jump.npz --obj 01A94440 --script "..." --arms 30,60,60fix
    python tools/objtrace.py fields work/ot-jump.npz                 # every float lane that moves, per arm
    python tools/objtrace.py fields work/ot-jump.npz --lo 0xC0 --hi 0x140
    python tools/objtrace.py classes work/ot-jump.npz                # class pointer (+0x0C) switches per arm

The general form of tools/ballobj.py. Reads --size bytes from the object every
vsync (0x1000 by default - velocity at +0x20, the jump/arc fields at +0xD0..+0xDC,
position at +0x540, the displacement vectors at +0x850/+0x860 all sit inside) plus
the game tick counter, from the same save state and the same script in every arm.

`fields` reports, for every float lane that changes: the total variation in each
arm over the same real time and the ratio against 30fps - a lane that covers twice
the ground at 60fps is running per tick; one that covers the same is correct.
Lanes that change only at 60fps, or only at 30fps, are listed too. Offsets are
relative to the object.

Arms: 30 and 60 as in tools/ratediff.py; `60fix` is 60 plus every group in
patch/kh2fm-60fps.pnach; `60w` is 60 plus the groups named with --group from
wip/working.pnach.

Script syntax as in tools/movetest.py: wait:N, hold:BTN[+BTN]:N, tap:BTN.
"""

from __future__ import annotations

import argparse
import sys

import numpy as np

import _bootstrap  # noqa: F401

import movetest
import ratediff
from game import config, sandlot, timing
from game.pnachtext import group_words, headers


def fix_words(arm: str, groups: list[str]) -> list:
    """60fix/30fix: every group in patch/; 60w/30w: the --group names from wip/working.pnach."""
    if arm.endswith("fix"):
        path = config.PATCHES / "kh2fm-60fps.pnach"
        return [w for _, name in headers(path.read_text(encoding="utf-8").splitlines())
                for w in group_words(path, name)]
    if arm.endswith("w"):
        return [w for name in groups for w in group_words(config.WIP / "working.pnach", name)]
    return []


def capture(args) -> int:
    roo = sandlot.connect(args.port)
    steps = movetest.parse(args.script)
    out = {"obj": np.array([args.obj]), "size": np.array([args.size]), "arms": np.array(args.arms.split(",")),
           "script": np.array([args.script])}
    for arm in args.arms.split(","):
        base = "60" if arm.startswith("60") else "30"
        ratediff.start_arm(roo, base, args.slot)
        sandlot.apply_words(roo, fix_words(arm, args.group))
        blocks, ticks = [], []
        for kind, buttons, n in steps:
            if kind == "hold":
                roo.input_set(*buttons)
            for _ in range(n):
                blocks.append(np.frombuffer(roo.read_bytes(args.obj, args.size), dtype="<u4"))
                ticks.append(roo.read(timing.TICKS))
                roo.frame_advance(1)
            if kind == "hold":
                roo.input_release()
        out[f"{arm}_block"] = np.stack(blocks)
        out[f"{arm}_ticks"] = np.array(ticks)
        print(f"  arm {arm}: {len(blocks)} vsyncs, {ticks[-1] - ticks[0]} ticks")
    np.savez_compressed(args.out, **out)
    print(f"saved {args.out}")
    return 0


def as_float(block: np.ndarray) -> np.ndarray:
    with np.errstate(all="ignore"):
        f = block.view("<f4").astype(np.float64)
    return f


def fields(args) -> int:
    z = np.load(args.npz)
    arms = [str(a) for a in z["arms"]]
    ref = as_float(z["30_block"]) if "30" in arms else None
    data = {a: as_float(z[f"{a}_block"]) for a in arms}
    lanes = data[arms[0]].shape[1]
    lo, hi = args.lo // 4, min(args.hi // 4, lanes)
    print(f"object {int(z['obj'][0]):08X}, script {str(z['script'][0])!r}")
    head = "  off   " + "  ".join(f"{a + ' tv':>12}" for a in arms) + "   ratio(s) vs 30   start -> end per arm"
    print(head)
    for k in range(lo, hi):
        cols = []
        tv = {}
        ok = True
        for a in arms:
            s = data[a][:, k]
            if not np.all(np.isfinite(s)) or np.any(np.abs(s) > 1e6) or np.any((s != 0) & (np.abs(s) < 1e-20)):
                ok = False
                break
            tv[a] = float(np.sum(np.abs(np.diff(s))))
        if not ok or max(tv.values()) < args.min_tv:
            continue
        ratios = "  ".join(f"{a}:{tv[a] / tv['30']:.2f}" if ref is not None and tv["30"] > 0 else f"{a}:-"
                           for a in arms if a != "30")
        ends = "  ".join(f"{data[a][0, k]:.3f}->{data[a][-1, k]:.3f}" for a in arms)
        cols = "  ".join(f"{tv[a]:12.4f}" for a in arms)
        print(f"  {4 * k:#05x} {cols}   {ratios}   {ends}")
    return 0


def classes(args) -> int:
    z = np.load(args.npz)
    for a in (str(x) for x in z["arms"]):
        cls = z[f"{a}_block"][:, 3]
        changes = [f"{t}:{cls[t - 1]:08X}->{cls[t]:08X}" for t in range(1, len(cls)) if cls[t] != cls[t - 1]]
        print(f"  arm {a}: start {cls[0]:08X}  " + " ".join(changes))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("capture")
    c.add_argument("out")
    c.add_argument("--obj", required=True, type=lambda s: int(s, 16))
    c.add_argument("--script", required=True)
    c.add_argument("--size", type=lambda s: int(s, 0), default=0x1000)
    c.add_argument("--arms", default="30,60")
    c.add_argument("--group", action="append", default=[])
    c.add_argument("--slot", type=int, default=sandlot.SLOT)
    c.add_argument("--port", type=int, default=28110)
    f = sub.add_parser("fields")
    f.add_argument("npz")
    f.add_argument("--lo", type=lambda s: int(s, 0), default=0)
    f.add_argument("--hi", type=lambda s: int(s, 0), default=0x1000)
    f.add_argument("--min-tv", type=float, default=0.01)
    k = sub.add_parser("classes")
    k.add_argument("npz")
    args = ap.parse_args()
    return {"capture": capture, "fields": fields, "classes": classes}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
