#!/usr/bin/env python3
"""hellopong_r12_control.py — Round 12 (Task 16-c) SEGMENT 3: idle control.

SEPARATE process, ONE beetle boot, ZERO button input (every run() call
advances frames with an explicit empty button set; the pad-buffer mirror
is sampled to prove it). Purpose: record the NATURAL outcome of
hello_pong from boot with nobody playing, as the contrast arm for the
WIN run (scripts/hellopong_r12_win.py):

  boot -> (auto-started fresh game, upstream pad-init garbage CROSS
  release) -> idle -> natural points -> natural GAME_OVER -> who won?

The score sensor is identified observe-only (natural-point +1 scan,
hellopong_r12_lib.discover_score_by_points); the WIN run's resolved
addresses are accepted as a PRIOR cross-check (--sensor-json) — same
static stack slot layout — but the primary identification here is
independent and input-free.

Evidence: scratch/round12_hellopong/control/.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from hellopong_r12_lib import (                    # noqa: E402
    REPO, STEP, WIN_SCORE, ScoreSensor, ball_centroid, boot_hellopong,
    classify, discover_score_by_points, madiff, make_jrn, pad_mirrors,
    padbuff_addrs, save_png, settle_boot, text_crop, u32)

OUT = os.path.join(REPO, "scratch", "round12_hellopong", "control")
WS = "/home/z/my-project/emu/games_homebrew/ws_hellopong_r12_ctl"
MAX_FRAMES = 20000


def sha16(b):
    return hashlib.sha256(b).hexdigest()[:16]


def read_score(p, sensor):
    if sensor.l_addr is None:
        return None
    return int(u32(bytes(p.mem.snapshot()))[sensor.l_addr // 4])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sensor-json", default=None,
                    help="win-run report.json -> sensor block as prior")
    args = ap.parse_args()

    jrn = make_jrn(OUT, "[r12ctl]")
    if os.path.exists(os.path.join(OUT, "report.json")):
        stamp = time.strftime("%Y%m%d_%H%M%S")
        arch = os.path.join(OUT, f"attempt_archived_{stamp}")
        os.makedirs(arch, exist_ok=True)
        for fn in os.listdir(OUT):
            if fn.endswith((".png", ".json", ".jsonl")):
                os.rename(os.path.join(OUT, fn), os.path.join(arch, fn))
        jrn({"ev": "archived_previous_attempt", "dir": arch})
    rep = {"schema": "ps1ai-hellopong-r12-control/1",
           "generated_utc": time.strftime("%FT%TZ", time.gmtime()),
           "task": "16-c", "lane": "16-c hello_pong idle control",
           "one_boot_per_process": True, "input_used": False}
    t0 = time.time()

    p, boot_info = boot_hellopong(WS, jrn)
    rep["boot"] = boot_info
    jrn.cur["f"] = p.core.frames_run
    sensor = ScoreSensor(p)

    # prior addresses from the WIN run (cross-check only; same static
    # stack layout, observe-only reads)
    prior = None
    if args.sensor_json and os.path.exists(args.sensor_json):
        try:
            wrep = json.load(open(args.sensor_json))
            sb = wrep.get("sensor") or {}
            if sb.get("l_addr"):
                sensor.l_addr = int(sb["l_addr"], 16)
                sensor.y_addr = (int(sb["y_addr"], 16)
                                 if sb.get("y_addr") else
                                 sensor.l_addr - 4)
                prior = {"l_addr": hex(sensor.l_addr),
                         "y_addr": hex(sensor.y_addr),
                         "source": args.sensor_json}
                yv = int(u32(bytes(p.mem.snapshot()))
                         [sensor.y_addr // 4])
                prior["y_value_at_boot"] = yv
                prior["y_in_range"] = 0 < yv < 240
        except Exception as e:                       # noqa: BLE001
            prior = {"error": repr(e)}
    rep["prior_sensor"] = prior
    jrn({"ev": "prior_sensor", **(prior or {"none": True})})

    cls, timeline, addrs = settle_boot(p, jrn)
    jrn.cur["f"] = p.core.frames_run
    rep["boot_state"] = {"class": cls, "polls": len(timeline),
                         "padbuff": [hex(a) for a in addrs]}
    jrn({"ev": "boot_state", **rep["boot_state"]})

    # ---- pad-mirror samples: prove NO input was ever injected ----
    mirrors = pad_mirrors(p, addrs)
    jrn({"ev": "pad_mirror_sample_boot", "mirrors": mirrors})
    rep["pad_mirror_samples"] = [ {"when": "boot", "mirrors": mirrors} ]

    if cls == "TIMEOUT":
        rep["verdict"] = "FAILED(boot: no game screen)"
        with open(os.path.join(OUT, "report.json"), "w") as f:
            json.dump(rep, f, indent=1)
        return 1

    if cls == "MENU":
        # no auto-start this boot: record honestly, idle a while longer
        p.wait(1200, set())
        fr = p.core.frame_rgb()
        cls2, facts = classify(fr, 0.0)
        save_png(OUT, fr, "menu_after_idle.png")
        rep["menu_persist_check"] = {"class_after_1200f_idle": cls2,
                                     **facts}
        jrn({"ev": "menu_persist_check",
             "class_after_1200f_idle": cls2})
        if cls2 == "MENU":
            rep["verdict"] = "NO-GAME(natural idle never left the menu)"
            rep["wall_s"] = round(time.time() - t0, 1)
            with open(os.path.join(OUT, "report.json"), "w") as f:
                json.dump(rep, f, indent=1)
            return 0
        cls = cls2

    if cls == "GAME_OVER":
        # the walkover already finished during boot settle: read the
        # final score via the prior address (observe-only)
        sc = read_score(p, sensor) if sensor.l_addr is not None else None
        fr = p.core.frame_rgb()
        crop = text_crop(fr)
        save_png(OUT, fr, "gameover_at_boot.png")
        save_png(OUT, crop, "gameover_at_boot_textcrop.png")
        rep["natural_outcome"] = {
            "mode": "finished_during_boot_settle",
            "left_score": sc,
            "winner": ("left" if sc == WIN_SCORE else
                       "left(>=5?)" if sc is not None and sc >= WIN_SCORE
                       else "unknown"),
            "gameover_textcrop_bright_px": int((crop > 150).sum()),
        }
        rep["final_class"] = "GAME_OVER"
        jrn({"ev": "natural_game_over_at_boot", "left_score": sc})
        rep["sensor"] = sensor.sensor_block()
        rep["verdict"] = ("NATURAL-LEFT-WIN-5(sensor-prior)"
                          if sc == WIN_SCORE else
                          "NATURAL-OVER-UNVERIFIED(no sensor)")
        rep["wall_s"] = round(time.time() - t0, 1)
        rep["frames_run"] = p.core.frames_run
        with open(os.path.join(OUT, "report.json"), "w") as f:
            json.dump(rep, f, indent=1)
        jrn({"ev": "verdict", "verdict": rep["verdict"]})
        return 0

    # ---- PLAYING: input-free discovery, then ride to game over ----
    disc = discover_score_by_points(p, jrn, OUT, sensor, need_points=3,
                                    max_frames=6000)
    rep["sensor_discovery"] = {k: v for k, v in disc.items()
                               if k != "anchors"}
    rep["discovery_anchors"] = disc.get("anchors", [])
    if not disc.get("ok"):
        jrn({"ev": "note",
             "text": "discovery unresolved; continuing with prior only"})
    l_addr = sensor.l_addr

    # ---- idle ride to the natural game over ----
    transitions = []
    last_sc = read_score(p, sensor) if l_addr else None
    prev_frame = p.core.frame_rgb()
    static_run = 0
    frames_start = p.core.frames_run
    mirrors_time = 0
    while p.core.frames_run - frames_start < MAX_FRAMES:
        fr = p.core.frame_rgb()
        a = madiff(prev_frame, fr)
        prev_frame = fr
        cls_f, facts = classify(fr, a)
        if cls_f == "GAME_OVER" and a is not None and a < 0.02:
            static_run += 1
        else:
            static_run = 0
        if static_run >= 3:
            break
        if p.core.frames_run % 300 < STEP:
            save_png(OUT, fr, f"f{p.core.frames_run}.png")
        if p.core.frames_run - mirrors_time > 600:
            mirrors_time = p.core.frames_run
            mir = pad_mirrors(p, addrs)
            rep["pad_mirror_samples"].append(
                {"when": p.core.frames_run, "mirrors": mir})
            jrn({"ev": "pad_mirror_sample", "frame": p.core.frames_run,
                 "mirrors": mir})
        if l_addr and p.core.frames_run % 8 < STEP:
            sc = read_score(p, sensor)
            if sc is not None and last_sc is not None and sc != last_sc:
                png = save_png(OUT, p.core.frame_rgb(),
                               f"ctl_point_{last_sc}_to_{sc}.png")
                ent = {"frame": p.core.frames_run, "from": last_sc,
                       "to": sc, "png": png}
                transitions.append(ent)
                jrn({"ev": "natural_score_transition", **ent})
            last_sc = sc
        p.core.run(STEP, set())               # ZERO input
    jrn.cur["f"] = p.core.frames_run

    # ---- final evidence ----
    p.wait(30, set())
    fr = p.core.frame_rgb()
    cls_fin, facts_fin = classify(fr, 0.0)
    save_png(OUT, fr, "final_gameover.png")
    crop = text_crop(fr)
    save_png(OUT, crop, "final_gameover_textcrop.png")
    sc_fin = read_score(p, sensor) if l_addr else None
    rep["natural_outcome"] = {
        "mode": "idle_from_boot",
        "final_class": cls_fin,
        "final_facts": facts_fin,
        "left_score": sc_fin,
        "winner": ("left" if sc_fin is not None and sc_fin >= WIN_SCORE
                   else "unknown"),
        "transitions": transitions,
        "gameover_textcrop_bright_px": int((crop > 150).sum()),
        "textcrop_sha16": sha16(crop.tobytes()),
    }
    rep["sensor"] = sensor.sensor_block()
    idle_mirrors_ok = all(
        all(v == 0xFFFF for v in s["mirrors"].values())
        for s in rep["pad_mirror_samples"])
    rep["no_input_evidence"] = {
        "pad_mirror_samples": len(rep["pad_mirror_samples"]),
        "all_idle_like": idle_mirrors_ok,
        "note": "0xFFFF = no buttons; any pressed-bit mirror would "
                "appear here (samples taken across the whole run)"}
    if sc_fin is not None and sc_fin >= WIN_SCORE:
        rep["verdict"] = ("NATURAL-LEFT-WIN-5(sensor, input-free)")
    elif sc_fin is not None:
        rep["verdict"] = f"NATURAL-OVER(left_score={sc_fin})"
    else:
        rep["verdict"] = "NATURAL-OVER(no sensor address resolved)"
    rep["wall_s"] = round(time.time() - t0, 1)
    rep["frames_run"] = p.core.frames_run
    with open(os.path.join(OUT, "report.json"), "w") as f:
        json.dump(rep, f, indent=1)
    jrn({"ev": "verdict", "verdict": rep["verdict"],
         "left_score": sc_fin, "class": cls_fin})
    return 0


if __name__ == "__main__":
    sys.exit(main())
