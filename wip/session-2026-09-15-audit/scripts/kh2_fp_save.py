import sys
sys.path.insert(0, "tools")
import numpy as np
import _bootstrap
import ratediff
from game import sandlot
roo = sandlot.connect()
snaps = {}
def run(tag, walk):
    ratediff.start_arm(roo, "60", 1)
    roo.frame_advance(10)
    snaps[tag + "0"] = ratediff.snapshot(roo)
    if walk: roo.input_set("LLeft", "LDown")
    roo.frame_advance(40)
    snaps[tag + "1"] = ratediff.snapshot(roo)
    if walk: roo.input_set("LRight", "LUp")
    roo.frame_advance(40); roo.input_release()
    snaps[tag + "2"] = ratediff.snapshot(roo)
    roo.frame_advance(20)
    snaps[tag + "3"] = ratediff.snapshot(roo)
run("w", True)
run("i", False)
np.savez_compressed("work/fp-walk.npz", lo=np.array([ratediff.LO]), **snaps)
print("saved")
z = snaps
f = {k: v.view("<f4").astype(np.float64) for k, v in z.items()}
w0, w1, w2, w3 = f["w0"], f["w1"], f["w2"], f["w3"]
i0, i2, i3 = f["i0"], f["i2"], f["i3"]
with np.errstate(all="ignore"):
    sane = np.ones(w0.size, bool)
    for s in (w0, w1, w2, w3, i0, i2, i3):
        sane &= np.isfinite(s) & (np.abs(s) < 2e4)
    d1, d2, d3 = w1 - w0, w2 - w1, w3 - w2
    idle = np.maximum(np.abs(i2 - i0), np.abs(i3 - i2))
st = {}
m = sane; st["sane"] = m.sum()
m = m & (np.abs(d1) >= 15) & (np.abs(d1) <= 2000); st["moved there 15..2000"] = m.sum()
m = m & (np.abs(d2) >= 15) & (np.sign(d1) != np.sign(d2)); st["and back, reversed"] = m.sum()
m2 = m & (idle < 5); st["idle drift < 5"] = m2.sum()
m3 = m2 & (np.abs(d3) < 10); st["settle < 10"] = m3.sum()
raw = z["w2"]; one = raw == 0x3F800000
near = np.zeros(one.size, bool)
for k in (1, 2, 3): near[:-k] |= one[k:]
m4 = m3 & near; st["w=1.0 within 12 bytes"] = m4.sum()
for k, v in st.items(): print(f"  {k:28s} {int(v)}")
lo = ratediff.LO
for i in np.flatnonzero(m3)[:40]:
    ctx = " ".join(f"{x:9.2f}" for x in w2[i - 2:i + 4])
    print(f"  {lo + 4 * int(i):08X}  w0 {w0[i]:9.2f} d1 {d1[i]:8.2f} d2 {d2[i]:8.2f} d3 {d3[i]:6.2f} idle {idle[i]:6.2f} w1? {bool(near[i])}  ctx(-2..+3) {ctx}")
