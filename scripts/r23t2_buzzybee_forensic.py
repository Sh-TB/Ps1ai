#!/usr/bin/env python3
"""r23t2_buzzybee_forensic.py — boot 2 forensics for the BuzzyBee intake.

Boot 1 outcome (disclosed): OpenBIOS shell cube @f180, then a BLACK screen
@f272+ — the game never rendered. Two competing hypotheses:
  H1: SYSTEM.CNF 'BOOT = ...' (spaces) broke the shello BOOT parse -> the
      EXE never loaded (working in-tree examples use 'BOOT=cdrom:\\X;1').
  H2: the EXE launched (cube->clear transition) but crashed/hung at startup
      -> black screen with game text present in RAM.

This boot decides definitively from RAM:
  - EXE_LOADED: t_size region (0x80010000..+0x48800) occupancy + distinctive
    main.c strings ('Your Last attempt', 'Credits to') present
  - ALIVE: some words changing frame-to-frame (counters/timers moving)
  - screenshots at f150/300/450/600 to see the exact screen timeline

Boot counter: 1 -> 2 (hard cap 2 for this train, asserted).
"""
import json
import os
import shutil
import sys
import time

import numpy as np
from PIL import Image

REPO = "/home/z/my-project/ps1ai"
sys.path.insert(0, REPO)
from ps1play.core.host import LibretroCore  # noqa: E402

OUT = os.path.join(REPO, "scratch", "r23", "buzzybee")
SHOTS = os.path.join(OUT, "shots")
CONTENT = "/home/z/my-project/emu/games_homebrew/patched/buzzybee_lic.cue"
CORE = "/home/z/my-project/ps1-test/cores/mednafen_psx_libretro.so"
BIOS = "/home/z/my-project/ps1-test/emu/system/openbios.bin"
BOOTS = os.path.join(OUT, "boots_used.json")

T_ADDR, T_SIZE = 0x80010000, 0x48800
STRINGS = [b"Your Last attempt", b"Your Best score", b"Credits to",
           b"BUZZYBEE", b"PS-X EXE"]

R = {"task": "r23t2 BuzzyBee boot2 forensic", "content": CONTENT,
     "started": time.strftime("%FT%TZ", time.gmtime()),
     "events": [], "shots": []}


def boots_used():
    if os.path.exists(BOOTS):
        with open(BOOTS) as f:
            return json.load(f).get("count", 0)
    return 0


def dump():
    with open(os.path.join(OUT, "boot2_log.json"), "w") as f:
        json.dump(R, f, indent=1, default=str)


def log(ev, **kw):
    rec = {"f": core.frames_run, "t": round(time.time() - T0, 1),
           "event": ev, **kw}
    R["events"].append(rec)
    print(f"[r23t2f] {json.dumps(rec, default=str)[:240]}", flush=True)
    dump()


def snap(tag):
    arr = core.frame_rgb()
    if arr is not None:
        p = os.path.join(SHOTS, f"{tag}_f{core.frames_run:05d}.png")
        Image.fromarray(arr).save(p)
        R["shots"].append({"tag": tag, "frame": core.frames_run,
                           "png": os.path.relpath(p, OUT)})
    return arr


T0 = time.time()
n0 = boots_used()
assert n0 == 1, f"boot counter {n0} != 1 (boot 2 of hard cap 2)"
with open(BOOTS) as f:
    prev = json.load(f)
with open(BOOTS, "w") as f:
    json.dump({"count": 2, "log": prev.get("log", []) +
               [{"boot": 2, "script": "r23t2_buzzybee_forensic.py",
                 "image": "buzzybee_lic.bin (unchanged, forensic boot)",
                 "t": time.strftime("%FT%TZ", time.gmtime())}]}, f, indent=1)

ws = os.path.join(OUT, "ws2")
os.makedirs(os.path.join(ws, "system"), exist_ok=True)
os.makedirs(os.path.join(ws, "saves"), exist_ok=True)
shutil.copyfile(BIOS, os.path.join(ws, "system", "openbios.bin"))
core = LibretroCore(CORE, os.path.join(ws, "system"),
                    os.path.join(ws, "saves"),
                    var_overrides={b"beetle_psx_renderer": b"software",
                                   b"beetle_psx_frame_duping": b"disabled"})
av = core.load_game(CONTENT)
log("boot", av=av)

# timeline: cube phase -> (clear) -> load -> launch
for f_target in (150, 300, 450, 600):
    while core.frames_run < f_target:
        core.run_frame()
    snap(f"t{f_target}")
    log("snap", at=f_target)

# ---- RAM forensics --------------------------------------------------------------
ram = core.ram
text = bytes(ram[T_ADDR:T_ADDR + T_SIZE])
nonzero = int(np.count_nonzero(text))
R["forensics"] = {"text_nonzero": nonzero,
                  "text_nonzero_pct": round(100 * nonzero / T_SIZE, 1),
                  "first_64": text[:64].hex()}
log("text_region", **{k: R["forensics"][k] for k in
                      ("text_nonzero", "text_nonzero_pct")})

sres = {}
for s in STRINGS:
    idx = bytes(ram[:0x200000]).find(s)
    sres[s.decode(errors="replace")] = hex(idx) if idx >= 0 else None
R["forensics"]["strings"] = sres
log("strings", **sres)

# alive check: 4096 sampled words at two instants
a = np.frombuffer(bytes(ram[0::4][:0x80000]), dtype="<u4").copy()
for _ in range(30):
    core.run_frame()
b = np.frombuffer(bytes(core.ram[0::4][:0x80000]), dtype="<u4")
changed = int(np.count_nonzero(a != b))
R["forensics"]["words_changed_over_30f"] = changed
log("alive_check", words_changed=changed)

# checksum evolution of the text region (is code still writing itself?)
t2 = bytes(core.ram[T_ADDR:T_ADDR + T_SIZE])
R["forensics"]["text_changed"] = bool(t2 != text)
log("text_changed", changed=bool(t2 != text))

# honest verdict for boot 2
R["verdict"] = {
    "EXE_LOADED": nonzero > 0x8000,
    "GAME_STRINGS": any(v for v in sres.values()),
    "ALIVE": changed > 0,
}
R["frames_total"] = core.frames_run
R["finished"] = time.strftime("%FT%TZ", time.gmtime())
dump()
print("[r23t2f] DONE", json.dumps(R["verdict"]), flush=True)
