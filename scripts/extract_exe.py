#!/usr/bin/env python3
"""extract_exe.py — pull SLUS_012.12 (PS-X EXE) out of the raw MODE2/2352
image. The EXE is the game's SOURCE OF TRUTH: code + static data at fixed
addresses (this is what GameShark codes address)."""
import os
import struct
import sys

BIN = "/home/z/my-project/ps1-test/emu/games/Metal Slug X (USA).bin"
OUT_DIR = "/home/z/my-project/ps1play/re"
SECTOR = 2352
USER_OFF = 24          # MODE2 Form1: 12 sync + 4 header + 8 subheader
USER_SZ = 2048

os.makedirs(OUT_DIR, exist_ok=True)
raw = open(BIN, "rb")
size = os.path.getsize(BIN)
n_sec = size // SECTOR
print(f"image: {size} bytes, {n_sec} raw sectors")

# ---- find "PS-X EXE" magic at a sector-aligned user-data offset ----------
found = None
buf = bytearray(SECTOR)
magic = b"PS-X EXE"
for s in range(16, n_sec):
    raw.seek(s * SECTOR + USER_OFF)
    raw.readinto(buf)
    if bytes(buf[:8]) == magic:
        found = s
        break
if found is None:
    sys.exit("!! PS-X EXE magic not found")
print(f"EXE file starts at raw sector {found} "
      f"(LBA {found}, byte {found * SECTOR + USER_OFF})")

# ---- parse the 2048-byte PS-EXE header ----------------------------------
# 0x00 "PS-X EXE" | 0x10 pc0 | 0x14 gp0 | 0x18 t_addr | 0x1C t_size
# 0x38 data_start
raw.seek(found * SECTOR + USER_OFF)
hdr = raw.read(USER_SZ)
pc0, gp0 = struct.unpack_from("<II", hdr, 0x10)
t_addr, t_size = struct.unpack_from("<II", hdr, 0x18)
data_start = struct.unpack_from("<I", hdr, 0x38)[0]
print(f"pc0 (entry)   = {pc0:#010x}")
print(f"gp0           = {gp0:#010x}")
print(f"t_addr (load) = {t_addr:#010x}")
print(f"t_size        = {t_size} ({t_size // 1024} KB)")
print(f"data_start    = {data_start:#010x}")

# ---- copy the whole file (2048B header + t_size) ------------------------
n_needed = (t_size + USER_SZ - 1) // USER_SZ
out_path = os.path.join(OUT_DIR, "SLUS_012.12")
with open(out_path, "wb") as out:
    for k in range(n_needed):
        raw.seek((found + k) * SECTOR + USER_OFF)
        out.write(raw.read(USER_SZ))
print(f"wrote {out_path}: {n_needed} sectors "
      f"({n_needed * USER_SZ} bytes)")

# also save an ISO9660 directory listing snapshot for reference
raw.seek(16 * SECTOR + USER_OFF)
pvd = raw.read(USER_SZ)
print("volume id:", pvd[40:72].decode("ascii", "replace").strip())
raw.close()
