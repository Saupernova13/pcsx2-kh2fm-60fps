import sys, struct
sys.path.insert(0, "tools")
import _bootstrap
import ratediff
import movetest
from game import config, sandlot
from game.pnachtext import group_words
roo = sandlot.connect()
SORA, BALL = 0x01A94440, 0x01ADD9D0
fix = []
for n in ("60 FPS - ball physics", "60 FPS - short hop", "60 FPS - friction"):
    fix += group_words(config.WIP / "working.pnach", n)
steps = movetest.parse("wait:6,hold:LLeft+LDown:8" + (",tap:Cross,wait:6" * 16))
for arm, words in (("30", []), ("60w", fix)):
    print(f"===== arm {arm}")
    ratediff.start_arm(roo, "30" if arm == "30" else "60", 1)
    sandlot.apply_words(roo, words)
    roo.bp_clear()
    roo.bp_add(0x002E7E48, description="hit handler")
    v = 0
    try:
        for kind, buttons, n in steps:
            if kind == "hold":
                roo.input_set(*buttons)
            for _ in range(n):
                st = roo.frame_advance(1)
                guard = 0
                while st is not None and getattr(st, "reason", "") == "breakpoint" and guard < 8:
                    r = roo.regs("GPR")
                    sp = r["sp"]
                    stack = struct.unpack("<24I", roo.read_bytes(sp, 96))
                    rets = [w for w in stack if 0x00100000 <= w < 0x00340000]
                    clk = struct.unpack("<f", roo.read_bytes(SORA + 0x170, 4))[0]
                    bh = struct.unpack("<f", roo.read_bytes(BALL + 0x544, 4))[0]
                    print(f"  vsync {v:3d} hit: a0 {r['a0']:08X} ra {r['ra']:08X}  sora clock {clk:5.1f}  ball y {bh:7.2f}  stack code ptrs " + " ".join(f"{w:08X}" for w in rets[:8]))
                    st = roo.frame_advance(1)
                    guard += 1
                v += 1
            if kind == "hold":
                roo.input_release()
    finally:
        roo.bp_clear()
        if not roo.paused():
            roo.pause()
