"""Generate [60 FPS - friction]: the shared velocity blend and friction step at real-time rate. Offline.

    python tools/mkfrictionfix.py            # print the group with a decoded listing
    python tools/mkfrictionfix.py --write    # write or replace the group in wip/working.pnach
    python tools/mkfrictionfix.py --check    # wip/working.pnach (and patch/, if it has it) agree

00184540 is the game's shared velocity step, called from 19 places - Sora on
the ground (0017C2B8) and in the air (0017C8AC), and 17 not yet identified (listed
in docs/addresses.md). Once per frame, with no delta:

    with movement input (speed at obj+0x1C):
        velocity = velocity * k1 + (facing obj+0x10 * speed) * (1 - k1)     f12 -> f20
    without:
        velocity = velocity * k2                                            f13 -> f21
    displacement = velocity * delta

At 30fps that runs 30 times a real second, at 60fps 60: friction bleeds speed
off twice as fast (Sora's air-combo lunge travelled 131.4 instead of 195.0) and
the blend reaches its target twice as fast (a ground combo travelled 286.6
instead of 244.5).

The fix takes k1 and k2 to the power delta/2 - the square root at 60fps - which
is the same decay per real second. The blend's resting value is the target itself,
so top speeds cannot change. It is phase-free, which matters with 19 callers that
set velocities at arbitrary moments; the ball's integrator used a tick gate
instead, because its update also adds gravity. Factors <= 0 are left alone.

Hook 00184558 (mov.s f20, f12) -> cave 000FE080; the delay slot keeps the game's
sd s1. f0 holds zero there (00184544) and t0 is free until 001845D0 sets it.
"""

from __future__ import annotations

import argparse
import sys

import _bootstrap  # noqa: F401

from ps2ee.disasm import decode

from game import config
from game.elf import Elf
from game.pnachtext import block_range, group_words, insert_after, normalise_blank_lines, remove_block

NAME = "60 FPS - friction"
HOOK = 0x00184558
BACK = 0x00184560
CAVE = 0x000FE080
AFTER = "60 FPS - short hop"

EXPECT = {0x00184544: 0x44800000, 0x00184550: 0x46006D46, 0x00184558: 0x46006506, 0x0018455C: 0xFFB10038,
          0x00184560: 0x46006032}


def j(target: int) -> int:
    return 0x08000000 | (target >> 2)


def rel(op_bits: int, pc: int, target: int) -> int:
    return op_bits | (((target - pc - 4) >> 2) & 0xFFFF)


def sqrt(dest: int, src: int) -> int:
    """SQRT.S on the R5900 FPU: fd = sqrt(ft). Standard MIPS reads fs; the PS2 (and PCSX2) read ft.

    The first version of this group put the operand in fs, as MIPS documents it, and
    so took the square root of f0 - which is zero at the hook - and zeroed every
    friction factor: Sora's air lunge vanished. Capstone decodes these words with the
    standard layout, as "sqrt.s $fN, $f0", so the listing below is misleading for them;
    the game's own SQRT words (0017C4B8, 46000004) use f0 in both fields and hide it.
    """
    return 0x46000000 | (src << 16) | (dest << 6) | 0x04


def build(elf: Elf) -> list[tuple[int, int, str]]:
    for addr, want in EXPECT.items():
        got = elf.word(addr)
        if got != want:
            raise SystemExit(f"ELF word at {addr:08X} is {got:08X}, expected {want:08X} - wrong build?")
    c = CAVE
    back = c + 0x34
    return [
        (c + 0x00, elf.word(HOOK), "mov.s  f20, f12       (copied from 00184558)"),
        (c + 0x04, 0x3C080035, "lui    t0, 0x35"),
        (c + 0x08, 0x8D089E1C, "lw     t0, -0x61E4(t0) [00349E1C] vsync wait: 0 = 60fps"),
        (c + 0x0C, rel(0x15000000, c + 0x0C, back), "bnez   t0, back       30fps: unchanged"),
        (c + 0x10, 0x00000000, "nop"),
        (c + 0x14, 0x4600A036, "c.le.s f20, f0        f0 is zero here"),
        (c + 0x18, rel(0x45010000, c + 0x18, c + 0x24), "bc1t   skip           k1 <= 0: leave it"),
        (c + 0x1C, 0x00000000, "nop"),
        (c + 0x20, sqrt(20, 20), "sqrt   f20 <- f20     k1 per 60 Hz frame (R5900: operand in ft)"),
        (c + 0x24, 0x4600A836, "c.le.s f21, f0        skip:"),
        (c + 0x28, rel(0x45010000, c + 0x28, back), "bc1t   back           k2 <= 0: leave it"),
        (c + 0x2C, 0x00000000, "nop"),
        (c + 0x30, sqrt(21, 21), "sqrt   f21 <- f21     k2 per 60 Hz frame (R5900: operand in ft)"),
        (c + 0x34, j(BACK), "j      00184560       back:"),
        (c + 0x38, 0x00000000, "nop"),
        (HOOK, j(CAVE), f"j      000FE080       (was {elf.word(HOOK):08X} mov.s f20, f12; delay slot keeps sd s1)"),
    ]


COMMENT = """// 60 FPS - friction. Derived 2026-09-15 on Sora in Twilight Town, A/B against the
// unpatched game at 30fps in PCSXROO: same state, same input.
//
// 00184540 is the shared velocity step behind 19 motion routines (Sora on the
// ground and in the air, objects, enemies). Once per frame, with no delta, it
// blends velocity toward the input target by k1 or decays it by k2, then moves by
// velocity * delta. At 60fps both ran twice per real second: an air-combo lunge
// travelled 131.4 instead of 195.0, a ground combo 286.6 instead of 244.5.
//
// Fix: at 60fps use sqrt(k1) and sqrt(k2) - the same decay per real second. The
// blend settles on the target itself, so top speeds are unchanged; nothing
// depends on tick phase. Unchanged at 30fps.
//
// Hook at 00184558 into a cave at 000FE080, after the short hop cave."""


def group_lines(words) -> list[str]:
    lines = [f"[{NAME}]", "author=Claude, from the 2026-09-15 PCSXROO A/B investigation",
             "description=Friction, lunges and acceleration at real speed for every object that uses the shared velocity step. Needs 60 FPS enabled."]
    lines += [f"patch=1,EE,{a:08X},word,{v:08X} // {t}" for a, v, t in words]
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
        insert_after(lines, AFTER, COMMENT.splitlines() + group_lines(words))
        path.write_text(nl.join(normalise_blank_lines(lines)) + nl, encoding="utf-8", newline="")
        print(f"wrote [{NAME}] into {path}")
    else:
        print()
        print(COMMENT)
        print("\n".join(group_lines(words)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
