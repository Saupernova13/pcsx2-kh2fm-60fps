import sys, struct
sys.path.insert(0, "tools")
import numpy as np
import _bootstrap
import ratediff
from game import sandlot, config
roo = sandlot.connect()
def fl():
    raw = ratediff.snapshot(roo)
    with np.errstate(all="ignore"):
        return raw.view("<f4").astype(np.float64), raw
LO = ratediff.LO
ratediff.start_arm(roo, "60", 1)
roo.frame_advance(10)
s0, raw0 = fl()
roo.input_set("LLeft", "LDown"); roo.frame_advance(40)
s1, _ = fl()
sandlot.shot(roo, "fp-after-there.png")
roo.input_set("LRight", "LUp"); roo.frame_advance(40); roo.input_release()
s2, _ = fl()
roo.frame_advance(20)
s3, _ = fl()
sandlot.shot(roo, "fp-after-back.png")
with np.errstate(all="ignore"):
    ok = np.isfinite(s0) & np.isfinite(s1) & np.isfinite(s2) & (np.abs(s0) < 1e5) & (np.abs(s1) < 1e5) & (np.abs(s2) < 1e5)
    d1 = np.where(ok, s1 - s0, 0); d2 = np.where(ok, s2 - s1, 0); d3 = np.where(ok, s3 - s2, 0)
for name, d in (("there", d1), ("back", d2), ("settle", d3)):
    big = np.flatnonzero(np.abs(d) > 15)
    print(f"{name}: {big.size} floats moved > 15")
rev = np.flatnonzero((np.abs(d1) > 15) & (np.abs(d2) > 15) & (np.sign(d1) != np.sign(d2)))
print(f"reversed: {rev.size}")
order = np.argsort(-np.abs(d1))
shown = 0
for i in order:
    if abs(d1[i]) <= 15 or not ok[i]:
        continue
    a = LO + 4 * int(i)
    ctx = " ".join(f"{v:9.2f}" for v in s1[i - 1:i + 4])
    print(f"  {a:08X}  s0 {s0[i]:10.2f}  d_there {d1[i]:9.2f}  d_back {d2[i]:9.2f}  d_settle {d3[i]:8.2f}   ctx(-1..+3) {ctx}")
    shown += 1
    if shown >= 40:
        break
