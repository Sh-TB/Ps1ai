#!/usr/bin/env python3
"""r63_tetrade_full_loop.py — R63 (Issue #8 re-delivery): the COMPLETE
Tetrade game loop on the current stack, one boot, real pad input only,
zero core edits, zero memory writes.

Flow: boot -> title -> START -> menu -> CROSS(Marathon) -> START ->
countdown -> anchor scan (struct located by signature, offsets derived
from the MIT-licensed source) -> Dellacherie 2-ply policy (current +
NEXT piece, board read from RAM) -> natural game over (stack overflow,
no writes) -> CONTINUE refused with CIRCLE -> menu -> restart -> fresh
Marathon verified (counters zeroed).

Struct offsets (TetradeGame, mips o32, ints): matrix[20][10]@+0,
tetrimino{type@+800, shape@+804, x@+868, y@+872, wasHeld@+876,
rotState@+880}, nextTCount@+892, nextTetriminos[14].type@+896+92k,
hold.type@+2184, score@+2276, single@+2280, double@+2284, triple@+2288,
tetrade@+2292, moveCooldown@+2296, setTime@+2300, level@+2304,
ghostY@+2308, isGameOver@+2312, isGamePaused@+2316.
"""
import json
import os
import sys
import time

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view  # noqa: E402
from PIL import Image

REPO = "/home/z/my-project/ps1ai"
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, "scripts"))
from ps1play.api import PS1Play  # noqa: E402

CUE = "/home/z/my-project/emu/games_homebrew/patched/tetrade_lic.cue"
WS = "/home/z/my-project/emu/games_homebrew/ws_r63_tetrade"
EVID = "/home/z/my-project/scratch/r63_tetrade"
OV = {b"beetle_psx_override_bios": b"openbios"}
os.makedirs(EVID, exist_ok=True)
T0 = time.time()
out = {"round": "R63", "phase": "full_loop", "game": "tetrade_lic",
       "started": time.strftime("%Y-%m-%dT%H:%M:%S"), "events": [],
       "pieces": []}
TRACE = open(f"{EVID}/r63_full_loop_trace.jsonl", "w")


def ev(**kw):
    kw["t"] = round(time.time() - T0, 2)
    out["events"].append(kw)
    TRACE.write(json.dumps(kw, default=str) + "\n")
    print(json.dumps(kw)[:200])


def shot(name):
    arr = np.asarray(p.core.frame_rgb())
    Image.fromarray(arr).save(f"{EVID}/{name}.png")
    return arr


# ---- piece shapes (verbatim semantics from the MIT source) -----------
BASE = {
    1: [[0, 0, 0, 0], [1, 1, 1, 1], [0, 0, 0, 0], [0, 0, 0, 0]],  # I
    2: [[0, 0, 0, 0], [0, 1, 1, 0], [0, 1, 1, 0], [0, 0, 0, 0]],  # O
    3: [[1, 0, 0, 0], [1, 1, 1, 0], [0, 0, 0, 0], [0, 0, 0, 0]],  # J
    4: [[0, 0, 1, 0], [1, 1, 1, 0], [0, 0, 0, 0], [0, 0, 0, 0]],  # L
    5: [[1, 1, 0, 0], [0, 1, 1, 0], [0, 0, 0, 0], [0, 0, 0, 0]],  # Z
    6: [[0, 1, 1, 0], [1, 1, 0, 0], [0, 0, 0, 0], [0, 0, 0, 0]],  # S
    7: [[0, 1, 0, 0], [1, 1, 1, 0], [0, 0, 0, 0], [0, 0, 0, 0]],  # T
}
W, H = 10, 20
Wts = {"lh": -4.500158, "epc": 3.418126, "rt": -3.217888,
       "ct": -9.348695, "holes": -7.899265, "wells": -3.385597}


def rot_shape(t, r):
    return np.rot90(np.array(BASE[t], dtype=int), k=-r)


def cells(shape):
    return [(int(r), int(c)) for r, c in zip(*np.nonzero(shape))]


def drop_y(board, shape, x):
    for y in range(H + 1):
        for dr, dc in cells(shape):
            rr, cc = y + dr, x + dc
            if rr >= H or (rr >= 0 and cc >= 0 and board[rr, cc]):
                return y - 1
    return -1


def evaluate(board, shape, x):
    """Dellacherie features for a hypothetical placement."""
    y = drop_y(board, shape, x)
    if y < 0:
        return None, None
    placed = board.copy()
    for dr, dc in cells(shape):
        placed[y + dr, x + dc] = 1
    full = np.flatnonzero((placed == 1).all(axis=1))
    nclear = len(full)
    lh = H - (y + np.mean([dr for dr, _ in cells(shape)]))
    epc = 0
    if nclear:
        for dr, dc in cells(shape):
            if y + dr in set(full.tolist()):
                epc += 1
        epc *= nclear
    # post-clear board: drop the surviving rows, pad empty rows on top
    b = placed
    if nclear:
        keep = [r for r in range(H) if r not in set(full.tolist())]
        b = np.vstack([np.zeros((H - len(keep), W), dtype=int),
                       placed[keep]])
    # row/col transitions (padded with filled borders)
    pad = np.ones((H + 2, W + 2), dtype=int)
    pad[1:H + 1, 1:W + 1] = (b > 0)
    rt = 0
    for r in range(1, H + 1):
        row = pad[r]
        rt += int(np.sum(row[1:W + 1] != row[:W]))
    ct = 0
    for c in range(1, W + 1):
        col = pad[:, c]
        ct += int(np.sum(col[1:H + 1] != col[:H]))
    holes = 0
    for c in range(W):
        col = b[:, c]
        seen = False
        for r in range(H):
            if col[r]:
                seen = True
            elif seen:
                holes += 1
    wells = 0
    for c in range(W):
        r = 0
        while r < H:
            left = b[r, c - 1] if c else 1
            right = b[r, c + 1] if c < W - 1 else 1
            if not b[r, c] and left and right:
                k = 0
                while (r + k < H and not b[r + k, c]
                       and (c == 0 or b[r + k, c - 1])
                       and (c == W - 1 or b[r + k, c + 1])):
                    k += 1
                wells += k * (k + 1) // 2
                r += k
            else:
                r += 1
    score = (Wts["lh"] * lh + Wts["epc"] * epc + Wts["rt"] * rt
             + Wts["ct"] * ct + Wts["holes"] * holes + Wts["wells"] * wells)
    if nclear == 4:
        score += 8.0
    return score, {"lh": round(lh, 2), "epc": epc, "rt": rt, "ct": ct,
                   "holes": holes, "wells": wells, "clear": nclear}


# ---- boot + entry (the sequence proven in probe1) --------------------
p = PS1Play(CUE, workspace=WS, var_overrides=OV)
p.boot()
p.core.run(900, set())
p.core.run(60, set())
p.core.run(120, {"START"})      # title -> menu
p.core.run(240, set())
p.core.run(12, {"B"})           # CROSS on ">Marathon Mode<"
p.core.run(60, set())
p.core.run(4, {"START"})        # begin (tap, not hold!)
p.core.run(280, set())          # 3-2-1 countdown (PAUSE_TIME=180f)
p.core.run(4, {"START"})        # ensure started
p.core.run(120, set())
shot("r63_20_gameplay")
ev(op="entered_marathon")

# ---- locate the TetradeGame struct by signature ----------------------
def find_base(ram):
    """Secondary filter accepts type in 1..7 OR -1 (the transient
    placed/awaiting-respawn value observed live at 0x1FECA0+800)."""
    a4 = ram.view("<i4")
    N = len(a4)
    wins = sliding_window_view(a4, 200)[: N - 590]
    for vmax in (7, 15):
        ok = ((wins >= 0) & (wins <= vmax)).all(axis=1)
        nz = ((wins > 0).sum(axis=1) <= 80)
        cand = np.flatnonzero(ok & nz)
        if not len(cand):
            continue
        c4 = cand * 4
        t_cur = a4[(c4 + 800) // 4]
        t_next = a4[(c4 + 896) // 4]
        lvl = a4[(c4 + 2304) // 4]
        sc = a4[(c4 + 2276) // 4]
        paused = a4[(c4 + 2316) // 4]
        over = a4[(c4 + 2312) // 4]
        m = (((t_cur >= 1) & (t_cur <= 7)) | (t_cur == -1)) \
            & (t_next >= 1) & (t_next <= 7) \
            & (lvl == 0) & (sc == 0) & (paused == 0) & (over == 0)
        hits = c4[m]
        if len(hits):
            return [int(h) for h in hits]
    return []


# retry: the -1 respawn window is transient; re-snapshot until a live
# piece exists (type 1..7) so the primary signature is unambiguous
base = None
for attempt in range(40):
    ram = np.frombuffer(bytes(p.mem.snapshot()), dtype=np.uint8)
    bases = find_base(ram)
    live = [b for b in bases
            if 1 <= int(ram.view("<i4")[(b + 800) // 4]) <= 7]
    if live:
        base = live[0]
        ev(op="struct_base", base=base, hex=hex(base), attempt=attempt,
           all_candidates=len(bases))
        break
    p.core.run(20, set())
if base is None:
    ev(op="verdict", v="BLOCKED_NO_STRUCT", attempts=40,
       last_candidates=len(bases))
    json.dump(out, open(f"{EVID}/r63_full_loop_summary.json", "w"),
              indent=1)
    sys.exit(2)

O_TYPE, O_SHAPE, O_X, O_Y, O_ROT = 800, 804, 868, 872, 880
O_N0, O_SCORE, O_SINGLE, O_DOUBLE, O_TRIPLE, O_TETRADE = 896, 2276, 2280, 2284, 2288, 2292
O_LEVEL, O_OVER, O_PAUSED = 2304, 2312, 2316


def read_state():
    ram = np.frombuffer(bytes(p.mem.snapshot()), dtype=np.uint8)
    a = ram.view("<i4")
    st = {
        "board": a[base // 4: base // 4 + 200].reshape(H, W).copy(),
        "type": int(a[(base + O_TYPE) // 4]),
        "x": int(a[(base + O_X) // 4]),
        "y": int(a[(base + O_Y) // 4]),
        "rot": int(a[(base + O_ROT) // 4]),
        "shape": a[(base + O_SHAPE) // 4:(base + O_SHAPE) // 4 + 16]
                   .reshape(4, 4).copy(),
        "next0": int(a[(base + O_N0) // 4]),
        "score": int(a[(base + O_SCORE) // 4]),
        "single": int(a[(base + O_SINGLE) // 4]),
        "double": int(a[(base + O_DOUBLE) // 4]),
        "triple": int(a[(base + O_TRIPLE) // 4]),
        "tetrade": int(a[(base + O_TETRADE) // 4]),
        "level": int(a[(base + O_LEVEL) // 4]),
        "over": int(a[(base + O_OVER) // 4]),
        "paused": int(a[(base + O_PAUSED) // 4]),
    }
    return st


st0 = read_state()
ev(op="state0", type=st0["type"], x=st0["x"], y=st0["y"],
   rot=st0["rot"], next0=st0["next0"], over=st0["over"],
   filled=int((st0["board"] > 0).sum()))

# ---- the policy loop --------------------------------------------------
MAX_PIECES = 400
t_wall_deadline = T0 + 460
npiece = 0
prev_next = st0["next0"]
while npiece < MAX_PIECES and time.time() < t_wall_deadline:
    st = read_state()
    if st["over"]:
        ev(op="game_over_detected", piece=npiece, score=st["score"],
           single=st["single"], level=st["level"])
        break
    if st["paused"]:
        p.core.run(4, {"START"})
        p.core.run(200, set())
        continue
    if not (1 <= st["type"] <= 7):
        p.core.run(20, set())
        continue
    board = (st["board"] > 0).astype(int)
    # 1-ply over current piece
    best = None
    for r in range(4):
        shape = rot_shape(st["type"], r)
        for x in range(-1, W):
            cc = cells(shape)
            if any(x + dc < 0 or x + dc >= W for _, dc in cc):
                continue
            v, info = evaluate(board, shape, x)
            if v is None:
                continue
            if best is None or v > best[0]:
                best = (v, r, x, info)
    if best is None:
        ev(op="no_placement", piece=npiece)
        break
    v0, r_t, x_t, info = best
    # 2-ply: refine with the NEXT piece (top-8 current placements)
    shorts = []
    for r in range(4):
        shape = rot_shape(st["type"], r)
        for x in range(-1, W):
            cc = cells(shape)
            if any(x + dc < 0 or x + dc >= W for _, dc in cc):
                continue
            v, inf2 = evaluate(board, shape, x)
            if v is None:
                continue
            shorts.append((v, r, x, inf2))
    shorts.sort(reverse=True)
    refined = None
    nb = 0
    for v, r, x, inf2 in shorts[:8]:
        y = drop_y(board, rot_shape(st["type"], r), x)
        if y < 0:
            continue
        b2 = board.copy()
        for dr, dc in cells(rot_shape(st["type"], r)):
            b2[y + dr, x + dc] = 1
        full = np.flatnonzero((b2 == 1).all(axis=1))
        for rr in full:
            b2[rr, :] = 0
        b2 = np.vstack([np.zeros((len(full), W), dtype=int), b2])[:H]
        bn = (b2 > 0).astype(int)
        vn = None
        if 1 <= st["next0"] <= 7:
            for rn in range(4):
                sn = rot_shape(st["next0"], rn)
                for xn in range(-1, W):
                    ccn = cells(sn)
                    if any(xn + dc < 0 or xn + dc >= W for _, dc in ccn):
                        continue
                    vv, _ = evaluate(bn, sn, xn)
                    if vv is not None and (vn is None or vv > vn):
                        vn = vv
        total = v + 0.5 * (vn if vn is not None else 0.0)
        if refined is None or total > refined[0]:
            refined = (total, r, x, inf2, v)
        nb += 1
    _, r_t, x_t, info, v1 = refined
    # ---- execute: rotate CW taps to r_t -------------------------------
    taps_r = 0
    while True:
        st = read_state()
        if st["over"] or st["rot"] == r_t or taps_r >= 4:
            break
        p.core.run(2, {"A"})       # CIRCLE = rotate CW
        p.core.run(6, set())
        taps_r += 1
    # ---- move to x_t ----------------------------------------------------
    taps_m = 0
    while taps_m < 12:
        st = read_state()
        if st["over"] or st["x"] == x_t:
            break
        btn = "RIGHT" if st["x"] < x_t else "LEFT"
        p.core.run(2, {btn})
        p.core.run(11, set())      # moveCooldown = 10
        taps_m += 1
    # ---- hard drop -------------------------------------------------------
    p.core.run(2, {"UP"})
    p.core.run(40, set())
    npiece += 1
    st1 = read_state()
    rec = {"n": npiece, "type": st["type"], "rot": r_t, "x": x_t,
           "v1": round(v1, 2), "info": info,
           "next_promoted": st1["next0"] != prev_next,
           "score": st1["score"], "single": st1["single"],
           "level": st1["level"], "over": st1["over"],
           "filled": int((st1["board"] > 0).sum())}
    out["pieces"].append(rec)
    TRACE.write(json.dumps(rec, default=str) + "\n")
    if rec["next_promoted"] or npiece % 10 == 0:
        print(json.dumps(rec)[:200])
    prev_next = st1["next0"]
    if st1["over"]:
        ev(op="game_over_detected", piece=npiece, score=st1["score"],
           single=st1["single"], level=st1["level"])
        break

ev(op="play_done", pieces=npiece)
shot("r63_21_end_of_play")
stf = read_state()
out["final"] = {k: stf[k] for k in
                ("score", "single", "double", "triple", "tetrade",
                 "level", "over")}
ev(op="final_state", **out["final"])
shot("r63_22_gameover_screen")

# ---- CONTINUE refused with CIRCLE -> menu -> restart -------------------
p.core.run(120, set())
p.core.run(4, {"A"})            # CIRCLE refuses the continue (source 919)
p.core.run(180, set())
shot("r63_23_after_circle")
p.core.run(120, set())
# back to menu/title: restart via the proven entry sequence
p.core.run(4, {"START"})
p.core.run(150, set())
p.core.run(12, {"B"})
p.core.run(60, set())
p.core.run(4, {"START"})
p.core.run(280, set())
st_r = read_state()
fresh = (st_r["score"] == 0 and st_r["single"] == 0
         and st_r["level"] == 0 and not st_r["over"]
         and int((st_r["board"] > 0).sum()) <= 4)
out["restart"] = {"fresh_verified": bool(fresh),
                  "score": st_r["score"], "single": st_r["single"],
                  "level": st_r["level"],
                  "filled": int((st_r["board"] > 0).sum())}
ev(op="restart_check", **out["restart"])
shot("r63_24_fresh_marathon")
p.core.run(200, set())
shot("r63_25_fresh_piece_falling")
p.core.shutdown()

out["verdict"] = "FULL_LOOP_DONE" if (stf["over"] and fresh) else "PARTIAL"
out["finished"] = time.strftime("%Y-%m-%dT%H:%M:%S")
TRACE.close()
json.dump(out, open(f"{EVID}/r63_full_loop_summary.json", "w"), indent=1)
print("VERDICT:", out["verdict"])
