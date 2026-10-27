#!/usr/bin/env python3
"""r21t3_zenmai_input3.py — BOOT 2 (final): patched-disc instrumented input run.

Disc: zenmai_lic_r21b.bin (patch2 = padtest-verified SIO recipe grafted into
zenmai pad_exchange; see r21t3_zenmai_patch2.py).

Sequence: settle 600f -> census -> UP pulse (per-frame RAM) -> census/PNG
(menu redraw = input causality) -> START pulse -> 300f -> census/PNG ->
type "look" (per-frame RAM) -> comp-buffer + pad-mirror hunt -> submit ->
300f -> PNG/census -> type+submit "west" -> PNG/census -> done.
"""
import json
import os
import shutil
import subprocess
import sys

import numpy as np
from PIL import Image

_REPO = "/home/z/my-project/ps1ai"
sys.path.insert(0, _REPO)
from ps1play.core.host import LibretroCore  # noqa: E402
from ps1play.core.inputmap import (  # noqa: E402
    JP_B, JP_Y, JP_START, JP_UP, JP_DOWN, JP_LEFT, JP_RIGHT,
    JP_A, JP_X, JP_L, JP_R)

OVERRIDES = {b"beetle_psx_renderer": b"software",
             b"beetle_psx_frame_duping": b"disabled",
             b"beetle_psx_override_bios": b"openbios"}
CONTENT = "/home/z/my-project/emu/games_homebrew/patched/zenmai_lic_r21b.cue"
CORE = "/home/z/my-project/ps1-test/cores/mednafen_psx_libretro.so"
OUT = "/home/z/my-project/ps1ai/scratch/r21t3_zenmai/boot2"
os.makedirs(OUT, exist_ok=True)

LETTERS = {                       # ps1play ids; BTN bit = PSX pad bit
    "l": [JP_DOWN, JP_A],
    "o": [JP_LEFT, JP_L, JP_A],
    "k": [JP_DOWN, JP_Y],
    "w": [JP_DOWN, JP_L, JP_R],
    "e": [JP_UP, JP_Y],
    "s": [JP_UP, JP_L, JP_B],
    "t": [JP_RIGHT, JP_L, JP_R],
}
BTN_BIT = {0: 1 << 0, 1: 1 << 15, 3: 1 << 3, 4: 1 << 4, 5: 1 << 6,
           6: 1 << 7, 7: 1 << 5, 8: 1 << 13, 9: 1 << 12, 10: 1 << 10,
           11: 1 << 11}

R = {"patch": "padtest recipe: CTRL=0 -> CTRL=0x1007 + dummy-read drain/arm",
     "phases": {}, "anchors": {}}
LOG = open(os.path.join(OUT, "run_log.txt"), "w")


def log(*a):
    s = " ".join(str(x) for x in a)
    print(s, flush=True)
    LOG.write(s + "\n")
    LOG.flush()


def png(core, tag):
    arr = core.frame_rgb()
    if arr is not None:
        Image.fromarray(arr).save(os.path.join(OUT, f"{tag}.png"))
    return arr


def census(core, tag):
    np.save(os.path.join(OUT, f"ram_{tag}.npy"), core.ram.copy())
    return core.ram.copy()


def ram_diff(a, b, top=10):
    d = np.flatnonzero(np.frombuffer(a, np.uint8) != np.frombuffer(b, np.uint8))
    return {"bytes": int(len(d)),
            "first_offs": [int(x) for x in d[:top]],
            "first_u16": [int(x) for x in
                          np.frombuffer(b, np.uint16)[d[:top] // 2 * 2][:10]]}


ws_sys = os.path.join(OUT, "ws_system")
os.makedirs(ws_sys, exist_ok=True)
shutil.copyfile("/home/z/my-project/ps1ai/third_party/openbios/openbios.bin",
                os.path.join(ws_sys, "openbios.bin"))
core = LibretroCore(CORE, ws_sys, os.path.join(OUT, "ws_saves"),
                    var_overrides=dict(OVERRIDES))
core.load_game(CONTENT)

# ---- P0 settle -----------------------------------------------------------
core.run(600)
png(core, "p0_menu_f600")
A = census(core, "menu_before")
log("P0 settle f=", core.frames_run)

# ---- P1 UP pulse with per-frame RAM --------------------------------------
SNAPS, TAGS = {}, {}
core.run(2, set())
for _ in range(3):
    core.run(1, {JP_UP})
    SNAPS[core.frames_run - 1] = core.ram.copy()
    TAGS[core.frames_run - 1] = "up_held"
for _ in range(2):
    core.run(1, set())
    SNAPS[core.frames_run - 1] = core.ram.copy()
core.run(8, set())
B = census(core, "menu_after_up")
png(core, "p1_after_up")
d_up = ram_diff(A, B)
R["phases"]["p1_up"] = d_up
log("P1 UP: ram delta=", d_up["bytes"])

# ---- P2 START -> game ------------------------------------------------------
core.run(2, {JP_START})
core.run(2, set())
core.run(300, set())
C = census(core, "after_start")
png(core, "p2_after_start")
d_start = ram_diff(B, C)
R["phases"]["p2_start"] = d_start
log("P2 START: ram delta=", d_start["bytes"])

# ---- typing engine ---------------------------------------------------------
def type_letter(ch):
    btns = LETTERS[ch]
    dirb = {b for b in btns if b in (JP_UP, JP_DOWN, JP_LEFT, JP_RIGHT,
                                     JP_L, JP_R)}
    face = {b for b in btns if b not in dirb}
    core.run(2, set())
    for _ in range(2):
        core.run(1, dirb)
        SNAPS[core.frames_run - 1] = core.ram.copy()
    core.run(1, dirb | face)
    SNAPS[core.frames_run - 1] = core.ram.copy()
    TAGS[core.frames_run - 1] = f"push_{ch}"
    core.run(1, dirb | face)
    SNAPS[core.frames_run - 1] = core.ram.copy()
    core.run(2, set())
    png(core, f"typ_{ch}_{core.frames_run}")
    log(f"typed {ch} f={core.frames_run}")


def type_word(word):
    for ch in word:
        type_letter(ch)


SNAPS, TAGS = {}, {}
pre_typ = census(core, "pre_type")
type_word("look")
typed = census(core, "typed_look")
png(core, "p3_look_typed")

pre16 = np.frombuffer(pre_typ, np.uint16)
post16 = np.frombuffer(typed, np.uint16)
hunt = {}
for name, seq in [("en_look", [0x6C, 0x6F, 0x6F, 0x6B]),
                  ("ja_look", [0x306D, 0x3078, 0x3078, 0x306B])]:
    hits = []
    for i in range(len(pre16) - 5):
        if pre16[i] == 0 and pre16[i + 4] == 0 and \
                all(post16[i + k] == v for k, v in enumerate(seq)):
            hits.append(i * 2)
    hunt[name] = {"count": len(hits), "offsets": hits[:4]}
R["anchors"]["comp_hunt"] = hunt
log("comp hunt:", json.dumps(hunt))

# pad mirror: u32 equal to held BTN mask on push frames, not equal before
pre32 = np.frombuffer(pre_typ, np.uint32)
cand = None
for idx, tag in sorted(TAGS.items()):
    if not tag.startswith("push_"):
        continue
    ch = tag.split("_")[1]
    m = 0
    for b in LETTERS[ch]:
        m |= BTN_BIT.get(b, 0)
    s = np.frombuffer(SNAPS[idx], np.uint32)
    c = np.flatnonzero(s == m)
    cand = c if cand is None else cand[np.isin(cand, c)]
    if cand is not None and len(cand) == 0:
        break
if cand is not None and len(cand):
    R["anchors"]["pad_mirror"] = {
        "offsets": [int(x) * 4 for x in cand[:6]],
        "va": [hex(0x80000000 + int(x) * 4) for x in cand[:6]]}
else:
    R["anchors"]["pad_mirror"] = None
log("pad mirror:", R["anchors"]["pad_mirror"])

# ---- P4 submit look --------------------------------------------------------
pre_sub = census(core, "pre_submit")
core.run(2, {JP_START})
core.run(2, set())
core.run(300, set())
D = census(core, "post_look")
png(core, "p4_look_response")
R["phases"]["p4_look"] = ram_diff(pre_sub, D)
log("P4 look resp delta=", R["phases"]["p4_look"]["bytes"])

# ---- P5 west ---------------------------------------------------------------
type_word("west")
png(core, "p5_west_typed")
core.run(2, {JP_START})
core.run(2, set())
core.run(300, set())
E = census(core, "post_west")
png(core, "p5_west_response")
R["phases"]["p5_west"] = ram_diff(D, E)
log("P5 west resp delta=", R["phases"]["p5_west"]["bytes"])
R["phases"]["total_frames"] = core.frames_run

with open(os.path.join(OUT, "frame_tags.json"), "w") as f:
    json.dump({str(k): v for k, v in TAGS.items()}, f, indent=1)

# ---- VLM -------------------------------------------------------------------
def vlm(paths, prompt, tag):
    args = ["z-ai", "vision", "-p", prompt, "-o",
            os.path.join(OUT, f"vlm_{tag}.json")]
    for p in paths:
        args += ["-i", p]
    try:
        subprocess.run(args, capture_output=True, timeout=120)
        d = json.load(open(os.path.join(OUT, f"vlm_{tag}.json")))
        return str(d["choices"][0]["message"]["content"]).strip()
    except Exception as e:                                    # noqa: BLE001
        log("vlm fail", tag, repr(e))
        return ""


R["vlm"] = {
    "menu": vlm([os.path.join(OUT, "p0_menu_f600.png"),
                 os.path.join(OUT, "p1_after_up.png")],
                "Two game-menu screenshots. For EACH, list the menu rows and "
                "state which row is highlighted (gold/colored) vs plain "
                "white.", "menu"),
    "after_start": vlm([os.path.join(OUT, "p2_after_start.png")],
                       "Transcribe all text on this game screen.", "start"),
    "look": vlm([os.path.join(OUT, "p4_look_response.png")],
                "Transcribe all text on this game screen, including any "
                "command line at the bottom.", "look"),
    "west": vlm([os.path.join(OUT, "p5_west_response.png")],
                "Transcribe all text on this game screen, including any "
                "command line at the bottom.", "west"),
}
log("VLM done")

json.dump(R, open(os.path.join(OUT, "report.json"), "w"), indent=1,
          ensure_ascii=False, default=str)
core.shutdown()
LOG.close()
print("done", flush=True)
