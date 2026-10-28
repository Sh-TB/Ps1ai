#!/usr/bin/env python3
"""r22t5 air_hockey calibration — BOOT 1 of max 3.

Reuses the r21t5 live-match checkpoints (game_r5 / game_r4 / game) READ-ONLY
for calibration probes (allowed by the task). No game RAM is ever written.

Phases:
  C0  boot -> load live-match checkpoint (game_r5, fallback game_r4/game)
      -> VLM scene card (paddle colors, puck color, CPU side, scoreboard).
  C1  paddle pin: LEFT-hold / idle / RIGHT-hold / clamp windows with per-3f
      RAM sampling of candidate words 0x800A148A / 0x800A148E (+raw bytes)
      and same-moment screen motion centroid of OUR half.
      Pin criteria: (a) monotonic consistent movement under the button,
      (b) VLM-corroborated on-screen displacement between labeled frames,
      (c) clamp at both screen edges.
  C2  puck hunt: 360f idle, u16LE series every 2f vs screen puck centroid
      -> top correlated words (puck x/y candidates).
  C3  score hunt: passive play (zero input, fully legal) up to ~3600f;
      per-3f snapshots; byte words with an exact +1 step at one tick are
      score candidates; VLM scoreboard before/after the event tick.

Evidence: /home/z/my-project/ps1ai/scratch/r22t5_airhockey/ (incremental).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time

import numpy as np
from PIL import Image

_REPO = "/home/z/my-project/ps1ai"
for _p in (_REPO, os.path.join(_REPO, "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from ps1play.api import PS1Play                                   # noqa: E402

OUT = os.path.join(_REPO, "scratch", "r22t5_airhockey")
GIFDIR = os.path.join(OUT, "gif_frames")
CUE = ("/home/z/my-project/emu/games_small/extracted/air_hockey_norm/"
       "Air Hockey (USA) 2352.cue")
CORE = "/home/z/my-project/emu/cores/mednafen_psx_libretro.so"
WS = "/home/z/my-project/emu/ws_r21t5_airhockey"
OV = {b"beetle_psx_override_bios": b"openbios"}

PAD1 = 0x09FF58                    # padbuff port1 (00 41 ff ff, r20/r21)
CANDS = [0x800A148A, 0x800A148E]   # r21t5 paddle candidates (u16LE view)

os.makedirs(OUT, exist_ok=True)
os.makedirs(GIFDIR, exist_ok=True)

R = {"task": "r22t5-calib", "started": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
     "cue": CUE, "ws": WS, "gs_code_search": "exhausted (see evidence.md)",
     "phases": {}}
GIF_N = [0]


def log(*a):
    print("[r22t5-c]", *a, file=sys.stderr, flush=True)


def jlog():
    json.dump(R, open(os.path.join(OUT, "calib_log.json"), "w"), indent=1,
              default=str)
    with open(os.path.join(OUT, "evidence.md"), "a") as f:
        f.write("")            # placeholder no-op; real appends explicit


def rel(p, n):
    p.core.run(n, set())       # released (run() latches last spec!)


def png(p, name):
    fr = p.core.frame_rgb()
    path = os.path.join(OUT, f"{name}.png")
    if fr is not None:
        Image.fromarray(fr).save(path)
    return path


def gifcap(p, every=2):
    GIF_N[0] += 1
    if GIF_N[0] % every:
        return
    fr = p.core.frame_rgb()
    if fr is not None:
        Image.fromarray(fr).resize((256, 120)).save(
            os.path.join(GIFDIR, f"g{GIF_N[0]:06d}.png"))


def gray(fr):
    return np.asarray(Image.fromarray(fr).convert("L"), np.float32)


def vlm(image_paths, prompt, tag):
    args = ["z-ai", "vision", "-p", prompt, "-o",
            os.path.join(OUT, f"vlm_{tag}.json")]
    for ip in image_paths:
        args += ["-i", ip]
    try:
        subprocess.run(args, capture_output=True, timeout=150)
        d = json.load(open(os.path.join(OUT, f"vlm_{tag}.json")))
        txt = d.get("content") or d.get("choices", [{}])[0].get(
            "message", {}).get("content", "")
        return str(txt).strip()
    except Exception as e:                                     # noqa: BLE001
        log("vlm failed", tag, repr(e))
        return ""


def u16le(ram, off):
    return int(ram[off]) | (int(ram[off + 1]) << 8)


# ------------------------------------------------------------------ C0 --
SCENE_PROMPT = ("PS1 air-hockey frame. Answer in <=60 words with fields: "
                "PLAYER_SIDE=<top|bottom>; PLAYER_COLOR=<...>; CPU_COLOR=<...>; "
                "PUCK_COLOR=<...>; SCOREBOARD=<exact text/numbers>; "
                "OTHER=<anything notable>.")


def load_live_match(p):
    """Load the newest r21t5 live-match checkpoint; VLM-verify it."""
    for name, note in (("game_r5", "run5 entry"), ("game_r4", "run4 entry"),
                       ("game", "run1 entry")):
        try:
            p.load_state(name)
        except Exception as e:                                 # noqa: BLE001
            log("load failed", name, repr(e))
            continue
        rel(p, 90)
        fp = png(p, f"c0_loaded_{name}")
        txt = vlm([fp], SCENE_PROMPT, f"c0_{name}")
        t = txt.lower()
        live = any(k in t for k in ("hockey", "puck", "rink", "paddle"))
        dead = any(k in t for k in ("menu", "title", "select", "loading",
                                    "black", "vs", "press start"))
        log(f"C0 {name}: live={live} dead={dead} :: {txt[:160]}")
        R["phases"].setdefault("c0", {})[name] = {
            "vlm": txt[:300], "live_guess": live and not dead}
        if live and not dead:
            R["phases"]["c0"]["chosen"] = name
            return name, txt
    return None, ""


def parse_colors(txt):
    """Cheap color parse from the VLM scene card."""
    t = txt.lower()
    out = {}
    for key in ("player", "cpu", "puck"):
        m = [c for c in ("red", "blue", "green", "yellow", "orange", "white",
                         "black", "purple", "pink", "cyan", "gray", "grey")
             if c in t]
        out[key] = m
    return out


# ------------------------------------------------------------------ C1 --
def motion_centroid(gray_fr, prev_gray, half, thresh=18):
    """Motion centroid x + row of the changed pixels inside `half`
    ('top'|'bottom'). Returns (cx, cy, n) or None."""
    d = np.abs(gray_fr - prev_gray) > thresh
    if half == "bottom":
        d[:120, :] = False
    else:
        d[120:, :] = False
    n = int(d.sum())
    if n < 6:
        return None
    ys, xs = np.nonzero(d)
    return float(xs.mean()), float(ys.mean()), n


def sample_word(ram):
    """All tracked words for one sample tick."""
    row = {}
    for a in CANDS:
        off = a - 0x80000000
        row[f"{a:08X}"] = u16le(ram, off)
    row["raw_88_8F"] = bytes(bytearray(ram[0xA1488:0xA1490])).hex(" ")
    return row


def phase1_pin(p, our_half):
    """LEFT/idle/RIGHT holds + clamp tests, per-3f sampling."""
    R["phases"]["c1"] = {"our_half": our_half, "samples": []}
    plan = ([("idle", None)] * 20 +
            [("LEFT", "LEFT")] * 40 +          # 120f hold
            [("idle", None)] * 30 +            # 90f settle / spring-back?
            [("RIGHT", "RIGHT")] * 40 +
            [("idle", None)] * 20)
    prev_gray = gray(p.core.frame_rgb())
    si = 0
    left_end_fr = right_end_fr = None
    for tag, btn in plan:
        p.core.run(3, {btn} if btn else set())
        gifcap(p, 3)
        fr = p.core.frame_rgb()
        g = gray(fr)
        mc = motion_centroid(g, prev_gray, our_half)
        prev_gray = g
        row = {"t": si * 3, "seg": tag, "btn": btn}
        row.update(sample_word(p.mem.ram))
        if mc:
            row["mcx"], row["mcy"], row["mn"] = (round(mc[0], 1),
                                                 round(mc[1], 1), mc[2])
        R["phases"]["c1"]["samples"].append(row)
        if tag == "LEFT" and btn:
            left_end_fr = fr
        if tag == "RIGHT" and btn:
            right_end_fr = fr
        si += 1
    Image.fromarray(left_end_fr).save(os.path.join(OUT, "c1_left_held.png"))
    Image.fromarray(right_end_fr).save(os.path.join(OUT, "c1_right_held.png"))
    vtxt = vlm([os.path.join(OUT, "c1_left_held.png"),
                os.path.join(OUT, "c1_right_held.png")],
               "Two PS1 air-hockey frames (img1 = LEFT held 120f, img2 = "
               "RIGHT held 120f). <=40 words: did the PLAYER paddle change "
               "horizontal position between them, and in which direction "
               "did it move? Did the puck move?", "c1_pin")
    R["phases"]["c1"]["vlm"] = vtxt[:400]
    log("C1 vlm:", vtxt[:200])

    # clamp tests: hold one way until the word stops moving (<=420f)
    clamp = {}
    for btn in ("LEFT", "RIGHT"):
        rel(p, 30)
        last, stable, held = None, 0, 0
        traj = []
        fr_clamp = None
        while held < 420 and stable < 45:
            p.core.run(3, {btn})
            held += 3
            v = u16le(p.mem.ram, CANDS[0] - 0x80000000)
            v2 = u16le(p.mem.ram, CANDS[1] - 0x80000000)
            traj.append((held, v, v2))
            if last is not None and v == last:
                stable += 3
            else:
                stable = 0
            last = v
        fr_clamp = png(p, f"c1_clamp_{btn}")
        clamp[btn] = {"held_f": held, "final": last, "stable_f": stable,
                      "cand2_final": traj[-1][2] if traj else None,
                      "png": fr_clamp, "traj_head": traj[:3],
                      "traj_tail": traj[-3:]}
        log(f"C1 clamp {btn}: {clamp[btn]}")
        rel(p, 40)
    R["phases"]["c1"]["clamp"] = clamp
    jlog()
    return R["phases"]["c1"]


# ------------------------------------------------------------------ C2 --
def phase2_puck(p, puck_colors, dur=360, step=2):
    """Track u16LE series + screen puck centroid; correlate."""
    R["phases"]["c2"] = {}
    rel(p, 30)
    rams, cxs, cys = [], [], []
    prev = [None, None]
    for i in range(dur // step):
        p.core.run(step, set())
        rams.append(p.mem.snapshot())
        fr = p.core.frame_rgb()
        cx, cy = puck_screen_xy(fr, puck_colors, prev)
        cxs.append(cx if cx is not None else np.nan)
        cys.append(cy if cy is not None else np.nan)
        if i % 15 == 0:
            gifcap(p, 1)
    cxs = np.array(cxs)
    cys = np.array(cys)
    have = ~np.isnan(cxs)
    log(f"C2 puck mask hits {int(have.sum())}/{len(cxs)}")
    if int(have.sum()) < 10:
        R["phases"]["c2"]["error"] = "puck mask too sparse"
        jlog()
        return []
    yx = cxs[1:] - np.nanmean(cxs)
    yy = cys[1:] - np.nanmean(cys)
    K = len(rams)
    yx = np.nan_to_num(yx)
    NW = 0x200000 // 2                     # u16 words in RAM

    # block-wise pass (memory-bounded): var/activity/corr per u16 column
    top = []
    BLOCK = 65536
    for b0 in range(0, NW, BLOCK):
        b1 = min(b0 + BLOCK, NW)
        S = np.stack([np.frombuffer(r.tobytes(), dtype="<u2",
                                    count=b1 - b0, offset=b0 * 2)
                      .astype(np.float64) for r in rams])   # (K, blk)
        d = S[1:] - S[:-1]
        var = S.std(axis=0)
        act = (np.abs(d) > 0).mean(axis=0)
        ok = (var > 6) & (act > 0.5) & (var < 4096)
        if not ok.any():
            continue
        for col in np.nonzero(ok)[0]:
            x = d[:, col]
            xs = x - x.mean()
            den = xs.std() * (yx.std() + 1e-9)
            cxr = float((xs * yx).mean() / den) if den > 1e-9 else 0.0
            if abs(cxr) < 0.35:
                continue
            top.append({"addr": hex(0x80000000 + (b0 + int(col)) * 2),
                        "corr_x": round(cxr, 3),
                        "var": round(float(var[col]), 1),
                        "min": int(S[:, col].min()),
                        "max": int(S[:, col].max())})
        del S, d
    R["phases"]["c2"]["n_candidates"] = len(top)
    top.sort(key=lambda r: -abs(r["corr_x"]))
    R["phases"]["c2"]["top_x"] = top[:14]
    log("C2 top:", [(r["addr"], r["corr_x"]) for r in top[:8]])
    jlog()
    return top


def puck_screen_xy(fr, colors, prev, size=(20, 5000)):
    """Color-mask puck centroid with anti-teleport hold."""
    a = fr.astype(np.int32)
    best = None
    for rgb in colors:
        mm = ((a[:, :, 0] - rgb[0]) ** 2 + (a[:, :, 1] - rgb[1]) ** 2 +
              (a[:, :, 2] - rgb[2]) ** 2) < 2600
        if not (size[0] < mm.sum() < size[1]):
            continue
        ys, xs = np.nonzero(mm)
        cand = (float(xs.mean()), float(ys.mean()), int(mm.sum()))
        if best is None or cand[2] > best[2]:
            best = cand
    if best and prev[0] is not None and (
            abs(best[0] - prev[0]) > 160 or abs(best[1] - prev[1]) > 100):
        return (prev[0], prev[1])
    if best:
        prev[0], prev[1] = best[0], best[1]
        return (best[0], best[1])
    return (None, None)


# ------------------------------------------------------------------ C3 --
def phase3_score(p, max_f=3600):
    """Passive play; byte words with an exact +1 step at one tick."""
    R["phases"]["c3"] = {"events": []}
    s_prev = p.mem.snapshot()
    png(p, "c3_score_before")
    scored_ticks = []
    ticks = max_f // 3
    for t in range(ticks):
        p.core.run(3, set())
        gifcap(p, 6)
        s = p.mem.snapshot()
        d = s.astype(np.int16) - s_prev.astype(np.int16)
        inc = np.nonzero(d == 1)[0]
        if len(inc):
            row = {"tick_f": (t + 1) * 3,
                   "offsets": [hex(0x80000000 + int(o)) for o in inc[:20]],
                   "n": int(len(inc))}
            R["phases"]["c3"]["events"].append(row)
            scored_ticks.append((t + 1) * 3)
            log("C3 +1 event @f", row["tick_f"], row["offsets"][:8])
            fp = png(p, f"c3_event_{len(scored_ticks)}")
            txt = vlm([fp], "PS1 air-hockey frame. <=25 words: exact "
                            "scoreboard numbers? Any goal/celebration text?",
                      f"c3_ev{len(scored_ticks)}")
            row["vlm"] = txt[:200]
            log("C3 vlm:", txt[:150])
            if len(scored_ticks) >= 3:
                break
        s_prev = s
    d = p.mem.snapshot()
    png(p, "c3_score_after")
    fp = png(p, "c3_score_final")
    txt = vlm([os.path.join(OUT, "c3_score_before.png"),
               os.path.join(OUT, "c3_score_final.png")],
              "Two PS1 air-hockey frames: img1 start-of-session scoreboard, "
              "img2 now. <=30 words: exact scoreboard numbers in each, and "
              "did any digit change?", "c3_final")
    R["phases"]["c3"]["vlm_final"] = txt[:300]
    log("C3 final vlm:", txt[:200])
    jlog()
    return R["phases"]["c3"]


# ------------------------------------------------------------------ main --
def main():
    t0 = time.time()
    with open(os.path.join(OUT, "evidence.md"), "a") as f:
        f.write(f"\n## r22t5 BOOT 1 — calibration ({time.strftime('%H:%M:%S')})\n"
                "- GS/CB code web search: exhausted (gamehacking.org 404 for "
                "SLUS-01467 + search blocked by CF/bot-walls; Wayback empty). "
                "No third-party codes used; pure behavioral RAM work.\n")
    p = PS1Play(CUE, core=CORE, workspace=WS, var_overrides=OV)
    info = p.boot()
    log("boot", {k: info.get(k) for k in ("core", "serial", "ram_bytes")})
    rel(p, 300)
    name, scene = load_live_match(p)
    if not name:
        R["verdict"] = "BOOT1_NO_LIVE_STATE"
        jlog()
        log("no live state usable")
        return
    with open(os.path.join(OUT, "evidence.md"), "a") as f:
        f.write(f"- C0: reused checkpoint `{name}` (read-only); scene card: "
                f"{scene[:200]}\n")
    half = "bottom"
    t = scene.lower()
    m = t.find("player_side")
    if m >= 0:
        hs = t[m:m + 30]
        half = "top" if "top" in hs else "bottom"
    R["phases"]["c0"]["our_half"] = half
    colors = parse_colors(scene)
    puck_colors = []
    cmap = {"white": (235, 235, 235), "red": (200, 40, 40),
            "yellow": (220, 200, 60), "orange": (230, 140, 40),
            "black": (35, 35, 35), "blue": (45, 65, 200),
            "green": (45, 170, 60), "purple": (150, 60, 200),
            "pink": (230, 100, 160), "cyan": (60, 200, 200),
            "gray": (140, 140, 140), "grey": (140, 140, 140)}
    for c in colors.get("puck", [])[:3]:
        puck_colors.append(cmap[c])
    if not puck_colors:
        puck_colors = [(235, 235, 235)]
    R["phases"]["c0"]["puck_colors"] = [[int(v) for v in c]
                                        for c in puck_colors]

    try:
        phase1_pin(p, half)
        with open(os.path.join(OUT, "evidence.md"), "a") as f:
            c1 = R["phases"]["c1"]
            cl = c1.get("clamp", {})
            f.write(f"- C1 pin: our_half={half}; VLM: {c1.get('vlm','')[:180]}\n")
            f.write(f"  - clamp LEFT: {cl.get('LEFT') and (cl['LEFT']['held_f'], cl['LEFT']['final'])}\n")
            f.write(f"  - clamp RIGHT: {cl.get('RIGHT') and (cl['RIGHT']['held_f'], cl['RIGHT']['final'])}\n")
        phase2_puck(p, puck_colors)
        with open(os.path.join(OUT, "evidence.md"), "a") as f:
            top = R["phases"]["c2"].get("top_x", [])[:6]
            f.write(f"- C2 puck hunt: {len(R['phases']['c2'].get('top_x', []))} "
                    f"corr>=0.35; top: "
                    f"{[(r['addr'], r['corr_x']) for r in top]}\n")
        phase3_score(p)
        with open(os.path.join(OUT, "evidence.md"), "a") as f:
            ev = R["phases"]["c3"].get("events", [])
            f.write(f"- C3 score events: {len(ev)} "
                    f"{[(e['tick_f'], e['offsets'][:4]) for e in ev[:3]]}\n")
            f.write(f"  - final VLM: {R['phases']['c3'].get('vlm_final','')[:180]}\n")
    except Exception:                                          # noqa: BLE001
        import traceback
        R["error"] = traceback.format_exc()[-1500:]
        log("PHASE ERROR", R["error"][-400:])
        jlog()
    R["finished"] = time.strftime("%Y-%m-%dT%H:%M:%SZ")
    R["wall_s"] = round(time.time() - t0, 1)
    R["verdict"] = "CALIB_DONE"
    jlog()
    log("DONE", R["wall_s"], "s")


if __name__ == "__main__":
    main()
