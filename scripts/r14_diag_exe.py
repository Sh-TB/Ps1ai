#!/usr/bin/env python3
"""r14_diag_exe.py — compare PS-EXE headers: cs50x.exe (crashes) vs
hello_pong GAMEPS1.EXE (boots). Extract hello_pong's exe from its
license-patched image at the GAMEPS1.EXE extent."""
import os
import struct
import sys

import numpy as np

EMU = "/home/z/my-project/emu/games_homebrew"
PATCHED = os.path.join(EMU, "patched")
RAW, DATA_OFF, SEC = 2352, 24, 2048

FIELDS = [
    (0x00, 8, "magic", None),
    (0x10, 4, "pc0", "<I"),
    (0x14, 4, "pad2", "<I"),
    (0x18, 4, "t_addr", "<I"),
    (0x1C, 4, "t_size", "<I"),
    (0x20, 4, "d_addr?", "<I"),
    (0x24, 4, "d_size?", "<I"),
    (0x28, 4, "b_addr?", "<I"),
    (0x2C, 4, "b_size?", "<I"),
    (0x30, 4, "s_addr(stack)", "<I"),
    (0x34, 4, "s_size", "<I"),
    (0x38, 4, "saved_sp", "<I"),
    (0x3C, 4, "saved_fp", "<I"),
    (0x40, 4, "saved_gp", "<I"),
    (0x44, 4, "saved_ra", "<I"),
    (0x48, 4, "saved_s0", "<I"),
    (0x4C, 60, "region/license str", None),
]


def find_exe_extent(bin_path):
    f = open(bin_path, "rb")
    f.seek(16 * RAW + DATA_OFF)
    pvd = f.read(SEC)
    assert pvd[1:6] == b"CD001"
    # scan PVD for root dir record (PSX-flavored offset)
    root_lba = None
    for o in range(80, 300):
        if pvd[o] not in (0x22, 0x26, 0x28) or pvd[o + 1] != 0:
            continue
        ext = struct.unpack("<I", pvd[o + 2:o + 6])[0]
        sz = struct.unpack("<I", pvd[o + 10:o + 14])[0]
        if 14 <= ext <= 60 and sz == 2048 and pvd[o + 25] == 2:
            root_lba = ext
            print(f"root dir record at PVD+{o}: lba={root_lba}")
            break
    f.seek(root_lba * RAW + DATA_OFF)
    d = f.read(SEC)
    off, out = 0, []
    while off < SEC and d[off]:
        ln = d[off]
        nm = d[off + 33:off + 33 + d[off + 32]]
        ext = struct.unpack("<I", d[off + 2:off + 6])[0]
        size = struct.unpack("<I", d[off + 10:off + 14])[0]
        flags = d[off + 25]
        out.append((nm.decode("ascii", "replace"), ext, size, flags))
        off += ln
    print("root dir:", out)
    for nm, ext, size, fl in out:
        if nm.upper().startswith("GAMEPS1.EXE"):
            f.seek(ext * RAW + DATA_OFF)
            return f.read(size), nm, ext
    return None, None, None


def dump_header(tag, data):
    print(f"\n===== {tag} ({len(data)} bytes) =====")
    for off, ln, name, fmt in FIELDS:
        raw = data[off:off + ln]
        if fmt:
            val = struct.unpack(fmt, raw[:4])[0]
            print(f"  {name:18s} @{off:#04x} = {val:#010x}")
        else:
            txt = raw.split(b"\x00")[0].decode("ascii", "replace")
            print(f"  {name:18s} @{off:#04x} = {txt!r}")
    # nonzero map of the first 0x800 header + body start
    hdr = np.frombuffer(data[:0x800], dtype=np.uint8)
    nz = np.flatnonzero(hdr)
    print(f"  header nonzero bytes: {len(nz)}/{0x800}"
          + (f" (first {hex(int(nz[0]))} .. last {hex(int(nz[-1]))})"
             if len(nz) else ""))
    # body entropy sample
    body = data[0x800:]
    print(f"  body: {len(body)} bytes; nonzero {int((np.frombuffer(body, dtype=np.uint8) > 0).sum())}")


def disas_at(data, vaddr, n=28):
    import capstone
    md = capstone.Cs(capstone.CS_ARCH_MIPS, capstone.CS_MODE_MIPS32 +
                     capstone.CS_MODE_LITTLE_ENDIAN)
    # find file offset for vaddr: assume t_addr maps to 0x800 body
    t_addr = struct.unpack("<I", data[0x18:0x1C])[0]
    off = 0x800 + (vaddr - t_addr)
    if off < 0 or off >= len(data):
        print(f"  (vaddr {vaddr:#x} outside text)")
        return
    code = data[off:off + n * 4]
    print(f"  ---- disasm @ {vaddr:#x} (file off {off:#x}) ----")
    for ins in md.disasm(code, vaddr):
        print(f"   {ins.address:#010x}: {ins.mnemonic:10s} {ins.op_str}")


def main():
    cs = open(os.path.join(EMU, "cs50x.exe"), "rb").read()
    dump_header("cs50x.exe (psxBreakout — CRASHES)", cs)
    pc0 = struct.unpack("<I", cs[0x10:0x14])[0]
    disas_at(cs, pc0)

    hp, nm, ext = find_exe_extent(os.path.join(PATCHED, "hello_pong_lic.bin"))
    if hp:
        open(os.path.join(EMU, "hellopong_exe.extracted"), "wb").write(hp)
        dump_header(f"hello_pong {nm} (BOOTS)", hp)
        pc0h = struct.unpack("<I", hp[0x10:0x14])[0]
        disas_at(hp, pc0h)


if __name__ == "__main__":
    main()
