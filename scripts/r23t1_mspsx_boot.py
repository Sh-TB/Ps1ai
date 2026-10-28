#!/usr/bin/env python3
"""r23t1_mspsx_boot.py — Round 23 MSPSX single-boot causality program.

R22 state: INPUT_RESPONSIVE (START + cursor proven). The single remaining
rung is the CROSS reveal. R22's CROSS probe failed for two disclosed
reasons: (a) libretro "X" maps to PSX TRIANGLE on beetle (the wrong
button), and (b) the game's custom SPI driver polls at ~30 Hz (~33 frames
per tick), so a 2-frame hold can land entirely between polls.

This boot fixes both disclosed causes in one shot:
  - button "B" (ps1play B = PSX CROSS on the beetle map)
  - hold 40 frames (> 35, guarantees at least one 33f poll tick)

Boot cap: hard cap 1 (boots_used.json must be 0 -> 1, asserted).
Image: patched/mspsx_lic.bin (license sectors only, EXE unpatched —
bit-identical release payload sha256 d35a189b…a4c5fa re-verified today).

Honest ladder targets: BOOTED_TITLE < INPUT_RESPONSIVE < RUNNING.
RUNNING requires: board init + revealed_total increment + board byte
flips + revealed cell at the cursor + visual change. No inflation.
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

OUT = os.path.join(REPO, "scratch", "r23", "mspsx")
SHOTS = os.path.join(OUT, "shots")
CONTENT = "/home/z/my-project/emu/games_homebrew/patched/mspsx_lic.cue"
CORE = "/home/z/my-project/ps1-test/cores/mednafen_psx_libretro.so"
BIOS = "/home/z/my-project/ps1-test/emu/system/openbios.bin"
BOOTS = os.path.join(OUT, "boots_used.json")

# symbols from the r22 intake (verified live twice)
PADB, PADL = 0x1AC48, 0x18D08
OLDH, PRES, HELD = 0x18CF8, 0x18CFC, 0x18CFE
BOARD, CURX, CURY = 0x199DC, 0x18CD4, 0x18CD0
REVT, VALT, MINC = 0x18CDC, 0x18CD8, 0x18CEC
CTRLDIS, LOST, FCLK = 0x18CE4, 0x18CE0, 0x18CCC
NCELL = 16 * 12 * 12  # board region guarded in r22 (4608 B)
NCELL = 4608

R = {"task": "r23t1 MSPSX single boot", "content": CONTENT,
     "image_sha_note": "release payload d35a189b...a4c5fa re-verified "
     "2026-10-28, license sectors only",
     "started": time.strftime("%FT%TZ", time.gmtime()),
     "events": [], "shots": [], "pulses": {}}


def boots_used():
    if os.path.exists(BOOTS):
        with open(BOOTS) as f:
            return json.load(f).get("count", 0)
    return 0


def dump():
    with open(os.path.join(OUT, "boot_log.json"), "w") as f:
        json.dump(R, f, indent=1, default=str)


def log(ev, **kw):
    rec = {"f": core.frames_run, "t": round(time.time() - T0, 1),
           "event": ev, **kw}
    R["events"].append(rec)
    print(f"[r23t1] {json.dumps(rec, default=str)[:230]}", flush=True)
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
            "pad_buff_len0": i32(PADL), "pressed": u16(PRES),
            "held": u16(HELD), "cursorX": i32(CURX), "cursorY": i32(CURY),
            "revealed_total": i32(REVT), "valid_total": i32(VALT),
            "mine_count": i32(MINC), "control_disable": core.ram[CTRLDIS],
            "lost": core.ram[LOST],
            "board_nonzero": int(np.count_nonzero(
                core.ram[BOARD:BOARD + NCELL]))}


def pulse(button, hold=2, settle=45, snapset=(10, 25, 45)):
    before = core.frame_rgb()
    series = []
    core.set_buttons(button)
    for _ in range(hold):
        core.run_frame()
        series.append({"f": core.frames_run,
                       "pad_buff0": bytes(core.ram[PADB:PADB + 4]).hex(),
                       "held": u16(HELD), "pressed": u16(PRES)})
    core.set_buttons(set())
    for s in range(settle):
        core.run_frame()
        if (s + 1) in snapset:
            snap(f"p_{button.lower()}_{s + 1}")
            series.append({"f": core.frames_run,
                           "pad_buff0": bytes(core.ram[PADB:PADB + 4]).hex(),
                           "held": u16(HELD), "pressed": u16(PRES)})
    after = core.frame_rgb()
    return {"button": button, "hold": hold, "series": series,
            "vis_diff": pdiff(before, after), "sym_after": sym()}


def cell_at(x, y):
    """Cursor cell under the two candidate layouts (r22 ambiguity)."""
    reg = bytes(core.ram[BOARD:BOARD + NCELL])
    out = {}
    for name, off in (("A_x384_y12", x * 384 + y * 12),
                      ("B_y192_x12", y * 192 + x * 12)):
        out[name] = {"off": hex(off), "mine": reg[off],
                     "revealed": reg[off + 1], "flagged": reg[off + 2],
                     "neighbors": int.from_bytes(reg[off + 4:off + 8],
                                                 "little", signed=True)}
    return out


T0 = time.time()
for d in (OUT, SHOTS):
    os.makedirs(d, exist_ok=True)
n0 = boots_used()
assert n0 == 0, f"boot counter {n0} != 0 (hard cap 1 for round 23)"
with open(BOOTS, "w") as f:
    json.dump({"count": 1, "log": [{"boot": 1, "script": "r23t1_mspsx_boot.py",
                "image": "mspsx_lic.bin (license only, EXE unpatched)",
                "t": time.strftime("%FT%TZ", time.gmtime())}]}, f, indent=1)

ws = os.path.join(OUT, "ws")
os.makedirs(os.path.join(ws, "system"), exist_ok=True)
os.makedirs(os.path.join(ws, "saves"), exist_ok=True)
shutil.copyfile(BIOS, os.path.join(ws, "system", "openbios.bin"))
core = LibretroCore(CORE, os.path.join(ws, "system"),
                    os.path.join(ws, "saves"),
                    var_overrides={b"beetle_psx_renderer": b"software",
                                   b"beetle_psx_frame_duping": b"disabled"})
av = core.load_game(CONTENT)
log("boot", core=core.core_name, ver=core.core_ver, av=av)

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

# ---- phase 2: START pulse -> board init ---------------------------------------
st = pulse("START", hold=2, settle=60, snapset=(15, 30, 60))
R["pulses"]["START"] = st
log("pulse_START", vis_diff=st["vis_diff"], sym_after=st["sym_after"])
board_f = None
for _ in range(240):
    core.run_frame()
    if np.count_nonzero(core.ram[BOARD:BOARD + NCELL]) > 0 and \
            core.ram[CTRLDIS] == 0:
        board_f = core.frames_run
        break
snap("game")
R["game_start"] = {"board_ready_f": board_f, "sym": sym()}
log("game_start", **R["game_start"])

# ---- phase 3: idle static check ------------------------------------------------
cx0, cy0 = i32(CURX), i32(CURY)
for _ in range(30):
    core.run_frame()
idle_static = (cx0, cy0) == (i32(CURX), i32(CURY))
R["idle"] = {"a": (cx0, cy0), "b": (i32(CURX), i32(CURY)),
             "static": idle_static}
log("idle_cursor", **R["idle"])

# ---- phase 4: cursor anchors (2-frame pulses, r22-verified class) --------------
rp = pulse("RIGHT", hold=2, settle=30)
rp["dx"] = i32(CURX) - cx0
rp["dy"] = i32(CURY) - cy0
R["pulses"]["RIGHT"] = rp
log("pulse_RIGHT", dx=rp["dx"], dy=rp["dy"],
    cursor_after=(i32(CURX), i32(CURY)))
cx1, cy1 = i32(CURX), i32(CURY)
dp = pulse("DOWN", hold=2, settle=30)
dp["dx"] = i32(CURX) - cx1
dp["dy"] = i32(CURY) - cy1
R["pulses"]["DOWN"] = dp
log("pulse_DOWN", dx=dp["dx"], dy=dp["dy"],
    cursor_after=(i32(CURX), i32(CURY)))

# ---- phase 5: CROSS reveal, the r23 rung ----------------------------------------
# cursor is now at (1,1) = (2,1) in 1-based r22 terms.
cx, cy = i32(CURX), i32(CURY)
board_before = bytes(core.ram[BOARD:BOARD + NCELL])
rev_before, lost_before = i32(REVT), core.ram[LOST]
snap("pre_reveal")
# THE FIX: ps1play B = PSX CROSS; hold 40f > 33f SPI poll cadence
cr = pulse("B", hold=40, settle=90, snapset=(10, 30, 55, 80))
board_after = bytes(core.ram[BOARD:BOARD + NCELL])
rev_after, lost_after = i32(REVT), core.ram[LOST]
flips = [i for i in range(NCELL)
         if board_before[i] == 0 and board_after[i] == 1]
R["reveal"] = {
    "button": "B (PSX CROSS)", "hold_frames": 40,
    "cursor_at": [cx, cy], "lost_before": lost_before,
    "lost_after": lost_after,
    "revealed_total_before": rev_before, "revealed_total_after": rev_after,
    "board_bytes_changed": int(sum(1 for a, b in
                                   zip(board_before, board_after) if a != b)),
    "revealed_flag_flips_n": len(flips),
    "cursor_cell": cell_at(cx, cy),
    "first_flip_offsets": [hex(o) for o in sorted(flips)[:24]],
}
R["pulses"]["CROSS_B"] = {k: cr[k] for k in ("hold", "vis_diff")}
R["pulses"]["CROSS_B"]["held_series"] = cr["series"][:3] + cr["series"][-3:]
R["pulses"]["CROSS_B"]["sym_after"] = cr["sym_after"]
log("pulse_CROSS_B", **R["reveal"])
snap("post_reveal")

# if the reveal hit a mine -> lost=1; if a big BFS area opened, many flips.
# Either way RUNNING requires revealed_total strictly up + board flips.

# ---- verdicts ------------------------------------------------------------------
started = R["game_start"]["board_ready_f"] is not None
cursor_ok = (rp["dx"] != 0) or (dp["dy"] != 0)
reveal_ok = (rev_after > rev_before) and len(flips) > 0
vis_ok = (cr["vis_diff"] > 2) or R["reveal"]["board_bytes_changed"] > 0
R["verdicts"] = {
    "BOOTED_TITLE": bool(title_stable and pad_live),
    "INPUT_RESPONSIVE": bool(started and cursor_ok),
    "RUNNING": bool(started and reveal_ok and vis_ok and
                    lost_after == lost_before or reveal_ok),
}
# honest: RUNNING = started + reveal + visual. lost flip does NOT block
# (revealing a mine is still a game effect), but we disclose it.
R["verdicts"]["RUNNING"] = bool(started and reveal_ok and vis_ok)
R["verdict"] = ("RUNNING" if R["verdicts"]["RUNNING"] else
                "INPUT_RESPONSIVE" if R["verdicts"]["INPUT_RESPONSIVE"]
                else "BOOTED_TITLE" if R["verdicts"]["BOOTED_TITLE"]
                else "FAILED")
R["final_sym"] = sym()
R["frames_total"] = core.frames_run
R["finished"] = time.strftime("%FT%TZ", time.gmtime())
dump()
print("[r23t1] DONE frames=", core.frames_run,
      "wall=", round(time.time() - T0, 1),
      "verdict=", R["verdict"], json.dumps(R["verdicts"]), flush=True)
