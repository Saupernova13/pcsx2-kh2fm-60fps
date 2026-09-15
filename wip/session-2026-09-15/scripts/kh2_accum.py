"""Scope the fixed-step accumulator at 001E63F0 and the delta-time globals."""
import struct
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path.home() / "Documents" / "GitHub" / "pcsxroo" / "pcsxroo"))

from ps2ee.disasm import decode
from ps2ee.savestate import SaveState

STATE = r"%USERPROFILE%\AppData\Roaming\EmuDeck\Emulators\PCSX2-Qt\sstates\SLPM-66675 (FAF99301).01.p2s"
TEXT = (0x00100000, 0x00340000)
MEMOPS = {0x23, 0x20, 0x24, 0x21, 0x25, 0x2B, 0x28, 0x29, 0x31, 0x39, 0x37, 0x3F, 0x09}

with SaveState(STATE) as s:
    ee = s.ee

def word(a):
    return struct.unpack_from("<I", ee, a)[0]

def f32(a):
    return struct.unpack_from("<f", ee, a)[0]

def dump(lo, hi):
    print(f"---- {lo:08X}..{hi:08X}")
    for a in range(lo, hi, 4):
        w = word(a)
        print(f"{a:08X}  {w:08X}  {decode(w, a)}")

# function start: walk back to the previous `jr ra` + delay slot
def func_start(addr):
    a = addr
    while a > TEXT[0]:
        if word(a - 8) == 0x03E00008:
            return a
        a -= 4
    return None

start = func_start(0x001E63F0)
print(f"accumulator function starts at {start:08X}")
dump(start, start + 0x40)
dump(0x001E6300, 0x001E63E0)
dump(0x001E64B0, 0x001E6620)

# callers (jal) of that function
jal = 0x0C000000 | (start >> 2)
callers = [a for a in range(TEXT[0], TEXT[1], 4) if word(a) == jal]
print(f"jal callers of {start:08X}: {[f'{c:08X}' for c in callers]}")
# stored as a function pointer (vtable) anywhere in RAM
ptrs = [a for a in range(0x00100000, 0x01E00000, 4) if word(a) == start]
print(f"pointer copies of {start:08X}: {[f'{p:08X}' for p in ptrs[:20]]}")

# lui-based references to the globals
targets = {0x00352BE0: [], 0x00349E10: [], 0x00349E14: [], 0x00349E18: [], 0x00349E0C: []}
for a in range(TEXT[0], TEXT[1], 4):
    w = word(a)
    if (w >> 26) != 0x0F:
        continue
    rt = (w >> 16) & 0x1F
    hi = w & 0xFFFF
    for k in range(1, 12):
        b = a + 4 * k
        v = word(b)
        op = v >> 26
        if op in MEMOPS and ((v >> 21) & 0x1F) == rt:
            imm = v & 0xFFFF
            if imm & 0x8000:
                imm -= 0x10000
            ea = ((hi << 16) + imm) & 0xFFFFFFFF
            if ea in targets:
                targets[ea].append((b, v))
        if op == 0x0F and ((v >> 16) & 0x1F) == rt:
            break

for t, uses in targets.items():
    kinds = Counter(decode(v, b).split()[0] for b, v in uses)
    print(f"== {t:08X} value now {f32(t):.4f}  {len(uses)} refs  {dict(kinds)}")
    if t == 0x00352BE0 or len(uses) <= 12:
        for b, v in uses:
            print(f"   {b:08X}  {decode(v, b)}")
