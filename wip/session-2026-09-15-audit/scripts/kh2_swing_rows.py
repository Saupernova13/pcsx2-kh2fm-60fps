import numpy as np
S = np.load("work/ot-mash-sora.npz"); B = np.load("work/ot-mash-ball.npz")
def fl(z, arm):
    with np.errstate(all="ignore"):
        return z[f"{arm}_block"].view("<f4").astype(np.float64), z[f"{arm}_block"]
offs = [0x540, 0x548, 0x20, 0x28, 0x5A0, 0x5A8, 0x1C, 0x10, 0x18, 0x170]
for arm in ("30", "60w"):
    s, raw = fl(S, arm); b, _ = fl(B, arm)
    print(f"===== arm {arm}")
    print("  v  cls       " + " ".join(f"{('+%03X' % o):>9}" for o in offs) + "   ball x    ball z")
    for v in range(70, 93):
        print(f"  {v:2d} {raw[v, 3]:08X} " + " ".join(f"{s[v, o // 4]:9.3f}" for o in offs)
              + f"  {b[v, 0x540 // 4]:8.2f} {b[v, 0x548 // 4]:9.2f}")
