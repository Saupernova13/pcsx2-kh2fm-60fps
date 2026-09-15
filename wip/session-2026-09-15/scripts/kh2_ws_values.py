import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path.home() / "Documents" / "GitHub" / "pcsxroo" / "pcsxroo"))

from ps2ee.disasm import decode

def f2h(x):
    return struct.unpack(">I", struct.pack(">f", x))[0]

def h2f(h):
    return struct.unpack(">f", struct.pack(">I", h))[0]

widen = (4 / 3) / (19.5 / 9)
h = f2h(widen)
print(f"factor {widen:.9f} -> {h:08X} -> {h2f(h):.9f}")
print(f"16:9 check {f2h((4/3)/(16/9)):08X}  0.8 = {h2f(0x3F4CCCCC):.7f}")
hi, lo = h >> 16, h & 0xFFFF
words = {
    0x00106E54: 0x3C1B0000 | hi,   # lui  $k1, hi
    0x00106E58: 0x377B0000 | lo,   # ori  $k1, $k1, lo
    0x00106E60: 0x449BF000,        # mtc1 $k1, $f30
}
for a, w in words.items():
    print(f"{a:08X}  {w:08X}  {decode(w, a)}")
