"""KH2FM's frame timing, and the three words PeterDelta's [60 FPS] group owns.

Disassembled from the unpatched ELF and measured live, 2026-09-14/15. The full
derivation is in docs/findings.md, "How the 60 FPS patch works".

The frame routine at 0014D060 waits for vsync, then sets the frame delta. The
game already has a real delta-time system - 211 reads of [00349E10] in .text - so
anything that scales by it is correct at 60fps on its own. What breaks at 60fps
is code that steps once per game tick and ignores it.
"""

# +1 per game tick: +20 per 20 vsyncs at 60fps, +10 at 30fps. The clean oracle
# for which arm is running. Found 2026-09-15 by diffing RAM across both arms.
TICKS = 0x0032B920

# Vsyncs since the last frame; incremented by the vsync callback 0014CF18,
# registered at 0014D020.
VSYNC_COUNT = 0x00349E08

# Multiplied into the delta (0014D0F0).
DELTA_SCALE = 0x00349E0C

# The frame delta, in units of 1/60 s: 2.0 at 30fps, 1.0 at 60fps. With the
# measured-delta flag set, the routine writes the vsync count on entry (1.0) and
# the count after its wait (2.0 at 30fps), so a VM paused inside that wait reads
# 1.0 even at 30fps. Prove the arm with TICKS, never with this.
DELTA = 0x00349E10
DELTA_UNCLAMPED = 0x00349E14
INV_DELTA = 0x00349E18

# Extra vsyncs to wait each frame. The game's init passes 1 (0014CFD8 -> setter
# 0014CE30), which is 30fps. [60 FPS] forces 0.
VSYNC_WAIT = 0x00349E1C

# Non-zero: the delta is the measured vsync count. Zero: the constant DELTA_BASE.
MEASURED_DELTA_FLAG = 0x00349E20

DELTA_BASE = 0x0036B0F4        # 2.0 in the ELF
DELTA_CAP = 0x0036B0F8         # 6.0 in the ELF; [60 FPS] sets 1.0
ACCUM_THRESHOLD = 0x0036EF20   # 2.0 in the ELF; [60 FPS] sets 1.0 (fixed-step accumulator in 001E6280)

# [60 FPS] carries an E-code: when this byte is 5 it writes VSYNC_WAIT = 1 again.
GAME_MODE = 0x0032BA24

FRAME_ROUTINE = 0x0014D060
VSYNC_WAIT_SETTER = 0x0014CE30
VSYNC_CALLBACK = 0x0014CF18

# What [60 FPS] writes every frame, and what the unpatched game holds there at 30fps.
PATCHED = {VSYNC_WAIT: 0x00000000, DELTA_CAP: 0x3F800000, ACCUM_THRESHOLD: 0x3F800000}
STOCK = {VSYNC_WAIT: 0x00000001, DELTA_CAP: 0x40C00000, ACCUM_THRESHOLD: 0x40000000}

# Game ticks in 4 vsyncs, per arm. The proof start() checks after switching.
TICKS_PER_4_VSYNCS = {60: 4, 30: 2}
