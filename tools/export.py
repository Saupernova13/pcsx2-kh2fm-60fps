"""Cut a release: patch/kh2fm-60fps.pnach is wip/working.pnach minus the groups that never ship.

    python tools/export.py --check                 # does patch/ match what working.pnach ships?
    python tools/export.py --release v03-something # refresh patch/ (needs docs/versions/v03-something.md)

working.pnach holds only this project's groups, including experiments that must
never be installed (identity.NEVER_SHIP). This drops those, block and comment
paragraph together, and writes everything else unchanged. The widescreen retarget
is not a group in either file - it ships as patch/widescreen-19.5x9-s24.json,
because it is ElHecht's hack with five words changed and is built at install time.

--release refuses to run without a version note, so the history cannot lapse.
Tag the commit to match: git tag -a v03-something -m "..."
"""

from __future__ import annotations

import argparse
import sys

import _bootstrap  # noqa: F401

from game import config, identity
from game.pnachtext import block_range, normalise_blank_lines

OUT = config.PATCHES / "kh2fm-60fps.pnach"


def build() -> str:
    lines = (config.WIP / "working.pnach").read_text(encoding="utf-8").splitlines()
    for name in identity.NEVER_SHIP:
        found = block_range(lines, name)
        if found:
            start, _, end = found
            while end < len(lines) and not lines[end].strip():
                end += 1
            del lines[start:end]
    return "\n".join(normalise_blank_lines(lines)) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--release", metavar="NAME")
    args = parser.parse_args()
    text = build()

    if args.release:
        note = config.REPO / "docs" / "versions" / f"{args.release}.md"
        if not note.is_file():
            print(f"REFUSING: write {note} first - what this version changes and what was discovered.")
            return 1
        OUT.write_text(text, encoding="utf-8", newline="\n")
        print(f"wrote {OUT}; now: git tag -a {args.release} -m \"{args.release}: <one line from the note>\"")
        return 0

    current = OUT.read_text(encoding="utf-8") if OUT.is_file() else ""
    same = current == text
    print(f"{OUT} {'matches' if same else 'DIFFERS FROM'} wip/working.pnach minus {identity.NEVER_SHIP}")
    if not same and args.check:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
