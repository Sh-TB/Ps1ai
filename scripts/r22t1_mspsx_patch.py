#!/usr/bin/env python3
"""r22t1_mspsx_patch.py — local-only MSPSX test images (task r22t1).

Stages:
  lic      -> patched/mspsx_lic.bin + .cue   (boot 1: 16 license sectors from
              the user's own retail MSX disc copied over the EMPTY license
              area; everything else byte-identical to the release image)
  padpatch -> patched/mspsx_lic_b2.bin+cue (boot 2: boot-1 image + in-place
              RXEN patch of the MSPSX.EXE payload, see evidence.md §0)

Patch (source-decoded, same length, 2 immediates — the r20-verified padtest
handshake equivalent):
  exe_off 0x2474  ori $v0,$v0,0x1003 -> 0x1007   (poll IRQ handler CTRL)
  exe_off 0x22BC  ori $v1,$v1,0x1013 -> 0x1017   (ack IRQ handler CTRL)

The EXE payload lives at LBA 24..43 (user data at sector*2352+24); patching
in place keeps the release PVD, directory records and the 4 CDDA tracks.
Never commit these images (game bytes + license policy).
"""
import hashlib
import os
import shutil
import sys

SEC = 2352
HDR = 24
PRISTINE = "/home/z/my-project/emu/games_homebrew/candidates_r21/mspsx_v0.1.bin"
PRISTINE_SHA = "d35a189b1ed14b7f07bf4cc31423ca43d8f34e35e8c3cb40c11bc6d3d0a4c5fa"
MSX = os.environ.get(
    "M1_RETAIL_BIN", "/home/z/my-project/emu/game/Metal Slug X (USA).bin")
OUT_DIR = "/home/z/my-project/emu/games_homebrew/patched"
EXE_LBA, EXE_SIZE = 24, 38912

# (exe_offset, expected_old_word_le, new_word_le)
PAD_PATCHES = [
    (0x2474, bytes.fromhex("03104234"), bytes.fromhex("07104234")),
    (0x22BC, bytes.fromhex("13106334"), bytes.fromhex("17106334")),
]


def sha(b):
    return hashlib.sha256(b).hexdigest()


def license_sectors():
    lic = open(MSX, "rb").read(16 * SEC)
    assert b"Sony Computer Entertainment" in lic, "MSX license not found"
    return lic


def build(stage):
    os.makedirs(OUT_DIR, exist_ok=True)
    pristine = open(PRISTINE, "rb").read()
    assert sha(pristine) == PRISTINE_SHA, "pristine artifact hash mismatch"
    img = bytearray(pristine)
    img[:16 * SEC] = license_sectors()

    if stage == "lic":
        name = "mspsx_lic.bin"
    elif stage == "padpatch":
        # patch the EXE payload in place (same size)
        exe = bytearray()
        nsect = (EXE_SIZE + 2047) // 2048
        for i in range(nsect):
            s = (EXE_LBA + i) * SEC + HDR
            exe += img[s:s + 2048]
        exe = exe[:EXE_SIZE]
        assert exe[:8] == b"PS-X EXE"
        assert sha(bytes(exe)).startswith("9764fa09500971ca"), \
            "EXE payload hash mismatch"
        for off, old, new in PAD_PATCHES:
            cur = bytes(exe[off:off + 4])
            assert cur == old, f"@{off:#x}: expected {old.hex()} got {cur.hex()}"
            exe[off:off + 4] = new
            print(f"exe@{off:#x}: {old.hex()} -> {new.hex()}")
        exe = bytes(exe)
        for i in range(nsect):
            s = (EXE_LBA + i) * SEC + HDR
            chunk = exe[i * 2048:(i + 1) * 2048]
            img[s:s + len(chunk)] = chunk
        name = "mspsx_lic_b2.bin"
    else:
        raise ValueError(stage)

    dst = os.path.join(OUT_DIR, name)
    with open(dst, "wb") as f:
        f.write(bytes(img))
    cue = os.path.join(OUT_DIR, name.replace(".bin", ".cue"))
    with open(cue, "w") as f:
        f.write(f'FILE "{name}" BINARY\n  TRACK 01 MODE2/2352\n'
                "    INDEX 01 00:00:00\n")
    print(f"wrote {dst}: {len(img)} bytes sha256={sha(bytes(img))}")
    return 0


def main():
    stage = sys.argv[1] if len(sys.argv) > 1 else "lic"
    return build(stage)


if __name__ == "__main__":
    sys.exit(main())
