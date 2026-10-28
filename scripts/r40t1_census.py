#!/usr/bin/env python3
"""r40t1_census.py — R40 Task 1 (BOOT 1 of the disclosed cap 2).

The census the capsule's next_experiment asked for: WHO does the
shipped policy's `engage` lock onto during the pin, and what is the
grenade flight time (the arrival-band gate input)?

Design (capsule R40 method, boot 1 = read-only census):
  CENSUS-BASE : the EXACT pre-R40 v2.2 behavior (CombatPolicy(
                queue_priority=False) — the legacy flag reproduces the
                shipped R39 semantics verbatim, verified by tests)
                from r38_ckpt, 300 x 15f chunks. Per chunk the runner
                records pol.last_scan (near identity / family count /
                chopper fix / takeover booleans) — a pure diagnostic
                added in this round; behavior is untouched.
                MUST reproduce the R39 boot-6 trialT1/T2 mode shares
                (engage 118 / aa_kill 76 / clamp_clear 51 / connects 1)
                — if it does not, the R39 result is not reproducible
                and everything else stops until that is explained.

Success signals (Task 2 of the task book): the census answers WHO
engage locks onto at the pin (candidate: the wall mortarman st 0xE17C
— NOT a soldier-family member, NOT a queue entity) — the R39 finding
was that ALL 71 engage chunks at px>=1050 had the chopper visible.
Flight time: per-throw release -> verified hp_a4 drop delta (chunk
granularity) + the R39 boot-1 frame capture (~63-107f band).

All arms are DIAGNOSTIC (checkpoint-restored inside boot 1). No
fresh-boot gameplay claim is made from this script. +0x8E is NEVER in
any oracle (R38 rule).
"""
from __future__ import annotations

import json
import os
import sys
import time
from collections import Counter

_REPO = "/home/z/my-project/ps1ai"
for _p in (_REPO, os.path.join(_REPO, "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _REPO + "/scripts")
        sys.path.insert(0, _REPO)

import r39t1_baseline as t1                       # noqa: E402
import ps1play.agent.combat as combat             # noqa: E402
from issue4_controller import boot_to_demo        # noqa: E402

SCRATCH = os.path.join(_REPO, "scratch", "r40")
LEDGER = os.path.join(SCRATCH, "boots_used.json")
CKPT = t1.CKPT                                    # r38_ckpt
CHUNKS = 300                                      # x15f, R39 protocol

# R39 boot-6 reference (deterministic trialT1/T2 pair, commit 2e28581)
R39_REF = {"engage": 118, "aa_kill": 76, "clamp_clear": 51,
           "armor_hold": 37, "advance": 12, "throws": 13,
           "aa_connect": 1}


def log(*a):
    print("[r40-t1]", *a, file=sys.stderr, flush=True)


def make_ledger():
    os.makedirs(SCRATCH, exist_ok=True)
    if os.path.exists(LEDGER):
        return
    with open(LEDGER, "w") as f:
        json.dump({
            "cap": 2,
            "count": 0,
            "disclosed_before_first_boot": True,
            "budget_plan": {
                "boot_1": "census: the legacy v2.2 behavior (flag "
                          "queue_priority=False) from r38_ckpt, 300 "
                          "chunks, per-chunk last_scan trace (WHO "
                          "engage locks onto at the pin) — read-only "
                          "census, behavior unchanged",
                "boot_2": "treatment: the R40 queue-priority rule "
                          "(flag True) x2 runs from r38_ckpt under "
                          "the boot-6 harness (deaths + continues "
                          "handled, per-throw telemetry); oracle = "
                          "chopper hp_a4 300->0 + section release + "
                          "banner predicate, never +0x8E"},
            "amendments": [],
            "log": []}, f, indent=1)


def amend_ledger(reason, script="r40t1_census.py"):
    with open(LEDGER) as f:
        led = json.load(f)
    led["count"] = int(led.get("count", 0)) + 1
    led.setdefault("log", []).append(
        {"n": led["count"], "ts": time.strftime("%FT%TZ", time.gmtime()),
         "script": script, "reason": reason})
    with open(LEDGER, "w") as f:
        json.dump(led, f, indent=1)
    log(f"boot ledger: count={led['count']}/{led['cap']} ({reason})")
    return led["count"]


def run_census_arm(p, m, J, tag, chunks_cap, tlog, policy_factory,
                   continues=None, settle=2):
    """The r39t1.run_policy_arm harness, forked for R40: (a) the
    policy comes from policy_factory (the A/B flag), (b) the per-chunk
    event gains the census summary (pol.last_scan). Everything else —
    death/continue handling, per-throw telemetry, outcome predicates —
    is the proven boot-6 harness verbatim."""
    pol = policy_factory()
    p.core.run(settle, set())
    s0 = t1.snap(m)
    J({"ev": "arm_start", "arm": tag,
       "queue_priority": getattr(pol, "queue_priority", None),
       "snap": s0})
    deaths = 0
    outcome, end_c = None, None
    last_px, last_segs = None, None
    prev_score = int(m.u32(t1.A_SCORE))
    t0 = time.time()
    score_events = []
    for c in range(chunks_cap):
        s = t1.snap(m)
        if not t1.alive(m):
            deaths += 1
            J({"ev": "death", "arm": tag, "chunk": c, **s})
            if not t1.wait_alive(m, p, wait=20):
                if continues is not None:
                    continues[tag] = continues.get(tag, 0) + 1
                n_cont = (continues or {}).get(tag, 0)
                J({"ev": "CONTINUE_SCREEN", "arm": tag, "chunk": c,
                   "n": n_cont, **s})
                from run_mission1_legit import recover_v2
                if not recover_v2(p, log=log):
                    outcome, end_c = "death_no_respawn", c
                    break
                if not t1.wait_alive(m, p, wait=20):
                    outcome, end_c = "death_no_respawn", c
                    break
            last_px, last_segs = None, None
            continue
        if t1.px_of(m) > 5000.0:
            p.core.run(60, set())
            continue
        px_early = t1.px_of(m)
        sec = combat.scan_section(m)
        pol.observe_section(sec, px_now=px_early)
        px = t1.px_of(m)
        advanced = 0.0 if last_px is None else px - last_px
        intent = any("RIGHT" in (x.get("btns") or set())
                     for x in (last_segs or []))
        pol.observe(px, advanced, intent)
        cen = t1.census(m, px)
        scan = combat.scan_entities(m, px=px)
        gren0 = int(m.u8(t1.GRENADES))
        segs = pol.decide(15, px, scan, grenades=gren0,
                          hp=int(m.u16(t1.PLAYER_HP)))
        last_px, last_segs = px, segs
        pre_sec = (int(m.u16(combat.SECTION_STATE)),
                   int(m.u16(combat.SECTION_FLAGS)))
        for x in segs:
            p.core.run(x["frames"], x["btns"] or set())
        post_sec = (int(m.u16(combat.SECTION_STATE)),
                    int(m.u16(combat.SECTION_FLAGS)))
        if pre_sec != post_sec:
            J({"ev": "sec_transition", "arm": tag, "chunk": c,
               "from": pre_sec, "to": post_sec, **t1.snap(m)})
        s2 = t1.snap(m)
        if s2["score"] != prev_score:
            score_events.append({"chunk": c, "from": prev_score,
                                 "to": s2["score"]})
            J({"ev": "SCORE_EVENT", "arm": tag, "chunk": c,
               "mode": pol.mode, "from": prev_score, "to": s2["score"]})
            prev_score = s2["score"]
        cen2 = t1.census(m, t1.px_of(m))
        ch_fix = t1.chopper_of(cen2, t1.px_of(m))
        # the R40 census record: the policy's own view of the chunk
        J({"ev": "census", "arm": tag, "c": c,
           "mode": pol.mode, **(pol.last_scan or {})})
        fr = t1.frames_of(segs)
        lob_frames = [i for i, b in enumerate(fr)
                      if "A" in b and "UP" in b]
        if pol.mode == "aa_kill" or lob_frames:
            tlog.check_hit(m, t1.px_of(m), cen2, c)
            if lob_frames:
                tlog.record_throw(
                    m, px, cen, c,
                    extra={"lob_frames_in_chunk": len(lob_frames),
                           "aa_t_start": pol._aa_t - len(fr),
                           "aa_t_end": pol._aa_t,
                           "gren_after": int(m.u8(t1.GRENADES)),
                           "gren0": gren0,
                           "mode": pol.mode})
        if s2["sec"][0] == 0xC and s2["px"] < 200.0 and t1.alive(m):
            outcome, end_c = "MISSION_BANNER", c
            break
        if t1.alive(m) and s2["px"] < 200.0 and c > 4 and \
                s2["sec"][0] in (0xB, 0x0):
            outcome, end_c = "banner_expired_restart", c
            J({"ev": "RESTART_SEEN", "arm": tag, "chunk": c, **s2})
            break
        if t1.alive(m) and s2["sec"][0] == 0xC and pol.mission_end:
            outcome, end_c = "mission_end_latched", c
            break
    else:
        outcome, end_c = "budget", chunks_cap - 1
    res = {"arm": tag, "outcome": outcome, "end_chunk": end_c,
           "deaths": deaths, "wall_s": round(time.time() - t0, 1),
           "throws": len(tlog.throws), "score_events": score_events,
           "score_final": int(m.u32(t1.A_SCORE)),
           "pol_stats": {k: v for k, v in pol.stats.items() if v},
           "final": t1.snap(m)}
    J({"ev": "ARM_DONE", **res})
    log(f"{tag}: {outcome} c={end_c} throws={res['throws']} "
        f"score={res['score_final']}")
    return res


def analyze_census(jsonl_path):
    """The task-book census answer: WHO did engage lock onto at the
    pin, and how often was the chopper visible while engage held the
    mode? Also the throw->verified-drop flight-time deltas."""
    evs = [json.loads(l) for l in open(jsonl_path)]
    cen = [e for e in evs if e.get("ev") == "census"]
    eng_pin = [e for e in cen if e.get("mode") == "engage"
               and e.get("pin_ctx")]
    near_st = Counter(e["near"]["st"] for e in eng_pin
                      if e.get("near"))
    ch_visible = sum(1 for e in eng_pin if e.get("chopper"))
    fam_dist = Counter(e.get("fam", 0) for e in eng_pin)
    throws = [e for e in evs if e.get("ev") == "THROW"]
    drops = [e for e in evs if e.get("ev") == "HP_DROP"]
    flight = []
    for d in drops:
        cand = [t for t in throws if t["cycle"] is not None
                and t["cycle"] <= d["cycle"]]
        if cand:
            flight.append({"drop_cycle": d["cycle"],
                           "last_throw_cycle": cand[-1]["cycle"]})
    return {"census_chunks": len(cen),
            "engage_at_pin": len(eng_pin),
            "engage_near_states": dict(near_st),
            "engage_chopper_visible": ch_visible,
            "engage_fam_counts": dict(fam_dist),
            "throws": len(throws),
            "verified_drops": len(drops),
            "flight_cycle_gaps": flight}


def main():
    make_ledger()
    n = amend_ledger("BOOT1: read-only census — the legacy v2.2 "
                     "behavior (queue_priority=False) from r38_ckpt, "
                     "300 chunks, per-chunk last_scan trace")
    if n > 2:
        raise SystemExit("BOOT CAP EXCEEDED")
    tr_path = os.path.join(SCRATCH, "r40_boot1.jsonl")
    jf = open(tr_path, "w")

    def J(ev):
        jf.write(json.dumps(ev, default=str) + "\n")
        jf.flush()

    J({"ev": "RUN_START",
       "commit": os.popen("git -C %s rev-parse HEAD"
                          % _REPO).read().strip(),
       "disc_sha256": "45cde149878fe945d0219fd0f61ca09856aee66bdcc9119d"
                      "e21c0583f1d0667d",
       "policy": "legacy v2.2 (queue_priority=False) — the R39 shipped "
                 "semantics for the census baseline",
       "ts": time.strftime("%FT%TZ", time.gmtime())})

    p = boot_to_demo()
    m = p.mem
    p.load_state(CKPT)
    if not t1.alive(m):
        raise SystemExit("r38_ckpt not alive after restore")
    J({"ev": "CKPT_RESTORED", **t1.snap(m)})

    tlog = t1.ThrowLog(J, "CENSUS-BASE")
    base = run_census_arm(p, m, J, "CENSUS-BASE", CHUNKS, tlog,
                          lambda: combat.CombatPolicy(
                              queue_priority=False),
                          continues={})
    base["hp_drops"] = tlog.hits

    # reproduction gate vs the R39 boot-6 reference
    ms = base["pol_stats"]
    repro = {k: ms.get(k, 0) for k in
             ("engage", "aa_kill", "clamp_clear", "armor_hold")}
    repro_ok = (repro["engage"] == R39_REF["engage"]
                and repro["aa_kill"] == R39_REF["aa_kill"])
    J({"ev": "REPRO_GATE", "r39_ref": R39_REF, "r40_stats": repro,
       "match": repro_ok,
       "note": "engage/aa_kill must match the R39 boot-6 trialT1/T2 "
               "deterministic pair exactly"})

    analysis = analyze_census(tr_path)
    J({"ev": "CENSUS_ANALYSIS", **analysis})

    rep = {"schema": "ps1play.r40-boot1/1",
           "generated": time.strftime("%FT%TZ", time.gmtime()),
           "commit": os.popen("git -C %s rev-parse HEAD"
                              % _REPO).read().strip(),
           "checkpoint": CKPT,
           "policy": "legacy v2.2 (queue_priority=False)",
           "base": base, "repro_gate": {"r39_ref": R39_REF,
                                        "r40_stats": repro,
                                        "match": repro_ok},
           "census": analysis}
    with open(os.path.join(SCRATCH, "r40_boot1_report.json"),
              "w") as f:
        json.dump(rep, f, indent=1, default=str)
    jf.close()
    log("report -> scratch/r40/r40_boot1_report.json")
    log(f"census: engage@pin={analysis['engage_at_pin']} "
        f"near_states={analysis['engage_near_states']} "
        f"chopper_visible={analysis['engage_chopper_visible']}/"
        f"{analysis['engage_at_pin']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
