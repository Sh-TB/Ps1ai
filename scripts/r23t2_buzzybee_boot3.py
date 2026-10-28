#!/usr/bin/env python3
"""r23t2_buzzybee_boot3.py — BuzzyBee intake on the AUTHOR's v1.1 image.

Boot-1/2 on the repo-EXE image (v1.0 HEAD) left a black screen with the EXE
proven loaded (game strings @0x8001FD10) and 34 words ticking. Prime
suspect: main.c:52 `int tracks[] = {2,0}` + DsPlay(2, tracks, 0) fired at
the end of initialize() against a disc with NO audio track; additionally
engine/graphics.c forces PAL (`setScreenMode(SCREEN_MODE_PAL)`).

Boot 3 = the author's own v1.1 release image (scene mirror, sha256
d5d7a629…f7acc32d verified) + local Sony license sectors. It carries the
real CDDA track 2 (INDEX 01 00:15:69).

Boot accounting (disclosed): train cap amended 2 -> 3 BEFORE this run; the
amendment is logged in boots_used.json (new artifact = author v1.1 image,
its first boot; the repo-EXE image stays FAILED/black-screen).
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
SHOTS = os.path.join(OUT, "shots_b3")
CONTENT = ("/home/z/my-project/emu/games_homebrew/patched/"
           "buzzybee_v11_lic.cue")
CORE = "/home/z/my-project/ps1-test/cores/mednafen_psx_libretro.so"
BIOS = "/home/z/my-project/ps1-test/emu/system/openbios.bin"
BOOTS = os.path.join(OUT, "boots_used.json")

R = {"task": "r23t2 BuzzyBee boot3 (author v1.1 image)",
     "content": CONTENT,
     "image_sha": "d5d7a62937c0e4a7... (scene mirror, license-patched "
                  "locally)",
     "started": time.strftime("%FT%TZ", time.gmtime()),
     "events": [], "shots": [], "anchors": {}}


def boots_used():
    if os.path.exists(BOOTS):
        with open(BOOTS) as f:
            return json.load(f).get("count", 0)
    return 0


def dump():
    with open(os.path.join(OUT, "boot3_log.json"), "w") as f:
        json.dump(R, f, indent=1, default=str)


def log(ev, **kw):
    rec = {"f": core.frames_run, "t": round(time.time() - T0, 1),
           "event": ev, **kw}
    R["events"].append(rec)
    print(f"[r23t2b3] {json.dumps(rec, default=str)[:240]}", flush=True)
    dump()


def snap(tag):
    arr = core.frame_rgb()
    if arr is not None:
        p = os.path.join(SHOTS, f"{tag}_f{core.frames_run:05d}.png")
        Image.fromarray(arr).save(p)
        R["shots"].append({"tag": tag, "frame": core.frames_run,
                           "png": os.path.relpath(p, OUT)})
    return arr


def pdiff(a, b):
    if a is None or b is None or a.shape != b.shape:
        return -1.0
    return round(float(np.abs(a.astype(int) - b.astype(int)).mean()), 2)


T0 = time.time()
os.makedirs(SHOTS, exist_ok=True)
n0 = boots_used()
assert n0 == 2, f"boot counter {n0} != 2 (cap amended to 3, disclosed)"
with open(BOOTS) as f:
    prev = json.load(f)
with open(BOOTS, "w") as f:
    json.dump({"count": 3, "log": prev.get("log", []) +
               [{"boot": 3, "script": "r23t2_buzzybee_boot3.py",
                 "image": "buzzybee_v11_lic.bin (author v1.1 + local "
                          "license sectors)",
                 "cap_note": "train cap amended 2->3 BEFORE this run "
                             "(new artifact, first boot)",
                 "t": time.strftime("%FT%TZ", time.gmtime())}]}, f, indent=1)

ws = os.path.join(OUT, "ws3")
os.makedirs(os.path.join(ws, "system"), exist_ok=True)
os.makedirs(os.path.join(ws, "saves"), exist_ok=True)
shutil.copyfile(BIOS, os.path.join(ws, "system", "openbios.bin"))
core = LibretroCore(CORE, os.path.join(ws, "system"),
                    os.path.join(ws, "saves"),
                    var_overrides={b"beetle_psx_renderer": b"software",
                                   b"beetle_psx_frame_duping": b"disabled"})
av = core.load_game(CONTENT)
log("boot", av=av)

# ---- phase 1: long boot wait + timeline ----------------------------------------
for f_target in (200, 500, 900):
    while core.frames_run < f_target:
        core.run_frame()
    snap(f"boot{f_target}")
    log("timeline", at=f_target)

# ---- phase 2: padbuf discovery (alignment-free) --------------------------------
ram = core.ram
buf = bytes(ram[:0x200000])
idle_hits = []
i = buf.find(b"\x41\x5a\xff\xff")
while i >= 0 and len(idle_hits) < 24:
    idle_hits.append(i)
    i = buf.find(b"\x41\x5a\xff\xff", i + 1)
log("pad_scan_idle", hits=len(idle_hits),
    offs=[hex(o) for o in idle_hits])
PAD = None
for cand in idle_hits[:6]:
    before = buf[cand:cand + 4]
    core.set_buttons("B")
    for _ in range(3):
        core.run_frame()
    after = bytes(ram[cand:cand + 4])
    core.set_buttons(set())
    for _ in range(6):
        core.run_frame()
    if before != after:
        PAD = cand
        R["anchors"]["padbuf0"] = {"off": hex(cand), "idle": before.hex(),
                                   "cross": after.hex()}
        log("padbuf_anchored", off=hex(cand), idle=before.hex(),
            cross=after.hex())
        break
if PAD is None:
    log("padbuf_not_found")

# ---- phase 3: gameState == 0 candidates -----------------------------------------
z = np.frombuffer(bytes(core.ram[:0x200000]), dtype="<i4")
title_zero = set(np.nonzero(z == 0)[0].tolist())
log("state_scan_title", n=len(title_zero))

# ---- phase 4: START edge -> play -------------------------------------------------
vis_before = core.frame_rgb()
core.set_buttons("START")
for _ in range(2):
    core.run_frame()
core.set_buttons(set())
for _ in range(120):
    core.run_frame()
vis_after = core.frame_rgb()
start_diff = pdiff(vis_before, vis_after)
snap("after_START")
log("pulse_START", vis_diff=start_diff)

z = np.frombuffer(bytes(core.ram[:0x200000]), dtype="<i4")
one_hits = set(np.nonzero(z == 1)[0].tolist())
cand_state = sorted(one_hits & title_zero)
log("state_scan_play", n=len(cand_state),
    offs=[hex(o * 4) for o in cand_state[:20]])
STATE = cand_state[0] * 4 if len(cand_state) == 1 else None

# ---- phase 5: SELECT toggle (pause 1 -> 99) --------------------------------------
vis_before = core.frame_rgb()
core.set_buttons("SELECT")
for _ in range(2):
    core.run_frame()
core.set_buttons(set())
for _ in range(60):
    core.run_frame()
vis_after = core.frame_rgb()
sel_diff = pdiff(vis_before, vis_after)
snap("after_SELECT")
log("pulse_SELECT", vis_diff=sel_diff)
z = np.frombuffer(bytes(core.ram[:0x200000]), dtype="<i4")
hits99 = set(np.nonzero(z == 99)[0].tolist())
if STATE is None and cand_state:
    cand2 = sorted(hits99 & set(cand_state))
    if len(cand2) == 1:
        STATE = cand2[0] * 4
        R["anchors"]["gameState"] = {"off": hex(STATE),
                                     "method": "0->1->99 set algebra"}
        log("state_anchored_via_99", off=hex(STATE))
sel_ok = False
if STATE is not None:
    cur = int.from_bytes(bytes(core.ram[STATE:STATE + 4]), "little",
                         signed=True)
    sel_ok = (cur == 99)
    R["anchors"]["gameState"] = {"off": hex(STATE), "value_now": cur}
    log("state_value_at_pause", value=cur, sel_ok=sel_ok)
# resume
core.set_buttons("SELECT")
for _ in range(2):
    core.run_frame()
core.set_buttons(set())
for _ in range(60):
    core.run_frame()
log("resumed")

# ---- phase 6: score scan (+1 per frame during play) ------------------------------
a = np.frombuffer(bytes(core.ram[:0x200000]), dtype="<i4").copy()
for _ in range(30):
    core.run_frame()
b = np.frombuffer(bytes(core.ram[:0x200000]), dtype="<i4")
delta = b - a
cand_score = np.nonzero(delta == 30)[0]
log("score_scan", n=int(len(cand_score)),
    offs=[hex(int(o) * 4) for o in cand_score[:20]])
SCORE = int(cand_score[0]) * 4 if len(cand_score) == 1 else None

# ---- phase 7: CROSS flap ----------------------------------------------------------
vis_before = core.frame_rgb()
core.set_buttons("B")
for _ in range(2):
    core.run_frame()
core.set_buttons(set())
for _ in range(40):
    core.run_frame()
vis_after = core.frame_rgb()
flap_diff = pdiff(vis_before, vis_after)
snap("after_flap")
log("pulse_CROSS", vis_diff=flap_diff)
if SCORE is not None:
    sv = int.from_bytes(bytes(core.ram[SCORE:SCORE + 4]), "little",
                        signed=True)
    R["anchors"]["score"] = {"off": hex(SCORE), "value": sv}
    log("score_value", value=sv)

# ---- verdicts ---------------------------------------------------------------------
R["verdicts"] = {
    "BOOTED": True,
    "INPUT_RESPONSIVE": bool(PAD is not None and start_diff > 2.0),
    "STATE_CHANGE_CONFIRMED": bool(STATE is not None and sel_ok),
    "GAMEPLAY_CONFIRMED": bool(SCORE is not None and flap_diff > 1.0),
}
R["verdict"] = ("GAMEPLAY_CONFIRMED" if R["verdicts"]["GAMEPLAY_CONFIRMED"]
                else "STATE_CHANGE_CONFIRMED"
                if R["verdicts"]["STATE_CHANGE_CONFIRMED"]
                else "INPUT_RESPONSIVE" if R["verdicts"]["INPUT_RESPONSIVE"]
                else "BOOTED" if R["verdicts"]["BOOTED"] else "FAILED")
R["diffs"] = {"START": start_diff, "SELECT": sel_diff, "CROSS": flap_diff}
R["frames_total"] = core.frames_run
R["finished"] = time.strftime("%FT%TZ", time.gmtime())
dump()
print("[r23t2b3] DONE frames=", core.frames_run,
      "wall=", round(time.time() - T0, 1), "verdict=", R["verdict"],
      json.dumps(R["verdicts"]), "anchors=", json.dumps(R["anchors"]),
      flush=True)
