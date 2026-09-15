"""The widescreen retarget's arithmetic, checked against ElHecht's 16:9 and the shipped JSON.

    python tools/ws-math.py                      # 19.5:9, the S24 Ultra panel (3120x1440)
    python tools/ws-math.py --aspect 16:9        # reproduces ElHecht's 3F400000 exactly
    python tools/ws-math.py --aspect 3088:1440   # Samsung's own listed resolution, 19.3:9
    python tools/ws-math.py --live               # disassemble 00106D40..00106F00 from a running PCSX2 (PINE)

The projection routine at 00106DE8 multiplies a 4:3 base (0.8) by the widen
factor (4/3)/aspect, loaded with lui $k1 at 00106E54; the three font x-scale
floats at 0036CE94..9C carry the same factor. A bare lui only sets the top 16
bits, so the full word needs lui+ori, with mtc1 moved into the stock nop at
00106E60.
"""

from __future__ import annotations

import argparse
import json
import struct
import sys

import _bootstrap  # noqa: F401

from game import config
from game.elf import from_f32, to_f32
from ps2ee.disasm import decode


def ratio(text: str) -> float:
    a, b = text.split(":")
    return float(a) / float(b)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--aspect", default="19.5:9")
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--pine-port", type=int, default=28011)
    args = parser.parse_args()

    aspect = ratio(args.aspect)
    factor = (4 / 3) / aspect
    word = from_f32(factor)
    hi, lo = word >> 16, word & 0xFFFF
    lui_only = to_f32(hi << 16)
    print(f"aspect {args.aspect} = {aspect:.6f}; widen factor (4/3)/aspect = {factor:.7f} = {word:08X}")
    print(f"  lui-only would load {lui_only:.7f}, {abs(lui_only / factor - 1):.2%} off")
    words = {0x00106E54: 0x3C1B0000 | hi, 0x00106E58: 0x377B0000 | lo, 0x00106E60: 0x449BF000}
    for addr, w in words.items():
        print(f"  {addr:08X}  {w:08X}  {decode(w, addr)}")
    print(f"  font x-scale 0036CE94..9C = {word:08X}")
    print(f"check: 16:9 gives {from_f32((4 / 3) / (16 / 9)):08X} (ElHecht ships 3F400000, lui 0x3F40)")

    if abs(aspect - 19.5 / 9) < 1e-9:
        spec = json.loads((config.PATCHES / "widescreen-19.5x9-s24.json").read_text(encoding="utf-8"))
        want = {int(r["addr"], 16) & 0x01FFFFFF: int(r["value"], 16) for r in spec["replace"]}
        want.update({int(i["addr"], 16): int(i["value"], 16) for i in spec["insert_after"]})
        ours = dict(words)
        ours.update({0x0036CE94: word, 0x0036CE98: word, 0x0036CE9C: word})
        print(f"patch/widescreen-19.5x9-s24.json agrees: {ours == want}")

    if args.live:
        from ps2ee.pine import Pine
        start, end = 0x00106D40, 0x00106F00
        with Pine(port=args.pine_port).connect() as pine:
            print(f"live: {pine.title()} ({pine.game_id()}), {pine.status()}")
            for i, w in enumerate(pine.read_block(start, (end - start) // 4)):
                a = start + i * 4
                print(f"  {a:08X}  {w:08X}  {decode(w, a)}")
            for a in (0x0036A0B8, 0x0036A0BC, 0x0036CE94):
                v = pine.read(a)
                print(f"  {a:08X}  {v:08X}  {struct.unpack('<f', struct.pack('<I', v))[0]:.4f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
