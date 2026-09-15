"""Game-state addresses published by the KH2FM modding community, for this disc.

Source: the Garden of Assemblage ROM edition's PCSX2-EX Lua script
(https://github.com/KH2FM-Mods-Num/GoA-ROM-Edition, "F266B00B GoA ROM.lua"), whose
PCSX2 branch is selected for GAME_ID 0xF266B00B or 0xFAF99301 - so these are the
same addresses on this English-patched disc. Only the facts (addresses and what
they hold) are recorded here; none of that script's code is.

Where this project measured one independently, the note says so.
"""

# --- where the player is ---
NOW = 0x0032BAE0        # current location: +0 world (byte), +1 room (byte), +2 door, +4 map, +6 battle, +8 event (shorts)
NOW_PREV_PLACE = 0x30   # previous world/room
SAVED_LOCATION = 0x01D5A970
SAVE = 0x0032BB30       # the in-RAM save: "KH2J" header; +0x0C world, +0x0D room, +0x0E door (as on the memory card)
SAVE_SPAWN_TABLE = 0x310  # six bytes per room: the spawn ids a warp loads into NOW+4

# --- data tables loaded from the disc ---
OBJ0_POINTER = 0x01D5BA10   # -> 00objentry.bin
SYS3_POINTER = 0x01C61AF8   # -> 03system.bin
BTL0_POINTER = 0x01C61AFC   # -> 00battle.bin
ARD_POINTER = 0x0034ECF4    # -> the current area's ARD

# --- party, gauges, menus ---
SLOT1 = 0x01C6C750      # unit slot 1 (Sora's stats); next slot +0x268
SLOT_STEP = 0x268
POINT1 = 0x01D48EFC     # party member 1 pointer block; next +0x38
POINT_STEP = 0x38
GAUGE1 = 0x01D48FA4     # next +0x34
GAUGE_STEP = 0x34
MENU1 = 0x01C5FF18      # main command menu; next +4
REACT = 0x01C5FF4E      # the reaction command on offer
CONTROLLABLE = 0x01D48DB8

# --- flow ---
BATTLE_STATUS = 0x01C61958  # out of battle / regular / forced
BATTLE_END = 0x01D490C0
TEXTBOX = 0x01D48D54
PAUSE = 0x00347E08
MUSIC = 0x00347D34
CAMERA_TYPE = 0x00348750

# --- time ---
TIMER = 0x00349DE8          # this project found it independently as a per-vsync clock (+20 per 20 vsyncs at both rates)
GAME_SPEED = 0x00349E0C     # this project's "delta scale": delta is multiplied by it in the frame routine
CUTSCENE_TIMER = 0x0035DE20
CUTSCENE_LENGTH = 0x0035DE28
CUTSCENE_SKIP = 0x0035DE08

# --- minigames ---
ATLANTICA_SONGS = 0x0035DAC4
GUMMI_SCORE = 0x01F8039C
GUMMI_MEDAL = 0x01F803C0
GUMMI_KILLS = 0x01F80856

# World ids as they appear in NOW+0 and SAVE+0x0C (the user's three saves all read 02).
WORLD_TWILIGHT_TOWN = 0x02
