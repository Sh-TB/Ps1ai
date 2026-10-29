#!/usr/bin/env python3
"""r43_mspsx_regression.py — R43 (the 40% track, mspsx): the recorded
r35 win regression, 1 boot.

The mspsx capsule's recorded lever ("next mspsx round = the r35 win
regression, 1 boot, when the 60/40 budget allocates it").  Recipe:
fresh cold boot -> title wait -> START -> fresh board (BOARD nonzero +
CTRLDIS 0) -> the r35c adaptive reveal loop (decode RAM board, nearest
unrevealed safe cell, zero-adjacency floods preferred, verified taps,
CROSS 40f hold) to REVT 160.

Oracle (capsule, unchanged): **REVT 0->160 monotone** + the
auto-flagged win screen (the 180f frame-diff win watch + the
0x18CC0-0x18D40 RAM window, the r35 milestone evidence set).
Baseline to compare: the r35 win = 59 clicks, 0 swallowed, 0 nav
failures, 14,665 frames (docs/issue6_r35_report.md).
+0x8E-style provenance rules do not apply here (different game); the
boot ledger cap 1 disclosed pre-run.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import time

import numpy as np

REPO = "/home/z/my-project/ps1ai"
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, "scripts"))
import r35c_lib as L                              # noqa: E402
from ps1play.core.host import LibretroCore        # noqa: E402

SCRATCH = os.path.join(REPO, "scratch", "r43_mspsx")
LEDGER = os.path.join(SCRATCH, "boots_used.json")
REPORT = os.path.join(SCRATCH, "r43_mspsx_regression_report.json")
EVID = os.path.join(REPO, "data", "games", "homebrew", "mspsx", "r43")


def log(*a):
    print("[r43-mspsx]", *a, file=sys.stderr, flush=True)


def amend_ledger():
    os.makedirs(SCRATCH, exist_ok=True)
    if not os.path.exists(LEDGER):
        with open(LEDGER, "w") as f:
            json.dump({"cap": 1, "count": 0, "log": [], "note":
                       "R43 regression: 1 cold boot, fresh board, the "
                       "r35c adaptive reveal to REVT 160"}, f, indent=1)
    with open(LEDGER) as f:
        led = json.load(f)
    led["count"] += 1
    led["log"].append({"n": led["count"],
                       "ts": time.strftime("%FT%TZ", time.gmtime()),
                       "script": "r43_mspsx_regression.py",
                       "reason": "the recorded 1-boot win regression"})
    with open(LEDGER, "w") as f:
        json.dump(led, f, indent=1)
    log(f"boot ledger: {led['count']}/{led['cap']}")
    return led["count"]


def conn_flood(cells, tx, ty, conn):
    NBR = L.NBR8 if conn == 8 else [(-1, 0), (1, 0), (0, -1), (0, 1)]
    adj = lambda x, y: sum(                       # noqa: E731
        1 for dx, dy in NBR
        if 0 <= x + dx < L.GRID_W and 0 <= y + dy < L.GRID_H
        and cells[(x + dx, y + dy)]["mine"])
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


def main():
    amend_ledger()
    os.makedirs(SCRATCH, exist_ok=True)
    os.makedirs(EVID, exist_ok=True)
    for d in (os.path.join(L.WS, "system"), os.path.join(L.WS, "saves")):
        os.makedirs(d, exist_ok=True)
    shutil.copyfile(L.BIOS, os.path.join(L.WS, "system", "openbios.bin"))
    core = LibretroCore(L.CORE, os.path.join(L.WS, "system"),
                        os.path.join(L.WS, "saves"),
                        var_overrides={
                            b"beetle_psx_renderer": b"software",
                            b"beetle_psx_frame_duping": b"disabled"})
    L.core = core
    ev = []

    def J(**kw):
        ev.append(kw)
        log(kw.get("event", ""), {k: v for k, v in kw.items()
                                  if k != "event"})

    t0 = time.time()
    av = core.load_game(L.CONTENT)
    J(event="boot", av=av, content=os.path.basename(L.CONTENT))
    # ---- title wait ------------------------------------------------------
    pad_live = False
    for _ in range(900):
        core.run_frame()
        if L.i32(0x18D08) >= 4 and \
                bytes(core.ram[L.PADB:L.PADB + 4]) == b"\x41\x5a\xff\xff":
            pad_live = True
            break
    J(event="title_wait", pad_live=pad_live, f=core.frames_run)
    # ---- START -> fresh board --------------------------------------------
    L.pulse(core, "START", hold=2, settle=60)
    board_f = None
    for _ in range(300):
        core.run_frame()
        if np.count_nonzero(core.ram[L.BOARD:L.BOARD + 4608]) > 0 and \
                core.ram[L.CTRLDIS] == 0:
            board_f = core.frames_run
            break
    J(event="board_init", board_f=board_f)
    ok = False
    clicks, revt_trace, win_watch = 0, [], None
    if board_f is None:
        J(event="ABORT", why="no fresh board after START")
    else:
        # ---- the r35c adaptive reveal loop --------------------------------
        CONN, clicks, swallows, fallback = 8, 0, 0, 0
        revt_trace = [L.i32(L.REVT)]
        nav_fail = 0
        dead = False
        while True:
            cells = L.decode()
            st = L.stats(cells)
            cur = (L.i32(L.CURX), L.i32(L.CURY))
            safe_un = [k for k, v in cells.items()
                       if v["active"] and not v["mine"] and
                       not v["revealed"]]
            if not safe_un:
                break
            zeros = [k for k in safe_un if L.adj_mines(cells, *k) == 0]
            pool = zeros if zeros else safe_un
            tgt = min(pool, key=lambda k: abs(k[0] - cur[0]) +
                      abs(k[1] - cur[1]))
            if not L.navigate(core, *tgt):
                nav_fail += 1
                J(event="nav_abort", target=list(tgt), cursor=list(cur))
                dead = True
                break
            pre_cells = L.decode()
            pre_revt = L.i32(L.REVT)
            pred8 = conn_flood(pre_cells, *tgt, 8)
            pred4 = conn_flood(pre_cells, *tgt, 4)
            core.set_buttons("B")
            for _ in range(40):
                core.run_frame()
            core.set_buttons(set())
            for _ in range(90):
                core.run_frame()
            clicks += 1
            post_cells = L.decode()
            newly = {k for k, v in post_cells.items()
                     if v["revealed"] and not pre_cells[k]["revealed"]}
            got = L.i32(L.REVT)
            if not newly and got == pre_revt:
                swallows += 1
                core.set_buttons("B")
                for _ in range(40):
                    core.run_frame()
                core.set_buttons(set())
                for _ in range(90):
                    core.run_frame()
                clicks += 1
                post_cells = L.decode()
                newly = {k for k, v in post_cells.items()
                         if v["revealed"] and
                         not pre_cells[k]["revealed"]}
                got = L.i32(L.REVT)
                if not newly:
                    J(event="click_dead_abort", target=list(tgt))
                    dead = True
                    break
            bad = [k for k in newly if post_cells[k]["mine"]]
            if bad:
                J(event="decode_bug_mine_revealed",
                  cells=[list(k) for k in bad])
                dead = True
                break
            if newly == pred8:
                CONN = 8
            elif newly == pred4:
                CONN = 4
            else:
                fallback += 1
            if got < pre_revt or got != pre_revt + len(newly):
                J(event="REVT_VIOLATION", pre=pre_revt, got=got,
                  new=len(newly), sym=L.sym())
                dead = True
                break
            revt_trace.append(got)
            if clicks % 10 == 0:
                J(event="progress", clicks=clicks, revt=got,
                  revealed=st["revealed"])
        st = L.stats(L.decode())
        J(event="reveal_end", dead=dead, clicks=clicks, swallows=swallows,
          nav_fail=nav_fail, fallback=fallback, stats=st,
          revt_final=revt_trace[-1] if revt_trace else None,
          monotone=all(b >= a for a, b in
                       zip(revt_trace, revt_trace[1:])))
        # ---- the win watch (the r35 milestone evidence set) --------------
        win_watch = None
        if not dead and st["revealed"] == 160 and st["mines"] == 32:
            base = core.frame_rgb()
            maxd = 0.0
            for _ in range(6):
                for _ in range(30):
                    core.run_frame()
                arr = core.frame_rgb()
                if arr is not None and base is not None:
                    maxd = max(maxd, float(np.abs(
                        arr.astype(int) - base.astype(int)).mean()))
            win_watch = {"watch_frames": 180,
                         "max_frame_diff": round(maxd, 3)}
            hexwin = {hex(a): int(core.ram[a])
                      for a in range(0x18CC0, 0x18D40, 4)}
            J(event="FULL_CLEAR", stats=st, ram_window=hexwin,
              **win_watch)
            try:
                rgb = core.frame_rgb()
                if rgb is not None:
                    from PIL import Image
                    Image.fromarray(rgb).save(
                        os.path.join(SCRATCH, "r43_mspsx_win.png"))
            except Exception as e:                       # noqa: BLE001
                log("png failed:", repr(e)[:120])
        ok = (not dead and st["revealed"] == 160 and
              st["mines"] == 32 and len(revt_trace) > 1 and
              all(b >= a for a, b in zip(revt_trace, revt_trace[1:])))
    monotone = (len(revt_trace) > 1 and revt_trace[0] == 0 and
                revt_trace[-1] == 160 and
                all(b >= a for a, b in zip(revt_trace, revt_trace[1:])))
    res = {
        "schema": "ps1play.r43-mspsx-regression/1",
        "generated": time.strftime("%FT%TZ", time.gmtime()),
        "commit": os.popen("git -C %s rev-parse HEAD"
                           % REPO).read().strip(),
        "oracle": {"revt_monotone_0_to_160": bool(monotone),
                   "win_screen_watch": win_watch},
        "baseline_comparison": {"r35_clicks": 59, "r35_frames": 14665,
                                "this_clicks": clicks,
                                "this_frames": core.frames_run},
        "events": ev,
        "wall_s": round(time.time() - t0, 1)}
    res["outcome"] = ("WIN_REGRESSION_VERIFIED" if ok else "REGRESSION_FAIL")
    with open(REPORT, "w") as f:
        json.dump(res, f, indent=1, default=str)
    log("FIN:", res["outcome"], "clicks=", clicks,
        "revt=", revt_trace[-1] if revt_trace else None)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
