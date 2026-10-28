#!/usr/bin/env python3
"""r22t1_mspsx_re.py — static RE of MSPSX v0.1 (source-decoded patch sites).

Upstream: github.com/AcidGunner/MSPSX (Unlicense; src/spi.c = spicyjpeg
PSn00bSDK example, MPL-2.0). Source says the pad driver (spi.c) is an
IRQ-driven SIO driver:
  poll IRQ (RCnt2): CTRL=0x0010 (ACK-IRQ reset) -> CTRL=0x1003|port<<13
                    -> write JOY_DATA=0x01
  ack IRQ (SIO):    CTRL=0x1013|port<<13, dummy read on first byte,
                    per-byte reads otherwise
beetle frontio.c semantics (cloned 2ba074e): a receive transfer starts only
when ReceivePending && CTRL&0x4 (RXEN); ReceivePending is armed ONLY by a
JOY_DATA READ. MSPSX never sets RXEN -> ReceiveInProgress never true ->
ReceiveBufferAvail never true -> all reads return 0 -> pad_buff zeros ->
Pad_Update sees btn=0 -> held=0xFFFF (phantom all-pressed once), then dead.

Expected patch (same length, 2 immediates): 0x1003 -> 0x1007, 0x1013 -> 0x1017
(add the RXEN bit 0x4), mirroring the r20-verified padtest CTRL 0x1007.

This script: parses the MODE2/2352 image, extracts MSPSX.EXE, disassembles,
finds the SIO CTRL store sites, emits patch file-offsets (inside EXE payload)
+ image-sector offsets. No emulator runs.
"""
import hashlib
import json
import os
import struct
import sys

BIN = "/home/z/my-project/emu/games_homebrew/candidates_r21/mspsx_v0.1.bin"
OUT = "/home/z/my-project/ps1ai/scratch/r22t1_mspsx"
SEC = 2352
HDR = 24  # sync 12 + header 4 + subheader 8

from capstone import Cs, CS_ARCH_MIPS, CS_MODE_MIPS32  # noqa: E402


def user_bytes(data, lba, nsect):
    out = bytearray()
    for i in range(lba, lba + nsect):
        out += data[i * SEC + HDR:i * SEC + HDR + 2048]
    return bytes(out)


def main():
    os.makedirs(OUT, exist_ok=True)
    data = open(BIN, "rb").read()
    sha = hashlib.sha256(data).hexdigest()
    assert sha.startswith("d35a189b1ed14b7f"), f"unexpected image sha {sha[:16]}"

    # PVD at LBA 16
    pvd = user_bytes(data, 16, 1)
    assert pvd[1:6] == b"CD001", pvd[:8]
    vol_id = pvd[40:72].decode().strip()
    root = struct.unpack_from("<I", pvd, 158)[0]  # rec: len@156, extent@158
    root_size = struct.unpack_from("<I", pvd, 166)[0]
    r = user_bytes(data, root, (root_size + 2047) // 2048)
    files = {}
    off = 0
    while off < len(r) and r[off]:
        ln = r[off]
        rec = r[off:off + ln]
        ext = struct.unpack_from("<I", rec, 2)[0]
        size = struct.unpack_from("<I", rec, 10)[0]
        nlen = rec[32]
        name = rec[33:33 + nlen].decode().rstrip(";1")
        files[name] = (ext, size)
        off += ln
    print("volume:", vol_id, "files:", {k: v for k, v in files.items()})

    cnf = user_bytes(data, *files["SYSTEM.CNF"])
    print("SYSTEM.CNF:", cnf[:120])
    exe_ext, exe_size = files["MSPSX.EXE"]
    exe = user_bytes(data, exe_ext, (exe_size + 2047) // 2048)[:exe_size]
    assert exe[:8] == b"PS-X EXE", exe[:8]
    t_addr, t_size = struct.unpack_from("<I", exe, 24)[0], \
        struct.unpack_from("<I", exe, 28)[0]
    print(f"MSPSX.EXE: extent={exe_ext} size={exe_size} t_addr={t_addr:#x} "
          f"t_size={t_size:#x} sha256={hashlib.sha256(exe).hexdigest()}")

    with open(os.path.join(OUT, "mspsx.exe"), "wb") as f:
        f.write(exe)
    # sector map for the EXE payload (image write-back)
    nsect = (exe_size + 2047) // 2048
    sect_map = [{"sector": exe_ext + i,
                 "img_off": (exe_ext + i) * SEC + HDR,
                 "exe_off": 0x800 + i * 2048} for i in range(nsect)]

    # ---- disassembly: find SIO register sites --------------------------
    code = exe[0x800:0x800 + t_size]
    base = t_addr
    md = Cs(CS_ARCH_MIPS, CS_MODE_MIPS32)
    md.detail = True
    ins = list(md.disasm(code, base))
    print("disassembled:", len(ins), "instructions")

    # Track a sliding window to see what feeds sh/st to 0x1044 (JOY_CTRL)
    hits = []
    for i, x in enumerate(ins):
        if x.mnemonic in ("sh", "sw") and "0x1044" in x.op_str:
            ctx = ins[max(0, i - 12):i + 2]
            imm = []
            for c in ctx:
                if c.mnemonic in ("ori", "addiu", "li") and \
                        ("0x10" in c.op_str or "0x40" in c.op_str
                         or "0x1013" in c.op_str or "0x1003" in c.op_str
                         or "0x0010" in c.op_str):
                    imm.append(f"{c.mnemonic} {c.op_str}")
            hits.append({
                "va": x.address, "exe_off": 0x800 + (x.address - base),
                "op": f"{x.mnemonic} {x.op_str}", "feeders": imm[-6:],
            })
    for h in hits:
        print(json.dumps(h))
    # Also any 0x1040/0x1048/0x104a access sites for completeness
    reg_hits = []
    for x in ins:
        for reg in ("0x1040", "0x1048", "0x104a"):
            if x.mnemonic in ("lw", "sw", "lb", "lbu", "sb", "lh", "lhu",
                              "sh") and reg in x.op_str:
                reg_hits.append({"va": x.address,
                                 "exe_off": 0x800 + (x.address - base),
                                 "op": f"{x.mnemonic} {x.op_str}"})
                break
    out = {"image_sha256": sha, "volume": vol_id, "files": files,
           "exe": {"extent": exe_ext, "size": exe_size, "t_addr": t_addr,
                   "t_size": t_size,
                   "sha256": hashlib.sha256(exe).hexdigest()},
           "ctrl_store_sites": hits, "other_sio_sites": reg_hits,
           "exe_sector_map": sect_map}
    with open(os.path.join(OUT, "re_scan.json"), "w") as f:
        json.dump(out, f, indent=1)
    print("wrote re_scan.json;", len(hits), "CTRL-store sites,",
          len(reg_hits), "other SIO sites")
    return 0


if __name__ == "__main__":
    sys.exit(main())
