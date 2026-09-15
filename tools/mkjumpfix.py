"""Generate [60 FPS - short hop]: cut a released jump's rise only on even jump-clock values. Offline.

    python tools/mkjumpfix.py            # print the group with a decoded listing
    python tools/mkjumpfix.py --write    # write or replace the group in wip/working.pnach
    python tools/mkjumpfix.py --check    # wip/working.pnach (and patch/, if it has it) agree

The defect (2026-09-15, Twilight Town, Sora): a jump is a closed-form arc on a
clock at obj+0xD0 that advances by delta. The jump controller 0017C690 cuts the
rise into the short apex arc once the jump button has been released (flag
0x40000 in obj+0x108) and the clock is past 6.0 ([0036C518]):

    0017C790  addiu t7, t7, -0x3AE8   ; 0036C518 = 6.0
    0017C794  lwc1  f0, 0(t7)
    0017C798  c.olt.s f0, f1          ; 6.0 < clock
    0017C79C  bc1f  0017C81C          ; not yet
    0017C7A0  lui   t7, 0x37          ; (delay slot)
    0017C7A4  addiu t7, t7, -0x3AE4   ; ... cut to the apex arc

At 30fps the clock steps 2, 4, 6, 8, so a tap cuts at 8; at 60fps it steps by 1
and cuts at 7 - one unit of rise early, 11.6 units lower (peak 103.5 against
115.1). More generally a release is only ever seen on an even clock at 30fps.
The group lets the cut happen only when the clock is even: unchanged at 30fps,
where the clock is always even, and the 30fps grid at 60fps. A held jump already
matched (peak 185.00 both).

Hook 0017C798 -> cave 000FE040 (after [60 FPS - ball physics], 000FE000..3C).
f3 and t0 are free there: nothing in the rest of the function reads them before
the next call clobbers them.
"""

from __future__ import annotations

import argparse
import sys

import _bootstrap  # noqa: F401

from ps2ee.disasm import decode

from game import config
from game.elf import Elf
from game.pnachtext import block_range, group_words, insert_after, normalise_blank_lines, remove_block

NAME = "60 FPS - short hop"
HOOK = 0x0017C798
NOT_YET = 0x0017C81C
GO = 0x0017C7A4
CAVE = 0x000FE040

EXPECT = {0x0017C794: 0xC5E00000, 0x0017C798: 0x46010034, 0x0017C79C: 0x4500001F, 0x0017C7A0: 0x3C0F0037,
          0x0017C7A4: 0x25EFC51C}
T0, T7, ZERO = 8, 15, 0


def j(target: int) -> int:
    return 0x08000000 | (target >> 2)


def branch(op: int, pc: int, target: int, rs: int = 0, rt: int = 0) -> int:
    return (op << 26) | (rs << 21) | (rt << 16) | (((target - pc - 4) >> 2) & 0xFFFF)


def bc1f(pc: int, target: int) -> int:
    return 0x45000000 | (((target - pc - 4) >> 2) & 0xFFFF)


def build(elf: Elf) -> list[tuple[int, int, str]]:
    for addr, want in EXPECT.items():
        got = elf.word(addr)
        if got != want:
            raise SystemExit(f"ELF word at {addr:08X} is {got:08X}, expected {want:08X} - wrong build?")
    lui_t7 = elf.word(0x0017C7A0)
    compare = elf.word(0x0017C798)
    c = CAVE
    words = [
        (c + 0x00, compare, "c.olt.s f0, f1        6.0 < clock (copied from 0017C798)"),
        (c + 0x04, bc1f(c + 0x04, c + 0x20), "bc1f   not_yet"),
        (c + 0x08, 0x00000000, "nop"),
        (c + 0x0C, 0x460008E4, "cvt.w.s f3, f1        clock as an integer"),
        (c + 0x10, 0x44081800, "mfc1   t0, f3"),
        (c + 0x14, 0x31080001, "andi   t0, t0, 1"),
        (c + 0x18, branch(0x04, c + 0x18, c + 0x2C, rs=T0, rt=ZERO), "beq    t0, zero, go   even: cut as the game does"),
        (c + 0x1C, 0x00000000, "nop"),
        (c + 0x20, j(NOT_YET), "j      0017C81C       not_yet: odd, or not past 6.0"),
        (c + 0x24, lui_t7, "lui    t7, 0x37       (copied from 0017C7A0, the displaced delay slot)"),
        (c + 0x28, 0x00000000, "nop"),
        (c + 0x2C, j(GO), "j      0017C7A4       go"),
        (c + 0x30, lui_t7, "lui    t7, 0x37       (copied from 0017C7A0)"),
        (HOOK, j(CAVE), f"j      000FE040       (was {compare:08X} c.olt.s f0, f1)"),
        (HOOK + 4, 0x00000000, f"nop                   (was {EXPECT[0x0017C79C]:08X} bc1f 0017C81C)"),
    ]
    return words


COMMENT = """// 60 FPS - short hop. Derived 2026-09-15 on Sora in Twilight Town, A/B against
// the unpatched game at 30fps in PCSXROO: same state, same input.
//
// A jump is a closed-form arc on a clock (obj+0xD0) that advances by delta, so a
// held jump already matches 30fps. Releasing the button cuts the rise into a short
// apex arc once the clock is past 6.0 (jump controller 0017C690, [0036C518]). At
// 30fps the clock steps 2, 4, 6, 8, so a tap cuts at 8; at 60fps it cuts at 7, one
// unit of rise early: a tap peaked 103.5 instead of 115.1. This lets the cut happen
// only on an even clock - unchanged at 30fps, where the clock is always even.
//
// Hook at 0017C798 into a cave at 000FE040, after the ball physics cave. Nothing
// branches into the displaced words; the delay-slot lui is replayed on both paths."""


def group_lines(words) -> list[str]:
    lines = [f"[{NAME}]", "author=Claude, from the 2026-09-15 PCSXROO A/B investigation",
             "description=Short hops and released jumps rise as high as at 30fps. Needs 60 FPS enabled."]
    for addr, value, text in words:
        lines.append(f"patch=1,EE,{addr:08X},word,{value:08X} // {text}")
    return lines


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()

    words = build(Elf())
    print("decoded:")
    for addr, value, text in words:
        print(f"  {addr:08X}  {value:08X}  {decode(value, addr):<32} // {text}")

    want = [(a & 0x01FFFFFF, v) for a, v, _ in words]
    if args.check:
        bad = 0
        for path in (config.WIP / "working.pnach", config.PATCHES / "kh2fm-60fps.pnach"):
            lines = path.read_text(encoding="utf-8").splitlines()
            if block_range(lines, NAME) is None:
                print(f"{path.name}: no [{NAME}] group")
                continue
            ok = group_words(path, NAME) == want
            print(f"{path.name} [{NAME}]: {'matches' if ok else 'DIFFERS from'} the generated words")
            bad += not ok
        return 1 if bad else 0

    if args.write:
        path = config.WIP / "working.pnach"
        text = path.read_text(encoding="utf-8")
        nl = "\r\n" if "\r\n" in text else "\n"
        lines = text.splitlines()
        remove_block(lines, NAME)
        block = COMMENT.splitlines() + group_lines(words)
        insert_after(lines, "60 FPS - ball physics", block)
        path.write_text(nl.join(normalise_blank_lines(lines)) + nl, encoding="utf-8", newline="")
        print(f"wrote [{NAME}] into {path}")
    else:
        print()
        print(COMMENT)
        print("\n".join(group_lines(words)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
