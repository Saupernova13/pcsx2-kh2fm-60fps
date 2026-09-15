"""Find code in a KH2 save state's EE RAM that references given data addresses.

Scans for `lui rX, hi` followed (within a window) by a load/store or addiu
through rX whose effective address equals a target.
"""
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path.home() / "Documents" / "GitHub" / "pcsxroo" / "pcsxroo"))

from ps2ee.disasm import decode
from ps2ee.savestate import SaveState

STATE = r"%USERPROFILE%\AppData\Roaming\EmuDeck\Emulators\PCSX2-Qt\sstates\SLPM-66675 (FAF99301).01.p2s"
TARGETS = [0x00349E1C, 0x0032BA24, 0x0036B0F4, 0x0036B0F8, 0x0036EF20]
TEXT = (0x00100000, 0x00340000)
WINDOW = 12

# opcodes that use base+imm: lw, lb, lbu, lh, lhu, sw, sb, sh, lwc1, swc1, ld, sd, addiu
MEMOPS = {0x23, 0x20, 0x24, 0x21, 0x25, 0x2B, 0x28, 0x29, 0x31, 0x39, 0x37, 0x3F, 0x09}

with SaveState(STATE) as s:
    ee = s.ee

def word(a):
    return struct.unpack_from("<I", ee, a)[0]

hits = {t: [] for t in TARGETS}
for a in range(TEXT[0], TEXT[1], 4):
    w = word(a)
    if (w >> 26) != 0x0F:
        continue
    rt = (w >> 16) & 0x1F
    hi = w & 0xFFFF
    for k in range(1, WINDOW):
        b = a + 4 * k
        v = word(b)
        op = v >> 26
        base = (v >> 21) & 0x1F
        if op in MEMOPS and base == rt:
            imm = v & 0xFFFF
            if imm & 0x8000:
                imm -= 0x10000
            ea = ((hi << 16) + imm) & 0xFFFFFFFF
            if ea in hits:
                hits[ea].append((a, b, v))
        # stop if rt gets overwritten by something other than this use
        if op == 0x0F and ((v >> 16) & 0x1F) == rt:
            break

for t in TARGETS:
    print(f"== {t:08X}  {len(hits[t])} refs")
    for a, b, v in hits[t]:
        print(f"   lui@{a:08X}  use@{b:08X}  {decode(v, b)}")
