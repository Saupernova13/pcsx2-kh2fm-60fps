import numpy as np, collections
z = np.load("work/rs-sandlot-idle.npz")
lo = int(z["lo"][0])
def j(kind, ref, cmp):
    ok = z[f"{ref}_ok_{kind}"] & z[f"{cmp}_ok_{kind}"]
    tr = z[f"{ref}_tv_{kind}"].astype(float); tc = z[f"{cmp}_tv_{kind}"].astype(float)
    rr = z[f"{ref}_rev_{kind}"].astype(float); rc = z[f"{cmp}_rev_{kind}"].astype(float)
    with np.errstate(all="ignore"):
        tvr = np.where(tr > 0, tc / tr, np.nan)
    return ok, tr, tc, rr, rc, tvr
for kind, mintv in (("f", 1e-3), ("i", 1)):
    ok, tr, tc, rr, rc, tvr = j(kind, "30", "60")
    _, tr2, tc2, _, rc2, tvr2 = j(kind, "30", "60t2")
    two = ok & (tr > mintv) & (tvr > 1.75) & (tvr < 2.3)
    if kind == "f":
        two |= ok & (tr > mintv) & (rr >= 8) & (rc >= 1.7 * rr) & (tvr > 1.3)
    thr = two & (tvr2 > 0.85) & (tvr2 < 1.2)
    other = two & (tvr2 > 1.6)
    print(f"===== {kind}: strict 2x {int(two.sum())}  threshold-driven {int(thr.sum())}  other {int(other.sum())}")
    for label, mask in (("threshold", thr), ("other", other)):
        idx = np.flatnonzero(mask)
        pages = collections.Counter((lo + 4 * int(i)) >> 16 for i in idx)
        print(f"  {label}: pages " + "  ".join(f"{p << 16:08X}:{n}" for p, n in pages.most_common(10)))
        for i in idx[:40]:
            print(f"    {lo + 4 * int(i):08X}  tv {tr[i]:14.4f} -> {tc[i]:14.4f} ({tvr[i]:.2f})  t2 {tvr2[i]:.2f}  rev {int(rr[i])}->{int(rc[i])}")
