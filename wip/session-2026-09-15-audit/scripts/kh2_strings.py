import sys
sys.path.insert(0, "tools")
import _bootstrap
from game.elf import Elf
e = Elf()
def cstr(a, n=120):
    out = bytearray()
    for i in range(n):
        b = e.word(a + i - ((a + i) % 4)) >> (8 * ((a + i) % 4)) & 0xFF
        if b == 0:
            break
        out.append(b)
    return out.decode("latin-1")
for a in (0x0036E978, 0x0036E998, 0x0036E9C0, 0x0036E9D0, 0x0036EF58, 0x0036EF88, 0x0036EF98, 0x0036EFC8):
    print(f"{a:08X}  {cstr(a)!r}")
