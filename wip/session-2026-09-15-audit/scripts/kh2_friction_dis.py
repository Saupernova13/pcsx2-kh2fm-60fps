import sys
sys.path.insert(0, "tools")
import _bootstrap
from game import sandlot
roo = sandlot.connect()
if not roo.paused():
    roo.pause()
for a, text in roo.dis(0x00184540, 88):
    print(f"  {a:08X}  {roo.read(a):08X}  {text}")
