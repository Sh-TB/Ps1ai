#!/usr/bin/env python3
"""r13_new_games.py — Round 13: add TWO new homebrew games.

  1. psxBreakout (NDR008/psxBreakout v1.0, cs50x.exe 78 KB PS-EXE) —
     the new TINY game. Ships as a bare PS-EXE, so this script BUILDS a
     minimal ISO9660 image (SYSTEM.CNF BOOT + the EXE), wraps it into a
     MODE2/2352 BIN and applies the local license-sector patch.
  2. Cave Story PSX (fgsfdsfgs/doukutsupsx v0.7, doukutsu_r7_us.iso) —
     the NEXT finish-target (a real full game). Ships as a plain .iso.

Policy: game bytes stay OUT of VCS (emu/games_homebrew is untracked);
manifest gets metadata + sha256 only. License sectors come from the
user's OWN local retail disc image (same legality note as
scripts/make_homebrew_lic.py — local workspace only).
"""
from __future__ import annotations

import hashlib
import os
import struct
import sys
import urllib.request

EMU = "/home/z/my-project/emu/games_homebrew"
PATCHED = os.path.join(EMU, "patched")
RETAIL_BIN = os.environ.get(
    "M1_RETAIL_BIN",
    "/home/z/my-project/emu/game/Metal Slug X (USA).bin")
SEC = 2048

BREAKOUT_URL = ("https://github.com/NDR008/psxBreakout/releases/"
                "download/v1.0/cs50x.exe")
DOUKUTSU_URL = ("https://github.com/fgsfdsfgs/doukutsupsx/releases/"
                "download/v0.7/doukutsu_r7_us.iso")

SYSTEM_CNF = (b"BOOT = cdrom:\\CS50X.EXE;1\r\n"
              b"TCB = 4\r\n"
              b"Event = 10\r\n"
              b"Stack = 801FFF00\r\n")


def sha256(b):
    return hashlib.sha256(b).hexdigest()


def download(url, dest):
    if os.path.exists(dest):
        print(f"cached: {dest}")
        return
    print(f"downloading {url}")
    urllib.request.urlretrieve(url, dest + ".part")
    os.rename(dest + ".part", dest)


def to_bcd(n):
    return ((n // 10) << 4) | (n % 10)


def msf_bcd(lba):
    m, rem = divmod(lba + 150, 75 * 60)
    s, f = divmod(rem, 75)
    return bytes([to_bcd(m), to_bcd(s), to_bcd(f)])


def dir_record(name, extent, size, flags=0):
    """ISO9660 directory record (both-endian numbers, zero dates)."""
    nm = name.encode("ascii")
    rec = bytearray()
    rec += bytes([33 + len(nm), 0])                    # len, ext attr
    rec += struct.pack("<I", extent) + struct.pack(">I", extent)
    rec += struct.pack("<I", size) + struct.pack(">I", size)
    rec += bytes(7)                                    # date
    rec += bytes([flags, 0, 0])                        # flags, unit, ilv
    rec += struct.pack("<H", 1) + struct.pack(">H", 1)  # volume seq
    rec += bytes([len(nm)]) + nm
    if len(rec) % 2:
        rec += b"\x00"
    return bytes(rec)


def build_breakout_iso():
    """Minimal ISO9660 (2048 B sectors): LBA16 PVD, 17 terminator,
    18/19 path tables, 20 root dir, 21+ file extents."""
    exe = open(os.path.join(EMU, "cs50x.exe"), "rb").read()
    assert exe[:8] == b"PS-X EXE", f"not a PS-EXE: {exe[:8]!r}"
    files = [("SYSTEM.CNF", SYSTEM_CNF), ("CS50X.EXE", exe)]

    # --- layout ---
    root_lba, pt_l, pt_m = 20, 18, 19
    extents, lba = [], 21
    for nm, data in files:
        extents.append((nm, lba, len(data)))
        lba += (len(data) + SEC - 1) // SEC
    total = lba

    img = bytearray(total * SEC)

    # --- path tables (root only) ---
    pt = bytes([1, 0]) + struct.pack("<I", root_lba) + \
        struct.pack("<H", 1) + b"\x00" + b"\x00"
    img[pt_l * SEC:pt_l * SEC + len(pt)] = pt
    pt_be = bytes([1, 0]) + struct.pack(">I", root_lba) + \
        struct.pack(">H", 1) + b"\x00" + b"\x00"
    img[pt_m * SEC:pt_m * SEC + len(pt_be)] = pt_be
    pt_size = len(pt)

    # --- root directory extent ---
    rd = bytearray()
    rd += dir_record("\x00", root_lba, SEC, flags=2)      # "."
    rd += dir_record("\x01", root_lba, SEC, flags=2)      # ".."
    for nm, ext, size in extents:
        rd += dir_record(nm + ";1", ext, size)
    img[root_lba * SEC:root_lba * SEC + len(rd)] = rd

    # --- file data ---
    for nm, ext, size in extents:
        data = SYSTEM_CNF if nm == "SYSTEM.CNF" else exe
        img[ext * SEC:ext * SEC + len(data)] = data

    # --- PVD ---
    pvd = bytearray(SEC)
    pvd[0] = 1
    pvd[1:6] = b"CD001"
    pvd[6] = 1
    pvd[8:40] = b"PLAYSTATION".ljust(32)
    pvd[40:72] = b"CS50X_BREAKOUT".ljust(32)
    pvd[80:88] = struct.pack("<I", total) + struct.pack(">I", total)
    pvd[120:128] = struct.pack("<I", 1) + struct.pack(">I", 1)
    pvd[128:136] = struct.pack("<I", 1) + struct.pack(">I", 1)
    pvd[136:144] = struct.pack("<I", SEC) + struct.pack(">I", SEC)
    pvd[144:152] = struct.pack("<I", pt_size) + \
        struct.pack(">I", pt_size)
    pvd[152:156] = struct.pack("<I", pt_l)          # L path table
    pvd[156:160] = struct.pack("<I", 0)             # optional L
    pvd[160:164] = struct.pack(">I", pt_m)          # M path table (BE)
    pvd[164:168] = struct.pack(">I", 0)             # optional M
    pvd[168:202] = dir_record("\x00", root_lba, SEC, flags=2)
    pvd[881] = 1
    img[16 * SEC:17 * SEC] = pvd
    term = bytearray(SEC)
    term[0] = 0xFF
    term[1:6] = b"CD001"
    term[6] = 1
    img[17 * SEC:18 * SEC] = term

    # --- round-trip sanity ---
    assert img[16 * SEC + 1:16 * SEC + 6] == b"CD001"
    exe_off = extents[1][1] * SEC
    assert img[exe_off:exe_off + 8] == b"PS-X EXE"
    return bytes(img)


def wrap_mode2_2352(user_2048):
    """Wrap 2048-byte user sectors into MODE2/2352 raw sectors
    (sync + MSF header + data subheader + 2048 data + zero EDC/ECC)."""
    n = len(user_2048) // SEC
    out = bytearray()
    for lba in range(n):
        out += b"\x00" + b"\xff" * 10 + b"\x00"
        out += msf_bcd(lba) + b"\x02"
        out += bytes([0, 0, 0x08, 0, 0, 0, 0x08, 0])
        out += user_2048[lba * SEC:(lba + 1) * SEC]
        out += bytes(280)                       # EDC + ECC (unchecked by emu)
    assert len(out) == n * 2352
    return bytes(out)


def apply_license(raw2352, tag):
    """Overwrite sectors 0..15 with the retail license sectors (raw
    2352-byte domain, exactly like make_homebrew_lic.py)."""
    lic = open(RETAIL_BIN, "rb").read(16 * 2352)
    if b"Sony Computer Entertainment" not in lic:
        raise SystemExit("retail license signature missing — wrong file?")
    b = bytearray(raw2352)
    assert len(b) >= 16 * 2352, "image too small for license area"
    b[0:16 * 2352] = lic
    dst = os.path.join(PATCHED, f"{tag}_lic.bin")
    with open(dst, "wb") as f:
        f.write(b)
    cue = dst.replace(".bin", ".cue")
    with open(cue, "w") as f:
        f.write(f'FILE "{tag}_lic.bin" BINARY\n'
                '  TRACK 01 MODE2/2352\n'
                '    INDEX 01 00:00:00\n')
    print(f"{tag}: {len(b)} bytes -> {dst} (+cue) sha256={sha256(b)[:16]}..")
    return dst, sha256(b)


def main():
    os.makedirs(PATCHED, exist_ok=True)
    out = {}

    # ---- 1. psxBreakout ----
    download(BREAKOUT_URL, os.path.join(EMU, "cs50x.exe"))
    exe = open(os.path.join(EMU, "cs50x.exe"), "rb").read()
    iso = build_breakout_iso()
    open(os.path.join(EMU, "cs50x.iso"), "wb").write(iso)
    raw = wrap_mode2_2352(iso)
    open(os.path.join(EMU, "cs50x.bin"), "wb").write(raw)
    p, h = apply_license(raw, "cs50x")
    out["psxBreakout"] = {
        "source": BREAKOUT_URL, "repo": "NDR008/psxBreakout",
        "license": "unknown (public release, CS50 final project)",
        "exe_sha256": sha256(exe), "bin_sha256": h,
        "bin_bytes": len(raw), "built_locally": True}

    # ---- 2. Cave Story PSX ----
    dst = os.path.join(EMU, "doukutsu_r7_us.iso")
    download(DOUKUTSU_URL, dst)
    iso2 = open(dst, "rb").read()
    size = len(iso2)
    print(f"doukutsu iso: {size} bytes  %2048={size % 2048}  "
          f"%2352={size % 2352}")
    if size % 2352 == 0 and size % 2048 != 0:
        raw2 = iso2                        # already raw 2352
        assert raw2[16 * 2352 + 25:16 * 2352 + 30] == b"CD001"
    else:
        assert size % 2048 == 0, "unexpected iso size"
        assert iso2[16 * 2048 + 1:16 * 2048 + 6] == b"CD001"
        raw2 = wrap_mode2_2352(iso2)
        open(os.path.join(EMU, "doukutsu.bin"), "wb").write(raw2)
    p2, h2 = apply_license(raw2, "doukutsu")
    out["doukutsupsx"] = {
        "source": DOUKUTSU_URL, "repo": "fgsfdsfgs/doukutsupsx",
        "release": "v0.7 (2022-10-13), MIT (port), Cave Story (c) Pixel",
        "iso_sha256": sha256(iso2), "bin_sha256": h2,
        "bin_bytes": len(raw2)}

    import json
    with open(os.path.join(EMU, "r13_new_games.json"), "w") as f:
        json.dump(out, f, indent=2)
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
