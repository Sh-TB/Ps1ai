#!/usr/bin/env python3
"""r22t1R_boot2.py — MSPSX boot 2 (license-patched disc, EXE UNPATCHED).

Boot-1 REFUTED the dead-input prediction (pad_buff[0]=41 5A FF FF, held=0,
title stable) and closed the evidence.md patch gate, so boot 2 runs the same
license-only image (`mspsx_lic.cue`) and spends the boot on the causality
program the verdict ladder needs:
  - title live + stable (BOOTED_TITLE anchor)
  - START 2-frame pulse -> title exits, board initializes
  - RIGHT / DOWN 2-frame pulses -> cursorX/cursorY deltas (INPUT_RESPONSIVE)
  - CROSS 2-frame pulse -> board cell revealed + revealed_total increment
    + screen change (RUNNING closed loop), VLM on the revealed tile
The RXEN-patched image is PREPARED but NOT BOOTED (see
scripts/r22t1R_rxen_patch.py header + evidence.md).

Boot counter: boots_used.json must be exactly 1 -> 2 (hard cap 2).
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

OUT = os.path.join(REPO, "scratch", "r22t1_mspsx")
SHOTS = os.path.join(OUT, "shots_b2")
CONTENT = "/home/z/my-project/emu/games_homebrew/patched/mspsx_lic.cue"
CORE = "/home/z/my-project/ps1-test/cores/mednafen_psx_libretro.so"
BIOS = "/home/z/my-project/ps1-test/emu/system/openbios.bin"
BOOTS = os.path.join(OUT, "boots_used.json")

PADB, PADL = 0x1AC48, 0x18D08
OLDH, PRES, HELD = 0x18CF8, 0x18CFC, 0x18CFE
BOARD, CURX, CURY = 0x199DC, 0x18CD4, 0x18CD0
REVT, VALT, MINC = 0x18CDC, 0x18CD8, 0x18CEC
CTRLDIS, LOST, FCLK = 0x18CE4, 0x18CE0, 0x18CCC

R = {"task": "r22t1-R boot2", "content": CONTENT, "exe": "UNPATCHED "
     "(RXEN patch gate closed by boot-1 refutation)",
     "started": time.strftime("%FT%TZ", time.gmtime()),
     "events": [], "shots": [], "pulses": {}}


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
    print(f"[b2] {json.dumps(rec, default=str)[:220]}", flush=True)
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


def u16(va):
    return int.from_bytes(bytes(core.ram[va:va + 2]), "little")


def i32(va):
    return int.from_bytes(bytes(core.ram[va:va + 4]), "little", signed=True)


def sym():
    return {"pad_buff0": bytes(core.ram[PADB:PADB + 4]).hex(),
            "pad_buff_len0": i32(PADL), "oldHeld": u16(OLDH),
            "pressed": u16(PRES), "held": u16(HELD),
            "cursorX": i32(CURX), "cursorY": i32(CURY),
            "revealed_total": i32(REVT), "valid_total": i32(VALT),
            "mine_count": i32(MINC), "control_disable": core.ram[CTRLDIS],
            "lost": core.ram[LOST], "FIRST_CLICK": core.ram[FCLK],
            "board_nonzero": int(np.count_nonzero(core.ram[BOARD:BOARD + 4608]))}


def pulse(button, hold=2, settle=45, snapset=(10, 25, 45)):
    """2-frame press + settle; per-frame pad_buff/pressed + sym series."""
    before = core.frame_rgb()
    series = []
    core.set_buttons(button)
    for _ in range(hold):
        core.run_frame()
        series.append({"f": core.frames_run,
                       "pad_buff0": bytes(core.ram[PADB:PADB + 4]).hex(),
                       "pressed": u16(PRES), "held": u16(HELD),
                       "cursorX": i32(CURX), "cursorY": i32(CURY)})
    core.set_buttons(set())
    for s in range(settle):
        core.run_frame()
        if (s + 1) in snapset:
            snap(f"p_{button.lower()}_{s + 1}")
            series.append({"f": core.frames_run,
                           "pad_buff0": bytes(core.ram[PADB:PADB + 4]).hex(),
                           "pressed": u16(PRES), "held": u16(HELD),
                           "cursorX": i32(CURX), "cursorY": i32(CURY)})
    after = core.frame_rgb()
    res = {"button": button, "hold": hold, "series": series,
           "vis_diff": pdiff(before, after), "sym_after": sym()}
    return res


def board_counts():
    """Decode board region under both candidate layouts."""
    reg = core.ram[BOARD:BOARD + 4608]
    out = {}
    for name, fn in (("A_x192_y12", lambda x, y: x * 192 + y * 12),
                     ("B_y192_x12", lambda x, y: y * 192 + x * 12)):
        cells = []
        for x in range(16):
            for y in range(12):
                o = fn(x, y)
                cells.append({"x": x, "y": y, "off": o,
                              "revealed": int(reg[o + 1]),
                              "flagged": int(reg[o + 2]),
                              "mine": int(reg[o]),
                              "neighbors": int.from_bytes(
                                  bytes(reg[o + 4:o + 8]), "little",
                                  signed=True)})
        out[name] = {
            "revealed_n": sum(1 for c in cells if c["revealed"] == 1),
            "flagged_n": sum(1 for c in cells if c["flagged"] == 1),
            "cursor_cell": None, "cells": cells}
    return out


T0 = time.time()
for d in (OUT, SHOTS):
    os.makedirs(d, exist_ok=True)
n0 = boots_used()
assert n0 == 1, f"boot counter {n0} != 1 (boot 2 of hard cap 2)"
with open(BOOTS) as f:  # read BEFORE truncating
    prev = json.load(f)
with open(BOOTS, "w") as f:
    json.dump({"count": 2, "log": prev.get("log", []) +
               [{"boot": 2, "script": "r22t1R_boot2.py",
                 "image": "mspsx_lic.bin (license only, EXE unpatched)",
                 "t": time.strftime("%FT%TZ", time.gmtime())}]}, f, indent=1)

ws = os.path.join(OUT, "ws")
shutil.copyfile(BIOS, os.path.join(ws, "system", "openbios.bin"))
core = LibretroCore(CORE, os.path.join(ws, "system"),
                    os.path.join(ws, "saves"),
                    var_overrides={b"beetle_psx_renderer": b"software",
                                   b"beetle_psx_frame_duping": b"disabled"})
av = core.load_game(CONTENT)
log("boot", boot_no=2, core=core.core_name, ver=core.core_ver, av=av)

# ---- phase 1: title live + stable --------------------------------------------
for _ in range(120):
    core.run_frame()
pad_live = False
for _ in range(600):
    core.run_frame()
    if i32(PADL) >= 4 and bytes(core.ram[PADB:PADB + 4]) == b"\x41\x5A\xff\xff":
        pad_live = True
        break
log("title_wait", pad_live=pad_live, sym=sym())
snap("title")
still = []
for _ in range(60):
    core.run_frame()
    still.append(u16(HELD))
title_stable = max(still) == 0 and i32(REVT) == 0
R["title"] = {"pad_live": pad_live, "held_series_max": max(still),
              "stable": title_stable, "sym": sym()}
snap("title_stable")
log("title_stable_check", **R["title"])

# ---- phase 2: START pulse -> game --------------------------------------------
st = pulse("START", hold=2, settle=60, snapset=(15, 30, 60))
R["pulses"]["START"] = st
log("pulse_START", vis_diff=st["vis_diff"],
    press=[s["pad_buff0"] for s in st["series"][:2]],
    sym_after=st["sym_after"])
board_f = None
for _ in range(240):
    core.run_frame()
    if np.count_nonzero(core.ram[BOARD:BOARD + 4608]) > 0 and \
            core.ram[CTRLDIS] == 0:
        board_f = core.frames_run
        break
snap("game")
R["game_start"] = {"board_ready_f": board_f, "sym": sym()}
log("game_start", **R["game_start"])

# ---- phase 3: idle cursor-static check ---------------------------------------
cx0, cy0 = i32(CURX), i32(CURY)
for _ in range(30):
    core.run_frame()
idle_static = (cx0, cy0) == (i32(CURX), i32(CURY))
R["idle"] = {"a": (cx0, cy0), "b": (i32(CURX), i32(CURY)),
             "static": idle_static}
log("idle_cursor", **R["idle"])

# ---- phase 4: D-pad anchors (2-frame pulses) ---------------------------------
rp = pulse("RIGHT", hold=2, settle=30)
rp["dx"] = i32(CURX) - cx0
rp["dy"] = i32(CURY) - cy0
R["pulses"]["RIGHT"] = rp
log("pulse_RIGHT", dx=rp["dx"], dy=rp["dy"],
    press=[s["pad_buff0"] for s in rp["series"][:2]],
    cursor_after=(i32(CURX), i32(CURY)))

dp = pulse("DOWN", hold=2, settle=30)
dp["dx"] = i32(CURX) - i32(CURX) if False else i32(CURX) - rp["sym_after"]["cursorX"]
dp["dy"] = i32(CURY) - rp["sym_after"]["cursorY"]
R["pulses"]["DOWN"] = dp
log("pulse_DOWN", dx=dp["dx"], dy=dp["dy"],
    press=[s["pad_buff0"] for s in dp["series"][:2]],
    cursor_after=(i32(CURX), i32(CURY)))

# ---- phase 5: CROSS reveal (closed-loop anchor) -------------------------------
cx1, cy1 = i32(CURX), i32(CURY)
board_before = bytes(core.ram[BOARD:BOARD + 4608])
rev_before = i32(REVT)
snap("pre_reveal")
cr = pulse("X", hold=2, settle=60, snapset=(10, 25, 45, 60))
board_after = bytes(core.ram[BOARD:BOARD + 4608])
rev_after = i32(REVT)
flips = [i for i in range(4608)
         if board_before[i] == 0 and board_after[i] == 1]
reveal_offs = sorted(set((i - 1) for i in flips if i % 12 == 1))
R["reveal"] = {
    "cursor_at": [cx1, cy1], "revealed_total_before": rev_before,
    "revealed_total_after": rev_after,
    "board_bytes_changed": int(sum(1 for a, b in zip(board_before,
                                                     board_after)
                                   if a != b)),
    "revealed_flag_flips_n": len(flips),
    "revealed_cell_offsets": [hex(o) for o in reveal_offs[:40]],
}
# which layout puts a revealed cell at the cursor?
for name, fn in (("A_x192_y12", lambda x, y: x * 192 + y * 12),
                 ("B_y192_x12", lambda x, y: y * 192 + x * 12)):
    o = fn(cx1, cy1)
    R["reveal"][f"cursor_cell_{name}"] = {
        "off": hex(o), "revealed_after": board_after[o + 1],
        "revealed_before": board_before[o + 1],
        "mine": board_after[o], "neighbors": int.from_bytes(
            board_after[o + 4:o + 8], "little", signed=True)}
R["pulses"]["CROSS"] = cr
log("pulse_CROSS", **{k: v for k, v in R["reveal"].items()
                      if k != "revealed_cell_offsets"},
    press=[s["pad_buff0"] for s in cr["series"][:2]])
snap("post_reveal")
R["board_counts_after"] = {k: v["revealed_n"] for k, v in
                           board_counts().items()}
R["board_counts_after"]["revealed_total_sym"] = i32(REVT)
log("board_counts", **R["board_counts_after"])

# ---- verdicts ----------------------------------------------------------------
started = R["game_start"]["board_ready_f"] is not None
cursor_ok = (rp["dx"] != 0) or (dp["dy"] != 0)
reveal_ok = (rev_after > rev_before) and len(flips) > 0
vis_ok = any(p["vis_diff"] > 2 for p in (st, cr)) or \
    R["reveal"]["board_bytes_changed"] > 0
R["verdicts"] = {
    "BOOTED_TITLE": bool(title_stable and pad_live),
    "INPUT_RESPONSIVE": bool(started and cursor_ok),
    "RUNNING": bool(started and reveal_ok and vis_ok),
}
R["verdict"] = ("RUNNING" if R["verdicts"]["RUNNING"] else
                "INPUT_RESPONSIVE" if R["verdicts"]["INPUT_RESPONSIVE"]
                else "BOOTED_TITLE" if R["verdicts"]["BOOTED_TITLE"]
                else "FAILED")
R["final_sym"] = sym()
R["frames_total"] = core.frames_run
R["finished"] = time.strftime("%FT%TZ", time.gmtime())
dump()
print("[b2] DONE frames=", core.frames_run, "wall=", round(time.time() - T0, 1),
      "verdict=", R["verdict"], json.dumps(R["verdicts"]), flush=True)
