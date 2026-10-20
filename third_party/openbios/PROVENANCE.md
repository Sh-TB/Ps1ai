# OpenBIOS (PS1) — provenance

`openbios.bin` (524288 bytes, MD5 `664ee444f38f6008d0cffc9d23e5c40d`,
SHA1 `bfd08f9d5c3def7b5b3662f9ec44af316f95aada`) is the open-source
PlayStation BIOS replacement built by the PCSX-Redux project.

- Source: `beetle-psx-libretro` commit `df2b53b` (the exact build this
  repository's core binary identifies as `Beetle PSX 0.9.44.1 df2b53b`),
  file `deps/openbios/openbios.bin`, repackaged here byte-identical.
  Upstream: https://github.com/libretro/beetle-psx-libretro (the blob's
  own upstream is https://github.com/grumpycoders/pcsx-redux,
  `src/mips/openbios`, "PS-X Realtime Kernel OpenBios, (C) 2019-2025
  PCSX-Redux").
- License: MIT (see `LICENSE.txt`, "(c) 2019 PCSX-Redux authors").
  Redistribution permitted with the license text; this file is NOT a
  copyrighted retail BIOS dump.
- Role in PS1Play: when a retail BIOS is absent, the core silently
  falls back to this exact image (verified at runtime: boot log line
  `Firmware is missing: %s` followed by the OpenBIOS shell cube). With
  `beetle_psx_override_bios = openbios` and this file named
  `openbios.bin` in the system directory, the core loads it through the
  official firmware path (`Override firmware found` in the boot log) —
  see `scripts/bios_probe.py --bios-override openbios`.
- Known limitation: the OpenBIOS tiny shell renders the rotating cube
  and parses `SYSTEM.CNF;1` (strings present in the ROM), but on this
  core build it neither responds to controller input nor dispatches a
  disc boot executable within 1800 frames (measured,
  `scripts/frame_scan.py`), so it cannot host the INPUT_CAUSALITY gate.
