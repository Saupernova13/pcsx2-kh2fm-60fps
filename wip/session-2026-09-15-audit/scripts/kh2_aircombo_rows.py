import numpy as np
z = np.load("work/ot-aircombo.npz")
offs = [0x540, 0x20, 0x5A0, 0x850, 0x860, 0x8A4, 0xBD0, 0xBE0, 0xBF0, 0x170]
for arm in ("30", "60"):
    b = z[f"{arm}_block"]
    with np.errstate(all="ignore"):
        f = b.view("<f4").astype(np.float64)
    i = b.view("<i4")
    t = z[f"{arm}_ticks"]
    print(f"===== arm {arm}")
    print("  v tick      " + " ".join(f"{('+%03X' % o):>9}" for o in offs) + "   dx/vsync")
    for v in range(18, 72):
        dx = f[v, 0x540 // 4] - f[v - 1, 0x540 // 4]
        cells = []
        for o in offs:
            if o == 0x170:
                cells.append(f"{int(i[v, o // 4]):9d}")
            else:
                cells.append(f"{f[v, o // 4]:9.3f}")
        print(f"  {v:2d} {t[v]:4d}  " + " ".join(cells) + f"   {dx:8.3f}")
