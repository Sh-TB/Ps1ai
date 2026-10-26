#!/usr/bin/env python3
"""r14_stage1_build.py — Round 14: psxBreakout boot FIX.

Root cause (measured this round): OpenBIOS's loadExe() issues ONE
dev_cd_read() for the whole exe body and IGNORES its return value; the
kernel CD path delivers at most 16 sectors (0x8000 bytes) per call.
hello_pong (14 sectors) boots; cs50x.exe (38 sectors) truncates at
0x8000 -> exec jumps into zeroed RAM -> dead black screen.

Fix: a 2 KB hand-assembled STAGE-1 loader exe (1-sector body, far
under the cap) that streams the real 77824-byte payload from the
disc file CS50X.EXE in 16-sector BIOS-legal chunks via B0 syscalls
(open=0x32 read=0x34 close=0x36, flushCache=A0:0x44) and jumps to the
game's own pc0 (0x80010000, argc=1/argv=NULL — same contract as the
shell's exec). No game bytes are modified.

Disc layout mirrors hello_pong's PSX-flavored structure exactly
(PVD root record @156, path tables @18/19, root@22, CNF@23):
  16 PVD (copy, patched volume id + space)
  17 terminator (copy)   18/19 path tables (copy)   20/21 (copy)
  22 root dir: SYSTEM.CNF;1@23(56) LOADER.EXE;1@24(4096)
               CS50X.EXE;1@26(79872, VERBATIM)
  0..15 license sectors from the user's own retail disc (local only).
"""
from __future__ import annotations

import hashlib
import json
import os
import struct

import capstone

EMU = "/home/z/my-project/emu/games_homebrew"
PATCHED = os.path.join(EMU, "patched")
RETAIL = "/home/z/my-project/emu/game/Metal Slug X (USA).bin"
HP_LIC = os.path.join(PATCHED, "hello_pong_lic.bin")
CS50X = os.path.join(EMU, "cs50x.exe")
OUT_DIR = "/home/z/my-project/ps1ai/scratch/round14_breakout"

RAW, DATA_OFF, SEC = 2352, 24, 2048

# ---------------- register numbers ----------------
R_ZERO, R_V0, R_A0, R_A1, R_A2 = 0, 2, 4, 5, 6
R_T0, R_T1 = 8, 9
R_S0, R_S1, R_S2 = 16, 17, 18
R_SP, R_RA = 29, 31

STAGE_TADDR = 0x80180000
PATH_ADDR = STAGE_TADDR + 0x100          # "cdrom:\CS50X.EXE;1"
SCRATCH = STAGE_TADDR + 0x2000           # header discard buffer
GAME_PC = 0x80010000
TOTAL_BODY = 0x13000                      # cs50x t_size


def enc_r(op, rs, rt, rd, sh, fn):
    return (op << 26) | (rs << 21) | (rt << 16) | (rd << 11) | (sh << 6) | fn


def enc_i(op, rs, rt, imm):
    return (op << 26) | (rs << 21) | (rt << 16) | (imm & 0xFFFF)


def enc_j(op, target):
    return (op << 26) | ((target >> 2) & 0x3FFFFFF)


def asm():
    """Two-pass assembler for the stage-1 program. Returns body bytes."""
    prog = []          # (kind, payload) kinds: I=instruction, L=label
    labels = {}

    def I(w):
        prog.append(("I", w))

    def L(name):
        prog.append(("L", name))

    def lui(rt, imm):
        I(enc_i(0x0F, 0, rt, imm))

    def ori(rt, rs, imm):
        I(enc_i(0x0D, rs, rt, imm))

    def addiu(rt, rs, imm):
        I(enc_i(0x09, rs, rt, imm))

    def sltu(rd, rs, rt):
        I(enc_r(0, rs, rt, rd, 0, 0x2B))

    def slt(rd, rs, rt):
        I(enc_r(0, rs, rt, rd, 0, 0x2A))

    def addu(rd, rs, rt):
        I(enc_r(0, rs, rt, rd, 0, 0x21))

    def subu(rd, rs, rt):
        I(enc_r(0, rs, rt, rd, 0, 0x23))

    def jr(rs):
        I(enc_r(0, rs, 0, 0, 0, 0x08))

    def jal(target):
        I(enc_j(0x03, target))

    def j_(name):
        prog.append(("J", (0x02, name)))

    def beq(rs, rt, name):
        prog.append(("B", (0x04, rs, rt, name)))

    def bne(rs, rt, name):
        prog.append(("B", (0x05, rs, rt, name)))

    def nop():
        I(0)

    def move(rd, rs):
        addu(rd, rs, R_ZERO)

    # ---------------- program ----------------
    L("start")
    lui(R_SP, 0x801F)
    ori(R_SP, R_SP, 0xFF00)               # sp = 0x801FFF00
    # open("cdrom:\CS50X.EXE;1", 0)
    lui(R_A0, PATH_ADDR >> 16)
    ori(R_A0, R_A0, PATH_ADDR & 0xFFFF)
    move(R_A1, R_ZERO)
    addiu(R_T1, R_ZERO, 0x32)             # B0 open
    jal(0xB0)
    nop()
    slt(R_T0, R_V0, R_ZERO)
    beq(R_T0, R_ZERO, "opened")
    nop()
    L("bad")
    j_("bad")
    nop()
    L("opened")
    move(R_S0, R_V0)                      # fd
    # read(fd, SCRATCH, 2048) — the PS-EXE header, discarded
    move(R_A0, R_S0)
    lui(R_A1, SCRATCH >> 16)
    ori(R_A1, R_A1, SCRATCH & 0xFFFF)
    addiu(R_A2, R_ZERO, 0x0800)
    addiu(R_T1, R_ZERO, 0x34)             # B0 read
    jal(0xB0)
    nop()
    slt(R_T0, R_V0, R_ZERO)
    bne(R_T0, R_ZERO, "bad")
    nop()
    # dest = GAME_PC ; remaining = TOTAL_BODY
    lui(R_S1, GAME_PC >> 16)
    ori(R_S1, R_S1, GAME_PC & 0xFFFF)
    lui(R_S2, TOTAL_BODY >> 16)
    ori(R_S2, R_S2, TOTAL_BODY & 0xFFFF)
    L("loop")
    ori(R_T0, R_ZERO, 0x8000)             # 32768 = 16 sectors (the cap)
    sltu(R_T0, R_S2, R_T0)                # rem < 32768 ?
    beq(R_T0, R_ZERO, "big")
    nop()
    move(R_A2, R_S2)                      # chunk = remaining
    j_("doread")
    nop()
    L("big")
    ori(R_A2, R_ZERO, 0x8000)             # chunk = 32768
    L("doread")
    move(R_A0, R_S0)
    move(R_A1, R_S1)
    addiu(R_T1, R_ZERO, 0x34)             # B0 read
    jal(0xB0)
    nop()
    slt(R_T0, R_V0, R_ZERO)
    bne(R_T0, R_ZERO, "bad")
    nop()
    addu(R_S1, R_S1, R_A2)
    subu(R_S2, R_S2, R_A2)
    bne(R_S2, R_ZERO, "loop")
    nop()
    # close(fd)
    move(R_A0, R_S0)
    addiu(R_T1, R_ZERO, 0x36)             # B0 close
    jal(0xB0)
    nop()
    # flushCache (A0 0x44)
    addiu(R_T1, R_ZERO, 0x44)
    jal(0xA0)
    nop()
    # jump to the game's own pc0 — same contract as shell exec(hdr,1,NULL)
    addiu(R_A0, R_ZERO, 1)
    move(R_A1, R_ZERO)
    lui(R_T0, GAME_PC >> 16)
    jr(R_T0)
    nop()

    # ---- pass 2: resolve labels ----
    out = []
    addr = STAGE_TADDR
    for kind, pay in prog:
        if kind == "L":
            labels[pay] = addr
        else:
            out.append((addr, kind, pay))
            addr += 4
    words = []
    for addr, kind, pay in out:
        if kind == "I":
            words.append(pay)
        elif kind == "J":
            op, name = pay
            words.append(enc_j(op, labels[name]))
        elif kind == "B":
            op, rs, rt, name = pay
            off = (labels[name] - (addr + 4)) >> 2
            assert -32768 <= off <= 32767, off
            words.append(enc_i(op, rs, rt, off))
    body = struct.pack(f"<{len(words)}I", *words)
    # pad to 2048 + place the path string at PATH_ADDR
    body = body.ljust(PATH_ADDR - STAGE_TADDR, b"\x00")
    path = b"cdrom:\\CS50X.EXE;1\x00"
    body += path
    body = body.ljust(0x800, b"\x00")
    assert len(body) == 0x800
    return body, labels


def disasm(body):
    md = capstone.Cs(capstone.CS_ARCH_MIPS,
                     capstone.CS_MODE_MIPS32 + capstone.CS_MODE_LITTLE_ENDIAN)
    lines = []
    for ins in md.disasm(body[:0x100], STAGE_TADDR):
        lines.append(f"  {ins.address:#010x}: {ins.mnemonic:8s} {ins.op_str}")
    return "\n".join(lines)


def ps_exe(pc, t_addr, t_size, s_addr, body):
    hdr = bytearray(0x800)
    hdr[0:8] = b"PS-X EXE"
    struct.pack_into("<I", hdr, 0x10, pc)
    struct.pack_into("<I", hdr, 0x18, t_addr)
    struct.pack_into("<I", hdr, 0x1C, t_size)
    struct.pack_into("<I", hdr, 0x30, s_addr)
    struct.pack_into("<I", hdr, 0x34, 0)
    return bytes(hdr) + body


def dir_record(name, extent, size, flags=0):
    """hello_pong-style record: 33 + namelen + 14 zero bytes of system
    use (bisect-proven: tight records make the shell checker reject the
    disc; the +14 padded style is what the known-bootable disc uses)."""
    nm = name.encode("ascii")
    rec = bytearray()
    rec += bytes([0, 0])                     # length placeholder
    rec += struct.pack("<I", extent) + struct.pack(">I", extent)
    rec += struct.pack("<I", size) + struct.pack(">I", size)
    rec += bytes([0x7e, 0x09, 0x06, 0x04, 0x17, 0x20, 0x00])  # hello_pong's dates
    rec += bytes([flags, 0, 0])
    rec += struct.pack("<H", 1) + struct.pack(">H", 1)
    rec += bytes([len(nm)]) + nm
    if len(rec) % 2:
        rec += b"\x00"
    rec += bytes(14)                         # hello_pong's system-use pad
    rec[0] = len(rec)
    return bytes(rec)


def msf(lba):
    m, rem = divmod(lba + 150, 75 * 60)
    s, f = divmod(rem, 75)
    to_bcd = lambda n: ((n // 10) << 4) | (n % 10)
    return bytes([to_bcd(m), to_bcd(s), to_bcd(f)])


def wrap2352(user):
    out = bytearray()
    n = len(user) // SEC
    for lba in range(n):
        out += b"\x00" + b"\xff" * 10 + b"\x00"
        out += msf(lba) + b"\x02"
        out += bytes([0, 0, 0x08, 0, 0, 0, 0x08, 0])
        out += user[lba * SEC:(lba + 1) * SEC]
        out += bytes(280)
    return bytes(out)


def rd_user(f, lba):
    f.seek(lba * RAW + DATA_OFF)
    return f.read(SEC)


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    body, labels = asm()
    dis = disasm(body)
    print("== stage-1 disassembly ==")
    print(dis)
    loader_exe = ps_exe(STAGE_TADDR, STAGE_TADDR, len(body), 0x801FFF00,
                        body)
    game_exe = open(CS50X, "rb").read()
    assert game_exe[:8] == b"PS-X EXE"
    assert struct.unpack("<I", game_exe[0x18:0x1C])[0] == GAME_PC
    assert struct.unpack("<I", game_exe[0x1C:0x20])[0] == TOTAL_BODY

    cnf = (b"BOOT=cdrom:\\LOADER.EXE;1\n"
           b"TCB=4\n"
           b"EVENT=10\n"
           b"STACK=801FFF00\n")

    # ---- user-domain sector layout (2048) ----
    n_files = 3
    root_lba, cnf_lba, loader_lba, game_lba = 22, 23, 24, 26
    loader_sectors = (len(loader_exe) + SEC - 1) // SEC      # 2
    game_sectors = (len(game_exe) + SEC - 1) // SEC          # 39
    total = game_lba + game_sectors                          # 65

    img = bytearray(total * SEC)

    # copy hello_pong's descriptors 16..21 verbatim, patch PVD
    f = open(HP_LIC, "rb")
    pvd = bytearray(rd_user(f, 16))
    pvd[40:72] = b"CS50X_BOOT".ljust(32)
    struct.pack_into("<I", pvd, 80, total)
    struct.pack_into(">I", pvd, 84, total)
    img[16 * SEC:17 * SEC] = pvd
    for lba in (17, 18, 19, 20, 21):
        img[lba * SEC:(lba + 1) * SEC] = rd_user(f, lba)
    f.close()

    # root directory @22
    root = bytearray()
    root += dir_record("\x00", root_lba, SEC, flags=2)
    root += dir_record("\x01", root_lba, SEC, flags=2)
    root += dir_record("SYSTEM.CNF;1", cnf_lba, len(cnf))
    root += dir_record("LOADER.EXE;1", loader_lba, len(loader_exe))
    root += dir_record("CS50X.EXE;1", game_lba, len(game_exe))
    img[root_lba * SEC:root_lba * SEC + len(root)] = root

    # file payloads
    img[cnf_lba * SEC:cnf_lba * SEC + len(cnf)] = cnf
    img[loader_lba * SEC:loader_lba * SEC + len(loader_exe)] = loader_exe
    img[game_lba * SEC:game_lba * SEC + len(game_exe)] = game_exe

    # ---- raw 2352 + license ----
    raw = wrap2352(bytes(img))
    lic = open(RETAIL, "rb").read(16 * RAW)
    assert b"Sony Computer Entertainment" in lic
    raw = lic + raw[16 * RAW:]

    dst = os.path.join(PATCHED, "breakout_r14.bin")
    open(dst, "wb").write(raw)
    with open(dst.replace(".bin", ".cue"), "w") as c:
        c.write('FILE "breakout_r14.bin" BINARY\n'
                '  TRACK 01 MODE2/2352\n'
                '    INDEX 01 00:00:00\n')

    rep = {
        "image": dst, "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "total_sectors": total,
        "stage1": {"t_addr": hex(STAGE_TADDR), "t_size": 0x800,
                   "pc0": hex(STAGE_TADDR), "path_str_addr": hex(PATH_ADDR),
                   "scratch": hex(SCRATCH),
                   "syscalls": {"open": "B0:0x32", "read": "B0:0x34",
                                "close": "B0:0x36",
                                "flushCache": "A0:0x44"},
                   "chunks": ["0x800 header (discard)", "0x8000", "0x8000",
                              "0x3000"],
                   "labels": {k: hex(v) for k, v in labels.items()}},
        "game_exe": {"sha256": hashlib.sha256(game_exe).hexdigest(),
                     "bytes": len(game_exe), "verbatim": True},
        "root_dir": ["SYSTEM.CNF;1@23", "LOADER.EXE;1@24",
                     "CS50X.EXE;1@26"],
    }
    with open(os.path.join(OUT_DIR, "stage1_build.json"), "w") as f:
        json.dump(rep, f, indent=1)
    print(json.dumps({k: v for k, v in rep.items() if k != "stage1"},
                     indent=1))
    print("stage1 labels:", rep["stage1"]["labels"])
    print("OK ->", dst)


if __name__ == "__main__":
    main()
