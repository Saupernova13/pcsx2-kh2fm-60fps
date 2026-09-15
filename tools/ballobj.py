"""Trace the real ball object every vsync in both arms, find its velocity field, and name who writes it.

    python tools/ballobj.py                 # both arms, 180 vsyncs, summaries and velocity candidates
    python tools/ballobj.py --watch         # also a write watchpoint on the ball's height, 60fps mid-flight

Reads the ball object's 4 KB region (01ADE000..01ADF000, which holds its
displacement vectors at +0x850/+0x860 and its collision shape at 01ADEAC0) and
the tick counter every vsync, from the Sandlot state with one Cross.

For each arm it reports lift, peak, landing and the fall's acceleration, then
correlates every word against the height change per game tick. On 2026-09-15 two
words matched perfectly: 01ADE224 and 01ADE234 (obj+0x854, +0x864), with
value / dy-per-tick = 1.0 at 60fps and 0.5 at 30fps. Velocity is stored per 60 Hz
frame and position moves by velocity x delta - so the bug had to be in the
velocity update, not in the position step. Writes work/ballobj-<fps>.npz.
"""

from __future__ import annotations

import argparse
import sys

import numpy as np

import _bootstrap  # noqa: F401

from game import config, physics, sandlot, timing

LO, HI = 0x01ADE000, 0x01ADF000
N_WORDS = (HI - LO) // 4
BALL_Y = sandlot.BALL_COLLISION + 4


def trace(roo, fps: int, vsyncs: int):
    sandlot.prepare(roo, fps)
    sandlot.press_cross(roo)
    block = np.zeros((vsyncs, N_WORDS), dtype=np.uint32)
    ticks = np.zeros(vsyncs, dtype=np.int64)
    for t in range(vsyncs):
        block[t] = np.frombuffer(roo.read_bytes(LO, HI - LO), dtype=np.uint32)
        ticks[t] = roo.read(timing.TICKS)
        roo.frame_advance(1)
    return block, ticks


def summarise(fps: int, block: np.ndarray, ticks: np.ndarray, vsyncs: int) -> None:
    with np.errstate(invalid="ignore", over="ignore"):
        f = block.view(np.float32).astype(np.float64)
    y = f[:, (BALL_Y - LO) // 4]
    h = y[0] - y
    tmax = int(np.argmax(h))
    lift = next((t for t in range(vsyncs) if h[t] > 0.5), None)
    if lift is None:
        print(f"===== {fps}fps: the ball never lifted")
        return
    land = next((t for t in range(tmax + 1, vsyncs) if h[t] <= 0.5), None)
    print(f"===== {fps}fps  lift {lift}  peak {h[tmax]:.1f} at {tmax}  land {land}  "
          f"air {None if land is None else land - lift}  ticks/vsync {(ticks[-1] - ticks[0]) / (vsyncs - 1):.3f}")
    print("  height per vsync from lift: " + " ".join(f"{v:.0f}" for v in h[lift:lift + 110]))
    if land and land - tmax >= 4:
        a = np.polyfit(np.arange(tmax, land, dtype=float), h[tmax:land], 2)[0]
        print(f"  fall accel {-2 * a:.4f} per vsync^2")

    idx = [t for t in range(lift, (land or vsyncs - 1)) if ticks[t + 1] > ticks[t]]
    dy = np.array([y[t + 1] - y[t] for t in idx])
    best = []
    with np.errstate(invalid="ignore", divide="ignore", over="ignore"):
        for lag in (0, 1):
            V = f[np.array(idx) + lag]
            ok = np.all(np.isfinite(V), axis=0) & (V.std(axis=0) > 1e-3) & np.all(np.abs(V) < 1e5, axis=0)
            Vc, dc = V - V.mean(axis=0), dy - dy.mean()
            corr = (Vc * dc[:, None]).sum(axis=0) / (np.sqrt((Vc ** 2).sum(axis=0) * (dc ** 2).sum()) + 1e-12)
            corr[~ok] = 0
            for i in np.argsort(-np.abs(corr))[:8]:
                ratio = np.nanmedian(V[:, i] / np.where(np.abs(dy) > 1e-3, dy, np.nan))
                best.append((abs(corr[i]), lag, LO + 4 * int(i), corr[i], ratio))
    best.sort(reverse=True)
    print(f"  velocity candidates vs height change per tick ({len(idx)} ticks):")
    for _c, lag, a, cr, ratio in best[:10]:
        print(f"    {a:08X} (ball+{a - sandlot.BALL:#x})  lag {lag}  corr {cr:+.4f}  value/dy_per_tick {ratio:+.4f}")


def watch_height(roo) -> None:
    print("===== write watchpoint on the ball's collision Y, 60fps, 30 vsyncs after the press")
    sandlot.prepare(roo, 60)
    sandlot.press_cross(roo)
    roo.frame_advance(30)
    roo.mc_clear()
    roo.mc_add(BALL_Y, BALL_Y + 4, on=("write",))
    seen: dict[tuple[int, int], list] = {}
    try:
        for _ in range(24):
            seq = roo.seq()
            roo.resume()
            stop = roo.wait(seq, timeout_ms=5000)
            if stop is None:
                print("  no hit in 5s")
                break
            regs = roo.regs("GPR")
            pc = getattr(stop, "pc", None) or regs.get("pc")
            seen.setdefault((pc, regs.get("ra")), [0, regs])[0] += 1
    finally:
        roo.mc_clear()
        if not roo.paused():
            roo.pause()
    for (pc, ra), (n, r) in seen.items():
        print(f"  pc {pc:08X} ra {ra:08X} hits {n}  " + " ".join(f"{k}={r.get(k, 0):08X}" for k in ("a0", "s0", "s1", "sp")))
        for a, text in roo.dis(pc - 48, 20):
            print(f"     {'->' if a == pc else '  '} {a:08X}  {text}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--vsyncs", type=int, default=180)
    ap.add_argument("--watch", action="store_true")
    args = ap.parse_args()

    roo = sandlot.connect()
    config.WORK.mkdir(parents=True, exist_ok=True)
    for fps in (60, 30):
        block, ticks = trace(roo, fps, args.vsyncs)
        np.savez(config.WORK / f"ballobj-{fps}.npz", lo=LO, block=block, ticks=ticks)
        summarise(fps, block, ticks, args.vsyncs)
    if args.watch:
        watch_height(roo)
    print(f"(velocity lives at ball+{physics.OFF_REQUESTED_DISP:#x} / +{physics.OFF_RESOLVED_DISP:#x} "
          f"as displacement/delta; the integrator's own state is ball+{physics.OFF_VELOCITY:#x})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
