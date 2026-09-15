"""Generate the two ball-physics fix candidates from first principles, and check them.

    python tools/mkballfix.py            # print both groups with a decoded listing
    python tools/mkballfix.py --write    # rewrite wip/experiments/001-ball-physics-candidates.pnach
    python tools/mkballfix.py --check    # both groups agree with patch/ and wip/working.pnach

FIX-D (shipped as [60 FPS - ball physics]) gates the airborne motion routine's
per-tick velocity block, 002EA49C..002EA570, to every other game tick while
[60 FPS] is active. FIX-B (withdrawn) scales the per-tick constants instead.

Every branch is hand-encoded and decoded back. The three instructions the hook
displaces are copied from the unpatched ELF, not typed in: capstone cannot
decode lq/sq (it shows them as MSA ops), so they are the one place a typo would
go unnoticed.
"""

from __future__ import annotations

import argparse
import sys

import _bootstrap  # noqa: F401

from game import config, physics, timing
from game.elf import Elf, from_f32
from game.pnachtext import block_range, patch_words
from ps2ee.disasm import decode

ZERO, T0, T1, S2, S6, SP = 0, 8, 9, 18, 22, 29
NOP = 0


def j(target: int) -> int:
    return 0x08000000 | ((target >> 2) & 0x03FFFFFF)


def beq(pc: int, rs: int, rt: int, target: int) -> int:
    return 0x10000000 | rs << 21 | rt << 16 | (((target - pc - 4) >> 2) & 0xFFFF)


def bne(pc: int, rs: int, rt: int, target: int) -> int:
    return 0x14000000 | rs << 21 | rt << 16 | (((target - pc - 4) >> 2) & 0xFFFF)


def lui(rt: int, imm: int) -> int:
    return 0x3C000000 | rt << 16 | (imm & 0xFFFF)


def lw(rt: int, imm: int, rs: int) -> int:
    return 0x8C000000 | rs << 21 | rt << 16 | (imm & 0xFFFF)


def andi(rt: int, rs: int, imm: int) -> int:
    return 0x30000000 | rs << 21 | rt << 16 | (imm & 0xFFFF)


def split_hi_lo(addr: int) -> tuple[int, int]:
    lo = addr & 0xFFFF
    hi = (addr >> 16) + (1 if lo & 0x8000 else 0)
    return hi & 0xFFFF, lo - 0x10000 if lo & 0x8000 else lo


def fix_d(elf: Elf) -> list[tuple[int, int, str]]:
    cave = physics.CAVE
    words: list[tuple[int, int, str]] = []
    pc = cave

    def emit(word: int, text: str) -> None:
        nonlocal pc
        words.append((pc, word, text))
        pc += 4

    wait_hi, wait_lo = split_hi_lo(timing.VSYNC_WAIT)
    tick_hi, tick_lo = split_hi_lo(timing.TICKS)
    update = cave + 0x28
    emit(lui(T0, wait_hi), f"lui  t0, 0x{wait_hi:X}")
    emit(lw(T0, wait_lo, T0), f"lw   t0, {wait_lo:#x}(t0)     [{timing.VSYNC_WAIT:08X}] extra vsync wait: 0 = 60fps")
    emit(bne(pc, T0, ZERO, update), "bnez t0, update          30fps: never gate")
    emit(lui(T1, tick_hi), f"lui  t1, 0x{tick_hi:X}")
    emit(lw(T1, tick_lo, T1), f"lw   t1, {tick_lo:#x}(t1)     [{timing.TICKS:08X}] game tick counter")
    emit(andi(T1, T1, 1), "andi t1, t1, 1")
    emit(beq(pc, T1, ZERO, update), "beqz t1, update          even tick: update as normal")
    emit(NOP, "nop")
    emit(j(physics.SKIP_TO), f"j    {physics.SKIP_TO:08X}            odd tick: keep last velocity")
    emit(NOP, "nop")
    assert pc == update
    after_copy = update + 0x10
    emit(beq(pc, SP, S6, after_copy), "beq  sp, s6, L1          replay the overwritten beql")
    emit(NOP, "nop")
    emit(elf.word(physics.HOOK + 0x08), f"lq   t0, 0(s6)            (copied from {physics.HOOK + 0x08:08X})")
    emit(elf.word(physics.HOOK + 0x0C), f"sq   t0, 0(sp)            (copied from {physics.HOOK + 0x0C:08X})")
    assert pc == after_copy
    emit(j(physics.RESUME), f"j    {physics.RESUME:08X}")
    emit(elf.word(physics.HOOK + 0x10), f"sw   zero, 4(sp)          (copied from {physics.HOOK + 0x10:08X})")
    words.append((physics.HOOK, j(cave), f"j    {cave:08X}          (was {elf.word(physics.HOOK):08X} beql sp, s6)"))
    words.append((physics.HOOK + 4, NOP, f"nop                      (was {elf.word(physics.HOOK + 4):08X} sw zero, 4(sp))"))
    return words


def fix_b(elf: Elf) -> list[tuple[int, int, str]]:
    g = elf.f32(physics.GRAVITY)
    return [
        (0x002EA548, 0x46000004, "sqrt.s f00, f00          (was mul.s f00, f03, f00)"),
        (0x002EA54C, 0x460018C2, "mul.s  f03, f03, f00     (was mov.s f03, f00)"),
        (0x002EA550, 0xE6430024, "swc1   f03, 0x24(s2)     (was swc1 f00, 0x24(s2))"),
        (physics.GRAVITY, from_f32(g / 2), f"gravity {g:.6f} -> {g / 2:.6f} (single reader 002EA55C)"),
    ]


def render(name: str, words) -> list[str]:
    return [f"[{name}]"] + [f"patch=1,EE,{a:08X},word,{w:08X} // {t}" for a, w, t in words]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    elf = Elf()
    expected_originals = {physics.HOOK: "beql", physics.HOOK + 0x10: "sw", 0x002EA544: "lwc1", 0x002EA550: "swc1"}
    for addr, mnemonic in expected_originals.items():
        text = decode(elf.word(addr), addr)
        if not text.startswith(mnemonic):
            raise SystemExit(f"ELF word at {addr:08X} is '{text}', expected {mnemonic}: wrong ELF?")

    groups = {"BALLFIX-B constant scaling": fix_b(elf), "BALLFIX-D tick gate": fix_d(elf)}

    if args.check:
        ok = True
        shipped = (config.PATCHES / "kh2fm-60fps.pnach").read_text(encoding="utf-8").splitlines()
        working = (config.WIP / "working.pnach").read_text(encoding="utf-8").splitlines()
        for label, lines, group, words in (
                ("patch/ [60 FPS - ball physics]", shipped, "60 FPS - ball physics", groups["BALLFIX-D tick gate"]),
                ("wip/ [EXPERIMENT ball physics constant scaling]", working,
                 "EXPERIMENT ball physics constant scaling", groups["BALLFIX-B constant scaling"])):
            r = block_range(lines, group)
            have = patch_words(lines[r[0]:r[2]]) if r else None
            want = [(f"{a:08X}", f"{w:08X}") for a, w, _ in words]
            same = have == want
            ok &= same
            print(f"{label}: {'matches' if same else 'DIFFERS'} the generated words")
        return 0 if ok else 1

    out = ["gametitle=Kingdom Hearts II Final Mix + (NTSC-J) SLPM-66675 - ball physics fix candidates (scratch)", ""]
    for name, words in groups.items():
        out += render(name, words) + [""]
        print(f"== {name}")
        for a, w, t in words:
            print(f"  {a:08X}  {w:08X}  {decode(w, a):32s}  // {t}")
    if args.write:
        path = config.WIP / "experiments" / "001-ball-physics-candidates.pnach"
        path.write_text("\n".join(out), encoding="utf-8", newline="\n")
        print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
