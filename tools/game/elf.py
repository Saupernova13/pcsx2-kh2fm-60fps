"""Read the unpatched boot ELF by EE address - the ground truth for stock words.

Every static scan in docs/findings.md used these helpers, first inline and now
here. Addresses are EE addresses: the ELF loads at 00100000 with no relocation.
"""

from __future__ import annotations

import struct
from pathlib import Path

from game import config, identity

JR_RA = 0x03E00008

# Opcodes that take base+imm, by name.
BASE_OPS = {
    0x09: "addiu", 0x1E: "lq", 0x1F: "sq", 0x20: "lb", 0x21: "lh", 0x23: "lw", 0x24: "lbu",
    0x25: "lhu", 0x28: "sb", 0x29: "sh", 0x2B: "sw", 0x31: "lwc1", 0x36: "lqc2", 0x37: "ld",
    0x39: "swc1", 0x3E: "sqc2", 0x3F: "sd",
}
REG = ["zero", "at", "v0", "v1", "a0", "a1", "a2", "a3", "t0", "t1", "t2", "t3", "t4", "t5", "t6", "t7",
       "s0", "s1", "s2", "s3", "s4", "s5", "s6", "s7", "t8", "t9", "k0", "k1", "gp", "sp", "fp", "ra"]


def signed16(value: int) -> int:
    value &= 0xFFFF
    return value - 0x10000 if value & 0x8000 else value


def to_f32(word: int) -> float:
    return struct.unpack("<f", struct.pack("<I", word & 0xFFFFFFFF))[0]


def from_f32(value: float) -> int:
    return struct.unpack("<I", struct.pack("<f", value))[0]


class Elf:
    def __init__(self, path: str | Path | None = None):
        self.path = Path(path) if path else config.elf_path()
        if not self.path.is_file():
            raise SystemExit(f"{self.path} not found - run tools/extract-elf.py first")
        self.data = self.path.read_bytes()
        phoff, = struct.unpack_from("<I", self.data, 0x1C)
        phentsize, phnum = struct.unpack_from("<HH", self.data, 0x2A)
        self.segments: list[tuple[int, int, int]] = []
        for i in range(phnum):
            typ, off, vaddr, _paddr, filesz, _memsz, _flags, _align = struct.unpack_from(
                "<8I", self.data, phoff + i * phentsize)
            if typ == 1 and filesz:
                self.segments.append((vaddr, off, filesz))
        self.code_lo = identity.TEXT_BASE
        self.code_hi = identity.CODE_SCAN_END

    # --- words ---
    def word(self, addr: int) -> int:
        for vaddr, off, size in self.segments:
            if vaddr <= addr < vaddr + size:
                return struct.unpack_from("<I", self.data, off + addr - vaddr)[0]
        raise KeyError(f"{addr:08X} is not in a file-backed segment")

    def f32(self, addr: int) -> float:
        return to_f32(self.word(addr))

    def code(self):
        return range(self.code_lo, self.code_hi, 4)

    def data_words(self):
        """(addr, word) for every word above the code scan boundary."""
        for vaddr, off, size in self.segments:
            lo = max(vaddr, self.code_hi)
            for a in range(lo, vaddr + size - 3, 4):
                yield a, struct.unpack_from("<I", self.data, off + a - vaddr)[0]

    # --- functions ---
    def function_start(self, addr: int) -> int:
        a = addr & ~3
        while a > self.code_lo + 8 and self.word(a - 8) != JR_RA:
            a -= 4
        return a

    def function_end(self, start: int) -> int:
        a = start
        while self.word(a) != JR_RA:
            a += 4
        return a + 8

    def function_starts(self) -> dict[int, int]:
        """Instruction address -> start of the function it sits in (previous jr ra + delay)."""
        starts, current = {}, self.code_lo
        for a in self.code():
            if a >= self.code_lo + 8 and self.word(a - 8) == JR_RA:
                current = a
            starts[a] = current
        return starts

    # --- references ---
    def absolute_refs(self, targets, window: int = 12) -> list[tuple[int, str, int]]:
        """(site, op, address) for every lui-paired base+imm that resolves into targets."""
        wanted = set(targets)
        found = []
        for a in self.code():
            x = self.word(a)
            if (x >> 26) != 0x0F:
                continue
            rt, hi = (x >> 16) & 31, x & 0xFFFF
            for k in range(1, window):
                b = a + 4 * k
                if b >= self.code_hi:
                    break
                v = self.word(b)
                op = v >> 26
                if op in BASE_OPS and ((v >> 21) & 31) == rt:
                    ea = ((hi << 16) + signed16(v)) & 0xFFFFFFFF
                    if ea in wanted:
                        found.append((b, BASE_OPS[op], ea))
                if op == 0x0F and ((v >> 16) & 31) == rt:
                    break
        return found

    def refs_in_range(self, lo: int, hi: int, window: int = 12) -> list[tuple[int, str, int]]:
        found = []
        for a in self.code():
            x = self.word(a)
            if (x >> 26) != 0x0F:
                continue
            rt, h = (x >> 16) & 31, x & 0xFFFF
            for k in range(1, window):
                b = a + 4 * k
                if b >= self.code_hi:
                    break
                v = self.word(b)
                op = v >> 26
                if op in BASE_OPS and ((v >> 21) & 31) == rt:
                    ea = ((h << 16) + signed16(v)) & 0xFFFFFFFF
                    if lo <= ea < hi:
                        found.append((b, BASE_OPS[op], ea))
                if op == 0x0F and ((v >> 16) & 31) == rt:
                    break
        return found

    def branch_target(self, a: int) -> int | None:
        x = self.word(a)
        op = x >> 26
        if op in (0x02, 0x03):
            return ((a + 4) & 0xF0000000) | ((x & 0x03FFFFFF) << 2)
        rt = (x >> 16) & 31
        if (op in (0x04, 0x05, 0x06, 0x07, 0x14, 0x15, 0x16, 0x17)
                or (op == 0x01 and rt in (0, 1, 2, 3, 16, 17, 18, 19))
                or (op == 0x11 and ((x >> 21) & 31) == 8)):
            return a + 4 + (signed16(x) << 2)
        return None

    def jumps_to(self, target: int) -> list[tuple[int, str]]:
        out = []
        for a in self.code():
            x = self.word(a)
            if (x >> 26) in (0x02, 0x03) and ((x & 0x03FFFFFF) << 2) == target:
                out.append((a, "jal" if (x >> 26) == 3 else "j"))
        return out

    def data_pointers(self, value: int) -> list[int]:
        return [a for vaddr, off, size in self.segments
                for a in range(vaddr, vaddr + size - 3, 4)
                if struct.unpack_from("<I", self.data, off + a - vaddr)[0] == value]

    def offset_uses(self, offsets, skip_bases=("sp", "gp", "zero")) -> dict[int, list[str]]:
        """Functions whose instructions use base+imm with imm in offsets, by function start."""
        wanted = set(offsets)
        starts = self.function_starts()
        by_function: dict[int, list[str]] = {}
        for a in self.code():
            x = self.word(a)
            op = x >> 26
            if op in BASE_OPS and (x & 0xFFFF) in wanted:
                base = REG[(x >> 21) & 31]
                if base in skip_bases:
                    continue
                rt = (x >> 16) & 31
                reg = f"f{rt}" if op in (0x31, 0x39) else f"vf{rt}" if op in (0x36, 0x3E) else REG[rt]
                by_function.setdefault(starts[a], []).append(
                    f"{a:08X} {BASE_OPS[op]:5s} {reg}, 0x{x & 0xFFFF:X}({base})")
        return by_function
