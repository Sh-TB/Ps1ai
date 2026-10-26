#!/usr/bin/env python3
"""r14_diag_bioscalls.py — scan cs50x.exe vs hello_pong exe for direct
BIOS-segment calls (jal/jalr to 0xA0/0xB0/0xC0......) and disassemble
cs50x's first init function 0x800103a8."""
import os
import struct

import capstone

EMU = "/home/z/my-project/emu/games_homebrew"
MIPS = capstone.CS_ARCH_MIPS
LE = capstone.CS_MODE_MIPS32 + capstone.CS_MODE_LITTLE_ENDIAN


def scan(tag, data, t_addr):
    md = capstone.Cs(MIPS, LE)
    body = data[0x800:]
    base = t_addr
    # jal opcode 0x0C << 26 | (target >> 2)
    bios_calls = {}
    jals = 0
    words = struct.unpack(f"<{len(body)//4}I", body[:len(body)//4*4])
    for i, w in enumerate(words):
        if (w >> 26) == 0x0C:               # jal
            tgt = (w & 0x3FFFFFF) << 2
            tgt |= 0x80000000 if (tgt & 0x08000000) else 0  # KSEG1/0 fill
            jals += 1
            if (tgt >> 24) in (0xA0, 0xB0, 0xC0):
                bios_calls.setdefault(tgt, []).append(base + i * 4)
    print(f"\n== {tag}: {jals} jal instructions, "
          f"{sum(len(v) for v in bios_calls.values())} BIOS-segment calls")
    for tgt in sorted(bios_calls):
        print(f"   BIOS {tgt:#010x} x{len(bios_calls[tgt])} "
              f"(e.g. from {bios_calls[tgt][0]:#010x})")


def disas_range(tag, data, t_addr, vstart, n=40):
    md = capstone.Cs(MIPS, LE)
    off = 0x800 + (vstart - t_addr)
    code = data[off:off + n * 4]
    print(f"\n== {tag} disasm @ {vstart:#x} ==")
    for ins in md.disasm(code, vstart):
        print(f"   {ins.address:#010x}: {ins.mnemonic:10s} {ins.op_str}")


def main():
    cs = open(os.path.join(EMU, "cs50x.exe"), "rb").read()
    hp = open(os.path.join(EMU, "hellopong_exe.extracted"), "rb").read()
    scan("cs50x.exe (CRASHES)", cs, 0x80010000)
    scan("hello_pong (BOOTS)", hp, 0x80010000)
    # cs50x crt0 first call
    disas_range("cs50x init@0x800103a8", cs, 0x80010000, 0x800103A8, 48)
    # strings of interest
    for tag, data in (("cs50x", cs), ("hello_pong", hp)):
        ss = []
        cur = bytearray()
        for b in data:
            if 32 <= b < 127:
                cur.append(b)
            else:
                if len(cur) >= 6:
                    ss.append(cur.decode())
                cur = bytearray()
        interesting = [s for s in ss if any(k in s.upper() for k in (
            "BIOS", "GPU", "CD", "PAD", "IRQ", "DMA", "SYS", "BREAK",
            "VSYNC", "OT", "PRINTF", "HELLO", "BREAKOUT", "CS50"))]
        print(f"\n== {tag} strings ({len(ss)} total, showing {len(interesting)}):")
        for s in interesting[:40]:
            print("   ", s[:100])


if __name__ == "__main__":
    main()
