import sys, struct
sys.path.insert(0, "tools")
import _bootstrap
from game import sandlot, timing
roo = sandlot.connect()
arms = {
    "30": timing.STOCK,
    "60": timing.PATCHED,
    "60t2": {**timing.PATCHED, timing.ACCUM_THRESHOLD: timing.STOCK[timing.ACCUM_THRESHOLD]},
}
for name, words in arms.items():
    if not roo.paused():
        roo.pause()
    roo.loadstate(sandlot.SLOT)
    if not roo.paused():
        roo.pause()
    for a, v in words.items():
        assert roo.write(a, v), hex(a)
    roo.frame_advance(2)
    t0 = roo.read(timing.TICKS)
    roo.frame_advance(20)
    t = roo.read(timing.TICKS) - t0
    vals = " ".join(f"{a:08X}={roo.read(a):08X}" for a in words)
    print(f"arm {name:5s} ticks per 20 vsyncs {t:3d}   {vals}")
