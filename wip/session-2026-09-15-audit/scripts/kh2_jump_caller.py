import sys, struct
sys.path.insert(0, "tools")
import _bootstrap
import ratediff
from game import sandlot
roo = sandlot.connect()
OBJ = 0x01A94440
ratediff.start_arm(roo, "60", 1)
roo.frame_advance(6)
roo.input_set("Circle"); roo.frame_advance(6); roo.input_release()
roo.frame_advance(5)
roo.mc_clear()
roo.mc_add(OBJ + 0xD4, OBJ + 0xD8, on=("write",))
try:
    seq = roo.seq(); roo.resume(); st = roo.wait(seq, timeout_ms=4000)
    r = roo.regs("GPR")
    sp = r["sp"]
    print(f"stop pc {st.pc:08X} sp {sp:08X} f-args: a0 {r['a0']:08X}")
    words = struct.unpack("<16I", roo.read_bytes(sp, 64))
    print("stack: " + " ".join(f"{w:08X}" for w in words))
    saved_ra = words[2]
    print(f"saved ra (caller of 0017C42C) {saved_ra:08X}")
    fr = roo.read_bytes(0x01A94440 + 0xC0, 0x28)
    print("obj +C0..+E4 floats: " + " ".join(f"{v:.3f}" for v in struct.unpack("<10f", fr)))
    for a, text in roo.dis(saved_ra - 160, 60):
        print(f"  {'->' if a == saved_ra else '  '} {a:08X}  {text}")
finally:
    roo.mc_clear()
    if not roo.paused():
        roo.pause()
