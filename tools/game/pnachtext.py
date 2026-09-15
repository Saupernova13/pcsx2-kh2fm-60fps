"""Text-level pnach blocks, so other authors' groups survive an edit byte for byte.

ps2ee.pnach parses a pnach into groups and lines, which is right for validating
this project's own groups, but rendering it back drops what it does not model -
gsaspectratio, author, comment blocks, commented-out lines. The installer edits
PCSX2's database patch in place, so it works on lines instead: a group's block
is its header, everything up to the next group, and the paragraph of // comments
directly above the header.
"""

from __future__ import annotations

import re
from pathlib import Path

HEADER = re.compile(r"^\s*\[(.+?)\]\s*$")


def headers(lines: list[str]) -> list[tuple[int, str]]:
    return [(i, m.group(1)) for i, line in enumerate(lines) if (m := HEADER.match(line))]


def leading_comment_start(lines: list[str], header_index: int) -> int:
    start = header_index
    while start > 0 and lines[start - 1].lstrip().startswith("//"):
        start -= 1
    return start


def block_range(lines: list[str], name: str) -> tuple[int, int, int] | None:
    """(start incl. its comment paragraph, header index, end) of a named group."""
    hs = headers(lines)
    for n, (index, header_name) in enumerate(hs):
        if header_name != name:
            continue
        end = leading_comment_start(lines, hs[n + 1][0]) if n + 1 < len(hs) else len(lines)
        while end > index + 1 and not lines[end - 1].strip():
            end -= 1
        return leading_comment_start(lines, index), index, end
    return None


def remove_block(lines: list[str], name: str) -> bool:
    found = block_range(lines, name)
    if not found:
        return False
    start, _, end = found
    while end < len(lines) and not lines[end].strip():
        end += 1
    del lines[start:end]
    return True


def insert_after(lines: list[str], anchor: str, block: list[str]) -> None:
    found = block_range(lines, anchor)
    if not found:
        raise SystemExit(f"cannot place a group: [{anchor}] is not in the base patch file")
    lines[found[2]:found[2]] = [""] + block + [""]


def normalise_blank_lines(lines: list[str]) -> list[str]:
    out: list[str] = []
    for line in lines:
        if not line.strip() and out and not out[-1].strip():
            continue
        out.append(line)
    while out and not out[-1].strip():
        out.pop()
    return out


def patch_words(block: list[str]) -> list[tuple[str, str]]:
    """(address, value) as written, upper-cased, for every live patch= line."""
    words = []
    for line in block:
        text = line.split("//", 1)[0].strip()
        if text.startswith("patch="):
            parts = [p.strip() for p in text.split(",")]
            words.append((parts[2].upper(), parts[4].upper()))
    return words


def group_words(path: str | Path, name: str) -> list[tuple[int, int]]:
    """A group's word writes as (EE address, value), for writing live in PCSXROO."""
    lines = Path(path).read_text(encoding="utf-8", errors="replace").splitlines()
    found = block_range(lines, name)
    if not found:
        raise SystemExit(f"group [{name}] not found in {path}")
    words = []
    for line in lines[found[1] + 1:found[2]]:
        text = line.split("//", 1)[0].strip()
        if not text.startswith("patch="):
            continue
        parts = [p.strip() for p in text.split(",")]
        if parts[1].upper() != "EE" or parts[3].lower() != "word":
            raise SystemExit(f"[{name}] has a line that is not an EE word write: {line.strip()}")
        words.append((int(parts[2], 16) & 0x01FFFFFF, int(parts[4], 16)))
    if not words:
        raise SystemExit(f"group [{name}] in {path} has no patch lines")
    return words
