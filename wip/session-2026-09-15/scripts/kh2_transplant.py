"""Carry a KH2FM save state from PCSX2 v2.5.274 into PCSXROO as raw memory.

Same method as pcsx2-bt3-60fps/tools/transplant.py: PCSXROO refuses the older
format, so pause the running KH2FM at a frame boundary, overwrite EE main RAM
(above the kernel) and the scratchpad with the state's, and resume. The target
must already be running KH2FM in a gameplay field so the CPU is in the same
main loop the source was saved from.

    python kh2_transplant.py STATE.p2s [--save-slot N] [--shot PATH]
"""
import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path.home() / "Documents" / "GitHub" / "pcsxroo" / "pcsxroo"))

from ps2ee.roo import Roo
from ps2ee.savestate import SaveState

CHUNK = 256 * 1024
SCRATCHPAD = 0x70000000
EE_START = 0x00080000


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("state")
    parser.add_argument("--port", type=int, default=28110)
    parser.add_argument("--save-slot", type=int, default=None)
    parser.add_argument("--shot", default=None, help="screenshot path after resuming")
    args = parser.parse_args()

    with SaveState(args.state) as state:
        print(f"source: PCSX2 {state.version()}")
        ee = state.ee
        scratch = state.read("Scratchpad.bin")
    print(f"  EE {len(ee) / 1048576:.0f} MB, scratchpad {len(scratch)} bytes")

    with Roo(args.port).connect() as roo:
        roo.frame_advance(1)
        if not roo.paused():
            print("  WARNING: not paused at a frame boundary")
        start = time.time()
        for off in range(EE_START, len(ee), CHUNK):
            if not roo.write_bytes(off, ee[off:off + CHUNK]):
                print(f"  write failed at {off:08X}")
                return 1
        print(f"  EE written in {time.time() - start:.1f}s")
        if not roo.write_bytes(SCRATCHPAD, scratch):
            print("  scratchpad write failed")
            return 1
        # A few words the patch and the timing loop use, as a sanity check.
        for a in (0x00349E10, 0x00349E1C, 0x0036B0F8, 0x0036EF20):
            print(f"  {a:08X} = {roo.read(a):08X}")
        roo.resume()
        if args.shot:
            time.sleep(2)
            roo.screenshot(args.shot)
            for _ in range(20):
                if Path(args.shot).exists():
                    break
                time.sleep(0.5)
            print(f"  screenshot {args.shot} exists={Path(args.shot).exists()}")
        if args.save_slot is not None:
            roo.savestate(args.save_slot)
            print(f"  saved to PCSXROO slot {args.save_slot}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
