#!/usr/bin/env python3
"""Verify the identity of the downloaded PS1 disc image.

Checks:
1. MD5 + SHA1 of the .bin
2. ISO9660 parse -> find SYSTEM.CNF -> BOOT=cdrom:SLUS_012.12?
3. Extract SLUS_012.12 PS-EXE -> serial/region strings
4. Compare extracted exe against repo's ps1play/re/SLUS_012.12
5. Track listing vs .cue
"""
import hashlib
import struct
import sys

import os
BIN = os.environ.get("DISC_BIN", "/home/z/my-project/emu/msx_usa/Metal Slug X (USA).bin")
REPO_EXE = "/home/z/my-project/ps1ai/ps1play/re/SLUS_012.12"


def md5sha1(path):
    h1, h2 = hashlib.md5(), hashlib.sha1()
    with open(path, "rb") as f:
        for c in iter(lambda: f.read(1 << 22), b""):
            h1.update(c), h2.update(c)
    return h1.hexdigest(), h2.hexdigest()


SECTOR = 2352  # RAW MODE2/2352 (Redump standard)
DATA_OFF = 24  # 12 sync + 4 header + 8 subheader


def iso9660_pvd(f):
    f.seek(0)
    sync = f.read(12)
    assert sync == b"\x00" + b"\xff" * 10 + b"\x00", f"not RAW2352: {sync.hex()}"
    for sector in range(16, 20):
        f.seek(sector * SECTOR + DATA_OFF)
        d = f.read(2048)
        if d[1:6] == b"CD001" and d[0] == 1:
            return d
    return None


def iso_root(pvd):
    root = pvd[156:190]
    lba = struct.unpack("<I", root[2:6])[0]
    size = struct.unpack("<I", root[10:14])[0]
    return lba, size


def list_dir(f, lba, size):
    f.seek(lba * SECTOR + DATA_OFF)
    data = f.read(size)
    out = {}
    i = 0
    while i < len(data):
        ln = data[i]
        if ln == 0:
            i = (i // 2048 + 1) * 2048
            continue
        rec = data[i:i + ln]
        ext_lba = struct.unpack("<I", rec[2:6])[0]
        fsize = struct.unpack("<I", rec[10:14])[0]
        flags = rec[25]
        name_len = rec[32]
        name = rec[33:33 + name_len]
        if name in (b"\x00", b"\x01"):
            i += ln
            continue
        out[name.decode("ascii", "replace")] = (ext_lba, fsize, flags)
        i += ln
    return out


def main():
    md5, sha1 = md5sha1(BIN)
    print("BIN md5 :", md5)
    print("BIN sha1:", sha1)

    with open(BIN, "rb") as f:
        pvd = iso9660_pvd(f)
        assert pvd, "no PVD found"
        volid = pvd[40:72].decode("ascii", "replace").rstrip()
        print("Volume ID:", repr(volid))
        rlba, rsize = iso_root(pvd)
        root = list_dir(f, rlba, rsize)
        for name, (lba, size, flags) in sorted(root.items()):
            print(f"  root/{name:20s} lba={lba:6d} size={size}")

        # SYSTEM.CNF
        cnf = None
        for cand in ("SYSTEM.CNF", "SYSTEM.CNF;1"):
            if cand in root:
                lba, size, _ = root[cand]
                f.seek(lba * SECTOR + DATA_OFF)
                cnf = f.read(size).decode("ascii", "replace")
        print("--- SYSTEM.CNF ---")
        print(cnf.strip() if cnf else "NOT FOUND")

        # license string area (sector 4, ISO layer) for region
        f.seek(4 * SECTOR + DATA_OFF)
        lic = f.read(120)
        print("--- license area (sec4) ---")
        print(repr(lic[:100]))

        # main exe
        exe = None
        for cand in ("SLUS_012.12", "SLUS_012.12;1"):
            if cand in root:
                lba, size, _ = root[cand]
                f.seek(lba * SECTOR + DATA_OFF)
                exe = f.read(size)
        if exe:
            open("/home/z/my-project/emu/msx_usa/SLUS_012.12.extracted", "wb").write(exe)
            print(f"SLUS_012.12: {len(exe)} bytes, "
                  f"md5={hashlib.md5(exe).hexdigest()}")
            print("  PSX-EXE magic:", exe[:8])
            pc0 = struct.unpack('<I', exe[12:16])[0]
            t_addr = struct.unpack('<I', exe[20:24])[0]
            t_size = struct.unpack('<I', exe[24:28])[0]
            print(f"  pc0=0x{pc0:08x} t_addr=0x{t_addr:08x} t_size={t_size}")
        # compare to repo exe
        try:
            repo = open(REPO_EXE, "rb").read()
            same = (repo == exe)
            print(f"repo exe: {len(repo)} bytes, identical={same}")
        except FileNotFoundError:
            print("repo exe not found")

    # cue content
    cue = open(os.environ.get("DISC_CUE", BIN.replace(".bin", ".cue"))).read()
    print("--- CUE ---")
    print(cue)


if __name__ == "__main__":
    main()
