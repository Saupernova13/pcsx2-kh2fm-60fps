import numpy as np
z = np.load("work/ot-aircombo-fix.npz")
offs = [0x540, 0x544, 0x20, 0x28, 0x1C, 0x10, 0x18, 0x170, 0xD0, 0xD4]
for arm in ("30", "60", "60w"):
    b = z[f"{arm}_block"]
    with np.errstate(all="ignore"):
        f = b.view("<f4").astype(np.float64)
    print(f"===== arm {arm}")
    print("  v  cls       " + " ".join(f"{('+%03X' % o):>9}" for o in offs))
    for v in range(12, 70, 1 if arm != "30" else 2):
        print(f"  {v:2d} {b[v, 3]:08X} " + " ".join(f"{f[v, o // 4]:9.3f}" for o in offs))
