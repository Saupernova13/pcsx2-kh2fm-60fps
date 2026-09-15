import sys, struct
sys.path.insert(0, "tools")
import _bootstrap
from game.elf import Elf
from ps2ee.disasm import decode
e = Elf()
for a in range(0x00100000, 0x00340000, 4):
    w = e.word(a)
    if (w >> 26) == 3 and ((w & 0x03FFFFFF) << 2) == 0x001E7008:
        print(f"---- jal at {a:08X}")
        for b in range(a - 40, a + 12, 4):
            print(f"  {b:08X}  {e.word(b):08X}  {decode(e.word(b), b)}")
