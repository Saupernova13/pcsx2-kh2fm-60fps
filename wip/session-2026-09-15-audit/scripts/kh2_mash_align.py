import numpy as np
S = np.load("work/ot-mash-sora.npz"); B = np.load("work/ot-mash-ball.npz")
def fl(z, arm):
    with np.errstate(all="ignore"):
        return z[f"{arm}_block"].view("<f4").astype(np.float64), z[f"{arm}_block"]
s30, s30r = fl(S, "30"); s60, s60r = fl(S, "60w")
b30, _ = fl(B, "30"); b60, _ = fl(B, "60w")
P = 0x540 // 4
def h(b, v): return b[0, P + 1] - b[v, P + 1]
print(" v | ball h30  h60w  vy30   vy60w  vx30   vx60w | sora x30   x60w    y30    y60w   z30     z60w  | clk30 clk60 | D0_30 D0_60 D4_30 D4_60 DC_30  DC_60")
first = None
for v in range(36, 142):
    bh30, bh60 = h(b30, v), h(b60, v)
    sx30, sy30, sz30 = s30[v, P:P + 3]; sx60, sy60, sz60 = s60[v, P:P + 3]
    # sampling-tolerant divergence: 60w at v vs 30 at v or v-1
    d_ball = min(abs(bh60 - h(b30, v)), abs(bh60 - h(b30, v - 1)))
    d_sora = min(np.hypot(sx60 - s30[v, P], sz60 - s30[v, P + 2]), np.hypot(sx60 - s30[v - 1, P], sz60 - s30[v - 1, P + 2]))
    flag = ""
    if first is None and (d_ball > 6 or d_sora > 6):
        first = v; flag = "  <== first divergence"
    if v % 2 == 0 or flag:
        print(f"{v:3d}| {bh30:7.1f} {bh60:7.1f} {b30[v,9]:6.2f} {b60[v,9]:6.2f} {b30[v,8]:6.2f} {b60[v,8]:6.2f} |"
              f" {sx30:7.1f} {sx60:7.1f} {sy30:6.1f} {sy60:6.1f} {sz30:8.1f} {sz60:8.1f} |"
              f" {s30[v,0x170//4]:5.0f} {s60[v,0x170//4]:5.0f} | {s30[v,0xD0//4]:5.0f} {s60[v,0xD0//4]:5.0f} {s30[v,0xD4//4]:5.1f} {s60[v,0xD4//4]:5.1f} {s30[v,0xDC//4]:6.1f} {s60[v,0xDC//4]:6.1f}{flag}")
print("first divergence at vsync", first)
