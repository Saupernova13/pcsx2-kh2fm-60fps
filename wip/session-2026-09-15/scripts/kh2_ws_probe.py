import sys
from pathlib import Path

sys.path.insert(0, str(Path.home() / "Documents" / "GitHub" / "pcsxroo" / "pcsxroo"))

from ps2ee.pine import Pine
from ps2ee.disasm import decode

start, end = 0x00106D40, 0x00106F00
with Pine(port=28011).connect() as p:
    print("status ", p.status())
    print("title  ", p.title())
    print("game_id", p.game_id())
    words = p.read_block(start, (end - start) // 4)
    for i, w in enumerate(words):
        a = start + i * 4
        print(f"{a:08X}  {w:08X}  {decode(w, a)}")
    for a in (0x2036A0B8, 0x2036A0BC, 0x2036CE94):
        print(f"{a & 0x0FFFFFFF:08X}  {p.read(a & 0x01FFFFFF):08X}")
