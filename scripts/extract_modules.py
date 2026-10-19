#!/usr/bin/env python3
"""extract_modules.py — pull the runtime overlay modules (ENEMY.BIN,
MISSION.BIN, ...) from the ISO and check whether they are PS-X EXEs
with their own load addresses. These modules hold the gameplay data
(hp/ammo/bombs/lives) that the published GameShark codes address."""
import os
import struct

BIN = "/home/z/my-project/ps1-test/emu/games/Metal Slug X (USA).bin"
OUT = "/home/z/my-project/ps1play/re"
S, U = 2352, 2048

f = open(BIN, "rb")


def sec(lba):
    f.seek(lba * S + 24)
    return f.read(U)


pvd = sec(16)
root = pvd[156:156 + 34]
lba_root = struct.unpack_from("<I", root, 2)[0]
size_root = struct.unpack_from("<I", root, 10)[0]
data = b""
lba = lba_root
while len(data) < size_root:
    data += sec(lba)
    lba += 1

os.makedirs(OUT, exist_ok=True)
i = 0
while i < len(data):
    rl = data[i]
    if rl == 0:
        i = (i // U + 1) * U
        if i >= len(data):
            break
        continue
    rec = data[i:i + rl]
    name = rec[33:33 + rec[32]].decode(errors="replace").split(";")[0]
    if name not in ("\x00", "\x01") and name.upper().endswith(".BIN"):
        lba_f = struct.unpack_from("<I", rec, 2)[0]
        sz_f = struct.unpack_from("<I", rec, 10)[0]
        content = b"".join(sec(lba_f + k)
                           for k in range((sz_f + U - 1) // U))[:sz_f]
        path = os.path.join(OUT, name.replace(";", ""))
        with open(path, "wb") as o:
            o.write(content)
        magic = content[:8]
        info = ""
        if magic == b"PS-X EXE":
            pc0, = struct.unpack_from("<I", content, 0x10)
            t_addr, t_size = struct.unpack_from("<II", content, 0x18)
            info = (f"PS-X EXE pc0={pc0:#010x} t_addr={t_addr:#010x} "
                    f"t_size={t_size}")
        else:
            info = f"raw module, magic={magic!r}"
        print(f"{name:16s} lba={lba_f:6d} size={sz_f:9d}  {info}")
    i += rl
f.close()
print("done")
