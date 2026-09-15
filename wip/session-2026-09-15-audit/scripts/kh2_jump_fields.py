import numpy as np
z = np.load("work/ot-jump.npz")
offs = [0x20, 0x24, 0x28, 0xD0, 0xD4, 0xD8, 0xDC, 0x120, 0x544]
for arm in ("30", "60"):
    b = z[f"{arm}_block"]
    with np.errstate(all="ignore"):
        f = b.view("<f4").astype(np.float64)
    t = z[f"{arm}_ticks"]
    print(f"===== arm {arm}")
    print("  v  tick  cls       " + " ".join(f"{('+%03X' % o):>10}" for o in offs))
    for v in range(10, 42):
        print(f"  {v:2d} {t[v]:5d}  {b[v, 3]:08X} " + " ".join(f"{f[v, o // 4]:10.3f}" for o in offs))
