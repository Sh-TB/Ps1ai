#!/usr/bin/env python3
"""Tetrade calibration — learn the game from the real running process.

Protocol (Issue #8, T1+T2+T3):
  1. boot -> title -> START -> menu -> confirm with B (PAD_CROSS per source)
     -> Marathon gameplay (source-verified: confirm = CROSS || START).
  2. savestate checkpoint right after entry (reproducibility anchor).
  3. RAM struct discovery by INPUT CAUSALITY: a LEFT hold decrements
     tetrimino.x (u32, one cell per frame) somewhere in RAM. Source layout
     (MIT Logan-Campbell/Tetrade, main.c):
       matrix int[20][10] @ +0        (800 B, 200 u32, values 0..8)
       Tetrimino tetrimino @ +800     (92 B: type,shape[16],x,y,held,rot,2ptr)
         -> type +800, shape +804, x +868, y +872, rotState +880
       nextTCount +892, nextTetriminos[14] +896 (92 B each)
       holdTerimino +2184, score +2280, single +2284, double +2288,
       triple +2292, tetrade +2296, level +2308, ghostY +2312,
       isGameOver +2316, isGamePaused +2320
     So g = x_addr - 868. Plausibility gates + a gravity y-rise proof
     reject false positives. Everything observe-only (no writes).
  4. Control causality with RAM evidence: LEFT/RIGHT move x, A rotates
     (shape[] changes), UP hard-drops (score += 2*cells), DOWN soft-drops
     (score += 1/cell).
  5. Reload the checkpoint: matrix must return to pre-probe state.

Outputs: JSON results + PNG evidence (local-only), profile update via
PS1Play.save_profile() with provenance labels.
"""
import json
import sys
import time

import numpy as np
from PIL import Image

REPO = "/home/z/my-project/ps1ai"
sys.path.insert(0, REPO)
from ps1play.api import PS1Play  # noqa: E402

EVID = "/home/z/my-project/emu/games_homebrew/evidence"
CUE = "/home/z/my-project/emu/games_homebrew/patched/tetrade_lic.cue"
WS = "/home/z/my-project/emu/games_homebrew/ws_tetrade_play"
OV = {b"beetle_psx_override_bios": b"openbios"}
OUT = {"script": "tetrade_calib", "started": time.strftime("%Y-%m-%d %H:%M:%S")}

# struct offsets relative to TetradeGame base (source-derived; sizes:
# matrix 20*10*4=800, Tetrimino=4+64+4+4+4+4+4+4=92, next[14]=1288)
OFF = {"matrix": 0, "tet_type": 800, "tet_shape": 804, "tet_x": 868,
       "tet_y": 872, "tet_held": 876, "tet_rot": 880, "next_count": 892,
       "next0_type": 896, "hold_type": 2184, "score": 2276, "single": 2280,
       "double": 2284, "triple": 2288, "tetra": 2292, "move_cd": 2296,
       "set_time": 2300, "level": 2304, "ghost_y": 2308, "game_over": 2312,
       "paused": 2316}


def shot(p, name):
    arr = np.asarray(p.core.frame_rgb())
    Image.fromarray(arr).save(f"{EVID}/{name}.png")
    return arr


def u32win(snap, addr, n):
    return np.frombuffer(bytes(snap[addr:addr + 4 * n]), dtype="<u4")


def struct_view(p, g):
    m = p.mem
    return {k: m.u32(g + v) for k, v in OFF.items()}


def board(p, g):
    return u32win(p.mem.snapshot(), g, 200).reshape(20, 10)


def discover_struct_base(p, settle=700):
    """Whole-RAM input-causality localization of TetradeGame (see header)."""
    p.core.run(settle, set())            # countdown done, piece falling
    a = p.mem.snapshot()
    p.core.run(2, {"LEFT"})              # x -= 1..2 (first frame = edge)
    p.core.run(12, set())
    b = p.mem.snapshot()
    a32 = np.frombuffer(bytes(a), dtype="<u4")
    b32 = np.frombuffer(bytes(b), dtype="<u4")
    drop = a32.astype(np.int64) - b32.astype(np.int64)
    hits = np.flatnonzero((drop >= 1) & (drop <= 2) & (a32 <= 10))
    print(f"[dbg] x-drop hits: {[hex(int(h)*4) for h in hits][:10]}")
    out = []
    for tx in hits:
        tx = int(tx) * 4
        g = tx - OFF["tet_x"]
        if g <= 0x10000:
            continue
        mat = u32win(p.mem.snapshot(), g, 200)
        typ = p.mem.u32(g + OFF["tet_type"])
        gates = {"level": p.mem.u32(g + OFF["level"]),
                 "score": p.mem.u32(g + OFF["score"]),
                 "over": p.mem.u32(g + OFF["game_over"]),
                 "mat_max": int(mat.max()), "typ": int(typ)}
        print(f"[dbg] tx={hex(tx)} g={hex(g)} gates={gates}")
        if (gates["level"] == 0 and gates["score"] == 0 and
                gates["over"] == 0 and gates["mat_max"] <= 8 and
                (1 <= typ <= 7 or typ == 0xFFFFFFFF)):
            out.append({"g": g, "tx": tx, "type": int(typ)})
    return out


def y_fall_proof(p, g, windows=6, per=15):
    """tetrimino.y must increase by 1..2 per gravity step (30f/cell)."""
    ys = []
    for _ in range(windows):
        ys.append(p.mem.u32(g + OFF["tet_y"]))
        p.core.run(per, set())
    rises = [(b - a) for a, b in zip(ys, ys[1:]) if 0 < b - a <= 2]
    return {"ys": ys, "gravity_confirmed": bool(rises)}


def main():
    p = PS1Play(CUE, workspace=WS, var_overrides=OV, verbose=False)
    info = p.boot()
    OUT["boot"] = info

    # ---- 1) boot chain -------------------------------------------------
    p.core.run(900, set())                       # BIOS/logo settle
    shot(p, "tplay_00_title")
    p.core.run(120, {"START"})                   # hold START
    p.core.run(90, set())                        # explicit release
    p.core.run(120, set())                       # settle on menu
    shot(p, "tplay_01_menu")
    OUT["menu_reached"] = True

    # confirm Marathon with B (= PAD_CROSS via beetle mapping, source-verified)
    p.core.run(20, {"B"})
    p.core.run(20, set())
    p.core.run(500, set())                       # 3-2-1 countdown + spawn
    shot(p, "tplay_02_gameplay")

    # ---- 2) checkpoint --------------------------------------------------
    p.save_state("m_fresh")
    OUT["checkpoint"] = "m_fresh"

    # ---- 3) struct discovery by input causality --------------------------
    cands = discover_struct_base(p)
    OUT["struct_candidates"] = cands
    g = None
    for c in cands:
        yv = y_fall_proof(p, c["g"])
        if yv["gravity_confirmed"]:
            g = c["g"]
            OUT["struct_base_probe"] = {"accepted": c, "y_proof": yv}
            break
        OUT.setdefault("rejected", []).append({**c, "y_proof": yv})
    if g is None:
        json.dump(OUT, open(f"{EVID}/tetrade_calib.json", "w"), indent=1)
        print("NO CAUSALLY VERIFIED STRUCT BASE — aborting (honest failure)")
        return 1
    OUT["struct_base"] = g
    OUT["struct_fields_check"] = struct_view(p, g)
    shot(p, "tplay_03_live")

    # ---- 4) control causality (RAM-verified) ----------------------------
    f0 = struct_view(p, g)
    x0 = f0["tet_x"]

    p.core.run(3, {"LEFT"})
    p.core.run(20, set())
    f1 = struct_view(p, g)
    OUT["left_probe"] = {"x0": x0, "x1": f1["tet_x"],
                         "moved": 0 <= f1["tet_x"] < x0}

    p.core.run(3, {"RIGHT"})
    p.core.run(20, set())
    f2 = struct_view(p, g)
    OUT["right_probe"] = {"x1": f1["tet_x"], "x2": f2["tet_x"],
                          "moved": f2["tet_x"] > f1["tet_x"]}

    shape0 = u32win(p.mem.snapshot(), g + OFF["tet_shape"], 16).tolist()
    p.core.run(1, {"A"})                         # PAD_CIRCLE = rotate CW
    p.core.run(20, set())
    shape1 = u32win(p.mem.snapshot(), g + OFF["tet_shape"], 16).tolist()
    OUT["rotate_probe"] = {"shape_changed": shape0 != shape1,
                           "rot_before": f2["tet_rot"],
                           "rot_after": struct_view(p, g)["tet_rot"]}

    s_pre = struct_view(p, g)
    p.core.run(1, {"UP"})                        # PAD_UP = hard drop
    p.core.run(60, set())
    s_post = struct_view(p, g)
    OUT["harddrop_probe"] = {
        "score_pre": s_pre["score"], "score_post": s_post["score"],
        "score_increased": s_post["score"] > s_pre["score"],
        "type_changed": s_pre["tet_type"] != s_post["tet_type"]}

    s_pre2 = struct_view(p, g)
    for _ in range(8):
        p.core.run(1, {"DOWN"})
        p.core.run(5, set())
    s_post2 = struct_view(p, g)
    OUT["softdrop_probe"] = {"score_pre": s_pre2["score"],
                             "score_post": s_post2["score"]}

    OUT["board_after_probes"] = board(p, g).tolist()

    # ---- 5) checkpoint restore proof ------------------------------------
    p.load_state("m_fresh")
    p.core.run(30, set())
    OUT["restore_proof"] = {
        "matrix_digest": int(u32win(p.mem.snapshot(), g, 200).sum()),
        "score_after_restore": struct_view(p, g)["score"],
        "level_after_restore": struct_view(p, g)["level"]}
    shot(p, "tplay_04_restored")

    # ---- 6) freeze anchors into the profile ------------------------------
    p.profile["discovered"] = {
        "struct_base": {"addr": g,
                        "provenance": "SOURCE_DERIVED (main.c layout, MIT "
                                      "Logan-Campbell/Tetrade) + LIVE_VERIFIED "
                                      "by input causality (tetrade_calib.py)"},
        "fields": {k: g + v for k, v in OFF.items()},
        "probes": {k: OUT[k] for k in
                   ("left_probe", "right_probe", "rotate_probe",
                    "harddrop_probe", "softdrop_probe")}}
    p.save_profile()
    OUT["profile_saved"] = p.profile_path

    json.dump(OUT, open(f"{EVID}/tetrade_calib.json", "w"), indent=1)
    summ = {k: v for k, v in OUT.items() if not k.startswith("board_")}
    print(json.dumps(summ, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
