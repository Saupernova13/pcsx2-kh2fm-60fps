"""Everything true of Kingdom Hearts II Final Mix+ (English undub) and nothing else.

The generic ps2ee library (in the sibling pcsxroo checkout) knows how to discover
emulators and walk EE memory; this file is the game knowledge the generic side
must never carry: identity, ELF layout, the safe zone, and the patch policy.
"""

from ps2ee.config import GameIdentity

SERIAL = "SLPM-66675"
# The English undub patched image. The untouched Japanese disc is F266B00B.
# PCSX2 matches a patch file to the running CRC, and every address in this repo
# was measured on FAF99301.
CRC = "FAF99301"
UNPATCHED_CRC = "F266B00B"
ELF_NAME = "SLPM_666.75"
GAME = "Kingdom Hearts II Final Mix+ (NTSC-J, English undub patch)"

# From the ELF's section headers. Code and initialised data share one RWX
# section, "main" (00100000..0037A4B4); .ctors, .dtors and .reginfo follow, then
# .bss runs to 01E4C868. The entry point is 0010001C.
TEXT_BASE = 0x00100000
TEXT_END = 0x0037A4B4
DATA_BASE = 0x0037A4B4
BSS_END = 0x01E4C868

# Because main holds both, a scan for instructions has to stop somewhere short
# of it. Every static scan in docs/findings.md stopped here: code runs at least
# to 00325700, and data words (the 10.0 constants from 003421D8) start above it.
CODE_SCAN_END = 0x00340000

# ri_gp_value from .reginfo, and $gp as read live on the game thread.
GP_BASE = 0x0037A800

# Zero in the user's save state 1 and in a live Sandlot session, 2026-09-15.
# PCSX2's own [Swap X and O] group uses 000FD050..000FD090 just below it.
SAFE_ZONE = 0x000FE000
SAFE_ZONE_SIZE = 0x2000

# PCSX2's name for this game's patch file, in patches/ and in patches.zip.
DB_PATCH_NAME = f"{SERIAL}_{CRC}.pnach"

IDENTITY = GameIdentity(
    serial=SERIAL,
    crc=CRC,
    elf_name=ELF_NAME,
    game=GAME,
    text_base=TEXT_BASE,
    text_end=TEXT_END,
    data_base=DATA_BASE,
    bss_end=BSS_END,
    gp_base=GP_BASE,
    safe_zone=SAFE_ZONE,
    safe_zone_size=SAFE_ZONE_SIZE,
)

# Groups in wip/working.pnach that must never ship. The constant-scaling
# candidate fixes the same routine as [60 FPS - ball physics] a different way;
# both on together would compensate twice and run the ball at half speed.
NEVER_SHIP = [
    "EXPERIMENT ball physics constant scaling",
]

# A display-aspect hack is a preference, not a fix, and it conflicts with
# ElHecht's [Widescreen 16:9]. Installed only with tools/install.py --widescreen.
OPTIONAL = [
    "Widescreen 19.5:9 - S24 Ultra",
]

# Groups from PCSX2's own database patch that this project's groups need, and
# never ships. They are other people's work.
REQUIRES = {
    "60 FPS - ball physics": "60 FPS",
    "Widescreen 19.5:9 - S24 Ultra": "Widescreen 16:9",
}
