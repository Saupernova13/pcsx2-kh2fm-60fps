import sys
sys.path.insert(0, "tools")
import _bootstrap
import ratediff
from game import sandlot
roo = sandlot.connect()
OBJ = 0x01A94440
ratediff.start_arm(roo, "60", 1)
roo.frame_advance(6)
roo.input_set("Circle"); roo.frame_advance(6); roo.input_release()
roo.frame_advance(5)   # vsync 17: two frames before the switch
roo.mc_clear()
roo.mc_add(OBJ + 0xD4, OBJ + 0xD8, on=("write",))
seen = {}
try:
    for _ in range(12):
        seq = roo.seq(); roo.resume(); st = roo.wait(seq, timeout_ms=4000)
        if st is None:
            print("no more hits"); break
        r = roo.regs("GPR")
        key = (st.pc, r.get("ra"))
        if key not in seen:
            seen[key] = r
            print(f"hit pc {st.pc:08X} ra {r.get('ra'):08X} a0 {r.get('a0'):08X} s0 {r.get('s0'):08X} s1 {r.get('s1'):08X} val {roo.read(OBJ + 0xD4):08X}")
finally:
    roo.mc_clear()
    if not roo.paused():
        roo.pause()
for (pc, ra) in seen:
    print(f"==== around pc {pc:08X}")
    for a, text in roo.dis(pc - 80, 36):
        print(f"  {'->' if a == pc else '  '} {a:08X}  {text}")
