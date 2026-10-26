#!/usr/bin/env python3
"""Disassemble PSXMC worldGetBlock/chunkGetBlock to extract the exact
struct offsets (chunks array in World, blocks array in Chunk) for the
fixed infdev_2025_04_18 binary (Task 16-c FIX-2 groundwork)."""
import struct
import sys

ELF = "/home/z/my-project/emu/games_homebrew/PSXMC.elf"
BASE = 0x80010000  # text start per map
TARGETS = {
    "worldGetBlock": (0x80025C4C, 0x64),
    "chunkGetBlock": (0x8001C120, 0x80),
}

raw = open(ELF, "rb").read()
# PS1 PS-EXE style? Check magic
print("magic:", raw[:4])
# Try ELF program headers to map vaddr -> file offset
if raw[:4] == b"\x7fELF":
    e_phoff = struct.unpack_from("<I", raw, 0x1C)[0]
    e_phentsize = struct.unpack_from("<H", raw, 0x2A)[0]
    e_phnum = struct.unpack_from("<H", raw, 0x2C)[0]
    segs = []
    for i in range(e_phnum):
        off = e_phoff + i * e_phentsize
        p_type, p_offset, p_vaddr, p_paddr, p_filesz = struct.unpack_from(
            "<IIIII", raw, off)
        if p_type == 1:
            segs.append((p_vaddr, p_offset, p_filesz))
            print(f"PT_LOAD vaddr={p_vaddr:#x} off={p_offset:#x} "
                  f"filesz={p_filesz:#x}")
else:
    # PS-X EXE: text at 0x80010000, header 0x800 bytes
    print("tsize:", struct.unpack_from("<I", raw, 0x1C)[0])
    segs = [(0x80010000, 0x800, len(raw) - 0x800)]


def v2f(v):
    for va, off, sz in segs:
        if va <= v < va + sz:
            return off + (v - va)
    return None


from capstone import Cs, CS_ARCH_MIPS, CS_MODE_MIPS32  # noqa: E402

md = Cs(CS_ARCH_MIPS, CS_MODE_MIPS32)
for name, (va, sz) in TARGETS.items():
    f = v2f(va)
    if f is None:
        print(f"{name}: vaddr {va:#x} not mapped")
        continue
    print(f"=== {name} @ {va:#x} (file {f:#x}) ===")
    code = raw[f:f + sz]
    for ins in md.disasm(code, va):
        print(f"  {ins.address:#x}: {ins.mnemonic:9s} {ins.op_str}")
