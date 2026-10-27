#!/usr/bin/env python3
"""r21t3_zenmai_patch2.py — boot-2 SIO patch for zenmai (r21t3).

Boot 1 (8-byte dummy-read patch) left input dead: patched code confirmed in
RAM at 0x1B3E8 and executed every frame, yet zero menu redraw (sbar static),
zero main-RAM writes, marquee-only VRAM churn -> pad_read() still returning
-1 or edge-less data.

Boot 2 grafts the r20-VERIFIED padtest recipe (scripts/make_padtest_hw.py,
proven against this exact core build) into zenmai's pad_exchange prologue:

  file 0xBB60  nop                 -> addiu $v1,$zero,0x1007
  file 0xBB68  addiu $v1,0x1003    -> sh    $zero,0x104a($v0)   (CTRL=0, DTR off)
  file 0xBB6C  sh $v1,0x104a($v0)  (unchanged, now stores 0x1007)
  file 0xBB70  (boot-1) lw $v1,0x1040($v0)  -> dummy READ: arms ReceivePending
               AND drains the RXEN "stray byte" started by the CTRL write
  file 0xBB74  (boot-1) nop

Net per-exchange sequence == padtest: CTRL=0 -> CTRL=0x0007 (TXEN|DTR|RXEN,
rising DTR edge) -> drain+arm via dummy read -> TX 01/42/00/00/00 ->
RX ff/41/5A/SW1/SW2. Bit12 (0x1003's IRQ-enable) is gone, matching padtest.
"""
import hashlib
import os
import sys

OUT_DIR = "/home/z/my-project/emu/games_homebrew/patched"
SRC = os.path.join(OUT_DIR, "zenmai-zork-r21.psexe")   # boot-1 patched exe
DST = os.path.join(OUT_DIR, "zenmai-zork-r21b.psexe")

PATCHES = [  # (file_offset, expected_old, new)
    (0xBB60, bytes.fromhex("00000000"), bytes.fromhex("07100324")),  # addiu v1,0x1007
    (0xBB68, bytes.fromhex("03100324"), bytes.fromhex("4a1040a4")),  # sh zero,0x104a(v0)
]


def main():
    exe = bytearray(open(SRC, "rb").read())
    for off, old, new in PATCHES:
        cur = bytes(exe[off:off + 4])
        assert cur == old, f"@{off:#x}: expected {old.hex()} got {cur.hex()}"
        exe[off:off + 4] = new
        print(f"@{off:#x}: {old.hex()} -> {new.hex()}")
    exe = bytes(exe)
    with open(DST, "wb") as f:
        f.write(exe)
    print(f"wrote {DST} sha256={hashlib.sha256(exe).hexdigest()}")
    # rebuild cue pointing at the same bin (bin rebuilt below from new exe)
    # cheap: rewrite zenmai_lic_r21b.bin by patching the EXE bytes inside the
    # existing r21 disc image (EXE payload sits at a fixed sector; simpler to
    # rebuild via iso9660_min like the wrap script)
    _HERE = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, _HERE)
    import iso9660_min
    cnf = (b"BOOT = cdrom:\\ZENMAI.EXE;1\nTCB = 4\nEVENT = 10\n"
           b"STACK = 801FFF00\n")
    bin_data, cue = iso9660_min.build_image(
        [("SYSTEM.CNF", cnf), ("ZENMAI.EXE", exe)])
    MSX = os.environ.get(
        "M1_RETAIL_BIN", "/home/z/my-project/emu/game/Metal Slug X (USA).bin")
    lic = open(MSX, "rb").read(16 * 2352)
    assert b"Sony Computer Entertainment" in lic
    bin_data = bytearray(bin_data)
    bin_data[:16 * 2352] = lic
    bin_data = bytes(bin_data)
    bin_path = os.path.join(OUT_DIR, "zenmai_lic_r21b.bin")
    with open(bin_path, "wb") as f:
        f.write(bin_data)
    with open(os.path.join(OUT_DIR, "zenmai_lic_r21b.cue"), "w") as f:
        f.write(cue.replace('"image.bin"', '"zenmai_lic_r21b.bin"'))
    print(f"wrote {bin_path}: {len(bin_data)} bytes "
          f"sha256={hashlib.sha256(bin_data).hexdigest()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
