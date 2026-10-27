#!/usr/bin/env python3
"""r19t1_run4_win.py — Round 19 Poy Poy, Run 4: WIN a round (RETIRE!).

Foundations (measured this round, artifacts in scratch/r19t1_poypoy/):
  - r19_f600.ckpt = fresh round start (timer 01:55, all hearts full,
    HUD baseline hearts [347,352,437,347], mag [0,0,0,0])
  - B tap near a white rock = GRAB (run1/run2); while carrying: hold B +
    aim dirs ~60f then release = CHARGED aimed throw (run3)
  - run3 dress rehearsal (aim RIGHT+UP) -> ball flight -> f~1069: a HUD
    card went hearts=0 + mag=226 and VLM confirms its character vanished
    from the field (prev_d_fly_180_r19run3.png) => RETIRED by our play
  - RETIRE! signature (r18 t48 VLM): the player's HUD card shows
    "RETIRE!" magenta text instead of hearts
      => detector: hearts[q]<=60 and mag[q]>=170 for 3 consecutive ticks
  - RAM screen-position slots (run3, 4-aligned i32; camera follows HARRY
    so 1P is a stable screen anchor ~(20,146)):
      1P (1322744,1322752) 2P (1254204,1254208)
      3P (1971500,1971504) 4P (537076,537084); camera x 657708 (run2)

One beetle boot:
  A. settle + 60f direction holds per direction (restore each) to check
     slot liveness + baseline HUD
  B. closed-loop match (tick=20f):
     - HARRY = 1P RAM slot (live) cross-checked with mask-v2 vision
       (border-connected backdrop removal, scipy) -> found/agree stats
     - opponents = 2P/3P/4P RAM slots gated by their HUD card alive
     - grab nearest white rock; carry -> charge 3 ticks (B+aim toward
       nearest alive opponent; throw 1 uses the proven RIGHT+UP) ->
       release; 8-tick flight cooldown; regrab loop
     - DODGE: opponent with a white ball overhead within 130px -> 1 tick
       perpendicular (away) move
     - RETIRE detect per HUD card; dense PNG capture around carry/throw/
       retire; pruning of early captures on first retire
  C. on first retire: play on up to +30 ticks (more retires = better),
     then 300f tail; stop; keep key PNGs.
"""
import json
import os
import sys
import time

import numpy as np
from PIL import Image
from scipy import ndimage

REPO = "/home/z/my-project/ps1ai"
sys.path.insert(0, REPO)
from ps1play.api import PS1Play                                   # noqa

OUT = "/home/z/my-project/ps1ai/scratch/r19t1_poypoy/run4"
FRAMES = "/home/z/my-project/ps1ai/scratch/r19t1_poypoy/win_frames"
CUE = "/home/z/my-project/emu/games_psx/poy_poy/Poy Poy (USA).cue"
WS = "/home/z/my-project/emu/games_psx/ws_poypoy_menu22"
MATCH = os.path.join(WS, "r19_f600.ckpt")
T0W = time.time()
BUDGET = 310            # hard wall cap for the whole emulator phase
THROW1_AIM = ("RIGHT", "UP")     # proven kill direction from run3
TICK = 20
HARRY_FALLBACK = (20.0, 146.0)
SLOTS = {"1P": (1322744, 1322752), "2P": (1254204, 1254208),
         "3P": (1971500, 1971504), "4P": (537076, 537084)}


def snap(p, name):
    img = p.core.frame_rgb()
    if img is not None and name:
        Image.fromarray(img).save(name)
    return img


def ram(p):
    return np.frombuffer(bytes(p.core.ram[:]), dtype=np.uint8).copy()


def i32(a, off):
    return int(np.frombuffer(a[off:off + 4].tobytes(), dtype="<i4")[0])


# ---------------- vision v2 ----------------
def blobs(mask, minpx, maxpx):
    lab, n = ndimage.label(mask)
    if n == 0:
        return []
    sizes = ndimage.sum_labels(mask, lab, index=np.arange(1, n + 1))
    out = []
    ys_all, xs_all = np.nonzero(mask)
    vals = lab[ys_all, xs_all]
    order = np.argsort(vals, kind="stable")
    bounds = np.searchsorted(vals[order], np.arange(1, n + 2))
    for i in range(n):
        npx = int(sizes[i])
        if not (minpx <= npx <= maxpx):
            continue
        sl = order[bounds[i]:bounds[i + 1]]
        xs, ys = xs_all[sl], ys_all[sl]
        out.append({"n": npx, "cx": float(xs.mean()), "cy": float(ys.mean()),
                    "x0": int(xs.min()), "x1": int(xs.max()),
                    "y0": int(ys.min()), "y1": int(ys.max())})
    return out


def border_removed(mask):
    lab, n = ndimage.label(mask)
    if n == 0:
        return mask
    edge = np.unique(np.concatenate((lab[0], lab[-1], lab[:, 0],
                                     lab[:, -1])))
    edge = edge[edge != 0]
    if len(edge) == 0:
        return mask
    return mask & ~np.isin(lab, edge)


def hud(a):
    H, W = a.shape[:2]
    strip = a[int(H * 0.80):, :, :]
    rs, gs, bs = strip[..., 0], strip[..., 1], strip[..., 2]
    qw = W // 4
    out = []
    for q in range(4):
        rsq = rs[:, q * qw:(q + 1) * qw]
        gsq = gs[:, q * qw:(q + 1) * qw]
        bsq = bs[:, q * qw:(q + 1) * qw]
        red = int(((rsq > 150) & (gsq < 95) & (bsq < 95)).sum())
        mag = int(((rsq > 160) & (bsq > 120) & (gsq < 110) &
                   (bsq <= rsq + 40)).sum())
        out.append({"hearts": red, "mag": mag})
    return out


def see(img, prev_gray):
    a = np.asarray(img, dtype=np.int16)
    H, W = a.shape[:2]
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    band = np.zeros((H, W), bool)
    band[int(H * 0.28):int(H * 0.86), :] = True
    gray = a.mean(2)
    s = {"hud": hud(a)}
    wht = (r > 205) & (g > 205) & (b > 205) & (np.abs(r - b) < 30) & band
    s["rocks"] = blobs(wht, 25, 2200)
    notfloor = ~((np.abs(r - 160) < 30) & (np.abs(g - 184) < 30) &
                 (np.abs(b - 184) < 30))
    sat = (np.maximum(np.maximum(r, g), b) -
           np.minimum(np.minimum(r, g), b)) > 45
    char = border_removed((sat & notfloor) & band)
    s["chars"] = blobs(char, 60, 3000)
    blue = ((b > r + 30) & (b > g + 15) & (b >= 115)) & band & notfloor
    s["harry_cands"] = blobs(border_removed(blue), 40, 4000)
    s["gray"] = gray
    return s


def main():
    os.makedirs(OUT, exist_ok=True)
    os.makedirs(FRAMES, exist_ok=True)
    rep = {"started": time.strftime("%FT%TZ", time.gmtime()),
           "match_ckpt": MATCH, "tick_frames": TICK,
           "policy": "RAM-slot anchored: grab rock -> charge 60f -> aim "
                     "nearest alive opponent -> release; dodge if opp "
                     "carrying near; RETIRE detect via HUD card"}
    log = open(os.path.join(OUT, "ticklog.jsonl"), "w")

    p = PS1Play(CUE, workspace=WS)
    p.boot()
    p.wait(120)

    # ---------- A. baseline + slot liveness holds ----------
    p.load_state(MATCH)
    p.core.run(30, set())
    idle_ram = ram(p)
    idle_img = snap(p, os.path.join(OUT, "w_idle.png"))
    rep["hud_start"] = hud(np.asarray(idle_img, dtype=np.int16))
    rep["slots_idle"] = {k: [i32(idle_ram, xo), i32(idle_ram, yo)]
                         for k, (xo, yo) in SLOTS.items()}
    holds = {}
    for name, btn in (("L", {"LEFT"}), ("R", {"RIGHT"}),
                      ("U", {"UP"}), ("D", {"DOWN"})):
        p.load_state(MATCH)
        p.core.run(30, set())
        p.core.run(60, btn)
        holds[name] = ram(p)
    np.savez_compressed(os.path.join(OUT, "slots.npz"), idle=idle_ram,
                        **{"hold_" + k: v for k, v in holds.items()})
    slot_live = {}
    for k, (xo, yo) in SLOTS.items():
        row = {"idle": rep["slots_idle"][k]}
        for hn, st in holds.items():
            row[hn] = [i32(st, xo), i32(st, yo)]
        row["moved"] = any(row[hn] != row["idle"] for hn in holds)
        slot_live[k] = row
    rep["slot_live"] = slot_live
    print("slot_live:", json.dumps(slot_live))

    # ---------- B. the match ----------
    p.load_state(MATCH)
    p.core.run(30, set())
    f0 = p.core.frames_run
    retired = [False, False, False, False]
    retire_events = []
    consec = [0, 0, 0, 0]
    flash_ticks = []
    tick = 0
    grabs = throws = dodges = harry_hits = 0
    charge_until = -1
    cooldown_until = -1
    thrown1 = False
    first_retire_tick = None
    last_hearts = None
    prev_gray = None
    stop_reason = None
    png_keep = {}          # tick -> png path (captures kept)
    try:
        while True:
            fr = p.core.frames_run
            img = p.core.frame_rgb()
            if img is None:
                stop_reason = "no_frame"
                break
            s = see(img, prev_gray)
            prev_gray = s["gray"]
            h = s["hud"]
            cur = ram(p)
            slot_pos = {k: (i32(cur, xo), i32(cur, yo))
                        for k, (xo, yo) in SLOTS.items()}
            hx, hy = (float(slot_pos["1P"][0]), float(slot_pos["1P"][1]))
            if not (0 <= hx <= 512 and 40 <= hy <= 210):
                hx, hy = HARRY_FALLBACK
            # vision-mask v2 quality metric: find harry blob near anchor
            vcands = s["harry_cands"]
            vpick = None
            if vcands:
                near = [c for c in vcands
                        if (c["cx"] - hx) ** 2 + (c["cy"] - hy) ** 2 < 80 ** 2]
                vpick = (min(near, key=lambda c: (c["cx"] - hx) ** 2 +
                             (c["cy"] - hy) ** 2) if near else None)
            # carry: white blob overlapping/above anchor
            carry = any(abs(rc["cx"] - hx) < 45 and
                        -64 <= (rc["cy"] - hy) <= 12 and rc["n"] > 220
                        for rc in s["rocks"])
            # retire detection
            for q in range(4):
                low = h[q]["hearts"] <= 60 and h[q]["mag"] >= 170
                consec[q] = consec[q] + 1 if low else 0
                if consec[q] == 3 and not retired[q]:
                    retired[q] = True
                    retire_events.append({"tick": tick, "frame": fr,
                                          "card": q + 1, "hud": h[q],
                                          "is_1p": q == 0})
                    print("RETIRE card", q + 1, "tick", tick, "frame", fr)
                    if q != 0 and first_retire_tick is None:
                        first_retire_tick = tick
            # harry hit metric
            if last_hearts is not None and \
                    h[0]["hearts"] < last_hearts[0]["hearts"] * 0.65 and \
                    last_hearts[0]["hearts"] > 60:
                harry_hits += 1
            last_hearts = h
            # center-band white flash (READY!/LUCK BONUS candidates)
            c = np.asarray(img, dtype=np.int16)
            Hc, Wc = c.shape[:2]
            bandc = c[int(Hc * 0.30):int(Hc * 0.62),
                      int(Wc * 0.22):int(Wc * 0.78)]
            wt = int(((bandc[..., 0] > 210) & (bandc[..., 1] > 210) &
                      (bandc[..., 2] > 210)).sum())
            if wt > 2200:
                flash_ticks.append({"tick": tick, "frame": fr, "wt": wt})

            action = set()
            reason = "idle"
            alive = {k: not retired[int(k[0]) - 1] for k in SLOTS}
            opps = []
            for k in ("2P", "3P", "4P"):
                if not alive[k]:
                    continue
                ox, oy = slot_pos[k]
                if 0 <= ox <= 512 and 40 <= oy <= 210:
                    opps.append((k, float(ox), float(oy)))
            dense = (carry or tick <= charge_until or
                     cooldown_until - tick in (0, 1, 2, 3, 4) or
                     first_retire_tick is not None)

            if first_retire_tick is not None and \
                    tick >= first_retire_tick + 30:
                stop_reason = "retire_confirmed_played_on"
                p.core.run(TICK, set())
                tick += 1
                break
            if all(retired[1:4]) and tick >= first_retire_tick + 12:
                stop_reason = "all_opponents_retired"
                p.core.run(TICK, set())
                tick += 1
                break

            if carry and cooldown_until <= tick:
                if charge_until < tick:            # (re)start charge
                    if not thrown1:
                        aim = set(THROW1_AIM)
                        aim_src = "proven_run3"
                    else:
                        best = None
                        for k, ox, oy in opps:
                            d2 = (ox - hx) ** 2 + (oy - hy) ** 2
                            if best is None or d2 < best[0]:
                                best = (d2, k, ox, oy)
                        if best:
                            dx, dy = best[2] - hx, best[3] - hy
                            aim = set()
                            if dx > 14:
                                aim.add("RIGHT")
                            elif dx < -14:
                                aim.add("LEFT")
                            if dy > 12:
                                aim.add("DOWN")
                            elif dy < -12:
                                aim.add("UP")
                            aim_src = "nearest=%s d=(%.0f,%.0f)" % (
                                best[1], dx, dy)
                        else:
                            aim = set(THROW1_AIM)
                            aim_src = "fallback_proven"
                    charge_until = tick + 3           # 3 ticks = 60f
                    reason = "charge_start %s %s" % (sorted(aim), aim_src)
                    rep.setdefault("aim_log", []).append(
                        {"tick": tick, "aim": sorted(aim), "src": aim_src})
                if tick < charge_until:
                    action = {"B"} | set(aim)
                    reason = "charging"
                else:
                    p.core.run(3, set())              # release
                    throws += 1
                    thrown1 = True
                    cooldown_until = tick + 8         # ~150f flight
                    charge_until = -1
                    reason = "release"
            elif not carry:
                dodged = False
                if cooldown_until <= tick:
                    for k, ox, oy in opps:
                        ball = any(abs(rc["cx"] - ox) < 42 and
                                   -70 <= (rc["cy"] - oy) <= 8 and
                                   rc["n"] > 150 for rc in s["rocks"])
                        d2 = (ox - hx) ** 2 + (oy - hy) ** 2
                        if ball and d2 < 130 ** 2:
                            dx, dy = hx - ox, hy - oy
                            if abs(dx) >= abs(dy):
                                action = {"LEFT"} if dx < 0 else {"RIGHT"}
                            else:
                                action = {"UP"} if dy < 0 else {"DOWN"}
                            dodges += 1
                            dodged = True
                            reason = "dodge %s d=%.0f" % (k, d2 ** 0.5)
                            break
                if not dodged:
                    tgt = None
                    for rc in s["rocks"]:
                        d2 = (rc["cx"] - hx) ** 2 + (rc["cy"] - hy) ** 2
                        if tgt is None or d2 < tgt[0]:
                            tgt = (d2, rc)
                    if tgt:
                        rc = tgt[1]
                        dx, dy = rc["cx"] - hx, rc["cy"] - hy
                        if abs(dx) <= 20 and abs(dy) <= 18:
                            p.core.run(2, {"B"})
                            grabs += 1
                            reason = "grab d=(%.0f,%.0f)" % (dx, dy)
                        else:
                            if dx > 12:
                                action.add("RIGHT")
                            elif dx < -12:
                                action.add("LEFT")
                            if dy > 10:
                                action.add("DOWN")
                            elif dy < -10:
                                action.add("UP")
                            reason = "walk rock d=(%.0f,%.0f)" % (dx, dy)
                    else:
                        reason = "no-rock"
            else:
                reason = "carry_cooldown"

            p.core.run(TICK, action)
            row = {"tick": tick, "frame": fr, "hud": h,
                   "harry": [round(hx), round(hy)],
                   "slots": {k: list(v) for k, v in slot_pos.items()},
                   "vision_hit": bool(vpick),
                   "carry": carry, "rocks": len(s["rocks"]),
                   "chars": len(s["chars"]), "wt": wt,
                   "action": sorted(action), "reason": reason,
                   "grabs": grabs, "throws": throws, "dodges": dodges}
            log.write(json.dumps(row, default=str) + "\n")
            if dense or tick % 2 == 0:
                png = os.path.join(FRAMES, "t%04d.png" % tick)
                Image.fromarray(img).save(png)
                png_keep[tick] = png
            tick += 1
            if first_retire_tick is not None:
                # prune early captures: keep every 4th before retire-10
                cut = first_retire_tick - 10
                for t0 in [t for t in png_keep if t < cut]:
                    if t0 % 4 != 0:
                        try:
                            os.remove(png_keep.pop(t0))
                        except OSError:
                            pass
            if time.time() - T0W > BUDGET:
                stop_reason = stop_reason or "wall_budget"
                break
            if fr - f0 > 15000:
                stop_reason = "frame_cap"
                break
        # tail 300f to catch banner/tally
        tail = []
        for k in range(15):
            p.core.run(20, set())
            img = p.core.frame_rgb()
            if img is not None:
                png = os.path.join(FRAMES, "t%04d.png" % (tick + k))
                Image.fromarray(img).save(png)
                png_keep[tick + k] = png
                tail.append({"tick": tick + k,
                             "frame": p.core.frames_run,
                             "hud": hud(np.asarray(img, dtype=np.int16))})
        rep["tail"] = tail[-6:]
    finally:
        img = snap(p, os.path.join(OUT, "w_end.png"))
        rep["end_hud"] = hud(np.asarray(img, dtype=np.int16)) \
            if img is not None else None

    rep["ticks"] = tick
    rep["frames_played"] = p.core.frames_run - f0
    rep["grabs"] = grabs
    rep["throws"] = throws
    rep["dodges"] = dodges
    rep["harry_hits"] = harry_hits
    rep["retire_events"] = retire_events
    rep["retired_cards"] = [i + 1 for i in range(4) if retired[i]]
    rep["flash_ticks"] = flash_ticks[-14:]
    rep["stop_reason"] = stop_reason
    rep["captures_kept"] = len(png_keep)
    rep["wall_s"] = round(time.time() - T0W, 1)
    rep["finished"] = time.strftime("%FT%TZ", time.gmtime())
    with open(os.path.join(OUT, "run4.json"), "w") as f:
        json.dump(rep, f, indent=1, default=str)
    log.close()
    print(json.dumps({k: rep[k] for k in
                      ("ticks", "grabs", "throws", "dodges", "harry_hits",
                       "retire_events", "retired_cards", "stop_reason",
                       "wall_s")}, indent=1, default=str))
    try:
        p.core.close()
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
