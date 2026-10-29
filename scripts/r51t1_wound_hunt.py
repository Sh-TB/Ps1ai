#!/usr/bin/env python3
"""r51t1_wound_hunt.py — R51 (the 60% track, #5/#9/#10).

The capsule lever (R50 close-out), executed verbatim: the WOUND-
ACCUMULATOR HUNT + the invulnerability census.  The R50 open
measurement: the connect magnitude is UNSETTLED (+500 x3 vs +1000 x3
across R48/R49/R50, all mid-wound-recovery of SURVIVING targets,
pre-states 0x42bc / 0x2b74 / 0x3f48, no discriminator); the strong
class-keyed form stays FALSIFIED; candidates named: a wound-
accumulator word OUTSIDE the bounded 0x88..0xA8 net / hit-geometry
damage.  And PIERCING was discovered: the 0xab94-state target is
bullet-TRANSPARENT (the bullet passed and killed the mortal behind,
+100) — the corridor gate needs an invulnerability predicate.

HYPOTHESIS (verbatim, the capsule R51): a u16 word OUTSIDE the
bounded 0x88..0xA8 net — in the extended wide-net 0x60..0x88 +
0xA8..0xE0 — co-moves with the connect payment magnitude (its pre-
value or delta discriminates the +500 connects from the +1000
connects); and the invulnerability census (0xab94 family + 0xae7c
dwell) closes the piercing hole in the corridor gate.

Method (the capsule): boot -> restore r47_frontier_a -> the R48/R49/
R50 direct-read telemetry VERBATIM with the word net EXTENDED
(disclosed pre-run refinement: read_words reads the union
0x60..0xE0 even offsets = the old bounded net + the capsule's
extended net; the old keys keep their format so R48/R49/R50
correlations join) -> controls (zero-input + movement-only,
verbatim) -> CONNECT group (fresh soft targets, no follow-up; the
corridor gate now checks THROUGH the target +60px BEYOND it — the
piercing predicate) -> KILL group (soft) -> ONE deliberate PIERCE
tap per pass (aimed at an 0xab94-state target with exactly one
mortal within 60px behind; prediction: the behind-mortal pays, the
transparent target does not react — the R50 discovery replicated
n=2) -> the invulnerability census (every census records the
0xab94/0xae7c slots + dwell) -> the r49-style offline global-frame
analysis correlates word pre/delta against the payment magnitude.

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
    census_full, direct_table, frame_walk, full_snapshot, union_post,
    corpse_transitions, TARGET_EXCLUDE_ST, SOFT_ST, TAP_FRAMES,
    TAIL_FRAMES, STATES)
import r50t1_controlled_corridor as R50T          # noqa: E402
from r50t1_controlled_corridor import (           # noqa: E402
    control_move, fire_tap, sc_jumps, slot_alive_in, slot_state_in)
from issue4_controller import boot_to_demo        # noqa: E402

SCRATCH = os.path.join(_REPO, "scratch", "r51")
R50T.SCRATCH = SCRATCH          # fire_tap's event PNGs land in r51
LEDGER = os.path.join(SCRATCH, "boots_used.json")
EVID = os.path.join(_REPO, "data", "games", "SLUS-01212",
                    "truck_evidence", "r51")

FRONTIER = ("r47_frontier_a", "r47_frontier_b")

CONNECT_GOAL = 3          # dedicated 0x42bc-class connects (no follow-up)
KILL_GOAL = 2             # soft kills (the +100 contrast class)
PIERCE_GOAL = 1           # the deliberate 0xab94 pierce replication
MAX_BULLETS_PER_KILL = 4
N_TAPS_CAP = 26
SKIP_RETRIES_MAX = 10
WALL_TAPS_S = 560
CONNECT_ST = 0x42BC       # the hit-reaction state
REG_ST = 0x515C           # the kill-registration state
AE7C_ST = 0xAE7C          # the exonerated-but-tracked class
INVUL_ST = 0xAB94         # the R50 bullet-transparent state
BEYOND_PX = 60.0          # the pierce-through corridor margin

# The capsule's extended wide-net: 0x60..0x86 + 0xAA..0xE0 (even u16
# offsets).  The R48 bounded net 0x88..0xA8 stays in the union so the
# new deltas join the three prior rounds' correlations.
HUNT_NET = tuple(range(0x60, 0x88, 2)) + tuple(range(0xAA, 0xE2, 2))
UNION_NET = tuple(sorted(set(R48.WIDE) | set(HUNT_NET)))

T0 = time.time()


def log(*a):
    print("[r51-t1]", *a, file=sys.stderr, flush=True)


def read_words_hunt(m, slot):
    """The EXTENDED word read (the disclosed pre-run refinement): the
    R48 bounded net + the capsule extended net, one union.  Monkey-
    patched onto R48 so full_snapshot's word_deltas widen without
    touching the R48/R50 protocol code."""
    base = combat.TABLE + slot * combat.STRIDE
    return {hex(off): int(m.u16(base + off)) for off in UNION_NET}


R48.read_words = read_words_hunt      # the disclosed patch point


def amend_ledger(reason):
    os.makedirs(SCRATCH, exist_ok=True)
    os.makedirs(EVID, exist_ok=True)
    if not os.path.exists(LEDGER):
        with open(LEDGER, "w") as f:
            json.dump({"cap": 1, "count": 0, "log": [], "note":
                       "R51 ledger: cap 1 DISCLOSED PRE-RUN = the "
                       "core+rom load ONLY.  NO sandbox rollback: "
                       "the R47 frontiers r47_frontier_a/b SURVIVED "
                       "on disk (verified pre-boot); both passes are "
                       "restore-only (restores are NOT boots, r35 "
                       "precedent).  Lineage TAINTED (never a clean "
                       "claim).  PRE-RUN REFINEMENT: read_words "
                       "widened to the union net 0x60..0xE0 (the R48 "
                       "bounded net + the capsule extended net "
                       "0x60..0x88 + 0xA8..0xE0); the corridor gate "
                       "checks THROUGH the target +60px BEYOND (the "
                       "R50 piercing predicate); ONE deliberate "
                       "PIERCE tap per pass.  m2_gate unchanged.",
                       "hypothesis":
                       "a u16 word OUTSIDE the bounded 0x88..0xA8 "
                       "net (in 0x60..0x88 + 0xA8..0xE0) co-moves "
                       "with the connect payment magnitude "
                       "(+500 vs +1000); the invulnerability "
                       "census (0xab94/0xae7c dwell) closes the "
                       "piercing hole"},
                      f, indent=1)
    with open(LEDGER) as f:
        led = json.load(f)
    led["count"] = int(led.get("count", 0)) + 1
    led.setdefault("log", []).append(
        {"n": led["count"], "ts": time.strftime("%FT%TZ", time.gmtime()),
         "script": "r51t1_wound_hunt.py", "reason": reason})
    with open(LEDGER, "w") as f:
        json.dump(led, f, indent=1)
    log(f"boot ledger: count={led['count']}/{led['cap']} ({reason})")
    return led["count"]


def invulnerable(e):
    return e["st"] in (INVUL_ST, AE7C_ST)


def corridor_occupants(cen, player_x, tgt_x):
    """The R50-verbatim gate (mortal targets): live entities strictly
    between the player and the target — the bullet is absorbed by a
    mortal target, so NOTHING beyond it can matter."""
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
                        "kind": e.get("kind"),
                        "invul": invulnerable(e)})
    return occ


def corridor_occupants_ext(cen, player_x, tgt_x, beyond=BEYOND_PX):
    """The piercing gate (TRANSPARENT targets only): a bullet that
    pierces a 0xab94 target keeps killing BEHIND it, so the corridor
    extends past the target end."""
    hi = max(player_x, tgt_x) + beyond
    lo = min(player_x, tgt_x)
    occ = []
    for e in cen:
        if e["slot"] and e["st"] in combat.CORPSE_ST:
            continue
        if e.get("x_px", 0.0) <= 0.0:
            continue
        if lo < e["x_px"] < hi:
            occ.append({"slot": e["slot"], "st": e["st"],
                        "x": round(e["x_px"], 1),
                        "kind": e.get("kind"),
                        "invul": invulnerable(e)})
    return occ


def invul_census(cen):
    return [{"slot": e["slot"], "st": e["st"],
             "x": round(e.get("x_px", 0.0), 1)}
            for e in cen if invulnerable(e)]


def approach(m, p, tgt):
    if tgt["dx_px"] > 8.0:
        p.core.run(3, {"RIGHT"})
    elif tgt["dx_px"] < -8.0:
        p.core.run(3, {"LEFT"})


def pick_target(cen, used, player_x, intent):
    """CONNECT/KILL: the R50-verbatim clear corridor UP TO the mortal
    target (the bullet is absorbed there).  PIERCE: the 0xab94 target
    itself, corridor clear THROUGH it +60 beyond, EXACTLY ONE mortal
    behind."""
    best = None
    for e in cen:
        if not e["targetable"] or e["slot"] in used:
            continue
        if intent != "PIERCE" and invulnerable(e):
            continue
        if intent == "PIERCE" and e["st"] != INVUL_ST:
            continue
        if intent == "PIERCE":
            occ = [o for o in corridor_occupants_ext(cen, player_x,
                                                     e["x_px"])
                   if o["slot"] != e["slot"]]
            if len(occ) != 1:
                continue
        else:
            occ = [o for o in corridor_occupants(cen, player_x,
                                                 e["x_px"])
                   if o["slot"] != e["slot"]]
            if occ:
                continue
        key = (-abs(e["dx_px"]),)
        if best is None or key < best[0]:
            best = (key, e)
    return best[1] if best else None


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
    out = {"frontier": frontier, "pass_tag": tag, "taps": [],
           "census_at_restore": [], "re_restores": 0,
           "deaths_seen": 0, "connects": 0, "kills": 0,
           "pierces": 0, "gate_skips": 0,
           "invul_dwell_frames": 0,
           "connected_slots": [], "kill_slots": [],
           "pierce_events": []}
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
    out["invul_at_restore"] = invul_census(cen)
    J({"ev": "CENSUS_FULL", "frontier": frontier, "px": s0["px"],
       "n_all": len(cen),
       "n_targetable": len([e for e in cen if e["targetable"]]),
       "invul": out["invul_at_restore"], "entities": cen})
    log(f"census {frontier}: {len(cen)} live, "
        f"invul={len(out['invul_at_restore'])}")
    # ---- the zero-input control walk (the R48/R49/R50 baseline) -----
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
                        "word_deltas": {s: {k: post_w[s][k] - pre_w[s][k]
                                            for k in pre_w[s]}
                                        for s in pre_w},
                        "corpses": corpse_transitions(pre_e, post_e)})
    J({"ev": "TAP", **out["taps"][0], "frontier": frontier})
    # ---- the movement-only control (verbatim) -------------------------
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
                and out["kills"] >= KILL_GOAL \
                and out["pierces"] >= PIERCE_GOAL:
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
        icen = invul_census(cen)
        out["invul_dwell_frames"] += len(icen)
        if icen:
            J({"ev": "INVUL_CENSUS", "frontier": frontier, "tap": i,
               "invul": icen})
        want_connect = out["connects"] < CONNECT_GOAL
        want_pierce = (not want_connect
                       and out["pierces"] < PIERCE_GOAL)
        intent = ("CONNECT" if want_connect
                  else "PIERCE" if want_pierce else "KILL")
        tgt = pick_target(cen, used, player_x, intent)
        if tgt is None:
            # fall through the preference chain before skipping
            for alt in ("CONNECT", "PIERCE", "KILL"):
                if alt == intent:
                    continue
                tgt = pick_target(cen, used, player_x, alt)
                if tgt is not None:
                    intent = alt
                    break
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
        if intent == "CONNECT":
            tap = fire_tap(p, m, J, out, i, "CONNECT", tgt, 1, None)
            used.add(tgt["slot"])
            hit = any(tr["to"] == CONNECT_ST
                      for tr in tap["target_st_transitions"])
            reg = any(tr["to"] == REG_ST
                      for tr in tap["target_st_transitions"])
            if hit and not reg:
                out["connects"] += 1
                out["connected_slots"].append(
                    {"slot": tgt["slot"], "tap": i,
                     "st_pre": tgt["st"],
                     "alive_at_tail": tap["target_alive_at_tail"],
                     "dscore": tap["score_delta"]})
                log(f"CONNECT {out['connects']} slot{tgt['slot']} "
                    f"st_pre={hex(tgt['st'])} "
                    f"dscore={tap['score_delta']}")
            elif reg:
                J({"ev": "CONNECT_BECAME_KILL", "frontier": frontier,
                   "tap": i, "slot": tgt["slot"]})
            else:
                J({"ev": "CONNECT_MISS", "frontier": frontier,
                   "tap": i, "slot": tgt["slot"]})
        elif intent == "PIERCE":
            behind = [o for o in corridor_occupants_ext(
                cen, player_x, tgt["x_px"]) if o["slot"] != tgt["slot"]]
            tap = fire_tap(p, m, J, out, i, "PIERCE", tgt, 1, None)
            used.add(tgt["slot"])
            ev = {"tap": i, "transparent_slot": tgt["slot"],
                  "transparent_st": tgt["st"],
                  "behind": behind,
                  "dscore": tap["score_delta"],
                  "corpses": tap["corpses"],
                  "transparent_reacted": any(
                      tr["to"] == CONNECT_ST
                      for tr in tap["target_st_transitions"])}
            out["pierce_events"].append(ev)
            out["pierces"] += 1
            J({"ev": "PIERCE_RESULT", "frontier": frontier, **ev})
            log(f"PIERCE tap {i}: behind={behind} "
                f"dscore={tap['score_delta']} "
                f"reacted={ev['transparent_reacted']}")
        else:
            kill_id += 1
            kslot = tgt["slot"]
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
                    if [o for o in corridor_occupants(
                            cen2, t1.px_of(m), live["x_px"])
                            if o["slot"] != kslot]:
                        break           # the gate: never fire blind
                    approach(m, p, live)
                    tgt = live
                tap = fire_tap(p, m, J, out, i, "KILL", tgt, b,
                               kill_id)
                reg = any(tr["to"] == REG_ST
                          for tr in tap["target_st_transitions"])
                if reg or tap["corpses"] or \
                        tap["target_alive_at_tail"] is False:
                    out["kills"] += 1
                    out["kill_slots"].append(
                        {"slot": kslot, "kill_id": kill_id,
                         "bullets": b})
                    log(f"KILL {kill_id} resolved slot{kslot} "
                        f"bullets={b}")
                    break
            else:
                used.add(kslot)
                J({"ev": "KILL_UNRESOLVED", "frontier": frontier,
                   "slot": kslot, "bullets": b})
                continue
    # ---- the second movement control (post-taps) ----------------------
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
       "pierces": out["pierces"], "gate_skips": out["gate_skips"],
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
    # the r47/r50 boot-1 defect precedent: boot 1 of this round spent
    # the ledger on a GATE-STARVATION defect (the beyond-margin put
    # every candidate inside its own corridor) - ZERO bullets fired,
    # ZERO protocol taps, the world touched only by the controls -
    # the cap amendment 1->2 is DISCLOSED HERE, before boot 2 runs.
    if os.path.exists(LEDGER):
        with open(LEDGER) as f:
            prev = json.load(f)
        cnt, cap = prev.get("count", 0), prev.get("cap", 1)
        if cnt >= 2 and cap < 3:
            prev["cap"] = 3
            prev.setdefault("log", []).append(
                {"n": cnt,
                 "ts": time.strftime("%FT%TZ", time.gmtime()),
                 "script": "r51t1_wound_hunt.py",
                 "cap_amendment":
                     "cap 2->3 DISCLOSED (the r47 2->3 defect "
                     "precedent): boot 2 also STARVED (29s wall, "
                     "ZERO bullets, ZERO protocol taps) - the "
                     "beyond-margin was still applied to MORTAL "
                     "targets (the bullet is absorbed by a mortal "
                     "target; only a TRANSPARENT target continues).  "
                     "boot 3 = the corrected gate: the R50-verbatim "
                     "corridor UP TO the target for CONNECT/KILL, "
                     "the +60px beyond extension for the PIERCE "
                     "intent ONLY; the gate dry-run "
                     "(r51_gate_dryrun.py, offline) PROVES taps flow "
                     "on the boot-2 census (CONNECT/KILL admitted on "
                     "both frontiers) before boot 3 was spent."})
            json.dump(prev, open(LEDGER, "w"), indent=1)
            log("cap amended 2->3 DISCLOSED (boot-2 gate defect, "
                "zero bullets; dry-run PASS)")
    n = amend_ledger("BOOT (core+rom load ONLY): restore "
                     "r47_frontier_a -> the wound-accumulator hunt "
                     "(union net 0x60..0xE0; the piercing corridor "
                     "gate +60 beyond; CONNECT x3 no-follow-up, KILL "
                     "x2, PIERCE x1; 2 movement-only controls; the "
                     "invulnerability census) -> restore "
                     "r47_frontier_b if goals unmet -> report.")
    if n > 3:
        raise SystemExit("BOOT CAP EXCEEDED (3 - the disclosed "
                         "defect amendments 1->2 + 2->3)")
    tag = time.strftime("r51_%H%M%S")
    stem = f"r51_boot{n}"
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
       "protocol": f"the wound-accumulator hunt: UNION_NET="
                   f"{[hex(o) for o in UNION_NET[:3]]}.."
                   f"{hex(UNION_NET[-1])} ({len(UNION_NET)} u16 "
                   f"offsets, the R48 bounded net + the capsule "
                   f"extended net); the corridor gate checks THROUGH "
                   f"the target +{BEYOND_PX:.0f}px BEYOND (the R50 "
                   f"piercing predicate); CONNECT_GOAL={CONNECT_GOAL} "
                   f"no-follow-up; KILL_GOAL={KILL_GOAL}; "
                   f"PIERCE_GOAL={PIERCE_GOAL} (0xab94 transparent "
                   f"target, exactly 1 mortal within {BEYOND_PX:.0f}px "
                   f"behind); TAP_FRAMES={TAP_FRAMES}+TAIL_FRAMES="
                   f"{TAIL_FRAMES} DIRECT table reads (R48 "
                   f"verbatim); the invulnerability census at every "
                   f"tap",
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
                    and r["kills"] >= KILL_GOAL
                    and r["pierces"] >= PIERCE_GOAL)
            if done or r.get("note") in (
                    "dead on restore", "frontier dead after restore"):
                break
        res = {"passes": pas, "final": t1.snap(m)}
        rep = {"schema": "ps1play.r51-wound-hunt/1",
               "generated": time.strftime("%FT%TZ", time.gmtime()),
               "commit": os.popen("git -C %s rev-parse HEAD"
                                  % _REPO).read().strip(),
               "frontiers_on_disk": have,
               "union_net": [hex(o) for o in UNION_NET],
               "run": res}
        with open(os.path.join(EVID, f"{stem}_report.json"), "w") as f:
            json.dump(rep, f, indent=1, default=str)
        fin_line = [(r["frontier"], r["connects"], r["kills"],
                     r["pierces"], r["gate_skips"]) for r in pas]
        log(f"FIN passes={fin_line} (wall {time.time() - T0:.0f}s)")
    finally:
        jf.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
