"""Catch who reads or writes something in the Sandlot scene: watchpoints and breakpoints, collected.

    python tools/watch.py --write 01ADD9F4:4 --fps 60 --fix --mash-to 64
    python tools/watch.py --write 01ADEAC4:4 --fps 60 --hit-then 30
    python tools/watch.py --read 01ADE220:20 --fps 60 --hit-then 52
    python tools/watch.py --write 01AC24B0:10 --write 01AC2A00:10 --fps 60 --mash-to 34
    python tools/watch.py --bp 002E7EE8 --fps 60 --hit-then 0

Sets the scene up with the Sandlot schedule (--mash-to N drives the mash for N
vsyncs; --hit-then N walks, presses Cross and advances N vsyncs), arms the stops,
then lets the game RUN and collects each distinct (pc, ra) with its registers
and a disassembly. Ranges are ADDR:LEN in hex. --skip LO-HI marks known per-tick
writers (the ball's motion routine and the fix's cave by default).

Two things learned the hard way (2026-09-15):
  - stops only fire under run/wait. Driving input with frame-advance first and
    arming afterwards is the pattern; a breakpoint armed during frame-advance
    steps looked like "breakpoints never fire".
  - numbers in a --cond expression are HEX. "t5 == 28170704" means 0x28170704.
"""

from __future__ import annotations

import argparse
import sys

import _bootstrap  # noqa: F401

from game import config, physics, sandlot, timing
from game.pnachtext import group_words

DEFAULT_SKIP = [(0x002EA41C, 0x002EAA60), (physics.CAVE, physics.CAVE + 0x40)]


def span(text: str) -> tuple[int, int]:
    addr, _, length = text.partition(":")
    lo = int(addr, 16)
    return lo, lo + int(length or "4", 16)


def lohi(text: str) -> tuple[int, int]:
    lo, _, hi = text.partition("-")
    return int(lo, 16), int(hi, 16)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--write", action="append", default=[], type=span)
    parser.add_argument("--read", action="append", default=[], type=span)
    parser.add_argument("--bp", action="append", default=[], type=lambda t: int(t, 16))
    parser.add_argument("--cond", help="breakpoint condition (numbers are hex)")
    parser.add_argument("--fps", type=int, default=60, choices=(30, 60))
    parser.add_argument("--fix", action="store_true", help="apply [60 FPS - ball physics]")
    parser.add_argument("--mash-to", type=int)
    parser.add_argument("--hit-then", type=int)
    parser.add_argument("--hits", type=int, default=60)
    parser.add_argument("--ticks", type=int, default=40, help="stop after this many game ticks")
    parser.add_argument("--skip", action="append", type=lohi)
    parser.add_argument("--no-default-skip", action="store_true")
    args = parser.parse_args()

    skip = (args.skip or []) + ([] if args.no_default_skip else DEFAULT_SKIP)
    fix = group_words(config.PATCHES / "kh2fm-60fps.pnach", "60 FPS - ball physics") if args.fix else None
    roo = sandlot.connect()
    sandlot.prepare(roo, args.fps, fix)
    if args.mash_to is not None:
        for t in range(args.mash_to):
            sandlot.mash_step(roo, t)
            roo.frame_advance(1)
        if args.mash_to % sandlot.MASH_PERIOD < sandlot.PRESS_VSYNCS:
            roo.input_set("Cross")
    elif args.hit_then is not None:
        sandlot.press_cross(roo)
        if args.hit_then:
            roo.frame_advance(args.hit_then)

    roo.mc_clear()
    roo.bp_clear()
    for lo, hi in args.write:
        roo.mc_add(lo, hi, on=("write",))
    for lo, hi in args.read:
        roo.mc_add(lo, hi, on=("read",))
    for addr in args.bp:
        roo.bp_add(addr, condition=args.cond, description="tools/watch.py")

    seen: dict[tuple[int, int], dict] = {}
    t_end = roo.read(timing.TICKS) + args.ticks
    try:
        for _ in range(args.hits):
            seq = roo.seq()
            roo.resume()
            stop = roo.wait(seq, timeout_ms=5000)
            if stop is None:
                print("  (no stop within 5s)")
                break
            regs = roo.regs("GPR")
            pc = getattr(stop, "pc", None) or regs.get("pc")
            key = (pc, regs.get("ra"))
            if key not in seen:
                seen[key] = {"n": 0, "tick": roo.read(timing.TICKS), "regs": regs,
                             "addrs": set(), "reason": getattr(stop, "reason", "?")}
            seen[key]["n"] += 1
            seen[key]["addrs"].add(getattr(stop, "mem_addr", 0) or 0)
            if roo.read(timing.TICKS) >= t_end:
                break
    finally:
        roo.mc_clear()
        roo.bp_clear()
        roo.input_release()
        if not roo.paused():
            roo.pause()

    for (pc, ra), info in sorted(seen.items(), key=lambda kv: kv[1]["tick"]):
        known = any(lo <= pc < hi for lo, hi in skip)
        r = info["regs"]
        print(f"pc {pc:08X}  ra {ra:08X}  hits {info['n']:3d}  first tick {info['tick']}  {info['reason']}"
              f"{'  (known per-tick writer)' if known else ''}")
        if known:
            continue
        print("   " + " ".join(f"{k}={r.get(k, 0):08X}" for k in ("a0", "a1", "a2", "s0", "s1", "s2", "t5", "t6", "t7", "v0", "sp")))
        for a, text in roo.dis(pc - 24, 11):
            print(f"      {'->' if a == pc else '  '} {a:08X}  {text}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
