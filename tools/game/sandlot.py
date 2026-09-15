"""The Sandlot juggling scene: the save state every A/B starts from, and its schedule.

The state is the user's own PCSX2 v2.5.274 save state 1 (Sora beside the glowing
ball in the Twilight Town Sandlot), carried into PCSXROO with tools/transplant.py
and saved there as slot 1. None ships - see the README.

Arms follow the BT3 rules: load the state paused, apply the arm, prove it, run.
PCSXROO must boot this game with [60 FPS] NOT enabled in its own gamesettings ini,
because PCSX2's bundled patches.zip carries an identical [60 FPS] group that keeps
re-applying under any rename. The arm is set by writing the three words directly.

Object addresses below are heap addresses in THIS state, not constants of the game.
"""

from __future__ import annotations

import struct
import time
from pathlib import Path

from ps2ee.roo import Roo

from game import config, timing

SLOT = 1

BALL = 0x01ADD9D0
BALL_COLLISION = 0x01ADEAC0   # collision-shape centre x, y, z (y negative-up), written by 0018A924
PROP2 = 0x01A94440            # the second prop, which flies as class 01C60040
GROUND_PROPS = (0x01AC2490, 0x01AADB90)
PARAM_BLOCK = 0x01CE36CC

# A stack scratch slot that looked like the ball and is not: 0037EC30 is the AABB
# centre computed on the stack by 00134E.., shared by every object's collision, so
# at 30fps it showed another object between ticks. Kept here as a warning.
STACK_AABB_CENTRE = 0x0037EC30

# The input schedule, in vsyncs, identical in every arm so every arm covers the
# same real time.
IDLE_VSYNCS = 6
WALK_BUTTONS = ("LLeft", "LDown")   # walk towards the ball; plain LLeft swings the wrong way
WALK_VSYNCS = 8
PRESS_VSYNCS = 2
MASH_PERIOD = 8                      # Cross 2 vsyncs on, 6 off


def connect(port: int = 28110) -> Roo:
    return Roo(port).connect()


def f32(roo: Roo, addr: int) -> float:
    return struct.unpack("<f", roo.read_bytes(addr, 4))[0]


def set_arm(roo: Roo, fps: int) -> None:
    for addr, value in (timing.PATCHED if fps == 60 else timing.STOCK).items():
        if not roo.write(addr, value):
            raise RuntimeError(f"arm write did not stick at {addr:08X}")


def start(roo: Roo, fps: int) -> None:
    """Load the state paused, apply the arm, prove it by the tick counter, leave it paused."""
    if not roo.paused():
        roo.pause()
    roo.loadstate(SLOT)
    if not roo.paused():
        print("  WARNING: VM running after loadstate; pausing")
        roo.pause()
    set_arm(roo, fps)
    roo.frame_advance(2)
    t0 = roo.read(timing.TICKS)
    roo.frame_advance(4)
    ticks = roo.read(timing.TICKS) - t0
    want = timing.TICKS_PER_4_VSYNCS[fps]
    if ticks != want:
        raise RuntimeError(f"{fps}fps arm not in effect: {ticks} ticks in 4 vsyncs, want {want}")


def apply_words(roo: Roo, words) -> None:
    for addr, value in words or ():
        if not roo.write(addr, value):
            raise RuntimeError(f"fix write did not verify at {addr:08X}")


def prepare(roo: Roo, fps: int, fix=None, offset: int = 0) -> None:
    """Start the arm, apply a fix, idle, and walk Sora to the ball. Leaves it paused."""
    start(roo, fps)
    apply_words(roo, fix)
    roo.frame_advance(IDLE_VSYNCS + offset)
    roo.input_set(*WALK_BUTTONS)
    roo.frame_advance(WALK_VSYNCS)
    roo.input_release()


def press_cross(roo: Roo) -> None:
    roo.input_set("Cross")
    roo.frame_advance(PRESS_VSYNCS)
    roo.input_release()


def mash_step(roo: Roo, t: int) -> None:
    """Drive the mash schedule for vsync t (call before advancing that vsync)."""
    phase = t % MASH_PERIOD
    if phase == 0:
        roo.input_set("Cross")
    elif phase == PRESS_VSYNCS:
        roo.input_release()


def spans(addrs, gap: int = 256) -> list[list[int]]:
    """Merge sorted addresses into [start, end) read spans."""
    out: list[list[int]] = []
    for a in sorted(addrs):
        if out and a - out[-1][1] <= gap:
            out[-1][1] = a + 4
        else:
            out.append([a, a + 4])
    return out


def shot(roo: Roo, name: str) -> Path:
    """Screenshot in place of one vsync step: a paused VM queues it, frame_advance flushes it."""
    config.WORK.mkdir(parents=True, exist_ok=True)
    path = config.WORK / name
    if path.exists():
        path.unlink()
    roo.screenshot(str(path))
    roo.frame_advance(1)
    for _ in range(40):
        if path.exists():
            break
        time.sleep(0.25)
    return path
