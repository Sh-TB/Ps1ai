#!/usr/bin/env python3
"""r30t6_buzzybee_padbuf_poke.py — Round 30 decisive isolation experiment.

State of the matrix (all disclosed today):
  - BuzzyBee image byte-identical to r23's (sha 042b94bb re-verified)
  - beetle rollback binary (79f8fac0): input dead for BuzzyBee
  - beetle REBUILT from vendored df2b53b source (447b7ebf): ALSO dead
  - ReARMed: dead for BuzzyBee
  - Tetrade (BIOS-pad) on the SAME binary+host: input ALIVE (0041ffbf)
  - doukutsu (SAME input.c driver) worked THIS MORNING pre-rollback
  - BuzzyBee kernel padbuf IS polled (input_pad=0 = valid released
    state) - only our BUTTON BITS never appear

Isolation experiment: find the game's own padbuf in RAM (pattern
00 41 FF FF near the input words 0x8005881C..) and INJECT button bits
directly: pad->btn = ~buttons. If in_update picks them up (input_pad ->
trig -> gameState 0->1), the GAME LOGIC is healthy and the failure is
exactly "core->SIO->kernel-interrupt button delivery". If the game does
NOT react even to direct padbuf injection, the failure is game-side.

This is NOT real input delivery - any gameplay data obtained this way is
recorded as input-INJECTED (disclosed, not a ladder rung). Cap amend 2->3
DISCLOSED PRE-RUN (fresh-core ledger): boot 3 = this experiment.
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

OUT = os.path.join(REPO, "scratch", "r30", "buzzybee")
SHOTS = os.path.join(OUT, "shots")
CONTENT = "/home/z/my-project/emu/games_homebrew/patched/buzzybee_ntsc_lic.cue"
CORE = "/home/z/my-project/ps1-test/cores/mednafen_psx_libretro.so"
BIOS = "/home/z/my-project/ps1-test/emu/system/openbios.bin"
BOOTS = os.path.join(OUT, "boots_used_beetle_rebuilt.json")

GS, BEST, SCORE, HEALTH = 0x80058830, 0x80058838, 0x8005883C, 0x8005EF48
IN_PAD, IN_HELD, IN_TRIG = 0x8005881C, 0x80058824, 0x80058820

R = {"task": "r30t6 BuzzyBee padbuf-poke isolation experiment",
     "boot_amendment": "cap 2->3 DISCLOSED PRE-RUN (rebuilt-core ledger): "
                       "boot 3 = direct padbuf button injection to isolate "
                       "game logic vs SIO delivery",
     "started": time.strftime("%FT%TZ", time.gmtime()),
     "events": [], "shots": []}


def dump():
    json.dump(R, open(os.path.join(OUT, "boot_log_r30t6.json"), "w"),
              indent=1, default=str)


def log(ev, **kw):
    rec = {"f": core.frames_run, "t": round(time.time() - T0, 1),
           "event": ev, **kw}
    R["events"].append(rec)
    print(f"[r30t6] {json.dumps(rec, default=str)[:240]}", flush=True)
    dump()


def snap(tag):
    arr = core.frame_rgb()
    if arr is not None:
        p = os.path.join(SHOTS, f"poke_{tag}_f{core.frames_run:05d}.png")
        Image.fromarray(arr).save(p)
        R["shots"].append({"tag": tag, "frame": core.frames_run,
                           "png": os.path.relpath(p, OUT)})
    return arr


def i32(va):
    return int.from_bytes(bytes(core.ram[va:va + 4]), "little", signed=True)


def u16(va):
    return int.from_bytes(bytes(core.ram[va:va + 2]), "little")


T0 = time.time()
led = json.load(open(BOOTS))
assert led["count"] == 2 and led["cap"] == 3, f"ledger: {led['count']}"
led["count"] = 3
json.dump(led, open(BOOTS, "w"), indent=1)
print("[r30t6] running boot 3 (cap amended 2->3 disclosed pre-run "
      "after the boot-2 crash)")

ws = os.path.join(OUT, "ws_rb")
os.makedirs(os.path.join(ws, "system"), exist_ok=True)
os.makedirs(os.path.join(ws, "saves"), exist_ok=True)
shutil.copyfile(BIOS, os.path.join(ws, "system", "openbios.bin"))
core = LibretroCore(CORE, os.path.join(ws, "system"),
                    os.path.join(ws, "saves"),
                    var_overrides={b"beetle_psx_renderer": b"software",
                                   b"beetle_psx_frame_duping": b"disabled"})
av = core.load_game(CONTENT)
log("boot", core=core.core_name, av=av)

# settle to title
for _ in range(900):
    core.run(1, set())
snap("title")
log("settle", gs=i32(GS))

# find padbuf: scan 0x80058000..0x80059500 for 00 41 FF FF
region = bytes(core.ram[0x58000:0x59500])
cands = []
off = 0
while True:
    off = region.find(b"\x00\x41\xff\xff", off)
    if off < 0:
        break
    cands.append(0x80058000 + off)
    off += 1
R["padbuf_candidates"] = [hex(a) for a in cands]
log("padbuf_scan", n=len(cands), addrs=[hex(a) for a in cands[:6]])

# verify candidate: inject START (btn = ~0x0008 = 0xFFF7 -> bytes F7 FF)
def poke_btn(addr, btn):
    """Write the active-low button u16 into a padbuf (numpy u8 view)."""
    core._ram[addr - 0x80000000 + 2] = (~btn) & 0xFF
    core._ram[addr - 0x80000000 + 3] = ((~btn) >> 8) & 0xFF


poke_addr = None
for a in cands:
    poke_btn(a, 0x0008)
    core.run_frame()
    core.run_frame()
    if i32(IN_TRIG) & 0x0008 or i32(IN_HELD) & 0x0008:
        poke_addr = a
        break
    poke_btn(a, 0x0000)
    core.run_frame()
R["poke_addr"] = hex(poke_addr) if poke_addr else None
log("poke_verify", addr=R["poke_addr"],
    trig=i32(IN_TRIG), held=i32(IN_HELD), gs=i32(GS))

if poke_addr is None:
    R["verdict"] = ("no candidate reacts to direct padbuf injection - "
                    "unexpected; game-side read path implicated")
    log("verdict", verdict=R["verdict"])
    led["log"][-1]["outcome"] = R["verdict"]
    json.dump(led, open(BOOTS, "w"), indent=1)
    sys.exit(0)

# GS transition: hold START via injection for 6 frames
for _ in range(6):
    poke_btn(poke_addr, 0x0008)
    core.run_frame()
poke_btn(poke_addr, 0x0000)
for _ in range(150):
    core.run_frame()
    if i32(GS) == 1:
        break
gs_after = i32(GS)
log("start_injected", gs=gs_after, sym={"best": i32(BEST),
                                        "score": i32(SCORE),
                                        "health": i32(HEALTH)})
snap("after_start_poke")

R["verdict"] = {
    "game_logic_alive": gs_after == 1,
    "interpretation": ("GAME LOGIC ALIVE via direct padbuf injection -> "
                       "failure isolated to core->SIO->kernel-interrupt "
                       "button delivery; deep-systems data below is "
                       "INPUT-INJECTED (disclosed, not a rung)")
    if gs_after == 1 else
    "injection verified in words but gameState did not move",
}
log("verdict", **R["verdict"])

if gs_after == 1:
    # run 1 (input-injected): flap bursts via injection, classify
    series = []
    for k in range(2400):
        btn = 0x4000 if (k % 60) < 4 else 0x0000     # CROSS
        poke_btn(poke_addr, btn)
        core.run_frame()
        series.append((i32(HEALTH), i32(SCORE), i32(GS)))
        if series[-1][2] == 5:
            break
    d = {"frames": len(series), "drain3": 0, "enemy_hit": 0,
         "flower": 0, "other": []}
    for a, b in zip(series, series[1:]):
        dh = b[0] - a[0]
        if dh == -3:
            d["drain3"] += 1
        elif dh <= -1500:
            d["enemy_hit"] += 1
        elif dh >= 500:
            d["flower"] += 1
        elif dh != 0:
            d["other"].append(dh)
    st_death = sym()
    snap("gameover_poked")
    R["run1_injected"] = {"class": d, "death_state": st_death,
                          "best_eq_score": st_death["best"] ==
                          st_death["score"]}
    log("run1_injected", **R["run1_injected"])

R["frames_total"] = core.frames_run
R["finished"] = time.strftime("%FT%TZ", time.gmtime())
dump()
led["log"][-1]["outcome"] = json.dumps(R["verdict"])
json.dump(led, open(BOOTS, "w"), indent=1)
print("[r30t6] DONE", json.dumps(R["verdict"]), flush=True)
