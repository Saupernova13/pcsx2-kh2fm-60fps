"""Carry a KH2FM save state from a PCSX2 build whose format PCSXROO refuses, as raw memory.

    python tools/transplant.py "<PCSX2>/sstates/SLPM-66675 (FAF99301).01.p2s" --shot
    python tools/transplant.py STATE.p2s --save-slot 1

PCSXROO (PCSX2 v2.9.x core) refuses states from the user's PCSX2 v2.5.274: "This
save state was created with PCSX2 version v2.5.274. It is no longer compatible".
Same method as the BT3 repo's transplant.py: pause the running game at a frame
boundary, overwrite EE main RAM from 00080000 up and the scratchpad with the
state's, and resume.

The target must already be running KH2FM in a gameplay field, so the CPU is in
the same main loop the source was saved from. On 2026-09-15 the target was save
03 on Memory Card 2 ("The Usual Spot", a Twilight Town field) and the source was
the Sandlot; the Sandlot came up intact on the first try. Then --save-slot keeps
it in PCSXROO's own format, and no transplant is needed again.
"""

from __future__ import annotations

import argparse
import sys
import time

import _bootstrap  # noqa: F401

from game import config, sandlot, timing
from ps2ee.savestate import SaveState

CHUNK = 256 * 1024
SCRATCHPAD = 0x70000000
EE_START = 0x00080000


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("state")
    parser.add_argument("--port", type=int, default=28110)
    parser.add_argument("--save-slot", type=int)
    parser.add_argument("--shot", action="store_true", help="screenshot work/transplant.png after resuming")
    args = parser.parse_args()

    with SaveState(args.state) as state:
        print(f"source: PCSX2 {state.version()}")
        ee = state.ee
        scratch = state.read("Scratchpad.bin")
    print(f"  EE {len(ee) / 1048576:.0f} MB, scratchpad {len(scratch)} bytes")

    roo = sandlot.connect(args.port)
    roo.frame_advance(1)
    if not roo.paused():
        print("  WARNING: not paused at a frame boundary")
    started = time.time()
    for off in range(EE_START, len(ee), CHUNK):
        if not roo.write_bytes(off, ee[off:off + CHUNK]):
            print(f"  write failed at {off:08X}")
            return 1
    print(f"  EE written in {time.time() - started:.1f}s")
    if not roo.write_bytes(SCRATCHPAD, scratch):
        print("  scratchpad write failed")
        return 1
    for addr in (timing.DELTA, timing.VSYNC_WAIT, timing.DELTA_CAP, timing.ACCUM_THRESHOLD):
        print(f"  {addr:08X} = {roo.read(addr):08X}")
    roo.resume()
    if args.shot:
        time.sleep(2)
        path = config.WORK / "transplant.png"
        config.WORK.mkdir(parents=True, exist_ok=True)
        roo.screenshot(str(path))
        for _ in range(20):
            if path.exists():
                break
            time.sleep(0.5)
        print(f"  screenshot {path} exists={path.exists()}")
    if args.save_slot is not None:
        roo.savestate(args.save_slot)
        print(f"  saved to PCSXROO slot {args.save_slot}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
