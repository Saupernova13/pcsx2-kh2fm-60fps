"""The juggling-ball prop class, as found in the Twilight Town Sandlot, 2026-09-15.

A prop switches class when it is hit: at rest it is class 01C60030 (motion
0017C290, which zeroes its velocity), airborne it is class 01C60340 (motion
002EA450, the integrator below). A second Sandlot prop flies as class 01C60040
(motion 0017C8F0), which this project has not examined.

Units: velocity is stored per 60 Hz frame, and moved by velocity * delta, so
position is correct at both rates. What is not is the velocity update itself,
which runs once per game tick. See docs/findings.md.
"""

# --- classes and routines ---
CLASS_REST = 0x01C60030
VTABLE_REST = 0x0034EB60
MOTION_REST = 0x0017C290

CLASS_AIRBORNE = 0x01C60340
VTABLE_AIRBORNE = 0x00363410
MOTION_AIRBORNE = 0x002EA450          # vtable +0x1C; the only table pointing at it

CLASS_PROP_AIRBORNE = 0x01C60040
VTABLE_PROP_AIRBORNE = 0x0034EB90
MOTION_PROP_AIRBORNE = 0x0017C8F0     # unexamined

# Same drag, gravity and cap pattern as MOTION_AIRBORNE, reading its own gravity
# copy at 0036D440 and the same param block. Reached by fall-through, no callers
# found. Not fixed.
SIBLING_INTEGRATOR = 0x0019FBC4

DISPLACEMENT_BUILDER = 0x00183088     # a0 = object; sums the per-tick displacement
COLLISION_RESOLVER = 0x00183918
HIT_HANDLER = 0x002E7E48              # called from 001DAE88; sets an absolute velocity
HIT_VY_WRITE = 0x002E7EE8             # swc1 f00, 0x24(t5): vy = -[a0+0x8]

# --- constants ---
GRAVITY = 0x00363404          # 0.408163 per tick; single reader, 002EA55C
RESTITUTION = 0x00363400      # 0.8, negated for the ground-bounce reflection at 002EA8C0
PARAM_BLOCK_PTR = 0x00352130  # -> runtime block (01CE36CC in the Sandlot state)
PARAM_HORIZONTAL_DECAY = 0x18 # 0.8 per tick; also read by 0019FBC4
PARAM_RISING_DRAG = 0x20      # 0.8 per tick while vy < 0; also read by 0019FBC4
HORIZONTAL_FLOOR = 0x003760C8 # 1.0; single reader

# The other data words holding 0.408163 are read by closed-form ballistic solves,
# not integrators: apex time v/g (0016A99C, 001846F4), launch speed sqrt(-2h/g)
# (0017C42C) and fall time (0017D130, 0017CA50).
GRAVITY_COPIES = {
    0x0036C1AC: 0x0016A99C,
    0x0036C510: 0x0017C42C,
    0x0036C534: 0x0017CA50,
    0x0036C554: 0x0017D130,
    0x0036C8AC: 0x001846F4,
    0x0036D440: 0x0019FBC4,
}

# --- object offsets ---
OFF_CLASS = 0x0C
OFF_VELOCITY = 0x20           # vec4; +0x24 is vy (negative is up)
OFF_TERMINAL = 0x120          # 10.0
OFF_POSITION = 0x540
OFF_PREV_POSITION = 0x590     # copied from +0x540 by the collision resolver
OFF_ENTRY_POSITION = 0x840    # copied from +0x540 at builder entry
OFF_REQUESTED_DISP = 0x850    # displacement / delta, before collision
OFF_RESOLVED_DISP = 0x860     # displacement / delta, after collision
OFF_RAW_PUSH_A = 0x560        # added to the displacement without delta; zero in every trace
OFF_RAW_PUSH_B = 0x870        # likewise

# --- the hit ---
HIT_POP_VY = -60.0            # a pop-up; one drag step later it reads -47.59
HIT_SIDE = (51.0, -42.0)      # side swipe: horizontal speed, vy
HIT_BUMP_VY = -10.0           # weak hit

# --- the fix: [60 FPS - ball physics] ---
HOOK = 0x002EA498             # was beql sp, s6, 002EA4AC
SKIP_TO = 0x002EA574          # first instruction after the velocity block
RESUME = 0x002EA4AC
CAVE = 0x000FE000             # 16 words, 000FE000..000FE03C
