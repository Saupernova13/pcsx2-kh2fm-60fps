import sys, struct
sys.path.insert(0, "tools")
import _bootstrap
from game.elf import Elf
e = Elf()
for a in range(0x0036C500, 0x0036C560, 4):
    w = e.word(a)
    print(f"  {a:08X}  {w:08X}  {struct.unpack('<f', struct.pack('<I', w))[0]:12.6f}")
