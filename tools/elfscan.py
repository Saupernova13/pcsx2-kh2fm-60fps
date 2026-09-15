"""Static questions about the unpatched KH2FM ELF - every scan the findings relied on.

    python tools/elfscan.py refs 00363404 00352130 003760C8   # who loads these addresses
    python tools/elfscan.py float 0.408163                    # data words holding a value, and their readers
    python tools/elfscan.py offsets 0x850 0x860 0x870         # functions using these object offsets
    python tools/elfscan.py callers 002EA450                  # calls, jumps and pointers to a function
    python tools/elfscan.py into 002EA49C 002EA574            # branches entering or leaving a range
    python tools/elfscan.py range 0037E000 00380000           # absolute references into a range
    python tools/elfscan.py dis 002EA530 20                   # capstone listing (no VU ops - use PCSXROO's dis)

Addresses are hex with or without 0x. Instruction scans stop at CODE_SCAN_END
(00340000): code and data share one ELF section here.
"""

from __future__ import annotations

import argparse
import sys

import _bootstrap  # noqa: F401

from game.elf import Elf, to_f32
from ps2ee.disasm import decode


def hexint(text: str) -> int:
    return int(text, 16)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("refs")
    p.add_argument("addrs", nargs="+", type=hexint)
    p = sub.add_parser("float")
    p.add_argument("value", type=float)
    p.add_argument("--tol", type=float, default=2e-5)
    p = sub.add_parser("offsets")
    p.add_argument("offsets", nargs="+", type=hexint)
    p.add_argument("--top", type=int, default=40)
    p = sub.add_parser("callers")
    p.add_argument("addr", type=hexint)
    p = sub.add_parser("into")
    p.add_argument("lo", type=hexint)
    p.add_argument("hi", type=hexint)
    p = sub.add_parser("range")
    p.add_argument("lo", type=hexint)
    p.add_argument("hi", type=hexint)
    p = sub.add_parser("dis")
    p.add_argument("addr", type=hexint)
    p.add_argument("count", type=int, nargs="?", default=16)
    args = parser.parse_args()

    elf = Elf()
    starts = elf.function_starts()

    if args.cmd == "refs":
        refs = elf.absolute_refs(args.addrs)
        for addr in args.addrs:
            uses = [(s, op) for s, op, ea in refs if ea == addr]
            funcs = sorted({starts[s] for s, _ in uses})
            print(f"== {addr:08X}: {len(uses)} refs in {len(funcs)} functions")
            for site, op in uses[:60]:
                print(f"   {site:08X}  {op:5s} (function {starts[site]:08X})")

    elif args.cmd == "float":
        hits = [a for a, w in elf.data_words() if abs(to_f32(w) - args.value) < args.tol]
        print(f"data words ~{args.value}: " + " ".join(f"{a:08X}" for a in hits))
        refs = elf.absolute_refs(hits)
        for addr in hits:
            uses = [s for s, _, ea in refs if ea == addr]
            print(f"  {addr:08X} ({elf.word(addr):08X}): {len(uses)} refs "
                  + " ".join(f"{s:08X}" for s in uses) + "  functions "
                  + " ".join(f"{f:08X}" for f in sorted({starts[s] for s in uses})))

    elif args.cmd == "offsets":
        by_function = elf.offset_uses(args.offsets)
        print(f"{len(by_function)} functions use offsets {[hex(o) for o in args.offsets]} (non-stack bases)")
        for fn, uses in sorted(by_function.items(), key=lambda kv: -len(kv[1]))[:args.top]:
            print(f"== {fn:08X}  ({len(uses)})")
            for use in uses[:12]:
                print("   " + use)

    elif args.cmd == "callers":
        fn = elf.function_start(args.addr)
        print(f"{args.addr:08X} is in the function starting {fn:08X}")
        for target in sorted({fn, args.addr}):
            print(f"  {target:08X}: jumps {[f'{kind} {a:08X}' for a, kind in elf.jumps_to(target)]}")
            print(f"  {target:08X}: data pointers {[f'{a:08X}' for a in elf.data_pointers(target)]}")
            print(f"  {target:08X}: lui/addiu loads {[f'{s:08X}' for s, op, _ in elf.absolute_refs([target]) if op == 'addiu']}")

    elif args.cmd == "into":
        entering, leaving = [], []
        for a in elf.code():
            t = elf.branch_target(a)
            if t is None:
                continue
            inside = args.lo - 4 <= a < args.hi
            if args.lo <= t < args.hi and not inside:
                entering.append((a, t))
            if inside and not (args.lo <= t < args.hi):
                leaving.append((a, t))
        print(f"branches from outside into {args.lo:08X}..{args.hi:08X}: {len(entering)}")
        for a, t in entering:
            print(f"   {a:08X} -> {t:08X}")
        print(f"branches inside leaving it: {len(leaving)}")
        for a, t in leaving:
            print(f"   {a:08X} -> {t:08X}")

    elif args.cmd == "range":
        refs = elf.refs_in_range(args.lo, args.hi)
        refs += [(a, kind, t) for t in range(args.lo, args.hi, 4) for a, kind in elf.jumps_to(t)]
        print(f"{len(refs)} references into {args.lo:08X}..{args.hi:08X}")
        for site, op, ea in sorted(refs, key=lambda r: r[2]):
            print(f"  {ea:08X}  at {site:08X}  {op}")

    elif args.cmd == "dis":
        for a in range(args.addr, args.addr + 4 * args.count, 4):
            w = elf.word(a)
            print(f"  {a:08X}  {w:08X}  {decode(w, a)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
