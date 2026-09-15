"""Extract the boot ELF (SLPM_666.75) from the KH2FM disc image into work/.

    python tools/extract-elf.py
    python tools/extract-elf.py --image "G:/roms/ps2/Kingdom Hearts II - Final Mix+.chd"
    python tools/extract-elf.py --keep-iso

The image comes from --image, else GAME_IMAGE / ROM_DIRS in local.json or the
environment, else PCSX2's own game list. A .chd is first expanded to an ISO with
chdman (the CHDMAN setting, then PATH, then EmuDeck's copy); the ISO is deleted
afterwards unless --keep-iso. The ELF is copyrighted game code: it stays in work/.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

import _bootstrap  # noqa: F401

from game import config
from ps2ee.ciso import DiscImage, find


def find_chdman() -> Path:
    explicit = config._setting("CHDMAN")
    candidates = [Path(explicit)] if explicit else []
    on_path = shutil.which("chdman")
    if on_path:
        candidates.append(Path(on_path))
    appdata = os.environ.get("APPDATA")
    if appdata:
        candidates.append(Path(appdata) / "EmuDeck" / "backend" / "tools" / "chdconv" / "chdman.exe")
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise SystemExit("chdman not found: set CHDMAN in local.json, or put chdman on PATH.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--image")
    parser.add_argument("--out")
    parser.add_argument("--keep-iso", action="store_true")
    args = parser.parse_args()

    image = Path(args.image) if args.image else config.game_image()
    config.WORK.mkdir(parents=True, exist_ok=True)
    iso = image
    made_iso = False
    if image.suffix.lower() == ".chd":
        iso = config.WORK / "kh2fm.iso"
        chdman = find_chdman()
        print(f"expanding {image} with {chdman}")
        subprocess.run([str(chdman), "extractdvd", "-i", str(image), "-o", str(iso), "-f"], check=True)
        made_iso = True

    with DiscImage(str(iso)) as disc:
        entry = find(disc, config.ELF_NAME)
        data = disc.read_range(entry.lba, entry.size)

    out = Path(args.out) if args.out else config.elf_path()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(data)
    print(f"{config.ELF_NAME} -> {out} ({len(data):,} bytes)")
    if made_iso and not args.keep_iso:
        iso.unlink()
        print(f"deleted {iso}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
