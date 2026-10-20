#!/usr/bin/env python3
"""target_exe_probe.py — TARGET_GAME-grade probe of the repository's
SLUS_012.12 main binary, booted BIOS-free through the exe-direct v2
path (no disc image needed, no disc image used).

The probe answers, with executable evidence and zero new copyrighted
acquisitions: "how far does the REAL game binary get on the PS1Play
chain before it needs something we do not have?"  The EXE was supplied
by the repository owner inside the original v0.5 source drop
(ps1play/re/SLUS_012.12).  The probe is STRICTLY observational: it
never writes game RAM, never patches the binary, and only diffs
memory/VRAM snapshots and the core's own logs.

Why the padded EXE: the SLUS_012.12 header records t_size = full file
size (0x97800, header included).  The core's standalone loader
requires TextSize == file_size - 0x800, so the probe appends exactly
2048 zero bytes.  The real text (0x97000 bytes) still lands at the
header-declared 0x80010000; the padding compensates the header's own
over-count and sits as inert zeros just past the text.

Observation regions (all passive, diffed against a post-load baseline):
  lowram  [0x000000, 0x010000)  game-written handlers / vectors
  text    [0x010000, 0x0A8000)  loader copy (expected nonzero)
  tail    [0x0A8000, 0x1FF000)  game data / BSS / heap writes
  stack   [0x1FF000, 0x200000)  stack pushes (SP = 0x801FFFF0)
  vram    1 MiB                 GPU writes
  frame   GPU output            nonzero-pixel fraction (frame_rgb)

Verdicts (honest):
  DISPATCHED   real game code visibly executed (any change outside the
               loader copy, VRAM activity, or GPU output).  Gameplay is
               NOT claimed.
  NO_DISPATCH  nothing outside the loader copy ever changed.
Wall identification: bounded PS1Play CPU-exception PC trace + the
exe-direct v2 boot log line.

Exit codes: 0 probe executed (any verdict) | 3 setup error.
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import time

import numpy as np

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)

from ps1play.core.host import LibretroCore  # noqa: E402

DEF_EXE = os.path.join(_REPO, "ps1play", "re", "SLUS_012.12")
DEF_CORE = os.environ.get(
    "M1_CORE", "/home/z/my-project/ps1-test/cores/mednafen_psx_libretro.so")
DEF_OUT = "/tmp/ps1play_target_exe_probe"

OVERRIDES = {b"beetle_psx_renderer": b"software",
             b"beetle_psx_hw_renderer": b"software",
             b"beetle_psx_frame_duping": b"disabled"}

PAD = 0x800
REGIONS = {
    "lowram": (0x000000, 0x010000),
    "text":   (0x010000, 0x0A8000),
    "tail":   (0x0A8000, 0x1FF000),
    "stack":  (0x1FF000, 0x200000),
}
EXC_RE = re.compile(
    r"PS1Play CPU exception (\d+): PC=0x([0-9A-Fa-f]{8}) instr=0x([0-9A-Fa-f]{8})")


def md5(path):
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def parse_header(data):
    pc0, gp0, t_addr, t_size = struct.unpack("<4I", data[0x10:0x20])
    b_addr, b_size = struct.unpack("<2I", data[0x28:0x30])
    s_addr, _s_size = struct.unpack("<2I", data[0x30:0x38])
    return {"pc0": pc0, "gp0": gp0, "t_addr": t_addr, "t_size": t_size,
            "b_addr": b_addr, "b_size": b_size, "sp": s_addr,
            "magic": data[0:8].decode("ascii", "replace")}


def _head():
    try:
        return subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"], cwd=_REPO,
            capture_output=True, timeout=10).stdout.decode().strip()
    except Exception:                                           # noqa: BLE001
        return "unknown"


def region_stats(ram, base, tag):
    lo, hi = REGIONS[tag]
    cur = ram[lo:hi]
    delta = int((cur != base[lo:hi]).sum())
    nonzero = int((cur != 0).sum())
    return {"changed_vs_baseline": delta, "nonzero_abs": nonzero}


def exceptions_in(log_history):
    out = []
    for line in log_history:
        m = EXC_RE.search(line)
        if m:
            out.append({"n": int(m.group(1)), "pc": m.group(2).upper(),
                        "instr": m.group(3).upper()})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--exe", default=DEF_EXE)
    ap.add_argument("--core", default=DEF_CORE)
    ap.add_argument("--out", default=DEF_OUT)
    ap.add_argument("--frames", type=int, default=900)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    if not os.path.exists(a.exe):
        print(json.dumps({"error": f"EXE not found: {a.exe}"}))
        return 3
    if not os.path.exists(a.core):
        print(json.dumps({"error": f"core not found: {a.core}"}))
        return 3

    shutil.rmtree(a.out, ignore_errors=True)
    os.makedirs(a.out)

    with open(a.exe, "rb") as f:
        raw = f.read()
    hdr = parse_header(raw)
    padded_path = os.path.join(a.out, "SLUS_012.12.pad.exe")
    with open(padded_path, "wb") as f:
        f.write(raw)
        f.write(b"\x00" * PAD)

    ws = os.path.join(a.out, "ws")
    sysdir, savedir = (os.path.join(ws, x) for x in ("system", "saves"))
    os.makedirs(sysdir)
    os.makedirs(savedir)
    shutil.copyfile(os.path.join(_REPO, "third_party", "openbios",
                                 "openbios.bin"),
                    os.path.join(sysdir, "openbios.bin"))

    res = {"tool": "target_exe_probe", "version": 1, "head": _head(),
           "core": a.core, "core_md5": md5(a.core),
           "exe": os.path.abspath(a.exe), "exe_md5": md5(a.exe),
           "exe_size": len(raw), "header": hdr,
           "padding_bytes": PAD,
           "padding_reason": ("header t_size counts the full file; the "
                              "core requires TextSize == size - 0x800"),
           "frames": a.frames, "content": "EXE only — NO disc image"}

    t0 = time.time()
    try:
        core = LibretroCore(a.core, sysdir, savedir,
                            var_overrides=dict(OVERRIDES))
        core.load_game(padded_path)
        core.set_buttons(set())

        boot_line = next((l for l in core.log_history
                          if "exe-direct boot" in l), None)
        res["boot_log"] = boot_line

        base = np.array(core.ram, copy=True)
        vram_base = (np.array(core.vram, copy=True)
                     if core.vram is not None else None)

        checkpoints = sorted({60, 300, a.frames})
        for cp in checkpoints:
            while core.frames_run < cp:
                core.run_frame()
            res[f"t{cp}"] = {tag: region_stats(core.ram, base, tag)
                             for tag in REGIONS}
            res[f"t{cp}"]["exceptions"] = exceptions_in(
                core.log_history)[-12:]

        vram = core.vram
        res["vram_changed_vs_baseline"] = (
            int((vram != vram_base).sum()) if vram is not None
            and vram_base is not None else None)

        shot = os.path.join(a.out, "last_frame.png")
        arr = core.frame_rgb()
        if arr is not None:
            try:
                from PIL import Image
                Image.fromarray(arr).save(shot)
                res["last_frame_png"] = shot
            except Exception:                                   # noqa: BLE001
                res["last_frame_png"] = None
            res["frame_nonzero_fraction"] = round(
                float((arr != 0).any(axis=2).mean()), 6)
        else:
            res["frame_nonzero_fraction"] = 0.0

        tail_changed = res[f"t{a.frames}"]["tail"]["changed_vs_baseline"]
        low_changed = res[f"t{a.frames}"]["lowram"]["changed_vs_baseline"]
        stack_changed = res[f"t{a.frames}"]["stack"]["changed_vs_baseline"]
        vram_changed = res["vram_changed_vs_baseline"] or 0
        gpu_active = res["frame_nonzero_fraction"] > 0.0
        dispatched = bool(tail_changed or low_changed or stack_changed
                          or vram_changed or gpu_active)
        res["dispatched"] = dispatched
        res["verdict"] = "DISPATCHED" if dispatched else "NO_DISPATCH"

        exc = res[f"t{a.frames}"]["exceptions"]
        if exc:
            pcs = sorted({e["pc"] for e in exc})
            res["wall"] = (f"CPU exceptions at PC={','.join(pcs)} "
                           f"(bounded trace, {len(exc)} sampled)")
        elif dispatched:
            res["wall"] = ("no exception in window; execution advanced "
                           "(see per-region diffs)")
        else:
            res["wall"] = ("silent stall: no change outside the loader "
                           "copy, no GPU output, no exception trace")
        res["frames_rendered"] = core.frame_count
        log_tail = []
        for l in core.log_history:
            if l not in log_tail and "PS1Play" in l:
                log_tail.append(l)
        res["ps1play_log_lines"] = log_tail[-12:]
        core.shutdown()
    except Exception as e:                                      # noqa: BLE001
        res["verdict"] = "HARNESS_ERROR"
        res["error"] = repr(e)
    res["elapsed_s"] = round(time.time() - t0, 1)

    with open(os.path.join(a.out, "target_exe_probe_result.json"),
              "w") as f:
        json.dump(res, f, indent=1, default=str)
    if a.json:
        print(json.dumps(res, indent=1, default=str))
    else:
        print(f"exe: {res['exe_md5']}  header: pc0=0x{hdr['pc0']:08X} "
              f"t_addr=0x{hdr['t_addr']:08X} t_size=0x{hdr['t_size']:X} "
              f"sp=0x{hdr['sp']:08X}")
        print(f"boot: {res.get('boot_log')}")
        for cp in checkpoints:
            st = res.get(f"t{cp}", {})
            regs = " ".join(
                f"{k}={st[k]['changed_vs_baseline']}"
                for k in ("lowram", "text", "tail", "stack") if k in st)
            print(f"  t{cp:>4}: changed[{regs}] exc={len(st.get('exceptions', []))}")
        print(f"vram_changed={res.get('vram_changed_vs_baseline')} "
              f"frame_nonzero={res.get('frame_nonzero_fraction')}")
        print(f"verdict: {res.get('verdict')}  wall: {res.get('wall')}")
        print(f"records: {os.path.join(a.out, 'target_exe_probe_result.json')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
