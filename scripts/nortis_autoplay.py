#!/usr/bin/env python3
"""nortis_autoplay.py — rule-based Nortis play session (local,
license-patched image; license status BLOCKED-for-distribution
unchanged).

Nortis boots straight into its field: move LEFT/RIGHT, rotate X,
drop START (controls screen). No RAM map yet (honest OBSERVED-only):
play activity = field-region frame diffs; score/lines = top-left
region hash changes (no OCR claim). One boot per process (H5).
"""
import json
import sys
import time
import zlib

import numpy as np
from PIL import Image

REPO = "/home/z/my-project/ps1ai"
sys.path.insert(0, REPO)
from ps1play.api import PS1Play                                   # noqa

EVID = "/home/z/my-project/emu/games_psx/evidence/nortis_play"
CUE = "/home/z/my-project/emu/games_homebrew/patched/nortis_lic.cue"
# 320x240 frame: playfield = left box (x 8..112, y 8..200);
# score/lines text block = x 120..230, y 28..48
FIELD = (8, 8, 112, 200)
SCORE = (120, 28, 230, 48)


def region(img, box):
    x0, y0, x1, y1 = box
    return img[y0:y1, x0:x1]


def diff(a, b):
    if a is None or b is None:
        return None
    if a.shape != b.shape:
        return None
    return float(np.abs(a.astype(np.int16) - b.astype(np.int16)).mean())


def main():
    out = {"started": time.strftime("%FT%TZ", time.gmtime())}
    p = PS1Play(CUE, workspace="/home/z/my-project/emu/games_psx/ws_nortis_auto")
    p.boot()
    p.wait(420)
    for _ in range(40):
        if bytes(p.mem.snapshot()).count(b"\x00\x41\xff\xff") > 0:
            break
        p.wait(30)
    p.wait(60)
    chunks = 300
    field_prev = region(p.core.frame_rgb(), FIELD)
    score_prev = region(p.core.frame_rgb(), SCORE)
    moves = 0
    score_changes = 0
    field_active = 0
    t0 = time.time()
    for c in range(chunks):
        # rule-based move: alternate left/right taps, rotate sometimes,
        # drop periodically — a crude but real playing policy
        if c % 12 == 11:
            btns = {"START"}                  # drop
        elif c % 4 == 1:
            btns = {"LEFT"}
        elif c % 4 == 3:
            btns = {"RIGHT"}
        elif c % 8 == 2:
            btns = {"X"}                      # rotate
        else:
            btns = set()
        if btns:
            moves += 1
        p.core.run(50, btns)
        p.core.run(10, set())
        img = p.core.frame_rgb()
        if img is None:
            break
        f = region(img, FIELD)
        s = region(img, SCORE)
        d = diff(f, field_prev)
        if d and d > 3.0:
            field_active += 1
        if zlib.crc32(s.tobytes()) != zlib.crc32(score_prev.tobytes()):
            score_changes += 1
            Image.fromarray(img).save(f"{EVID}/auto_score_c{c:03d}.png")
        field_prev, score_prev = f, s
        if c % 50 == 0:
            Image.fromarray(img).save(f"{EVID}/auto_c{c:03d}.png")
    out["chunks"] = chunks
    out["moves"] = moves
    out["field_active_chunks"] = field_active
    out["score_region_changes"] = score_changes
    out["wall_s"] = round(time.time() - t0, 1)
    out["finished"] = time.strftime("%FT%TZ", time.gmtime())
    with open(f"{EVID}/autoplay_report.json", "w") as f:
        json.dump(out, f, indent=1)
    print(json.dumps(out, indent=1))
    try:
        p.core.close()
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
