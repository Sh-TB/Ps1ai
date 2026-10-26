#!/usr/bin/env python3
"""nortis_lineclear.py — Issue #6 round 6: Nortis line-clear campaign
with SOURCE-DRIVEN ground truth (upstream jbreckmckye/nortis psx/).

Source facts this script relies on (cloned to scratch/nortis_src):
  - Field: g_field[26][10] of BlockNames enum (int, little-endian),
    WIDTH 10, HEIGHT 26, HIDDEN_ROWS 2 -> 1040 bytes.
  - GameState (7 ints): blockName, blockRotation, clearedLines,
    points, positionX, positionY, playState (PLAY_PLAYING=0,
    PLAY_GAMEOVER=1).
  - Shapes (shapeHexes[8][4] 16-bit): I 0x0F00/0x4444, J 0xE200...,
    standard bit scheme (0x8000 >> (row*4+col)).
  - Spawn: positionX=4 (I:3), positionY=2 (I:1, T:1).
  - pad_getInput(): ONE action/frame; ROTATE=CIRCLE press-edge,
    DROP=CROSS press-edge, RESTART=START press-edge; LEFT/RIGHT fire
    on press edge (btnHeldFor 0 % 15 == 0) then every 15 held frames.
    libretro mapping: PSX CIRCLE=A, PSX CROSS=B.
  - Gravity: game_getSpeed() = 60 - MAX(MIN(1,sets),20)*2 = 20 f/row
    ALWAYS (flipped-args bug in source: level pinned to 20).
  - Line clear: isLineComplete(row) full 10 cols -> cleared++,
    clearedLines += cleared; HUD SCORE = clearedLines, LINES = x12.

Plan: boot license-patched image -> START -> RAM-scan GameState +
g_field (behavioral verification) -> greedy flat-stack policy with
RAM-truth perception (settled field ONLY — active piece is not in
g_field) -> hard drop placements -> clearedLines/points causality.
"""
import argparse
import json
import os
import sys
import time

import numpy as np
from PIL import Image

REPO = "/home/z/my-project/ps1ai"
sys.path.insert(0, REPO)
from ps1play.api import PS1Play                                   # noqa

CUE = "/home/z/my-project/emu/games_homebrew/patched/nortis_lic.cue"
EVID = "/home/z/my-project/ps1ai/scratch/issue6_round6_nortis"
WS = "/home/z/my-project/emu/ws_nortis_lc"

WIDTH, HEIGHT, HIDDEN = 10, 26, 2
FIELD_BYTES = WIDTH * HEIGHT * 4          # 1040 (legacy; unused here)
# --- RELEASE-BINARY GROUND TRUTH (calib3/calib4 evidence) ---
# GameState @ 0x15fb0: 7 u32s [block, rot, clearedLines, points,
# positionX, positionY, playState].  Field array @ 0x15FCC (right
# after the state): rows of 10 u32s (stride 40B); field_row =
# positionY - 2 (two hidden virtual rows); the array holds settled
# cells only near spawn but ALSO tracks the active piece (drawn
# each frame) -> bot always re-reads + verifies plans.
STATE_OFF = 0x15FB0
FIELD_OFF = 0x1615C         # TRUE settled field (calib5/6): changes
                            # ONLY at commit; two copies exist (Q here
                            # and Q+0x410); render array @0x15FCC is
                            # NOT the collision field.
ROWS = 26                   # row = positionY - 2 (2 hidden rows)
VIS_ROWS = 22               # visible band = rows 2..25
SHAPES = {  # blockName -> 4 rotations of 16-bit shape words
    1: (0x0F00, 0x4444, 0x0F00, 0x4444),             # I
    2: (0xE200, 0x44C0, 0x8E00, 0xC880),             # J
    3: (0xE800, 0xC440, 0x2E00, 0x88C0),             # L
    4: (0xCC00, 0xCC00, 0xCC00, 0xCC00),             # O
    5: (0x6C00, 0x8C40, 0x6C00, 0x8C40),             # S
    6: (0x0E40, 0x4C40, 0x4E00, 0x4640),             # T
    7: (0x4C80, 0xC600, 0x4C80, 0xC600),             # Z
}


def log(*a):
    print("[ntc]", *a, file=sys.stderr, flush=True)


def png(p, name):
    rgb = p.core.frame_rgb()
    if rgb is not None:
        Image.fromarray(rgb).save(os.path.join(EVID, f"{name}.png"))
        return f"{name}.png"
    return None


def shape_cells(word):
    """(row, col) cells of a 16-bit shape word."""
    return [(r, c) for r in range(4) for c in range(4)
            if word & (0x8000 >> (r * 4 + c))]


def cells_at(word, x, y):
    """field cells occupied by shape word at (x, y)."""
    return [(y + r, x + c) for (r, c) in shape_cells(word)]


def lands_ok(field, cells):
    for (r, c) in cells:
        if c < 0 or c >= WIDTH or r >= len(field):
            return False
        if r >= 0 and field[r][c]:
            return False
    return True


def drop_row(field, word, x, y0=0):
    """lowest y where the shape at column-x collides (top-anchored)."""
    y = y0
    while lands_ok(field, cells_at(word, x, y + 1)):
        y += 1
    return y


def best_placement(field, block):
    """min (max_height, bumpiness) over rotations x columns."""
    best = None
    for r, word in enumerate(SHAPES[block]):
        cols = [c for (_, c) in shape_cells(word)]
        lo, hi = -min(cols), WIDTH - 1 - max(cols)
        for x in range(lo, hi + 1):
            if not lands_ok(field, cells_at(word, x, 0)):
                continue
            y = drop_row(field, word, x)
            f2 = [row[:] for row in field]
            for (rr, cc) in cells_at(word, x, y):
                f2[rr][cc] = block
            # clear completed rows (source: mutateField_clearLines)
            n_rows = len(f2)
            kept = [row for row in f2 if not all(row)]
            cleared = n_rows - len(kept)
            for _ in range(cleared):
                kept.insert(0, [0] * WIDTH)
            f2 = kept
            hs = []
            for c in range(WIDTH):
                h = 0
                for rr in range(n_rows):
                    if f2[rr][c]:
                        h = n_rows - rr
                        break
                hs.append(h)
            score = (-cleared, max(hs),
                     sum(abs(hs[i] - hs[i + 1])
                         for i in range(WIDTH - 1)))
            if best is None or score < best[0]:
                best = (score, r, x, cleared)
    return best            # (score, rotation, targetX, clears)


def read_state(ram, gs_off=STATE_OFF):
    w = np.frombuffer(ram, dtype="<u4", count=7, offset=gs_off)
    return {"block": int(w[0]), "rot": int(w[1]), "lines": int(w[2]),
            "points": int(w[3]), "x": int(w[4]), "y": int(w[5]),
            "play": int(w[6])}


def read_field(ram):
    """Settled field: 26x10 u32s; row r == virtual y (r+2)."""
    a = np.frombuffer(ram, dtype="<u4", count=ROWS * WIDTH,
                      offset=FIELD_OFF)
    return a.reshape(ROWS, WIDTH).astype(np.int32)


def wait_playing(p, m, J):
    """title -> menu -> gameplay.  playing_seen alone can fire on the
    MENU (stale state), so confirm with a THROWAWAY hard drop: in-game
    it lands a visible piece into the field; on the menu nothing moves.
    Retry START until the field shows a settled cell."""
    for k in range(6):
        p.core.run(60, set())
    p.core.run(1, {"START"})
    confirmed = False
    for k in range(60):
        p.core.run(30, set())
        st = read_state(bytes(p.mem.snapshot()))
        if not (1 <= st["block"] <= 7 and st["play"] == 0
                and 0 <= st["x"] <= 9 and 0 <= st["y"] <= 25):
            if k in (12, 30, 48):
                p.core.run(1, {"START"})
            continue
        if confirmed:
            J({"ev": "playing_seen", "f": k * 30, **st})
            return True
        # first sane state: throwaway hard drop + field check
        p.core.run(2, {"B"})
        p.core.run(60, set())
        fld = read_field(bytes(p.mem.snapshot()))
        if fld[2:].any():                    # a piece really landed
            confirmed = True
            J({"ev": "gameplay_confirmed_by_drop", **st})
        elif k in (12, 30, 48):
            p.core.run(1, {"START"})
    return False


def play(p, m, J, tag, max_pieces=48):
    """RAM-truth greedy play.  Layout is FIXED (calib3/4): state at
    STATE_OFF, field at FIELD_OFF (row = positionY - 2)."""
    pieces = 0
    clears = []
    lines_prev = 0
    pts_prev = 0
    game_over = False
    cycles = 1
    t0 = time.time()
    while pieces < max_pieces and cycles <= 2:
        if time.time() - t0 > 420:
            J({"ev": "WALL", "pieces": pieces})
            break
        ram = bytes(p.mem.snapshot())
        st = read_state(ram)
        if st["play"] != 0:
            J({"ev": "GAME_OVER", "pieces": pieces, "cycle": cycles,
               **st})
            png(p, f"{tag}_gameover_p{pieces}")
            if cycles >= 2:
                game_over = True
                break
            # restart: the proven START accept on the game-over screen
            p.core.run(1, {"START"})
            p.core.run(120, set())
            p.core.run(1, {"START"})
            p.core.run(240, set())
            st2 = read_state(bytes(p.mem.snapshot()))
            if st2["play"] == 0 and st2["lines"] == 0:
                cycles += 1
                lines_prev = 0
                pts_prev = 0
                J({"ev": "RESTART_OK", "cycle": cycles, **st2})
                png(p, f"{tag}_restart_c{cycles}")
                continue
            game_over = True
            break
        field = read_field(ram)
        plan = best_placement(field.tolist(), st["block"])
        if plan is None:
            # no legal placement: force the game to top out (drop the
            # live piece until spawn collision declares game over)
            J({"ev": "NO_PLAN", "piece": pieces, **st})
            for _ in range(8):
                p.core.run(2, {"B"})
                p.core.run(40, set())
                stt = read_state(bytes(p.mem.snapshot()))
                if stt["play"] != 0:
                    break
            continue
        _, rot_want, x_want, clears_want = plan
        word = SHAPES[st["block"]][rot_want]
        y_land = drop_row(field.tolist(), word, x_want)
        plan_cells = sorted(cells_at(word, x_want, y_land))
        # rotation taps (edge = 2f press; CIRCLE suppresses nothing here
        # since taps are sequential)
        taps_r = rot_want if st["block"] != 4 else 0
        for _ in range(taps_r):
            p.core.run(2, {"A"})
            p.core.run(4, set())
        # steering: re-read x each tap
        tap_log = []
        for _ in range(14):
            ram = bytes(p.mem.snapshot())
            st = read_state(ram)
            if st["play"] != 0:
                break
            dx = x_want - st["x"]
            if dx == 0:
                break
            btn = "RIGHT" if dx > 0 else "LEFT"
            p.core.run(2, {btn})
            p.core.run(4, set())
            stt = read_state(bytes(p.mem.snapshot()), )
            tap_log.append(stt["x"])
        # hard drop (2f CROSS edge = one DROP action)
        pre_field = read_field(bytes(p.mem.snapshot()))
        st_pre2 = read_state(bytes(p.mem.snapshot()))
        p.core.run(2, {"B"})
        p.core.run(24, set())
        ram = bytes(p.mem.snapshot())
        st2 = read_state(ram)
        pieces += 1
        # ---- plan verification: diff fields -> actual new cells ----
        field2 = read_field(ram)
        new_cells = sorted((int(r), int(c)) for r, c in
                           zip(*np.nonzero(field2 != pre_field)))
        delta = [(r, c) for (r, c) in plan_cells
                 if field2[r][c] != field[r][c]]
        J({"ev": "PIECE", "n": pieces, "block": st["block"],
           "spawn_x": st["x"], "rot": rot_want, "x_want": x_want,
           "x_at_drop": st_pre2["x"], "y_at_drop": st_pre2["y"],
           "taps": tap_log,
           "landed": new_cells, "plan": sorted(plan_cells),
           "plan_hits": len(delta), "plan_size": len(plan_cells),
           "lines": st2["lines"], "points": st2["points"]})
        if st2["lines"] > lines_prev:
            d = st2["lines"] - lines_prev
            clears.append({"piece": pieces, "cleared": d,
                           "lines": st2["lines"],
                           "points": st2["points"],
                           "planned": clears_want})
            J({"ev": "LINE_CLEAR", **{k: st2[k] for k in
                                      ("lines", "points")},
               "delta": d, "piece": pieces, "planned": clears_want})
            png(p, f"{tag}_CLEAR_p{pieces}_d{d}")
            p.core.run(30, set())
            png(p, f"{tag}_CLEAR_after_p{pieces}")
            lines_prev = st2["lines"]
            pts_prev = st2["points"]
        elif st2["points"] != pts_prev:
            pts_prev = st2["points"]
        if pieces % 8 == 0:
            png(p, f"{tag}_p{pieces}")
            log(f"piece {pieces}: lines={st2['lines']} "
                f"points={st2['points']}")
            fh = []
            for c in range(WIDTH):
                h = 0
                for rr in range(2, ROWS):
                    if field2[rr][c]:
                        h = ROWS - rr
                        break
                fh.append(h)
            J({"ev": "FIELD_DUMP", "piece": pieces,
               "heights": fh,
               "rows": ["".join(str(int(v)) if v else "."
                                for v in row)
                        for row in field2]})
    J({"ev": "PLAY_done", "pieces": pieces, "clears": clears,
       "lines": lines_prev, "points": pts_prev,
       "game_over": game_over, "cycles": cycles})
    return {"pieces": pieces, "clears": clears, "lines": lines_prev,
            "points": pts_prev, "game_over": game_over,
            "cycles": cycles}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", type=int, default=1)
    ap.add_argument("--pieces", type=int, default=48)
    args = ap.parse_args()
    os.makedirs(EVID, exist_ok=True)
    tag = f"lc{args.run}_{time.strftime('%H%M%S')}"
    jf = open(os.path.join(EVID, f"{tag}.jsonl"), "w")

    def J(ev):
        jf.write(json.dumps(ev, default=str) + "\n")
        jf.flush()

    t0 = time.time()
    p = PS1Play(CUE, workspace=WS)
    p.boot()
    p.wait(420)
    for _ in range(40):
        if bytes(p.mem.snapshot()).count(b"\x00\x41\xff\xff") > 0:
            break
        p.wait(30)
    J({"ev": "boot", "run": args.run})
    log(f"=== nortis lineclear run {args.run}: booted ===")
    ok = wait_playing(p, p.mem, J)
    J({"ev": "play_state", "ok": ok})
    if not ok:
        log("did not reach gameplay")
        png(p, f"{tag}_notplaying")
        return 1
    png(p, f"{tag}_entry")
    rec = play(p, p.mem, J, tag, max_pieces=args.pieces)
    out = {"run": args.run, "started": time.strftime("%FT%TZ",
                                                     time.gmtime()),
           "play": rec, "wall_s": round(time.time() - t0, 1)}
    with open(os.path.join(EVID, f"report_{tag}.json"), "w") as f:
        json.dump(out, f, indent=1, default=str)
    J({"ev": "RUN_DONE", **out})
    jf.close()
    log(f"RUN {tag}: pieces={rec['pieces'] if rec else None} "
        f"clears={len(rec['clears']) if rec else '?'} "
        f"lines={rec['lines'] if rec else '?'} wall={out['wall_s']}s")
    try:
        p.core.close()
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
