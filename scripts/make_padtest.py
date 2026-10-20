#!/usr/bin/env python3
"""build_padtest.py — build a fully lawful, self-made PS1 pad-test disc.

Generates PADTEST.EXE (hand-assembled MIPS I, no third-party code):
  default : InitPad/StartPad via BIOS jump table (B(12h)/B(13h)), then a
            loop that fills the screen with GP0(02h):
            RIGHT=red  LEFT=blue  CROSS=green  START=white  none=black
  --simple: blink white/gray forever (exe-boot + GPU proof, no BIOS calls)
Then packs SYSTEM.CNF + EXE into an ISO9660/MODE2 image with the
built-in pure-Python writer (scripts/iso9660_min.py, correct EDC; no
external tools needed).

Everything is generated from scratch (zero copyrighted content).

Usage:
  python3 build_padtest.py [WORKDIR] [--simple]

Outputs: <work>/padtest.bin + padtest.cue (+ PADTEST.EXE, SYSTEM.CNF)
"""
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import iso9660_min

R = 0
A0, A1, A2, A3 = 4, 5, 6, 7
T0, T1, T2, T3, T4, T5, T6, T7 = 8, 9, 10, 11, 12, 13, 14, 15
RA = 31

BASE = 0x80010000
BUF1 = 0x80018000
BUF2 = 0x80018100
GP0 = 0x1F801810
GP1 = 0x1F801814


class Asm:
    """Minimal MIPS I assembler (only what the payload needs)."""

    def __init__(self, base):
        self.base = base
        self.words = []
        self.labels = {}
        self.fixups = []

    def emit(self, w):
        self.words.append(w & 0xFFFFFFFF)

    def label(self, name):
        self.labels[name] = self.base + 4 * len(self.words)

    def _fix(self):
        for idx, lbl, kind in self.fixups:
            tgt = self.labels[lbl]
            if kind == "br":
                off = (tgt - (self.base + 4 * idx + 4)) >> 2
                assert -0x8000 <= off <= 0x7FFF, f"branch range {lbl}"
                self.words[idx] |= off & 0xFFFF
            else:
                assert (tgt & 3) == 0, f"unaligned jump {lbl}"
                self.words[idx] |= (tgt >> 2) & 0x3FFFFFF
        self.fixups = []

    def lui(self, rt, imm):
        self.emit(0x0F << 26 | rt << 16 | (imm & 0xFFFF))

    def ori(self, rt, rs, imm):
        self.emit(0x0D << 26 | rs << 21 | rt << 16 | (imm & 0xFFFF))

    def li(self, rt, val):
        v = val & 0xFFFFFFFF
        self.lui(rt, (v >> 16) & 0xFFFF)
        if v & 0xFFFF:
            self.ori(rt, rt, v & 0xFFFF)

    def addiu(self, rt, rs, imm):
        self.emit(0x09 << 26 | rs << 21 | rt << 16 | (imm & 0xFFFF))

    def orR(self, rd, rs, rt):
        self.emit(rs << 21 | rt << 16 | rd << 11 | 0x25)

    def sw(self, rt, off, rs):
        self.emit(0x2B << 26 | rs << 21 | rt << 16 | (off & 0xFFFF))

    def lbu(self, rt, off, rs):
        self.emit(0x24 << 26 | rs << 21 | rt << 16 | (off & 0xFFFF))

    def andi(self, rt, rs, imm):
        self.emit(0x0C << 26 | rs << 21 | rt << 16 | (imm & 0xFFFF))

    def beq(self, rs, rt, lbl):
        self.emit(0x04 << 26 | rs << 21 | rt << 16)
        self.fixups.append((len(self.words) - 1, lbl, "br"))

    def bne(self, rs, rt, lbl):
        self.emit(0x05 << 26 | rs << 21 | rt << 16)
        self.fixups.append((len(self.words) - 1, lbl, "br"))

    def beqz(self, rs, lbl):
        self.beq(rs, R, lbl)

    def j(self, lbl):
        self.emit(0x02 << 26)
        self.fixups.append((len(self.words) - 1, lbl, "j"))

    def jalr(self, rs):
        self.emit(rs << 21 | RA << 11 | 0x09)

    def nop(self):
        self.emit(0)


def _fill(a, color):
    """Emit one GP0(02h) full-screen fill with the given 24-bit color."""
    a.li(T1, GP0)
    a.li(T6, 0x02000000)
    a.orR(T6, T6, color)
    a.sw(T6, 0, T1)
    a.li(T6, 0x00010000)          # x=0 y=1 (row 0 stays dark: boot marker)
    a.sw(T6, 0, T1)
    a.li(T6, 0x00F00140)          # h=240 w=320
    a.sw(T6, 0, T1)


def _delay(a, n, lbl_a, lbl_b):
    a.li(T7, n)
    a.label(lbl_a)
    a.addiu(T7, T7, -1)
    a.bne(T7, R, lbl_b)
    a.nop()


def _emit_program(a, simple=False):
    a.li(T0, GP1)
    a.li(T1, 0x05000000)          # GP1(05h): display area x=0 y=0
    a.sw(T1, 0, T0)
    a.nop()

    if simple:
        # v0 payload: blink white/gray -- proves exe boot + GPU, no BIOS calls
        a.label("loop")
        _fill(a, 0xFFFFFF)
        _delay(a, 4000000, "delayA", "delayA")
        _fill(a, 0x777777)
        _delay(a, 4000000, "delayB", "delayB")
        a.j("loop")
        a.nop()
        return

    a.li(A0, BUF1)                # InitPad(buf1,34,buf2,34) = B(0x12)
    a.li(A1, 34)
    a.li(A2, BUF2)
    a.li(A3, 34)
    a.li(T0, 0x800000B0 + 0x12 * 4)
    a.jalr(T0)
    a.nop()

    a.li(T0, 0x800000B0 + 0x13 * 4)   # StartPad() = B(0x13)
    a.jalr(T0)
    a.nop()

    a.label("loop")
    a.li(T1, BUF1)
    a.lbu(T2, 2, T1)              # SW1: SELECT L3 R3 START UP RIGHT DOWN LEFT
    a.lbu(T3, 3, T1)              # SW2: L2 R2 L1 R1 TRI CIRCLE CROSS SQ
    a.li(T4, 0x000000)            # default black (0x00BBGGRR)

    a.andi(T5, T2, 0x20)          # RIGHT?
    a.beqz(T5, "chk_left")
    a.nop()
    a.li(T4, 0x0000FF)            # red
    a.j("dofill")
    a.nop()

    a.label("chk_left")
    a.andi(T5, T2, 0x80)          # LEFT?
    a.beqz(T5, "chk_cross")
    a.nop()
    a.li(T4, 0xFF0000)            # blue
    a.j("dofill")
    a.nop()

    a.label("chk_cross")
    a.andi(T5, T3, 0x40)          # CROSS?
    a.beqz(T5, "chk_start")
    a.nop()
    a.li(T4, 0x00FF00)            # green
    a.j("dofill")
    a.nop()

    a.label("chk_start")
    a.andi(T5, T2, 0x08)          # START?
    a.beqz(T5, "dofill")
    a.nop()
    a.li(T4, 0xFFFFFF)            # white

    a.label("dofill")
    _fill(a, 0)                   # placeholder color patched below? no --
    # (we cannot re-emit; instead branch already chose T4, so emit fill using T4)
    return


def _emit_program_full(a):
    """Pad-reactive payload using T4 as the live color register."""
    a.li(T0, GP1)
    a.li(T1, 0x05000000)
    a.sw(T1, 0, T0)
    a.nop()

    a.li(A0, BUF1)
    a.li(A1, 34)
    a.li(A2, BUF2)
    a.li(A3, 34)
    a.li(T0, 0x800000B0 + 0x12 * 4)
    a.jalr(T0)
    a.nop()

    a.li(T0, 0x800000B0 + 0x13 * 4)
    a.jalr(T0)
    a.nop()

    a.label("loop")
    a.li(T1, BUF1)
    a.lbu(T2, 2, T1)
    a.lbu(T3, 3, T1)
    a.li(T4, 0x000000)

    a.andi(T5, T2, 0x20)
    a.beqz(T5, "chk_left")
    a.nop()
    a.li(T4, 0x0000FF)
    a.j("dofill")
    a.nop()

    a.label("chk_left")
    a.andi(T5, T2, 0x80)
    a.beqz(T5, "chk_cross")
    a.nop()
    a.li(T4, 0xFF0000)
    a.j("dofill")
    a.nop()

    a.label("chk_cross")
    a.andi(T5, T3, 0x40)
    a.beqz(T5, "chk_start")
    a.nop()
    a.li(T4, 0x00FF00)
    a.j("dofill")
    a.nop()

    a.label("chk_start")
    a.andi(T5, T2, 0x08)
    a.beqz(T5, "dofill")
    a.nop()
    a.li(T4, 0xFFFFFF)

    a.label("dofill")
    a.li(T1, GP0)
    a.li(T6, 0x02000000)
    a.orR(T6, T6, T4)
    a.sw(T6, 0, T1)
    a.li(T6, 0x00010000)
    a.sw(T6, 0, T1)
    a.li(T6, 0x00F00140)
    a.sw(T6, 0, T1)

    a.li(T7, 2000000)
    a.label("delay")
    a.addiu(T7, T7, -1)
    a.bne(T7, R, "delay")
    a.nop()

    a.j("loop")
    a.nop()


def _write_and_pack(code, work):
    """Package code into PS-X EXE, SYSTEM.CNF and ISO via mkpsxiso."""
    hdr = bytearray(0x800)
    hdr[0x00:0x08] = b"PS-X EXE"
    # Header layout per mednafen LoadEXE (libretro.c): PC@0x10,
    # TextStart@0x18, TextSize@0x1C, SP@0x30.
    struct.pack_into("<I", hdr, 0x10, BASE)          # pc0 (entry)
    struct.pack_into("<I", hdr, 0x18, BASE)          # t_addr (TextStart)
    struct.pack_into("<I", hdr, 0x1C, len(code))     # t_size (TextSize)
    struct.pack_into("<I", hdr, 0x30, 0x801FFFF0)    # initial SP
    struct.pack_into("<I", hdr, 0x34, 0x801FFF00)    # SP base
    struct.pack_into("<I", hdr, 0x38, 0x801FFFDC)    # FP
    exe = bytes(hdr) + code
    with open(os.path.join(work, "PADTEST.EXE"), "wb") as f:
        f.write(exe)
    with open(os.path.join(work, "SYSTEM.CNF"), "w") as f:
        f.write("BOOT = cdrom:\\PADTEST.EXE;1\n")
        f.write("TCB = 4\n")
        f.write("EVENT = 10\n")
        f.write("STACK = 801FFF00\n")
    # Pure-Python ISO9660 MODE2/2352 writer (correct EDC, no mkpsxiso).
    # PS1 data tracks start at MSF 00:02:00 (BIOS expects PVD at sector 16
    # counted from INDEX 01).
    bin_data, cue = iso9660_min.build_image(
        [("SYSTEM.CNF", open(os.path.join(work, "SYSTEM.CNF"), "rb").read()),
         ("PADTEST.EXE", exe)])
    with open(os.path.join(work, "padtest.bin"), "wb") as f:
        f.write(bin_data)
    with open(os.path.join(work, "padtest.cue"), "w") as f:
        f.write(cue.replace('"image.bin"', '"padtest.bin"'))
    rc = 0
    for p in ("padtest.bin", "padtest.cue", "PADTEST.EXE"):
        fp = os.path.join(work, p)
        if os.path.exists(fp):
            print(f"  {p}: {os.path.getsize(fp)} bytes")
    return rc


def main():
    work = "/tmp/ps1play_padtest"
    argv = [x for x in sys.argv[1:]]
    if argv and not argv[0].startswith("--"):
        work = argv.pop(0)
    os.makedirs(work, exist_ok=True)
    simple = "--simple" in argv
    a = Asm(BASE)
    if simple:
        _emit_program(a, simple=True)
    else:
        _emit_program_full(a)
    a._fix()
    code = b"".join(struct.pack("<I", w) for w in a.words)
    print(f"code: {len(code)} bytes, {len(a.words)} instructions")
    sys.exit(_write_and_pack(code, work))


if __name__ == "__main__":
    main()
