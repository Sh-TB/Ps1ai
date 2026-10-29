#!/usr/bin/env python3
"""r52t1_payframe_wound.py — R52 (the 60% track, #5/#9/#10).

The capsule lever (R51 close-out), executed verbatim: the FRAME-EXACT
PAY-FRAME UNION-NET WOUND HUNT.  The R51 open measurement: the
connect magnitude is UNSETTLED (+500 x3 vs +1000 x5 across R48-R51,
all mid-wound-recovery of SURVIVING targets, pre-states 0x42bc /
0x2b74 / 0x3f48 / 0x42bc, no discriminator) and the tap-WINDOW word
hunt is NEGATIVE (the union net 0x60..0xE0 churn fills the window).
The R51 capsule named the lever: the discriminator must be read AT
THE PAY FRAME.

HYPOTHESIS (verbatim, the capsule R52): a word (or a state function
of words) exists whose PAY-FRAME value separates the +500 connects
from the +1000 connects with ZERO overlap (the magnitude model
refines to payment = f(wound_state)); the wound-accumulator word, if
it exists, shows a decrement-then-recovery shape co-timed with the
connect inside the union net 0x60..0xE0.

Method (the capsule): boot -> the pay-frame union-net reads (u16
0x60..0xE0, slots 1..39 — live slots per frame) across EVERY
tap+flight window on dedicated CONNECT targets (no follow-up) +
KILL contrast taps + the PIERCE replication + the movement-inclusive
controls (verbatim) -> the r52 offline analysis evaluates the
discriminator on the pay-frame word state.

PRE-RUN DISCLOSURE (the THIRD sandbox rollback, the R45/R47
contingency verbatim): the scratch/ workspace was reset by the
sandbox — the r47_frontier_a/b states and the r47b gs1 checkpoint
are LOST (never committed — no-game-bytes).  The session-5 anchor
issue5_m1_start (Oct 20) SURVIVED on disk (verified pre-run).  The
capsule contingency applies verbatim: a rebuild boot only if a
frontier is lost, disclosed.

Boot plan (cap 2, DISCLOSED PRE-RUN — the R47 two-stage FOREGROUND
protocol):
  boot 1 = the tainted frontier REBUILD: restore issue5_m1_start ->
    the shipped policy in 15f chunks with continue-rescues (deaths
    allowed, counted, disclosed — TAINTED lineage, never a clean
    claim) -> EAGER rolling frontier saves past px 1200 (rolling
    r52_frontier_a/b, every >= 25 px gain, sane-clamped 0<=px<5000)
    -> early exit when both slots are saved and the latest px >= 1240.
  boot 2 = the R52 experiment, restore-only: the R51 protocol
    verbatim (CONNECT x4 no-follow-up, KILL x2, PIERCE x1, the
    zero-input + movement-only controls, the invulnerability census,
    the corridor gate: UP-TO for mortal targets, +60px BEYOND for
    the TRANSPARENT target only) with the word telemetry ELEVATED to
    pay-frame granularity (the disclosed patch point: R50T.frame_walk
    -> frame_walk_hunt records the union-net u16 states for every
    live slot EVERY frame of the tap+flight window).
  Restores are NOT boots (r35 precedent).

Oracle unchanged: walker words + verified score gains + alive
0x0EE518; never +0x8E in any oracle (the union net = disclosed
exploratory telemetry, the R45/R47/R48/R49/R50/R51 precedent).

Wall guards DISCLOSED PRE-RUN: PUSH_CAP 900 / WALL_PUSH_S 330
(the R47 verbatim); N_TAPS_CAP 30, WALL_TAPS_S 420 (the tool-window
fit refinement, disclosed; the GOALS are the binding constraints —
the R51 goals CONNECT 3/KILL 2/PIERCE 1 widen to CONNECT 4 to give
the in-round magnitude pool both classes).
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
import r47t1_singletap_taps as R47T               # noqa: E402
import r51t1_wound_hunt as R51T                   # noqa: E402
import r50t1_controlled_corridor as R50T          # noqa: E402
import r48t1_frame_exact_taps as R48              # noqa: E402
from r51t1_wound_hunt import (                    # noqa: E402
    invulnerable, corridor_occupants, corridor_occupants_ext,
    invul_census, approach, pick_target)
from r48t1_frame_exact_taps import (              # noqa: E402
    census_full, direct_table, full_snapshot, union_post,
    corpse_transitions, mini_census, TAP_FRAMES, TAIL_FRAMES, STATES,
    RE_RESTORE_MAX)
from issue4_controller import boot_to_demo        # noqa: E402
from run_mission1_legit import recover_v2         # noqa: E402

SCRATCH = os.path.join(_REPO, "scratch", "r52")
PNGDIR = os.path.join(SCRATCH, "pngs")
LEDGER = os.path.join(SCRATCH, "boots_used.json")
EVID = os.path.join(_REPO, "data", "games", "SLUS-01212",
                    "truck_evidence", "r52")

ANCHOR = "issue5_m1_start"
FRONTIER = ("r52_frontier_a", "r52_frontier_b")

# goals (DISCLOSED PRE-RUN; the R51 verbatim structure, CONNECT
# widened 3->4 for the in-round magnitude pool)
CONNECT_GOAL = 4
KILL_GOAL = 2
PIERCE_GOAL = 1
N_TAPS_CAP = 30
SKIP_RETRIES_MAX = 10
WALL_TAPS_S = 420

T0 = time.time()


def log(*a):
    print("[r52-t1]", *a, file=sys.stderr, flush=True)


# ------------------------------------------------------------------
# THE R52 LEVER: pay-frame union-net telemetry.
# frame_walk_hunt REPLACES R50T.frame_walk (the disclosed patch
# point): every frame of the tap+flight window records the union-net
# u16 states (0x60..0xE0, even offsets) for every LIVE slot — the
# discriminator reads the word state AT the pay frame.
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


R50T.frame_walk = frame_walk_hunt     # the DISCLOSED patch point
# the R51 union-net read patch is already applied by the import
# (r51t1 patched R48.read_words -> the union net at import time).


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
                       "R52 cap 2 DISCLOSED PRE-RUN (the R47 "
                       "two-stage FOREGROUND protocol).  THIRD "
                       "SANDBOX ROLLBACK DISCLOSURE: scratch/ was "
                       "reset by the sandbox — the r47_frontier_a/b "
                       "states and the r47b gs1 checkpoint are LOST "
                       "(never committed - no-game-bytes); "
                       "issue5_m1_start (Oct 20) SURVIVED (verified "
                       "pre-run).  The capsule contingency applies "
                       "verbatim: a rebuild boot only if a frontier "
                       "is lost, disclosed.  boot1 = the tainted "
                       "frontier rebuild (r47 stage-1 verbatim, "
                       "r52_frontier_a/b names); boot2 = the R52 "
                       "pay-frame union-net wound hunt, "
                       "restore-only.  Lineage TAINTED (never a "
                       "clean claim).  THE R52 LEVER DISCLOSED: "
                       "R50T.frame_walk patched to frame_walk_hunt "
                       "(per-frame union-net u16 states for live "
                       "slots across the tap+flight window); the "
                       "R51 union-net R48.read_words patch applies "
                       "verbatim via the import.  Goals CONNECT=4 "
                       "KILL=2 PIERCE=1 (CONNECT widened for the "
                       "in-round magnitude pool); m2_gate unchanged.",
                       "hypothesis":
                       "a word (or state function of words) exists "
                       "whose PAY-FRAME value separates the +500 "
                       "connects from the +1000 connects with ZERO "
                       "overlap (payment = f(wound_state)); the "
                       "wound accumulator, if it exists, shows a "
                       "decrement-then-recovery shape co-timed with "
                       "the connect inside the union net"},
                      f, indent=1)
    with open(LEDGER) as f:
        led = json.load(f)
    # the cap gate BEFORE the increment (the phantom-entry fix: the
    # two cap-check crashes incremented count with NO core load -
    # refunded disclosed; now an over-cap call cannot consume a
    # ledger entry at all)
    if int(led.get("count", 0)) + 1 > int(led.get("cap", 0)):
        raise SystemExit(
            f"BOOT CAP EXCEEDED (ledger cap {led.get('cap')}; "
            "the ledger is the disclosed authority; no entry "
            "consumed)")
    led["count"] = int(led.get("count", 0)) + 1
    led.setdefault("log", []).append(
        {"n": led["count"], "ts": time.strftime("%FT%TZ", time.gmtime()),
         "script": "r52t1_payframe_wound.py", "reason": reason})
    with open(LEDGER, "w") as f:
        json.dump(led, f, indent=1)
    log(f"boot ledger: count={led['count']}/{led['cap']} ({reason})")
    return led["count"]


# ------------------------------------------------------------------
# stage 2: the R51 pass structure verbatim, on the pay-frame
# telemetry (the taps now carry per-frame union-net states).
# ------------------------------------------------------------------
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
       "vm": __import__("r41t2_nodes_live", fromlist=["read_vm"])
       .read_vm(m)})
    cen = census_full(m, s0["px"])
    out["census_at_restore"] = cen
    out["invul_at_restore"] = invul_census(cen)
    J({"ev": "CENSUS_FULL", "frontier": frontier, "px": s0["px"],
       "n_all": len(cen),
       "n_targetable": len([e for e in cen if e["targetable"]]),
       "invul": out["invul_at_restore"], "entities": cen})
    log(f"census {frontier}: {len(cen)} live, "
        f"invul={len(out['invul_at_restore'])}")
    # ---- the zero-input control walk (the R48-R51 baseline) ---------
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
                        "word_deltas": {s: {k: post_w[s][k] - pre_w[s][k]
                                            for k in pre_w[s]}
                                        for s in pre_w},
                        "corpses": corpse_transitions(pre_e, post_e)})
    J({"ev": "TAP", **out["taps"][0], "frontier": frontier})
    # ---- the movement-only control (verbatim) -------------------------
    R50T.control_move(p, m, J, out, 1)
    # ---- the gated tap loop (the R51 verbatim structure) --------------
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
        want_pierce = (not want_connect
                       and out["pierces"] < PIERCE_GOAL)
        intent = ("CONNECT" if want_connect
                  else "PIERCE" if want_pierce else "KILL")
        tgt = pick_target(cen, used, player_x, intent)
        if tgt is None:
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
            else:
                J({"ev": "CONNECT_MISS", "frontier": frontier,
                   "tap": i, "slot": tgt["slot"]})
        elif intent == "PIERCE":
            behind = [o for o in corridor_occupants_ext(
                cen, player_x, tgt["x_px"]) if o["slot"] != tgt["slot"]]
            tap = R50T.fire_tap(p, m, J, out, i, "PIERCE", tgt, 1,
                                None)
            used.add(tgt["slot"])
            ev = {"tap": i, "transparent_slot": tgt["slot"],
                  "transparent_st": tgt["st"],
                  "behind": behind,
                  "dscore": tap["score_delta"],
                  "corpses": tap["corpses"],
                  "transparent_reacted": any(
                      tr["to"] == R51T.CONNECT_ST
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
                    if [o for o in corridor_occupants(
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
    R50T.control_move(p, m, J, out, i)
    # ---- walk-end survival of the connected slots ---------------------
    dt = R48.direct_table(m)
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


def do_stage1(J, tag, stem):
    """boot 1: the tainted frontier rebuild (the R47 stage-1
    verbatim, r52_frontier_a/b names via the disclosed patch)."""
    p = boot_to_demo()
    m = p.mem
    p.load_state(ANCHOR)
    if not t1.alive(m):
        raise SystemExit(f"anchor restore not alive: {t1.snap(m)}")
    J({"ev": "ANCHOR_RESTORED", "state": ANCHOR, **t1.snap(m)})
    log(f"anchor restored px={t1.px_of(m):.1f}")
    res = {"push": R47T.push_phase(p, m, J, tag)}
    res["final"] = t1.snap(m)
    rep = {"schema": "ps1play.r52-payframe/1", "stage": 1,
           "generated": time.strftime("%FT%TZ", time.gmtime()),
           "commit": os.popen("git -C %s rev-parse HEAD"
                              % _REPO).read().strip(),
           "anchor": ANCHOR, "frontiers": FRONTIER, "run": res}
    with open(os.path.join(EVID, f"{stem}_report.json"), "w") as f:
        json.dump(rep, f, indent=1, default=str)
    log(f"STAGE1 FIN push={res['push']['outcome']} "
        f"frontiers={res['push']['frontiers']} "
        f"px={res['push']['frontier_px']:.1f}")
    return 0


def do_stage2(J, tag, stem):
    order = []
    for fr in FRONTIER:
        if os.path.exists(os.path.join(STATES, fr + ".state")):
            order.append(fr)
        else:
            J({"ev": "FRONTIER_ABSENT", "frontier": fr})
    if not order:
        raise SystemExit("no r52_frontier_* states on disk - run "
                         "stage 1 first (never fabricate a frontier)")
    p = boot_to_demo()
    m = p.mem
    pas = []
    for fr in order:
        r = run_pass(p, m, J, tag, fr)
        pas.append(r)
        done = (r["connects"] >= CONNECT_GOAL
                and r["kills"] >= KILL_GOAL
                and r["pierces"] >= PIERCE_GOAL)
        if done or r.get("note") in (
                "dead on restore", "frontier dead after restore"):
            break
    res = {"passes": pas, "final": t1.snap(m)}
    rep = {"schema": "ps1play.r52-payframe/1", "stage": 2,
           "generated": time.strftime("%FT%TZ", time.gmtime()),
           "commit": os.popen("git -C %s rev-parse HEAD"
                              % _REPO).read().strip(),
           "anchor": ANCHOR, "frontiers_on_disk": order,
           "union_net": [hex(o) for o in UNION_NET],
           "run": res}
    with open(os.path.join(EVID, f"{stem}_report.json"), "w") as f:
        json.dump(rep, f, indent=1, default=str)
    fin_line = [(r["frontier"], r["connects"], r["kills"],
                 r["pierces"], r["gate_skips"]) for r in pas]
    log(f"STAGE2 FIN passes={fin_line}")
    return 0


def main():
    global T0
    T0 = time.time()
    stage = (sys.argv[1] if len(sys.argv) > 1 else "1").strip()
    assert stage in ("1", "2"), \
        "usage: r52t1_payframe_wound.py [1|2]"
    reasons = {
        "1": "BOOT stage-1 (the tainted frontier REBUILD; DISCLOSED: "
             "the THIRD sandbox rollback lost the r47_frontier_a/b "
             "states (never committed - no-game-bytes); issue5_m1_"
             "start SURVIVED, verified pre-run; the capsule "
             "contingency verbatim, the R45/R47 precedent): boot -> "
             "restore issue5_m1_start -> tainted push (deaths "
             "counted, continue-rescues counted, eager frontier "
             "saves r52_frontier_a/b px>1200 every >=25px "
             "sane-clamped, early exit both saved & latest >=1240) "
             "-> exit",
        "2": "BOOT stage-2 (the PAY-FRAME UNION-NET WOUND HUNT, "
             "restore-only): boot -> restore r52_frontier_a -> the "
             "R51 protocol verbatim (CONNECT x4 no-follow-up, KILL "
             "x2, PIERCE x1, the zero-input + movement-only "
             "controls, the invulnerability census, the corridor "
             "gate: UP-TO mortal / +60px BEYOND transparent) with "
             "the word telemetry ELEVATED to pay-frame granularity "
             "(frame_walk_hunt: per-frame union-net u16 states for "
             "every live slot) -> restore r52_frontier_b if the "
             "goals are unmet -> report",
    }
    n = amend_ledger(reasons[stage])
    tag = time.strftime(f"r52_{stage}_%H%M%S")
    stem = f"r52_boot{n}_s{stage}"
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
           "THIRD sandbox rollback: scratch/ reset — the "
           "r47_frontier_a/b states + the r47b gs1 checkpoint LOST "
           "(never committed - no-game-bytes); issue5_m1_start "
           "survived (Oct 20, verified pre-run); the capsule "
           "contingency (a rebuild boot, disclosed) applies "
           "verbatim (the R45/R47 precedent)",
       "lineage": ("TAINTED (continue-rescues; never a clean claim)"
                   if stage == "1" else
                   "TAINTED frontier postures (restore-only taps)"),
       "oracle": "walker words + verified score gains + alive "
                 "0x0EE518; never +0x8E (the union net = disclosed "
                 "exploratory telemetry)",
       "protocol": "TAP_FRAMES=3 + TAIL_FRAMES=20; frame_walk_hunt "
                   "records the union-net u16 states for every live "
                   "slot EVERY frame (the pay-frame lever); "
                   f"CONNECT_GOAL={CONNECT_GOAL} KILL_GOAL={KILL_GOAL} "
                   f"PIERCE_GOAL={PIERCE_GOAL}",
       "ts": time.strftime("%FT%TZ", time.gmtime())})
    try:
        if stage == "1":
            rc = do_stage1(J, tag, stem)
        else:
            rc = do_stage2(J, tag, stem)
    finally:
        jf.close()
    log(f"report -> {EVID}/{stem}_report.json "
        f"(wall {time.time() - T0:.0f}s)")
    return rc


if __name__ == "__main__":
    sys.exit(main())
