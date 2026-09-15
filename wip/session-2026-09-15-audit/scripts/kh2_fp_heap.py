import numpy as np, collections
z = np.load("work/fp-walk.npz")
lo = int(z["lo"][0])
raw = {k: z[k] for k in ("w0", "w1", "w2", "w3", "i0", "i2", "i3")}
with np.errstate(all="ignore"):
    f = {k: v.view("<f4").astype(np.float64) for k, v in raw.items()}
n = f["w0"].size
# vec4 base b: words b,b+1,b+2 = x,y,z and b+3 = 1.0 in w2
one = raw["w2"] == 0x3F800000
bases = np.flatnonzero(one) - 3
bases = bases[(bases >= 0)]
rows = []
for b in bases:
    x0, y0, z0 = f["w0"][b:b + 3]
    x1, y1, z1 = f["w1"][b:b + 3]
    x2, y2, z2 = f["w2"][b:b + 3]
    ix, iy, iz = f["i2"][b:b + 3] - f["i0"][b:b + 3]
    vals = np.array([x0, y0, z0, x1, y1, z1, x2, y2, z2])
    if not np.all(np.isfinite(vals)) or np.any(np.abs(vals) > 2e4):
        continue
    dxz1 = np.hypot(x1 - x0, z1 - z0)
    dxz2 = np.hypot(x2 - x1, z2 - z1)
    if dxz1 < 15 or dxz2 < 15 or dxz1 > 2000:
        continue
    if abs(y0 - 550) > 60:
        continue
    if max(abs(ix), abs(iz)) > 5:
        continue
    rows.append((b, (round(x2, 1), round(y2, 1), round(z2, 1)), dxz1, dxz2, x1 - x0, z1 - z0))
print(f"{len(rows)} vec4s near ground height that walked there and back and hold still idle")
groups = collections.defaultdict(list)
for r in rows:
    groups[r[1]].append(r)
for key, g in sorted(groups.items(), key=lambda kv: -len(kv[1])):
    addrs = " ".join(f"{lo + 4 * r[0]:08X}" for r in g[:12])
    r = g[0]
    print(f"  pos {key}  moved {r[2]:.1f} there, {r[3]:.1f} back (dx {r[4]:.1f} dz {r[5]:.1f})  x{len(g)}: {addrs}")
