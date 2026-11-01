#!/usr/bin/env python3
"""r66t1_payframe_destarve.py — R66 (Issues #5/#10 primary experiment).

The R53 capsule lever + the R65-specified smallest decisive experiment,
executed with the R52 discipline:

  stage 1  the tainted frontier REBUILD boot: restore issue5_m1_start
           (validated pre-run this round) -> the shipped policy in 15f
           chunks with continue-rescues (deaths counted, TAINTED
           lineage) -> eager rolling frontier saves r66_frontier_a/b
           past px 1200 every >=25 px (sane-clamped) -> early exit when
           both saved and latest px >= 1240.

  stage 2  restore-only from the r66 frontiers.  The R51/R52 protocol
           structure verbatim (the zero-input + movement-only controls,
           the invulnerability census, the corridor gate: UP-TO mortal,
           CONNECT no-follow-up, KILL contrast) with the pay-frame
           union-net telemetry (frame_walk_hunt verbatim) and THREE
           DISCLOSED R66 amendments (pre-run):

      A. GATE_DIAG — the per-skip blocking-occupant dump the R52
         starvation never recorded: EVERY live entity (slot/st/x/
         kind/targetable/invul) + per-candidate rejection reason
         (invulnerable | corridor_occupied + the occupant list) +
         player px.  This is the starvation diagnostic the R53
         capsule named FIRST.
      B. PIERCE WITHHELD — PIERCE_GOAL=0 (the n=4 evidence: taps in
         the wasp window pierce without reaction; the R65 spec says
         withhold them and let the gate body pass).
      C. THE DE-STARVE ARM (pass B only, evidence-gated): when the
         gate skips, the runner ADVANCES the player forward (bounded
         RIGHT walks, budget-capped) instead of only settling 6f —
         the R52 protocol never advanced the player, and the R52
         frontier sits at the x~1277-1351 spawner-cluster edge.  Pass
         A is verbatim (diagnostics only); pass B arms the advance.

  Oracle unchanged: walker words + verified score gains + alive
  0x0EE518; never +0x8E in any oracle (the union net = disclosed
  exploratory telemetry, the R45..R52 precedent).

  No RAM writes anywhere.  Legal inputs only (pad buttons).  Save
  states are used as restore points between passes, never rewound
  into a claimed clean run (all lineage here is TAINTED and labeled).

Evidence: data/games/SLUS-01212/truck_evidence/r66/
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
import r47t1_singletap_taps as R47T               # noqa: E402
import r48t1_frame_exact_taps as R48              # noqa: E402
import r50t1_controlled_corridor as R50T          # noqa: E402
import r51t1_wound_hunt as R51T                   # noqa: E402
from r51t1_wound_hunt import (                    # noqa: E402
    invulnerable, corridor_occupants, invul_census, approach,
    pick_target)
from r48t1_frame_exact_taps import (              # noqa: E402
    census_full, direct_table, full_snapshot, union_post,
    corpse_transitions, mini_census, TAP_FRAMES, TAIL_FRAMES, STATES,
    RE_RESTORE_MAX)
from issue4_controller import boot_to_demo        # noqa: E402

SCRATCH = os.path.join(_REPO, "scratch", "r66")
PNGDIR = os.path.join(SCRATCH, "pngs")
LEDGER = os.path.join(SCRATCH, "boots_used.json")
EVID = os.path.join(_REPO, "data", "games", "SLUS-01212",
                    "truck_evidence", "r66")

ANCHOR = "issue5_m1_start"
FRONTIER = ("r66_frontier_a", "r66_frontier_b")

# goals — DISCLOSED PRE-RUN (the R52 structure, PIERCE withheld per
# the R65 spec; KILL contrast kept at 1 to spend the budget on the
# CONNECT class where the missing +500 lives)
CONNECT_GOAL = 4
KILL_GOAL = 1
PIERCE_GOAL = 0
N_TAPS_CAP = 30
SKIP_RETRIES_MAX = 12
WALL_TAPS_S = 420
# the de-starve arm (pass B): advance budget per pass, in frames
ADVANCE_BUDGET_F = 240
ADVANCE_STEP_F = 15

T0 = time.time()


def log(*a):
    print("[r66-t1]", *a, file=sys.stderr, flush=True)


# ------------------------------------------------------------------
# THE R52 LEVER verbatim: pay-frame union-net telemetry.
# ------------------------------------------------------------------
UNION_NET = R51T.UNION_NET          # 0x60..0xE0 even (the R51 union)
_WORD_CACHE = tuple(UNION_NET)


def frame_walk_hunt(p, m, J, tap, phase, n_frames, btns):
    rows = []
    for k in range(n_frames):
        p.core.run(1, btns)
        sc = int(m.u32(t1.A_SCORE))
        px = t1.px_of(m)
        ents = mini_census(m, px)
        words = {}
        for e in ents:
            slot = e["slot"]
            if not slot or e["x"] == 0.0:
                continue
            base = combat.TABLE + slot * combat.STRIDE
            words[str(slot)] = [int(m.u16(base + off))
                                for off in _WORD_CACHE]
        rows.append({"f_rel": k + 1, "sc": sc, "px": round(px, 1),
                     "ents": ents,
                     "direct": direct_table(m),
                     "words": words,
                     "net": [hex(o) for o in _WORD_CACHE]
                     if k == 0 else None})
    J({"ev": "FRAME_WALK", "tap": tap, "phase": phase,
       "n": n_frames, "rows": rows})
    return rows


R50T.frame_walk = frame_walk_hunt     # the DISCLOSED patch point (R52)


def png(p, name, tag):
    try:
        rgb = p.core.frame_rgb()
        if rgb is not None:
            from PIL import Image
            os.makedirs(PNGDIR, exist_ok=True)
            Image.fromarray(rgb).save(
                os.path.join(PNGDIR, f"{tag}_{name}.png"))
    except Exception as e:                                  # noqa: BLE001
        log("png failed:", repr(e)[:120])


R50T.png = png
R47T.png = png
R47T.PNGDIR = PNGDIR
R47T.FRONTIER = FRONTIER


def amend_ledger(reason):
    os.makedirs(SCRATCH, exist_ok=True)
    os.makedirs(EVID, exist_ok=True)
    if not os.path.exists(LEDGER):
        with open(LEDGER, "w") as f:
            json.dump({"cap": 2, "count": 0, "log": [], "note":
                       "R66 cap 2 DISCLOSED PRE-RUN (the R47 "
                       "two-stage FOREGROUND protocol).  FOURTH "
                       "sandbox rollback disclosure: scratch/ was "
                       "reset — the r52_frontier_a/b states are "
                       "LOST (never committed - no-game-bytes); "
                       "issue5_m1_start (Oct 20) SURVIVED and was "
                       "RE-VALIDATED this round by boot 1 "
                       "(r66_env_probe.json: restores alive, "
                       "px 258.6, survives 60f idle).  The capsule "
                       "contingency applies verbatim: a rebuild "
                       "boot, disclosed.  boot1(env probe, spent) + "
                       "this ledger's boot = stage-1 rebuild; the "
                       "NEXT boot = stage-2 restore-only hunt.  "
                       "Lineage TAINTED (never a clean claim).  "
                       "R66 AMENDMENTS DISCLOSED PRE-RUN: (A) "
                       "GATE_DIAG per-skip blocking-occupant dump; "
                       "(B) PIERCE withheld (PIERCE_GOAL=0, the n=4 "
                       "evidence + the R65 spec); (C) pass B arms "
                       "the bounded forward-advance de-starve arm "
                       "(ADVANCE_BUDGET_F=240, RIGHT walks on skip). "
                       "Goals CONNECT=4 KILL=1.  m2_gate unchanged.",
                       "hypothesis":
                       "the +500 connect class is capturable under "
                       "pay-frame telemetry once the corridor gate "
                       "is de-starved; the gate starved in R52 "
                       "because the frontier sits at the spawner-"
                       "cluster edge and the protocol never "
                       "advanced the player (to be CONFIRMED by "
                       "the GATE_DIAG dump, not assumed); any word "
                       "whose pay-frame value separates +500 from "
                       "+1000 with ZERO overlap refines payment = "
                       "f(wound_state); the slot12 +0xa0 accumulator "
                       "candidate is tested first"},
                      f, indent=1)
    with open(LEDGER) as f:
        led = json.load(f)
    if int(led.get("count", 0)) + 1 > int(led.get("cap", 0)):
        raise SystemExit(
            f"BOOT CAP EXCEEDED (ledger cap {led.get('cap')}; "
            "the ledger is the disclosed authority; no entry "
            "consumed)")
    led["count"] = int(led.get("count", 0)) + 1
    led.setdefault("log", []).append(
        {"n": led["count"], "ts": time.strftime("%FT%TZ", time.gmtime()),
         "script": "r66t1_payframe_destarve.py", "reason": reason})
    with open(LEDGER, "w") as f:
        json.dump(led, f, indent=1)
    log(f"boot ledger: count={led['count']}/{led['cap']} ({reason})")
    return led["count"]


# ------------------------------------------------------------------
# R66 amendment A: the per-skip blocking-occupant dump.
# ------------------------------------------------------------------
def corridor_occupants_r66(cen, player_x, tgt_x):
    """THE R66 EVIDENCE-CORRECTED GATE (game-semantic, MSX-owned).

    The R50/R51 gate counted EVERY live entity between player and
    target as a blocker.  The R66 pass-A GATE_DIAG dump (13 skips,
    r66_boot3_s2a.jsonl) shows the top blockers are entities that
    CANNOT absorb a player bullet or register a payment:

      * projectile_air (st 0xbdf8/0x1be0/0x2950/0x9558/0xac64):
        in-flight projectiles — a different entity layer; no observed
        bullet interaction or payment across R38-R52;
      * st 0xab94 (the transparent wasp): bullet-TRANSPARENT per the
        n=4 piercing evidence (R50/R51: bullets pass through and
        kill behind it; the target NEVER reacts, never pays).

    A blocker must be able to ABSORB the bullet or REGISTER the
    payment: mortal enemy-kind entities that are not corpses, not
    x=0, not in-flight projectiles, not 0xab94.  st 0xae7c still
    blocks (it registered kills in R48-R51 — it absorbs bullets).
    """
    lo, hi = min(player_x, tgt_x), max(player_x, tgt_x)
    occ = []
    for e in cen:
        if e["slot"] and e["st"] in combat.CORPSE_ST:
            continue
        if e.get("x_px", 0.0) <= 0.0:
            continue
        if e.get("kind") == "projectile_air":
            continue
        if e.get("st") == R51T.INVUL_ST:
            continue
        if lo < e["x_px"] < hi:
            occ.append({"slot": e["slot"], "st": e["st"],
                        "x": round(e["x_px"], 1),
                        "kind": e.get("kind")})
    return occ


def pick_target_r66(cen, used, player_x):
    """The R66 target selection on the corrected gate: CONNECT targets
    prefer a FRESH soft state (0x4054) — the freshness-spread
    hypothesis (the R48 +500 came from a fresh 0x4054 connect; the
    +1000s all came from wound-recovery st_pre 0x42bc/0x3f48/0x2b74)
    — then the farthest clear target.  The bullet-transparent 0xab94
    is never a connect target."""
    best = None
    for e in cen:
        if not e.get("targetable") or e["slot"] in used:
            continue
        if e.get("st") == R51T.INVUL_ST:
            continue
        occ = [o for o in corridor_occupants_r66(cen, player_x,
                                                 e["x_px"])
               if o["slot"] != e["slot"]]
        if occ:
            continue
        key = (0 if e["st"] == R48.SOFT_ST else 1,
               -abs(e["dx_px"]))
        if best is None or key < best[0]:
            best = (key, e)
    return best[1] if best else None


def gate_diag(cen, player_x, used):
    """WHY is the gate starving?  Every live entity classified, and
    every targetable candidate with its rejection reason."""
    ents = []
    for e in cen:
        if not e["slot"] or e.get("x_px", 0.0) <= 0.0:
            continue
        ents.append({"slot": e["slot"], "st": e["st"],
                     "x": round(e.get("x_px", 0.0), 1),
                     "kind": e.get("kind"),
                     "targetable": bool(e.get("targetable")),
                     "invul": bool(invulnerable(e))})
    rejected = []
    for e in cen:
        if not e.get("targetable") or e["slot"] in used:
            continue
        if e.get("x_px", 0.0) <= 0.0:
            continue
        if invulnerable(e):
            rejected.append({"slot": e["slot"], "st": e["st"],
                             "x": round(e["x_px"], 1),
                             "reason": "invulnerable"})
            continue
        occ = [o for o in corridor_occupants(cen, player_x, e["x_px"])
               if o["slot"] != e["slot"]]
        if occ:
            rejected.append({"slot": e["slot"], "st": e["st"],
                             "x": round(e["x_px"], 1),
                             "reason": "corridor_occupied",
                             "occupants": occ})
        else:
            rejected.append({"slot": e["slot"], "st": e["st"],
                             "x": round(e["x_px"], 1),
                             "reason": "usable_but_lost_race"})
    return {"entities": ents, "candidates_rejected": rejected,
            "n_live": len(ents),
            "n_targetable": len([x for x in ents
                                 if x["targetable"]]),
            "n_invul": len([x for x in ents if x["invul"]])}


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


# ------------------------------------------------------------------
# the tap + control bodies (R50T verbatim on the pay-frame telemetry)
# ------------------------------------------------------------------
def fire_tap(p, m, J, out, i, intent, tgt, bullet, kill_id):
    return R50T.fire_tap(p, m, J, out, i, intent, tgt, bullet, kill_id)


def control_move(p, m, J, out, i):
    return R50T.control_move(p, m, J, out, i)


def run_pass(p, m, J, tag, frontier, destarve):
    out = {"frontier": frontier, "pass_tag": tag, "destarve": destarve,
           "taps": [], "census_at_restore": [], "re_restores": 0,
           "deaths_seen": 0, "connects": 0, "kills": 0,
           "gate_skips": 0, "gate_diags": [],
           "advance_frames_used": 0,
           "invul_dwell_frames": 0,
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
    out["invul_at_restore"] = invul_census(cen)
    J({"ev": "CENSUS_FULL", "frontier": frontier, "px": s0["px"],
       "n_all": len(cen),
       "n_targetable": len([e for e in cen if e["targetable"]]),
       "invul": out["invul_at_restore"], "entities": cen})
    log(f"census {frontier}: {len(cen)} live, "
        f"invul={len(out['invul_at_restore'])}")
    # ---- the zero-input control walk (the R48-R52 baseline) ---------
    cen, pre_e, pre_w = full_snapshot(m)
    pre_sc = int(m.u32(t1.A_SCORE))
    ctrl_rows = frame_walk_hunt(p, m, J, 0, "CONTROL_ZERO_INPUT",
                                TAP_FRAMES + TAIL_FRAMES, set())
    cen2, post_e, post_w = full_snapshot(m)
    post_e, post_w = union_post(m, post_e, post_w, pre_e)
    post_sc = int(m.u32(t1.A_SCORE))
    out["taps"].append({"tap": 0, "kind": "CONTROL_ZERO_INPUT",
                        "score_delta": post_sc - pre_sc,
                        "frame_rows": ctrl_rows,
                        "corpses": corpse_transitions(pre_e, post_e)})
    J({"ev": "TAP", **out["taps"][0], "frontier": frontier})
    # ---- the movement-only control (verbatim) -------------------------
    control_move(p, m, J, out, 1)
    # ---- the gated tap loop -------------------------------------------
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
            if out["re_restores"] > RE_RESTORE_MAX:
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
        intent = "CONNECT" if want_connect else "KILL"
        if destarve:
            # amendment C: the corrected gate + fresh-soft preference
            tgt = pick_target_r66(cen, used, player_x)
        else:
            tgt = pick_target(cen, used, player_x, intent)
        if tgt is None:
            for alt in ("CONNECT", "KILL"):
                if alt == intent:
                    continue
                tgt = pick_target(cen, used, player_x, alt)
                if tgt is not None:
                    intent = alt
                    break
        if tgt is None:
            skips += 1
            out["gate_skips"] = skips
            diag = gate_diag(cen, player_x, used)
            out["gate_diags"].append({"tap": i, **diag})
            J({"ev": "GATE_DIAG", "frontier": frontier, "tap": i,
               "player_x": round(player_x, 1), **diag})
            log(f"tap {i}: GATE_SKIP #{skips} px={player_x:.0f} "
                f"live={diag['n_live']} tgt={diag['n_targetable']} "
                f"invul={diag['n_invul']} "
                f"rejected={len(diag['candidates_rejected'])}")
            if skips > SKIP_RETRIES_MAX:
                out["note"] = "corridor gate starved (retries gone)"
                break
            if destarve and out["advance_frames_used"] < \
                    ADVANCE_BUDGET_F:
                # amendment C: advance the player forward (bounded)
                p.core.run(ADVANCE_STEP_F, {"RIGHT"})
                out["advance_frames_used"] += ADVANCE_STEP_F
                J({"ev": "DESTARVE_ADVANCE", "frontier": frontier,
                   "tap": i, "step_f": ADVANCE_STEP_F,
                   "budget_used": out["advance_frames_used"]})
            else:
                p.core.run(6, set())      # the verbatim settle
            continue
        approach(m, p, tgt)
        if intent == "CONNECT":
            tap = fire_tap(p, m, J, out, i, "CONNECT", tgt, 1, None)
            used.add(tgt["slot"])
            hit = any(tr["to"] == R51T.CONNECT_ST
                      for tr in tap["target_st_transitions"])
            reg = any(tr["to"] == R51T.REG_ST
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
                log(f"tap {i}: single bullet REGISTERED slot"
                    f"{tgt['slot']} — one-hit, not a connect")
            else:
                J({"ev": "CONNECT_MISS", "frontier": frontier,
                   "tap": i, "slot": tgt["slot"]})
                log(f"tap {i}: connect missed (no 0x42bc)")
        else:
            kill_id += 1
            kslot = tgt["slot"]
            reg_done = False
            b = 0
            for b in range(1, R51T.MAX_BULLETS_PER_KILL + 1):
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
                    if [o for o in (corridor_occupants_r66 if destarve
                                    else corridor_occupants)(
                            cen2, t1.px_of(m), live["x_px"])
                            if o["slot"] != kslot]:
                        break           # the gate: never fire blind
                    approach(m, p, live)
                    tgt = live
                tap = fire_tap(p, m, J, out, i, "KILL", tgt, b,
                               kill_id)
                reg = any(tr["to"] == R51T.REG_ST
                          for tr in tap["target_st_transitions"])
                if reg or tap["corpses"] or \
                        tap["target_alive_at_tail"] is False:
                    reg_done = True
                    break
            if reg_done:
                out["kills"] += 1
                out["kill_slots"].append(
                    {"slot": kslot, "kill_id": kill_id,
                     "bullets": b})
                log(f"KILL {kill_id} resolved slot{kslot} "
                    f"bullets={b}")
            else:
                used.add(kslot)
                J({"ev": "KILL_UNRESOLVED", "frontier": frontier,
                   "slot": kslot, "bullets": b})
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
       "gate_skips": out["gate_skips"],
       "advance_frames_used": out["advance_frames_used"],
       "connect_survival_at_walk_end":
           out["connect_survival_at_walk_end"]})
    return out


def do_stage1(J, tag, stem):
    """boot: the tainted frontier rebuild (the R47 stage-1 verbatim,
    r66_frontier_a/b names)."""
    p = boot_to_demo()
    m = p.mem
    p.load_state(ANCHOR)
    if not t1.alive(m):
        raise SystemExit(f"anchor restore not alive: {t1.snap(m)}")
    J({"ev": "ANCHOR_RESTORED", "state": ANCHOR, **t1.snap(m)})
    log(f"anchor restored px={t1.px_of(m):.1f}")
    res = {"push": R47T.push_phase(p, m, J, tag)}
    res["final"] = t1.snap(m)
    rep = {"schema": "ps1play.r66-destarve/1", "stage": 1,
           "generated": time.strftime("%FT%TZ", time.gmtime()),
           "commit": os.popen("git -C %s rev-parse HEAD"
                              % _REPO).read().strip(),
           "anchor": ANCHOR, "frontiers": FRONTIER, "run": res}
    with open(os.path.join(EVID, f"{stem}_report.json"), "w") as f:
        json.dump(rep, f, indent=1, default=str)
    log(f"STAGE1 FIN push={res['push']['outcome']} "
        f"frontiers={res['push'].get('frontiers')} "
        f"px={res['push'].get('frontier_px', -1):.1f}")
    return 0


def do_stage2(J, tag, stem, only=None):
    """only: 'a' -> the verbatim diagnostics pass on frontier_a ONLY;
    'b' -> the de-starve pass on frontier_b ONLY; None -> both (the
    original two-pass single-boot plan).  The split exists because the
    tool window caps one process at ~10 min while two guarded passes
    can reach ~15; each invocation is its own disclosed boot."""
    order = []
    for fr in FRONTIER:
        if os.path.exists(os.path.join(STATES, fr + ".state")):
            order.append(fr)
        else:
            J({"ev": "FRONTIER_ABSENT", "frontier": fr})
    if not order:
        raise SystemExit("no r66_frontier_* states on disk - run "
                         "stage 1 first (never fabricate a frontier)")
    if only == "a":
        order = order[:1]
    elif only == "b":
        order = order[1:]
    p = boot_to_demo()
    m = p.mem
    pas = []
    for k, fr in enumerate(order):
        # pass A (frontier_a): verbatim diagnostics.  pass B
        # (frontier_b): the de-starve arm armed (disclosed pre-run).
        destarve = (fr == FRONTIER[1]) or (only == "b")
        if only == "a":
            destarve = False
        r = run_pass(p, m, J, tag, fr, destarve=destarve)
        pas.append(r)
        done = (r["connects"] >= CONNECT_GOAL
                and r["kills"] >= KILL_GOAL)
        if done or r.get("note") in (
                "dead on restore", "frontier dead after restore"):
            break
    res = {"passes": pas, "final": t1.snap(m)}
    rep = {"schema": "ps1play.r66-destarve/1", "stage": 2,
           "generated": time.strftime("%FT%TZ", time.gmtime()),
           "commit": os.popen("git -C %s rev-parse HEAD"
                              % _REPO).read().strip(),
           "anchor": ANCHOR, "frontiers_on_disk": order,
           "union_net": [hex(o) for o in UNION_NET],
           "amendments": {"gate_diag": True, "pierce_withheld": True,
                          "destarve_advance_pass_b": True},
           "run": res}
    with open(os.path.join(EVID, f"{stem}_report.json"), "w") as f:
        json.dump(rep, f, indent=1, default=str)
    fin_line = [(r["frontier"], r["connects"], r["kills"],
                 r["gate_skips"], r["advance_frames_used"])
                for r in pas]
    log(f"STAGE2 FIN passes={fin_line}")
    return 0


def main():
    global T0
    T0 = time.time()
    stage = (sys.argv[1] if len(sys.argv) > 1 else "1").strip()
    only = (sys.argv[2] if len(sys.argv) > 2 else None)
    if stage == "2":
        assert only in ("a", "b", None), \
            "usage: r66t1_payframe_destarve.py 2 [a|b]"
    assert stage in ("1", "2"), \
        "usage: r66t1_payframe_destarve.py [1|2] [a|b]"
    reasons = {
        "1": "BOOT stage-1 (the tainted frontier REBUILD; DISCLOSED: "
             "the FOURTH sandbox rollback lost the r52_frontier_a/b "
             "states (never committed - no-game-bytes); "
             "issue5_m1_start SURVIVED, re-validated by boot 1 "
             "r66_env_probe; the capsule contingency verbatim, the "
             "R45/R47/R52 precedent): boot -> restore issue5_m1_"
             "start -> tainted push (deaths counted, continue-"
             "rescues counted, eager frontier saves r66_frontier_a/b "
             "px>1200 every >=25px sane-clamped, early exit both "
             "saved & latest >=1240) -> exit",
        "2": "BOOT stage-2%s (the INSTRUMENTED PAY-FRAME DE-STARVE "
             "hunt, restore-only): boot -> restore r66_frontier_a "
             "-> pass A verbatim diagnostics (GATE_DIAG per-skip "
             "dump; PIERCE withheld)%s Goals CONNECT=4 KILL=1.  "
             "The a/b split is DISCLOSED: the tool window caps one "
             "process at ~10 min; each pass is its own disclosed "
             "boot instead of one two-pass boot."
             % ("" if only is None else f" pass {only.upper()}",
                "" if only is None else (
                    " -> restore r66_frontier_b -> pass B with the "
                    "bounded forward-advance de-starve arm"
                    if only == "b" else
                    " (diagnostics only this boot)")),
    }
    n = amend_ledger(reasons[stage])
    tag = time.strftime(f"r66_{stage}{only or ''}_%H%M%S")
    stem = f"r66_boot{n}_s{stage}{only or ''}"
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
       "stage": stage,
       "rollback_disclosure":
           "FOURTH sandbox rollback: scratch/ reset — the "
           "r52_frontier_a/b states LOST (never committed - "
           "no-game-bytes); issue5_m1_start survived (Oct 20) and "
           "was re-validated by this round's boot 1 "
           "(r66_env_probe.json); the capsule contingency (a "
           "rebuild boot, disclosed) applies verbatim",
       "lineage": ("TAINTED (continue-rescues; never a clean claim)"
                   if stage == "1" else
                   "TAINTED frontier postures (restore-only taps)"),
       "oracle": "walker words + verified score gains + alive "
                 "0x0EE518; never +0x8E (the union net = disclosed "
                 "exploratory telemetry)",
       "protocol": "TAP_FRAMES=3 + TAIL_FRAMES=20; frame_walk_hunt "
                   "records the union-net u16 states for every live "
                   "slot EVERY frame (the R52 pay-frame lever "
                   "verbatim); CONNECT_GOAL="
                   f"{CONNECT_GOAL} KILL_GOAL={KILL_GOAL} "
                   f"PIERCE_GOAL={PIERCE_GOAL} (WITHHELD); GATE_DIAG "
                   "per-skip; pass B arms the bounded advance",
       "ts": time.strftime("%FT%TZ", time.gmtime())})
    try:
        if stage == "1":
            rc = do_stage1(J, tag, stem)
        else:
            rc = do_stage2(J, tag, stem, only=only)
    finally:
        jf.close()
    log(f"report -> {EVID}/{stem}_report.json "
        f"(wall {time.time() - T0:.0f}s)")
    return rc


if __name__ == "__main__":
    sys.exit(main())
