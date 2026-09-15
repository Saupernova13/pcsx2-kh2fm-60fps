"""Does Sora push the resting ball when he walks into it? And faster at 60fps?

    python tools/pushtest.py

Walks Sora through the resting ball (LLeft+LDown held 90 vsyncs, no attack) at
30fps, 60fps, and 60fps with each fix candidate, and records the ball's position
and its requested (+0x850) and resolved (+0x860) displacement every vsync.

Result 2026-09-15: zero movement in every arm. A resting ball is not body-pushed,
which ruled out "a per-tick push-out" as the cause of the mashing divergence.
"""

from __future__ import annotations

import argparse
import struct
import sys

import numpy as np

import _bootstrap  # noqa: F401

from game import config, physics, sandlot
from game.pnachtext import group_words

N = 90


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", type=int, default=28110)
    args = ap.parse_args()
    ours = config.PATCHES / "kh2fm-60fps.pnach"
    working = config.WIP / "working.pnach"
    arms = (("30fps", 30, None), ("60 unpatched", 60, None),
            ("60+constant scaling", 60, group_words(working, "EXPERIMENT ball physics constant scaling")),
            ("60+ball physics", 60, group_words(ours, "60 FPS - ball physics")))
    roo = sandlot.connect(args.port)
    results = {}
    for name, fps, fix in arms:
        sandlot.start(roo, fps)
        sandlot.apply_words(roo, fix)
        roo.frame_advance(sandlot.IDLE_VSYNCS)
        roo.input_set(*sandlot.WALK_BUTTONS)
        rows = np.zeros((N, 10))
        for t in range(N):
            rows[t, 0] = roo.read(0x0032B920)
            rows[t, 1:4] = struct.unpack("<3f", roo.read_bytes(sandlot.BALL_COLLISION, 12))
            rows[t, 4:7] = struct.unpack("<3f", roo.read_bytes(sandlot.BALL + physics.OFF_REQUESTED_DISP, 12))
            rows[t, 7:10] = struct.unpack("<3f", roo.read_bytes(sandlot.BALL + physics.OFF_RESOLVED_DISP, 12))
            roo.frame_advance(1)
        roo.input_release()
        results[name.replace(" ", "_").replace("+", "p")] = rows
        step = np.hypot(np.diff(rows[:, 1]), np.diff(rows[:, 3]))
        moved = np.cumsum(np.concatenate([[0.0], step]))
        first = next((t for t in range(1, N) if step[t - 1] > 0.05), None)
        print(f"== {name}: first ball movement at vsync {first}; moved by 30/60/89: "
              f"{moved[30]:.1f} / {moved[60]:.1f} / {moved[-1]:.1f}; height change {rows[0, 2] - rows[:, 2].min():.1f}")
        print(f"   sum|requested xz| {np.hypot(rows[:, 4], rows[:, 6]).sum():.1f}   "
              f"sum|resolved xz| {np.hypot(rows[:, 7], rows[:, 9]).sum():.1f}")
    config.WORK.mkdir(parents=True, exist_ok=True)
    np.savez(config.WORK / "pushtest.npz", **results)
    return 0


if __name__ == "__main__":
    sys.exit(main())
