import sys, struct
sys.path.insert(0, "tools")
import _bootstrap
import ratediff
from game import config, sandlot
from game.pnachtext import group_words
roo = sandlot.connect()
OBJ = 0x01A94440
fix = group_words(config.WIP / "working.pnach", "60 FPS - friction")
def f(bits):
    return struct.unpack("<f", struct.pack("<I", bits & 0xFFFFFFFF))[0]
for label, words in (("60 plain", []), ("60 + friction", fix)):
    print(f"===== {label}")
    ratediff.start_arm(roo, "60", 1)
    sandlot.apply_words(roo, words)
    roo.frame_advance(6)
    roo.input_set("Circle"); roo.frame_advance(14); roo.input_release()
    roo.frame_advance(4)
    roo.input_set("Cross"); roo.frame_advance(2); roo.input_release()
    roo.frame_advance(1)
    roo.bp_clear()
    roo.bp_add(0x00184560, condition="a1 == 0x01A94440", description="friction step for Sora")
    try:
        for k in range(6):
            seq = roo.seq(); roo.resume(); st = roo.wait(seq, timeout_ms=4000)
            if st is None:
                print("  no stop"); break
            fp = roo.regs("FPR")
            v = struct.unpack("<3f", roo.read_bytes(OBJ + 0x20, 12))
            spd = struct.unpack("<f", roo.read_bytes(OBJ + 0x1C, 4))[0]
            names = {n.lower(): val for n, val in fp.items()}
            def g(n):
                for key in (n, n.replace("f", "fpr"), "f" + n[1:].zfill(2)):
                    if key in names:
                        return f(names[key])
                return float("nan")
            print(f"  stop {k}: pc {st.pc:08X}  f12 {g('f12'):.4f} f13 {g('f13'):.4f} f20 {g('f20'):.4f} f21 {g('f21'):.4f}  "
                  f"vel ({v[0]:.3f},{v[1]:.3f},{v[2]:.3f}) speed {spd:.3f}")
            if k == 0:
                print("  FPR names: " + ", ".join(list(fp)[:8]))
    finally:
        roo.bp_clear()
        if not roo.paused():
            roo.pause()
