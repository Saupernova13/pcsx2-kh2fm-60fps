"""Find every `field = field + constant` float update in the ELF - candidate per-tick integrators. Offline.

    python tools/integrators.py                        # every site
    python tools/integrators.py --min 0.05 --max 5     # constants in a gravity-like range
    python tools/integrators.py --offset 0x24          # updates of +0x24 only (vy on the prop classes)

The ball bug was one instance of an idiom: load a field, add a constant loaded
from data, store the sum back to the same field - with no delta anywhere in the
arithmetic, so it runs once per frame whatever the frame rate. At 002EA55C:

    lwc1 f03, 0x24(s2)        vy
    lwc1 f00, 0x3404(t7)      gravity, 00363404
    add.s f00, f03, f00
    swc1 f00, 0x24(s2)

This scans .text for an add.s or sub.s whose one operand was loaded from
N(base) and whose other came from an absolute data address (lui + offset), with
the result stored back to the same N(base) within a short window. Each site is
reported with the constant's value, the field offset, and whether its function
also loads delta (00349E10) or 1/delta (00349E18) - a function that does may
still integrate per tick (the ball's did), but one that does not cannot be
scaling this update by delta.

Static and heuristic: it misses constants held in registers across calls and
fields reached through computed pointers. It ranks where to look; a trace and a
watchpoint decide.
"""

from __future__ import annotations

import argparse
import struct
import sys

import _bootstrap  # noqa: F401

from game import identity
from game.elf import Elf

BACK = 18
FWD = 10
DELTA = 0x00349E10
INV_DELTA = 0x00349E18


def s16(x: int) -> int:
    return x - 0x10000 if x & 0x8000 else x


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--min", type=float, default=0.0)
    ap.add_argument("--max", type=float, default=1e9)
    ap.add_argument("--offset", type=lambda s: int(s, 0), default=None)
    ap.add_argument("--no-delta-only", action="store_true", help="only functions that never load delta")
    args = ap.parse_args()

    elf = Elf()
    lo, hi = identity.TEXT_BASE, identity.CODE_SCAN_END
    words = [elf.word(a) for a in range(lo, hi, 4)]

    def at(a: int) -> int:
        return words[(a - lo) // 4]

    # Functions are approximated by jr ra boundaries, as elsewhere in this repo.
    starts = [lo]
    for a in range(lo, hi - 8, 4):
        if at(a) == 0x03E00008:
            starts.append(a + 8)
    starts.append(hi)
    delta_fn = {}
    for s, e in zip(starts, starts[1:]):
        uses = False
        for a in range(s, e, 4):
            w = at(a)
            if (w >> 26) == 0x0F and (w & 0xFFFF) == 0x0035:
                rt = (w >> 16) & 0x1F
                for b in range(a + 4, min(a + 40, e), 4):
                    v = at(b)
                    if ((v >> 21) & 0x1F) == rt and (v >> 26) in (0x31, 0x23, 0x09):
                        if ((0x35 << 16) + s16(v & 0xFFFF)) & 0xFFFFFFFF in (DELTA, INV_DELTA):
                            uses = True
                        break
        delta_fn[s] = uses
    import bisect

    def fn_of(a: int) -> int:
        return starts[bisect.bisect_right(starts, a) - 1]

    def last_def(reg: int, a: int):
        """The most recent instruction before `a` that writes FP register `reg`, within the window."""
        for b in range(a - 4, a - 4 * BACK, -4):
            v = at(b)
            op = v >> 26
            if op == 0x31 and ((v >> 16) & 0x1F) == reg:
                return ("load", b, (v >> 21) & 0x1F, s16(v & 0xFFFF))
            if op == 0x11:
                rs = (v >> 21) & 0x1F
                if rs in (0x10, 0x14) and ((v >> 6) & 0x1F) == reg:
                    return ("calc", b, None, None)
                if rs == 0x04 and ((v >> 11) & 0x1F) == reg:
                    return ("mtc1", b, None, None)
        return None

    def absolute_of(b: int, base: int, imm: int):
        for c in range(b - 4, b - 4 * 8, -4):
            u = at(c)
            if (u >> 26) == 0x0F and ((u >> 16) & 0x1F) == base:
                return (((u & 0xFFFF) << 16) + imm) & 0xFFFFFFFF
            if ((u >> 16) & 0x1F) == base and (u >> 26) not in (0x31, 0x39, 0x11):
                return None   # base register rewritten by something other than a lui
        return None

    def pointer_of(b: int, base: int, imm: int):
        """base = [lui-built absolute pointer]: returns (pointer address, field offset) or None."""
        for c in range(b - 4, b - 4 * 8, -4):
            u = at(c)
            if ((u >> 16) & 0x1F) != base:
                continue
            if (u >> 26) == 0x23:   # lw base, off(reg)
                reg, off = (u >> 21) & 0x1F, s16(u & 0xFFFF)
                ptr = absolute_of(c, reg, off)
                return (ptr, imm) if ptr is not None and 0x00300000 <= ptr < 0x00380000 else None
            return None
        return None

    hits = []
    delta_family = 0
    for a in range(lo + 4 * BACK, hi - 4 * FWD, 4):
        w = at(a)
        if (w >> 26) != 0x11 or ((w >> 21) & 0x1F) != 0x10 or (w & 0x3F) not in (0, 1, 2):
            continue
        ft, fs, fd = (w >> 16) & 0x1F, (w >> 11) & 0x1F, (w >> 6) & 0x1F
        const = None
        for reg in (ft, fs):
            d = last_def(reg, a)
            if d and d[0] == "load":
                addr = absolute_of(d[1], d[2], d[3])
                if addr is not None and 0x00300000 <= addr < 0x00380000:
                    const = (reg, addr, None)
                    break
                via = pointer_of(d[1], d[2], d[3])
                if via is not None:
                    const = (reg, via[0], via[1])
                    break
        if const is None:
            continue
        # follow the result through mov.s to its store
        dest = {fd}
        store = None
        for b in range(a + 4, a + 4 * FWD, 4):
            v = at(b)
            if (v >> 26) == 0x11 and ((v >> 21) & 0x1F) == 0x10 and (v & 0x3F) == 6 and ((v >> 11) & 0x1F) in dest:
                dest.add((v >> 6) & 0x1F)
            if (v >> 26) == 0x39 and ((v >> 16) & 0x1F) in dest and ((v >> 21) & 0x1F) != 29:
                store = (b, (v >> 21) & 0x1F, s16(v & 0xFFFF))
                break
        if store is None:
            continue
        # the stored field must also have been loaded in the window (field = field op constant)
        loaded = any((at(b) >> 26) == 0x31 and ((at(b) >> 21) & 0x1F) == store[1] and s16(at(b) & 0xFFFF) == store[2]
                     for b in range(a - 4, a - 4 * BACK, -4))
        if not loaded:
            continue
        if const[2] is None and 0x00349E0C <= const[1] <= 0x00349E18:
            delta_family += 1
            continue
        if const[2] is None:
            value = struct.unpack("<f", struct.pack("<I", elf.word(const[1])))[0]
            if not (args.min <= abs(value) <= args.max):
                continue
            where = f"{const[1]:08X}"
        else:
            value = float("nan")   # read through a pointer: only known at run time
            where = f"[{const[1]:08X}]+{const[2]:#x}"
        if args.offset is not None and store[2] != args.offset:
            continue
        fn = fn_of(a)
        if args.no_delta_only and delta_fn.get(fn):
            continue
        op = ("add", "sub", "mul")[w & 0x3F]
        hits.append((a, fn, store[2], where, value, op, store[0], delta_fn.get(fn)))

    print(f"({delta_family} sites add or subtract delta itself - timers in delta units, correct at 60fps - not listed)")
    print(f"{len(hits)} field = field {{+,-,*}} constant sites (constants from data, or through a data pointer)")
    print(f"{'site':>10} {'function':>10} {'field':>7} {'constant':>20} {'value':>12} op   {'store':>10} delta-in-fn")
    for a, fn, off, where, value, op, store, uses in sorted(hits, key=lambda h: (h[3], h[0])):
        shown = "runtime" if value != value else f"{value:12.6f}"
        print(f"  {a:08X}  {fn:08X}  {off:+#06x}  {where:>20}  {shown:>12} {op}  {store:08X}  {'yes' if uses else 'no'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
