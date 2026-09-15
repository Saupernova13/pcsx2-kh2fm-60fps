"""How KH2FM times a frame, and what PeterDelta's [60 FPS] group changes - from the ELF alone.

    python tools/frame-timing.py            # stock values, references, callers
    python tools/frame-timing.py --dis      # also disassemble the frame routine and the vsync paths

Everything here is read from the unpatched boot ELF in work/ (tools/extract-elf.py),
so it is the stock game: the values [60 FPS] overwrites, every instruction that
reads them, who sets the vsync wait and with what, and where the vsync count is
incremented. The live side of the same story is tools/tickrate.py.
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter

import _bootstrap  # noqa: F401

from game import timing
from game.elf import Elf
from ps2ee.disasm import decode

NAMES = {
    timing.VSYNC_COUNT: "vsync count", timing.DELTA_SCALE: "delta scale", timing.DELTA: "delta",
    timing.DELTA_UNCLAMPED: "delta before cap", timing.INV_DELTA: "1/delta", timing.VSYNC_WAIT: "vsync wait",
    timing.MEASURED_DELTA_FLAG: "measured-delta flag", timing.DELTA_BASE: "constant delta",
    timing.DELTA_CAP: "delta cap", timing.ACCUM_THRESHOLD: "accumulator threshold", timing.GAME_MODE: "game mode",
}


def listing(elf: Elf, lo: int, hi: int) -> None:
    print(f"---- {lo:08X}..{hi:08X}")
    for a in range(lo, hi, 4):
        w = elf.word(a)
        print(f"  {a:08X}  {w:08X}  {decode(w, a)}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dis", action="store_true")
    args = parser.parse_args()
    elf = Elf()
    starts = elf.function_starts()

    print("===== stock values (what [60 FPS] finds before it writes)")
    for addr, name in NAMES.items():
        w = elf.word(addr)
        print(f"  {addr:08X}  {w:08X}  f={elf.f32(addr):10.6f}  {name}")

    print("===== references in code")
    refs = elf.absolute_refs(NAMES)
    by_target: dict[int, list[tuple[int, str]]] = {}
    for site, op, ea in refs:
        by_target.setdefault(ea, []).append((site, op))
    for addr, name in NAMES.items():
        uses = by_target.get(addr, [])
        kinds = Counter(op for _, op in uses)
        funcs = sorted({starts[s] for s, _ in uses})
        print(f"  {addr:08X} {name:22s} {len(uses):4d} refs {dict(kinds)} in {len(funcs)} functions")
        if len(uses) <= 12:
            for site, op in uses:
                print(f"      {site:08X}  {op:5s} (function {starts[site]:08X})")

    print("===== who sets the vsync wait (setter 0014CE30) and the measured-delta flag (setter 0014CE20)")
    for target in (timing.VSYNC_WAIT_SETTER, 0x0014CE20):
        for site, kind in elf.jumps_to(target):
            arg = decode(elf.word(site + 4), site + 4)
            print(f"  {kind} {target:08X} at {site:08X}; delay slot: {arg}")

    print("===== the vsync callback registration")
    for site, op, ea in elf.absolute_refs([timing.VSYNC_CALLBACK, 0x0014CF88]):
        print(f"  {site:08X}  {op} -> {ea:08X}  (function {starts[site]:08X})")

    print("===== the fixed-step accumulator (reads the accumulator threshold)")
    for site, _op, _ea in elf.absolute_refs([timing.ACCUM_THRESHOLD]):
        fn = starts[site]
        callers = elf.jumps_to(fn)
        print(f"  {site:08X} in function {fn:08X}; called from {[f'{c:08X}' for c, _ in callers]}")

    if args.dis:
        listing(elf, 0x0014CE20, 0x0014CF80)
        listing(elf, 0x0014D060, 0x0014D240)
        listing(elf, 0x0014D478, 0x0014D4E8)
    return 0


if __name__ == "__main__":
    sys.exit(main())
