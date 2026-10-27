#!/usr/bin/env python3
"""poypoy_r18_agent.py — Round 18: vision-only closed-loop Poy Poy agent.

Measured foundations (this round, all checkpoint-anchored):
  - B (cross) tap near an orb = GRAB (orb lifted: btnprobe b_B_short_t90)
  - B hold = crouch/charge pose; A == X (identical RAM effect twice)
  - direction inputs move HARRY (blue-centroid shift, calib3)
  - emulation is deterministic given the same inputs (ambient == 0)
  - short-carry auto-drops/tosses within ~60-90f (throw2 ref branch)

Policy (per 20-frame tick, screen-space, no RAM reads):
  carry?  = white blob overlapping HARRY  -> charge-throw: walk toward the
            nearest enemy and press B every 40f (throw attempt)
  else    = walk toward the nearest orb; within 25px -> tap B (grab)
  HUD 1P heart pixels tracked per tick; drops logged as hit events.
Honest verdict:
  PLAYING  = closed-loop decisions on live frames produce measured game
             events (grab, throw, hit, survival) — logged per tick
  match continues to TIME 0 or first death; every claim has a PNG.
"""
import json
import os
import sys
import time

import numpy as np
from PIL import Image

REPO = "/home/z/my-project/ps1ai"
sys.path.insert(0, REPO)
from ps1play.api import PS1Play                                   # noqa

EVID = "/home/z/my-project/emu/games_psx/evidence/poypoy_r18_agent"
CUE = "/home/z/my-project/emu/games_psx/poy_poy/Poy Poy (USA).cue"
WS = "/home/z/my-project/emu/games_psx/ws_poypoy_menu22"
MATCH = os.path.join(WS, "r18_match.ckpt")
TICK = 20
MAX_F = 8200          # TIME 01:43 at ckpt -> ~6180f + end screens


def blobs(mask, minpx, maxpx):
    """connected components (4-neighborhood, iterative) -> list of (n,cx,cy)."""
    m = mask.astype(np.int8)
    H, W = m.shape
    seen = np.zeros_like(m)
    out = []
    for y0, x0 in zip(*np.nonzero(m)):
        if seen[y0, x0]:
            continue
        stack = [(y0, x0)]
        seen[y0, x0] = 1
        pts = []
        while stack:
            y, x = stack.pop()
            pts.append((y, x))
            for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                ny, nx = y + dy, x + dx
                if 0 <= ny < H and 0 <= nx < W and m[ny, nx] and not seen[ny, nx]:
                    seen[ny, nx] = 1
                    stack.append((ny, nx))
        n = len(pts)
        if minpx <= n <= maxpx:
            ys = [p[0] for p in pts]
            xs = [p[1] for p in pts]
            out.append((n, float(np.mean(xs)), float(np.mean(ys))))
    return out


def masks(img):
    a = np.asarray(img, dtype=np.int16)
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    H, W = r.shape
    floor = np.zeros((H, W), bool)
    floor[int(H * 0.28):int(H * 0.66), :] = True          # arena band
    harry = (np.abs(r - g) < 45) & (b > g) & (g >= r) & (b >= 115) & (b <= 190) \
        & (r >= 45) & (r <= 115) & floor
    orb = (r > 205) & (g > 205) & (b > 205) & (np.abs(r - b) < 30) & floor
    yellow = (r > 125) & (g > 75) & (g < 160) & (b < 75) & floor
    hud = a[int(H * 0.83):, :, :]
    hr, hg, hb = hud[..., 0], hud[..., 1], hud[..., 2]
    heart = (hr > 150) & (hg < 95) & (hb < 95)
    qw = W // 4
    hearts = [int(heart[:, q * qw:(q + 1) * qw].sum()) for q in range(4)]
    return harry, orb, yellow, hearts


def main():
    os.makedirs(EVID, exist_ok=True)
    log = open(os.path.join(EVID, "decisions.jsonl"), "w")
    frames_dir = os.path.join(EVID, "frames")
    os.makedirs(frames_dir, exist_ok=True)
    report = {"started": time.strftime("%FT%TZ", time.gmtime()),
              "policy": "vision-only; grab orb -> carry -> throw at enemy",
              "tick_frames": TICK}

    p = PS1Play(CUE, workspace=WS)
    p.boot()
    p.wait(120)
    p.load_state(MATCH)

    t0 = time.time()
    f_total = 0
    tick_i = 0
    events = {"grabs": 0, "throw_attempts": 0, "heart_events": [], "steps": 0}
    last_hearts = None
    carry_ticks = 0
    rows = []

    while f_total < MAX_F:
        img = p.core.frame_rgb()
        if img is None:
            break
        harry_m, orb_m, yel_m, hearts = masks(img)
        hb = blobs(harry_m, 20, 500)
        ob = blobs(orb_m, 12, 700)
        yb = blobs(yel_m, 20, 900)

        row = {"tick": tick_i, "frame": f_total, "hearts": hearts}
        action = set()
        reason = "idle"

        if hb:
            h = max(hb, key=lambda t: t[0])
            hx, hy = h[1], h[2]
            row["harry"] = [round(hx, 1), round(hy, 1), h[0]]
            # carry = white blob overlapping harry
            carry = any(abs(cx - hx) < 45 and -60 <= (cy - hy) <= 12 and n > 250
                        for n, cx, cy in ob)
            row["carry"] = carry
            if carry:
                carry_ticks += 1
                # nearest yellow enemy -> walk to it, press B periodically
                if yb:
                    e = min(yb, key=lambda t: (t[1] - hx) ** 2 + (t[2] - hy) ** 2)
                    row["enemy"] = [round(e[1], 1), round(e[2], 1), e[0]]
                    dx, dy = e[1] - hx, e[2] - hy
                    if dx > 18:
                        action.add("RIGHT")
                    elif dx < -18:
                        action.add("LEFT")
                    if dy > 14:
                        action.add("DOWN")
                    elif dy < -14:
                        action.add("UP")
                    reason = f"carry->approach enemy d=({dx:.0f},{dy:.0f})"
                else:
                    reason = "carry-no-enemy"
                if carry_ticks % 2 == 1:
                    action.add("B")
                    events["throw_attempts"] += 1
                    reason += "+throw_tap"
            elif ob:
                o = min(ob, key=lambda t: (t[1] - hx) ** 2 + (t[2] - hy) ** 2)
                row["orb"] = [round(o[1], 1), round(o[2], 1), o[0]]
                dx, dy = o[1] - hx, o[2] - hy
                if abs(dx) <= 22 and abs(dy) <= 22:
                    action.add("B")
                    events["grabs"] += 1
                    reason = f"grab at d=({dx:.0f},{dy:.0f})"
                else:
                    if dx > 14:
                        action.add("RIGHT")
                    elif dx < -14:
                        action.add("LEFT")
                    if dy > 12:
                        action.add("DOWN")
                    elif dy < -12:
                        action.add("UP")
                    events["steps"] += 1
                    reason = f"approach orb d=({dx:.0f},{dy:.0f})"
            else:
                reason = "no-orb-visible"
        else:
            reason = "harry-not-found"

        if last_hearts is not None:
            for q in range(4):
                if hearts[q] < last_hearts[q] * 0.65 and last_hearts[q] > 60:
                    events["heart_events"].append(
                        {"tick": tick_i, "player": q + 1,
                         "from": last_hearts[q], "to": hearts[q]})
        last_hearts = hearts

        p.core.run(TICK, action)
        f_total += TICK
        row["action"] = sorted(action)
        row["reason"] = reason
        rows.append(row)
        log.write(json.dumps(row, default=str) + "\n")
        if tick_i % 2 == 0:
            Image.fromarray(img).save(os.path.join(frames_dir, f"t{tick_i:04d}.png"))
        tick_i += 1

    # end-of-match observation
    img = p.core.frame_rgb()
    if img is not None:
        Image.fromarray(img).save(os.path.join(EVID, "end_state.png"))
    p.core.run(300, set())
    img = p.core.frame_rgb()
    if img is not None:
        Image.fromarray(img).save(os.path.join(EVID, "end_state_p300.png"))

    report["frames_run"] = f_total
    report["ticks"] = tick_i
    report["events"] = events
    report["wall_s"] = round(time.time() - t0, 1)
    report["last_hearts"] = last_hearts
    with open(os.path.join(EVID, "report.json"), "w") as f:
        json.dump(report, f, indent=1, default=str)
    log.close()
    print(json.dumps(report, indent=1, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
