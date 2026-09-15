import numpy as np
z = np.load("work/jump-sora.npz")
r, p = z["ref"], z["plain"]
hr, hp = r[0, 1] - r[:, 1], p[0, 1] - p[:, 1]
print("vsync  h30      h60      d30/vsync  d60/vsync   x30      x60      z30       z60")
for t in range(0, 50):
    d30 = hr[t] - hr[t - 1] if t else 0
    d60 = hp[t] - hp[t - 1] if t else 0
    print(f"{t:4d}  {hr[t]:7.2f}  {hp[t]:7.2f}  {d30:8.3f}  {d60:8.3f}   {r[t,0]:8.2f} {p[t,0]:8.2f} {r[t,2]:9.2f} {p[t,2]:9.2f}")
