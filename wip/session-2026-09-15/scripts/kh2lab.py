"""Shared helpers for the KH2FM Sandlot ball investigation in PCSXROO.

Arms follow the BT3 testing rules: load the state paused, then apply the arm,
then run. The state was captured with the 60 FPS group on, so the 30fps arm
must write the stock words back after loading.
"""
import struct
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path.home() / "Documents" / "GitHub" / "pcsxroo" / "pcsxroo"))

from ps2ee.roo import Roo  # noqa: E402

SCRATCH = Path(__file__).resolve().parent
PNACH = Path.home() / "Documents" / "GitHub" / "pcsxroo" / "bin" / "patches" / "SLPM-66675_FAF99301.pnach"
GROUP = b"[60 FPS]"
GROUP_OFF = b"[60 FPS - off for A/B]"
SLOT = 1

# What the 60 FPS group writes, and what stock KH2FM holds there at 30fps:
# 00349E1C extra vsync wait (game init passes 1), 0036B0F8 frame-delta cap
# (ELF 6.0), 0036EF20 fixed-step accumulator threshold (ELF 2.0).
PATCHED = {0x00349E1C: 0x00000000, 0x0036B0F8: 0x3F800000, 0x0036EF20: 0x3F800000}
STOCK = {0x00349E1C: 0x00000001, 0x0036B0F8: 0x40C00000, 0x0036EF20: 0x40000000}

DELTA = 0x00349E10
# Game-tick counter: +1 per game tick, so +20 per 20 vsyncs at 60fps and +10
# at 30fps. Measured 2026-09-15 by diffing RAM across both arms.
TICKS = 0x0032B920


def connect(port: int = 28110) -> Roo:
    return Roo(port).connect()


def set_group(enabled: bool) -> None:
    """Rename the local [60 FPS] group. NOT an arm switch: PCSX2's bundled
    patches.zip carries an identical [60 FPS] for this serial and CRC, so the
    enabled name keeps matching. Kept only to undo the old experiments."""
    data = PNACH.read_bytes()
    new = data.replace(GROUP_OFF, GROUP) if enabled else data.replace(GROUP, GROUP_OFF)
    if new != data:
        PNACH.write_bytes(new)


def set_arm(roo: Roo, fps: int) -> None:
    """PCSXROO boots with the 60 FPS group NOT enabled, so the three words it
    owns stay whatever is written here - the game does not rewrite them in
    field gameplay (mode 1). The patch's mode-5 conditional is not modelled."""
    for addr, value in (PATCHED if fps == 60 else STOCK).items():
        if not roo.write(addr, value):
            raise RuntimeError(f"arm write did not stick at {addr:08X}")


def f32(roo: Roo, addr: int) -> float:
    return struct.unpack("<f", roo.read_bytes(addr, 4))[0]


def start(roo: Roo, fps: int) -> None:
    """Load the Sandlot state paused, apply the arm, prove it, leave it paused.

    Proof is the game-tick counter, not the delta: at 30fps a paused VM sits
    inside the frame routine's vsync wait, where 00349E10 still holds the
    pre-wait count (1.0) rather than the 2.0 the game goes on to use.
    """
    if not roo.paused():
        roo.pause()
    roo.loadstate(SLOT)
    if not roo.paused():
        print("  WARNING: VM running after loadstate; pausing")
        roo.pause()
    set_arm(roo, fps)
    roo.frame_advance(2)
    t0 = roo.read(TICKS)
    roo.frame_advance(4)
    ticks = roo.read(TICKS) - t0
    want = 4 if fps == 60 else 2
    if ticks != want:
        raise RuntimeError(f"{fps}fps arm not in effect: {ticks} ticks in 4 vsyncs, want {want}")


def spans(addrs, gap: int = 256):
    """Merge sorted addresses into (start, end) read spans."""
    out = []
    for a in sorted(addrs):
        if out and a - out[-1][1] <= gap:
            out[-1][1] = a + 4
        else:
            out.append([a, a + 4])
    return out


def shot(roo: Roo, name: str) -> Path:
    """Screenshot needs a running VM: run briefly, capture, pause again."""
    path = SCRATCH / name
    if path.exists():
        path.unlink()
    roo.screenshot(str(path))
    roo.frame_advance(1)
    for _ in range(40):
        if path.exists():
            break
        time.sleep(0.25)
    return path
