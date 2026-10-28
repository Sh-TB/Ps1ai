#!/usr/bin/env python3
"""r35c_lib.py — shared helpers for R35-C mspSX full-board win train.

Symbols/protocol ground truth from r29t1 (live-verified round 29):
  BOARD 0x199DC CURX 0x18CD4 CURY 0x18CD0 REVT 0x18CDC MINC 0x18CEC
  CTRLDIS 0x18CE4 LOST 0x18CE0 PADB 0x1AC48
  cell struct 12B {u8 mine; u8 revealed; u8 flagged; pad; i32 neighbors;
  bool hasNeighborMines; u8 active; u8 processed}
  offset = x*192 + y*12 ; GRID 16x12 ; MINES 32 ; active 160 safe + 32 mines
  taps: hold 2f settle >=45f (SPI poll ~33f, retries for swallowed polls)
  CROSS (ps1play "B") = reveal/chord ; CIRCLE ("O") = flag toggle
"""
import json
import os
import time

import numpy as np
from PIL import Image

REPO = "/home/z/my-project/ps1ai"
OUT = os.path.join(REPO, "scratch", "r35c")
SHOTS = os.path.join(OUT, "shots")
GIFD = os.path.join(OUT, "gif_frames")
WS = os.path.join(OUT, "ws")
CONTENT = "/home/z/my-project/emu/games_homebrew/patched/mspsx_lic.cue"
CORE = "/home/z/my-project/ps1-test/cores/mednafen_psx_libretro.so"
BIOS = "/home/z/my-project/ps1-test/emu/system/openbios.bin"
LEDDER = os.path.join(OUT, "boots_used.json")
JSONL = os.path.join(OUT, "r35c_events.jsonl")

BOARD, CURX, CURY = 0x199DC, 0x18CD4, 0x18CD0
REVT, MINC, CTRLDIS, LOST = 0x18CDC, 0x18CEC, 0x18CE4, 0x18CE0
PADB = 0x1AC48
GRID_W, GRID_H, MINES = 16, 12, 32
XSTR, YSTR, CELL = 192, 12, 12
SAFE_TOTAL = GRID_W * GRID_H - MINES  # 160


def jlog(event, **kw):
    rec = {"t": time.strftime("%FT%TZ", time.gmtime()),
           "wall": round(time.time() - T0, 1), "event": event, **kw}
    if "core" in globals() and core is not None:
        rec["f"] = core.frames_run
    with open(JSONL, "a") as fh:
        fh.write(json.dumps(rec, default=str) + "\n")
    print(f"[r35c] {json.dumps(rec, default=str)[:260]}", flush=True)


def consume_boot(script, reason):
    led = json.load(open(LEDDER))
    led["count"] += 1
    led["log"].append({"boot": led["count"], "script": script,
                       "reason": reason,
                       "t": time.strftime("%FT%TZ", time.gmtime())})
    json.dump(led, open(LEDDER, "w"), indent=1)
    return led["count"]


def amend_ledger(note):
    led = json.load(open(LEDDER))
    led["amendments"].append({"t": time.strftime("%FT%TZ", time.gmtime()),
                              "note": note})
    json.dump(led, open(LEDDER, "w"), indent=1)
    print(f"[r35c] AMENDMENT: {note}", flush=True)


T0 = time.time()
core = None  # set by caller after load_game


# ---- RAM access -------------------------------------------------------------
def i32(va):
    return int.from_bytes(bytes(core.ram[va:va + 4]), "little", signed=True)


def sym():
    return {"cursor": [i32(CURX), i32(CURY)], "revealed_total": i32(REVT),
            "mine_count": i32(MINC), "ctrl_dis": int(core.ram[CTRLDIS]),
            "lost": int(core.ram[LOST]),
            "pad": bytes(core.ram[PADB:PADB + 4]).hex()}


def decode():
    reg = bytes(core.ram[BOARD:BOARD + 24 * 16 * CELL])
    cells = {}
    for x in range(GRID_W):
        for y in range(GRID_H):
            off = x * XSTR + y * YSTR
            c = reg[off:off + CELL]
            cells[(x, y)] = {"mine": c[0], "revealed": c[1], "flagged": c[2],
                             "neighbors": int.from_bytes(c[4:8], "little",
                                                         signed=True),
                             "active": c[9]}
    return cells


def stats(cells):
    act = [k for k, v in cells.items() if v["active"]]
    return {"active": len(act),
            "mines": sum(1 for k in act if cells[k]["mine"]),
            "revealed": sum(1 for k in act if cells[k]["revealed"]),
            "flagged": sum(1 for k in act if cells[k]["flagged"])}


NBR8 = [(-1, -1), (0, -1), (1, -1), (-1, 0), (1, 0), (-1, 1), (0, 1), (1, 1)]


def adj_mines(cells, x, y):
    """Our own adjacent-mine count from mine bytes (independent of the
    game's stored neighbors field)."""
    n = 0
    for dx, dy in NBR8:
        nx, ny = x + dx, y + dy
        if 0 <= nx < GRID_W and 0 <= ny < GRID_H and cells[(nx, ny)]["mine"]:
            n += 1
    return n


def check_neighbors(cells):
    """Cross-validate game-stored neighbors vs our own count."""
    bad = []
    nonzero = 0
    for (x, y), v in cells.items():
        if not v["active"] or v["mine"]:
            continue
        if v["neighbors"] != 0:
            nonzero += 1
        mine_n = adj_mines(cells, x, y)
        if v["neighbors"] != mine_n:
            bad.append({"cell": [x, y], "stored": v["neighbors"],
                        "computed": mine_n})
    return {"nonzero_stored": nonzero, "mismatches": bad[:12],
            "n_mismatch": len(bad)}


def flood_sim(cells, tx, ty):
    """Classic minesweeper flood from (tx,ty); returns set of newly
    revealed cells. Uses OUR adjacency; assumes flood ignores flags."""
    out = set()
    if cells[(tx, ty)]["revealed"] or cells[(tx, ty)]["mine"]:
        return out
    stack = [(tx, ty)]
    while stack:
        x, y = stack.pop()
        c = cells[(x, y)]
        if c["revealed"] or (x, y) in out or c["mine"]:
            continue
        out.add((x, y))
        if adj_mines(cells, x, y) == 0:
            for dx, dy in NBR8:
                nx, ny = x + dx, y + dy
                if 0 <= nx < GRID_W and 0 <= ny < GRID_H:
                    cc = cells[(nx, ny)]
                    if not cc["revealed"] and not cc["mine"] and \
                            (nx, ny) not in out:
                        stack.append((nx, ny))
    return out


# ---- input / navigation -----------------------------------------------------
def pulse(core, button, hold=2, settle=45):
    core.set_buttons(button)
    for _ in range(hold):
        core.run_frame()
    core.set_buttons(set())
    for _ in range(settle):
        core.run_frame()


def tap_axis(core, btn, want_delta, cur_addr, tries=3):
    for _ in range(tries):
        v0 = i32(cur_addr)
        pulse(core, btn, hold=2, settle=45)
        if i32(cur_addr) - v0 == want_delta:
            return True
    return False


def navigate(core, tx, ty, jlog=jlog):
    cx, cy = i32(CURX), i32(CURY)
    plan = [("RIGHT", +1, CURX)] * (tx - cx) if tx > cx else \
           [("LEFT", -1, CURX)] * (cx - tx)
    plan += [("DOWN", +1, CURY)] * (ty - cy) if ty > cy else \
            [("UP", -1, CURY)] * (cy - ty)
    for btn, d, addr in plan:
        if not tap_axis(core, btn, d, addr):
            jlog("nav_fail", btn=btn, at=[i32(CURX), i32(CURY)],
                 target=[tx, ty])
            return False
    ok = (i32(CURX), i32(CURY)) == (tx, ty)
    return ok


def snap(core, tag, R=None):
    arr = core.frame_rgb()
    if arr is not None:
        p = os.path.join(SHOTS, f"{tag}_f{core.frames_run:06d}.png")
        Image.fromarray(arr).save(p)
        if R is not None:
            R["shots"].append({"tag": tag, "frame": core.frames_run,
                               "png": p})
    return arr


class Sampler:
    """Samples frame_rgb every `stride` frames into GIFD as PNGs."""

    def __init__(self, core, stride=90, maxn=600):
        self.core = core
        self.stride = stride
        self.maxn = maxn
        self.n = 0
        os.makedirs(GIFD, exist_ok=True)

    def run(self, frames):
        for _ in range(frames):
            self.core.run_frame()
            if self.core.frames_run % self.stride == 0:
                self.sample()

    def sample(self):
        arr = self.core.frame_rgb()
        if arr is None:
            return
        self.n += 1
        p = os.path.join(GIFD, f"{self.core.frames_run:07d}.png")
        Image.fromarray(arr).save(p)
        if self.n > self.maxn:  # decimate oldest half to bound disk/memory
            fs = sorted(os.listdir(GIFD))
            for f in fs[::2]:
                os.remove(os.path.join(GIFD, f))
            self.n = len(os.listdir(GIFD))


def checkpoint(core, name):
    blob = core.serialize()
    p = os.path.join(WS, name)
    with open(p, "wb") as fh:
        fh.write(blob)
    jlog("checkpoint", file=name, bytes=len(blob), f=core.frames_run)
    return p


def latest_checkpoint(prefix):
    cands = sorted(f for f in os.listdir(WS) if f.startswith(prefix)
                   and f.endswith(".bin"))
    return os.path.join(WS, cands[-1]) if cands else None
