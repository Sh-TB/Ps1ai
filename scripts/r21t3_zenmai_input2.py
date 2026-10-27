#!/usr/bin/env python3
"""r21t3_zenmai_input2.py — ONE-boot instrumented input run on patched zenmai.

Disc: zenmai_lic_r21.bin (8-byte SIO patch, see r21t3_zenmai_patch.py).
Game source understood from msonrm/zenmai (ps1-v1.5.0 == HEAD for input):

  * lang_menu(): UP/DOWN toggles sel (0=日本語, 1=ENGLISH), START or any face
    button confirms (edge-triggered, reads pad every field).
  * interactive_en(): T9 glide keyboard.
      row = D-pad (none=0 LEFT=1 UP=2 RIGHT=3 DOWN=4, +5 with L1)
      v   = face (R1=0 SQ=1 TRI=2 CIR=3 X=4)
      char = GP_ENG[row][v]: row4={5,j,k,l,-} row5={6,m,n,o,-} row6={7,p,q,r,s}
             row7={8,t,u,v,-} row8={9,w,x,y,z} row2={3,d,e,f,-} row3={4,g,h,i,-}
      push on the frame a face button is pressed (prev face released).
    SELECT=edge = space, R2 held 24f = backspace (tap = '0'!), R3 = clear,
    START edge with clen>0 = submit, START with clen==0 = options.

Plan (this boot):
  P0 settle 900f on language menu -> PNG
  P1 UP pulse -> PNG (cursor redraw = menu input causality), START pulse ->
     opening text (West of House) -> PNG + state save
  P2 type "look" with per-frame RAM snapshots -> find comp[] buffer +
     pad_prev mirror (RAM anchors) -> PNG per letter
  P3 submit -> response PNG + census (VLM later)
  P4 type+submit "west" -> move response (world state change) -> PNG
  P5 type+submit "look" again -> new room description -> PNG
  Fallback (if no push detected): long-hold START 300f + re-assert probes.
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
    JP_B, JP_Y, JP_SELECT, JP_START, JP_UP, JP_DOWN, JP_LEFT, JP_RIGHT,
    JP_A, JP_X, JP_L, JP_R)

OVERRIDES = {b"beetle_psx_renderer": b"software",
             b"beetle_psx_frame_duping": b"disabled",
             b"beetle_psx_override_bios": b"openbios"}
CONTENT = "/home/z/my-project/emu/games_homebrew/patched/zenmai_lic_r21.cue"
CORE = "/home/z/my-project/ps1-test/cores/mednafen_psx_libretro.so"
OUT = "/home/z/my-project/ps1ai/scratch/r21t3_zenmai"

# GP_ENG letter -> ps1play button ids
#   face: SQ=JP_Y(1) TRI=JP_X(9) CIR=JP_A(8) X=JP_B(0) R1=JP_R(11) L1=JP_L(10)
LETTERS = {
    "l": [JP_DOWN, JP_A],
    "o": [JP_LEFT, JP_L, JP_A],
    "k": [JP_DOWN, JP_Y],
    "w": [JP_DOWN, JP_L, JP_R],
    "e": [JP_UP, JP_Y],
    "s": [JP_UP, JP_L, JP_B],
    "t": [JP_RIGHT, JP_L, JP_R],
    "n": [JP_LEFT, JP_L, JP_Y],
    "h": [JP_RIGHT, JP_Y],
    "r": [JP_UP, JP_L, JP_X],
}

R = {"patch": "8-byte dummy JOY_DATA read @0x8001B370 (arms ReceivePending)",
     "phases": {}, "anchors": {}}
os.makedirs(OUT, exist_ok=True)
ws_sys = os.path.join(OUT, "ws_system")
os.makedirs(ws_sys, exist_ok=True)
shutil.copyfile("/home/z/my-project/ps1ai/third_party/openbios/openbios.bin",
                os.path.join(ws_sys, "openbios.bin"))
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


def ram_diff(a, b, top=8):
    d = np.flatnonzero(np.frombuffer(a, np.uint8) != np.frombuffer(b, np.uint8))
    return {"bytes": int(len(d)),
            "first": [int(x) for x in d[:top]],
            "first_u16": [int(x) for x in
                          np.frombuffer(b, np.uint16)[d[:top] // 2 * 2][:8]]}


core = LibretroCore(CORE, ws_sys, os.path.join(OUT, "ws_saves"),
                    var_overrides=dict(OVERRIDES))
core.load_game(CONTENT)

# ---------------- P0: settle on language menu ----------------
core.run(900)
png(core, "p0_menu_f900")
R["phases"]["p0"] = {"settle_frames": 900}
log("P0 settle done f=", core.frames_run)

# ---------------- P1: language menu ----------------
g0 = core.frame_rgb()
core.run(2, {JP_UP})
core.run(2, set())
g1 = core.frame_rgb()
up_mad = float(np.abs(g1.astype(int) - g0.astype(int)).mean())
png(core, "p1_after_up")
core.run(4, set())
R["phases"]["p1_up"] = {"screen_mad": round(up_mad, 3)}
log(f"P1 UP pulse: screen_mad={up_mad:.2f}")

core.run(2, {JP_START})
core.run(2, set())
core.run(240, set())
png(core, "p1_after_start")
open_ram = census(core, "opening")
R["phases"]["p1_start"] = {"frames": core.frames_run}
log("P1 START -> opening at f=", core.frames_run)

# ---------------- typing engine ----------------
SNAPS = {}          # frame_idx -> ram bytes (during typing windows)
FRAME_TAGS = {}     # frame_idx -> event label


def type_letter(ch):
    btns = LETTERS[ch]
    dirb = {b for b in btns if b in (JP_UP, JP_DOWN, JP_LEFT, JP_RIGHT,
                                     JP_L, JP_R)}
    face = {b for b in btns if b not in dirb}
    # release
    core.run(2, set())
    # direction first
    for f in range(2):
        core.run(1, dirb)
        SNAPS[core.frames_run - 1] = core.ram.copy()
    # face press: push happens on the first face frame
    for i, f in enumerate(range(2)):
        core.run(1, dirb | face)
        SNAPS[core.frames_run - 1] = core.ram.copy()
        if i == 0:
            FRAME_TAGS[core.frames_run - 1] = f"push_{ch}"
    # release all
    core.run(2, set())
    png(core, f"typ_{ch}_{core.frames_run}")
    log(f"typed {ch} at f={core.frames_run}")


def type_word(word):
    base = core.frames_run
    for ch in word:
        type_letter(ch)
    R["anchors"].setdefault("typing", {})[word] = {
        "start_frame": base, "end_frame": core.frames_run}


def submit():
    core.run(2, set())
    core.run(2, {JP_START})
    core.run(2, set())
    FRAME_TAGS[core.frames_run - 1] = "submit"
    log("submit at f=", core.frames_run)


# ---------------- P2: type "look" with per-frame RAM snapshots ------------
SNAPS.clear()
FRAME_TAGS.clear()
pre_typing = census(core, "pre_look")
type_word("look")
png(core, "p2_look_typed")
typed_ram = census(core, "typed_look")

# find comp[] buffer: u16 cells that became 'l'(0x6C),'o'(0x6F),'o','k'(0x6B)
pre = np.frombuffer(pre_typing, np.uint16)
post = np.frombuffer(typed_ram, np.uint16)
word = "look"
hits = []
for i in range(len(pre) - 3):
    if (pre[i] == 0 and post[i] == ord("l") and post[i + 1] == ord("o")
            and post[i + 2] == ord("o") and post[i + 3] == ord("k")):
        hits.append(i)
comp_off = hits[0] * 2 if hits else None
R["anchors"]["comp_buffer"] = {
    "offset_bytes": comp_off,
    "va": hex(0x80000000 + comp_off) if comp_off is not None else None,
    "candidate_count": len(hits)}
log("comp buffer:", R["anchors"]["comp_buffer"])

# find pad mirror: u32 static that equals last held mask during pushes
masks = []
for idx, tag in FRAME_TAGS.items():
    if tag.startswith("push_"):
        ch = tag.split("_")[1]
        m = 0
        for b in LETTERS[ch]:
            if b == JP_B: m |= 1 << 0
            elif b == JP_Y: m |= 1 << 15
            elif b == JP_SELECT: m |= 1 << 0
            elif b == JP_START: m |= 1 << 3
            elif b == JP_UP: m |= 1 << 4
            elif b == JP_DOWN: m |= 1 << 6
            elif b == JP_LEFT: m |= 1 << 7
            elif b == JP_RIGHT: m |= 1 << 5
            elif b == JP_A: m |= 1 << 13
            elif b == JP_X: m |= 1 << 12
            elif b == JP_L: m |= 1 << 10
            elif b == JP_R: m |= 1 << 11
        masks.append((idx, m))
pad_off = None
if masks and comp_off is not None:
    pre32 = np.frombuffer(pre_typing, np.uint32)
    idx0, m0 = masks[0]
    s0 = np.frombuffer(SNAPS[idx0], np.uint32)
    cand = np.flatnonzero((s0 == m0) & (pre32 != m0))
    for idx, m in masks[1:]:
        s = np.frombuffer(SNAPS[idx], np.uint32)
        cand = cand[(s[cand] == m)]
    if len(cand):
        pad_off = int(cand[0]) * 4
R["anchors"]["pad_word_mirror"] = {
    "offset_bytes": pad_off,
    "va": hex(0x80000000 + pad_off) if pad_off is not None else None,
    "note": "static pad_prev (active-high BTN_* mask) captured on push frames"}
log("pad mirror:", R["anchors"]["pad_word_mirror"])
R["phases"]["p2"] = {"snap_frames": len(SNAPS)}

# ---------------- P3: submit "look" ----------------
pre_submit = census(core, "pre_submit_look")
submit()
core.run(240, set())
resp1 = png(core, "p3_look_response")
post_submit = census(core, "post_look")
d1 = ram_diff(pre_submit, post_submit)
R["phases"]["p3_look_response"] = d1
log("P3 look response: ram delta=", d1["bytes"])

# ---------------- P4: type+submit "west" ----------------
type_word("west")
png(core, "p4_west_typed")
submit()
core.run(240, set())
resp2 = png(core, "p4_west_response")
west_ram = census(core, "post_west")
d2 = ram_diff(post_submit, west_ram)
R["phases"]["p4_west_response"] = d2
log("P4 west response: ram delta=", d2["bytes"])

# ---------------- P5: type+submit "look" again ----------------
type_word("look")
submit()
core.run(240, set())
resp3 = png(core, "p5_look2_response")
look2_ram = census(core, "post_look2")
d3 = ram_diff(west_ram, look2_ram)
R["phases"]["p5_look2_response"] = d3
log("P5 look2 response: ram delta=", d3["bytes"])
R["phases"]["total_frames"] = core.frames_run

# ---------------- save logs ----------------
with open(os.path.join(OUT, "frame_tags.json"), "w") as f:
    json.dump({str(k): v for k, v in FRAME_TAGS.items()}, f, indent=1)
np.save(os.path.join(OUT, "ram_typed_look.npy"), typed_ram)

# ---------------- VLM on key frames ----------------
def vlm(image_paths, prompt, tag):
    args = ["z-ai", "vision", "-p", prompt, "-o",
            os.path.join(OUT, f"vlm_{tag}.json")]
    for ip in image_paths:
        args += ["-i", ip]
    try:
        subprocess.run(args, capture_output=True, timeout=120)
        d = json.load(open(os.path.join(OUT, f"vlm_{tag}.json")))
        txt = d.get("content") or d.get("choices", [{}])[0].get(
            "message", {}).get("content", "")
        return str(txt).strip()
    except Exception as e:                                    # noqa: BLE001
        log("vlm failed", tag, repr(e))
        return ""


PROMPT = ("Transcribe ALL text visible in this PlayStation screen capture, "
          "top to bottom, preserving line breaks. Include the command line "
          "at the bottom if any.")
R["vlm"] = {
    "menu": vlm([os.path.join(OUT, "p0_menu_f900.png"),
                 os.path.join(OUT, "p1_after_up.png")],
                "Two screens from a Japanese game. First screen: transcribe "
                "all text. Second screen: transcribe all text and say which "
                "menu row (first or second) is highlighted.", "menu"),
    "opening": vlm([os.path.join(OUT, "p1_after_start.png")],
                   PROMPT, "opening"),
    "look": vlm([os.path.join(OUT, "p3_look_response.png")], PROMPT, "look"),
    "west": vlm([os.path.join(OUT, "p4_west_response.png")], PROMPT, "west"),
    "look2": vlm([os.path.join(OUT, "p5_look2_response.png")], PROMPT,
                 "look2"),
}
log("VLM done")

json.dump(R, open(os.path.join(OUT, "report.json"), "w"), indent=1,
          ensure_ascii=False, default=str)
core.shutdown()
LOG.close()
print("done", flush=True)
