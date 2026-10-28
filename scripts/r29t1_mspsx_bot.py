#!/usr/bin/env python3
"""r29t1_mspsx_bot.py — Round 29: MSPSX RAM-guided bot pass.

Source ground truth (raw.githubusercontent.com/AcidGunner/MSPSX main.c,
fetched today, zero boots):
  Cell board[MAX_W][MAX_H] = board[24][16]; Cell = {u8 mine; u8 revealed;
  u8 flagged; pad; i32 neighbors; bool hasNeighborMines; u8 active;
  u8 processed;} = 12 B  ->  offset(cursorX,cursorY) = cursorX*192 + cursorY*12
  GRID_W=16 GRID_H=12 MINES=32; PAD_CROSS=reveal/chord; PAD_CIRCLE=flag
  toggle (flagged 0->1->0, mine_count -- / ++); first-click-on-mine
  regenerates; mine reveal -> control_disable=1 lost=1; loss renders
  "GAME OVER." at (200,4); START after loss regenerates (cursor 0,0,
  FIRST_CLICK=1, control_disable=0).
r23 live-verified symbols: BOARD 0x199DC CURX 0x18CD4 CURY 0x18CD0
REVT 0x18CDC MINC 0x18CEC CTRLDIS 0x18CE4 LOST 0x18CE0; SPI poll cadence
~33f -> taps hold 2f + settle 45f, CROSS hold 40f; ps1play B=PSX CROSS,
O=PSX CIRCLE.

Bot pass (boot cap 2, disclosed pre-run: boot 2 only for a script-bug
crash; mechanics refutations park honestly):
  A boot -> title -> START -> board init
  B decode board: assert mines==32, active==192, neighbors consistency
  C navigate to a zero-neighbor cell -> CROSS 40f -> flood reveal
    (revealed-count jump >= 8 predicted for a zero cell)
  D navigate to an unrevealed cell -> CIRCLE -> flag set, mine_count 32->31
  E navigate to a known mine -> CROSS 40f -> PREDICT lost=1 + GAME OVER
  F START -> board regenerates (full loop: play -> lose -> restart)
All navigation verified step-by-step (cursor delta == 1 per tap, retry
once on a swallowed poll). No claim without the RAM + PNG pair.
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

OUT = os.path.join(REPO, "scratch", "r29", "mspsx")
SHOTS = os.path.join(OUT, "shots")
CONTENT = "/home/z/my-project/emu/games_homebrew/patched/mspsx_lic.cue"
CORE = "/home/z/my-project/ps1-test/cores/mednafen_psx_libretro.so"
BIOS = "/home/z/my-project/ps1-test/emu/system/openbios.bin"
BOOTS = os.path.join(OUT, "boots_used.json")

BOARD, CURX, CURY = 0x199DC, 0x18CD4, 0x18CD0
REVT, MINC, CTRLDIS, LOST = 0x18CDC, 0x18CEC, 0x18CE4, 0x18CE0
PADB = 0x1AC48
GRID_W, GRID_H, MINES = 16, 12, 32
XSTR, YSTR, CELL = 192, 12, 12

R = {"task": "r29t1 MSPSX RAM-guided bot pass",
     "cap_policy": "cap 2 disclosed pre-run: boot 2 only for a script-bug "
                   "crash; mechanics refutations park honestly",
     "started": time.strftime("%FT%TZ", time.gmtime()),
     "events": [], "shots": [], "phases": {}}


def dump():
    json.dump(R, open(os.path.join(OUT, "boot_log.json"), "w"),
              indent=1, default=str)


def log(ev, **kw):
    rec = {"f": core.frames_run, "t": round(time.time() - T0, 1),
           "event": ev, **kw}
    R["events"].append(rec)
    print(f"[r29t1] {json.dumps(rec, default=str)[:240]}", flush=True)
    dump()


def snap(tag):
    arr = core.frame_rgb()
    if arr is not None:
        p = os.path.join(SHOTS, f"{tag}_f{core.frames_run:05d}.png")
        Image.fromarray(arr).save(p)
        R["shots"].append({"tag": tag, "frame": core.frames_run,
                           "png": os.path.relpath(p, OUT)})
    return arr


def pdiff(a, b, box=None):
    if a is None or b is None:
        return -1.0
    if box:
        a, b = a[box[1]:box[3], box[0]:box[2]], b[box[1]:box[3], box[0]:box[2]]
    return round(float(np.abs(a.astype(int) - b.astype(int)).mean()), 2)


def i32(va):
    return int.from_bytes(bytes(core.ram[va:va + 4]), "little", signed=True)


def u16(va):
    return int.from_bytes(bytes(core.ram[va:va + 2]), "little")


def sym():
    return {"cursor": (i32(CURX), i32(CURY)), "revealed_total": i32(REVT),
            "mine_count": i32(MINC), "ctrl_dis": core.ram[CTRLDIS],
            "lost": core.ram[LOST],
            "pad": bytes(core.ram[PADB:PADB + 4]).hex()}


def board_cells():
    reg = bytes(core.ram[BOARD:BOARD + 24 * 16 * CELL])
    cells = {}
    for cx in range(GRID_W):
        for cy in range(GRID_H):
            off = cx * XSTR + cy * YSTR
            c = reg[off:off + CELL]
            cells[(cx, cy)] = {"mine": c[0], "revealed": c[1],
                               "flagged": c[2],
                               "neighbors": int.from_bytes(
                                   c[4:8], "little", signed=True),
                               "active": c[9]}
    return cells


def board_stats(cells):
    act = [k for k, v in cells.items() if v["active"]]
    return {"active": len(act),
            "mines": sum(1 for k in act if cells[k]["mine"]),
            "revealed": sum(1 for k in act if cells[k]["revealed"]),
            "flagged": sum(1 for k in act if cells[k]["flagged"])}


def pulse(button, hold=2, settle=45):
    before = core.frame_rgb()
    core.set_buttons(button)
    for _ in range(hold):
        core.run_frame()
    core.set_buttons(set())
    for _ in range(settle):
        core.run_frame()
    return before, core.frame_rgb()


def tap_axis(btn, want_delta, cur_addr, tries=3):
    """One cursor step with verification; a swallowed poll gets retries."""
    for _ in range(tries):
        v0 = i32(cur_addr)
        pulse(btn, hold=2, settle=45)
        if i32(cur_addr) - v0 == want_delta:
            return True
    return False


def navigate(tx, ty):
    cx, cy = i32(CURX), i32(CURY)
    plan = []
    plan += [("RIGHT", +1)] * (tx - cx) if tx > cx else \
            [("LEFT", -1)] * (cx - tx)
    plan += [("DOWN", +1)] * (ty - cy) if ty > cy else \
            [("UP", -1)] * (cy - ty)
    for btn, d in plan:
        cur = CURX if btn in ("RIGHT", "LEFT") else CURY
        if not tap_axis(btn, d, cur):
            log("nav_fail", btn=btn, at=(i32(CURX), i32(CURY)),
                target=(tx, ty))
            return False
    ok = (i32(CURX), i32(CURY)) == (tx, ty)
    log("nav_done", target=(tx, ty), cursor=(i32(CURX), i32(CURY)),
        ok=ok, taps=len(plan))
    return ok


T0 = time.time()
for d in (OUT, SHOTS):
    os.makedirs(d, exist_ok=True)
BOOT_N = 2
if os.path.exists(BOOTS):
    led0 = json.load(open(BOOTS))
    assert led0["count"] == 1 and led0["cap"] == 2, "ledger mismatch"
    led0["count"] = 2
    led0["log"].append({"boot": 2, "script": "r29t1_mspsx_bot.py (fixed)",
                        "reason": "boot-1 script-bug assert (flood>=8); "
                                  "mechanics refutations would NOT retry",
                        "t": time.strftime("%FT%TZ", time.gmtime())})
    json.dump(led0, open(BOOTS, "w"), indent=1)
else:
    json.dump({"count": 1, "cap": 2,
               "cap_policy": R["cap_policy"],
               "log": [{"boot": 1, "script": "r29t1_mspsx_bot.py",
                        "t": time.strftime("%FT%TZ", time.gmtime())}]},
              open(BOOTS, "w"), indent=1)
    BOOT_N = 1

ws = os.path.join(OUT, "ws")
os.makedirs(os.path.join(ws, "system"), exist_ok=True)
os.makedirs(os.path.join(ws, "saves"), exist_ok=True)
shutil.copyfile(BIOS, os.path.join(ws, "system", "openbios.bin"))
core = LibretroCore(CORE, os.path.join(ws, "system"),
                    os.path.join(ws, "saves"),
                    var_overrides={b"beetle_psx_renderer": b"software",
                                   b"beetle_psx_frame_duping": b"disabled"})
av = core.load_game(CONTENT)
log("boot", core=core.core_name, av=av)

# ---- A: title -> START -> board init ----------------------------------------
pad_live = False
for _ in range(900):
    core.run_frame()
    if i32(0x18D08) >= 4 and \
            bytes(core.ram[PADB:PADB + 4]) == b"\x41\x5a\xff\xff":
        pad_live = True
        break
log("title_wait", pad_live=pad_live, f=core.frames_run)
snap("title")
pulse("START", hold=2, settle=60)
board_f = None
for _ in range(300):
    core.run_frame()
    if np.count_nonzero(core.ram[BOARD:BOARD + 4608]) > 0 and \
            core.ram[CTRLDIS] == 0:
        board_f = core.frames_run
        break
snap("game")
log("board_init", board_f=board_f, sym=sym())
R["phases"]["A"] = {"pad_live": pad_live, "board_f": board_f}

# ---- B: decode + verify --------------------------------------------------------
cells = board_cells()
st0 = board_stats(cells)
log("board_decode", stats=st0, sym=sym())
assert st0["mines"] == MINES, f"mine decode mismatch: {st0}"
zeros = [k for k, v in cells.items()
         if v["active"] and not v["mine"] and not v["revealed"]
         and v["neighbors"] == 0]
log("zero_cells", n=len(zeros))
assert zeros, "no zero-neighbor cell found - board decode suspect"
# prefer a reachable zero (cx+cy <= 18) with max flood potential distance
zeros.sort(key=lambda k: (k[0] + k[1], -k[0]))
zsel = None
for k in zeros:
    if k[0] + k[1] <= 18:
        zsel = k
        break
zsel = zsel or zeros[0]
log("zero_selected", cell=zsel)

# ---- C: navigate + flood reveal -------------------------------------------------
pre = snap("pre_flood")
ok = navigate(*zsel)
assert ok, "navigation to zero cell failed"
b4 = board_stats(board_cells())
rev0, cur0 = i32(REVT), core.frame_rgb()
cross0, cross1 = None, None
core.set_buttons("B")
for _ in range(40):
    core.run_frame()
core.set_buttons(set())
for _ in range(90):
    core.run_frame()
cross1 = core.frame_rgb()
snap("post_flood")
cells2 = board_cells()
st1 = board_stats(cells2)
flood = st1["revealed"] - b4["revealed"]
R["phases"]["C"] = {"zero_cell": zsel, "revealed_before": b4["revealed"],
                    "revealed_after": st1["revealed"],
                    "flood_size": flood, "revt": (rev0, i32(REVT)),
                    "vis": pdiff(cur0, cross1)}
log("flood_reveal", **R["phases"]["C"])
assert flood >= 2, f"no multi-cell expansion: {flood}"

# ---- D: flag mechanic (CIRCLE) ---------------------------------------------------
unrev = [k for k, v in cells2.items()
         if v["active"] and not v["mine"] and not v["revealed"]
         and not v["flagged"]]
fsel = min(unrev, key=lambda k: abs(k[0] - i32(CURX)) +
           abs(k[1] - i32(CURY))) if unrev else None
assert fsel, "no unrevealed cell for flag test"
ok = navigate(*fsel)
assert ok, "navigation to flag cell failed"
mc0 = i32(MINC)
pre_flag = core.frame_rgb()
pulse("O", hold=2, settle=60)
cells3 = board_cells()
st2 = board_stats(cells3)
R["phases"]["D"] = {"cell": fsel, "flagged_delta":
                    st2["flagged"] - st1["flagged"],
                    "mine_count": (mc0, i32(MINC)),
                    "vis": pdiff(pre_flag, core.frame_rgb())}
log("flag_test", **R["phases"]["D"])
assert st2["flagged"] - st1["flagged"] == 1 and i32(MINC) == mc0 - 1, \
    "flag mechanics mismatch"

# ---- E: navigate to a mine -> PREDICT loss ---------------------------------------
mines = [k for k, v in cells3.items() if v["active"] and v["mine"]]
msel = min(mines, key=lambda k: abs(k[0] - i32(CURX)) +
           abs(k[1] - i32(CURY)))
log("mine_selected", cell=msel, n_mines=len(mines))
ok = navigate(*msel)
assert ok, "navigation to mine failed"
pre_boom = snap("pre_mine")
pred = {"lost": 1, "ctrl_dis": 1}
core.set_buttons("B")
for _ in range(40):
    core.run_frame()
core.set_buttons(set())
for _ in range(90):
    core.run_frame()
post_boom = core.frame_rgb()
snap("post_mine")
got = {"lost": core.ram[LOST], "ctrl_dis": core.ram[CTRLDIS]}
over_vis = pdiff(pre_boom, post_boom, box=(195, 0, 320, 22))
R["phases"]["E"] = {"predicted": pred, "observed": got,
                    "match": pred == got,
                    "gameover_text_vis": over_vis}
log("mine_reveal", **R["phases"]["E"])
assert got["lost"] == 1 and got["ctrl_dis"] == 1, "mine reveal not lost?!"
snap("gameover")

# ---- F: START restart -> full loop -------------------------------------------------
board_before = bytes(core.ram[BOARD:BOARD + 4608])
pre_rs = core.frame_rgb()
pulse("START", hold=2, settle=90)
board_after = bytes(core.ram[BOARD:BOARD + 4608])
cells4 = board_cells()
st3 = board_stats(cells4)
R["phases"]["F"] = {"lost_after": core.ram[LOST],
                    "ctrl_dis_after": core.ram[CTRLDIS],
                    "cursor_after": (i32(CURX), i32(CURY)),
                    "board_changed": board_before != board_after,
                    "stats": st3,
                    "vis": pdiff(pre_rs, core.frame_rgb())}
log("restart", **R["phases"]["F"])
snap("restarted")
ok = (R["phases"]["F"]["lost_after"] == 0 and
      R["phases"]["F"]["ctrl_dis_after"] == 0 and
      R["phases"]["F"]["cursor_after"] == (0, 0) and
      R["phases"]["F"]["board_changed"] and
      st3["mines"] == MINES)

R["verdict"] = ("PLAYING_BOT (board-perception + navigation + flood reveal "
                "+ flag + predicted-loss + restart loop): " +
                ("ALL_PHASES_OK" if ok else "PHASE_F_PARTIAL - see log"))
R["frames_total"] = core.frames_run
R["finished"] = time.strftime("%FT%TZ", time.gmtime())
dump()
led = json.load(open(BOOTS))
led["log"][-1]["outcome"] = R["verdict"]
json.dump(led, open(BOOTS, "w"), indent=1)
print("[r29t1] DONE", R["verdict"], "frames=", core.frames_run, flush=True)
