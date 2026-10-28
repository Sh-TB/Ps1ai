#!/usr/bin/env python3
"""r35c_reveal.py — R35-C phase 2: reveal ALL 160 safe cells (REVT 0->160).

Resume protocol: unserialize newest checkpoint (ck_decode.bin or
ck_reveal_*.bin). The restore calls load_game + unserialize; per ledger
rule savestate restores are NOT counted boots (logged as kind=restore).

Execution is adaptive from RAM each step:
  - decode board, choose nearest unrevealed safe cell (zero-adjacency
    cells preferred -> floods), navigate with verified taps, CROSS 40f,
    verify revealed-set == flood prediction (8-conn first, 4-conn
    fallback, else permissive non-mine-only fallback, all logged).
  - any newly-revealed "mine" per decode => decode bug => abort.
Milestone at REVT==160: PNG + RAM window dump + 180f win-watch.
"""
import json
import os
import sys
import time

import numpy as np

REPO = "/home/z/my-project/ps1ai"
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, "scripts"))
import r35c_lib as L  # noqa: E402
from ps1play.core.host import LibretroCore  # noqa: E402

CTRLDIS = L.CTRLDIS
BOOTJS = os.path.join(L.OUT, "reveal_summary.json")
R = {"phase": "reveal", "events": [], "shots": []}


def dump():
    json.dump(R, open(BOOTJS, "w"), indent=1, default=str)


def jlog(event, **kw):
    L.jlog(event, **kw)
    R["events"].append({"event": event, **kw})
    dump()


# ---- fresh process: build core + restore checkpoint (no cold boot) ----------
os.makedirs(os.path.join(L.WS, "system"), exist_ok=True)
os.makedirs(os.path.join(L.WS, "saves"), exist_ok=True)
if not os.path.exists(os.path.join(L.WS, "system", "openbios.bin")):
    import shutil
    shutil.copyfile(L.BIOS, os.path.join(L.WS, "system", "openbios.bin"))
core = LibretroCore(L.CORE, os.path.join(L.WS, "system"),
                    os.path.join(L.WS, "saves"),
                    var_overrides={b"beetle_psx_renderer": b"software",
                                   b"beetle_psx_frame_duping": b"disabled"})
L.core = core
ck = L.latest_checkpoint("ck_reveal_") or os.path.join(L.WS, "ck_decode.bin")
av = core.load_game(L.CONTENT)          # mechanical substrate of restore
core.unserialize(open(ck, "rb").read())  # -> exact checkpoint state
led = json.load(open(L.LEDDER))
led["log"].append({"boot": None, "kind": "restore_not_counted",
                   "script": "r35c_reveal.py", "checkpoint": os.path.basename(ck),
                   "t": time.strftime("%FT%TZ", time.gmtime())})
json.dump(led, open(L.LEDDER, "w"), indent=1)
jlog("restore", checkpoint=os.path.basename(ck), av=av, sym=L.sym())

# sanity: state must match the decode-time board
cells0 = L.decode()
st0 = L.stats(cells0)
assert st0["mines"] == 32 and st0["active"] == 192, "restore sanity failed"
S = L.Sampler(core, stride=90)


def runf(n):
    S.run(n)


def conn_flood(cells, tx, ty, conn):
    NBR = L.NBR8 if conn == 8 else [(-1, 0), (1, 0), (0, -1), (0, 1)]

    def adj(x, y):
        n = 0
        for dx, dy in NBR:
            nx, ny = x + dx, y + dy
            if 0 <= nx < L.GRID_W and 0 <= ny < L.GRID_H and \
                    cells[(nx, ny)]["mine"]:
                n += 1
        return n

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
        if adj(x, y) == 0:
            for dx, dy in NBR:
                nx, ny = x + dx, y + dy
                if 0 <= nx < L.GRID_W and 0 <= ny < L.GRID_H:
                    stack.append((nx, ny))
    return out


CONN = 8
FALLBACK = None
last_ck = core.frames_run
clicks = 0
swallows = 0
mismatch_fallback = 0

t0w = time.time()
while True:
    cells = L.decode()
    st = L.stats(cells)
    cur = (L.i32(L.CURX), L.i32(L.CURY))
    safe_un = [k for k, v in cells.items()
               if v["active"] and not v["mine"] and not v["revealed"]]
    if not safe_un:
        break
    zeros = [k for k in safe_un if L.adj_mines(cells, *k) == 0]
    pool = zeros if zeros else safe_un
    tgt = min(pool, key=lambda k: abs(k[0] - cur[0]) + abs(k[1] - cur[1]))
    kind = "zero" if zeros else "single"

    if not L.navigate(core, *tgt):
        jlog("nav_abort", target=list(tgt), cursor=list(cur))
        raise SystemExit("navigation failed - checkpoint preserved")
    assert (L.i32(L.CURX), L.i32(L.CURY)) == tgt

    pre_cells = L.decode()
    pre_revt = L.i32(L.REVT)
    pred8 = conn_flood(pre_cells, *tgt, 8)
    pred4 = conn_flood(pre_cells, *tgt, 4)

    # CROSS hold 40f (game polls pad every ~33f) then settle 90f
    core.set_buttons("B")
    runf(40)
    core.set_buttons(set())
    runf(90)
    clicks += 1

    post_cells = L.decode()
    newly = {k for k, v in post_cells.items()
             if v["revealed"] and not pre_cells[k]["revealed"]}
    got_revt = L.i32(L.REVT)

    if not newly and got_revt == pre_revt:
        # swallowed poll: retry the click once
        swallows += 1
        jlog("click_swallowed", target=list(tgt), kind=kind, retry=1)
        core.set_buttons("B")
        runf(40)
        core.set_buttons(set())
        runf(90)
        clicks += 1
        post_cells = L.decode()
        newly = {k for k, v in post_cells.items()
                 if v["revealed"] and not pre_cells[k]["revealed"]}
        got_revt = L.i32(L.REVT)
        if not newly:
            jlog("click_dead_abort", target=list(tgt), sym=L.sym())
            L.snap(core, "click_dead")
            raise SystemExit("click had no effect twice - abort")

    bad_mine = [k for k in newly if post_cells[k]["mine"]]
    if bad_mine:
        L.snap(core, "MINE_DECODE_BUG")
        jlog("decode_bug_mine_revealed", cells=[list(k) for k in bad_mine],
             sym=L.sym())
        raise SystemExit("revealed a cell decoded as mine - decode bug")

    exact = None
    if newly == pred8:
        exact = 8
        if CONN != 8:
            jlog("conn_mode_switch", from_=CONN, to=8)
            CONN = 8
    elif newly == pred4:
        exact = 4
        if CONN != 4:
            jlog("conn_mode_switch", from_=CONN, to=4)
            CONN = 4
    else:
        mismatch_fallback += 1
        if FALLBACK is None:
            FALLBACK = True
            jlog("sim_fallback_permissive",
                 detail={"predicted8": sorted(list(map(list, pred8)))[:24],
                         "predicted4": sorted(list(map(list, pred4)))[:24],
                         "got": sorted(list(map(list, newly)))[:24]})
        else:
            jlog("sim_mismatch_repeat", target=list(tgt), got_n=len(newly),
                 pred8_n=len(pred8), pred4_n=len(pred4))

    jlog("reveal_click", target=list(tgt), kind=kind, new=len(newly),
         revt=(pre_revt, got_revt), exact_conn=exact, clicks=clicks,
         wall=round(time.time() - t0w, 1))

    if got_revt != pre_revt + len(newly):
        jlog("revt_mismatch", sym=L.sym())
        raise SystemExit("REVT vs board mismatch")

    if core.frames_run - last_ck > 1500:
        L.checkpoint(core, f"ck_reveal_{core.frames_run:07d}.bin")
        last_ck = core.frames_run

# ---- milestone: REVT==160 full clear ----------------------------------------
st = L.stats(L.decode())
assert st["revealed"] == 160 and st["mines"] == 32, st
L.snap(core, "full_clear")
hexwin = {hex(a): int(core.ram[a]) for a in range(0x18CC0, 0x18D40, 4)}
jlog("FULL_CLEAR", stats=st, sym=L.sym(), ram_window=hexwin)

base = core.frame_rgb()
maxd = 0.0
for i in range(6):
    runf(30)
    arr = core.frame_rgb()
    if arr is not None and base is not None:
        maxd = max(maxd, float(np.abs(arr.astype(int) - base.astype(int)).mean()))
L.snap(core, "full_clear_plus180f")
jlog("win_watch_reveal", watch_frames=180, max_frame_diff=round(maxd, 3),
     sym=L.sym())

L.checkpoint(core, f"ck_reveal_{core.frames_run:07d}.bin")
R["summary"] = {"revealed": st["revealed"], "clicks": clicks,
                "swallows": swallows, "mismatch_fallback": mismatch_fallback,
                "conn": CONN, "frames": core.frames_run,
                "wall_s": round(time.time() - t0w, 1)}
dump()
print("[r35c] PHASE2 OK REVT=160 clicks=", clicks, "frames=", core.frames_run,
      flush=True)
