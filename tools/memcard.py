"""List the saves on a PS2 memory card image, and pull a file out. Read-only, offline.

    python tools/memcard.py "<PCSX2>/memcards/Mcd001.ps2"                 # every directory and file
    python tools/memcard.py Mcd002.ps2 --grep 66675                          # KH2FM saves only
    python tools/memcard.py Mcd002.ps2 --extract BISLPM-66675FM00/BISLPM-66675FM00 --out work/save.bin

The standard PS2 memory card filesystem, as PCSX2 writes it: a superblock at
page 0 ("Sony PS2 Memory Card Format"), 512-byte pages with 16 spare ECC bytes
each when the card flags say so, 1024-byte clusters, a two-level FAT (indirect
clusters listed in the superblock, FAT entries with bit 31 = in use and the low
31 bits = next cluster), and 512-byte directory entries (mode, length, first
cluster, name at +0x40). Files and directories are chained through the FAT from
their first cluster, counted from the superblock's alloc_offset.

It exists to find which save states can be made: the user's KH2 saves say which
worlds, fights and minigames this project can reach for its A/B sweeps.
"""

from __future__ import annotations

import argparse
import struct
import sys
from pathlib import Path

MAGIC = b"Sony PS2 Memory Card Format "
DF_DIRECTORY = 0x0020
DF_FILE = 0x0010
DF_EXISTS = 0x8000


class Card:
    def __init__(self, path: Path):
        self.data = path.read_bytes()
        if not self.data.startswith(MAGIC):
            raise SystemExit(f"{path}: not a PS2 memory card image")
        (self.page_len, self.pages_per_cluster, self.pages_per_block, _, self.clusters_per_card,
         self.alloc_offset, self.alloc_end, self.rootdir_cluster) = struct.unpack_from("<HHHHIIII", self.data, 0x28)
        self.ifc_list = struct.unpack_from("<32I", self.data, 0x50)
        self.card_flags = self.data[0x151]
        spare = 16 if self.card_flags & 1 else 0
        # Some images carry spares even when the flag reads otherwise; trust the file size.
        pages = self.clusters_per_card * self.pages_per_cluster
        if len(self.data) == pages * (self.page_len + 16):
            spare = 16
        elif len(self.data) == pages * self.page_len:
            spare = 0
        self.spare = spare
        self.cluster_len = self.page_len * self.pages_per_cluster
        self.entries_per_cluster = self.cluster_len // 4

    def cluster(self, n: int) -> bytes:
        out = bytearray()
        for p in range(self.pages_per_cluster):
            off = (n * self.pages_per_cluster + p) * (self.page_len + self.spare)
            out += self.data[off:off + self.page_len]
        return bytes(out)

    def fat(self, n: int) -> int:
        per = self.entries_per_cluster
        ifc = self.ifc_list[(n // per) // per]
        fat_cluster = struct.unpack_from("<I", self.cluster(ifc), ((n // per) % per) * 4)[0]
        return struct.unpack_from("<I", self.cluster(fat_cluster), (n % per) * 4)[0]

    def chain(self, first: int) -> list[int]:
        out, n = [], first
        for _ in range(self.clusters_per_card):
            out.append(n)
            entry = self.fat(n)
            if entry & 0x80000000 == 0:
                break
            nxt = entry & 0x7FFFFFFF
            if nxt == 0x7FFFFFFF:
                break
            n = nxt
        return out

    def read_chain(self, first: int, length: int) -> bytes:
        data = b"".join(self.cluster(self.alloc_offset + c) for c in self.chain(first))
        return data[:length]

    def entries(self, first: int, count: int) -> list[dict]:
        raw = self.read_chain(first, count * 512)
        out = []
        for i in range(count):
            e = raw[i * 512:(i + 1) * 512]
            if len(e) < 512:
                break
            mode, _, length = struct.unpack_from("<HHI", e, 0)
            created = e[8:16]
            cluster = struct.unpack_from("<I", e, 0x10)[0]
            modified = e[0x18:0x20]
            name = e[0x40:0x60].split(b"\0", 1)[0].decode("latin-1")
            out.append({"mode": mode, "length": length, "cluster": cluster, "name": name,
                        "created": stamp(created), "modified": stamp(modified)})
        return out

    def walk(self):
        root = self.entries(self.rootdir_cluster, 1)[0]
        for d in self.entries(self.rootdir_cluster, root["length"])[2:]:
            if not d["mode"] & DF_EXISTS or not d["mode"] & DF_DIRECTORY:
                continue
            files = [f for f in self.entries(d["cluster"], d["length"])[2:] if f["mode"] & DF_EXISTS]
            yield d, files


def stamp(b: bytes) -> str:
    _, sec, minute, hour, day, month, year = struct.unpack("<BBBBBBH", b)
    return f"{year:04d}-{month:02d}-{day:02d} {hour:02d}:{minute:02d}:{sec:02d}"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("card")
    ap.add_argument("--grep", default="")
    ap.add_argument("--extract", default="", help="DIR/FILE to write out")
    ap.add_argument("--out", default="")
    args = ap.parse_args()

    card = Card(Path(args.card))
    if args.extract:
        want_dir, want_file = args.extract.split("/", 1)
        for d, files in card.walk():
            if d["name"] == want_dir:
                for f in files:
                    if f["name"] == want_file:
                        Path(args.out).write_bytes(card.read_chain(f["cluster"], f["length"]))
                        print(f"wrote {args.out} ({f['length']} bytes)")
                        return 0
        raise SystemExit(f"{args.extract} not found")

    print(f"{args.card}: {card.clusters_per_card} clusters, spare {card.spare}, alloc_offset {card.alloc_offset}")
    for d, files in card.walk():
        if args.grep and args.grep not in d["name"]:
            continue
        print(f"{d['name']:<32} modified {d['modified']}")
        for f in files:
            print(f"    {f['name']:<28} {f['length']:>8}  {f['modified']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
