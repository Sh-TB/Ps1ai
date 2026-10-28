#!/usr/bin/env python3
"""r32t0_doukutsu_ccp_patch.py — Round 32: the disclosed CCP(0)->(1)
patch rollout to doukutsupsx (the R31-validated minecraft repair pattern).

Locator (PSN00bSDK stub bytes are build-invariant, verified against the
minecraft ELF where ChangeClearPAD=B(0x5B) @0x80035664):
  stub:  addiu $t2,0xb0 ; jr $t2 ; addiu $t1,0x5B   (12 B, unique hit)
  ISO:   MODE2/2352, EXE header sector 24, text payload from sector 25
  VA<->file: va2off/off2va sector-aware (validated: an InitPAD caller
  exists at the computed jal word, and the in_init context shows
  padbuf +0x2920/+0x2942 with addiu $a1,0x22 = 34)

in_init call chain @VA 0x80010524..0x80010554: InitPAD args -> wrapper ->
FF halfword stores -> StartPAD-class call -> jal ChangeClearPAD with the
ARGUMENT IN THE DELAY SLOT: move $a0, $zero @0x80010554.

Patch rule: for EVERY jal-CCP site whose $a0 is set to zero (delay slot
or the instruction before), rewrite that instruction to addiu $a0,$zero,1
(0x24040001). Sites with a dynamic $a0 are left untouched and reported.
Output: doukutsu_ccp1.iso (LOCAL copy; the original stays byte-identical).
"""
import hashlib
import os
import shutil
import struct

SRC = "/home/z/my-project/emu/games_homebrew/doukutsu_r7_us.iso"
DST = "/home/z/my-project/emu/games_homebrew/doukutsu_ccp1.iso"
TEXT_SEC = 25
T_ADDR = 0x80010000
STUB_PAT = bytes.fromhex("b0000a24080040015b000924")
MOVE_A0_0 = bytes.fromhex("25200000")   # move $a0,$zero (or-encoding)
MOVE_A0_0B = bytes.fromhex("21200000")  # move $a0,$zero (addu-encoding)
ADDIU_A0_0 = bytes.fromhex("00000424")  # addiu $a0, $zero, 0
ADDIU_A0_1 = bytes.fromhex("01000424")  # addiu $a0, $zero, 1


def off2va(o):
    sec = o // 2352
    insec = o % 2352
    return T_ADDR + (sec - TEXT_SEC) * 2048 + (insec - 24)


def main():
    d = bytearray(open(SRC, "rb").read())
    print(f"src: {len(d)} bytes sha256={hashlib.sha256(bytes(d)).hexdigest()[:16]}...")
    stubs = [i for i in range(len(d) - 12) if d[i:i + 12] == STUB_PAT]
    assert len(stubs) == 1, f"stub hits: {stubs}"
    stub_va = off2va(stubs[0])
    print(f"CCP stub: file {hex(stubs[0])} VA {stub_va:08X}")
    jal = struct.pack("<I", 0x0C000000 | ((stub_va >> 2) & 0x3FFFFFF))
    sites = [i for i in range(len(d) - 8) if d[i:i + 4] == jal]
    print(f"call sites: {[hex(off2va(s)) for s in sites]}")

    patches = []
    report = []
    for s in sites:
        delay = bytes(d[s + 4:s + 8])
        if delay in (MOVE_A0_0, MOVE_A0_0B, ADDIU_A0_0):
            patches.append((s + 4, "delay slot"))
            continue
        # walk back up to 12 instructions for the LAST $a0 write
        found = None
        from capstone import Cs, CS_ARCH_MIPS, CS_MODE_MIPS32, \
            CS_MODE_LITTLE_ENDIAN
        md = Cs(CS_ARCH_MIPS, CS_MODE_MIPS32 | CS_MODE_LITTLE_ENDIAN)
        lo = max(0, s - 48)
        wins = list(md.disasm(bytes(d[lo:s]), off2va(lo)))
        for ins in reversed(wins):
            if ins.op_str.startswith("$a0,") and                     ins.mnemonic in ("move", "addiu", "li", "or"):
                # writes $a0
                if ins.mnemonic == "move" and \
                        ins.op_str == "$a0, $zero":
                    found = (ins.address, "move $a0,$zero")
                elif ins.mnemonic == "or" and \
                        ins.op_str == "$a0, $zero, $zero":
                    found = (ins.address, "or $a0,$zero,$zero")
                elif ins.mnemonic == "addu" and \
                        ins.op_str == "$a0, $zero, $zero":
                    found = (ins.address, "addu $a0,$zero,$zero")
                elif ins.mnemonic == "addiu" and \
                        ins.op_str == "$a0, $zero, 0":
                    found = (ins.address, "addiu $a0,0")
                break
        if found:
            va, why = found
            off = TEXT_SEC * 2352 + 24 + (va - T_ADDR) \
                if False else None
            # convert VA back to file offset (sector-aware)
            x = va - T_ADDR
            off = (TEXT_SEC + x // 2048) * 2352 + 24 + (x % 2048)
            patches.append((off, why))
        else:
            report.append((hex(off2va(s)),
                           "dynamic/unknown arg - left"))
    print("zero-arg sites to patch:",
          [(hex(off2va(o)), k) for o, k in patches])
    for msg in report:
        print("left untouched:", msg)
    assert patches, "no zero-arg CCP call sites found - abort"

    for off, kind in patches:
        assert bytes(d[off:off + 4]) in (MOVE_A0_0, MOVE_A0_0B, ADDIU_A0_0), \
            (hex(off2va(off)), bytes(d[off:off+4]).hex(), kind)
        d[off:off + 4] = ADDIU_A0_1

    # runtime dispatcher: sltiu $s0,$s2,1 -> addiu $s0,$zero,1
    # (the pad-mode dispatcher calls CCP(0) whenever mode != 0; force the
    # always-CCP(1) semantics = Tetrade class, disclosed)
    SLTIU = bytes.fromhex("0100502e")   # sltiu $s0, $s2, 1
    dhits = [i for i in range(len(d) - 4) if d[i:i + 4] == SLTIU]
    print("dispatcher sltiu hits:", [hex(off2va(h)) for h in dhits])
    for h in dhits:
        d[h:h + 4] = bytes.fromhex("01001024")  # addiu $s0, $zero, 1
        patches.append((h, "dispatcher sltiu->always1"))
    open(DST, "wb").write(bytes(d))
    print(f"patched {len(patches)} site(s) -> {DST} "
          f"sha256={hashlib.sha256(bytes(d)).hexdigest()[:16]}...")
    print("OK")


if __name__ == "__main__":
    main()
