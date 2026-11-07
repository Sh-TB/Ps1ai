#!/usr/bin/env python3
"""r67t1_payframe_500hunt.py — R67 (Issues #5/#10 primary experiment).

THE CAPSULE LEVER R67 verbatim:
  "restore r66_frontier_a/b -> CONNECT taps preferring fresh 0x4054
   with the pay-frame telemetry verbatim until TWO +500 captures land
   -> the zero-overlap test on the widened set -> the product-path
   truck campaign ... as the separate gameplay track".

BUDGET LINE verbatim: "restore-only arms from the r66 frontiers while
they survive on disk (a rebuild boot only if lost, disclosed)".

Disclosed deltas from the R66 runner (r66t1_payframe_destarve.py,
imported verbatim for its helpers):

  A. THE GOAL: the R66 CONNECT=4/KILL=1 stop rule is replaced by
     PAY500_GOAL=2 — the pass stops when TWO +500 payments have landed
     ACROSS THE ROUND (the R66 findings §7 smallest decisive
     experiment: n>=2 +500 captures under the SAME telemetry).  The
     shared round counter lives in scratch/r67/pay500_counter.json and
     is updated ATOMICALLY with each verified +500 (the R52
     ledger-counting rule).
  B. THE TARGETS: pick_target_r66 verbatim (fresh-soft 0x4054
     preference on the R66-corrected corridor gate — the
     freshness-spread lead).
  C. THE DE-STARVE ARM: armed on BOTH passes (the R66 pass-B evidence:
     the bounded forward advance found the targets that paid; both
     frontiers sit at the spawner-cluster edge).
  D. THE TELEMETRY: verbatim (the R66 pay-frame union-net frame walk
     through the R50T.fire_tap patch point: TAP_FRAMES=3 + TAIL=20,
     mini census, direct table, UNION_NET 0x60..0xE0 even).
  E. THE LEDGER: a FRESH r67 ledger (scratch/r67/boots_used.json),
     cap 3 DISCLOSED PRE-RUN: boot 1 = the env probe
     (r67_env_probe.py), boot 2 = the frontier_a hunt, boot 3 = the
     frontier_b hunt.  RESTORE-ONLY: NO rebuild boot — the r66
     frontiers are on disk (verified pre-run by the dry-run and
     re-validated by boot 1).  If a restore proves dead on THIS
     machine the pass records it honestly and the capsule contingency
     (a rebuild boot, disclosed) applies OUT of this cap.
  F. m2_gate unchanged (interactive M2 entry stays gated on a clean
     deaths=0 no-restart deep-resolve posture).
  G. THE GATE CORPSE SET (a dry-run finding, disclosed): the R66
     experiment gate used combat.CORPSE_ST = {0x4BE4, 0x5CC8} — the
     death-registration terminal 0x5B0C is NOT in it, so a
     just-registered corpse could still block the corridor.  The
     committed PRODUCT adapter contract
     (ps1play/adapters/metal_slug_x/adapter.py CORPSE_ST) INCLUDES
     0x5B0C.  The R67 hunt aligns the experiment gate with the
     product contract: corridor_occupants_r67 / pick_target_r67 are
     the R66 functions verbatim with the 0x5B0C exclusion added
     (pinned by the dry-run); the R66 script itself is NOT edited
     (it stays the disclosure baseline of its completed round).

Oracle unchanged: walker words + verified score gains + alive
0x0EE518; never +0x8E in any oracle.  No RAM writes anywhere.  Legal
inputs only (pad buttons).  Save states are restore points between
passes, never rewound into a claimed clean run (all lineage TAINTED
and labeled — the R66 disclosure).

Evidence: data/games/SLUS-01212/truck_evidence/r67/
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
from r51t1_wound_hunt import (                     # noqa: E402
    invul_census, approach, pick_target)
from r48t1_frame_exact_taps import (              # noqa: E402
    census_full, direct_table, full_snapshot, union_post,
    corpse_transitions, TAP_FRAMES, TAIL_FRAMES, STATES,
    RE_RESTORE_MAX)
from r66t1_payframe_destarve import (             # noqa: E402
    frame_walk_hunt, corridor_occupants_r66, pick_target_r66,
    gate_diag, slot_state_in, sc_jumps, slot_alive_in,
    ADVANCE_BUDGET_F, ADVANCE_STEP_F, SKIP_RETRIES_MAX)
from issue4_controller import boot_to_demo        # noqa: E402

SCRATCH = os.path.join(_REPO, "scratch", "r67")
PNGDIR = os.path.join(SCRATCH, "pngs")
LEDGER = os.path.join(SCRATCH, "boots_used.json")
COUNTER = os.path.join(SCRATCH, "pay500_counter.json")
EVID = os.path.join(_REPO, "data", "games", "SLUS-01212",
                    "truck_evidence", "r67")

FRONTIER = ("r66_frontier_a", "r66_frontier_b")

# ---- R67 goals — DISCLOSED PRE-RUN -----------------------------------
PAY500_GOAL = 2               # the capsule lever verbatim
N_TAPS_CAP = 30
WALL_TAPS_S = 420

T0 = time.time()


def log(*a):
    print("[r67-t1]", *a, file=sys.stderr, flush=True)


# ---- the ledger + the round +500 counter -----------------------------
def _write(path, obj):
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(obj, f, indent=1)
    os.replace(tmp, path)


def amend_ledger(reason):
    os.makedirs(SCRATCH, exist_ok=True)
    os.makedirs(EVID, exist_ok=True)
    if not os.path.exists(LEDGER):
        _write(LEDGER, {
            "cap": 3, "count": 0, "log": [],
            "note": (
                "R67 cap 3 DISCLOSED PRE-RUN (restore-only round): "
                "boot 1 = the env probe (r67_env_probe.py: boot -> "
                "restore-validate issue5_m1_start + BOTH r66 "
                "frontiers on THIS machine); boot 2 = the frontier_a "
                "hunt; boot 3 = the frontier_b hunt.  NO rebuild "
                "boot: the r66 frontiers SURVIVED on disk (verified "
                "pre-run; the capsule budget line verbatim).  "
                "FIFTH sandbox rollback disclosure: this session's "
                "sandbox is fresh; nothing was lost (frontiers + "
                "anchor verified by the dry-run file checks), but "
                "restore aliveness on THIS machine is exactly what "
                "boot 1 validates.  GOAL: PAY500_GOAL=2 shared "
                "across the round (atomic counter), fresh-soft "
                "0x4054 preference, de-starve advance armed on BOTH "
                "passes, pay-frame telemetry verbatim.  m2_gate "
                "unchanged."),
            "hypothesis": (
                "the delay signature (+500 tail f1, +1000 tail f3/f4) "
                "plus the 19 candidate offsets separate the "
                "magnitudes once n>=2 +500 captures exist; the "
                "corrected gate makes fresh 0x4054 targets reachable "
                "at the frontiers (the capsule R67 hypothesis "
                "verbatim)"),
        })
    with open(LEDGER) as f:
        led = json.load(f)
    if int(led.get("count", 0)) + 1 > int(led.get("cap", 0)):
        raise SystemExit(
            f"BOOT CAP EXCEEDED (ledger cap {led.get('cap')}; "
            "the ledger is the disclosed authority; no entry "
            "consumed)")
    led["count"] = int(led.get("count", 0)) + 1
    led.setdefault("log", []).append(
        {"n": led["count"], "ts": time.strftime("%FT%TZ",
                                                time.gmtime()),
         "script": "r67t1_payframe_500hunt.py", "reason": reason})
    _write(LEDGER, led)
    log(f"boot ledger: count={led['count']}/{led['cap']} ({reason})")
    return led["count"]


def read_pay500():
    """The shared round counter (atomic with each verified capture)."""
    if not os.path.exists(COUNTER):
        return {"plus500_captured": 0, "events": []}
    with open(COUNTER) as f:
        return json.load(f)


def bump_pay500(out, tap, frontier):
    """Called ONLY when the causal chain verifies (offline check is the
    analysis's job; this in-runner check is the honest first pass: a
    +500 score_delta on a CONNECT tap whose sc_jumps contain exactly
    one +500 jump)."""
    sj = [j for j in tap.get("sc_jumps", []) if j["d"] == 500]
    if tap.get("score_delta") != 500 or len(sj) != 1:
        return False
    c = read_pay500()
    c["plus500_captured"] = int(c.get("plus500_captured", 0)) + 1
    c.setdefault("events", []).append(
        {"frontier": frontier, "tap": tap["tap"],
         "slot": tap["target"]["slot"],
         "st_pre": tap["target"]["st"],
         "pay_jump": sj[0], "captured_at":
             time.strftime("%FT%TZ", time.gmtime())})
    _write(COUNTER, c)
    log(f"PAY500 #{c['plus500_captured']} captured (tap {tap['tap']}, "
        f"slot{tap['target']['slot']})")
    return True


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


# the R66 patch point verbatim: R50T.fire_tap renders through png()
R50T.png = png
R47T.png = png
R47T.PNGDIR = PNGDIR
R47T.FRONTIER = FRONTIER


# ---- R67 amendment G: the gate aligned with the product contract ----
R67_CORPSE_ST = frozenset(combat.CORPSE_ST) | {0x5B0C}


def corridor_occupants_r67(cen, player_x, tgt_x):
    """corridor_occupants_r66 VERBATIM with ONE disclosed delta (the
    dry-run finding): a 0x5B0C row (the death-registration terminal)
    never blocks — it is a corpse by the committed PRODUCT adapter
    contract (adapter.py CORPSE_ST includes 0x5B0C; combat.CORPSE_ST
    does not).  Everything else identical: mortal ground rows only;
    corpses, x=0 rows, in-flight projectiles and the transparent
    0xab94 never block."""
    lo, hi = min(player_x, tgt_x), max(player_x, tgt_x)
    occ = []
    for e in cen:
        if e["slot"] and e["st"] in R67_CORPSE_ST:
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


def pick_target_r67(cen, used, player_x):
    """pick_target_r66 VERBATIM on the R67 gate: CONNECT targets
    prefer a FRESH soft state (0x4054) — the freshness-spread lead —
    then the farthest clear target; the transparent 0xab94 is never a
    connect target."""
    best = None
    for e in cen:
        if not e.get("targetable") or e["slot"] in used:
            continue
        if e.get("st") == R51T.INVUL_ST:
            continue
        occ = [o for o in corridor_occupants_r67(cen, player_x,
                                                 e["x_px"])
               if o["slot"] != e["slot"]]
        if occ:
            continue
        key = (0 if e["st"] == R48.SOFT_ST else 1,
               -abs(e["dx_px"]))
        if best is None or key < best[0]:
            best = (key, e)
    return best[1] if best else None


def run_pass(p, m, J, tag, frontier, round_state):
    out = {"frontier": frontier, "pass_tag": tag, "destarve": True,
           "taps": [], "census_at_restore": [], "re_restores": 0,
           "deaths_seen": 0, "connects": 0, "kills": 0, "pay500": 0,
           "gate_skips": 0, "gate_diags": [],
           "advance_frames_used": 0, "invul_dwell_frames": 0,
           "connected_slots": [], "kill_slots": [], "pay500_taps": []}
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
    R50T.control_move(p, m, J, out, 1)
    # ---- the gated tap loop -------------------------------------------
    used = set()
    kill_id = 0
    i = 1
    skips = 0
    while i < N_TAPS_CAP:
        if time.time() - T0 > WALL_TAPS_S:
            out["note"] = "wall_guard"
            break
        if round_state["plus500_captured"] >= PAY500_GOAL:
            out["note"] = "pay500_goal_met"
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
        # THE R67 INTENT: CONNECT taps only while the +500 goal is
        # open (the KILL fallback stays for unresolvable connects —
        # the verbatim R50T two-intent structure).
        intent = "CONNECT"
        tgt = pick_target_r67(cen, used, player_x)
        if tgt is None:
            tgt = pick_target_r67(cen, used, player_x)
            if tgt is not None:
                intent = "KILL"
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
            if out["advance_frames_used"] < ADVANCE_BUDGET_F:
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
            tap = R50T.fire_tap(p, m, J, out, i, "CONNECT", tgt, 1,
                                None)
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
            # THE R67 COUNTER (amendment A): any +500 counts, connect
            # or one-hit — the R66 capture was itself a one-bullet
            # kill; the magnitude is the payload, not the label.
            if tap["score_delta"] == 500 and \
                    bump_pay500(out, tap, frontier):
                out["pay500"] += 1
                out["pay500_taps"].append(
                    {"tap": i, "slot": tgt["slot"],
                     "st_pre": tgt["st"],
                     "kind": ("connect" if hit and not reg
                              else "one-hit"),
                     "pay_jump": [j for j in tap["sc_jumps"]
                                  if j["d"] == 500]})
                J({"ev": "PAY500_CAPTURED", "frontier": frontier,
                   "round_count":
                       round_state["plus500_captured"], **out["pay500_taps"][-1]})
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
                    if [o for o in corridor_occupants_r67(
                            cen2, t1.px_of(m), live["x_px"])
                            if o["slot"] != kslot]:
                        break           # the gate: never fire blind
                    approach(m, p, live)
                    tgt = live
                tap = R50T.fire_tap(p, m, J, out, i, "KILL", tgt, b,
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
                if tap["score_delta"] == 500 and \
                        bump_pay500(out, tap, frontier):
                    out["pay500"] += 1
                    out["pay500_taps"].append(
                        {"tap": i, "slot": kslot,
                         "st_pre": tap["target"]["st"]
                         if tap.get("target") else None,
                         "kind": "kill", "bullets": b,
                         "pay_jump": [j for j in tap["sc_jumps"]
                                      if j["d"] == 500]})
                    J({"ev": "PAY500_CAPTURED", "frontier": frontier,
                       "round_count":
                           round_state["plus500_captured"],
                       **out["pay500_taps"][-1]})
            else:
                used.add(kslot)
                J({"ev": "KILL_UNRESOLVED", "frontier": frontier,
                   "slot": kslot, "bullets": b})
    # ---- the second movement control (post-taps) ----------------------
    if not t1.alive(m):
        p.load_state(frontier)
        t1.wait_alive(m, p, wait=10)
    R50T.control_move(p, m, J, out, i)
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
       "pay500": out["pay500"], "gate_skips": out["gate_skips"],
       "advance_frames_used": out["advance_frames_used"],
       "round_pay500": round_state["plus500_captured"],
       "connect_survival_at_walk_end":
           out["connect_survival_at_walk_end"]})
    return out


def do_hunt(J, tag, stem, only):
    """only: 'a' -> frontier_a; 'b' -> frontier_b (each invocation is
    its own disclosed boot — the R66 a/b split precedent)."""
    order = []
    for fr in FRONTIER:
        if os.path.exists(os.path.join(STATES, fr + ".state")):
            order.append(fr)
        else:
            J({"ev": "FRONTIER_ABSENT", "frontier": fr})
    if not order:
        raise SystemExit("no r66_frontier_* states on disk — the "
                         "restore-only budget line does NOT hold; "
                         "the rebuild contingency is a DISCLOSED "
                         "boot outside this round's cap")
    if only == "a":
        order = order[:1]
    elif only == "b":
        order = order[1:]
    p = boot_to_demo()
    m = p.mem
    pas = []
    for fr in order:
        r = run_pass(p, m, J, tag, fr, read_pay500())
        pas.append(r)
        if (read_pay500()["plus500_captured"] >= PAY500_GOAL
                or r.get("note") in (
                    "dead on restore",
                    "frontier dead after restore")):
            break
    res = {"passes": pas, "final": t1.snap(m)}
    rep = {"schema": "ps1play.r67-500hunt/1", "stage": 2,
           "generated": time.strftime("%FT%TZ", time.gmtime()),
           "commit": os.popen("git -C %s rev-parse HEAD"
                              % _REPO).read().strip(),
           "goal": {"pay500_goal": PAY500_GOAL,
                    "round_captured":
                        read_pay500()["plus500_captured"]},
           "frontiers_on_disk": order,
           "amendments": {"goal_pay500_2": True,
                          "fresh_soft_preference": True,
                          "destarve_armed_both_passes": True,
                          "telemetry_verbatim_r66": True},
           "run": res}
    with open(os.path.join(EVID, f"{stem}_report.json"), "w") as f:
        json.dump(rep, f, indent=1, default=str)
    fin_line = [(r["frontier"], r["pay500"], r["connects"],
                 r["kills"], r["gate_skips"],
                 r["advance_frames_used"]) for r in pas]
    log(f"STAGE2 FIN passes={fin_line} "
        f"round_pay500={read_pay500()['plus500_captured']}")
    return 0


def main():
    global T0
    T0 = time.time()
    only = (sys.argv[1] if len(sys.argv) > 1 else "a").strip().lower()
    assert only in ("a", "b"), "usage: r67t1_payframe_500hunt.py [a|b]"
    reasons = {
        "a": "BOOT stage-2 pass A (the INSTRUMENTED +500 HUNT, "
             "restore-only): boot -> restore r66_frontier_a -> "
             "CONNECT taps preferring fresh 0x4054 on the corrected "
             "gate with the pay-frame telemetry verbatim -> stop at "
             "the round +500 goal (2) or the disclosed caps.  The "
             "a/b split is DISCLOSED: the tool window caps one "
             "process at ~10 min; each pass is its own disclosed "
             "boot (the R66 precedent).",
        "b": "BOOT stage-2 pass B (the INSTRUMENTED +500 HUNT, "
             "restore-only): boot -> restore r66_frontier_b -> the "
             "same amended protocol as pass A (fresh-soft "
             "preference, de-starve armed, pay-frame telemetry "
             "verbatim) -> stop at the round +500 goal (2) or the "
             "disclosed caps.",
    }
    n = amend_ledger(reasons[only])
    tag = time.strftime(f"r67_2{only}_%H%M%S")
    stem = f"r67_boot{n}_s2{only}"
    os.makedirs(SCRATCH, exist_ok=True)
    os.makedirs(EVID, exist_ok=True)
    tr_path = os.path.join(EVID, f"{stem}.jsonl")
    jf = open(tr_path, "w")

    def J(ev):
        jf.write(json.dumps(ev, default=str) + "\n")
        jf.flush()

    try:
        do_hunt(J, tag, stem, only)
    finally:
        jf.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
