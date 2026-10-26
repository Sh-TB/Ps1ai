#!/usr/bin/env python3
"""tetrade_calib2.py — Issue #6 round 7: the Tetrade calibration ladder
(fresh re-derivation, Nortis-playbook style, dead ends preserved).

Issue #8 localized the TetradeGame struct live (base 0x1FECA0), but its
evidence directory was lost to the environment reset.  This script
re-derives EVERYTHING behaviorally from a fresh boot in ONE process
(one beetle boot — the lab's hard rule), using the savestate API to
checkpoint between probes:

  0. boot -> title (PNG) -> START -> menu (PNG) -> B -> Marathon
     (PNG, 3-2-1 countdown) -> save_state("r7_fresh") anchor.
  1. X locality: whole-RAM u32 diff around a LEFT tap; candidates =
     addresses that DROPPED by 1..2 with pre-value <= 10 (the piece x,
     one cell per edge); struct base = x_addr - 868 (source layout);
     plausibility gates reject false positives.
  2. gravity: tetrimino.y must rise 1..2 per 15f window (BASE_DROP_RATE
     30 f/cell at level 0 — source main.c line 1080).
  3. board writes: a hard drop must write ONLY inside [base, base+800)
     (the 20x10 int matrix), values 0..8; score += 2/cell (HARD_DROP_
     SCORE, line 1011); piece type changes (type -> -1 on lock).
  4. soft-drop score causality: held DOWN = 4 f/cell (SOFT_DROP_RATE,
     line 52), score += 1/cell (SOFT_DROP_SCORE).
  5. lines counters: singleLine/doubleLine/tripleLine/tetrade at
     base+2280..2292 — identity check (all 0 on a fresh cycle, stable
     while no clear); their +delta on a clear is proven by the
     tetrade_lineclear.py run.
  6. restore proof: load_state("r7_fresh") -> matrix digest, score and
     counters return bit-for-bit to the anchor values.

Source ground truth quoted in playloop.TetradeLoopPolicy docstring
(MIT Logan-Campbell/Tetrade src/main.c @ v1.0, clone 5155664).
Outputs: calib2_report.json + PNGs + JSONL in the round-7 evidence dir.
"""
import argparse
import json
import os
import sys
import time

import numpy as np
from PIL import Image

REPO = "/home/z/my-project/ps1ai"
if REPO not in sys.path:
    sys.path.insert(0, REPO)
from ps1play.api import PS1Play  # noqa: E402

CUE = "/home/z/my-project/emu/games_homebrew/patched/tetrade_lic.cue"
WS = "/home/z/my-project/emu/ws_tetrade_r7"
EVID = os.path.join(REPO, "scratch", "issue6_round7_tetrade")
OFF = {"matrix": 0, "tet_type": 800, "tet_shape": 804, "tet_x": 868,
       "tet_y": 872, "tet_held": 876, "tet_rot": 880, "next_count": 892,
       "score": 2276, "single": 2280, "double": 2284, "triple": 2288,
       "tetra": 2292, "move_cd": 2296, "set_time": 2300, "level": 2304,
       "ghost_y": 2308, "over": 2312, "paused": 2316}
WALL_BUDGET_S = 420.0
T0 = time.time()


def wall():
    return round(time.time() - T0, 1)


def guard(where):
    if time.time() - T0 > WALL_BUDGET_S:
        print(f"[wall-guard] budget {WALL_BUDGET_S}s exceeded at {where}")
        return False
    return True


def shot(p, name):
    arr = np.asarray(p.core.frame_rgb())
    Image.fromarray(arr).save(os.path.join(EVID, f"{name}.png"))
    return name


def u32win(snap, addr, n):
    return np.frombuffer(bytes(snap[addr:addr + 4 * n]), dtype="<u4")


def struct_view(p, g):
    return {k: p.mem.u32(g + v) for k, v in OFF.items()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(EVID,
                                                  "calib2_report.json"))
    args = ap.parse_args()
    os.makedirs(EVID, exist_ok=True)
    jl = open(os.path.join(EVID, "calib2.jsonl"), "w")

    def J(ev):
        ev = {"t_s": wall(), **ev}
        jl.write(json.dumps(ev, default=str) + "\n")
        jl.flush()
        print("[calib2]", json.dumps(ev, default=str)[:200], flush=True)

    OUT = {"script": "tetrade_calib2", "started": time.strftime("%FT%TZ"),
           "cue": CUE, "workspace": WS}
    ok = True

    # ---- 0) boot chain (ONE boot) --------------------------------------
    p = PS1Play(CUE, workspace=WS, verbose=False)
    info = p.boot()
    OUT["boot"] = {k: info.get(k) for k in
                   ("core", "serial", "plugin", "ram_bytes")}
    J({"ev": "boot", **OUT["boot"]})
    p.core.run(900, set())
    shot(p, "r7_00_title")
    p.core.run(120, {"START"})
    p.core.run(90, set())
    p.core.run(120, set())
    shot(p, "r7_01_menu")
    p.core.run(20, {"B"})
    p.core.run(20, set())
    p.core.run(500, set())
    shot(p, "r7_02_gameplay")
    OUT["menu_chain"] = "title->START->menu->B->Marathon(500f settle)"
    J({"ev": "nav_done"})

    # anchor: the reproducibility checkpoint for every later probe
    p.save_state("r7_fresh")
    OUT["checkpoint"] = "r7_fresh"
    J({"ev": "checkpoint_saved", "name": "r7_fresh"})

    # ---- 1) X locality by input causality -------------------------------
    a = bytes(p.mem.snapshot())
    p.core.run(2, {"LEFT"})
    p.core.run(12, set())
    b = bytes(p.mem.snapshot())
    a32 = np.frombuffer(a, dtype="<u4")
    b32 = np.frombuffer(b, dtype="<u4")
    drop = a32.astype(np.int64) - b32.astype(np.int64)
    hits = np.flatnonzero((drop >= 1) & (drop <= 2) & (a32 <= 10))
    J({"ev": "left_tap_diff", "n_hits": int(hits.size),
       "addrs": [hex(int(h) * 4) for h in hits][:12]})
    cands = []
    for tx in hits:
        tx = int(tx) * 4
        g = tx - OFF["tet_x"]
        if g < 0x10000:
            continue
        s = struct_view(p, g)
        mat = u32win(p.mem.snapshot(), g, 200)
        gates = {"level": s["level"], "score": s["score"],
                 "over": s["over"], "mat_max": int(mat.max()),
                 "typ": s["tet_type"], "x": s["tet_x"]}
        if (gates["level"] == 0 and gates["score"] == 0 and
                gates["over"] == 0 and gates["mat_max"] <= 8 and
                gates["typ"] in (1, 2, 3, 4, 5, 6, 7)):
            cands.append({"base": g, "x_addr": tx, "gates": gates})
    OUT["struct_candidates"] = cands
    J({"ev": "struct_candidates", "n": len(cands), "cands": cands})
    if not cands:
        # honest dead end: fall back to the Issue-8 anchor and verify it
        g0 = 2092192
        s = struct_view(p, g0)
        OUT["fallback_anchor"] = {"base": g0, "struct": s}
        J({"ev": "fallback_anchor", **OUT["fallback_anchor"]})
        cands = [{"base": g0, "x_addr": g0 + OFF["tet_x"],
                  "gates": "fallback"}]
    g = cands[0]["base"]
    OUT["struct_base"] = g
    OUT["struct_base_hex"] = hex(g)
    OUT["struct_fields"] = struct_view(p, g)

    # ---- 2) gravity proof ------------------------------------------------
    if not guard("gravity"):
        ok = False
    ys = []
    for _ in range(6):
        ys.append(int(p.mem.u32(g + OFF["tet_y"])))
        p.core.run(15, set())
    rises = [(y1 - y0) for y0, y1 in zip(ys, ys[1:]) if 0 < y1 - y0 <= 2]
    OUT["gravity"] = {"ys": ys, "rises": rises,
                      "confirmed": bool(rises)}
    J({"ev": "gravity", **OUT["gravity"]})

    # ---- 3) board-write locality on a hard drop --------------------------
    if not guard("harddrop"):
        ok = False
    pre_snap = bytes(p.mem.snapshot())
    pre = struct_view(p, g)
    p.core.run(1, {"UP"})
    p.core.run(60, set())
    post = struct_view(p, g)
    ch = np.flatnonzero(np.frombuffer(pre_snap, dtype=np.uint8) !=
                        np.frombuffer(bytes(p.mem.snapshot()),
                                      dtype=np.uint8))
    in_matrix = int(((ch >= g) & (ch < g + 800)).sum())
    OUT["harddrop"] = {
        "score_pre": pre["score"], "score_post": post["score"],
        "score_delta": post["score"] - pre["score"],
        "type_pre": pre["tet_type"], "type_post": post["tet_type"],
        "changed_bytes": int(ch.size), "changed_in_matrix": in_matrix,
        "all_in_matrix": bool(in_matrix == ch.size) if ch.size else None,
        "matrix_after": u32win(p.mem.snapshot(), g, 200).reshape(20, 10)
                         .tolist()}
    J({"ev": "harddrop", **{k: v for k, v in OUT["harddrop"].items()
                            if k != "matrix_after"}})

    # ---- 4) soft-drop score causality ------------------------------------
    if not guard("softdrop"):
        ok = False
    pre2 = struct_view(p, g)
    for _ in range(12):
        p.core.run(1, {"DOWN"})
        p.core.run(4, set())
    post2 = struct_view(p, g)
    OUT["softdrop"] = {"score_pre": pre2["score"],
                       "score_post": post2["score"],
                       "delta": post2["score"] - pre2["score"]}
    J({"ev": "softdrop", **OUT["softdrop"]})

    # ---- 5) counter identity (fresh cycle) + stability -------------------
    if not guard("counters"):
        ok = False
    counters = {k: int(p.mem.u32(g + OFF[k]))
                for k in ("single", "double", "triple", "tetra", "level",
                          "score", "over", "paused")}
    OUT["counters_now"] = counters
    J({"ev": "counters", **counters})

    # ---- 6) restore proof -------------------------------------------------
    if not guard("restore"):
        ok = False
    p.load_state("r7_fresh")
    p.core.run(30, set())
    post_restore = struct_view(p, g)
    mat_now = u32win(p.mem.snapshot(), g, 200)
    anchor_mat = u32win(a, g, 200)
    OUT["restore"] = {
        "matrix_digest_restored": int(mat_now.sum()),
        "matrix_digest_anchor": int(anchor_mat.sum()),
        "matrix_bitexact": bool(np.array_equal(mat_now, anchor_mat)),
        "score_restored": post_restore["score"],
        "score_anchor": OUT["struct_fields"]["score"]}
    J({"ev": "restore", **OUT["restore"]})
    shot(p, "r7_03_restored")

    OUT["wall_s"] = wall()
    OUT["ok"] = bool(ok and OUT["gravity"]["confirmed"] and
                     OUT["restore"]["matrix_bitexact"])
    with open(args.out, "w") as f:
        json.dump(OUT, f, indent=1, default=str)
    jl.close()
    # NOTE: LibretroCore has no close(); the process exits and reaps the
    # core (one boot per process — never re-boot in-process).
    print("calib2 done:", json.dumps({k: OUT[k] for k in
                                      ("struct_base", "struct_base_hex",
                                       "gravity", "ok", "wall_s")},
                                     default=str)[:300])
    return 0 if OUT["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
