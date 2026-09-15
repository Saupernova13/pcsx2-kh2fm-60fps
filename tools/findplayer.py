"""Find the player's position in RAM by walking away and back. PCSXROO, or offline on a saved walk.

    python tools/findplayer.py                                  # Sandlot state: LLeft+LDown 40 vsyncs, then LRight+LUp
    python tools/findplayer.py --there LUp --back LDown --save work/fp-north.npz
    python tools/findplayer.py --load work/fp-walk.npz --all    # re-rank a saved walk, caches too; no emulator

From one save state, in the 60fps arm: idle, hold --there for --vsyncs, hold --back
for as long, let go and settle; then the same from the same state with no input.
RAM (tools/ratediff.py's range) is snapshotted at every step.

A world position is a vec4 whose w reads 1.0. Every such vec4 is a candidate when
its horizontal (x, z) position moved at least --min-step on each leg and drifted no
more than --idle-drift in the idle run; --y keeps only those starting near a known
ground height. Identical positions are grouped - an object keeps copies of its own
position, and caches and render state hold more. A group is reported as an object
when one of its copies sits at +0x540 of a block whose +0x0C holds a known object
class (tools/game/physics.py): that is the object's own position. Objects are
ranked by how far they walked - input moves the player furthest, the party follows
- and --all lists the other positions after them.

2026-09-15, the Twilight Town Sandlot state (work/fp-walk.npz): three objects
walked. 01A94440 moved 304 there and 280 back - Sora, whom the ball notes had taken
for a second prop - with copies of his position at +0x70, +0x5C0, +0x6E0, +0x730
and +0xC40. 01AC2490 (152 / 59) and 01AADB90 (143 / 73) followed: Donald and Goofy.
Among the positions that are not objects, single copies elsewhere walked as far as
Sora, so the class check is what names him. The first version of this tool required
every word to reverse sign on the way back and to hold within 2.0 after release, and
found nothing - Sora walks diagonally, and slides for a few vsyncs after the stick is
let go.
"""

from __future__ import annotations

import argparse
import collections
import sys

import numpy as np

import _bootstrap  # noqa: F401

import ratediff
from game import config, physics, sandlot

ONE = 0x3F800000
KEYS = ("w0", "w1", "w2", "w3", "i0", "i1", "i2", "i3")


def walk(roo, args) -> dict[str, np.ndarray]:
    """Snapshot RAM through the walk, then through an idle run from the same state."""
    snaps: dict[str, np.ndarray] = {}
    for tag, there, back in (("w", args.there.split("+"), args.back.split("+")), ("i", None, None)):
        ratediff.start_arm(roo, args.arm, args.slot)
        roo.frame_advance(args.lead)
        snaps[tag + "0"] = ratediff.snapshot(roo)
        if there:
            roo.input_set(*there)
        roo.frame_advance(args.vsyncs)
        snaps[tag + "1"] = ratediff.snapshot(roo)
        if back:
            roo.input_set(*back)
        roo.frame_advance(args.vsyncs)
        roo.input_release()
        snaps[tag + "2"] = ratediff.snapshot(roo)
        roo.frame_advance(args.settle)
        snaps[tag + "3"] = ratediff.snapshot(roo)
        print(f"  {'walk' if there else 'idle'} run captured")
    return snaps


def positions(snaps: dict[str, np.ndarray], key: str, bases: np.ndarray) -> np.ndarray:
    with np.errstate(all="ignore"):
        f = snaps[key].view("<f4").astype(np.float64)
    return np.stack([f[bases + j] for j in range(3)], axis=1)


def candidates(snaps: dict[str, np.ndarray], args) -> tuple[int, list]:
    """Every vec4 with w = 1.0 that walked there and back and holds still idle, grouped by position."""
    bases = np.flatnonzero(snaps["w2"] == ONE) - 3
    bases = bases[bases >= 0]
    p0, p1, p2, q0, q2 = (positions(snaps, k, bases) for k in ("w0", "w1", "w2", "i0", "i2"))
    with np.errstate(all="ignore"):
        walked = np.concatenate([p0, p1, p2], axis=1)
        keep = np.all(np.isfinite(walked), axis=1) & np.all(np.abs(walked) <= 2e4, axis=1)
        there = np.hypot(p1[:, 0] - p0[:, 0], p1[:, 2] - p0[:, 2])
        back = np.hypot(p2[:, 0] - p1[:, 0], p2[:, 2] - p1[:, 2])
        idle = np.max(np.abs(q2 - q0)[:, [0, 2]], axis=1)
        keep &= (there >= args.min_step) & (back >= args.min_step) & (there <= 2000) & (idle <= args.idle_drift)
        if args.y is not None:
            keep &= np.abs(p0[:, 1] - args.y) <= args.y_tol
    groups: dict[tuple, list] = collections.defaultdict(list)
    for k in np.flatnonzero(keep):
        groups[tuple(float(v) for v in np.round(p2[k], 1))].append((int(bases[k]), float(there[k]), float(back[k])))
    ranked = sorted(groups.items(), key=lambda kv: -max(m[1] + m[2] for m in kv[1]))
    return int(keep.sum()), ranked


def owner(snaps: dict[str, np.ndarray], base: int) -> int | None:
    """The word index of the object whose +0x540 this vec4 is, if +0x0C holds a known class."""
    obj = base - physics.OFF_POSITION // 4
    if obj < 0:
        return None
    return obj if int(snaps["w2"][obj + physics.OFF_CLASS // 4]) in physics.CLASSES else None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--slot", type=int, default=sandlot.SLOT)
    ap.add_argument("--arm", default="60", choices=list(ratediff.ARMS))
    ap.add_argument("--there", default="LLeft+LDown", help="buttons held on the way out, joined with +")
    ap.add_argument("--back", default="LRight+LUp", help="buttons held on the way back")
    ap.add_argument("--vsyncs", type=int, default=40, help="vsyncs per leg")
    ap.add_argument("--lead", type=int, default=10, help="idle vsyncs before the first snapshot")
    ap.add_argument("--settle", type=int, default=20, help="vsyncs after letting go")
    ap.add_argument("--min-step", type=float, default=15.0, help="horizontal distance each leg must cover")
    ap.add_argument("--idle-drift", type=float, default=5.0, help="largest x or z drift allowed with no input")
    ap.add_argument("--y", type=float, help="keep only positions whose height starts within --y-tol of this")
    ap.add_argument("--y-tol", type=float, default=60.0)
    ap.add_argument("--all", action="store_true", help="also list positions that are not an object's own")
    ap.add_argument("--top", type=int, default=20, help="other positions to list with --all")
    ap.add_argument("--save", default=str(config.WORK / "findplayer.npz"), help="where a live walk's snapshots go")
    ap.add_argument("--load", help="rank a saved walk instead of running one")
    ap.add_argument("--port", type=int, default=28110)
    args = ap.parse_args()

    if args.load:
        z = np.load(args.load)
        snaps = {k: z[k] for k in KEYS if k in z.files}
        lo = int(z["lo"][0])
    else:
        roo = sandlot.connect(args.port)
        snaps = walk(roo, args)
        lo = ratediff.LO
        config.WORK.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(args.save, lo=np.array([lo]), **snaps)
        print(f"saved {args.save}")

    n, ranked = candidates(snaps, args)
    print(f"{n} vec4s walked there and back and hold still idle: {len(ranked)} distinct positions")

    def line(pos, members) -> str:
        # Heap copies first: objects live on the heap; data and stack hold caches.
        members.sort(key=lambda m: (lo + 4 * m[0] < 0x01000000, m[0]))
        addrs = " ".join(f"{lo + 4 * b:08X}" for b, _, _ in members[:12])
        return (f"({pos[0]:8.1f} {pos[1]:7.1f} {pos[2]:8.1f})  there {max(m[1] for m in members):6.1f}  "
                f"back {max(m[2] for m in members):6.1f}  x{len(members)}: {addrs}")

    objects, others = [], []
    for pos, members in ranked:
        owners = sorted({o for o in (owner(snaps, b) for b, _, _ in members) if o is not None})
        (objects if owners else others).append((pos, members, owners))
    print(f"== objects whose own position walked, furthest first ({len(objects)})")
    for pos, members, owners in objects:
        for o in owners:
            cls = int(snaps["w2"][o + physics.OFF_CLASS // 4])
            print(f"  object {lo + 4 * o:08X}  class {cls:08X} ({physics.CLASSES[cls]})")
        print(f"    {line(pos, members)}")
    if args.all:
        print(f"== other positions, furthest first ({len(others)}; top {args.top})")
        for pos, members, _ in others[:args.top]:
            print(f"  {line(pos, members)}")
    return 0 if objects else 1


if __name__ == "__main__":
    sys.exit(main())
