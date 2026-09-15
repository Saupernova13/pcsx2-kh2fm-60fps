"""This game's config: repo paths, patch policy, and the bound identity.

Imports the generic discovery config from the sibling pcsxroo checkout's ps2ee,
binds this game's identity, then re-exports the generic functions so tools read
``from game import config`` exactly as the BT3 tools do.
"""

from __future__ import annotations

import os
from pathlib import Path

from ps2ee import config as _generic

from game import identity

REPO = Path(__file__).resolve().parent.parent.parent
WORK = REPO / "work"
PATCHES = REPO / "patch"
WIP = REPO / "wip"

# This repo's overrides come from ITS local.json, not pcsxroo's.
_generic.LOCAL_JSON = REPO / "local.json"

_generic.bind(identity.IDENTITY)

SERIAL = identity.SERIAL
CRC = identity.CRC
ELF_NAME = identity.ELF_NAME
GAME = identity.GAME
TEXT_BASE = identity.TEXT_BASE
TEXT_END = identity.TEXT_END
DATA_BASE = identity.DATA_BASE
BSS_END = identity.BSS_END
GP_BASE = identity.GP_BASE
SAFE_ZONE = identity.SAFE_ZONE
SAFE_ZONE_SIZE = identity.SAFE_ZONE_SIZE
EE_RAM_SIZE = _generic.EE_RAM_SIZE
NEVER_SHIP = identity.NEVER_SHIP
OPTIONAL = identity.OPTIONAL
DB_PATCH_NAME = identity.DB_PATCH_NAME

from ps2ee.config import (  # noqa: E402, F401
    _setting,
    global_ini,
    pcsx2_dir,
    pcsxroo_dir,
    sstates_dir,
)


def patches_dir() -> Path:
    """PCSX2's user patches folder, which overrides the bundled database per game."""
    return pcsx2_dir() / "patches"


def game_ini() -> Path:
    """The per-game settings ini, named by serial and the running CRC."""
    return pcsx2_dir() / "gamesettings" / f"{SERIAL}_{CRC}.ini"


def patches_zip() -> Path:
    """PCSX2's bundled patch database."""
    return pcsx2_dir() / "resources" / "patches.zip"


def elf_path() -> Path:
    """Where tools/extract-elf.py drops the extracted boot ELF."""
    return WORK / ELF_NAME


def game_image() -> Path:
    """The KH2FM disc image (.chd, .iso or .cso)."""
    explicit = _setting("GAME_IMAGE")
    if explicit:
        return Path(explicit)
    roots = [Path(p) for p in _setting("ROM_DIRS", "").split(os.pathsep) if p]
    if not roots:
        roots = _rom_dirs_from_ini()
    for root in roots:
        for pattern in ("*Kingdom Hearts II*Final Mix*.chd", "*Kingdom Hearts II*Final Mix*.iso",
                        "*Kingdom Hearts II*Final Mix*.cso"):
            for hit in sorted(root.rglob(pattern)):
                return hit
    raise FileNotFoundError(
        "Could not locate the KH2FM disc image. Set GAME_IMAGE in the environment or in local.json."
    )


def _rom_dirs_from_ini() -> list[Path]:
    ini = global_ini()
    if not ini.exists():
        return []
    dirs, in_section = [], False
    for line in ini.read_text(errors="replace").splitlines():
        stripped = line.strip()
        if stripped.startswith("["):
            in_section = stripped.lower() == "[gamelist]"
            continue
        if in_section and "=" in stripped:
            value = stripped.split("=", 1)[1].strip()
            if value and Path(value).is_dir():
                dirs.append(Path(value))
    return dirs
