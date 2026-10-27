#!/usr/bin/env python3
"""r21-t5 run 5 — full continuous path + improved paddle hunt + goal attempt.

run4 reached the live match ("FIGHT ME! GO THUNDER BOY") but the paddle
hunt's 0.6 corr gate rejected the best candidate (0x800a14f8 corr 0.555 —
the blob target mixed puck+paddle motion). run5:
  * same proven path (START -> CROSS -> ... -> CIRCLE -> wait load),
    no restores after any confirm gate (run-3 CD-stream lesson);
  * paddle blob restricted to the bottom 40 rows (paddle-only motion);
  * lower rank gate (0.45) + causal top-2 verify (LEFT vs RIGHT flip);
  * color-mask chase policy (paddle tracks puck, pushes to CPU goal);
  * scoreboard VLM + RAM +1 scan -> PLAYING only with the full chain.
"""
from __future__ import annotations

import json
import os
import sys
import time

import numpy as np
from PIL import Image

sys.path.insert(0, "/home/z/my-project/ps1ai/scripts")
import r21t5_airhockey_causality as m                      # noqa: E402
import r21t5_airhockey_run4 as r4                          # noqa: E402
from ps1play.api import PS1Play                            # noqa: E402

R5 = {"task": "r21t5-run5", "started": time.strftime("%Y-%m-%dT%H:%M:%SZ")}


def log(*a):
    print("[r21t5-r5]", *a, file=sys.stderr, flush=True)


def paddle_hunt2(p):
    """LEFT/idle/RIGHT sampling with a paddle-only screen target."""
    rams, grays, segs = [], [], []
    plan = ([("idle", None)] * 6 + [("LEFT", "LEFT")] * 10 +
            [("idle", None)] * 8 + [("RIGHT", "RIGHT")] * 10 +
            [("idle", None)] * 8)
    for t, btn in plan:
        p.core.run(3, {btn} if btn else set())
        rams.append(p.mem.snapshot())
        grays.append(m.gray(p.core.frame_rgb()).astype(np.float32))
        segs.append(t)
    grays = np.stack(grays)
    dif = np.abs(grays[1:] - grays[:-1]) > 18
    # paddle-only target: motion centroid over the bottom 40 rows
    blob_cx, spread = [], []
    for mm0 in dif:
        mm = mm0.copy()
        mm[:200, :] = False
        if mm.sum() > 6:
            xs = np.nonzero(mm)[1]
            blob_cx.append(float(xs.mean()))
            spread.append(float(xs.max() - xs.min()))
        else:
            blob_cx.append(np.nan)
            spread.append(0.0)
    cx = np.nan_to_num(np.array(blob_cx))
    R5["hunt_bottom_motion_frac"] = round(
        float(dif[:, 200:, :].sum() / max(dif.sum(), 1)), 3)

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
        cands = np.nonzero((aL <= 512) & (aI <= 64) & opp & (rng < 8192))[0]
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
                        "first": int(series[0, o]), "last": int(series[-1, o]),
                        "sL": int(np.sum(sL[o])) if not np.isscalar(sL) else 0,
                        "sR": int(np.sum(sR[o])) if not np.isscalar(sR) else 0})
        return out

    s16 = np.stack([r.view("<i2").astype(np.int32) for r in rams])
    s8 = np.stack([r.astype(np.int32) for r in rams])
    c16, c8 = hunt(s16, 2), hunt(s8, 1)
    R5["hunt"] = {"u16le_top": c16[:10], "u8_top": c8[:10]}
    log("  hunt u16LE:", [(c["hex"], c["corr"]) for c in c16[:5]])
    log("  hunt u8  :", [(c["hex"], c["corr"]) for c in c8[:5]])

    # causal top-2 verification (inline, no restore)
    seen_off = set()
    for pick in (c16[:2] + c8[:2]):
        if pick["off"] in seen_off or abs(pick["corr"]) < 0.45:
            continue
        seen_off.add(pick["off"])
        rd, le = pick["off"], pick in c16

        def read():
            ram = p.mem.ram
            return int(ram.view("<i2")[rd // 2]) if le else int(ram[rd])

        v0 = read()
        p.core.run(20, {"LEFT"})
        v_left, fr_left = read(), p.core.frame_rgb()
        m.rel(p, 50)
        p.core.run(20, {"RIGHT"})
        v_right, fr_right = read(), p.core.frame_rgb()
        m.rel(p, 50)
        moved = (v_left != v_right)
        log(f"  verify {pick['hex']} corr={pick['corr']} {v0} ->L {v_left}"
            f" ->R {v_right} moved={moved}")
        if not moved:
            continue
        Image.fromarray(fr_left).save(os.path.join(
            m.OUT, "p4_left_held.png"))
        Image.fromarray(fr_right).save(os.path.join(
            m.OUT, "p4_right_held.png"))
        vtxt = m.vlm([os.path.join(m.OUT, "p4_left_held.png"),
                      os.path.join(m.OUT, "p4_right_held.png")],
                     "Two PS1 air-hockey frames (img1 LEFT held 20f, img2 "
                     "RIGHT held 20f). <=30 words: did the player paddle "
                     "move between them and which way? Did the puck move?",
                     "p5_pad")
        R5["paddle_vlm"] = vtxt[:250]
        log("  paddle vlm:", vtxt[:150])
        return {"ok": True, "addr": pick["hex"],
                "dtype": "u16LE" if le else "u8", "corr": pick["corr"],
                "start": v0, "after_LEFT": v_left, "after_RIGHT": v_right,
                "vlm": vtxt[:250]}
    return {"ok": False}


def goal_attempt2(p):
    fp = m.png(p, "p4b_setup")
    desc = m.vlm([fp], "PS1 air-hockey frame, <=40 words: (1) player paddle "
                 "color, (2) CPU paddle color, (3) puck color, (4) which "
                 "side top/bottom is the CPU goal, (5) exact scoreboard "
                 "text.", "p5_desc")
    log("  desc:", desc[:180])
    t = desc.lower()
    cpu_top = "top" in t and "bottom" not in t.split("cpu")[0][:20]
    R5["p4b_desc"] = desc[:300]
    push_btn = "UP" if cpu_top else "DOWN"
    retreat = "DOWN" if cpu_top else "UP"
    colors = [rgb for name, rgb in
              (("white", (235, 235, 235)), ("red", (200, 40, 40)),
               ("yellow", (220, 200, 60)), ("orange", (230, 140, 40)),
               ("black", (30, 30, 30)), ("dark", (30, 30, 30)),
               ("blue", (40, 60, 200)), ("green", (40, 170, 60)))
              if name in t] or [(235, 235, 235)]
    prev = [None, None]
    s_start = p.mem.snapshot()
    goal = {"attempted": True, "bursts": [], "goal": False,
            "cpu_top_guess": bool(cpu_top)}

    def mask_xy(fr, rgb, half=None, size=(30, 4000)):
        a = fr.astype(np.int32)
        mm = ((a[:, :, 0] - rgb[0]) ** 2 + (a[:, :, 1] - rgb[1]) ** 2 +
              (a[:, :, 2] - rgb[2]) ** 2) < 2500
        if half == "bottom":
            mm[:120, :] = False
        elif half == "top":
            mm[120:, :] = False
        if not (size[0] < mm.sum() < size[1]):
            return None
        ys, xs = np.nonzero(mm)
        return float(xs.mean()), float(ys.mean()), int(mm.sum())

    def puck_xy(fr):
        best = None
        for rgb in colors:
            c = mask_xy(fr, rgb)
            if c and (best is None or c[2] > best[2]):
                best = c
        if best and prev[0] is not None and (
                abs(best[0] - prev[0]) > 200 or abs(best[1] - prev[1]) > 120):
            return (prev[0], prev[1])
        if best:
            prev[0], prev[1] = best[0], best[1]
        return (best[0], best[1]) if best else None

    for burst in range(12):
        fr = p.core.frame_rgb()
        kxy = puck_xy(fr)
        acted = "none"
        if kxy:
            kx, ky = kxy
            pxy = mask_xy(fr, colors[0], "bottom" if cpu_top else "top",
                          (60, 6000))
            if pxy:
                px, py, _ = pxy
                dx = kx - px
                puck_ahead = (ky < py) if cpu_top else (ky > py)
                if abs(dx) > 8:
                    acted = "LEFT" if dx < 0 else "RIGHT"
                    p.core.run(4, {acted})
                elif puck_ahead:
                    acted = "PUSH_" + push_btn
                    extra = "LEFT" if dx < -3 else "RIGHT" if dx > 3 else None
                    btns = {push_btn} | ({extra} if extra else set())
                    p.core.run(10, btns)
                else:               # puck behind paddle: don't own-goal
                    acted = "RETREAT_" + retreat
                    p.core.run(6, {retreat})
            else:
                acted = "TRACK"
                p.core.run(4, {"LEFT" if kx < 128 else "RIGHT"})
            m.gifcap(p, 2)
        else:
            acted = "SCAN"
            p.core.run(8, {push_btn})
            m.gifcap(p, 2)
        m.rel(p, 22)
        if burst % 2 == 1:
            fp = m.png(p, f"p5_burst{burst}")
            vtxt = m.vlm([fp], "PS1 air-hockey frame. <=20 words: exact "
                         "scoreboard numbers now? Any goal celebration or "
                         "announcement text visible?", f"p5_b{burst}")
            goal["bursts"].append({"burst": burst, "acted": acted,
                                   "puck": kxy and [round(kxy[0]),
                                                    round(kxy[1])],
                                   "vlm": vtxt[:160]})
            log(f"  b{burst} acted={acted} puck={kxy} :: {vtxt[:100]}")
            if any(k in vtxt.lower() for k in
                   ("goal", "1-0", "0-1", "1 - 0", "0 - 1", "celebrat")):
                d = p.mem.snapshot().astype(np.int16) - \
                    s_start.astype(np.int16)
                inc = np.nonzero(d == 1)[0]
                goal["ram_plus1_words"] = [hex(0x80000000 + int(o))
                                           for o in inc[:16]]
                if len(inc):
                    goal.update(goal=True, goal_burst=burst)
                    m.png(p, "p5_goal_candidate")
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
    p.boot()
    p.core.run(2000)
    m.png(p, "r5_title")
    typ, vtxt = r4.confirm(p, "START", 300, "m0")       # -> AIR HOCKEY!!
    R5["g1"] = vtxt[:150]
    typ, vtxt = r4.confirm(p, "B", 500, "m1")           # -> PLAYER SELECT
    R5["g2"] = vtxt[:150]
    if "PLAYER" not in vtxt.upper():
        for b in ("A", "B", "START"):
            typ, vtxt = r4.confirm(p, b, 400, f"m2_{b}")
            R5.setdefault("g3", []).append({b: vtxt[:150]})
            if "PLAYER" in vtxt.upper():
                break
    typ, vtxt = r4.confirm(p, "A", 300, "m3")           # confirm player
    R5["g4"] = vtxt[:150]
    ok, vtxt = r4.wait_live(p, 2100, "load")            # NO restore
    R5["load_ok"] = ok
    R5["load_vlm"] = vtxt[:200]
    if ok:
        m.rel(p, 60)
        m.png(p, "p4_game_entry")
        p.save_state("game_r5")
        R5["paddle"] = paddle_hunt2(p)
        if R5["paddle"].get("ok"):
            R5["goal"] = goal_attempt2(p)
    R5["finished"] = time.strftime("%Y-%m-%dT%H:%M:%SZ")
    R5["wall_s"] = round(time.time() - t0, 1)
    json.dump(R5, open(os.path.join(m.OUT, "run5_log.json"), "w"),
              indent=1, default=str)
    log("DONE", R5.get("load_ok"), R5.get("paddle"), R5.get("goal"))


if __name__ == "__main__":
    main()
