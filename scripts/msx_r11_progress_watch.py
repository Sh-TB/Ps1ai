#!/usr/bin/env python3
"""msx_r11_progress_watch.py — Round 11 / Segment 2 (Issue #7 arena).

Question: does ANY RAM word move at SQUADRON_FELL / armored-trio kill
events that could be the mission-progress latch, even though the
px-2212 camera gate stays held?

Plan (ONE beetle boot, savestate `wr9_arena` from msx_r10_cap.py):
  1. FRONT: the PROVEN YB arm (msx_r10_timergate.kill_phase) until the
     front armored duo is down (rounds 9/10: +500/slot, FIELD_CLEAR).
  2. REAR: the PROVEN rear2 surgical recipe (2 f LEFT flip + stationary
     grenade lobs) for slot 12.
  3. WATCH: keep killing respawn cycles for as long as survivable
     (timergate-v2 edge-hold kite + anti-air + grenade lobs) while
     sampling every 60 f:
       - the world-alive latch 0x0EB5FC
       - FLAGS_WORD 0x0EE518 (round-8 semantics: 0xFF live / 0x1 menu)
       - SECTION_STATE 0x0EB5F4 / SECTION_FLAGS 0x0EB5D0 / PROGRESS
         0x0EB5D4 (the section-walker globals)
       - A_SCORE 0x0EE318, PLAYER_HP 0x0CA2F6, px 0x0CA2E0
       - EVERY u16 word in 0x0E7000-0x0E9000 via PollDiffIndex
         (msx_r11_lib): words whose transitions align with kill events
         are logged with timestamps and classified kill_exact /
         kill_correlated / ambient.

Death = DISCLOSED savestate restore (a retry, never a continue; no
continues exist past px 2212).  No RAM writes.  Verdict:
PROGRESS_WORD_FOUND(addr, semantics) / NEGATIVE — either is valuable.
Evidence: scratch/round11_msx/progress_watch/.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

import numpy as np

_REPO = "/home/z/my-project/ps1ai"
for _p in (_REPO, os.path.join(_REPO, "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import msx_r10_timergate as tg                          # noqa: E402
tg.OUTDIR = "/home/z/my-project/ps1ai/scratch/round11_msx/progress_watch"
from msx_r10_timergate import (                         # noqa: E402
    A_SCORE, GRENADES, PLAYER_HP, CHOPPER_ST,
    census, alive, px_of, png, kill_phase)
from msx_r11_lib import PollDiffIndex, count_waves      # noqa: E402
from ps1play.telemetry import JsonlTrace                # noqa: E402
from issue4_controller import boot                      # noqa: E402
from mission import ensure_mission                      # noqa: E402

OUTDIR = tg.OUTDIR
STATE = "wr9_arena"
PIN_PX = 2212.0
BLOCK_LO, BLOCK_HI = 0x0E7000, 0x0E9000
WATCHED = {"world_alive_latch": 0x0EB5FC, "SECTION_STATE": 0x0EB5F4,
           "SECTION_FLAGS": 0x0EB5D0, "SECTION_PROGRESS": 0x0EB5D4}
FLAGS_WORD = 0x0EE518


def log(*a):
    print("[r11-pw]", *a, file=sys.stderr, flush=True)


def watched_values(m):
    d = {k: int(m.u16(a)) for k, a in WATCHED.items()}
    d["FLAGS_WORD"] = int(m.u32(FLAGS_WORD))
    return d


def surgical_rear(p, m, J, max_cycles=14):
    """rear2 recipe verbatim: 2 f LEFT flip once, then stationary lobs."""
    kills, dmg = [], {}
    score0 = int(m.u32(A_SCORE))
    png(p, "pw_rear2_start.png")
    turned = False
    for k in range(max_cycles):
        if not alive(m):
            J({"ev": "pw_rear2_death", "cycle": k})
            return {"stop": "DEATH", "kills": kills, "dmg": dmg,
                    "score_delta": int(m.u32(A_SCORE)) - score0}
        slots = census(m)
        sv = {s["slot"]: s for s in slots
              if s["slot"] in (10, 11, 12) and (s["st"] or s["hpA4"])}
        J({"ev": "pw_rear2_census", "cycle": k,
           "px": round(px_of(m), 1), "php": int(m.u16(PLAYER_HP)),
           "gren": int(m.u8(GRENADES)),
           "slots": {k2: {"st": v["st"], "hp": v["hpA4"],
                          "sx": v["sx"]}
                     for k2, v in sv.items()},
           "score": int(m.u32(A_SCORE))})
        armed = [s for s in sv.values() if s["st"] in CHOPPER_ST
                 and s["hpA4"] > 0]
        for s_slot, s in sv.items():
            hist = dmg.setdefault(s_slot, [])
            if hist and s["hpA4"] < hist[-1]["hpA4"]:
                J({"ev": "PW_HP_DROP", "cycle": k, "slot": s_slot,
                   "from": hist[-1]["hpA4"], "to": s["hpA4"],
                   "score": int(m.u32(A_SCORE))})
                hist.append(s)
            elif not hist:
                hist.append(s)
        for s_slot in list(dmg):
            if s_slot not in sv or sv[s_slot]["hpA4"] == 0:
                kills.append({"cycle": k, "slot": s_slot})
                J({"ev": "PW_REAR_KILL", "cycle": k, "slot": s_slot,
                   "score": int(m.u32(A_SCORE))})
                del dmg[s_slot]
        if not armed:
            J({"ev": "PW_REAR_CLEAR", "cycle": k,
               "score": int(m.u32(A_SCORE))})
            return {"stop": "ARMED_EMPTY", "kills": kills, "dmg": dmg,
                    "score_delta": int(m.u32(A_SCORE)) - score0,
                    "final_px": round(px_of(m), 1)}
        if not turned:
            p.core.run(2, {"LEFT"})
            p.core.run(1, set())
            turned = True
        gren = int(m.u8(GRENADES))
        if gren > 0 and k % 2 == 0:
            p.core.run(6, {"A", "LEFT"})
            p.core.run(38, set())
        elif gren > 0:
            p.core.run(3, {"B"})
            p.core.run(6, set())
            p.core.run(8, {"UP", "A", "LEFT"})
            p.core.run(30, set())
        else:
            p.core.run(8, {"UP", "Y", "LEFT"})
            p.core.run(20, set())
    return {"stop": "CYCLES", "kills": kills, "dmg": dmg,
            "score_delta": int(m.u32(A_SCORE)) - score0,
            "final_px": round(px_of(m), 1)}


def watch_phase(p, m, J, max_frames=21000, sample=60):
    """Keep killing respawn cycles; poll the block every `sample` f.

    Returns the watch result; the PollDiffIndex rides on `out["idx"]`."""
    idx = PollDiffIndex(BLOCK_LO, BLOCK_HI)
    out = {"idx": idx, "kills": [], "kill_frames": [],
           "squadron_fell": [], "sightings": [], "polls": [],
           "dmg_events": 0, "survived": False, "frames": 0,
           "released": False, "score_delta": 0, "watched_series": []}
    t0f = p.core.frames_run
    score0 = int(m.u32(A_SCORE))
    hp_hist: dict[int, int] = {}
    armed_prev = 0
    chunk = 0
    jump_cd = 0
    released = False
    png(p, "pw_watch_start.png")
    while p.core.frames_run - t0f < max_frames:
        if not alive(m):
            out["frames"] = p.core.frames_run - t0f
            out["score_delta"] = int(m.u32(A_SCORE)) - score0
            J({"ev": "PW_DEATH", "watch_frames": out["frames"],
               "kills": len(out["kills"]),
               "squadron_fell": len(out["squadron_fell"]),
               "score_delta": out["score_delta"]})
            png(p, "pw_watch_death.png")
            return out
        f = p.core.frames_run
        px = px_of(m)
        slots = census(m)
        armed = [s for s in slots if s["st"] in CHOPPER_ST
                 and s["hpA4"] > 0]
        th = [s for s in slots
              if s["st"] not in (0x4BE4, 0x5CC8) and s["hpA4"] > 0
              and 0 < s["sx"] < 320]
        wv = watched_values(m)
        blk = bytes(bytearray(m.ram[BLOCK_LO:BLOCK_HI]))
        ch = idx.add_poll(f, blk)
        out["sightings"].append({"frame": f, "armed": bool(armed),
                                 "n_armed": len(armed)})
        out["watched_series"].append({"frame": f, **wv})
        for s in armed:
            prev_hp = hp_hist.get(s["slot"])
            if prev_hp is not None and s["hpA4"] < prev_hp:
                out["dmg_events"] += 1
                J({"ev": "PW_WATCH_HP_DROP", "frame": f,
                   "slot": s["slot"], "from": prev_hp,
                   "to": s["hpA4"], "score": int(m.u32(A_SCORE))})
            hp_hist[s["slot"]] = s["hpA4"]
        for s_slot in list(hp_hist):
            live = [x for x in armed if x["slot"] == s_slot]
            if not live or live[0]["hpA4"] == 0:
                out["kill_frames"].append(f)
                out["kills"].append({"frame": f, "slot": s_slot,
                                     "score": int(m.u32(A_SCORE))})
                J({"ev": "PW_KILL", "frame": f, "slot": s_slot,
                   "score": int(m.u32(A_SCORE))})
                png(p, f"pw_kill_s{s_slot}_f{f:06d}.png")
                del hp_hist[s_slot]
        if armed_prev > 0 and not armed:
            out["squadron_fell"].append(f)
            J({"ev": "SQUADRON_FELL", "frame": f,
               "n_kills_so_far": len(out["kills"]),
               "score": int(m.u32(A_SCORE))})
            png(p, f"pw_fell_f{f:06d}.png")
        armed_prev = len(armed)
        J({"ev": "pw_poll", "chunk": chunk, "frame": f,
           "px": round(px, 1), "php": int(m.u16(PLAYER_HP)),
           "score": int(m.u32(A_SCORE)),
           "gren": int(m.u8(GRENADES)),
           "n_armed": len(armed), "n_threats": len(th),
           "watched": wv, "block_changed_u16": len(ch)})
        if chunk % 10 == 0:
            png(p, f"pw_watch_c{chunk:04d}.png")
        if px > PIN_PX + 20.0:
            released = True
            J({"ev": "PX_ADVANCED_PAST_PIN", "px": round(px, 1)})
        chunk += 1
        # ---- tactics: keep killing, stay alive at the edge ----
        near = min(th, key=lambda s: abs(s["sx"] - 120)) if th else None
        near_d = abs(near["sx"] - 120) if near else 999
        behind = [s for s in armed if s["x"] < px - 20]
        if behind:
            gren = int(m.u8(GRENADES))
            p.core.run(2, {"LEFT"})
            p.core.run(1, set())
            if gren > 0:
                p.core.run(6, {"A", "LEFT"})
                p.core.run(38, set())
            else:
                p.core.run(8, {"UP", "Y", "LEFT"})
                p.core.run(20, set())
        elif armed:
            tgt = min(armed, key=lambda s: abs(s["x"] - px))
            d = "RIGHT" if tgt["x"] >= px else "LEFT"
            up = {"UP", "Y", d} if tgt["h"] < 45 else {"Y", d}
            p.core.run(24, up)
            p.core.run(16, set())
        elif th:
            if px < PIN_PX - 60.0:
                p.core.run(40, {"RIGHT"})
                p.core.run(20, set())
            elif near_d < 45 and jump_cd <= 0:
                d = "RIGHT" if near["sx"] > 120 else "LEFT"
                p.core.run(12, {"B"})
                jump_cd = 6
            elif near_d < 100:
                d = "RIGHT" if near["sx"] > 120 else "LEFT"
                p.core.run(28, {"Y", d})
                p.core.run(12, set())
            else:
                p.core.run(60, set())
            jump_cd -= 1
        else:
            p.core.run(60, set())
    out["frames"] = p.core.frames_run - t0f
    out["score_delta"] = int(m.u32(A_SCORE)) - score0
    p0 = px_of(m)
    p.core.run(300, {"RIGHT"})
    p1 = px_of(m)
    adv = round(p1 - p0, 1)
    J({"ev": "PW_WALK_PROBE", "px0": round(p0, 1), "px1": round(p1, 1),
       "advance": adv, "released": adv >= 100.0})
    png(p, "pw_watch_probe.png")
    out["survived"] = True
    out["probe_advance"] = adv
    out["released"] = released or adv >= 100.0
    if adv >= 100.0:
        try:
            p.save_state("wr9_unlocked")
            J({"ev": "STATE_SAVED", "state": "wr9_unlocked"})
        except Exception as e:                         # noqa: BLE001
            J({"ev": "STATE_SAVE_FAIL", "err": repr(e)[:120]})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--watch-frames", type=int, default=21000)
    ap.add_argument("--restores", type=int, default=2)
    ap.add_argument("--kill-cycles", type=int, default=60)
    ap.add_argument("--max-s", type=float, default=700.0)
    args = ap.parse_args()
    os.makedirs(OUTDIR, exist_ok=True)
    t0 = time.time()
    trace = JsonlTrace(os.path.join(OUTDIR, "trace.jsonl"))

    def J(ev):
        ev["t"] = round(time.time() - t0, 1)
        trace.write(ev)

    p, fw = boot()
    m = p.mem
    g = ensure_mission(p, tries=6, log=log, want_hp_cands=False)
    J({"ev": "boot", "fw": fw, "in_mission": bool(g.get("in_mission"))})
    if not g.get("in_mission"):
        json.dump({"verdict": "GATE_FAILED"}, open(
            os.path.join(OUTDIR, "report.json"), "w"), indent=1)
        return 2

    # v2 fix: poll the block index THROUGH the kill phases too.  The v1
    # run indexed only the passive watch windows, so the front/rear
    # kills (which happen before the watch) were invisible to the
    # kill_exact classifier.  A core.run shim polls the block + score
    # after EVERY run call in every phase (front / rear / watch), and
    # records score-step (+>=400) events as kill frames.
    gidx = PollDiffIndex(BLOCK_LO, BLOCK_HI)
    shim_kill_frames: list[int] = []
    orig_run = p.core.run
    score_state = {"prev": None}

    def run_shim(frames, buttons):
        orig_run(frames, buttons)
        try:
            f = p.core.frames_run
            gidx.add_poll(f, bytes(bytearray(
                m.ram[BLOCK_LO:BLOCK_HI])))
            sc = int(m.u32(A_SCORE))
            prev = score_state["prev"]
            if prev is not None and sc - prev >= 400:
                shim_kill_frames.append(f)
            score_state["prev"] = sc
        except Exception:                              # noqa: BLE001
            pass

    p.core.run = run_shim
    try:
        p.load_state(STATE)
    except Exception as e:                             # noqa: BLE001
        json.dump({"verdict": "NO_STATE", "err": repr(e)[:160]},
                  open(os.path.join(OUTDIR, "report.json"), "w"),
                  indent=1)
        return 3
    J({"ev": "state_loaded", "px": round(px_of(m), 1),
       "score": int(m.u32(A_SCORE)), "php": int(m.u16(PLAYER_HP)),
       "gren": int(m.u8(GRENADES)),
       "watched": watched_values(m)})
    png(p, "pw_post_load.png")

    front = kill_phase(p, m, J, args.kill_cycles)
    J({"ev": "FRONT_DONE", "stop": front["stop"],
       "n_kills": len(front.get("kills", [])),
       "score_delta": front.get("score_delta")})
    if front["stop"] == "DEATH":
        p.load_state(STATE)
        J({"ev": "restore_after_front_death", "disclosed": True})
        front = kill_phase(p, m, J, args.kill_cycles)
    rear = surgical_rear(p, m, J)
    J({"ev": "REAR_DONE", "stop": rear["stop"],
       "n_kills": len(rear.get("kills", [])),
       "score_delta": rear.get("score_delta")})

    watches = []
    idxs = []
    restores = 0
    for attempt in range(args.restores + 1):
        if attempt > 0:
            try:
                p.load_state(STATE)
            except Exception:                          # noqa: BLE001
                break
            restores += 1
            J({"ev": "restore", "attempt": attempt, "disclosed": True,
               "reason": "watch death (savestate retry, NOT a "
                         "continue)"})
            f2 = kill_phase(p, m, J, 40)
            J({"ev": "REFRONT_DONE", "stop": f2["stop"],
               "n_kills": len(f2.get("kills", []))})
            if f2["stop"] == "DEATH":
                continue
            r2 = surgical_rear(p, m, J)
            J({"ev": "REREAR_DONE", "stop": r2["stop"]})
        w = watch_phase(p, m, J, args.watch_frames)
        idxs.append(w.pop("idx"))
        watches.append(w)
        if w["survived"] or w.get("released"):
            break
        if time.time() - t0 > args.max_s:
            J({"ev": "time_wall"})
            break

    # ---- analysis: block word transitions vs kill events ----
    # v2: union of shim kill frames (front/rear/watch score steps) and
    # watch-phase census kill frames; classify the GLOBAL index (which
    # now covers the kill phases) plus the per-attempt watch indexes.
    kill_frames = sorted({kf for w in watches for kf in w["kill_frames"]}
                         | set(shim_kill_frames))
    all_labeled: dict[int, dict] = {}
    lab = gidx.classify(kill_frames)
    for off, rec in lab.items():
        rec["attempt"] = "all_phases"
        all_labeled[off] = {**rec, "addr": rec["addr"]}
    for i, idx in enumerate(idxs):
        lab = idx.classify(kill_frames)
        for off, rec in lab.items():
            rec["attempt"] = i
            cur = all_labeled.get(off)
            if cur is None or rec["class"].startswith("kill_exact"):
                all_labeled[off] = {**rec, "addr": rec["addr"]}
    classes = {}
    for off, rec in all_labeled.items():
        classes.setdefault(rec["class"], []).append(rec)
    for k in classes:
        classes[k].sort(key=lambda r: (-r["n_flips"], r["addr"]))
    exact = classes.get("kill_exact", [])

    # watched-global transitions at kill events (persistent-change rule)
    glob_trans = {}
    for i, w in enumerate(watches):
        ser = w["watched_series"]
        for name in list(WATCHED) + ["FLAGS_WORD"]:
            vals = [s[name] for s in ser]
            for j in range(1, len(vals)):
                if vals[j] != vals[j - 1]:
                    at_kill = any(abs(ser[j]["frame"] - kf) <= 120
                                  for kf in kill_frames)
                    holds = all(v == vals[j] for v in vals[j:j + 5])
                    glob_trans.setdefault(name, []).append({
                        "attempt": i,
                        "frame": ser[j]["frame"],
                        "from": vals[j - 1], "to": vals[j],
                        "near_kill": at_kill, "holds_5": holds})
    glob_sig = {k: [t for t in v if t["near_kill"] and t["holds_5"]]
                for k, v in glob_trans.items()}
    glob_sig = {k: v for k, v in glob_sig.items() if v}

    waves = count_waves([s for w in watches for s in w["sightings"]])
    total_kills = sum(len(w["kills"]) for w in watches)
    total_fell = sum(len(w["squadron_fell"]) for w in watches)
    released = any(w.get("released") for w in watches)

    if exact or glob_sig:
        verdict = "PROGRESS_WORD_FOUND"
        detail = {
            "kill_exact_words": [
                {"addr": hex(r["addr"]), "n_flips": r["n_flips"],
                 "first_flip": r["first_flip"], "attempt": r["attempt"]}
                for r in exact[:24]],
            "global_transitions_at_kills": glob_sig}
    else:
        verdict = "NEGATIVE"
        detail = {
            "kill_exact_words": [],
            "class_counts": {k: len(v) for k, v in classes.items()},
            "global_transitions": {k: v[:8]
                                   for k, v in glob_trans.items()}}
    rep = {"schema": "ps1play-r11-progress-watch/1", "verdict": verdict,
           "state": STATE, "pin_px": PIN_PX,
           "block": [hex(BLOCK_LO), hex(BLOCK_HI)],
           "kill_events": total_kills, "squadron_fell_events": total_fell,
           "dmg_events": sum(w["dmg_events"] for w in watches),
           "waves": waves, "camera_released": released,
           "watches": [{k: v for k, v in w.items()
                        if k not in ("kill_frames",)}
                       for w in watches],
           "restores_disclosed": restores, "continues_used": 0,
           "detail": detail,
           "frames": p.core.frames_run,
           "wall_s": round(time.time() - t0, 1)}
    json.dump(rep, open(os.path.join(OUTDIR, "report.json"), "w"),
              indent=1)
    # full candidate table
    json.dump({hex(off): rec for off, rec in all_labeled.items()},
              open(os.path.join(OUTDIR, "word_candidates.json"), "w"),
              indent=1)
    J({"ev": "run_end", "verdict": verdict,
       "kill_exact": len(exact), "kills": total_kills})
    log("done:", verdict, "kill_exact words:", len(exact),
        "kills:", total_kills, "fell:", total_fell,
        "released:", released)
    return 0


if __name__ == "__main__":
    sys.exit(main())
