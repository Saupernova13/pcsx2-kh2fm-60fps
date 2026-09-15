"""Track the Sandlot ball every vsync in both arms, then find who writes its height.

The ball's vertical coordinate is 0037EC34 (negative-up: smaller is higher),
found by diffing RAM across one hit. Same state, same vsync input schedule in
both arms, so the two runs cover the same real time.

    python kh2_balltrack.py [--vsyncs 180] [--no-watch]
"""
import argparse
import struct

import numpy as np

import kh2lab

BLOCK_LO, BLOCK_HI = 0x0037EB00, 0x0037F100
BALL_Y = 0x0037EC34


def run_arm(roo, fps: int, vsyncs: int):
    kh2lab.start(roo, fps)
    roo.frame_advance(6)
    roo.input_set("LLeft", "LDown")
    roo.frame_advance(8)
    roo.input_release()
    roo.input_set("Cross")
    roo.frame_advance(2)
    roo.input_release()
    n = (BLOCK_HI - BLOCK_LO) // 4
    block = np.zeros((vsyncs, n), dtype=np.uint32)
    ticks = np.zeros(vsyncs, dtype=np.int64)
    for t in range(vsyncs):
        block[t] = struct.unpack(f"<{n}I", roo.read_bytes(BLOCK_LO, BLOCK_HI - BLOCK_LO))
        ticks[t] = roo.read(kh2lab.TICKS)
        roo.frame_advance(1)
    return block, ticks


def summarise(fps: int, block: np.ndarray, ticks: np.ndarray) -> dict:
    y = block[:, (BALL_Y - BLOCK_LO) // 4].view(np.float32).astype(np.float64)
    rest = y[0]
    tmin = int(np.argmin(y))
    ymin = y[tmin]
    lift = next((t for t in range(len(y)) if y[t] < rest - 0.5), None)
    land = next((t for t in range(tmin + 1, len(y)) if y[t] >= rest - 0.5), None)
    out = {"fps": fps, "rest": rest, "peak_height": rest - ymin, "lift": lift, "peak_at": tmin, "land": land}
    if lift is not None:
        out["rise_vsyncs"] = tmin - lift
    if land is not None:
        out["fall_vsyncs"] = land - tmin
        out["air_vsyncs"] = land - lift if lift is not None else None
        seg_t = np.arange(tmin, land, dtype=np.float64)
        seg_y = y[tmin:land]
        if len(seg_t) >= 4:
            a, b, c = np.polyfit(seg_t, seg_y, 2)
            out["g_per_vsync2"] = 2 * a
    tick_rate = (ticks[-1] - ticks[0]) / (len(ticks) - 1)
    out["ticks_per_vsync"] = tick_rate
    if "g_per_vsync2" in out:
        out["g_per_tick2"] = out["g_per_vsync2"] / tick_rate ** 2
    print(f"===== {fps}fps")
    for k, v in out.items():
        print(f"  {k:16s} {v:.4f}" if isinstance(v, float) else f"  {k:16s} {v}")
    print("  height above rest every 4 vsyncs:")
    print("   " + " ".join(f"{rest - v:6.1f}" for v in y[::4]))
    return out


def watch_writers(roo, hits: int = 24):
    print("===== write watchpoint on ball Y, 60fps, mid-flight")
    kh2lab.start(roo, 60)
    roo.frame_advance(6)
    roo.input_set("LLeft", "LDown")
    roo.frame_advance(8)
    roo.input_release()
    roo.input_set("Cross")
    roo.frame_advance(2)
    roo.input_release()
    roo.frame_advance(30)
    roo.mc_clear()
    note = roo.mc_add(BALL_Y, BALL_Y + 4, on=("write",))
    print(f"  mc.add -> {note}")
    seen = {}
    try:
        for _ in range(hits):
            seq = roo.seq()
            roo.resume()
            stop = roo.wait(seq, timeout_ms=5000)
            if stop is None:
                print("  no further hit within 5s")
                break
            regs = roo.regs("GPR")
            pc = getattr(stop, "pc", None) or regs.get("pc")
            key = (pc, regs.get("ra"))
            if key not in seen:
                seen[key] = {"count": 0, "regs": regs}
            seen[key]["count"] += 1
    finally:
        roo.mc_clear()
        if not roo.paused():
            roo.pause()
    for (pc, ra), info in seen.items():
        r = info["regs"]
        print(f"  pc {pc:08X}  ra {ra:08X}  hits {info['count']}  a0 {r.get('a0', 0):08X}  s0 {r.get('s0', 0):08X}  s1 {r.get('s1', 0):08X}")
        for addr, text in roo.dis(pc - 20, 10):
            mark = "->" if addr == pc else "  "
            print(f"     {mark} {addr:08X}  {text}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--vsyncs", type=int, default=180)
    ap.add_argument("--no-watch", action="store_true")
    args = ap.parse_args()

    roo = kh2lab.connect()
    results = {}
    for fps in (60, 30):
        block, ticks = run_arm(roo, fps, args.vsyncs)
        np.savez(kh2lab.SCRATCH / f"ball-{fps}.npz", lo=BLOCK_LO, block=block, ticks=ticks)
        results[fps] = summarise(fps, block, ticks)

    a, b = results[60], results[30]
    print("===== 60fps / 30fps, same real time")
    for k in ("peak_height", "rise_vsyncs", "fall_vsyncs", "air_vsyncs", "g_per_vsync2", "g_per_tick2"):
        if k in a and k in b and a[k] and b[k]:
            print(f"  {k:16s} {a[k] / b[k]:.3f}")

    if not args.no_watch:
        watch_writers(roo)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
