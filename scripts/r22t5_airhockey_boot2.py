#!/usr/bin/env python3
"""r22t5 air_hockey BOOT 2 — calibration + proving run in ONE boot (2 of 3).

Order inside this single boot (nothing is ever written to game RAM):
  G   boot -> title -> FULL LEGAL gate walk (r21t5-proven sequence):
        START -> CROSS -> [PLAYER SELECT confirm] -> CIRCLE -> wait load
        every gate VLM-gated; no savestate restores inside the walk
        (run-3 lesson: restore during CD streaming freezes the load).
  S   at LIVE_MATCH: save_state("r22_match") (posterity) + VLM scene card.
  A   paddle pin: LEFT 120f / idle 90f / RIGHT 120f / idle 60f, per-3f
      sampling of u16LE words 0x800A1480..0x800A14A0 (+raw bytes) with
      same-moment motion centroids of BOTH halves. Selection: responds
      only during holds (idle-stable), anti-symmetric sL/sR, clamps both
      edges; VLM two labeled held-frames corroborate displacement.
  B   puck hunt: 240f passive, block-wise u16LE corr vs screen puck
      centroid (black mask) -> puck x/y candidates.
  C   closed loop: puck x/y from RAM -> paddle target -> press-and-hold
      LEFT/RIGHT to track -> strike (UP) when aligned. Continuous +1 RAM
      score scan every 3f across the whole match; deflection = puck vx
      sign flip while tracking with |paddle-puck| small; goal = score
      delta + VLM scoreboard. Concede mode (hold far edge) if nothing
      lands by burst 40, to anchor the score word through a CPU goal.
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
import r22t5_airhockey_calib as C                          # noqa: E402
from ps1play.api import PS1Play                            # noqa: E402

OUT = C.OUT
R = {"task": "r22t5-boot2", "started": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
     "phases": {}}
WORDS = list(range(0x800A1480, 0x800A14A2, 2))   # struct neighborhood


def log(*a):
    print("[r22t5-b2]", *a, file=sys.stderr, flush=True)


def jlog():
    json.dump(R, open(os.path.join(OUT, "boot2_log.json"), "w"), indent=1,
              default=str)


def ev(text):
    with open(os.path.join(OUT, "evidence.md"), "a") as f:
        f.write(text.rstrip("\n") + "\n")


def read_words(p):
    ram = p.mem.ram
    return {hex(a): C.u16le(ram, a - 0x80000000) for a in WORDS}


def sample(p, prev_gray):
    """One 3f tick: word row + dual-half motion centroids."""
    row = read_words(p)
    row["raw88"] = bytes(bytearray(
        p.mem.ram[0xA1488:0xA1490])).hex(" ")
    g = C.gray(p.core.frame_rgb())
    for half in ("top", "bottom"):
        mc = C.motion_centroid(g, prev_gray, half)
        row[f"mc_{half}"] = None if mc is None else round(mc[0], 1)
        row[f"mn_{half}"] = 0 if mc is None else mc[2]
        row[f"mcy_{half}"] = None if mc is None else round(mc[1], 1)
    return row, g


# ------------------------------------------------------------------ gates --
GATE_PROMPT = ("PS1 game screen. Reply EXACTLY: TYPE=<LIVE_MATCH|VS|MENU|"
               "LOADING_BLACK>; DETAIL=<visible text/highlight/score, "
               "<=15 words>")


def gate_png(p, tag):
    fp = C.png(p, tag)
    txt = C.vlm([fp], GATE_PROMPT, tag)
    t = txt.upper()
    if "LIVE_MATCH" in t or "FIGHT" in t or "GO THUNDER" in t:
        typ = "LIVE_MATCH"
    elif "LOADING" in t or "BLACK" in t:
        typ = "LOADING_BLACK"
    elif "VS" in t:
        typ = "VS"
    elif "MENU" in t or "SELECT" in t or "GAME" in t:
        typ = "MENU"
    else:
        typ = "UNKNOWN"
    log(f"  gate {tag}: {typ} :: {txt[:110]}")
    return typ, txt


def confirm(p, btn, wait, tag):
    p.core.run(3, {btn})
    C.rel(p, wait - 3)
    return gate_png(p, f"b2_gate_{tag}")


def wait_live(p, max_ms=2400, tag="load"):
    waits = 0
    txt = ""
    while waits * 300 < max_ms:
        C.rel(p, 300)
        C.gifcap(p, 2)
        typ, txt = gate_png(p, f"b2_{tag}_{waits}")
        R["phases"].setdefault("gates", []).append(
            {"w": waits, "type": typ, "vlm": txt[:160]})
        if typ == "LIVE_MATCH":
            return True, txt
        waits += 1
    return False, txt


def gate_walk(p):
    """title -> START -> CROSS -> player select -> CIRCLE -> load."""
    p.core.run(2000)
    fp = C.png(p, "b2_title")
    txt = C.vlm([fp], "PS1 screen <=20 words: exact title text and any "
                      "menu/highlight visible.", "b2_title")
    R["phases"]["title_vlm"] = txt[:200]
    ev(f"### Boot 2 gate walk ({time.strftime('%H:%M:%S')})\n- title: "
       f"{txt[:150]}")
    log("title:", txt[:120])
    typ, txt = confirm(p, "START", 300, "start")          # -> AIR HOCKEY!!
    ev(f"- START -> {txt[:120]}")
    if typ != "LIVE_MATCH":
        typ, txt = confirm(p, "B", 500, "cross")          # -> PLAYER SELECT
        ev(f"- CROSS -> {txt[:120]}")
        if "PLAYER" not in txt.upper() and typ != "LIVE_MATCH":
            for b in ("A", "B", "START"):
                typ, txt = confirm(p, b, 400, f"m2_{b}")
                ev(f"- {b} -> {txt[:120]}")
                if "PLAYER" in txt.upper() or typ == "LIVE_MATCH":
                    break
    if typ != "LIVE_MATCH":
        typ, txt = confirm(p, "A", 300, "circle")         # confirm + load
        ev(f"- CIRCLE -> {txt[:120]}")
    if typ == "LIVE_MATCH":
        return True, txt
    ok, txt = wait_live(p, 2400, "load")                  # NO restore
    ev(f"- load_ok={ok}: {txt[:120]}")
    return ok, txt


# ------------------------------------------------------------------- pin --
def analyze_pin(samples):
    """Pick our paddle word: idle-stable + anti-symmetric holds + clamps."""
    segs = [s["seg"] for s in samples]
    arr = {k: np.array([s[k] for s in samples], np.float64)
           for k in samples[0] if k.startswith("0x")}
    d = {k: np.diff(v) for k, v in arr.items()}
    mi = [i for i, s in enumerate(segs[1:]) if s in ("LEFT", "RIGHT")]
    ii = [i for i, s in enumerate(segs[1:]) if s == "idle"]
    li = [i for i in mi if segs[i + 1] == "LEFT"]
    ri = [i for i in mi if segs[i + 1] == "RIGHT"]
    out = []
    for k, dv in d.items():
        idle_max = float(np.abs(dv[ii]).max()) if ii else 999.0
        sL = float(dv[li].sum()) if li else 0.0
        sR = float(dv[ri].sum()) if ri else 0.0
        out.append({"word": k, "idle_max": round(idle_max, 1),
                    "sL": round(sL, 1), "sR": round(sR, 1),
                    "rng": round(float(arr[k].max() - arr[k].min()), 1),
                    "first": int(arr[k][0]), "last": int(arr[k][-1])})
    out.sort(key=lambda r: -min(abs(r["sL"]), abs(r["sR"]))
             * (1.0 if r["idle_max"] <= 4 else 0.0))
    return out, arr


def phase_pin(p, scene):
    half = "bottom" if "bottom" in scene.lower() else "top"
    R["phases"]["pin"] = {"our_half": half, "samples": []}
    C.rel(p, 60)
    plan = ([("idle", None)] * 8 +
            [("LEFT", "LEFT")] * 40 +
            [("idle", None)] * 30 +
            [("RIGHT", "RIGHT")] * 40 +
            [("idle", None)] * 20)
    prev_gray = C.gray(p.core.frame_rgb())
    left_fr = right_fr = None
    for tag, btn in plan:
        p.core.run(3, {btn} if btn else set())
        C.gifcap(p, 3)
        row, prev_gray = sample(p, prev_gray)
        row["seg"] = tag
        R["phases"]["pin"]["samples"].append(row)
        if tag == "LEFT" and btn:
            left_fr = p.core.frame_rgb()
        if tag == "RIGHT" and btn:
            right_fr = p.core.frame_rgb()
    Image.fromarray(left_fr).save(os.path.join(OUT, "b2_left_held.png"))
    Image.fromarray(right_fr).save(os.path.join(OUT, "b2_right_held.png"))
    vtxt = C.vlm([os.path.join(OUT, "b2_left_held.png"),
                  os.path.join(OUT, "b2_right_held.png")],
                 "Two PS1 air-hockey frames (img1 = LEFT held 120f, img2 = "
                 "RIGHT held 120f). <=40 words: did the PLAYER paddle change "
                 "horizontal position and which way? Did the puck move?",
                 "b2_pin")
    R["phases"]["pin"]["vlm"] = vtxt[:400]
    log("pin vlm:", vtxt[:200])

    ranked, arr = analyze_pin(R["phases"]["pin"]["samples"])
    R["phases"]["pin"]["ranked"] = ranked[:10]

    # clamp tests on the best candidate (top ranked by anti-sym+idle-stable)
    best = None
    for r in ranked:
        if r["idle_max"] <= 4 and min(abs(r["sL"]), abs(r["sR"])) >= 24 \
                and np.sign(r["sL"]) != np.sign(r["sR"]):
            best = int(r["word"], 16)
            break
    if best is None and ranked:
        best = int(ranked[0]["word"], 16)
    R["phases"]["pin"]["best_word"] = hex(best) if best else None
    clamp = {}
    if best:
        off = best - 0x80000000
        for btn in ("LEFT", "RIGHT"):
            C.rel(p, 20)
            last, stable, held = None, 0, 0
            while held < 420 and stable < 45:
                p.core.run(3, {btn})
                held += 3
                v = C.u16le(p.mem.ram, off)
                if last is not None and v == last:
                    stable += 3
                else:
                    stable = 0
                last = v
            fp = C.png(p, f"b2_clamp_{btn}")
            clamp[btn] = {"held_f": held, "final": last, "stable_f": stable,
                          "png": os.path.basename(fp)}
            log(f"clamp {btn}: {clamp[btn]}")
            C.rel(p, 30)
        vtxt2 = C.vlm([clamp["LEFT"]["png"] and os.path.join(
            OUT, clamp["LEFT"]["png"]),
            clamp["RIGHT"]["png"] and os.path.join(OUT, clamp["RIGHT"]["png"])],
            "Two PS1 air-hockey frames: img1 = paddle held to its LEFT "
            "clamp, img2 = RIGHT clamp. <=30 words: is the player paddle at "
            "the left edge in img1 and right edge in img2?", "b2_clamp")
        clamp["vlm"] = vtxt2[:300]
        log("clamp vlm:", vtxt2[:180])
    R["phases"]["pin"]["clamp"] = clamp
    jlog()
    return best, clamp, half


# ------------------------------------------------------------------ puck --
def phase_puck(p, puck_colors, dur=240, step=2):
    C.rel(p, 20)
    rams, cxs, cys = [], [], []
    prev = [None, None]
    for i in range(dur // step):
        p.core.run(step, set())
        C.gifcap(p, 4)
        rams.append(p.mem.snapshot())
        cx, cy = C.puck_screen_xy(p.core.frame_rgb(), puck_colors, prev)
        cxs.append(np.nan if cx is None else cx)
        cys.append(np.nan if cy is None else cy)
    cxs = np.array(cxs)
    cys = np.array(cys)
    if int((~np.isnan(cxs)).sum()) < 12:
        R["phases"].setdefault("puck", {})["error"] = "mask sparse"
        return []
    yx = np.nan_to_num(cxs[1:] - np.nanmean(cxs))
    yy = np.nan_to_num(cys[1:] - np.nanmean(cys))
    NW = 0x200000 // 2
    top = []
    BLOCK = 65536
    for b0 in range(0, NW, BLOCK):
        b1 = min(b0 + BLOCK, NW)
        S = np.stack([np.frombuffer(r.tobytes(), dtype="<u2",
                                    count=b1 - b0, offset=b0 * 2)
                      .astype(np.float64) for r in rams])
        d = S[1:] - S[:-1]
        var = S.std(axis=0)
        act = (np.abs(d) > 0).mean(axis=0)
        ok = (var > 6) & (act > 0.5) & (var < 4096)
        for col in np.nonzero(ok)[0]:
            x = d[:, col]
            xs = x - x.mean()
            denx = xs.std() * (yx.std() + 1e-9)
            deny = xs.std() * (yy.std() + 1e-9)
            cxr = (float((xs * yx).mean() / denx) if denx > 1e-9 else 0.0)
            cyr = (float((xs * yy).mean() / deny) if deny > 1e-9 else 0.0)
            if abs(cxr) >= 0.35 or abs(cyr) >= 0.35:
                top.append({"addr": hex(0x80000000 + (b0 + int(col)) * 2),
                            "corr_x": round(cxr, 3), "corr_y": round(cyr, 3),
                            "var": round(float(var[col]), 1),
                            "min": int(S[:, col].min()),
                            "max": int(S[:, col].max())})
        del S, d
    top.sort(key=lambda r: -max(abs(r["corr_x"]), abs(r["corr_y"])))
    R["phases"].setdefault("puck", {})["top_x"] = top[:12]
    log("puck top:", [(r["addr"], r["corr_x"]) for r in top[:8]])
    jlog()
    return top


# ----------------------------------------------------------------- score --
class ScoreScan:
    """Continuous per-tick +1 byte scan across the whole match."""

    def __init__(self):
        self.prev = None
        self.events = []
        self.seen_offsets = {}

    def tick(self, p, tag=""):
        s = p.mem.snapshot()
        if self.prev is not None:
            d = s.astype(np.int16) - self.prev.astype(np.int16)
            inc = np.nonzero(d == 1)[0]
            for o in inc[:12]:
                key = int(o)
                ent = self.seen_offsets.setdefault(
                    key, {"addr": hex(0x80000000 + key), "hits": 0,
                          "ticks": [], "vals": []})
                ent["hits"] += 1
                ent["ticks"].append(tag)
                ent["vals"].append(int(s[key]))
                if len(ent["ticks"]) <= 2:
                    self.events.append({"tick": tag,
                                        "addr": ent["addr"],
                                        "val_after": int(s[key])})
        self.prev = s
        return self.events


# ----------------------------------------------------------- closed loop --
def phase_loop(p, best_word, puck_top, scene, scan, half, max_bursts=90):
    scene_t = scene.lower()
    # PLAYER_SIDE field decides; default bottom (both r21 scene cards said it)
    player_top = "player_side=top" in scene_t or (
        "top" in scene_t and "bottom" not in scene_t)
    cpu_top = not player_top
    puckc = R["phases"].setdefault("loop", {})
    puckc["cpu_top"] = bool(cpu_top)
    vlm_budget = [5]          # goal/deflection VLM cap
    push = "UP" if cpu_top else "DOWN"
    retreat = "DOWN" if cpu_top else "UP"
    puck_addr = None
    if puck_top:
        pick = max(puck_top, key=lambda r: abs(r["corr_x"]))
        if abs(pick["corr_x"]) >= 0.5:
            puck_addr = int(pick["addr"], 16)
    puckc["puck_addr"] = hex(puck_addr) if puck_addr else None
    puck_y_addr = None
    if puck_top:
        picky = max(puck_top, key=lambda r: abs(r["corr_y"]))
        if abs(picky["corr_y"]) >= 0.5:
            puck_y_addr = int(picky["addr"], 16)
    puckc["puck_y_addr"] = hex(puck_y_addr) if puck_y_addr else None
    pad_off = (best_word - 0x80000000) if best_word else None
    puckc["bursts"] = []
    events = {"deflections": [], "goals": []}
    px_hist = []
    concede_after = 40
    conceded = False

    def rd(off):
        return C.u16le(p.mem.ram, off)

    for burst in range(max_bursts):
        acted = "idle"
        px = rd(puck_addr - 0x80000000) if puck_addr else None
        py = rd(puck_y_addr - 0x80000000) if puck_y_addr else None
        padx = rd(pad_off) if pad_off is not None else None
        if conceded:                      # concede mode: park at far edge
            acted = "CONCEDE_LEFT" if half == "bottom" else "CONCEDE_RIGHT"
            p.core.run(6, {"LEFT"})
        elif px is None or padx is None:
            acted = f"SCAN_{push}"
            p.core.run(8, {push})
        else:
            dx = px - padx
            if abs(dx) > 10:
                acted = "LEFT" if dx < 0 else "RIGHT"
                p.core.run(4, {acted})
            else:
                # aligned: strike toward the CPU goal
                acted = f"PUSH_{push}"
                extra = "LEFT" if dx < -3 else "RIGHT" if dx > 3 else None
                btns = {push} | ({extra} if extra else set())
                p.core.run(10, btns)
        C.rel(p, 16)
        C.gifcap(p, 2)
        scan.tick(p, tag=f"burst{burst}")
        px_hist.append(px)
        # deflection: puck vx sign flip while we were tracking/acting
        if px is not None and len(px_hist) >= 3:
            vx0 = px_hist[-2] - px_hist[-3]
            vx1 = px_hist[-1] - px_hist[-2]
            if vx0 * vx1 < 0 and abs(vx1) >= 2 and not conceded:
                near = (padx is not None and px is not None
                        and abs(px - padx) <= 26)
                if near:
                    fp = C.png(p, f"b2_deflect_{len(events['deflections'])}")
                    dfl = {"burst": burst, "px": px, "padx": padx,
                           "vx0": vx0, "vx1": vx1,
                           "png": os.path.basename(fp)}
                    if vlm_budget[0] > 0:
                        vlm_budget[0] -= 1
                        txt = C.vlm([fp], "PS1 air-hockey frame. <=25 words: "
                                          "is the puck close to / touching "
                                          "the player paddle (just bounced "
                                          "off it)?", f"b2_dfl{burst}")
                        dfl["vlm"] = txt[:200]
                    events["deflections"].append(dfl)
                    log("DEFLECTION?", dfl)
        # goal detection: repeated or struct-neighborhood +1 offsets only
        for addr, ent in scan.seen_offsets.items():
            if ent.get("vlm_done") or vlm_budget[0] <= 0:
                continue
            near_struct = 0x800A1300 <= addr <= 0x800A1700
            if ent["hits"] >= 2 or near_struct:
                ent["vlm_done"] = True
                vlm_budget[0] -= 1
                fp = C.png(p, f"b2_goal_{addr}")
                txt = C.vlm([fp], "PS1 air-hockey frame. <=25 words: exact "
                                  "scoreboard numbers? goal/celebration "
                                  "text visible?", f"b2_goal{addr}")
                ent["vlm"] = txt[:200]
                events["goals"].append({"burst": burst, "addr": ent["addr"],
                                        "hits": ent["hits"],
                                        "vals": ent["vals"][:4],
                                        "vlm": txt[:200],
                                        "png": os.path.basename(fp)})
                log("GOAL-EVENT", addr, ent["vals"], txt[:120])
        # periodic scoreboard VLM
        if burst and burst % 12 == 0:
            fp = C.png(p, f"b2_sb_{burst}")
            txt = C.vlm([fp], "PS1 air-hockey frame. <=15 words: exact "
                              "scoreboard numbers now?", f"b2_sb{burst}")
            puckc["bursts"].append({"burst": burst, "acted": acted,
                                    "px": px, "padx": padx,
                                    "sb_vlm": txt[:120]})
            log(f"b{burst} acted={acted} px={px} padx={padx} :: {txt[:80]}")
        if burst == concede_after and not events["goals"] \
                and not events["deflections"]:
            conceded = True
            log("entering concede mode (anchor score via CPU goal)")
        if burst == concede_after + 16:
            conceded = False          # back to real play
    puckc["events"] = events
    puckc["score_scan"] = {hex(a): {"hits": e["hits"],
                                    "vals": e["vals"][:6],
                                    "ticks": e["ticks"][:6]}
                           for a, e in scan.seen_offsets.items()}
    jlog()
    return events


# ------------------------------------------------------------------ main --
def main():
    t0 = time.time()
    p = PS1Play(C.CUE, core=C.CORE, workspace=C.WS, var_overrides=C.OV)
    info = p.boot()
    log("boot", {k: info.get(k) for k in ("core", "serial", "ram_bytes")})
    try:
        ok, gtxt = gate_walk(p)
        if not ok:
            R["verdict"] = "GATE_WALK_FAILED"
            ev("- **gate walk FAILED** — see b2_gate_* PNGs")
            jlog()
            return
        C.rel(p, 120)
        scene = ""
        for attempt in range(4):      # VS-screen guard: wait for a live rink
            fp = C.png(p, f"b2_scene{attempt}")
            scene = C.vlm([fp], C.SCENE_PROMPT, f"b2_scene{attempt}")
            R["phases"].setdefault("scene_poll", []).append(scene[:200])
            if any(k in scene.lower() for k in
                   ("table", "rink", "puck", "goal", "scoreboard")) \
                    and "select" not in scene.lower() \
                    and "vs" not in scene.lower()[:20]:
                break
            C.rel(p, 400)
        p.save_state("r22_match")
        C.png(p, "b2_scene")
        R["phases"]["scene"] = scene[:400]
        ev(f"- LIVE_MATCH reached (legal gates); scene: {scene[:220]}")
        log("scene:", scene[:200])
        scan = ScoreScan()
        scan.tick(p, tag="start")

        best, clamp, half = phase_pin(p, scene)
        scan.tick(p, tag="pin")
        ev(f"- PIN: best={hex(best) if best else None} clamp={json.dumps({k: v for k, v in clamp.items() if k != 'vlm'})}")
        if clamp.get("vlm"):
            ev(f"  - clamp VLM: {clamp['vlm'][:220]}")
        ev(f"  - pin VLM: {R['phases']['pin'].get('vlm', '')[:220]}")
        ev(f"  - ranked: {[(r['word'], r['sL'], r['sR'], r['idle_max']) for r in R['phases']['pin'].get('ranked', [])[:5]]}")

        # puck colors from scene card
        colors = C.parse_colors(scene)
        cmap = {"white": (235, 235, 235), "red": (200, 40, 40),
                "yellow": (220, 200, 60), "orange": (230, 140, 40),
                "black": (35, 35, 35), "blue": (45, 65, 200),
                "green": (45, 170, 60), "purple": (150, 60, 200),
                "pink": (230, 100, 160), "cyan": (60, 200, 200),
                "gray": (140, 140, 140), "grey": (140, 140, 140)}
        puck_colors = [cmap[c] for c in colors.get("puck", [])[:3]
                       if c in cmap] or [(35, 35, 35)]
        puck_top = phase_puck(p, puck_colors)
        scan.tick(p, tag="puckhunt")
        ev(f"- PUCK: top {[(r['addr'], r['corr_x']) for r in puck_top[:5]]}")

        events = phase_loop(p, best, puck_top, scene, scan, half)
        n_defl = len(events["deflections"])
        n_goal = len(events["goals"])
        ev(f"- LOOP: deflections={n_defl} goal_events={n_goal}")
        ev(f"  - deflections: {events['deflections'][:3]}")
        ev(f"  - goals: {events['goals'][:3]}")
        final = C.png(p, "b2_final")
        ftxt = C.vlm([os.path.join(OUT, "b2_scene.png"), final],
                     "Two PS1 air-hockey frames (img1 = match start, img2 = "
                     "now). <=30 words: exact scoreboard numbers in each "
                     "and did any digit change?", "b2_final")
        ev(f"- FINAL scoreboard VLM: {ftxt[:220]}")
        R["phases"]["final_vlm"] = ftxt[:300]
        pin_ok = bool(best) and clamp and \
            clamp.get("LEFT", {}).get("stable_f", 99) >= 30 and \
            clamp.get("RIGHT", {}).get("stable_f", 99) >= 30
        R["verdict"] = ("PLAYING" if (pin_ok and (n_goal or n_defl))
                        else "RUNNING")
        R["pin_ok"] = bool(pin_ok)
    except Exception:                                          # noqa: BLE001
        import traceback
        R["error"] = traceback.format_exc()[-1600:]
        ev(f"- **ERROR**: `{R['error'][-400:]}`")
        log("ERROR", R["error"][-300:])
        R["verdict"] = "ERROR"
    R["finished"] = time.strftime("%Y-%m-%dT%H:%M:%SZ")
    R["wall_s"] = round(time.time() - t0, 1)
    ev(f"- boots used: 2/3; wall {R['wall_s']}s; verdict **{R['verdict']}**")
    jlog()
    log("DONE", R["verdict"], R["wall_s"], "s")


if __name__ == "__main__":
    main()
