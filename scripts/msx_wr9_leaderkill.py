#!/usr/bin/env python3
"""msx_wr9_leaderkill.py — Round 9 task 9-a (Issue #7): the targeted
RED-leader chopper-kill attempt series at the town-arena camera gate.

ONE beetle boot per process (hard rule 1).  boot -> gate -> load_state
`wr9_arena` (captured by msx_wr9_arena.py at arena entry) -> run ONE arm:

  YB   sustained AIMED UP+FIRE ("UP+Y") bursts at the RED leader
       (redness proxy near the chopper's screen-x), else nearest chopper —
       the web strategy (arcadequartermaster MS2 M1: the squadron falls
       with its red leader).
  J1   hop + UP-lob (UP+A) at the jump apex — the session-3 proven
       chopper recipe (3 connects: hp_a4 300->200->100->0, |dx| 7..29).
  GR   grenade economy: flat lobs at the armored truck (100 dmg,
       |dx| 53..135 proven) alternating ground UP-lobs at choppers.
  MIX  YB x3 + J1 x2 + GR x1 rotation.
  C    no-input control (chopper/truck behaviour baseline).

Observables every cycle (all read-only, VERIFIED addrs):
  chopper slots (st 0xAA94/0xABDC) hp_a4 300->0 drops, kills, squadron
  collapse (ALL chopper slots empty within 600f of a kill), truck hp_a4
  drops, score deltas, deaths.  Resolution test after the last set-piece
  combatant dies: walk-right probe (300f RIGHT) — px advance >= 100 =>
  CAMERA_UNLOCKED; savestate wr9_unlocked + optional sensor walk to the
  train yard (--walk-chunks > 0).

No cheats, no RAM writes.  wr9_ state restores are retries (disclosed),
not continues.  Evidence: JSONL + PNGs + report.json.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

import numpy as np
from PIL import Image

_REPO = "/home/z/my-project/ps1ai"
for _p in (_REPO, os.path.join(_REPO, "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from ps1play.telemetry import JsonlTrace                    # noqa: E402
from ps1play.agent.wagon import WagonSensor                 # noqa: E402
from issue4_controller import boot                          # noqa: E402
from mission import ensure_mission                          # noqa: E402

SCRATCH = "/home/z/my-project/ps1ai/scratch/issue6_round9_msx"
OUTDIR = os.path.join(SCRATCH, "leaderkill")

PLAYER_X = 0x0CA2E0
PLAYER_HP = 0x0CA2F6
A_SCORE = 0x0EE318
GRENADES = 0x0EDCF4
FLAGS_WORD = 0x0EE518
TABLE, STRIDE = 0x0CA268, 0x14C
# r9 cap2 lesson: the arena pin (px 2212) is held by THREE 300-HP
# ground enemies of family 0xA0D0 (cap2/report.json census: slots 10-12,
# hpA4 300, h 63) plus a related 0xAB94 flyer — same armored-HP class as
# the choppers (300).  Extended targetable set (disclosed in report).
CHOPPER_ST = (0xAA94, 0xABDC, 0xA0D0, 0xAB94)
TRUCK_ST = (0x9E88,)
FALLER_ST = 0xB4E4
CORPSE_ST = (0x4BE4, 0x5CC8)


def log(*a):
    print("[wr9-lk]", *a, file=sys.stderr, flush=True)


def px_of(m):
    return int(m.u32(PLAYER_X)) / 65536.0


def alive(m):
    return (int(m.u32(FLAGS_WORD)) & 0xFF) == 0xFF and px_of(m) != 0.0 \
        and int(m.u16(PLAYER_HP)) > 0


def census(m):
    tv = m.ram[TABLE:TABLE + 36 * STRIDE].view("<u2").astype(np.int32) \
        .reshape(36, STRIDE // 2)
    out = []
    for s in range(1, 36):
        st = int(tv[s, 0])
        xw = (int(tv[s, 61]) << 16) | int(tv[s, 60])
        if not st and not xw:
            continue
        out.append({"slot": s, "st": st,
                    "x": round(xw / 65536.0, 1), "h": int(tv[s, 63]),
                    "sx": int(tv[s, 71]), "hpA4": int(tv[s, 82])})
    return out


def choppers(slots):
    return [s for s in slots if s["st"] in CHOPPER_ST and s["hpA4"] > 0]


def trucks(slots):
    return [s for s in slots if s["hpA4"] >= 100 and s["h"] <= 40
            and s["st"] in TRUCK_ST]


def redness(rgb, sx):
    if rgb is None:
        return None
    h, w = rgb.shape[:2]
    c0, c1 = max(0, sx - 10), min(w, sx + 11)
    if c1 <= c0 or sx <= 0:
        return None
    win = rgb[0:min(h, 140), c0:c1].astype(np.int16)
    r = win[:, :, 0] - (win[:, :, 1] + win[:, :, 2]) // 2
    return round(float(r.mean(axis=0).max()), 1)


def png(p, name):
    rgb = p.core.frame_rgb()
    if rgb is not None:
        Image.fromarray(rgb).save(os.path.join(OUTDIR, name))
    return rgb


def with_red(p, m, slots):
    rgb = p.core.frame_rgb()
    return [{**s, "red": redness(rgb, s["sx"])} for s in slots]


def pick_target(ch, px):
    """RED leader first (redness proxy, threshold 8), else nearest."""
    if not ch:
        return None, None
    reds = [c for c in ch if (c.get("red") or 0) >= 8.0]
    if reds:
        leader = max(reds, key=lambda c: c["red"])
        return leader, "RED"
    near = min(ch, key=lambda c: abs(c["x"] - px))
    return near, "NEAREST"


def snapshot_census(p, m, J, tag):
    slots = census(m)
    ch = with_red(p, m, choppers(slots))
    tr = trucks(slots)
    snap = {"ev": tag, "frame": p.core.frames_run,
            "px": round(px_of(m), 1), "score": int(m.u32(A_SCORE)),
            "gren": int(m.u8(GRENADES)),
            "php": int(m.u16(PLAYER_HP)),
            "choppers": ch, "trucks": tr,
            "fallers": sum(1 for s in slots if s["st"] == FALLER_ST)}
    J(snap)
    return snap


def run_arm(p, m, J, arm, cycles, lock_px):
    """One leader-kill arm from the wr9_arena restore."""
    hp_hist = {}          # slot -> last hpA4 (choppers)
    truck_hp = {}
    kills = []
    hp_drops = []
    score_events = 0
    deaths = restores = 0
    resolved_streak = 0
    unlocked = False
    squad_fell = False
    red_seen = {}
    s0 = snapshot_census(p, m, J, "arm_start")
    score0 = s0["score"]
    png(p, f"arm_{arm}_start.png")
    for k in range(cycles):
        if not alive(m):
            deaths += 1
            J({"ev": "death", "cycle": k, **{x: s0[x] for x in ()},
               "px": round(px_of(m), 1)})
            log("death in arm", arm, "cycle", k)
            if deaths > 3:
                return {"arm": arm, "stop": "DEATHS", "deaths": deaths,
                        "cycles": k}
            p.load_state("wr9_arena")
            restores += 1
            J({"ev": "restore", "arm": arm, "cycle": k, "n": restores,
               "disclosed": True})
            hp_hist.clear()
            truck_hp.clear()
            s0 = snapshot_census(p, m, J, "arm_restart")
            continue
        px = px_of(m)
        slots = census(m)
        ch = with_red(p, m, choppers(slots))
        tr = trucks(slots)
        sc = int(m.u32(A_SCORE))
        # ---------- hp drop / kill bookkeeping ----------
        for c in ch:
            prev = hp_hist.get(c["slot"])
            if prev is not None and c["hpA4"] < prev:
                hp_drops.append({"cycle": k, "slot": c["slot"],
                                 "from": prev, "to": c["hpA4"],
                                 "red": c.get("red"), "dx":
                                 round(c["x"] - px, 1)})
                J({"ev": "CHOPPER_HP_DROP", "arm": arm, **hp_drops[-1],
                   "score": sc})
                png(p, f"arm_{arm}_hit_{c['slot']}_{k}.png")
            hp_hist[c["slot"]] = c["hpA4"]
            if c.get("red") is not None:
                red_seen.setdefault(c["slot"], []).append(c["red"])
        for c in list(hp_hist):
            if all(x["slot"] != c for x in ch):
                kills.append({"cycle": k, "slot": c,
                              "last_hp": hp_hist.pop(c)})
                J({"ev": "CHOPPER_KILL", "arm": arm, **kills[-1],
                   "score": sc, "remaining": ch})
                png(p, f"arm_{arm}_kill_{c}_{k}.png")
                # squadron-collapse watch: 600f no-input
                fell = True
                for w in range(10):
                    p.core.run(60, set())
                    if not alive(m):
                        break
                    if choppers(census(m)):
                        fell = False
                        break
                if fell and alive(m):
                    squad_fell = True
                    J({"ev": "SQUADRON_FELL", "arm": arm, "cycle": k,
                       "after_kill_slot": c,
                       "score": int(m.u32(A_SCORE))})
                    png(p, f"arm_{arm}_squadfell_{k}.png")
                    log("SQUADRON FELL after slot", c)
                break
        for t in tr:
            prev = truck_hp.get(t["slot"])
            if prev is not None and t["hpA4"] < prev:
                J({"ev": "TRUCK_HP_DROP", "arm": arm, "cycle": k,
                   "slot": t["slot"], "from": prev, "to": t["hpA4"],
                   "score": sc})
                png(p, f"arm_{arm}_truckhit_{k}.png")
            truck_hp[t["slot"]] = t["hpA4"]
        if int(m.u32(A_SCORE)) > sc:
            score_events += 1
        # ---------- resolution / unlock ----------
        if not ch and not tr:
            resolved_streak += 1
        else:
            resolved_streak = 0
        if resolved_streak >= 3:
            J({"ev": "SETPIECE_RESOLVED", "arm": arm, "cycle": k,
               "px": round(px, 1), "score": int(m.u32(A_SCORE))})
            p0 = px
            p.core.run(300, {"RIGHT"})
            p1 = px_of(m)
            unlocked = (p1 - p0) >= 100.0
            J({"ev": "WALK_PROBE", "arm": arm, "px0": round(p0, 1),
               "px1": round(p1, 1), "advance": round(p1 - p0, 1),
               "unlocked": unlocked})
            png(p, f"arm_{arm}_probe_{k}.png")
            if unlocked:
                try:
                    p.save_state("wr9_unlocked")
                    J({"ev": "STATE_SAVED", "state": "wr9_unlocked"})
                except Exception as e:                # noqa: BLE001
                    J({"ev": "STATE_SAVE_FAIL", "err": repr(e)[:120]})
            return {"arm": arm, "stop": "RESOLVED" if unlocked
                    else "RESOLVED_CAMERA_HELD", "cycles": k + 1,
                    "deaths": deaths, "restores": restores,
                    "kills": kills, "hp_drops": hp_drops,
                    "squadron_fell": squad_fell, "unlocked": unlocked,
                    "score_delta": int(m.u32(A_SCORE)) - score0,
                    "final_px": round(p1, 1)}
        # ---------- arm input ----------
        tgt, why = pick_target(ch, px)
        if tgt is not None:
            dx = round(tgt["x"] - px, 1)
            d = "RIGHT" if dx >= 0 else "LEFT"
        else:
            dx, d = None, "RIGHT"
        gren = int(m.u8(GRENADES))
        if arm == "C":
            p.core.run(60, set())
        elif arm == "YB":
            up = {"UP", "Y", d} if abs(dx or 0) > 4 else {"UP", "Y"}
            p.core.run(24, up)
            p.core.run(16, set())
        elif arm == "J1":
            p.core.run(3, {"B"})
            p.core.run(8, set())
            if gren > 0:
                lob = {"UP", "A"} if abs(dx or 0) <= 4 else {"UP", "A", d}
                p.core.run(8, lob)
            else:
                p.core.run(8, {"UP", "Y", d} if abs(dx or 0) > 4
                           else {"UP", "Y"})
            p.core.run(25, set())
        elif arm == "GR":
            if tr and gren > 0:
                td = "RIGHT" if tr[0]["x"] >= px else "LEFT"
                p.core.run(6, {"A", td})
                p.core.run(34, set())
            elif gren > 0:
                lob = {"UP", "A"} if abs(dx or 0) <= 4 else {"UP", "A", d}
                p.core.run(6, lob)
                p.core.run(34, set())
            else:
                p.core.run(24, {"UP", "Y", d} if abs(dx or 0) > 4
                           else {"UP", "Y"})
                p.core.run(16, set())
        elif arm == "MIX":
            ph = k % 6
            if ph < 3:
                up = {"UP", "Y", d} if abs(dx or 0) > 4 else {"UP", "Y"}
                p.core.run(24, up)
                p.core.run(16, set())
            elif ph < 5 and gren > 0:
                p.core.run(3, {"B"})
                p.core.run(8, set())
                lob = {"UP", "A"} if abs(dx or 0) <= 4 else {"UP", "A", d}
                p.core.run(8, lob)
                p.core.run(25, set())
            elif gren > 0:
                if tr:
                    td = "RIGHT" if tr[0]["x"] >= px else "LEFT"
                    p.core.run(6, {"A", td})
                else:
                    p.core.run(6, {"A", d})
                p.core.run(34, set())
            else:
                p.core.run(40, set())
        if k % 5 == 4:
            snapshot_census(p, m, J, "census")
    snapshot_census(p, m, J, "arm_end")
    return {"arm": arm, "stop": "CYCLES", "cycles": cycles,
            "deaths": deaths, "restores": restores, "kills": kills,
            "hp_drops": hp_drops, "squadron_fell": squad_fell,
            "unlocked": unlocked,
            "score_delta": int(m.u32(A_SCORE)) - score0,
            "final_px": round(px_of(m), 1),
            "red_seen": {str(k): v for k, v in red_seen.items()}}


def walk_phase(p, m, J, chunks):
    """Post-unlock: walk right with the WagonSensor to the train yard."""
    from ps1play.agent.route import RoutePolicy, StallDetector
    sensor = WagonSensor(m.ram, every=10)
    policy = RoutePolicy(allow_grenades=True, jump_enabled=True)
    det = StallDetector()
    train_saved = False
    deaths = 0
    for c in range(chunks):
        if not alive(m):
            deaths += 1
            J({"ev": "walk_death", "c": c})
            if deaths > 3:
                return {"stop": "DEATHS", "sensor": sensor.summary()}
            p.load_state("wr9_unlocked")
            J({"ev": "restore", "phase": "walk", "n": deaths,
               "disclosed": True})
            continue
        segs = policy.decide(60, det)
        for s in segs:
            p.core.run(s["frames"], s["btns"] or set())
            for ev in sensor.poll(p.core.frames_run):
                if ev["type"] == "spawn" and len(sensor.spawns) <= 150:
                    rgb = p.core.frame_rgb()
                    if rgb is not None:
                        Image.fromarray(rgb).save(os.path.join(
                            OUTDIR, f"wspawn_{ev['slot']:02d}_{ev['fp']}_"
                            f"{p.core.frames_run:06d}.png"))
        if c % 40 == 0:
            J({"ev": "walk", "c": c, "px": round(px_of(m), 1),
               "spawns": len(sensor.spawns),
               "score": int(m.u32(A_SCORE))})
            png(p, f"walk_c{c:04d}.png")
        if not train_saved and len(sensor.spawns) >= 10 \
                and len(sensor.persistent_slots()) >= 2:
            png(p, "wr9_trainride.png")
            try:
                p.save_state("wr9_trainride")
                train_saved = True
                J({"ev": "TRAIN_RIDE", "c": c, "px": round(px_of(m), 1),
                   "persistent": sensor.persistent_slots()})
                log("TRAIN_RIDE marker c", c)
            except Exception as e:                    # noqa: BLE001
                J({"ev": "trainride_save_fail", "err": repr(e)[:120]})
    return {"stop": "BUDGET", "sensor": sensor.summary(),
            "train_saved": train_saved, "deaths": deaths}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", default="YB",
                    choices=["C", "YB", "J1", "GR", "MIX"])
    ap.add_argument("--cycles", type=int, default=60)
    ap.add_argument("--walk-chunks", type=int, default=0)
    ap.add_argument("--budget-s", type=float, default=700.0)
    ap.add_argument("--state", default="wr9_arena")
    args = ap.parse_args()
    os.makedirs(OUTDIR, exist_ok=True)
    t0 = time.time()
    tag = f"{args.arm}_{time.strftime('%H%M%S')}"
    trace = JsonlTrace(os.path.join(OUTDIR, f"trace_{tag}.jsonl"))

    def J(ev):
        ev["t"] = round(time.time() - t0, 1)
        trace.write(ev)

    p, fw = boot()                                    # ONE boot
    m = p.mem
    g = ensure_mission(p, tries=6, log=log, want_hp_cands=False)
    J({"ev": "boot", "fw": fw,
       "in_mission": bool(g.get("in_mission"))})
    if not g.get("in_mission"):
        json.dump({"verdict": "GATE_FAILED"}, open(
            os.path.join(OUTDIR, f"report_{tag}.json"), "w"), indent=1)
        return 2
    try:
        p.load_state(args.state)
    except Exception as e:                            # noqa: BLE001
        log("load_state failed:", repr(e)[:200])
        json.dump({"verdict": "NO_STATE", "err": repr(e)[:200]},
                  open(os.path.join(OUTDIR, f"report_{tag}.json"),
                       "w"), indent=1)
        return 3
    J({"ev": "state_loaded", "state": args.state})
    lock_px = px_of(m)
    s = snapshot_census(p, m, J, "post_load")
    png(p, f"post_load_{tag}.png")
    log("loaded", args.state, "px", lock_px, "choppers",
        len(s["choppers"]), "trucks", len(s["trucks"]))
    rep = {"schema": "ps1play-wr9-leaderkill/1", "tag": tag,
           "state": args.state, "lock_px": round(lock_px, 1),
           "post_load": s}
    if args.arm != "C" and not s["choppers"] and not s["trucks"]:
        rep["arm_result"] = {"stop": "NO_COMBATANTS_AT_STATE"}
    else:
        rep["arm_result"] = run_arm(p, m, J, args.arm, args.cycles,
                                    lock_px)
    if rep["arm_result"].get("unlocked") and args.walk_chunks > 0:
        rep["walk"] = walk_phase(p, m, J, args.walk_chunks)
    rep["frames"] = p.core.frames_run
    rep["wall_s"] = round(time.time() - t0, 1)
    json.dump(rep, open(os.path.join(OUTDIR, f"report_{tag}.json"), "w"),
              indent=1)
    J({"ev": "run_end", "stop": rep["arm_result"].get("stop"),
       "wall_s": rep["wall_s"]})
    log("done:", rep["arm_result"].get("stop"),
        "score_delta:", rep["arm_result"].get("score_delta"),
        "kills:", len(rep["arm_result"].get("kills") or []),
        "squad_fell:", rep["arm_result"].get("squadron_fell"),
        "unlocked:", rep["arm_result"].get("unlocked"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
