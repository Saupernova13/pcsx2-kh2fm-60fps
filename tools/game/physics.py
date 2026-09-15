"""Object classes and motion code, as found in the Twilight Town Sandlot, 2026-09-15.

A prop switches class when it is hit: at rest it is class 01C60030 (motion
0017C290), airborne it is class 01C60340 (motion 002EA450, the integrator below).
Characters share the object layout, the displacement builder and the classes:
Sora, Donald and Goofy are 01C60030 on the ground, and a character in the air is
01C60040 (motion 0017C8F0). The ball notes took Sora for "a second prop"; walking
him away and back (tools/findplayer.py) corrected that.

Units: velocity is stored per 60 Hz frame, and moved by velocity * delta, so
position is correct at both rates. What is not is code that changes velocity or
state once per frame or per game tick: the prop integrator's drag and gravity, the
jump controller's cut, and the shared velocity step. See docs/findings.md.

The generators hold their own hook sites and expected words: tools/mkballfix.py,
tools/mkjumpfix.py, tools/mkfrictionfix.py.
"""

# --- classes and routines ---
CLASS_REST = 0x01C60030
VTABLE_REST = 0x0034EB60
MOTION_REST = 0x0017C290              # grounded motion; calls VELOCITY_STEP from 0017C2B8

CLASS_AIRBORNE = 0x01C60340
VTABLE_AIRBORNE = 0x00363410
MOTION_AIRBORNE = 0x002EA450          # vtable +0x1C; the only table pointing at it

CLASS_CHAR_AIRBORNE = 0x01C60040      # a character in the air; first named a second prop's class
VTABLE_CHAR_AIRBORNE = 0x0034EB90
MOTION_CHAR_AIRBORNE = 0x0017C8F0     # calls CLOCK_ADVANCE with AIR_BLEND and AIR_FRICTION

CLASS_ORIGIN = 0x01C60060             # three Sandlot objects sitting at the origin
VTABLE_ORIGIN = 0x0034EB30
MOTION_ORIGIN = 0x0017A968

CLASSES = {CLASS_REST: "rest / grounded", CLASS_AIRBORNE: "prop airborne",
           CLASS_CHAR_AIRBORNE: "character airborne", CLASS_ORIGIN: "origin"}

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
OFF_FACING = 0x10             # unit vector
OFF_CLASS = 0x0C
OFF_INPUT_SPEED = 0x1C        # movement input speed; > 0 selects the blend in VELOCITY_STEP
OFF_VELOCITY = 0x20           # vec4; +0x24 is vy (negative is up)
OFF_TERMINAL = 0x120          # 10.0
OFF_MOTION_CLOCK = 0x170      # the current motion's clock, 60 Hz units, reset when a motion starts
OFF_POSITION = 0x540
OFF_PREV_POSITION = 0x590     # copied from +0x540 by the collision resolver
OFF_FRAME_DISP = 0x5A0        # this frame's displacement
OFF_ENTRY_POSITION = 0x840    # copied from +0x540 at builder entry
OFF_REQUESTED_DISP = 0x850    # displacement / delta, before collision
OFF_RESOLVED_DISP = 0x860     # displacement / delta, after collision
OFF_RAW_PUSH_A = 0x560        # added to the displacement without delta; zero in every trace
OFF_RAW_PUSH_B = 0x870        # likewise

# --- the hit ---
HIT_POP_VY = -60.0            # a pop-up; one drag step later it reads -47.59
HIT_SIDE = (51.0, -42.0)      # side swipe: horizontal speed, vy
HIT_BUMP_VY = -10.0           # weak hit

# --- a character's jump: [60 FPS - short hop] ---
# A jump is a closed-form arc on a clock that advances by delta: a rise over a
# duration, a short apex arc, then a parabola under 0.408163.
JUMP_CONTROLLER = 0x0017C690  # cuts a released jump's rise into the apex arc once JUMP_CUT < clock
JUMP_CUT = 0x0036C518         # 6.0
ARC_SETUP = 0x0017C42C        # writes base, height, clock and duration = sqrt(2h/g) via 0017D130
CLOCK_ADVANCE = 0x0017C870    # clock += delta, then VELOCITY_STEP, then ARC_HEIGHT
ARC_HEIGHT = 0x0017C930       # rise while clock < duration, then the parabola (0036C530 0.5, 0036C534 g)
APEX_DURATION = 0x0036C51C    # 5.0
APEX_HEIGHT = 0x0036C520      # 5.102040
OFF_JUMP_CLOCK = 0xD0
OFF_JUMP_DURATION = 0xD4      # 30.108 for Sora's jump
OFF_JUMP_BASE = 0xD8
OFF_JUMP_HEIGHT = 0xDC        # -185.0 for Sora's jump
OFF_JUMP_FLAGS = 0x108        # JUMP_CONTROLLER tests 0x40000 here for the release

# --- the shared velocity step: [60 FPS - friction] ---
# With input (OFF_INPUT_SPEED > 0): v = v*k1 + facing*speed*(1 - k1); without:
# v = v*k2; then displacement = v*delta. k1 arrives in f12 (-> f20), k2 in f13
# (-> f21). Once per frame, with no delta. VU0 code: disassemble it with PCSXROO.
VELOCITY_STEP = 0x00184540
AIR_BLEND = 0x0036C524        # 0.9, k1 in the air
AIR_FRICTION = 0x0036C528     # 0.95, k2 in the air
VELOCITY_STEP_CALLERS = (
    0x0017C2B8,   # grounded class motion, factors from +0xF0
    0x0017C8AC,   # airborne character motion
    0x0019FE60, 0x001A0AE0, 0x001B219C, 0x001B2B30, 0x001C9510, 0x001D23B4, 0x001D2628,
    0x001D2E48, 0x002BEC54, 0x002C1A38, 0x002D6EF4, 0x002E1928, 0x002E2F28, 0x002EAE44,
    0x002EB6B4, 0x002EC830, 0x002ED148,   # not identified
)

# --- the fix: [60 FPS - ball physics] ---
HOOK = 0x002EA498             # was beql sp, s6, 002EA4AC
SKIP_TO = 0x002EA574          # first instruction after the velocity block
RESUME = 0x002EA4AC
CAVE = 0x000FE000             # 16 words, 000FE000..000FE03C
