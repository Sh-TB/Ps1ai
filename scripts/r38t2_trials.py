#!/usr/bin/env python3
"""r38t2_trials.py — R38 phase TRIALS (boot 2 of the disclosed cap 3).

From the rebuilt checkpoint `r38_ckpt` (px in [810, 868]):

  trialA x2 : the SHIPPED ps1play.agent.combat.CombatPolicy — 15f
              micro-chunks, cap 480 chunks (7200f). Full telemetry:
              per-chunk section state/flags, score, grenades, php
              (INDICATOR ONLY - never an oracle), deaths, and a full
              40-slot entity census (slot, x_px, +0x8E, +0xA4, st, h)
              so truck/chopper/soldiers are tracked wherever they sit
              (the slot-33 lesson).
  trialB x1 : control - pure RIGHT hold, matched 7200f budget. The
              R35 survivor behaviour; isolates what engagement adds.

SUCCESS ORACLE (Task 4/8): score events (kills), walker state 0xC /
(0,8)->(0xC,9) pre-banner path, MISSION 1 banner PNG. +0x8E is NEVER
in the oracle (R38 capsule contradiction rule).

Task-5 discriminators read straight off the telemetry (no extra boot):
  - grenades spent while truck hp_a4 flat  -> throws not connecting
    (geometry), NOT damage-absorption;
  - grenades flat while truck in range     -> policy never engaged;
  - hp_a4 steps of -100 with score +400/+800 -> VERIFIED damage events.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

from PIL import Image                                     # noqa: E402

_REPO = "/home/z/my-project/ps1ai"
for _p in (_REPO, os.path.join(_REPO, "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from ps1play import labconfig                            # noqa: E402
from ps1play.telemetry import JsonlTrace                 # noqa: E402
import ps1play.agent.combat as combat                    # noqa: E402
from issue4_controller import boot, boot_to_demo         # noqa: E402

SCRATCH = os.path.join(_REPO, "scratch", "r38")
LEDGER = os.path.join(SCRATCH, "boots_used.json")
CKPT = "r38_ckpt"
TABLE, STRIDE, SLOTS = combat.TABLE, combat.STRIDE, 40
PLAYER_X = 0x0CA2E0
A_SCORE = 0x0EE318
GRENADES = 0x0EDCF4
PLAYER_HP = 0x0CA2F6          # indicator only (R38 contradiction rule)
A_FLAGS = 0x0EE518
COMMIT_EVID = os.path.join(_REPO, "data", "games", "SLUS-01212",
                           "truck_evidence", "r38")


def log(*a):
    print("[r38-trial]", *a, file=sys.stderr, flush=True)


def amend_ledger(reason):
    with open(LEDGER) as f:
        led = json.load(f)
    led["count"] = int(led.get("count", 0)) + 1
    led.setdefault("log", []).append(
        {"n": led["count"], "ts": time.strftime("%FT%TZ", time.gmtime()),
         "script": "r38t2_trials.py", "reason": reason})
    with open(LEDGER, "w") as f:
        json.dump(led, f, indent=1)
    log(f"boot ledger: count={led['count']}/{led['cap']} ({reason})")
    return led["count"]


def px_of(m):
    return int(m.u32(PLAYER_X)) / 65536.0


def alive(m):
    return (int(m.u32(A_FLAGS)) & 0xFF) == 0xFF and px_of(m) != 0.0


def snap(m):
    return {"px": round(px_of(m), 1), "score": int(m.u32(A_SCORE)),
            "gren": int(m.u8(GRENADES)), "php": int(m.u16(PLAYER_HP)),
            "sec": (int(m.u16(combat.SECTION_STATE)),
                    int(m.u16(combat.SECTION_FLAGS))),
            "prog": int.from_bytes(
                m.ram[0xEB5D4:0xEB5D8].tobytes(), "little")}


def census(m, px):
    """Full 40-slot read-only census (unfiltered, the slot-33 lesson)."""
    out = []
    for s in range(1, SLOTS):
        base = TABLE + s * STRIDE
        xw = int(m.u32(base + 0x78))
        if not xw:
            continue
        f8e = int(m.u16(base + 0x8E))
        if not f8e:
            continue
        out.append({"slot": s,
                    "x": round(xw / 65536.0, 1),
                    "f8e": f8e,
                    "a4": int(m.u16(base + 0xA4)),
                    "st": int(m.u16(base)),
                    "h": int(m.u16(base + 0x7E))})
    return out


def png(p, name, tag):
    d = os.path.join(SCRATCH, "png", tag)
    os.makedirs(d, exist_ok=True)
    rgb = p.core.frame_rgb()
    if rgb is not None:
        Image.fromarray(rgb).save(os.path.join(d, name + ".png"))
    return d


def wait_alive(m, p, wait=60):
    for _ in range(wait):
        p.core.run(30, set())
        if alive(m):
            return True
    return False


def run_trial(p, m, tag, arm, chunks_cap, jf):
    """One trial from the pristine checkpoint. arm: 'policy'|'right'."""
    J = lambda ev: (jf.write(json.dumps(ev, default=str) + "\n"),
                    jf.flush())
    p.load_state(CKPT)
    pol = combat.CombatPolicy()
    J({"ev": "start", "arm": arm, "tag": tag, **snap(m)})
    log(f"=== {tag} arm={arm} ===")

    # settle after restore (the trial harness convention: 2f warmup)
    p.core.run(2, set())
    deaths = 0
    outcome, end_c = None, None
    last_px, last_segs = None, None
    score_events = []           # (chunk, from, to) verified kill oracle
    prev_score = int(m.u32(A_SCORE))
    truck_trace = []            # (chunk, truck_a4, gren) discriminator
    t0 = time.time()
    for c in range(chunks_cap):
        s = snap(m)
        if not alive(m):
            deaths += 1
            J({"ev": "death", "chunk": c, **s})
            if not wait_alive(m, p):
                outcome = "death_no_respawn"
                break
            last_px, last_segs = None, None
            continue
        if px_of(m) > 5000.0:
            p.core.run(60, set())          # mission-transition garbage
            continue
        px_early = px_of(m)
        sec = combat.scan_section(m)
        pol.observe_section(sec, px_now=px_early)
        px = px_of(m)
        advanced = 0.0 if last_px is None else px - last_px
        intent = any("RIGHT" in (x.get("btns") or set())
                     for x in (last_segs or []))
        pol.observe(px, advanced, intent)
        scan = combat.scan_entities(m, px=px)
        if arm == "policy":
            segs = pol.decide(15, px, scan,
                              grenades=int(m.u8(GRENADES)),
                              hp=int(m.u16(PLAYER_HP)))
        else:
            segs = [{"frames": 60, "btns": {"RIGHT"}}]
        last_px, last_segs = px, segs
        pre_sec = (int(m.u16(combat.SECTION_STATE)),
                   int(m.u16(combat.SECTION_FLAGS)))
        for x in segs:
            p.core.run(x["frames"], x["btns"] or set())
        post_sec = (int(m.u16(combat.SECTION_STATE)),
                    int(m.u16(combat.SECTION_FLAGS)))
        if pre_sec != post_sec:
            png(p, f"sec_{post_sec[0]:02x}_{post_sec[1]:02x}", tag)
            J({"ev": "sec_transition", "chunk": c, "from": pre_sec,
               "to": post_sec, **snap(m)})
        s2 = snap(m)
        if s2["score"] != prev_score:
            score_events.append({"chunk": c, "from": prev_score,
                                 "to": s2["score"]})
            J({"ev": "SCORE_EVENT", "chunk": c, "from": prev_score,
               "to": s2["score"], "mode": pol.mode})
            prev_score = s2["score"]
        # truck discriminator: track the FIRST armored slot (a4>0)
        cen = census(m, px)
        tr = [e for e in cen if 0 < e["a4"] <= 600 and e["h"] == 64]
        if tr:
            truck_trace.append({"chunk": c, "a4": tr[0]["a4"],
                                "gren": s2["gren"],
                                "x": tr[0]["x"], "st": tr[0]["st"]})
        J({"ev": "chunk", "c": c, "mode": pol.mode,
           "sec": s2["sec"], "px": s2["px"], "score": s2["score"],
           "gren": s2["gren"], "php": s2["php"],
           "n_census": len(cen),
           "census": cen if c % 5 == 0 or tr or len(cen) < 8 else None})
        if s2["sec"][0] == 0xC and s2["px"] < 200.0:
            outcome = "MISSION_BANNER"
            end_c = c
            png(p, "mission_banner", tag)
            J({"ev": "MISSION_BANNER", "chunk": c, **s2})
            break
        if s2["px"] < 200.0 and c > 4 and s2["sec"][0] in (0xB, 0x0):
            outcome = "banner_expired_restart"
            end_c = c
            png(p, "restart_seen", tag)
            J({"ev": "RESTART_SEEN", "chunk": c, **s2})
            break
        if s2["sec"][0] == 0xC and pol.mission_end:
            outcome = "mission_end_latched"
            end_c = c
            png(p, "mission_end_latched", tag)
            J({"ev": "MISSION_END_LATCHED", "chunk": c, **s2})
            break
    else:
        outcome = "budget"
    png(p, "final", tag)
    res = {"tag": tag, "arm": arm, "outcome": outcome,
           "end_chunk": end_c, "deaths": deaths,
           "frames_budget": chunks_cap * 15 if arm == "policy" else
           chunks_cap * 60,
           "wall_s": round(time.time() - t0, 1),
           "score_events": score_events,
           "score_final": int(m.u32(A_SCORE)),
           "truck_trace_tail": truck_trace[-12:],
           "truck_a4_min": min((t["a4"] for t in truck_trace),
                               default=None),
           "grenades_spent": (truck_trace[0]["gren"] -
                              truck_trace[-1]["gren"])
           if len(truck_trace) >= 2 else None,
           "pol_stats": {k: v for k, v in pol.stats.items() if v},
           "final": snap(m)}
    J({"ev": "RUN_DONE", **res})
    log(f"{tag}: {outcome} c={end_c} deaths={deaths} "
        f"score={res['score_final']}")
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--chunks", type=int, default=480,
                    help="cap per policy trial (15f micro-chunks)")
    ap.add_argument("--runs", type=int, default=2)
    args = ap.parse_args()
    os.makedirs(SCRATCH, exist_ok=True)
    os.makedirs(COMMIT_EVID, exist_ok=True)

    n = amend_ledger("TRIALS: boot_to_demo -> load r38_ckpt x3 arms")
    if n > 3:
        raise SystemExit("BOOT CAP EXCEEDED")
    p, fw = boot_to_demo(), None
    m = p.mem
    p.load_state(CKPT)
    if not alive(m):
        raise SystemExit("r38_ckpt not alive after restore - wrong "
                         "workspace or wiped checkpoint")

    results = []
    jf = open(os.path.join(SCRATCH, "trials.jsonl"), "w")
    for r in range(args.runs):
        results.append(run_trial(p, m, f"trialA{r + 1}", "policy",
                                 args.chunks, jf))
    results.append(run_trial(p, m, "trialB_control", "right",
                             max(1, args.chunks * 15 // 60), jf))
    jf.close()

    rep = {"schema": "ps1play.r38-d7-trial/1",
           "generated": time.strftime("%FT%TZ", time.gmtime()),
           "commit_head": os.popen(
               "git -C %s rev-parse HEAD" % _REPO).read().strip(),
           "checkpoint": CKPT,
           "checkpoint_report": json.load(
               open(os.path.join(SCRATCH, "reach_report.json"))),
           "game_sha256":
               "45cde149878fe945d0219fd0f61ca09856aee66bdcc9119de21c0583"
               "f1d0667d",
           "oracle": "score events + walker 0xC / pre-banner (0,8)->"
                     "(0xC,9) + banner PNG; +0x8E excluded (R38 rule)",
           "runs": results,
           "wall_s_total": round(sum(r["wall_s"] for r in results), 1)}
    out = os.path.join(SCRATCH, "trial_report.json")
    with open(out, "w") as f:
        json.dump(rep, f, indent=1)
    compact = {k: rep[k] for k in ("schema", "generated", "commit_head",
                                   "checkpoint", "oracle", "runs",
                                   "wall_s_total")}
    with open(os.path.join(COMMIT_EVID, "r38_trial_report.json"),
              "w") as f:
        json.dump(compact, f, indent=1)
    log("report ->", out, "+ compact ->", COMMIT_EVID)
    return 0


if __name__ == "__main__":
    sys.exit(main())
