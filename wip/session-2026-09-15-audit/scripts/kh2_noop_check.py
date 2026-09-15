import numpy as np
for k in ("aircombo", "tapjump", "groundcombo"):
    z = np.load(f"work/ot-noop-{k}.npz")
    a, b = z["30_block"], z["30w_block"]
    with np.errstate(all="ignore"):
        fa, fb = a.view("<f4").astype(np.float64), b.view("<f4").astype(np.float64)
    pos = slice(0x540 // 4, 0x54C // 4)
    dpos = np.nanmax(np.abs(fa[:, pos] - fb[:, pos]))
    vel = slice(0x20 // 4, 0x2C // 4)
    dvel = np.nanmax(np.abs(fa[:, vel] - fb[:, vel]))
    words = int(np.sum(a != b))
    print(f"{k:12s} 30fps vs 30fps+groups: max |position diff| {dpos:.6f}  max |velocity diff| {dvel:.6f}  differing words {words}")
