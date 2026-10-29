#!/usr/bin/env python3
"""r50t1_controlled_corridor.py — R50 (the 60% track, #5/#9/#10).

The capsule lever (R49 close-out), executed verbatim: the CONTROLLED-
CORRIDOR tap protocol.  The R49 refinement: payments are PLAYER-
BULLET-VICTIM-LOCKED (only the bullet's actual victim pays) — every
R49 +100 co-landed with a CYCLING ZONE ENTITY (the spawner zone
x~1277-1351) registered in the bullet corridor, never the aimed
target; and the identical 0x42bc connect context paid +500 once and
+1000 once (the unresolved residual).

HYPOTHESIS (verbatim, the capsule R50): the payment model is
PLAYER-BULLET-VICTIM-LOCKED with per-class magnitudes (+100 the
soft-soldier kill reward, +500 the 0x42bc surviving-connect) — a
CONTROLLED-CORRIDOR tap protocol (fire ONLY when the census shows
the aimed target as the ONLY mortal entity in the bullet corridor,
i.e. no cycling zone entity between player and target; prefer
targets dx > 100 beyond the x~1277-1351 spawner cluster) yields
n >= 3 clean per-class payments with ZERO co-landing ambiguity and
settles the magnitude table; the movement-only control (walk 3f +
20f idle, no Y) tests whether the corridor churn alone can pay; the
0xae7c-class census (slot33's class) dates its kills to settle the
+1000 residual.

Method (the capsule): boot -> restore r47_frontier_a -> the R48/R49
direct-read telemetry VERBATIM -> the corridor census gate before
EVERY tap (skip the tap and re-census when the corridor is
occupied) -> CONNECT group (no follow-up) AND KILL group until
n >= 3 clean each or the census thins -> the r49-style offline
global-frame analysis -> the magnitude table.

IN-ROUND DISCLOSED REFINEMENT (pre-run, the ledger note): the KILL
group PREFERS a 0xae7c-class target (max 2 dedicated) while it is
available with a clear corridor — the b-tap1 residual candidate
(the 0xae7c-class kill paying +500) is then tested DIRECTLY, not
just censused; soft-soldier kills fill the rest of the KILL goal.

PRE-RUN DISCLOSURE: NO sandbox rollback — the R47 frontiers
SURVIVED on disk (verified pre-boot).  Boot plan (cap 1, DISCLOSED
PRE-RUN): boot = the core+rom load ONLY; both passes restore-only.
TAINTED lineage carried (never a clean claim).  m2_gate unchanged.

Oracle unchanged: walker words + verified score gains + alive
0x0EE518; never +0x8E in any oracle.
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

SCRATCH = os.path.join(_REPO, "scratch", "r50")
LEDGER = os.path.join(SCRATCH, "boots_used.json")
EVID = os.path.join(_REPO, "data", "games", "SLUS-01212",
                    "truck_evidence", "r50")

FRONTIER = ("r47_frontier_a", "r47_frontier_b")

CONNECT_GOAL = 3          # dedicated 0x42bc connects (no follow-up)
KILL_GOAL = 3             # dedicated kills (0xae7c-class first, max 2)
MAX_BULLETS_PER_KILL = 4
N_TAPS_CAP = 26
SKIP_RETRIES_MAX = 10     # the corridor-gate re-census budget
WALL_TAPS_S = 560
CORRIDOR_MARGIN = 5.0     # px kept clear inside the target end
CONNECT_ST = 0x42BC       # the hit-reaction state (the +500 class key)
REG_ST = 0x515C           # the kill-registration state (the +100 class)
AE7C_ST = 0xAE7C          # the residual-candidate class (slot33)

T0 = time.time()


def log(*a):
    print("[r50-t1]", *a, file=sys.stderr, flush=True)


def amend_ledger(reason):
    os.makedirs(SCRATCH, exist_ok=True)
    os.makedirs(EVID, exist_ok=True)
    if not os.path.exists(LEDGER):
        with open(LEDGER, "w") as f:
            json.dump({"cap": 1, "count": 0, "log": [], "note":
                       "R50 ledger: cap 1 DISCLOSED PRE-RUN = the "
                       "core+rom load ONLY.  NO sandbox rollback: "
                       "the R47 frontiers r47_frontier_a/b SURVIVED "
                       "on disk (verified pre-boot); both passes are "
                       "restore-only (restores are NOT boots, r35 "
                       "precedent).  Lineage TAINTED (never a clean "
                       "claim).  IN-ROUND DISCLOSED REFINEMENT (pre-"
                       "run): the KILL group PREFERS a 0xae7c-class "
                       "target (max 2) — the b-tap1 +1000 residual "
                       "candidate tested DIRECTLY.  m2_gate "
                       "unchanged.",
                       "hypothesis":
                       "PLAYER-BULLET-VICTIM-LOCKED payments with "
                       "per-class magnitudes: the controlled-"
                       "corridor gate (the aimed target = the ONLY "
                       "mortal in the bullet corridor) yields n>=3 "
                       "clean per-class payments with zero co-"
                       "landing ambiguity; the movement-only "
                       "control never pays; the 0xae7c census/"
                       "kills settle the +1000 residual"},
                      f, indent=1)
    with open(LEDGER) as f:
        led = json.load(f)
    led["count"] = int(led.get("count", 0)) + 1
    led.setdefault("log", []).append(
        {"n": led["count"], "ts": time.strftime("%FT%TZ", time.gmtime()),
         "script": "r50t1_controlled_corridor.py", "reason": reason})
    with open(LEDGER, "w") as f:
        json.dump(led, f, indent=1)
    log(f"boot ledger: count={led['count']}/{led['cap']} ({reason})")
    return led["count"]


def slot_state_in(rows, slot):
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
            out.append({"f_rel": b["f_rel"], "d": d, "sc": b["sc"]})
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


def corridor_occupants(cen, player_x, tgt_x):
    """Live mortals strictly between the player and the target
    (the R50 gate: the aimed target must be the ONLY one)."""
    lo, hi = min(player_x, tgt_x), max(player_x, tgt_x)
    occ = []
    for e in cen:
        if e["slot"] and e["st"] in combat.CORPSE_ST:
            continue
        if e.get("x_px", 0.0) <= 0.0:
            continue
        if lo < e["x_px"] < hi:
            occ.append({"slot": e["slot"], "st": e["st"],
                        "x": round(e["x_px"], 1),
                        "kind": e.get("kind")})
    return occ


def approach(m, p, tgt):
    if tgt["dx_px"] > 8.0:
        p.core.run(3, {"RIGHT"})
    elif tgt["dx_px"] < -8.0:
        p.core.run(3, {"LEFT"})


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


def fire_tap(p, m, J, out, i, intent, tgt, bullet, kill_id):
    cen, pre_e, pre_w = full_snapshot(m)
    pre_sc = int(m.u32(t1.A_SCORE))
    pre_php = int(m.u16(t1.PLAYER_HP))
    px0 = t1.px_of(m)
    tap_rows = frame_walk(p, m, J, i, f"AIMED_Y_{intent}",
                          TAP_FRAMES, {"Y"})
    tail_rows = frame_walk(p, m, J, i, f"FLIGHT_TAIL_{intent}",
                           TAIL_FRAMES, set())
    cen2, post_e, post_w = full_snapshot(m)
    post_e, post_w = union_post(m, post_e, post_w, pre_e)
    post_sc = int(m.u32(t1.A_SCORE))
    post_php = int(m.u16(t1.PLAYER_HP))
    corpses = corpse_transitions(pre_e, post_e)
    rows = tap_rows + tail_rows
    trans = slot_state_in(rows, tgt["slot"]) if tgt else []
    tap = {"tap": i, "intent": intent, "bullet": bullet,
           "kill_id": kill_id, "kind": f"AIMED_Y_{intent}",
           "target": tgt, "score_delta": post_sc - pre_sc,
           "sc_start": pre_sc, "sc_end": post_sc,
           "php": (pre_php, post_php),
           "player_x_at_fire": round(px0, 1),
           "frame_rows": rows,
           "ents_pre": pre_e, "ents_post": post_e,
           "word_deltas": {s: {k: post_w[s][k] - pre_w[s][k]
                               for k in pre_w[s]} for s in pre_w},
           "corpses": corpses,
           "target_st_transitions": trans,
           "sc_jumps": sc_jumps(rows),
           "target_alive_at_tail":
               slot_alive_in(rows, tgt["slot"]) if tgt else None}
    out["taps"].append(tap)
    J({"ev": "TAP", **tap, "frontier": out["frontier"]})
    out["deaths_seen"] += len(corpses)
    log(f"tap {i} [{intent} b{bullet}] "
        + (f"tgt slot{tgt['slot']} st{hex(tgt['st'])} "
           f"dx{tgt['dx_px']:+.0f} " if tgt else "")
        + f"dscore={tap['score_delta']} corpses={corpses} "
        f"trans={[(t['to'] and hex(t['to'])) for t in trans]}")
    if corpses or any(t["to"] in (CONNECT_ST, REG_ST) for t in trans):
        png(p, f"ev_tap{i}", out["pass_tag"])
    return tap


def control_move(p, m, J, out, i):
    """The movement-only control: walk 3f RIGHT + 20f idle, NO Y."""
    cen, pre_e, pre_w = full_snapshot(m)
    pre_sc = int(m.u32(t1.A_SCORE))
    rows = frame_walk(p, m, J, i, "CONTROL_MOVE_ONLY", TAP_FRAMES,
                      {"RIGHT"})
    rows += frame_walk(p, m, J, i, "CONTROL_MOVE_TAIL",
                       TAIL_FRAMES, set())
    cen2, post_e, post_w = full_snapshot(m)
    post_e, post_w = union_post(m, post_e, post_w, pre_e)
    post_sc = int(m.u32(t1.A_SCORE))
    ctrl = {"tap": i, "intent": "CONTROL_MOVE",
            "kind": "CONTROL_MOVE_ONLY",
            "score_delta": post_sc - pre_sc,
            "frame_rows": rows,
            "sc_jumps": sc_jumps(rows),
            "corpses": corpse_transitions(pre_e, post_e)}
    out["taps"].append(ctrl)
    J({"ev": "TAP", **ctrl, "frontier": out["frontier"]})
    log(f"tap {i} [CONTROL_MOVE] dscore={ctrl['score_delta']} "
        f"corpses={ctrl['corpses']}")
    return ctrl


def pick_target(cen, used, player_x, want_class=None):
    """Clear-corridor targets only; WANT_CLASS prefers a state
    family (e.g. 0xae7c) else the farthest clear soft target."""
    best = None
    for e in cen:
        if not e["targetable"] or e["slot"] in used:
            continue
        occ = corridor_occupants(cen, player_x, e["x_px"])
        if occ:
            continue
        key = (0 if (want_class and e["st"] == want_class) else 1,
               -abs(e["dx_px"]))
        if best is None or key < best[0]:
            best = (key, e)
    return best[1] if best else None


def run_pass(p, m, J, tag, frontier):
    out = {"frontier": frontier, "pass_tag": tag, "taps": [],
           "census_at_restore": [], "re_restores": 0,
           "deaths_seen": 0, "connects": 0, "kills": 0,
           "ae7c_kills": 0, "gate_skips": 0,
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
    J({"ev": "CENSUS_FULL", "frontier": frontier, "px": s0["px"],
       "n_all": len(cen),
       "n_targetable": len([e for e in cen if e["targetable"]]),
       "entities": cen})
    log(f"census {frontier}: {len(cen)} live")
    # ---- the zero-input control walk (the R48/R49 baseline) ---------
    cen, pre_e, pre_w = full_snapshot(m)
    pre_sc = int(m.u32(t1.A_SCORE))
    ctrl_rows = frame_walk(p, m, J, 0, "CONTROL_ZERO_INPUT",
                           TAP_FRAMES + TAIL_FRAMES, set())
    cen2, post_e, post_w = full_snapshot(m)
    post_e, post_w = union_post(m, post_e, post_w, pre_e)
    post_sc = int(m.u32(t1.A_SCORE))
    out["taps"].append({"tap": 0, "kind": "CONTROL_ZERO_INPUT",
                        "score_delta": post_sc - pre_sc,
                        "frame_rows": ctrl_rows,
                        "corpses": corpse_transitions(pre_e, post_e)})
    J({"ev": "TAP", **out["taps"][0], "frontier": frontier})
    # ---- the movement-only controls (the R50 lever) ------------------
    control_move(p, m, J, out, 1)
    # ---- the gated tap loop ------------------------------------------
    used = set()
    kill_id = 0
    i = 1
    skips = 0
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
        cen = census_full(m, t1.px_of(m))
        player_x = t1.px_of(m)
        want_connect = out["connects"] < CONNECT_GOAL
        want_ae7c = (not want_connect) and out["ae7c_kills"] < 2
        tgt = pick_target(cen, used, player_x,
                          want_class=AE7C_ST if want_ae7c else None)
        if tgt is None:
            skips += 1
            out["gate_skips"] = skips
            J({"ev": "GATE_SKIP", "frontier": frontier, "tap": i,
               "reason": "corridor_occupied_or_no_target",
               "n_all": len(cen)})
            if skips > SKIP_RETRIES_MAX:
                out["note"] = "corridor gate starved (retries gone)"
                break
            p.core.run(6, set())          # let the zone churn settle
            continue
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
                log(f"CONNECT {out['connects']} slot{tgt['slot']} "
                    f"(0x42bc, no follow-up)")
            elif reg:
                J({"ev": "CONNECT_BECAME_KILL", "frontier": frontier,
                   "tap": i, "slot": tgt["slot"]})
                log(f"tap {i}: single bullet REGISTERED slot"
                    f"{tgt['slot']} — one-hit, not a connect")
            else:
                J({"ev": "CONNECT_MISS", "frontier": frontier,
                   "tap": i, "slot": tgt["slot"]})
                log(f"tap {i}: connect missed (no 0x42bc)")
        else:
            kill_id += 1
            kslot = tgt["slot"]
            is_ae7c = tgt["st"] == AE7C_ST
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
                        break
                    occ = corridor_occupants(cen2, t1.px_of(m),
                                             live["x_px"])
                    if occ:
                        break           # the gate: never fire blind
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
                if is_ae7c:
                    out["ae7c_kills"] += 1
                out["kill_slots"].append(
                    {"slot": kslot, "kill_id": kill_id,
                     "class": "0xae7c" if is_ae7c else "soft",
                     "bullets": b})
                kcls = "0xae7c" if is_ae7c else "soft"
                log(f"KILL {kill_id} ({kcls}) resolved slot{kslot} "
                    f"bullets={b}")
            else:
                used.add(kslot)
                J({"ev": "KILL_UNRESOLVED", "frontier": frontier,
                   "slot": kslot, "bullets": b})
    # ---- the second movement control (post-taps, different zone) -----
    if not t1.alive(m):
        p.load_state(frontier)
        t1.wait_alive(m, p, wait=10)
    control_move(p, m, J, out, i)
    # ---- walk-end survival of the connected slots ---------------------
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
       "ae7c_kills": out["ae7c_kills"],
       "gate_skips": out["gate_skips"],
       "connect_survival_at_walk_end":
           out["connect_survival_at_walk_end"]})
    return out


def main():
    have = [fr for fr in FRONTIER
            if os.path.exists(os.path.join(STATES, fr + ".state"))]
    if not have:
        raise SystemExit("no r47_frontier_* states on disk - the "
                         "capsule contingency (a rebuild boot) would "
                         "need a fresh disclosed cap; never fabricate")
    log("frontiers on disk (NO rollback this round):", have)
    # the r47 boot-2 defect precedent: boot 1 of this round crashed
    # post-restore (NameError post_sc, zero taps fired) - the cap
    # amendment 1->2 is DISCLOSED HERE, before boot 2 runs.
    if os.path.exists(LEDGER):
        with open(LEDGER) as f:
            prev = json.load(f)
        if prev.get("count", 0) >= 1:
            prev["cap"] = 2
            prev.setdefault("log", []).append(
                {"n": prev["count"],
                 "ts": time.strftime("%FT%TZ", time.gmtime()),
                 "script": "r50t1_controlled_corridor.py",
                 "cap_amendment":
                     "cap 1->2 DISCLOSED (the r47 boot-2 defect "
                     "precedent): boot 1 crashed post-restore at "
                     "the control-walk record (NameError post_sc "
                     "undefined - a runner defect, ZERO taps "
                     "fired, the world untouched by any protocol "
                     "action; the partial jsonl preserved as "
                     "r50_boot1.jsonl).  boot 2 = the fixed runner "
                     "(the same protocol verbatim)."})
            json.dump(prev, open(LEDGER, "w"), indent=1)
            log("cap amended 1->2 DISCLOSED (boot-1 runner crash, "
                "zero taps)")
    n = amend_ledger("BOOT (core+rom load ONLY): restore "
                     "r47_frontier_a -> the corridor-census-gated "
                     "class-keyed taps (2 movement-only controls; "
                     "CONNECT no-follow-up; KILL prefers the 0xae7c "
                     "class) -> restore r47_frontier_b if goals "
                     "unmet -> report.")
    if n > 2:
        raise SystemExit("BOOT CAP EXCEEDED (2 - the disclosed "
                         "1->2 runner-defect amendment)")
    tag = time.strftime("r50_%H%M%S")
    stem = f"r50_boot{n}"
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
       "lineage": "TAINTED frontier postures (restore-only taps)",
       "protocol": f"the corridor-census gate (the aimed target = "
                   f"the ONLY mortal in the bullet corridor; "
                   f"CORRIDOR_MARGIN={CORRIDOR_MARGIN}) + 2 "
                   f"movement-only controls; CONNECT_GOAL="
                   f"{CONNECT_GOAL} no-follow-up; KILL_GOAL="
                   f"{KILL_GOAL} (0xae7c-class first, max 2); "
                   f"TAP_FRAMES={TAP_FRAMES}+TAIL_FRAMES="
                   f"{TAIL_FRAMES} DIRECT table reads (R48 "
                   f"verbatim)",
       "oracle": "walker words + verified score gains + alive "
                 "0x0EE518; never +0x8E",
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
        rep = {"schema": "ps1play.r50-corridor/1",
               "generated": time.strftime("%FT%TZ", time.gmtime()),
               "commit": os.popen("git -C %s rev-parse HEAD"
                                  % _REPO).read().strip(),
               "frontiers_on_disk": have, "run": res}
        with open(os.path.join(EVID, f"{stem}_report.json"), "w") as f:
            json.dump(rep, f, indent=1, default=str)
        fin_line = [(r["frontier"], r["connects"], r["kills"],
                     r["ae7c_kills"], r["gate_skips"]) for r in pas]
        log(f"FIN passes={fin_line} (wall {time.time() - T0:.0f}s)")
    finally:
        jf.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
