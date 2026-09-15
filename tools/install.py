"""Add this project's groups to PCSX2's own KH2FM patch, without shipping anyone else's.

    python tools/install.py                  # add every group in patch/kh2fm-60fps.pnach and enable them
    python tools/install.py --widescreen     # also build [Widescreen 19.5:9 - S24 Ultra]
    python tools/install.py --enable-60fps   # also enable PeterDelta's [60 FPS], if it is off
    python tools/install.py --dry-run        # say what would change, write nothing
    python tools/install.py --status
    python tools/install.py --remove         # take this project's groups back out

This repository holds only its own work. The patch it installs into is the one
PCSX2 already has for the game: patches/SLPM-66675_FAF99301.pnach if the user has
one, otherwise the SLPM-66675_FAF99301.pnach entry inside PCSX2's
resources/patches.zip, written out to patches/. Every group by another author -
ElHecht's widescreen, PeterDelta's 60 FPS and the rest - is left byte for byte as
it was. This project's 60fps groups are inserted together, in the order
patch/kh2fm-60fps.pnach lists them, right after [60 FPS], which all of them need;
any earlier copy of any of them is replaced.

The 19.5:9 group is ElHecht's [Widescreen 16:9] with five words changed. It is
built here, from the 16:9 group in the user's own file, using only the changes
recorded in patch/widescreen-19.5x9-s24.json, and only after every word it
changes is confirmed to be the word it expects to replace.

PCSX2 reads patch files and the per-game ini at boot: quit and relaunch it.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import textwrap
import zipfile
from datetime import datetime
from pathlib import Path

import _bootstrap  # noqa: F401

from game import config, identity
from game.pnachtext import block_range, headers, insert_after, normalise_blank_lines, patch_words, remove_block
from ps2ee.pnach import Pnach

WIDESCREEN = "Widescreen 19.5:9 - S24 Ultra"
NEEDS = "60 FPS"
# Names this project has shipped at some point, so an old install is cleaned up too.
FORMER = ["60 FPS - ball physics"]


# --- this project's groups ---------------------------------------------------

def our_blocks() -> list[tuple[str, list[str]]]:
    """Every group in patch/kh2fm-60fps.pnach, with its comment paragraph, in file order."""
    path = config.PATCHES / "kh2fm-60fps.pnach"
    lines = path.read_text(encoding="utf-8").splitlines()
    out = []
    for _, name in headers(lines):
        start, _, end = block_range(lines, name)
        out.append((name, lines[start:end]))
    if not out:
        raise SystemExit(f"{path} has no groups")
    return out


def our_names() -> list[str]:
    return [name for name, _ in our_blocks()]


def widescreen_block(base_lines: list[str]) -> list[str]:
    spec = json.loads((config.PATCHES / "widescreen-19.5x9-s24.json").read_text(encoding="utf-8"))
    found = block_range(base_lines, spec["base_group"])
    if not found:
        raise SystemExit(f"[{spec['base_group']}] is not in the base patch file; cannot build [{WIDESCREEN}]")
    _, header, end = found
    base = [line for line in base_lines[header + 1:end] if line.strip().startswith("patch=")]
    if len(base) != spec["base_patch_lines"]:
        raise SystemExit(f"[{spec['base_group']}] has {len(base)} patch lines, expected {spec['base_patch_lines']}: "
                         "a different database version. Not building a widescreen group from it.")

    replace = {r["addr"].upper(): r for r in spec["replace"]}
    inserts = {i["after"].upper(): i for i in spec["insert_after"]}
    out_patches: list[str] = []
    seen: set[str] = set()
    for line in base:
        code, _, comment = line.partition("//")
        parts = [p.strip() for p in code.strip().split(",")]
        addr = parts[2].upper()
        if addr in replace:
            r = replace[addr]
            if parts[4].upper() != r["base"].upper():
                raise SystemExit(f"{addr} in [{spec['base_group']}] is {parts[4]}, expected {r['base']}; not building.")
            parts[4] = r["value"]
            note = f"{comment.strip()}; {r['note']}" if comment.strip() else r["note"]
            out_patches.append(",".join(parts) + f" // {note}")
            seen.add(addr)
        else:
            out_patches.append(line.strip())
        if addr in inserts:
            i = inserts[addr]
            out_patches.append(f"patch=1,EE,{i['addr']},word,{i['value']} // {i['note']}")
    missing = set(replace) - seen
    if missing:
        raise SystemExit(f"[{spec['base_group']}] lacks {sorted(missing)}; not building.")

    comment_lines = []
    for paragraph in spec["why"]:
        if comment_lines:
            comment_lines.append("//")
        comment_lines += ["// " + w for w in textwrap.wrap(paragraph, 84)]
    return comment_lines + [
        f"[{spec['name']}]",
        f"gsaspectratio={spec['gsaspectratio']}",
        f"author={spec['author']}",
        f"description={spec['description']}",
    ] + out_patches


def validate(block: list[str], name: str) -> None:
    problems = Pnach.parse("\n".join(block)).validate()
    if problems:
        raise SystemExit(f"[{name}] failed validation:\n  " + "\n  ".join(problems))


# --- files -----------------------------------------------------------------

def base_text() -> tuple[str, str]:
    user = config.patches_dir() / config.DB_PATCH_NAME
    if user.is_file():
        return user.read_text(encoding="utf-8", errors="replace"), str(user)
    zpath = config.patches_zip()
    if not zpath.is_file():
        raise SystemExit(f"No {user} and no {zpath}: cannot find PCSX2's patch for this game.")
    with zipfile.ZipFile(zpath) as z:
        try:
            return z.read(config.DB_PATCH_NAME).decode("utf-8", errors="replace"), f"{zpath}::{config.DB_PATCH_NAME}"
        except KeyError:
            raise SystemExit(f"{zpath} has no {config.DB_PATCH_NAME}.") from None


def newline_of(path: Path) -> str:
    return "\r\n" if path.is_file() and b"\r\n" in path.read_bytes() else "\n"


def edit_ini(text: str, enable: list[str], disable: list[str]) -> str:
    lines = text.splitlines()
    section = next((i for i, l in enumerate(lines) if l.strip().lower() == "[patches]"), None)
    if section is None:
        if lines and lines[-1].strip():
            lines.append("")
        lines += ["[Patches]"]
        section = len(lines) - 1
    end = next((i for i in range(section + 1, len(lines)) if lines[i].strip().startswith("[")), len(lines))
    body = lines[section + 1:end]
    enabled = {l.split("=", 1)[1].strip(): l for l in body if l.strip().lower().startswith("enable")}
    body = [l for l in body if not (l.strip().lower().startswith("enable") and l.split("=", 1)[1].strip() in disable)]
    insert_at = max((i for i, l in enumerate(body) if l.strip().lower().startswith("enable")), default=-1) + 1
    for name in enable:
        if name not in enabled:
            body.insert(insert_at, f"Enable = {name}")
            insert_at += 1
    return "\n".join(lines[:section + 1] + body + lines[end:]) + "\n"


def enabled_names(ini: Path) -> list[str]:
    if not ini.is_file():
        return []
    names, inside = [], False
    for line in ini.read_text(errors="replace").splitlines():
        s = line.strip()
        if s.startswith("["):
            inside = s.lower() == "[patches]"
        elif inside and s.lower().startswith("enable") and "=" in s:
            names.append(s.split("=", 1)[1].strip())
    return names


def backup(path: Path) -> Path | None:
    if not path.is_file():
        return None
    dest = config.WORK / "install-backups" / f"{path.name}.{datetime.now():%Y%m%d-%H%M%S}"
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, dest)
    return dest


def emulator_running() -> bool:
    try:
        from ps2ee.pine import Pine
        with Pine().connect():
            return True
    except Exception:  # noqa: BLE001 - any failure to connect means not running
        return False


# --- commands --------------------------------------------------------------

def status() -> int:
    text, source = base_text()
    lines = text.splitlines()
    ini = config.game_ini()
    enabled = enabled_names(ini)
    blocks = dict(our_blocks())
    print(f"PCSX2         {config.pcsx2_dir()}")
    print(f"patch file    {source}")
    print(f"game ini      {ini}")
    for name in [NEEDS, "Widescreen 16:9"] + list(blocks) + [WIDESCREEN]:
        found = block_range(lines, name)
        mark = "present" if found else "absent "
        print(f"  [{name}]  {mark}  {'enabled' if name in enabled else 'off'}")
    for name, block in blocks.items():
        found = block_range(lines, name)
        if found:
            same = patch_words(lines[found[0]:found[2]]) == patch_words(block)
            print(f"  [{name}] words match this repo: {same}")
    found = block_range(lines, WIDESCREEN)
    if found and block_range(lines, "Widescreen 16:9"):
        same = patch_words(lines[found[0]:found[2]]) == patch_words(widescreen_block(lines))
        print(f"  [{WIDESCREEN}] words match this repo: {same}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--widescreen", action="store_true", help=f"also build and enable [{WIDESCREEN}]")
    parser.add_argument("--enable-60fps", action="store_true", help="also enable PeterDelta's [60 FPS]")
    parser.add_argument("--remove", action="store_true", help="remove this project's groups")
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.status:
        return status()

    blocks = our_blocks()
    ours = [name for name, _ in blocks]
    everything = list(dict.fromkeys(ours + FORMER + [WIDESCREEN]))

    text, source = base_text()
    lines = text.splitlines()
    before = {name: (patch_words(lines[r[0]:r[2]]) if (r := block_range(lines, name)) else None) for name in everything}

    for name in everything:
        while remove_block(lines, name):
            pass

    enable: list[str] = []
    disable: list[str] = []
    if args.remove:
        disable = list(everything)
        print("removing this project's groups")
    else:
        if not block_range(lines, NEEDS):
            raise SystemExit(f"[{NEEDS}] is not in {source}; this project's groups need it.")
        combined: list[str] = []
        for name, block in blocks:
            validate(block, name)
            combined += block + [""]
            enable.append(name)
        insert_after(lines, NEEDS, combined[:-1])
        if args.enable_60fps:
            enable.append(NEEDS)
        disable += [n for n in FORMER if n not in ours]
        if args.widescreen:
            block = widescreen_block(lines)
            validate(block, WIDESCREEN)
            insert_after(lines, identity.REQUIRES[WIDESCREEN], block)
            enable.append(WIDESCREEN)
            disable.append(identity.REQUIRES[WIDESCREEN])

    lines = normalise_blank_lines(lines)
    patch_path = config.patches_dir() / config.DB_PATCH_NAME
    ini = config.game_ini()

    print(f"base          {source}")
    print(f"writes        {patch_path}")
    print(f"game ini      {ini}")
    for name in everything:
        found = block_range(lines, name)
        now = patch_words(lines[found[0]:found[2]]) if found else None
        if now is None and before[name] is None:
            continue
        change = ("unchanged" if now == before[name] else
                  "added" if before[name] is None else "removed" if now is None else "replaced")
        print(f"  [{name}]  {change}{'' if now is None else f'  ({len(now)} patch lines)'}")
    current = enabled_names(ini)
    print(f"  enable  {[n for n in enable if n not in current]}")
    print(f"  disable {[n for n in disable if n in current]}")
    if NEEDS not in current and NEEDS not in enable and not args.remove:
        print(f"  NOTE [{NEEDS}] is not enabled, so this project's groups will do nothing. Pass --enable-60fps.")

    if args.dry_run:
        print("\n(dry run - nothing written)")
        return 0

    for path in (patch_path, ini):
        saved = backup(path)
        if saved:
            print(f"  backup  {saved}")
    patch_nl = newline_of(patch_path)
    patch_path.parent.mkdir(parents=True, exist_ok=True)
    patch_path.write_bytes((patch_nl.join(lines) + patch_nl).encode("utf-8"))
    ini_nl = newline_of(ini)
    ini_text = ini.read_text(errors="replace") if ini.is_file() else ""
    new_ini = edit_ini(ini_text, enable, disable)
    if ini_nl != "\n":
        new_ini = new_ini.replace("\n", ini_nl)
    ini.parent.mkdir(parents=True, exist_ok=True)
    ini.write_bytes(new_ini.encode("utf-8"))
    print("written.")

    if emulator_running():
        # PINE cannot tell PCSX2 from another PINE server such as PCSXROO, so do not claim which.
        print("\n  !! A PINE server answered - if PCSX2 is running, quit and relaunch it:"
              " it reads patches and the game ini at boot.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
