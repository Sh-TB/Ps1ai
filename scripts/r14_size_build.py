#!/usr/bin/env python3
"""r14_size_build.py — build hello_pong variants with PADDED exe bodies
to empirically find the OpenBIOS shell's exe-load size cliff.

Base: hello_pong GAMEPS1.EXE (t_size 0x7000 = 14 sectors, boots).
Variants: pad the BODY with zeros to t_size in {0x8000, 0x9000, 0xA000,
0xC000, 0x10000, 0x11000, 0x13000} sectors-worth, patch t_size (+0x1C)
and the root dirent size, write into a copy of hello_pong_lic.bin.

The padding is inert: the game's own code/data range is unchanged; the
extra bytes land in unused RAM above the original image.
"""
import os
import struct

EMU = "/home/z/my-project/emu/games_homebrew"
PATCHED = os.path.join(EMU, "patched")
RAW, DATA_OFF, SEC = 2352, 24, 2048

SRC = os.path.join(PATCHED, "hello_pong_lic.bin")
EXE = open(os.path.join(EMU, "hellopong_exe.extracted"), "rb").read()
assert EXE[:8] == b"PS-X EXE"
ORIG_TSIZE = struct.unpack("<I", EXE[0x1C:0x20])[0]
ORIG_FSIZE = 30720                      # dirent size on disc


def rd_user(f, lba):
    f.seek(lba * RAW + DATA_OFF)
    return f.read(SEC)


def find_payload(f):
    pvd = rd_user(f, 16)
    root_lba = None
    for o in range(80, 300):
        if pvd[o] not in (0x22, 0x26, 0x28) or pvd[o + 1] != 0:
            continue
        ext = struct.unpack("<I", pvd[o + 2:o + 6])[0]
        sz = struct.unpack("<I", pvd[o + 10:o + 14])[0]
        if 14 <= ext <= 60 and sz == 2048 and pvd[o + 25] == 2:
            root_lba = ext
            break
    d = rd_user(f, root_lba)
    off, out = 0, None
    while off < SEC and d[off]:
        ln = d[off]
        nm = d[off + 33:off + 33 + d[off + 32]]
        if nm.upper().startswith(b"GAMEPS1.EXE"):
            out = (root_lba, off, struct.unpack("<I", d[off + 2:off + 6])[0],
                   struct.unpack("<I", d[off + 10:off + 14])[0])
        off += ln
    return out


def build(tsize):
    tag = f"hellopong_pad{tsize//1024}K"
    dst = os.path.join(PATCHED, f"{tag}.bin")
    body = EXE[0x800:0x800 + ORIG_TSIZE] + \
        bytes(tsize - ORIG_TSIZE)          # zero padding to target t_size
    exe = EXE[:0x800] + body
    with open(dst, "wb") as g:
        g.write(open(SRC, "rb").read())
    f = open(dst, "r+b")
    root_lba, rec_off, ext, old_size = find_payload(f)
    assert old_size == ORIG_FSIZE, old_size
    # sanity: room in image
    import os as _os
    assert ext * RAW + DATA_OFF + len(exe) <= _os.path.getsize(dst), "no room"
    # patch t_size in the on-disc exe header
    f.seek(ext * RAW + DATA_OFF + 0x1C)
    f.write(struct.pack("<I", tsize))
    # write body after header
    f.seek(ext * RAW + DATA_OFF + 0x800)
    f.write(body)
    # patch dirent size LE+BE
    f.seek(root_lba * RAW + DATA_OFF + rec_off + 10)
    f.write(struct.pack("<I", len(exe)) + struct.pack(">I", len(exe)))
    f.close()
    # verify
    f = open(dst, "rb")
    hdr = rd_user(f, ext)
    assert hdr[:8] == b"PS-X EXE"
    ts = struct.unpack("<I", hdr[0x1C:0x20])[0]
    f.close()
    with open(dst.replace(".bin", ".cue"), "w") as c:
        c.write(f'FILE "{tag}.bin" BINARY\n'
                '  TRACK 01 MODE2/2352\n'
                '    INDEX 01 00:00:00\n')
    print(f"{tag}: t_size={ts:#x} ({ts//2048} sectors) file={len(exe)} "
          f"-> {dst}")
    return dst


def main():
    for ts in (0x8000, 0x9000, 0xA000, 0xC000, 0x10000, 0x11000, 0x13000):
        build(ts)


if __name__ == "__main__":
    main()
