#!/usr/bin/env python3
"""r49t1_class_keyed.py — R49 (the 60% track, Issues #5/#9/#10).

The capsule lever (R48 close-out), executed verbatim.  The R48 frame-
exact verdict: TWO pay classes — (1) DEATH-INITIATION-LOCKED +100 on
the 0x515c entry frame (n=3), (2) SURVIVING-CONNECT +500 at slot-20's
0x42bc hit-reaction while slot 20 SURVIVED (n=1, deterministic across
R45/R48).  BOTH pure models falsified: payments land at the connect/
kill-registration frame, the corpse lags 1-14f.

HYPOTHESIS (verbatim, the capsule R49): the TWO PAY CLASSES are
CLASS-KEYED: the +100 death-registration payment is the soldier-class
kill reward (0x515c entry), while the +500 surviving-connect payment
keys on a DIFFERENT target class (slot 20's 0x42bc hit-reaction) —
aimed taps DEDICATED to 0x42bc-class targets that are then left alive
(no follow-up kill) should reproduce +500-class payments with the
target surviving to walk end, and taps dedicated to 0x4054/0x5b0c
soldiers should yield +100-class only; the payment magnitude reads
off the class, not off kill vs hit.

Method (the capsule): boot -> restore r47_frontier_a -> the direct-
read telemetry VERBATIM (the R48 recording: TAP_FRAMES 3 + TAIL 20f,
per-frame score + FULL-kind mini census + DIRECT table reads slots
1..39) -> taps GROUPED by target class: CONNECT taps (ONE bullet on a
fresh soft target; the slot is then NEVER fired at again — survival
checked at the tail end AND at walk end) vs KILL taps (fresh soldier
slots, single bullets until the 0x515c registration / corpse) -> the
frame-exact event table per group -> the class-keyed magnitude table.
The burning states stay excluded AS TARGETS, RECORDED (R46 verbatim).

PRE-RUN DISCLOSURE: NO sandbox rollback this round — the R47
frontiers (r47_frontier_a/b) SURVIVED on disk (verified pre-boot in
main()).  Boot plan (cap 1, DISCLOSED PRE-RUN): boot = the core+rom
load ONLY; both frontier passes are restore-only (restores are NOT
boots, r35 precedent).  TAINTED lineage carried (the frontier
postures were built with continue-rescues; never a clean claim).
m2_gate unchanged: the INTERACTIVE M2 entry stays gated on a clean
(deaths=0, no-restart) deep resolve posture.

Oracle unchanged: walker words + verified score gains + alive
0x0EE518; never +0x8E in any oracle (the wide net is DISCLOSED
exploratory telemetry, not an oracle).
"""
from __future__ import annotations

import json
import os
import sys
import time

_REPO = "/home/z/my-project/ps1ai"
for _p in (_REPO, os.path.join(_REPO, "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import r39t1_baseline as t1                       # noqa: E402
import ps1play.agent.combat as combat             # noqa: E402
import r41t2_nodes_live as t2                     # noqa: E402
import r48t1_frame_exact_taps as R48              # noqa: E402
from r48t1_frame_exact_taps import (              # noqa: E402
    census_full, direct_table, entity_state, read_words, full_snapshot,
    union_post, corpse_transitions, frame_walk, TARGET_EXCLUDE_ST,
    SOFT_ST, TAP_FRAMES, TAIL_FRAMES, STATES)
from issue4_controller import boot_to_demo        # noqa: E402

SCRATCH = os.path.join(_REPO, "scratch", "r49")
LEDGER = os.path.join(SCRATCH, "boots_used.json")
EVID = os.path.join(_REPO, "data", "games", "SLUS-01212",
                    "truck_evidence", "r49")

FRONTIER = ("r47_frontier_a", "r47_frontier_b")

CONNECT_GOAL = 4          # dedicated 0x42bc connects (no follow-up)
KILL_GOAL = 3             # dedicated soldier kills
MAX_BULLETS_PER_KILL = 4
N_TAPS_CAP = 24
WALL_TAPS_S = 560
CONNECT_ST = 0x42BC       # the hit-reaction state (the +500 class key)
REG_ST = 0x515C           # the kill-registration state (the +100 class)

T0 = time.time()


def log(*a):
    print("[r49-t1]", *a, file=sys.stderr, flush=True)


def amend_ledger(reason):
    os.makedirs(SCRATCH, exist_ok=True)
    os.makedirs(EVID, exist_ok=True)
    if not os.path.exists(LEDGER):
        with open(LEDGER, "w") as f:
            json.dump({"cap": 1, "count": 0, "log": [], "note":
                       "R49 ledger: cap 1 DISCLOSED PRE-RUN = the "
                       "core+rom load ONLY.  NO sandbox rollback this "
                       "round: the R47 frontiers r47_frontier_a/b "
                       "SURVIVED on disk (verified pre-boot); both "
                       "passes are restore-only (restores are NOT "
                       "boots, r35 precedent).  Lineage TAINTED "
                       "(the R45/R47 frontier rebuilds carried "
                       "continue-rescues; never a clean claim).  "
                       "m2_gate unchanged: the INTERACTIVE M2 entry "
                       "stays gated on a clean deep resolve posture.",
                       "hypothesis":
                       "the two pay classes are CLASS-KEYED: +100 = "
                       "the soldier kill reward at the 0x515c entry; "
                       "+500 = the surviving-connect payment keyed on "
                       "the 0x42bc hit-reaction class; dedicated no-"
                       "follow-up connects reproduce +500 with the "
                       "target surviving, dedicated soldier kills "
                       "yield +100 only — magnitude reads off the "
                       "class, not off kill vs hit"},
                      f, indent=1)
    with open(LEDGER) as f:
        led = json.load(f)
    led["count"] = int(led.get("count", 0)) + 1
    led.setdefault("log", []).append(
        {"n": led["count"], "ts": time.strftime("%FT%TZ", time.gmtime()),
         "script": "r49t1_class_keyed.py", "reason": reason})
    with open(LEDGER, "w") as f:
        json.dump(led, f, indent=1)
    log(f"boot ledger: count={led['count']}/{led['cap']} ({reason})")
    return led["count"]


def slot_state_in(rows, slot):
    """st transitions of one slot inside a frame-walk window."""
    out = []
    prev = None
    for r in rows:
        st = None
        for d in r["direct"]:
            if d["slot"] == slot:
                st = d["st"]
                break
        if st is not None and st != prev:
            out.append({"f_rel": r["f_rel"], "from": prev, "to": st})
            prev = st
    return out


def sc_jumps(rows):
    out = []
    for a, b in zip(rows, rows[1:]):
        d = b["sc"] - a["sc"]
        if d:
            out.append({"f_rel": b["f_rel"], "d": d,
                        "sc": b["sc"]})
    return out


def slot_alive_in(rows, slot):
    st = xw = None
    for r in rows:
        for d in r["direct"]:
            if d["slot"] == slot:
                st, xw = d["st"], d["x"]
    if st is None:
        return None
    return not (st in combat.CORPSE_ST or xw == 0.0)


def approach(m, p, tgt):
    if tgt["dx_px"] > 8.0:
        p.core.run(3, {"RIGHT"})
    elif tgt["dx_px"] < -8.0:
        p.core.run(3, {"LEFT"})


def fire_tap(p, m, J, out, i, intent, tgt, bullet, kill_id):
    cen, pre_e, pre_w = full_snapshot(m)
    pre_sc = int(m.u32(t1.A_SCORE))
    pre_php = int(m.u16(t1.PLAYER_HP))
    tap_rows = frame_walk(p, m, J, i, f"AIMED_Y_{intent}",
                          TAP_FRAMES, {"Y"})
    tail_rows = frame_walk(p, m, J, i, f"FLIGHT_TAIL_{intent}",
                           TAIL_FRAMES, set())
    cen2, post_e, post_w = full_snapshot(m)
    post_e, post_w = union_post(m, post_e, post_w, pre_e)
    post_sc = int(m.u32(t1.A_SCORE))
    post_php = int(m.u16(t1.PLAYER_HP))
    corpses = corpse_transitions(pre_e, post_e)
    gone = [s for s, po in post_e.items()
            if po["st"] in combat.CORPSE_ST or po["f8e"] == 0]
    rows = tap_rows + tail_rows
    trans = slot_state_in(rows, tgt["slot"])
    tap = {"tap": i, "intent": intent, "bullet": bullet,
           "kill_id": kill_id, "kind": f"AIMED_Y_{intent}",
           "target": tgt, "score_delta": post_sc - pre_sc,
           "sc_start": pre_sc, "sc_end": post_sc,
           "php": (pre_php, post_php), "frame_rows": rows,
           "ents_pre": pre_e, "ents_post": post_e,
           "word_deltas": {s: {k: post_w[s][k] - pre_w[s][k]
                               for k in pre_w[s]} for s in pre_w},
           "slots_gone": gone, "corpses": corpses,
           "target_st_transitions": trans,
           "sc_jumps": sc_jumps(rows),
           "target_alive_at_tail": slot_alive_in(rows, tgt["slot"])}
    out["taps"].append(tap)
    J({"ev": "TAP", **tap, "frontier": out["frontier"]})
    out["deaths_seen"] += len(corpses)
    log(f"tap {i} [{intent} b{bullet}] tgt slot{tgt['slot']} "
        f"st{hex(tgt['st'])} dx{tgt['dx_px']:+.0f} "
        f"dscore={tap['score_delta']} corpses={corpses} "
        f"trans={[(t['to'] and hex(t['to'])) for t in trans]}")
    if corpses or any(t["to"] in (CONNECT_ST, REG_ST) for t in trans):
        png(p, f"ev_tap{i}", out["pass_tag"])
    return tap


def png(p, name, tag):
    try:
        rgb = p.core.frame_rgb()
        if rgb is not None:
            from PIL import Image
            d = os.path.join(SCRATCH, "pngs")
            os.makedirs(d, exist_ok=True)
            Image.fromarray(rgb).save(
                os.path.join(d, f"{tag}_{name}.png"))
    except Exception as e:                                  # noqa: BLE001
        log("png failed:", repr(e)[:120])


def run_pass(p, m, J, tag, frontier):
    """Restore-only class-keyed tap protocol from one frontier."""
    out = {"frontier": frontier, "pass_tag": tag, "taps": [],
           "census_at_restore": [], "re_restores": 0,
           "deaths_seen": 0, "connects": 0, "kills": 0,
           "connected_slots": [], "kill_slots": []}
    p.load_state(frontier)
    if not t1.alive(m):
        p.core.run(30, set())
        if not t1.alive(m):
            J({"ev": "FRONTIER_DEAD", "frontier": frontier})
            out["note"] = "dead on restore"
            return out
    s0 = t1.snap(m)
    J({"ev": "FRONTIER_RESTORED", "frontier": frontier, **s0,
       "vm": t2.read_vm(m)})
    cen = census_full(m, s0["px"])
    out["census_at_restore"] = cen
    n_tgt = len([e for e in cen if e["targetable"]])
    J({"ev": "CENSUS_FULL", "frontier": frontier, "px": s0["px"],
       "n_all": len(cen), "n_targetable": n_tgt, "entities": cen})
    log(f"census {frontier}: {len(cen)} live ({n_tgt} targetable)")
    # ---- the zero-input control walk (baseline, R48 verbatim) -------
    cen, pre_e, pre_w = full_snapshot(m)
    pre_sc = int(m.u32(t1.A_SCORE))
    ctrl_rows = frame_walk(p, m, J, 0, "CONTROL_ZERO_INPUT",
                           TAP_FRAMES + TAIL_FRAMES, set())
    cen2, post_e, post_w = full_snapshot(m)
    post_e, post_w = union_post(m, post_e, post_w, pre_e)
    post_sc = int(m.u32(t1.A_SCORE))
    ctrl = {"tap": 0, "kind": "CONTROL_ZERO_INPUT",
            "score_delta": post_sc - pre_sc,
            "frame_rows": ctrl_rows,
            "corpses": corpse_transitions(pre_e, post_e)}
    out["taps"].append(ctrl)
    J({"ev": "TAP", **ctrl, "frontier": frontier})
    log(f"control walk: dscore={ctrl['score_delta']} "
        f"corpses={ctrl['corpses']}")
    # ---- the class-keyed tap loop ------------------------------------
    used = set()          # connected or killed: NEVER targeted again
    kill_id = 0
    i = 0
    while i < N_TAPS_CAP:
        if time.time() - T0 > WALL_TAPS_S:
            out["note"] = "wall_guard"
            break
        if out["connects"] >= CONNECT_GOAL \
                and out["kills"] >= KILL_GOAL:
            break
        i += 1
        if not t1.alive(m):
            out["re_restores"] += 1
            J({"ev": "READOUT_DEATH", "frontier": frontier,
               "tap": i, "re_restores": out["re_restores"]})
            if out["re_restores"] > R48.RE_RESTORE_MAX:
                out["note"] = "player died, re-restore budget gone"
                break
            p.load_state(frontier)
            if not t1.wait_alive(m, p, wait=10):
                out["note"] = "frontier dead after restore"
                break
            J({"ev": "RE_RESTORED", "frontier": frontier,
               "tap": i, **t1.snap(m)})
        cen = census_full(m, t1.px_of(m))
        want_connect = out["connects"] < CONNECT_GOAL
        tgt = None
        for e in cen:
            if e["targetable"] and e["slot"] not in used:
                tgt = e
                break
        if tgt is None:
            J({"ev": "CENSUS_NO_TARGET", "frontier": frontier,
               "tap": i, "n_all": len(cen)})
            out["note"] = f"no_targetable_at_tap{i}"
            break
        approach(m, p, tgt)
        if want_connect:
            tap = fire_tap(p, m, J, out, i, "CONNECT", tgt, 1, None)
            used.add(tgt["slot"])
            hit = any(t["to"] == CONNECT_ST
                      for t in tap["target_st_transitions"])
            reg = any(t["to"] == REG_ST
                      for t in tap["target_st_transitions"])
            if hit and not reg:
                out["connects"] += 1
                out["connected_slots"].append(
                    {"slot": tgt["slot"], "tap": i,
                     "st_pre": tgt["st"],
                     "alive_at_tail": tap["target_alive_at_tail"],
                     "dscore": tap["score_delta"]})
                log(f"CONNECT registered slot{tgt['slot']} "
                    f"(0x42bc seen, no follow-up; target left alive)")
            elif reg:
                # the single bullet killed it: the connect-class test
                # did NOT engage — record honestly, do not count.
                J({"ev": "CONNECT_BECAME_KILL", "frontier": frontier,
                   "tap": i, "slot": tgt["slot"],
                   "dscore": tap["score_delta"]})
                log(f"tap {i}: single bullet REGISTERED slot"
                    f"{tgt['slot']} (one-hit class?) — not counted "
                    f"as a connect")
            else:
                J({"ev": "CONNECT_MISS", "frontier": frontier,
                   "tap": i, "slot": tgt["slot"],
                   "dscore": tap["score_delta"]})
                log(f"tap {i}: connect tap missed (no 0x42bc)")
        else:
            kill_id += 1
            kslot = tgt["slot"]
            reg_done = False
            for b in range(1, MAX_BULLETS_PER_KILL + 1):
                if b > 1:
                    if not t1.alive(m):
                        break
                    cen2 = census_full(m, t1.px_of(m))
                    live = None
                    for e in cen2:
                        if e["slot"] == kslot:
                            live = e
                            break
                    if live is None or not live["targetable"]:
                        break            # corpse/gone: kill resolved
                    approach(m, p, live)
                    tgt = live
                tap = fire_tap(p, m, J, out, i, "KILL", tgt, b,
                               kill_id)
                reg = any(t["to"] == REG_ST
                          for t in tap["target_st_transitions"])
                if reg or tap["corpses"] or \
                        tap["target_alive_at_tail"] is False:
                    reg_done = True
                    break
            if reg_done:
                out["kills"] += 1
                out["kill_slots"].append(
                    {"slot": kslot, "kill_id": kill_id,
                     "st_pre": None, "bullets": b})
                log(f"KILL {kill_id} resolved on slot{kslot} "
                    f"(bullets={b})")
            else:
                used.add(kslot)   # unresolved: drop it either way
                J({"ev": "KILL_UNRESOLVED", "frontier": frontier,
                   "slot": kslot, "kill_id": kill_id, "bullets": b})
                log(f"kill {kill_id} UNRESOLVED on slot{kslot} "
                    f"after {b} bullets")
    # ---- walk-end survival of the connected slots --------------------
    dt = direct_table(m)
    live_now = {d["slot"]: d for d in dt}
    out["connect_survival_at_walk_end"] = []
    for c in out["connected_slots"]:
        d = live_now.get(c["slot"])
        alive = bool(d and d["st"] not in combat.CORPSE_ST
                     and d["x"] != 0.0) if d else None
        out["connect_survival_at_walk_end"].append(
            {"slot": c["slot"], "alive": alive,
             "st": (d or {}).get("st"), "x": (d or {}).get("x")})
    fin = t1.snap(m)
    out["final"] = fin
    J({"ev": "PASS_DONE", "frontier": frontier, **fin,
       "connects": out["connects"], "kills": out["kills"],
       "connect_survival_at_walk_end":
           out["connect_survival_at_walk_end"]})
    return out


def main():
    # ---- pre-boot on-disk frontier verification (the disclosure) ----
    have = [fr for fr in FRONTIER
            if os.path.exists(os.path.join(STATES, fr + ".state"))]
    if not have:
        raise SystemExit("no r47_frontier_* states on disk - the "
                         "capsule contingency (a rebuild boot) would "
                         "need a fresh disclosed cap; never fabricate")
    log("frontiers on disk (NO rollback this round):", have)
    reasons = ("BOOT (core+rom load ONLY): restore r47_frontier_a -> "
               "class-keyed tap protocol (control walk; CONNECT taps "
               "1 bullet no-follow-up on fresh soft targets vs KILL "
               "taps on fresh soldiers; per-frame score + DIRECT "
               "table reads) -> restore r47_frontier_b if the group "
               "goals unmet -> report.")
    n = amend_ledger(reasons)
    if n > 1:
        raise SystemExit("BOOT CAP EXCEEDED (1 - any defect amendment "
                         "must be DISCLOSED per the r47/r48 "
                         "precedent before a second boot)")
    tag = time.strftime("r49_%H%M%S")
    stem = f"r49_boot{n}"
    os.makedirs(SCRATCH, exist_ok=True)
    os.makedirs(EVID, exist_ok=True)
    tr_path = os.path.join(EVID, f"{stem}.jsonl")
    jf = open(tr_path, "w")

    def J(ev):
        jf.write(json.dumps(ev, default=str) + "\n")
        jf.flush()

    J({"ev": "RUN_START",
       "commit": os.popen("git -C %s rev-parse HEAD"
                          % _REPO).read().strip(),
       "rollback_disclosure": "NONE this round: r47_frontier_a/b "
                              "survived on disk (verified pre-boot)",
       "lineage": "TAINTED frontier postures (restore-only taps; "
                  "the R45/R47 rebuilds carried continue-rescues)",
       "protocol": f"CONNECT_GOAL={CONNECT_GOAL} (1 bullet, no "
                   f"follow-up) vs KILL_GOAL={KILL_GOAL}; "
                   f"TAP_FRAMES={TAP_FRAMES} + TAIL_FRAMES="
                   f"{TAIL_FRAMES} per-frame score/census telemetry "
                   "+ DIRECT per-frame table reads (R48 verbatim)",
       "oracle": "walker words + verified score gains + alive "
                 "0x0EE518; never +0x8E (the wide net = disclosed "
                 "exploratory telemetry)",
       "ts": time.strftime("%FT%TZ", time.gmtime())})
    try:
        p = boot_to_demo()
        m = p.mem
        pas = []
        for fr in have:
            r = run_pass(p, m, J, tag, fr)
            pas.append(r)
            done = (r["connects"] >= CONNECT_GOAL
                    and r["kills"] >= KILL_GOAL)
            if done or r.get("note") in (
                    "dead on restore", "frontier dead after restore"):
                break
        res = {"passes": pas, "final": t1.snap(m)}
        rep = {"schema": "ps1play.r49-classkeyed/1",
               "generated": time.strftime("%FT%TZ", time.gmtime()),
               "commit": os.popen("git -C %s rev-parse HEAD"
                                  % _REPO).read().strip(),
               "frontiers_on_disk": have, "run": res}
        with open(os.path.join(EVID, f"{stem}_report.json"), "w") as f:
            json.dump(rep, f, indent=1, default=str)
        fin_line = [(r["frontier"], r["connects"], r["kills"])
                    for r in pas]
        log(f"FIN passes={fin_line} (wall {time.time() - T0:.0f}s)")
    finally:
        jf.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
