#!/usr/bin/env python3
"""r21-t5: air_hockey SLUS-01467 single-button causality map -> controlled gameplay.

ONE comprehensive emulator boot (reserve boot allowed but avoided) that runs:

  P0  boot -> f2000 title, save_state("title"), RAM baseline
  P0b pad-bitmap battery: for each button, load("title"), idle, 3f pulse
      (read pad word u16 BE @0x09FF5A after EVERY pulse frame), settle 30f.
      Fixes r20's loose end (r20 probed the 0x0041 header @0x09FF58; the
      button word is at +2, big-endian, active-low). Records which bit
      clears per ps1play button name = the button-bitmap mapping.
      Also per-button title-screen reaction (single-frame RAM delta +
      screen-diff PNG) -> the title causality map.
  P1  title -> PLAYER SELECT via the r20-proven SELECT lever
      (3f pulse + 30f gap x4), labeled PNG after each pulse.
  P2  menu semantics: from save_state("menu"), one button per probe
      (UP/DOWN/X/START/B/A/SELECT), load->pulse->gap->labeled PNG each;
      ranked by measured screen reaction.
  P3  exact button sequence menu -> gameplay (VLM-guided adaptive walk,
      one button advance at a time), transition PNGs, save_state("game").
  P4  gameplay: LEFT/RIGHT 5f-tick sampling; paddle-word hunt = u16LE/u8
      words with opposite-sign drift during LEFT vs RIGHT segments and
      screen-correlated (moving-blob cx on the player half); bidirectional
      verify from a fresh load; VLM confirms the paddle visibly moves.
  P4b goal attempt: VLM-guided color chase policy (paddle tracks puck x,
      pushes toward the opponent goal); scoreboard watched via VLM +
      RAM +1-event scan. Goal through play -> PLAYING, else honest RUNNING.

Evidence: /home/z/my-project/ps1ai/scratch/r21t5_airhockey/
Disc: the r20 stride-fixed dump (read-only /tmp fallback allowed by task).
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
from ps1play.core.memory import diff_regions                      # noqa: E402

OUT = os.path.join(_REPO, "scratch", "r21t5_airhockey")
GIFDIR = os.path.join(OUT, "gif_frames")
CUE = "/tmp/my-project/emu/games_small/extracted/air_hockey_norm/Air Hockey (USA) 2352.cue"
CORE = "/home/z/my-project/emu/cores/mednafen_psx_libretro.so"
WS = "/home/z/my-project/emu/ws_r21t5_airhockey"
OV = {b"beetle_psx_override_bios": b"openbios"}

PAD1 = 0x09FF58                 # padbuff port1 signature 00 41 ff ff (r20)
MASK_OFF = PAD1 + 2             # u16 BIG-ENDIAN active-low button word
PAD2 = 0x09FF7A                 # port2

# PSX pad word bits (standard, active-low) — the hypothesis this run tests
BIT_NAMES = {0: "SELECT", 3: "START", 4: "UP", 5: "RIGHT", 6: "DOWN",
             7: "LEFT", 8: "L2", 9: "R2", 10: "L1", 11: "R1",
             12: "TRIANGLE", 13: "CIRCLE", 14: "CROSS", 15: "SQUARE"}

# ps1play name -> expected PSX button (libretro positional mapping)
PLAY2PSX = {"B": "CROSS", "A": "CIRCLE", "X": "TRIANGLE", "Y": "SQUARE",
            "SELECT": "SELECT", "START": "START",
            "UP": "UP", "DOWN": "DOWN", "LEFT": "LEFT", "RIGHT": "RIGHT"}

os.makedirs(OUT, exist_ok=True)
os.makedirs(GIFDIR, exist_ok=True)

R = {"task": "r21t5", "started": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
     "cue": CUE, "ws": WS, "phases": {}}
GIF_N = [0]


def log(*a):
    print("[r21t5]", *a, file=sys.stderr, flush=True)


def jlog():
    json.dump(R, open(os.path.join(OUT, "run_log.json"), "w"), indent=1,
              default=str)   # numpy-scalar safety net


def pad_word(p):
    """u16 button word @padbuff+2. MEASURED r21: stored LITTLE-ENDIAN with
    the standard PSX bit layout (SELECT=0x0001 .. SQUARE=0x8000); r20's
    'u16 BE' note byte-swaps it (BE read puts SELECT at bit8)."""
    ram = p.mem.ram
    return int(ram[MASK_OFF]) | (int(ram[MASK_OFF + 1]) << 8)


def pad_word2(p):
    ram = p.mem.ram
    return int(ram[PAD2 + 2]) | (int(ram[PAD2 + 3]) << 8)


def cleared_bits(mask_ever_pressed):
    return [BIT_NAMES[b] for b in range(16) if mask_ever_pressed >> b & 1]


def png(p, name):
    fr = p.core.frame_rgb()
    path = os.path.join(OUT, f"{name}.png")
    if fr is not None:
        Image.fromarray(fr).save(path)
    return path


def gifcap(p, every=3):
    """Append every `every`-th call a downscaled frame for the run GIF."""
    GIF_N[0] += 1
    if GIF_N[0] % every:
        return
    fr = p.core.frame_rgb()
    if fr is not None:
        im = Image.fromarray(fr).resize((256, 120))
        im.save(os.path.join(GIFDIR, f"f{GIF_N[0]:06d}.png"))


def gray(fr):
    return np.asarray(Image.fromarray(fr).convert("L"), np.float32)


def screen_mad(a, b):
    return float(np.abs(a - b).mean())


def vlm(image_paths, prompt, tag):
    """Classify PNG(s) through the z-ai vision CLI. Returns text (or '')."""
    args = ["z-ai", "vision", "-p", prompt, "-o",
            os.path.join(OUT, f"vlm_{tag}.json")]
    for ip in image_paths:
        args += ["-i", ip]
    try:
        subprocess.run(args, capture_output=True, timeout=120)
        d = json.load(open(os.path.join(OUT, f"vlm_{tag}.json")))
        txt = d.get("content") or d.get("choices", [{}])[0].get(
            "message", {}).get("content", "")
        return str(txt).strip()
    except Exception as e:                                    # noqa: BLE001
        log("vlm failed", tag, repr(e))
        return ""


def static_mad(p, gap=30):
    """MAD between now and +gap frames: menus are static (<~8), animated
    title/attract screens are not (ambient ~40 here)."""
    g0 = gray(p.core.frame_rgb())
    rel(p, gap)
    return screen_mad(gray(p.core.frame_rgb()), g0)


def ramb_delta(p, s0):
    """Single-frame RAM delta + top regions vs snapshot s0."""
    s1 = p.mem.snapshot()
    d = diff_regions(s0, s1)
    d["regions"] = [(int(a), int(b), int(c)) for a, b, c in d["regions"]]
    return int(np.count_nonzero(s0 != s1)), d


def rel(p, n):
    """Run n frames with buttons RELEASED (run() latches the last spec!)."""
    p.core.run(n, set())


# ======================================================================
# P0 — boot to title
# ======================================================================
def phase0(p):
    info = p.boot()
    log("boot", {k: info.get(k) for k in ("core", "serial", "plugin",
                                          "ram_bytes")})
    p.core.run(2000)
    g0 = gray(p.core.frame_rgb())
    p.core.run(60)
    g1 = gray(p.core.frame_rgb())
    png(p, "p0_title_f2000")
    p.save_state("title")
    R["phases"]["p0"] = {
        "boot": {k: info.get(k) for k in ("core", "serial", "plugin",
                                          "ram_bytes", "input_device")},
        "title_ambient_mad": round(screen_mad(g0, g1), 3),
        "pad_word_title": hex(pad_word(p)),
        "pad_word_title_port2": hex(pad_word2(p)),
        "pad_hexdump_p1": p.mem.hexdump(PAD1, 8),
    }
    log("title @f2000 pad=", hex(pad_word(p)), "port2=",
        hex(pad_word2(p)), "ambient=", R["phases"]["p0"]["title_ambient_mad"])
    jlog()
    return g1


# ======================================================================
# P0b — pad-bitmap battery (one button per load of "title")
# ======================================================================
def phase0b(p, title_gray):
    buttons = ["SELECT", "START", "UP", "DOWN", "LEFT", "RIGHT",
               "B", "A", "X", "Y"]
    out = {}
    for btn in buttons:
        p.load_state("title")
        rel(p, 10)
        words = []
        # 3-frame pulse, read the BE word after every frame
        for _ in range(3):
            p.core.run(1, {btn})
            words.append(pad_word(p))
        pressed_mask = 0
        for w in words:
            pressed_mask |= (~w) & 0xFFFF
        rel(p, 30)                    # gap (buttons released)
        s0 = p.mem.snapshot()
        rel(p, 1)
        d1, _ = ramb_delta(p, s0)
        react = screen_mad(gray(p.core.frame_rgb()), title_gray)
        pngname = f"p0b_title_after_{btn}"
        if react > 1.0:
            png(p, pngname)
        # sparse-refresh fallback: one 10f hold if 3f never flipped
        mode = "3f"
        if not pressed_mask:
            p.load_state("title")
            rel(p, 10)
            for _ in range(10):
                p.core.run(1, {btn})
                w = pad_word(p)
                words.append(w)
                pressed_mask |= (~w) & 0xFFFF
            mode = "10f-hold"
            rel(p, 30)
        out[btn] = {
            "psx_button": PLAY2PSX[btn],
            "pulse_words": [hex(w) for w in words],
            "ever_pressed_mask": hex(pressed_mask),
            "ever_pressed_bits": cleared_bits(pressed_mask),
            "pad_flip_ok": bool(pressed_mask),
            "probe_mode": mode,
            "ram_delta_next_frame": d1,
            "screen_mad_vs_title": round(react, 3),
            "png": pngname if react > 1.0 else None,
        }
        log(f"  pad {btn:6s}->{PLAY2PSX[btn]:9s} mask={hex(pressed_mask):6s}"
            f" bits={out[btn]['ever_pressed_bits']} flip={bool(pressed_mask)}"
            f" react={react:.2f} ramd1={d1}")
    R["phases"]["p0b_bitmap"] = out
    jlog()
    return out


# ======================================================================
# P1 — SELECT battery at title (r20-lever comparability record).
# The walk in P2/P3 starts from wherever the screen ends up (s0).
# ======================================================================
def phase1(p, title_gray):
    p.load_state("title")
    rel(p, 10)
    pulses = []
    for i in range(4):
        s0 = p.mem.snapshot()
        pw = []
        for _ in range(3):
            p.core.run(1, {"SELECT"})
            pw.append(pad_word(p))
        d, _ = ramb_delta(p, s0)
        rel(p, 30)
        g = gray(p.core.frame_rgb())
        mad = screen_mad(g, title_gray)
        png(p, f"p1_after_select_{i}")
        pulses.append({"i": i, "ram_delta": d,
                       "mad_vs_title": round(mad, 3),
                       "pad_words_during_pulse": [hex(w) for w in pw],
                       "pad_min_pressed": hex(min(pw))})
        log(f"  select#{i} ramd={d} mad={mad:.2f} pad_min={hex(min(pw))}")
    sm = static_mad(p, 30)
    png(p, "p1_after_battery")
    p.save_state("s0")
    changed = sm < 8.0          # static screen == a menu, not the animated title
    R["phases"]["p1"] = {"pulses": pulses, "static_mad_after": round(sm, 2),
                         "screen_static": bool(changed), "state_saved": "s0"}
    jlog()
    return changed


# ======================================================================
# P2 — one-button-at-a-time battery on the current screen (s0):
# pulse 3f + 57f gap + labeled PNG per button = the causality map row.
# ======================================================================
PROBES = ["UP", "DOWN", "LEFT", "RIGHT", "X", "START", "B", "A",
          "SELECT"]


def screen_battery(p, state, tag):
    p.load_state(state)
    rel(p, 10)
    base_gray = gray(p.core.frame_rgb())
    base_ram = p.mem.snapshot()
    out = {}
    for btn in PROBES:
        p.load_state(state)
        rel(p, 10)
        s0 = p.mem.snapshot()
        p.core.run(3, {btn})
        dp, _ = ramb_delta(p, s0)
        rel(p, 57)                # settle -> 60f after pulse
        d, regions = ramb_delta(p, base_ram)
        mad = screen_mad(gray(p.core.frame_rgb()), base_gray)
        png(p, f"{tag}_{btn}")
        out[btn] = {"ram_delta_pulse": dp, "ram_delta_vs_base": d,
                    "mad_vs_base": round(mad, 2),
                    "top_regions": regions["regions"][:3]}
        log(f"  {tag} {btn:6s} ramdPulse={dp} vsBase={d} mad={mad:.2f}")
    p.load_state(state)
    rel(p, 10)
    return out


def phase2(p):
    out = screen_battery(p, "s0", "p2_after")
    R["phases"]["p2"] = {"screen": "s0", "battery": out}
    jlog()
    return out


# ======================================================================
# P3 — greedy walk to gameplay: apply each screen's strongest reactor,
# VLM-identify the new screen, backtrack on revisits. Bounded.
# ======================================================================
NEG_MARKS = ("black screen", "loading", "cannot", "no visible",
             "not live", "no game", "no hockey", "no score",
             "transition")


def looks_like_gameplay(vtxt):
    t = vtxt.lower()
    if any(k in t for k in NEG_MARKS):
        return False
    game = any(k in t for k in ("rink", "hockey", "puck", "scoreboard",
                                "goalie", "face-off", "faceoff", "fight",
                                "go thunder", "period", "live match"))
    menu = any(k in t for k in ("menu", "select", "option", "cursor",
                                "highlight", "title"))
    return game and not menu


VLM_PROMPT = ("PS1 game screen, <=25 words: what screen is this (exact "
              "title/entries/highlighted entry) or live hockey gameplay? "
              "Mention any score/HUD text.")


def apply_and_classify(p, state, btn, depth):
    p.load_state(state)
    rel(p, 10)
    png(p, f"p3_d{depth}_before_{btn}")
    p.core.run(3, {btn})
    for k in range(12):           # transition capture (released)
        rel(p, 10)
        gifcap(p, 2)
        if k in (0, 3, 6, 11):
            png(p, f"p3_trans{depth}_{k:02d}")
    png(p, f"p3_d{depth}_after_{btn}")
    vtxt = vlm([os.path.join(OUT, f"p3_d{depth}_after_{btn}.png")],
               VLM_PROMPT, f"p3_d{depth}")
    log(f"  p3 d{depth} {btn}: {vtxt[:130]}")
    return vtxt


def phase3(p):
    seq = []
    seen = set()
    stack = [("s0", sorted(R["phases"]["p2"]["battery"],
                           key=lambda b: -R["phases"]["p2"]["battery"][b]
                           ["mad_vs_base"]), 0)]
    gameplay = False
    steps = 0
    while stack and steps < 12:
        state, cands, ci = stack[-1]
        if ci >= len(cands):
            stack.pop()
            continue
        stack[-1] = (state, cands, ci + 1)
        btn = cands[ci]
        vtxt = apply_and_classify(p, state, btn, steps)
        steps += 1
        sig = vtxt[:60].lower()
        seq.append({"depth": len(stack) - 1, "from_state": state, "btn": btn,
                    "vlm": vtxt[:220]})
        if looks_like_gameplay(vtxt):
            gameplay = True
            png(p, "p3_gameplay_reached")
            break
        if sig in seen:
            log("  revisit -> backtrack", btn)
            continue
        seen.add(sig)
        nxt_state = f"p3s{steps}"
        p.save_state(nxt_state)          # baseline of the NEW screen
        bat = screen_battery(p, nxt_state, f"p3_d{steps}_probe")
        cands2 = sorted(bat, key=lambda b: -bat[b]["mad_vs_base"])
        seq[-1]["new_state"] = nxt_state
        seq[-1]["battery"] = bat
        stack.append((nxt_state, cands2, 0))
    R["phases"]["p3"] = {"sequence": seq, "gameplay": gameplay, "steps": steps}
    if gameplay:
        rel(p, 60)
        png(p, "p4_game_entry")
        p.save_state("game")
    jlog()
    return gameplay

# ======================================================================
# P4 — paddle control: LEFT/RIGHT pulses + paddle-word hunt
# ======================================================================
def phase4(p):
    R["phases"]["p4"] = {}
    p.load_state("game")
    rel(p, 30)
    rams, grays, segs = [], [], []
    plan = ([("idle", None)] * 5 + [("LEFT", "LEFT")] * 4 +
            [("idle", None)] * 5 + [("RIGHT", "RIGHT")] * 4 +
            [("idle", None)] * 4)
    for tag, btn in plan:
        p.core.run(5, {btn} if btn else set())
        rams.append(p.mem.snapshot())
        grays.append(gray(p.core.frame_rgb()).astype(np.float32))
        segs.append(tag)
    grays = np.stack(grays)          # (K,240,512) — list broke subtraction
    K = len(rams)
    dif = np.abs(grays[1:] - grays[:-1]) > 18
    tot = max(dif.sum(), 1)
    frac_bottom = float(dif[:, 120:, :].sum() / tot)
    R["phases"]["p4"]["motion_frac_bottom"] = round(frac_bottom, 3)
    lo_row, hi_row = (120, 240) if frac_bottom >= 0.5 else (0, 120)

    blob_cx = []
    for m in dif:
        mm = m.copy()
        mm[:lo_row, :] = False
        mm[hi_row:, :] = False
        if mm.sum() > 8:
            blob_cx.append(float(np.nonzero(mm)[1].mean()))
        else:
            blob_cx.append(np.nan)
    cx = np.nan_to_num(np.array(blob_cx))

    def hunt(series, aligned):
        d = np.diff(series, axis=0)               # (K-1, N)
        move_idx = np.array([i for i, s in enumerate(segs[1:])
                             if s in ("LEFT", "RIGHT")])
        idle_idx = np.array([i for i, s in enumerate(segs[1:])
                             if s == "idle"])
        aL = np.abs(d[move_idx]).max(axis=0) if len(move_idx) else 0
        aI = np.abs(d[idle_idx]).max(axis=0) if len(idle_idx) else 0
        li = [i for i in move_idx if segs[i + 1] == "LEFT"]
        ri = [i for i in move_idx if segs[i + 1] == "RIGHT"]
        sL = d[np.array(li)].sum(axis=0) if li else 0
        sR = d[np.array(ri)].sum(axis=0) if ri else 0
        opp = (np.sign(sL) != np.sign(sR)) & (np.abs(sL) >= 2) \
            & (np.abs(sR) >= 2)
        rng = series.max(axis=0) - series.min(axis=0)
        cands = np.nonzero((aL <= 512) & (aI <= 16) & opp & (rng < 8192))[0]
        if not len(cands):
            return []
        sub = series[:, cands].astype(np.float64)      # (K, C) columns only
        y = cx - cx.mean()
        xs = sub[1:]
        xc = xs - xs.mean(axis=0)
        num = (xc * y[:, None]).mean(axis=0)
        den = xs.std(axis=0) * (y.std() + 1e-9)
        corr = np.divide(num, den, out=np.zeros_like(num), where=den > 1e-9)
        res = []
        for i in np.argsort(-np.abs(corr))[:20]:
            o = int(cands[i])
            res.append({"off": o * aligned,
                        "hex": hex(0x80000000 + o * aligned),
                        "corr": round(float(corr[i]), 3),
                        "first": int(series[0, o]),
                        "last": int(series[-1, o])})
        return res

    series16 = np.stack([r.view("<i2").astype(np.int32) for r in rams])
    series8 = np.stack([r.astype(np.int32) for r in rams])
    be16 = np.stack([np.frombuffer(r.tobytes(), dtype=">u2")
                     .astype(np.int32) for r in rams])
    c16, c8, cb = hunt(series16, 2), hunt(series8, 1), hunt(be16, 2)
    R["phases"]["p4"]["u16le_top"] = c16[:12]
    R["phases"]["p4"]["u8_top"] = c8[:12]
    R["phases"]["p4"]["u16be_top"] = cb[:8]
    log("  u16LE top:", [(c["hex"], c["corr"]) for c in c16[:5]])
    log("  u8   top:", [(c["hex"], c["corr"]) for c in c8[:5]])

    pick = next((c for c in c16 + c8 if abs(c["corr"]) > 0.6), None)
    R["phases"]["p4"]["pick"] = pick

    verify = {"ok": False}
    if pick:
        p.load_state("game")
        rel(p, 30)
        rd, le = pick["off"], pick in c16
        if le:
            v0 = int(p.mem.ram.view("<i2")[rd // 2])
        else:
            v0 = int(p.mem.ram[rd])
        p.core.run(15, {"LEFT"})
        v_left = (int(p.mem.ram.view("<i2")[rd // 2]) if le
                  else int(p.mem.ram[rd]))
        fr_left = p.core.frame_rgb()
        rel(p, 60)
        p.core.run(15, {"RIGHT"})
        v_right = (int(p.mem.ram.view("<i2")[rd // 2]) if le
                   else int(p.mem.ram[rd]))
        fr_right = p.core.frame_rgb()
        Image.fromarray(fr_left).save(os.path.join(OUT, "p4_left_held.png"))
        Image.fromarray(fr_right).save(os.path.join(OUT, "p4_right_held.png"))
        moved = (v_left != v_right)
        verify = {"addr": pick["hex"], "dtype": "u16LE" if le else "u8",
                  "start": v0, "after_LEFT": v_left, "after_RIGHT": v_right,
                  "moved": moved, "ok": moved}
        vtxt = vlm([os.path.join(OUT, "p4_left_held.png"),
                    os.path.join(OUT, "p4_right_held.png")],
                   "Two PS1 air-hockey frames (img1 LEFT held 15f, img2 "
                   "RIGHT held 15f). <=30 words: did the player paddle move "
                   "between them and which way? Does the puck differ?",
                   "p4_paddle")
        verify["vlm"] = vtxt[:250]
        log("  verify:", verify)
        gifcap(p, 1)
    R["phases"]["p4"]["verify"] = verify
    jlog()
    return verify, pick


# ======================================================================
# P4b — goal attempt (bounded, VLM-guided chase, RAM+VLM anchored)
# ======================================================================
GOAL_HINTS = ("goal", "1-0", "0-1", "score", "celebrat", "1 - 0", "0 - 1")


def phase4b(p):
    p.load_state("game")
    rel(p, 30)
    png(p, "p4b_setup")
    desc = vlm([os.path.join(OUT, "p4b_setup.png")],
               "PS1 air-hockey frame, <=40 words: (1) paddle color of the "
               "player and of the CPU, (2) puck color, (3) which side "
               "(top/bottom) is the CPU goal, (4) exact scoreboard text.",
               "p4b_desc")
    log("  p4b desc:", desc[:180])
    t = desc.lower()
    cpu_top = "top" in t and "cpu" in t
    # player goal side guess: CPU at top -> we push UP
    push_btn = "UP" if cpu_top else "DOWN"
    goal = {"attempted": True, "desc": desc[:300], "bursts": [],
            "goal": False}
    s_start = p.mem.snapshot()

    def puck_xy(fr, colors):
        a = fr.astype(np.int32)
        best = None
        for rgb in colors:
            m = ((a[:, :, 0] - rgb[0]) ** 2 + (a[:, :, 1] - rgb[1]) ** 2 +
                 (a[:, :, 2] - rgb[2]) ** 2) < 2500
            if 30 < m.sum() < 4000:
                ys, xs = np.nonzero(m)
                cand = (float(xs.mean()), float(ys.mean()), int(m.sum()))
                if best is None or cand[2] > best[2]:
                    best = cand
        if best and PREV[0] is not None:
            # reject teleport-like jumps (paddle/puck color aliasing)
            if abs(best[0] - PREV[0]) > 200 or abs(best[1] - PREV[1]) > 120:
                return (PREV[0], PREV[1])
        if best:
            PREV[0], PREV[1] = best[0], best[1]
        return (best[0], best[1]) if best else None

    PREV = [None, None]

    # puck color guesses from VLM text (fallback: bright neutral disc)
    colors = []
    for name, rgb in (("white", (235, 235, 235)), ("red", (200, 40, 40)),
                      ("yellow", (220, 200, 60)), ("orange", (230, 140, 40)),
                      ("black", (30, 30, 30)), ("dark", (30, 30, 30)),
                      ("blue", (40, 60, 200)), ("green", (40, 170, 60))):
        if name in t:
            colors.append(rgb)
    if not colors:
        colors = [(235, 235, 235)]

    for burst in range(8):
        fr = p.core.frame_rgb()
        pxy = puck_xy(fr, colors)
        acted = None
        if pxy:
            dx = pxy[0] - 128           # screen center x
            if abs(dx) > 10:
                acted = "LEFT" if dx < 0 else "RIGHT"
                p.core.run(4, {acted})
                gifcap(p, 2)
            else:                   # aligned: push toward the CPU goal
                extra = ("LEFT" if dx < -4 else
                         "RIGHT" if dx > 4 else None)
                btns = {push_btn} | ({extra} if extra else set())
                acted = push_btn + (("+" + extra) if extra else "")
                p.core.run(10, btns)
                gifcap(p, 2)
        else:                     # puck not found: sweep toward center
            acted = "UP"
            p.core.run(8, {"UP"})
            gifcap(p, 2)
        rel(p, 24)
        if burst % 2 == 1:
            png(p, f"p4b_burst{burst}")
            vtxt = vlm([os.path.join(OUT, f"p4b_burst{burst}.png")],
                       "PS1 air-hockey frame. <=20 words: scoreboard "
                       "numbers now? Any goal celebration/announcement "
                       "text visible?", f"p4b_burst{burst}")
            goal["bursts"].append({"burst": burst, "acted": acted,
                                   "puck": pxy and [round(pxy[0]),
                                                    round(pxy[1])],
                                   "vlm": vtxt[:160]})
            log(f"  p4b burst{burst} acted={acted} puck={pxy} :: {vtxt[:100]}")
            if any(k in vtxt.lower() for k in GOAL_HINTS):
                s_now = p.mem.snapshot()
                d = s_now.astype(np.int16) - s_start.astype(np.int16)
                inc = np.nonzero(d == 1)[0]
                goal["ram_plus1_words"] = [hex(0x80000000 + int(o))
                                           for o in inc[:16]]
                if len(inc):
                    goal.update(goal=True, goal_burst=burst,
                                goal_addr=goal["ram_plus1_words"][:4])
                    png(p, "p4b_goal_candidate")
                    log("  GOAL anchored @bursts", burst,
                        goal["ram_plus1_words"][:4])
                    break
        gifcap(p, 2)
    # final +1 scan even without VLM hint
    s_now = p.mem.snapshot()
    d = s_now.astype(np.int16) - s_start.astype(np.int16)
    inc = np.nonzero(d == 1)[0]
    goal["ram_plus1_words_final"] = [hex(0x80000000 + int(o))
                                     for o in inc[:16]]
    R["phases"]["p4b"] = goal
    jlog()
    return goal


# ======================================================================
# main
# ======================================================================
def main():
    t0 = time.time()
    p = PS1Play(CUE, core=CORE, workspace=WS, var_overrides=OV)
    title_gray = phase0(p)
    for phase in ("p0b", "p1", "p2", "p3", "p4", "p4b"):
        try:
            if phase == "p0b":
                phase0b(p, title_gray)
            elif phase == "p1":
                phase1(p, title_gray)
            elif phase == "p2":
                phase2(p)
            elif phase == "p3":
                if not phase3(p):
                    log("walk ended without gameplay")
                    break
            elif phase == "p4":
                verify, _pick = phase4(p)
                if not verify.get("ok"):
                    log("paddle verify failed")
                    break
            elif phase == "p4b":
                phase4b(p)
        except Exception:                                     # noqa: BLE001
            import traceback
            R["phases"].setdefault(phase, {})["error"] =                 traceback.format_exc()[-1200:]
            log("PHASE ERROR", phase)
            jlog()
            break
    goal = R["phases"].get("p4b", {}).get("goal", False)
    ctrl = R["phases"].get("p4", {}).get("verify", {}).get("ok", False)
    R["verdict"] = "PLAYING" if goal else "RUNNING" if ctrl else \
        "TITLE_INTERACTIVE"
    R["finished"] = time.strftime("%Y-%m-%dT%H:%M:%SZ")
    R["wall_s"] = round(time.time() - t0, 1)
    jlog()
    log("DONE", R["verdict"], f"{R['wall_s']}s")


if __name__ == "__main__":
    main()
