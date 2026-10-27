#!/usr/bin/env python3
"""r21-t5 run 4 — ONE continuous session, no restores past any confirm gate.

Run-3 lesson: restoring a save state while the game streams CD data (match
loading screen: static artwork + progress bar, RAM churning) freezes the
load forever. Run-2 lesson: the full path is
  title(BATTLE MANIA) --START--> AIR HOCKEY!! menu --B/A-->
  GAME SELECT --confirm--> PLAYER SELECT --A--> load --> MATCH.
So this run walks the whole path in one boot, VLM-verifies each gate,
waits out the match load WITHOUT save/restore, then runs the paddle hunt
and goal attempt inline (states are saved for posterity but never loaded
after the confirm).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time

import numpy as np
from PIL import Image

sys.path.insert(0, "/home/z/my-project/ps1ai/scripts")
import r21t5_airhockey_causality as m                      # noqa: E402
from ps1play.api import PS1Play                            # noqa: E402

R4 = {"task": "r21t5-run4", "started": time.strftime("%Y-%m-%dT%H:%M:%SZ")}


def log(*a):
    print("[r21t5-r4]", *a, file=sys.stderr, flush=True)


def classify(p, tag, prompt=None):
    m.png(p, f"r4_{tag}")
    vtxt = m.vlm([os.path.join(m.OUT, f"r4_{tag}.png")],
                 prompt or ("PS1 game screen. Reply EXACTLY: TYPE=<LIVE_MATCH|"
                            "MENU|LOADING_BLACK>; DETAIL=<visible text/score/"
                            "highlighted entry, <=15 words>"), tag)
    t = vtxt.upper()
    if "LIVE_MATCH" in t:
        typ = "LIVE_MATCH"
    elif "BLACK" in t or "LOADING" in t:
        typ = "LOADING_BLACK"
    elif "MENU" in t:
        typ = "MENU"
    else:
        typ = "UNKNOWN"
    log(f"  {tag}: {typ} :: {vtxt[:110]}")
    return typ, vtxt


def confirm(p, btn, wait=400, tag=""):
    p.core.run(3, {btn})
    m.rel(p, wait - 3)
    return classify(p, f"gate{tag}_{btn}")


def wait_live(p, max_ms=2000, tag="load"):
    """Wait for the match WITHOUT any restore. Returns (ok, last vlm)."""
    waits = 0
    vtxt = ""
    while waits * 300 < max_ms:
        m.rel(p, 300)
        m.gifcap(p, 2)
        typ, vtxt = classify(p, f"{tag}_{waits}")
        R4.setdefault("load_waits", []).append({"w": waits, "type": typ,
                                                "vlm": vtxt[:160]})
        if typ == "LIVE_MATCH" or m.looks_like_gameplay(vtxt):
            return True, vtxt
        waits += 1
    return False, vtxt


# ---------------------------------------------------------------- P4' --
def paddle_hunt(p):
    rams, grays, segs = [], [], []
    plan = ([("idle", None)] * 5 + [("LEFT", "LEFT")] * 4 +
            [("idle", None)] * 5 + [("RIGHT", "RIGHT")] * 4 +
            [("idle", None)] * 4)
    for t, btn in plan:
        p.core.run(5, {btn} if btn else set())
        rams.append(p.mem.snapshot())
        grays.append(m.gray(p.core.frame_rgb()).astype(np.float32))
        segs.append(t)
    grays = np.stack(grays)
    dif = np.abs(grays[1:] - grays[:-1]) > 18
    frac_bottom = float(dif[:, 120:, :].sum() / max(dif.sum(), 1))
    lo_row, hi_row = (120, 240) if frac_bottom >= 0.5 else (0, 120)
    blob_cx = []
    for mm0 in dif:
        mm = mm0.copy()
        mm[:lo_row, :] = False
        mm[hi_row:, :] = False
        blob_cx.append(float(np.nonzero(mm)[1].mean()) if mm.sum() > 8
                       else np.nan)
    cx = np.nan_to_num(np.array(blob_cx))

    def hunt(series, aligned):
        d = np.diff(series, axis=0)
        mi = [i for i, s in enumerate(segs[1:]) if s in ("LEFT", "RIGHT")]
        ii = [i for i, s in enumerate(segs[1:]) if s == "idle"]
        li = [i for i in mi if segs[i + 1] == "LEFT"]
        ri = [i for i in mi if segs[i + 1] == "RIGHT"]
        aL = np.abs(d[mi]).max(axis=0) if mi else 0
        aI = np.abs(d[ii]).max(axis=0) if ii else 0
        sL = d[np.array(li)].sum(axis=0) if li else 0
        sR = d[np.array(ri)].sum(axis=0) if ri else 0
        opp = (np.sign(sL) != np.sign(sR)) & (np.abs(sL) >= 2) \
            & (np.abs(sR) >= 2)
        rng = series.max(axis=0) - series.min(axis=0)
        cands = np.nonzero((aL <= 512) & (aI <= 16) & opp & (rng < 8192))[0]
        if not len(cands):
            return []
        sub = series[:, cands].astype(np.float64)
        y = cx - cx.mean()
        xs = sub[1:]
        xc = xs - xs.mean(axis=0)
        num = (xc * y[:, None]).mean(axis=0)
        den = xs.std(axis=0) * (y.std() + 1e-9)
        corr = np.divide(num, den, out=np.zeros_like(num), where=den > 1e-9)
        out = []
        for i in np.argsort(-np.abs(corr))[:20]:
            o = int(cands[i])
            out.append({"off": o * aligned,
                        "hex": hex(0x80000000 + o * aligned),
                        "corr": round(float(corr[i]), 3),
                        "first": int(series[0, o]), "last": int(series[-1, o])})
        return out

    s16 = np.stack([r.view("<i2").astype(np.int32) for r in rams])
    s8 = np.stack([r.astype(np.int32) for r in rams])
    c16, c8 = hunt(s16, 2), hunt(s8, 1)
    R4["hunt"] = {"motion_frac_bottom": round(frac_bottom, 3),
                  "u16le_top": c16[:10], "u8_top": c8[:10]}
    log("  hunt u16LE:", [(c["hex"], c["corr"]) for c in c16[:5]])
    log("  hunt u8  :", [(c["hex"], c["corr"]) for c in c8[:5]])
    pick = next((c for c in c16 + c8 if abs(c["corr"]) > 0.6), None)
    R4["pick"] = pick
    if not pick:
        return {"ok": False}
    # inline bidirectional verify (NO restore)
    rd, le = pick["off"], pick in c16

    def read():
        ram = p.mem.ram
        return int(ram.view("<i2")[rd // 2]) if le else int(ram[rd])

    v0 = read()
    p.core.run(15, {"LEFT"})
    v_left, fr_left = read(), p.core.frame_rgb()
    m.rel(p, 60)
    p.core.run(15, {"RIGHT"})
    v_right, fr_right = read(), p.core.frame_rgb()
    Image.fromarray(fr_left).save(os.path.join(m.OUT, "p4_left_held.png"))
    Image.fromarray(fr_right).save(os.path.join(m.OUT, "p4_right_held.png"))
    vtxt = m.vlm([os.path.join(m.OUT, "p4_left_held.png"),
                  os.path.join(m.OUT, "p4_right_held.png")],
                 "Two PS1 air-hockey frames (img1 LEFT held 15f, img2 RIGHT "
                 "held 15f). <=30 words: did the player paddle move between "
                 "them and which way? Does the puck/score differ?", "p4_pad")
    R4["paddle_vlm"] = vtxt[:250]
    ok = (v_left != v_right)
    log(f"  verify {pick['hex']} {v0} ->L {v_left} ->R {v_right} ok={ok}")
    return {"ok": ok, "addr": pick["hex"], "dtype": "u16LE" if le else "u8",
            "start": v0, "after_LEFT": v_left, "after_RIGHT": v_right}


# --------------------------------------------------------------- P4b' --
def goal_attempt(p):
    png_setup = m.png(p, "p4b_setup")
    desc = m.vlm([png_setup], "PS1 air-hockey frame, <=40 words: (1) player "
                 "paddle color, (2) CPU paddle color, (3) puck color, (4) "
                 "which side top/bottom is the CPU goal, (5) exact "
                 "scoreboard text.", "p4b_desc")
    log("  desc:", desc[:180])
    t = desc.lower()
    cpu_top = "top" in t
    push_btn = "UP" if cpu_top else "DOWN"
    colors = [rgb for name, rgb in
              (("white", (235, 235, 235)), ("red", (200, 40, 40)),
               ("yellow", (220, 200, 60)), ("orange", (230, 140, 40)),
               ("black", (30, 30, 30)), ("dark", (30, 30, 30)),
               ("blue", (40, 60, 200)), ("green", (40, 170, 60)))
              if name in t] or [(235, 235, 235)]
    R4["p4b_desc"] = desc[:300]
    prev = [None, None]
    s_start = p.mem.snapshot()
    goal = {"attempted": True, "bursts": [], "goal": False}

    def puck_xy(fr):
        a = fr.astype(np.int32)
        best = None
        for rgb in colors:
            mm = ((a[:, :, 0] - rgb[0]) ** 2 + (a[:, :, 1] - rgb[1]) ** 2 +
                  (a[:, :, 2] - rgb[2]) ** 2) < 2500
            if 30 < mm.sum() < 4000:
                ys, xs = np.nonzero(mm)
                cand = (float(xs.mean()), float(ys.mean()), int(mm.sum()))
                if best is None or cand[2] > best[2]:
                    best = cand
        if best and prev[0] is not None and (
                abs(best[0] - prev[0]) > 200 or abs(best[1] - prev[1]) > 120):
            return (prev[0], prev[1])
        if best:
            prev[0], prev[1] = best[0], best[1]
        return (best[0], best[1]) if best else None

    for burst in range(10):
        pxy = puck_xy(p.core.frame_rgb())
        acted = None
        if pxy:
            dx = pxy[0] - 128
            if abs(dx) > 10:
                acted = "LEFT" if dx < 0 else "RIGHT"
                p.core.run(4, {acted})
                m.gifcap(p, 2)
            else:
                extra = ("LEFT" if dx < -4 else "RIGHT" if dx > 4 else None)
                btns = {push_btn} | ({extra} if extra else set())
                acted = push_btn + (("+" + extra) if extra else "")
                p.core.run(10, btns)
                m.gifcap(p, 2)
        else:
            acted = push_btn
            p.core.run(8, {push_btn})
            m.gifcap(p, 2)
        m.rel(p, 24)
        if burst % 2 == 1:
            fp = m.png(p, f"p4b_burst{burst}")
            vtxt = m.vlm([fp], "PS1 air-hockey frame. <=20 words: exact "
                         "scoreboard numbers now? Any goal celebration or "
                         "announcement text visible?", f"p4b_b{burst}")
            goal["bursts"].append({"burst": burst, "acted": acted,
                                   "puck": pxy and [round(pxy[0]),
                                                    round(pxy[1])],
                                   "vlm": vtxt[:160]})
            log(f"  b{burst} acted={acted} puck={pxy} :: {vtxt[:100]}")
            if any(k in vtxt.lower() for k in
                   ("goal", "1-0", "0-1", "1 - 0", "0 - 1", "celebrat")):
                d = p.mem.snapshot().astype(np.int16) - \
                    s_start.astype(np.int16)
                inc = np.nonzero(d == 1)[0]
                goal["ram_plus1_words"] = [hex(0x80000000 + int(o))
                                           for o in inc[:16]]
                if len(inc):
                    goal.update(goal=True, goal_burst=burst)
                    m.png(p, "p4b_goal_candidate")
                    log("  GOAL anchored", goal["ram_plus1_words"][:4])
                    break
        m.gifcap(p, 2)
    d = p.mem.snapshot().astype(np.int16) - s_start.astype(np.int16)
    inc = np.nonzero(d == 1)[0]
    goal["ram_plus1_final"] = [hex(0x80000000 + int(o)) for o in inc[:16]]
    return goal


def main():
    t0 = time.time()
    p = PS1Play(m.CUE, core=m.CORE, workspace=m.WS, var_overrides=m.OV)
    info = p.boot()
    log("boot", {k: info.get(k) for k in ("serial", "ram_bytes")})
    # 1) title
    p.core.run(2000)
    m.png(p, "r4_title")
    p.save_state("title_r4")
    # 2) START -> AIR HOCKEY!! menu
    typ, vtxt = confirm(p, "START", 300, "m0")
    R4["g1"] = {"btn": "START", "vlm": vtxt[:200]}
    if typ != "LIVE_MATCH":
        # 3) CROSS confirm -> GAME SELECT
        typ, vtxt = confirm(p, "B", 500, "m1")
        R4["g2"] = {"btn": "B(CROSS)", "vlm": vtxt[:200]}
        # 4) if GAME SELECT still showing a menu -> confirm again
        if typ == "MENU" and ("GAME" in vtxt.upper() and "SLIDER" in
                              vtxt.upper() or "SELECT" in vtxt.upper()):
            for b in ("B", "A", "START", "UP"):
                typ, vtxt = confirm(p, b, 400, f"m2_{b}")
                R4.setdefault("g3", []).append({"btn": b, "vlm": vtxt[:200]})
                if typ == "LIVE_MATCH" or m.looks_like_gameplay(vtxt):
                    break
                if "PLAYER" in vtxt.upper():
                    break
        # 5) PLAYER SELECT -> CIRCLE confirm -> load -> match
        if typ != "LIVE_MATCH":
            typ, vtxt = confirm(p, "A", 300, "m3")
            R4["g4"] = {"btn": "A(CIRCLE)", "vlm": vtxt[:200]}
            ok, vtxt = wait_live(p, 2100, "load")
            R4["load_ok"] = ok
    else:
        R4["load_ok"] = True
    live = R4.get("load_ok") or typ == "LIVE_MATCH"
    R4["live"] = bool(live)
    if live:
        m.rel(p, 60)
        m.png(p, "p4_game_entry")
        p.save_state("game_r4")       # saved for posterity, NEVER restored
        R4["paddle"] = paddle_hunt(p)
        if R4["paddle"].get("ok"):
            R4["goal"] = goal_attempt(p)
    R4["finished"] = time.strftime("%Y-%m-%dT%H:%M:%SZ")
    R4["wall_s"] = round(time.time() - t0, 1)
    json.dump(R4, open(os.path.join(m.OUT, "run4_log.json"), "w"),
              indent=1, default=str)
    log("DONE", R4.get("live"), R4.get("paddle"), R4.get("goal"))


if __name__ == "__main__":
    main()
