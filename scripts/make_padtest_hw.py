#!/usr/bin/env python3
"""make_padtest_hw.py — BIOS-free pad-test PS-X EXE (direct SIO polling).

The retail-BIOS experiment (scripts/retail_bios_experiment.py) proved the
user-supplied BIOS files are NOT valid retail images (invalid reset code,
no kernel strings, CPU exception-loops at 0xBFC00000; see the experiment
report). That blocks the InitPAD(B(12h))/StartPad(B(13h)) payload because
the kernel jump table never gets initialized.

This builder removes the BIOS from the equation entirely:

  * payload polls the pad THROUGH THE SIO HARDWARE REGISTERS exactly as
    this core implements them (mednafen/psx/frontio.c):
      - JOY_CTRL(0x1F80104A): bit0 TXEN, bit1 DTR (port-1 select), bit2
        RXEN; writing control also drives SetDTR (a rising edge resets
        the pad's command phase)
      - JOY_TX/RX(0x1F801040): write byte, poll JOY_STAT(0x1F801044)
        bit1 until the reply byte is available, read it back
      - sequence per poll: 0x01 -> 0x41, 0x42 -> 0x5A, 0x00 -> SW1,
        0x00 -> SW2 (sw1 = 0xFF ^ buttons[0])
  * meant to be booted as RAW PS-X EXE content (the core's own Load()
    path, libretro.c "Load a raw PS-X EXE..."), no disc and no kernel:
    the payload therefore never calls the BIOS jump table.
  * RAM breadcrumbs at 0x80018000 (all written by the payload itself):
      +0x00 magic "PAD1" (0x50414431)  -> EXE really dispatched
      +0x04 loop counter               -> still running
      +0x08 last SW1, +0x0C last SW2   -> live pad state (input!)
      +0x10 polls_ok, +0x14 polls_fail -> poll health

Output: <work>/PADTEST.EXE (raw PS-X EXE, header + code, exact size rule
TextSize == filesize - 0x800 enforced by the core's LoadEXE).
"""
import os
import struct
import sys

R = 0
AT = 1
S0, S1, S2, S3, S4, S5, S6, S7 = 16, 17, 18, 19, 20, 21, 22, 23
T0, T1, T2, T3, T4, T5, T6, T7, T8, T9 = 8, 9, 10, 11, 12, 13, 14, 15, 24, 25
RA = 31

BASE = 0x80010000
MAGIC = 0x50414431                      # "PAD1"
GP0, GP1 = 0x1F801810, 0x1F801814
SIO_DATA, SIO_STAT = 0x1F801040, 0x1F801044
SIO_MODE, SIO_CTRL, SIO_BAUD = 0x1F801048, 0x1F80104A, 0x1F80104E

SW_NONE, SW_RIGHT, SW_LEFT = 0xFF, 0xDF, 0x7F


class Asm:
    """Minimal MIPS I assembler (only what the payload needs)."""

    def __init__(self, base):
        self.base = base
        self.words = []
        self.labels = {}
        self.fixups = []

    def emit(self, w):
        self.words.append(w & 0xFFFFFFFF)

    def pc(self):
        return self.base + 4 * len(self.words)

    def label(self, name):
        self.labels[name] = self.pc()

    def ulabel(self, name):
        """Unique label (for macros inlined more than once)."""
        self._uid = getattr(self, "_uid", 0) + 1
        return f"{name}{self._uid}"

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

    def sh(self, rt, off, rs):
        self.emit(0x29 << 26 | rs << 21 | rt << 16 | (off & 0xFFFF))

    def lw(self, rt, off, rs):
        self.emit(0x23 << 26 | rs << 21 | rt << 16 | (off & 0xFFFF))

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

    def bnez(self, rs, lbl):
        self.bne(rs, R, lbl)

    def j(self, lbl):
        self.emit(0x02 << 26)
        self.fixups.append((len(self.words) - 1, lbl, "j"))

    def nop(self):
        self.emit(0)


def _wait_and_read(a, fail_lbl):
    """Wait for a reply byte, read it (result in T3, re-arms RX).
    NOTE: this core enforces the MIPS load-delay slot — a register
    loaded by LW is only visible to the instruction AFTER the next
    one, so every LW is followed by a NOP."""
    wl = a.ulabel("wloop")
    wg = a.ulabel("wgot")
    a.li(T2, 400000)
    a.label(wl)
    a.lw(T3, 0, S3)                     # status
    a.nop()                             # load delay slot
    a.andi(T3, T3, 0x2)
    a.bnez(T3, wg)
    a.nop()
    a.addiu(T2, T2, -1)
    a.beqz(T2, fail_lbl)
    a.nop()
    a.j(wl)
    a.nop()
    a.label(wg)
    a.lw(T3, 0, S0)                     # read RX byte (clears + re-arms)
    a.nop()                             # load delay: T3 valid for caller


def _send(a, val):
    """Transmit one byte (TXEN+RXEN+DTR already set)."""
    a.li(T1, val)
    a.sw(T1, 0, S0)


def _fill(a, color_reg):
    """GP0(02h) full-screen fill, row 0 left dark as the boot marker."""
    a.li(T1, GP0)
    a.li(T7, 0x02000000)
    a.orR(T7, T7, color_reg)
    a.sw(T7, 0, T1)
    a.li(T7, 0x00010000)
    a.sw(T7, 0, T1)
    a.li(T7, 0x00F00140)
    a.sw(T7, 0, T1)


def build():
    a = Asm(BASE)

    # ---- init ----------------------------------------------------------
    a.li(S0, SIO_DATA)
    a.li(S3, SIO_STAT)
    a.li(S4, SIO_CTRL)
    a.li(S5, SIO_MODE)
    a.li(S6, SIO_BAUD)
    a.li(S1, GP1)
    a.li(T1, 0x05000000)                # display area (0,0)
    a.sw(T1, 0, S1)
    a.nop()
    a.li(S2, 0x80018000)                # breadcrumb base

    # SIO bring-up: reset line, mode, baud. CTRL(0x4A) and BAUD(0x4E)
    # are only halfword-aligned, so they MUST use SH (a word store there
    # raises AdES — verified on the instrumented build).
    a.li(T1, 0x0040)
    a.sh(T1, 0, S4)                     # CTRL = RESET
    a.sw(R, 0, S5)                      # MODE = 0 (word-aligned)
    a.li(T1, 0x0088)
    a.sh(T1, 0, S6)                     # BAUD = 0x88

    # Bootstrap quirk of this core: FrontIO_Power() leaves
    # ReceivePending=false and only a DATA-register READ sets it, so
    # without a dummy read the RX side never arms (chicken-and-egg).
    a.lw(T1, 0, S0)                     # dummy read -> ReceivePending=true

    # RAM breadcrumbs: magic + zeroed counters
    a.li(T1, MAGIC)
    a.sw(T1, 0, S2)
    a.sw(R, 4, S2)
    a.sw(R, 8, S2)
    a.sw(R, 12, S2)
    a.sw(R, 16, S2)
    a.sw(R, 20, S2)

    # ---- main loop ------------------------------------------------------
    a.label("loop")
    a.lw(T0, 4, S2)
    a.nop()                             # load delay slot
    a.addiu(T0, T0, 1)
    a.sw(T0, 4, S2)                     # loop counter++

    # pad poll. Core-verified protocol (mednafen/psx/frontio.c):
    #  * every CTRL write with RXEN+armed ReceivePending starts a
    #    "stray" RX byte -> re-synchronize by waiting+reading once
    #    after DTR rises;
    #  * the pad processes a command at the END of its byte window, so
    #    replies arrive ONE WINDOW LATE:
    #    TX 01/42/00/00/00 -> RX ff/41/5A/SW1/SW2.
    a.li(T1, 0x0004)
    a.sh(T1, 0, S4)                     # DTR off
    a.li(T1, 0x0007)
    a.sh(T1, 0, S4)                     # TXEN|DTR|RXEN (rising edge)
    _wait_and_read(a, "pfail")          # sync: drain the stray RX byte
    _send(a, 0x01)
    _wait_and_read(a, "pfail")          # idle 0xFF (discarded)
    _send(a, 0x42)
    _wait_and_read(a, "pfail")          # 0x41 id (discarded)
    _send(a, 0x00)
    _wait_and_read(a, "pfail")          # 0x5A (discarded)
    _send(a, 0x00)
    _wait_and_read(a, "pfail")          # SW1
    a.orR(T8, T3, R)                    # T8 = SW1
    _send(a, 0x00)
    _wait_and_read(a, "pfail")          # SW2
    a.orR(T9, T3, R)                    # T9 = SW2

    a.sw(T8, 8, S2)
    a.sw(T9, 12, S2)
    a.lw(T0, 16, S2)
    a.nop()                             # load delay slot
    a.addiu(T0, T0, 1)
    a.sw(T0, 16, S2)                    # polls_ok++
    a.j("colorsel")
    a.nop()
    a.label("pfail")
    a.li(T8, SW_NONE)                   # treat failed poll as no-buttons
    a.sw(T8, 8, S2)
    a.lw(T0, 20, S2)
    a.nop()                             # load delay slot
    a.addiu(T0, T0, 1)
    a.sw(T0, 20, S2)                    # polls_fail++
    a.li(T9, 0xFF)                      # SW2 undefined on failure

    a.label("colorsel")
    a.li(T4, 0x000000)                  # default black (0x00BBGGRR)
    a.andi(T5, T8, 0x20)
    a.beqz(T5, "chk_left")
    a.nop()
    a.li(T4, 0x0000FF)                  # RIGHT -> red
    a.j("dofill")
    a.nop()
    a.label("chk_left")
    a.andi(T5, T8, 0x80)
    a.beqz(T5, "chk_cross")
    a.nop()
    a.li(T4, 0xFF0000)                  # LEFT -> blue
    a.j("dofill")
    a.nop()
    a.label("chk_cross")
    a.andi(T5, T9, 0x40)
    a.beqz(T5, "chk_start")
    a.nop()
    a.li(T4, 0x00FF00)                  # CROSS -> green
    a.j("dofill")
    a.nop()
    a.label("chk_start")
    a.andi(T5, T8, 0x08)
    a.beqz(T5, "dofill")
    a.nop()
    a.li(T4, 0xFFFFFF)                  # START -> white

    a.label("dofill")
    _fill(a, T4)

    a.li(T7, 200000)                    # breathing room between polls
    a.label("delay")
    a.addiu(T7, T7, -1)
    a.bnez(T7, "delay")
    a.nop()

    a.j("loop")
    a.nop()

    a._fix()
    return b"".join(struct.pack("<I", w) for w in a.words)


def write_exe(code, work):
    hdr = bytearray(0x800)
    hdr[0x00:0x08] = b"PS-X EXE"
    # Header layout per the core's LoadEXE: PC@0x10, TextStart@0x18,
    # TextSize@0x1C (must equal filesize-0x800), SP@0x30.
    struct.pack_into("<I", hdr, 0x10, BASE)
    struct.pack_into("<I", hdr, 0x18, BASE)
    struct.pack_into("<I", hdr, 0x1C, len(code))
    struct.pack_into("<I", hdr, 0x30, 0x801FFFF0)
    path = os.path.join(work, "PADTEST.EXE")
    with open(path, "wb") as f:
        f.write(bytes(hdr) + code)
    print(f"PADTEST.EXE: {os.path.getsize(path)} bytes "
          f"({len(code)} code bytes, {len(code) // 4} instructions)")
    return path


def main():
    work = sys.argv[1] if len(sys.argv) > 1 else "/tmp/ps1play_padtest_hw"
    os.makedirs(work, exist_ok=True)
    code = build()
    write_exe(code, work)
    return 0


if __name__ == "__main__":
    sys.exit(main())
