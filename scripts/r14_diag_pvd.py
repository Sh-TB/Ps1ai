#!/usr/bin/env python3
"""r14_diag_pvd.py — full structural dump of hello_pong_lic.bin's
volume descriptors (the KNOWN-BOOTABLE layout) vs our strict-ECMA
cs50x.iso (dropped to shell cube). Annotate every PVD field."""
import os
import struct

EMU = "/home/z/my-project/emu/games_homebrew"
RAW, DATA_OFF, SEC = 2352, 24, 2048


def user(f, lba):
    f.seek(lba * RAW + DATA_OFF)
    return f.read(SEC)


def pvd_fields(p):
    def le(o):
        return struct.unpack("<I", p[o:o + 4])[0]
    def be(o):
        return struct.unpack(">I", p[o:o + 4])[0]
    rows = [
        ("type", f"{p[0]}"), ("id", p[1:6].decode('ascii', 'replace')),
        ("version", f"{p[6]}"),
        ("system_id", p[8:40].split(b'\0')[0].decode('ascii', 'replace')),
        ("volume_id", p[40:72].split(b'\0')[0].decode('ascii', 'replace')),
        ("vol_space_size", f"le={le(80)} be={be(84)}"),
        ("vol_set_size", f"le={le(120)} be={be(124)}"),
        ("vol_seq_num", f"le={le(128)} be={le(132) if False else be(132)}"),
        ("log_block_size", f"le={le(136)} be={be(140)}"),
        ("path_table_size", f"le={le(144)} be={be(148)}"),
        ("L_path_table", f"{le(152)}"), ("opt_L_path", f"{le(156)}"),
        ("M_path_table", f"{be(160)}"), ("opt_M_path", f"{be(164)}"),
    ]
    for name, val in rows:
        print(f"   {name:16s} = {val}")
    # scan for plausible root dir records 140..220
    print("   -- dir-record scan in PVD --")
    for o in range(140, 220):
        ln = p[o]
        if 34 <= ln <= 40 and p[o + 1] == 0:
            ext = struct.unpack("<I", p[o + 2:o + 6])[0]
            sz = struct.unpack("<I", p[o + 10:o + 14])[0]
            flags = p[o + 25]
            nlen = p[o + 32]
            nm = p[o + 33:o + 33 + nlen]
            print(f"   @+{o}: len={ln} ext={ext} size={sz} flags={flags} "
                  f"name={nm!r}")


def main():
    f = open(os.path.join(EMU, "patched", "hello_pong_lic.bin"), "rb")
    print("===== hello_pong_lic.bin PVD (LBA16) =====")
    p = user(f, 16)
    assert p[1:6] == b"CD001"
    pvd_fields(p)
    print("\n   raw bytes 140..200:")
    print("   " + p[140:200].hex(" "))

    print("\n===== sector map 15..26 (first 12 bytes each) =====")
    for lba in range(15, 27):
        s = user(f, lba)
        print(f"   LBA {lba:3d}: {s[:12].hex(' ')}  "
              f"{'PVD/CD001' if s[1:6]==b'CD001' else ''}"
              f"{' terminator' if s[0]==0xFF else ''}"
              f"{' PS-X EXE' if s[:8]==b'PS-X EXE' else ''}"
              f"{' BOOT=' if s[:5]==b'BOOT ' else ''}")

    print("\n===== hello_pong SYSTEM.CNF (LBA23) =====")
    cnf = user(f, 23)
    print("   " + repr(cnf.split(b"\x00")[0]))

    print("\n===== cs50x.iso (strict-ECMA, FAILED) PVD =====")
    try:
        g = open(os.path.join(EMU, "cs50x.iso"), "rb")
        g.seek(16 * SEC)
        q = g.read(SEC)
        pvd_fields(q)
        print("\n   raw bytes 140..200:")
        print("   " + q[140:200].hex(" "))
        g.seek(20 * SEC)
        root = g.read(SEC)
        print("   strict root dir first 96 bytes:")
        print("   " + root[:96].hex(" "))
    except FileNotFoundError:
        print("   (cs50x.iso not found)")

    print("\n===== hello_pong root dir (LBA22) =====")
    d = user(f, 22)
    print("   " + d[:128].hex(" "))


if __name__ == "__main__":
    main()
