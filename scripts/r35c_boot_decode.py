#!/usr/bin/env python3
"""r35c_boot_decode.py — R35-C phase 1: boot, title->START, full board
decode + validation, savestate checkpoint.

Consumes boot 1 of 3 (ledger amended pre-run inside consume_boot()).
Everything after decode is offline; later phases resume from the
checkpoint (savestate restores do NOT count as boots).
"""
import json
import os
import shutil
import sys

import numpy as np
from PIL import Image

REPO = "/home/z/my-project/ps1ai"
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, "scripts"))
import r35c_lib as L  # noqa: E402
from ps1play.core.host import LibretroCore  # noqa: E402

BOARD = L.BOARD
CTRLDIS = L.CTRLDIS

for d in (L.OUT, L.SHOTS, L.GIFD, os.path.join(L.WS, "system"),
          os.path.join(L.WS, "saves")):
    os.makedirs(d, exist_ok=True)

BOOT_N = L.consume_boot("r35c_boot_decode.py",
                        "boot 1/3: boot -> title -> START -> decode+validate "
                        "-> checkpoint; later phases resume from savestate")
L.jlog("boot_pre", boot=BOOT_N, cap=3)

shutil.copyfile(L.BIOS, os.path.join(L.WS, "system", "openbios.bin"))
core = LibretroCore(L.CORE, os.path.join(L.WS, "system"),
                    os.path.join(L.WS, "saves"),
                    var_overrides={b"beetle_psx_renderer": b"software",
                                   b"beetle_psx_frame_duping": b"disabled"})
L.core = core
av = core.load_game(L.CONTENT)
L.jlog("boot", core_name=core.core_name, av=av, boot=BOOT_N)

# ---- title wait -------------------------------------------------------------
pad_live = False
for _ in range(900):
    core.run_frame()
    if L.i32(0x18D08) >= 4 and \
            bytes(core.ram[L.PADB:L.PADB + 4]) == b"\x41\x5a\xff\xff":
        pad_live = True
        break
L.jlog("title_wait", pad_live=pad_live, f=core.frames_run)
L.snap(core, "title")

# ---- START -> gameplay ------------------------------------------------------
L.pulse(core, "START", hold=2, settle=60)
board_f = None
for _ in range(300):
    core.run_frame()
    if np.count_nonzero(core.ram[BOARD:BOARD + 4608]) > 0 and \
            core.ram[CTRLDIS] == 0:
        board_f = core.frames_run
        break
L.jlog("board_init", board_f=board_f, sym=L.sym())
L.snap(core, "game_start")

# ---- decode + validate ------------------------------------------------------
cells = L.decode()
st = L.stats(cells)
nb = L.check_neighbors(cells)
s = L.sym()
L.jlog("board_decode", stats=st, sym=s, neighbors_check=nb)

ok = (st["active"] == 192 and st["mines"] == 32 and st["revealed"] == 0
      and st["flagged"] == 0 and s["mine_count"] == 32
      and s["revealed_total"] == 0 and s["cursor"] == [0, 0]
      and s["lost"] == 0 and s["ctrl_dis"] == 0)
L.jlog("decode_assert", ok=ok)
if not ok:
    L.snap(core, "decode_FAIL")
    raise SystemExit("decode validation failed - see board_decode event")

# neighbor cross-validation: tolerate lazy-compute (all stored 0 at init)
if nb["n_mismatch"] == 0:
    L.jlog("neighbors_consistent", mode="full" if nb["nonzero_stored"] > 0
           else "trivial_all_zero")
elif nb["nonzero_stored"] == 0:
    L.jlog("neighbors_lazy_at_init",
           note="all stored neighbor fields 0 pre-first-click; using our own "
                "adjacency from mine bytes for planning")
else:
    L.snap(core, "neighbors_FAIL")
    raise SystemExit(f"neighbor mismatch on live data: {nb}")

mines = sorted([list(k) for k, v in cells.items() if v["mine"]])
zeros = sorted([list(k) for k, v in cells.items()
                if v["active"] and not v["mine"] and L.adj_mines(cells, *k) == 0])
L.jlog("derived", n_mines=len(mines), n_zero_cells=len(zeros),
       first_mines=mines[:8])
L.snap(core, "decoded_board")

# persist board for offline planning
board_js = {"cells": {f"{x},{y}": v for (x, y), v in cells.items()},
            "stats": st, "mines": mines, "zero_cells": zeros,
            "neighbors_check": nb, "frame": core.frames_run,
            "sym": s}
with open(os.path.join(L.OUT, "board_decode.json"), "w") as fh:
    json.dump(board_js, fh, indent=1)

# ---- checkpoint -------------------------------------------------------------
L.checkpoint(core, "ck_decode.bin")
L.jlog("phase1_done", boot=BOOT_N, stats=st,
       note="next phases resume from ck_decode.bin (no new boots)")
print("[r35c] PHASE1 OK boot=", BOOT_N, flush=True)
