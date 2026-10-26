#!/usr/bin/env python3
"""r13_breakout_container.py — Round 13 fallback container for
psxBreakout: instead of booting the hand-rolled ISO9660 (OpenBIOS
falls back to the shell cube — research artifact kept as cs50x.iso),
we reuse the KNOWN-BOOTABLE hello_pong image structure and swap the
game payload:

  * parse hello_pong_lic.bin (MODE2/2352, user data at +24)
  * locate GAMEPS1.EXE;1 in the root dir
  * overwrite its extent bytes with cs50x.exe (+ zero tail)
  * patch the dirent size (LE+BE) to the new exe size
  * SYSTEM.CNF still boots GAMEPS1.EXE;1 -> loads our bytes (the
    PS-EXE header self-describes t_addr/t_size)

License sectors are already correct (copied from hello_pong_lic.bin,
which got them from the user's retail disc). Output:
patched/breakout_lic.bin + .cue. Game bytes stay out of VCS.
"""
import os
import shutil
import struct

EMU = "/home/z/my-project/emu/games_homebrew"
PATCHED = os.path.join(EMU, "patched")
SEC = 2048
RAW = 2352
DATA_OFF = 24                       # MODE2 form1 user data offset


def rd_user(f, lba):
    f.seek(lba * RAW + DATA_OFF)
    return f.read(SEC)


def find_root_record(pvd):
    """PSX builders deviate from ECMA-119 (hello_pong's PVD puts the
    root dir record at 156, not 168) — and the PSX BIOS reportedly
    reads it at the same nonstandard slot. Scan for a plausible 34-byte
    directory record instead of trusting one offset."""
    for o in range(80, 300):
        if pvd[o] not in (0x22, 0x26, 0x28) or pvd[o + 1] != 0:
            continue
        ext = struct.unpack("<I", pvd[o + 2:o + 6])[0]
        sz = struct.unpack("<I", pvd[o + 10:o + 14])[0]
        if 14 <= ext <= 60 and sz == 2048 and pvd[o + 25] == 2 \
                and pvd[o + 32] == 1:
            return o, ext, sz
    raise SystemExit("root dir record not found in PVD")


def main():
    src = os.path.join(PATCHED, "hello_pong_lic.bin")
    exe = open(os.path.join(EMU, "cs50x.exe"), "rb").read()
    assert exe[:8] == b"PS-X EXE"
    dst = os.path.join(PATCHED, "breakout_lic.bin")
    shutil.copyfile(src, dst)

    f = open(dst, "r+b")
    pvd = rd_user(f, 16)
    assert pvd[1:6] == b"CD001"
    rec_off, root_lba, root_size = find_root_record(pvd)
    print(f"root dir record at PVD+{rec_off}: lba={root_lba} "
          f"size={root_size}")

    d = rd_user(f, root_lba)
    off, target = 0, None
    while off < min(root_size, SEC):
        ln = d[off]
        if ln == 0:
            break
        nm = d[off + 33:off + 33 + d[off + 32]]
        if nm.upper().startswith(b"GAMEPS1.EXE"):
            target = (off, nm, struct.unpack("<I",
                                             d[off + 2:off + 6])[0],
                      struct.unpack("<I", d[off + 10:off + 14])[0])
        off += ln
    assert target, "GAMEPS1.EXE;1 not found"
    rec_off, nm, ext, old_size = target
    print(f"payload: {nm} ext={ext} old_size={old_size} "
          f"new_size={len(exe)}")
    import os as _os
    fsize = _os.path.getsize(dst)
    assert ext * RAW + DATA_OFF + len(exe) <= fsize, \
        "exe overwrite would exceed image"

    # ---- overwrite payload extent (may grow past the old exe: the
    # trailing bytes were hello_pong assets, unused by cs50x) ----
    f.seek(ext * RAW + DATA_OFF)
    f.write(exe)
    if old_size > len(exe):
        f.write(bytes(old_size - len(exe)))      # zero tail

    # ---- patch dirent size (LE + BE) ----
    rec_abs = root_lba * RAW + DATA_OFF + rec_off
    f.seek(rec_abs + 10)
    f.write(struct.pack("<I", len(exe)) + struct.pack(">I",
                                                      len(exe)))
    f.close()

    # ---- verify ----
    f = open(dst, "rb")
    check = rd_user(f, ext)
    assert check[:8] == b"PS-X EXE"
    assert len(check) >= min(len(exe), 2048)
    f.seek(root_lba * RAW + DATA_OFF + rec_off + 10)
    sz = f.read(8)
    assert struct.unpack("<I", sz[:4])[0] == len(exe)
    f.close()

    cue = dst.replace(".bin", ".cue")
    with open(cue, "w") as fh:
        fh.write('FILE "breakout_lic.bin" BINARY\n'
                 '  TRACK 01 MODE2/2352\n'
                 '    INDEX 01 00:00:00\n')
    import hashlib
    h = hashlib.sha256(open(dst, "rb").read()).hexdigest()
    print(f"container ready: {dst} ({os.path.getsize(dst)} bytes) "
          f"sha256={h}")
    print(f"cue: {cue}")


if __name__ == "__main__":
    main()
