#!/usr/bin/env python3
"""r47t1_singletap_taps.py — R47 (the 60% track, Issues #5/#9/#10).

The capsule lever (R46 close-out): the SINGLE-BULLET TAP PROTOCOL.
HYPOTHESIS (verbatim): the score system is PER-HIT, not per-kill — a
single-bullet tap (TAP_FRAMES ~3 = about one bullet per tap) from the
frontier postures yields score deltas of exactly +100 per bullet
CONNECT on a ground soldier (surviving hits included), reclassifying
the R45/R46 "one-hit" reading as PER-HIT SCORING (the two models
agree at the death tap and diverge on surviving hits); if instead
connects score 0 and only the death pays +100, the one-hit reading
stands; the +500/+1000 first-tap events become attributable
(multi-connect bursts).

The R46 lessons encoded (all four):
  1. FULL-kind census per tap — air included (the R46 ground-only
     filter discarded the attribution evidence).  A filter that
     shrinks the TARGET set must not shrink the RECORDING set.
  2. The burning-ground states (0xa264/0xa414) + the wreck (0xa44c)
     are excluded AS TARGETS (unkillable scenery) but still RECORDED.
  3. Class labels use the PRE-DEATH row (the st word is a state
     handler, not identity).
  4. Churn is not chip — the zero-input control tap (3f, the same
     timescale) is the baseline; the offline analysis subtracts it
     (r47_analysis_correct.py).  The runner only records.

PRE-RUN DISCLOSURE (the sandbox rollback, the R45 contingency
verbatim): the R45 frontiers (r45_frontier_a/b) are LOST to the
sandbox filesystem reset — their bytes were never committed (the
no-game-bytes rule).  The session-5 anchor issue5_m1_start (Oct 20)
SURVIVED on disk.  The capsule budget anticipated exactly this:
"a rebuild boot only if a frontier is lost, disclosed".

Boot plan (cap 2, DISCLOSED PRE-RUN — the R45 two-stage FOREGROUND
protocol):
  boot 1 = the tainted frontier REBUILD: restore issue5_m1_start ->
    the shipped policy in 15f chunks with continue-rescues (deaths
    allowed, counted, disclosed — TAINTED lineage, never a clean
    claim) -> EAGER rolling frontier saves past px 1200 (rolling
    r47_frontier_a/b, every >= 25 px gain, sane-clamped 0<=px<5000)
    -> early exit when both slots are saved and the latest px >= 1240.
  boot 2 = the R47 experiment, restore-only: restore r47_frontier_a
    -> FULL-kind census -> ONE zero-input control tap (3f) -> up to
    24 single-bullet taps (3f Y, nearest targetable ground enemy,
    soft-st preferred) with per-tap FULL-kind corpse/score/word
    tables -> restore r47_frontier_b if the census thins -> report.
  Restores are NOT boots (r35 precedent).

Oracle unchanged: walker words + verified score gains + alive
0x0EE518; never +0x8E in any oracle (the wide net 0x88..0xA8 is
DISCLOSED exploratory telemetry, not an oracle).
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
from issue4_controller import boot_to_demo        # noqa: E402
from run_mission1_legit import recover_v2         # noqa: E402

SCRATCH = os.path.join(_REPO, "scratch", "r47")
PNGDIR = os.path.join(SCRATCH, "pngs")
LEDGER = os.path.join(SCRATCH, "boots_used.json")
EVID = os.path.join(_REPO, "data", "games", "SLUS-01212",
                    "truck_evidence", "r47")
STATES = "/home/z/my-project/emu/ws/states"

ANCHOR = "issue5_m1_start"
FRONTIER = ("r47_frontier_a", "r47_frontier_b")

PUSH_CAP = 900             # 15f chunks for the rebuild push
WALL_PUSH_S = 330

WINDOW = (1150.0, 1450.0)  # the target window (the readout window)
FRONTIER_PX = 1200.0
FRONTIER_STEP = 25.0
EARLY_EXIT_PX = 1240.0

SOFT_ST = 0x4054
CORPSE_ST = combat.CORPSE_ST
# target exclusions: corpse (state), the truck wreck, the EVOLVED
# burning states + the landed-shell family (unkillable scenery)
TARGET_EXCLUDE_ST = (0xA44C, 0xA264, 0xA414)

TAPS = 24                  # single-bullet taps per frontier pass
TAP_FRAMES = 3             # ONE bullet per tap (the R47 protocol)
WIDE = tuple(range(0x88, 0xAA, 2))   # the disclosed wide net
RE_RESTORE_MAX = 2
WALL_TAPS_S = 480


def log(*a):
    print("[r47-t1]", *a, file=sys.stderr, flush=True)


def amend_ledger(reason):
    os.makedirs(SCRATCH, exist_ok=True)
    os.makedirs(EVID, exist_ok=True)
    if not os.path.exists(LEDGER):
        with open(LEDGER, "w") as f:
            json.dump({"cap": 2, "count": 0, "log": [], "note":
                       "R47 cap 2 DISCLOSED PRE-RUN (the R45 "
                       "two-stage FOREGROUND protocol).  SANDBOX "
                       "ROLLBACK DISCLOSURE: the R45 frontiers "
                       "(r45_frontier_a/b) are LOST to the sandbox "
                       "filesystem reset (never committed - "
                       "no-game-bytes); issue5_m1_start (Oct 20) "
                       "SURVIVED.  The capsule contingency applies "
                       "verbatim: a rebuild boot only if a frontier "
                       "is lost, disclosed.  boot1 = the tainted "
                       "frontier rebuild (continue-rescues counted, "
                       "never a clean claim); boot2 = the "
                       "single-bullet tap protocol, restore-only.  "
                       "Restores are NOT boots (r35 precedent).",
                       "hypothesis":
                       "the score system is PER-HIT, not per-kill: "
                       "single-bullet taps (3f Y) yield exactly "
                       "+100 per bullet CONNECT on a ground soldier "
                       "(surviving hits included); connects scoring "
                       "0 with only the death paying +100 keeps the "
                       "one-hit reading"},
                      f, indent=1)
    with open(LEDGER) as f:
        led = json.load(f)
    led["count"] = int(led.get("count", 0)) + 1
    led.setdefault("log", []).append(
        {"n": led["count"], "ts": time.strftime("%FT%TZ", time.gmtime()),
         "script": "r47t1_singletap_taps.py", "reason": reason})
    with open(LEDGER, "w") as f:
        json.dump(led, f, indent=1)
    log(f"boot ledger: count={led['count']}/{led['cap']} ({reason})")
    return led["count"]


def png(p, name, tag):
    try:
        rgb = p.core.frame_rgb()
        if rgb is not None:
            os.makedirs(PNGDIR, exist_ok=True)
            from PIL import Image
            Image.fromarray(rgb).save(
                os.path.join(PNGDIR, f"{tag}_{name}.png"))
            return f"{tag}_{name}.png"
    except Exception as e:                                  # noqa: BLE001
        log("png failed:", repr(e)[:120])
    return None


def read_words(m, slot):
    base = combat.TABLE + slot * combat.STRIDE
    return {hex(off): int(m.u16(base + off)) for off in WIDE}


def entity_state(m, slot):
    base = combat.TABLE + slot * combat.STRIDE
    xw = int(m.u32(base + 0x78))
    return {"slot": slot,
            "x": round(xw / 65536.0, 1) if xw else 0.0,
            "st": int(m.u16(base)),
            "f8e": int(m.u16(base + 0x8E)),
            "f9e": int(m.u16(base + 0x9E)),
            "a4": int(m.u16(base + 0xA4)),
            "h": int(m.u16(base + 0x7E))}


def census_full(m, px):
    """FULL-kind census (the R46 lesson: record ALL kinds, act on the
    filtered subset).  Returns every live entity slot the table scan
    sees, each with kind + geometry + state.  The TARGETABLE subset
    (ground enemy, in-window, corpse/wreck/burning excluded) is
    flagged and soft-st preferred, then nearest."""
    ents = combat.scan_entities(m, px=px)
    out = []
    for e in ents:
        targetable = (e.get("kind") == "enemy"
                      and WINDOW[0] <= e["x_px"] <= WINDOW[1]
                      and e["st"] not in TARGET_EXCLUDE_ST)
        out.append(dict(e, targetable=bool(targetable)))
    out.sort(key=lambda e: (not e["targetable"],
                            e["st"] != SOFT_ST, abs(e["dx_px"])))
    return out


def target_of(cen):
    for e in cen:
        if e["targetable"]:
            return e
    return None


def save_frontier(p, m, J, px, state):
    try:
        p.save_state(state)
        n = len(census_full(m, px))
        J({"ev": "FRONTIER_SAVED", "state": state, "px": px,
           "census_n": n})
        log(f"frontier saved px={px:.1f} -> {state} (census {n})")
        return True
    except Exception as e:                                  # noqa: BLE001
        J({"ev": "FRONTIER_SAVE_FAILED", "state": state,
           "err": repr(e)[:160]})
        return False


def push_phase(p, m, J, tag):
    """Stage 1: the tainted rebuild push (the R45 stage-1 verbatim
    structure: sensor order at BOTH chunk ends, sane clamp, wrap
    fast-forward, eager rolling frontier saves)."""
    pol = combat.CombatPolicy(queue_priority=True)
    p.core.run(2, set())
    J({"ev": "PUSH_START", "snap": t1.snap(m), "vm": t2.read_vm(m)})
    t0 = time.time()
    last_px, last_segs = None, None
    prev_score = int(m.u32(t1.A_SCORE))
    deaths, rescues = 0, 0
    max_px = -1.0
    saved = {"i": 0, "px": -1.0}
    outcome = "budget"
    for c in range(PUSH_CAP):
        if time.time() - t0 > WALL_PUSH_S:
            outcome = "wall_guard"
            break
        px0 = t1.px_of(m)
        sane0 = 0.0 <= px0 < 5000.0
        if sane0:
            max_px = max(max_px, px0)
        # SENSOR ORDER (chunk start): alive FIRST.
        if not t1.alive(m):
            deaths += 1
            J({"ev": "death", "chunk": c, "deaths": deaths,
               **t1.snap(m)})
            png(p, f"death_c{c}", tag)
            if not t1.wait_alive(m, p, wait=20):
                if not recover_v2(p, log=log) or \
                        not t1.wait_alive(m, p, wait=20):
                    outcome = "death_no_respawn"
                    break
            rescues += 1
            last_px, last_segs = None, None
            continue
        if px0 > 5000.0:
            p.core.run(60, set())          # the wrap/transition world
            continue
        if sane0 and px0 > FRONTIER_PX and \
                px0 > saved["px"] + FRONTIER_STEP:
            if save_frontier(p, m, J, px0, FRONTIER[saved["i"] % 2]):
                saved["i"] += 1
                saved["px"] = px0
                if saved["i"] >= 2 and px0 >= EARLY_EXIT_PX:
                    outcome = "frontiers_saved"
                    break
        px = t1.px_of(m)
        max_px = max(max_px, px)
        advanced = 0.0 if last_px is None else px - last_px
        intent = any("RIGHT" in (x.get("btns") or set())
                     for x in (last_segs or []))
        sec = combat.scan_section(m)
        pol.observe_section(sec, px_now=px)
        pol.observe(px, advanced, intent)
        scan = combat.scan_entities(m, px=px)
        gren0 = int(m.u8(t1.GRENADES))
        segs = pol.decide(15, px, scan, grenades=gren0,
                          hp=int(m.u16(t1.PLAYER_HP)))
        last_px, last_segs = px, segs
        print(f"[r47-trace] push c={c} px={px:.0f} mode={pol.mode}",
              file=sys.stderr, flush=True)
        for x in segs:
            p.core.run(x["frames"], x["btns"] or set())
            if not t1.alive(m):
                break
        s2 = t1.snap(m)
        sane2 = 0.0 <= s2["px"] < 5000.0
        if sane2:
            max_px = max(max_px, s2["px"])
        # SENSOR ORDER (chunk end): alive FIRST.
        if not t1.alive(m):
            J({"ev": "CHUNK_END_DEATH", "chunk": c,
               "deaths_at_start": deaths, "px_end": s2["px"], **s2})
            png(p, f"chunkend_death_c{c}", tag)
            continue
        elif sane2 and max_px > 700.0 and s2["px"] < 700.0:
            J({"ev": "RESTART_LEAK_DYNAMIC", "chunk": c,
               "max_px": round(max_px, 1), "px_end": s2["px"], **s2})
            log(f"restart leak c{c} (deaths kept, push continues)")
            last_px, last_segs = None, None
            continue
        if sane2 and s2["px"] > FRONTIER_PX and \
                s2["px"] > saved["px"] + FRONTIER_STEP:
            if save_frontier(p, m, J, s2["px"], FRONTIER[saved["i"] % 2]):
                saved["i"] += 1
                saved["px"] = s2["px"]
                if saved["i"] >= 2 and s2["px"] >= EARLY_EXIT_PX:
                    outcome = "frontiers_saved"
                    break
        if s2["score"] != prev_score:
            J({"ev": "SCORE_EVENT", "chunk": c, "from": prev_score,
               "to": s2["score"]})
            prev_score = s2["score"]
        if c % 40 == 0:
            J({"ev": "PUSH_DUMP", "chunk": c, "mode": pol.mode,
               "max_px": round(max_px, 1), "deaths": deaths,
               "rescues": rescues, "saved_i": saved["i"], **s2})
    fin = t1.snap(m)
    J({"ev": "PUSH_DONE", "outcome": outcome, "deaths": deaths,
       "rescues": rescues, "frontiers": saved["i"],
       "frontier_px": round(saved["px"], 1), **fin})
    log(f"push done: {outcome} deaths={deaths} rescues={rescues} "
        f"frontiers={saved['i']} px={saved['px']:.1f}")
    return {"outcome": outcome, "deaths": deaths, "rescues": rescues,
            "frontiers": saved["i"], "frontier_px": saved["px"]}


def full_snapshot(m):
    """The per-tap FULL-kind recording table (all slots, all kinds):
    entity states + the wide-net words.  Score/php are appended by
    the caller."""
    cen = census_full(m, t1.px_of(m))
    return cen, {str(e["slot"]): entity_state(m, e["slot"])
                 for e in cen}, \
           {str(e["slot"]): read_words(m, e["slot"]) for e in cen}


def union_post(m, post_e, post_w, pre_e):
    """The scan can DROP a slot between pre and post (a death inside
    the tap removes it from the table walk) - re-read those slots
    DIRECTLY from the entity table (unconditional table reads, the
    r45t1 entity_state semantics) so the per-tap delta table always
    covers every pre slot."""
    for s in pre_e:
        if s not in post_e:
            si = int(s)
            post_e[s] = entity_state(m, si)
            post_w[s] = read_words(m, si)
    return post_e, post_w


def corpse_transitions(pre_ents, post_ents):
    """Deaths = the slot's st becomes 0x4be4 with x==0 (the corrected
    rule); returns the slots that transitioned IN this tap."""
    out = []
    for s, pe in pre_ents.items():
        po = post_ents.get(s)
        if po is None:
            continue
        if not (pe["st"] in CORPSE_ST and pe["x"] == 0.0) \
                and po["st"] in CORPSE_ST and po["x"] == 0.0:
            out.append(s)
    return out


def run_pass(p, m, J, tag, frontier):
    """Stage 2 pass: restore-only single-bullet tap protocol from one
    frontier posture.  FULL-kind recording; single-bullet aiming."""
    out = {"frontier": frontier, "taps": [], "census_at_restore": [],
           "re_restores": 0, "deaths_seen": 0}
    hist = {}
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
    png(p, f"restore_{frontier}", tag)
    cen = census_full(m, s0["px"])
    out["census_at_restore"] = cen
    n_tgt = len([e for e in cen if e["targetable"]])
    J({"ev": "CENSUS_FULL", "frontier": frontier, "px": s0["px"],
       "window": WINDOW, "n_all": len(cen), "n_targetable": n_tgt,
       "entities": cen})
    log(f"census {frontier}: {len(cen)} live ({n_tgt} targetable)")
    # ---- the zero-input control tap (3f, the same timescale) -------
    cen, pre_e, pre_w = full_snapshot(m)
    pre_sc = int(m.u32(t1.A_SCORE))
    p.core.run(TAP_FRAMES, set())
    cen2, post_e, post_w = full_snapshot(m)
    post_e, post_w = union_post(m, post_e, post_w, pre_e)
    post_sc = int(m.u32(t1.A_SCORE))
    ctrl = {"tap": 0, "kind": "CONTROL_ZERO_INPUT",
            "score_delta": post_sc - pre_sc,
            "ents_pre": pre_e, "ents_post": post_e,
            "word_deltas": {s: {k: post_w[s][k] - pre_w[s][k]
                                for k in pre_w[s]} for s in pre_w},
            "corpses": corpse_transitions(pre_e, post_e)}
    out["taps"].append(ctrl)
    J({"ev": "TAP", **ctrl, "frontier": frontier})
    log(f"control tap: dscore={ctrl['score_delta']} "
        f"corpses={ctrl['corpses']}")
    # ---- the single-bullet taps ------------------------------------
    for i in range(1, TAPS + 1):
        if time.time() - T0 > WALL_TAPS_S:
            out["note"] = "wall_guard"
            break
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
            J({"ev": "RE_RESTORED", "frontier": frontier,
               "tap": i, **t1.snap(m)})
        cen = census_full(m, t1.px_of(m))
        tgt = target_of(cen)
        if tgt is None:
            J({"ev": "CENSUS_NO_TARGET", "frontier": frontier,
               "tap": i, "n_all": len(cen)})
            out["note"] = f"no_targetable_at_tap{i}"
            break
        # face the target (a brief hold; disclosed scripted input)
        if tgt["dx_px"] > 8.0:
            p.core.run(3, {"RIGHT"})
        elif tgt["dx_px"] < -8.0:
            p.core.run(3, {"LEFT"})
        cen, pre_e, pre_w = full_snapshot(m)
        pre_sc = int(m.u32(t1.A_SCORE))
        pre_php = int(m.u16(t1.PLAYER_HP))
        p.core.run(TAP_FRAMES, {"Y"})
        cen2, post_e, post_w = full_snapshot(m)
        post_e, post_w = union_post(m, post_e, post_w, pre_e)
        post_sc = int(m.u32(t1.A_SCORE))
        post_php = int(m.u16(t1.PLAYER_HP))
        gone = [s for s, po in post_e.items()
                if po["st"] in CORPSE_ST or po["f8e"] == 0]
        corpses = corpse_transitions(pre_e, post_e)
        wd = {s: {k: post_w[s][k] - pre_w[s][k] for k in pre_w[s]}
              for s in pre_w}
        dscore = post_sc - pre_sc
        tap = {"tap": i, "kind": "AIMED_Y_SINGLE",
               "target": tgt, "score_delta": dscore,
               "php": (pre_php, post_php),
               "ents_pre": pre_e, "ents_post": post_e,
               "word_deltas": wd, "slots_gone": gone,
               "corpses": corpses}
        out["taps"].append(tap)
        J({"ev": "TAP", **tap, "frontier": frontier})
        out["deaths_seen"] += len(corpses)
        for s in corpses:
            hist.setdefault(s, []).append(i)
        log(f"tap {i}: tgt slot{tgt['slot']} st{hex(tgt['st'])} "
            f"dx{tgt['dx_px']:+.0f} dscore={dscore} "
            f"corpses={corpses} gone={gone}")
        if corpses:
            png(p, f"kill_tap{i}", tag)
    fin = t1.snap(m)
    out["final"] = fin
    J({"ev": "PASS_DONE", "frontier": frontier, **fin})
    return out


def do_stage1(J, tag, stem):
    p = boot_to_demo()
    m = p.mem
    p.load_state(ANCHOR)
    if not t1.alive(m):
        raise SystemExit(f"anchor restore not alive: {t1.snap(m)}")
    J({"ev": "ANCHOR_RESTORED", "state": ANCHOR, **t1.snap(m)})
    log(f"anchor restored px={t1.px_of(m):.1f}")
    res = {"push": push_phase(p, m, J, tag)}
    res["final"] = t1.snap(m)
    rep = {"schema": "ps1play.r47-singletap/1", "stage": 1,
           "generated": time.strftime("%FT%TZ", time.gmtime()),
           "commit": os.popen("git -C %s rev-parse HEAD"
                              % _REPO).read().strip(),
           "anchor": ANCHOR, "run": res}
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
        raise SystemExit("no r47_frontier_* states on disk - run "
                         "stage 1 first (never fabricate a frontier)")
    p = boot_to_demo()
    m = p.mem
    pas = []
    for fr in order:
        r = run_pass(p, m, J, tag, fr)
        pas.append(r)
        # continue to the second frontier only if the first was
        # unproductive (census thinned / dead world)
        if r.get("note") not in ("no_targetable_at_tap1",
                                 "dead on restore",
                                 "frontier dead after restore") \
                and r["deaths_seen"] > 0:
            break
    res = {"passes": pas, "final": t1.snap(m)}
    rep = {"schema": "ps1play.r47-singletap/1", "stage": 2,
           "generated": time.strftime("%FT%TZ", time.gmtime()),
           "commit": os.popen("git -C %s rev-parse HEAD"
                              % _REPO).read().strip(),
           "anchor": ANCHOR, "run": res}
    with open(os.path.join(EVID, f"{stem}_report.json"), "w") as f:
        json.dump(rep, f, indent=1, default=str)
    log(f"STAGE2 FIN passes="
        f"{[(r['frontier'], len(r['taps'])) for r in pas]}")
    return 0


def main():
    global T0
    T0 = time.time()
    stage = (sys.argv[1] if len(sys.argv) > 1 else "1").strip()
    assert stage in ("1", "2"), "usage: r47t1_singletap_taps.py [1|2]"
    reasons = {
        "1": "BOOT stage-1 (the frontier REBUILD; DISCLOSED: the R45 "
             "frontiers r45_frontier_a/b are LOST to the sandbox "
             "filesystem reset - the capsule contingency, the R45 "
             "precedent verbatim; the rebuilt lineage is TAINTED, "
             "continue-rescues counted, never a clean claim): boot -> "
             "restore issue5_m1_start (survived) -> tainted push "
             "(deaths counted, eager frontier saves r47_frontier_a/b "
             "px>1200 every >=25px sane-clamped, early exit both "
             "saved & latest >=1240) -> exit",
        "2": "BOOT stage-2 (the SINGLE-BULLET TAP PROTOCOL, "
             "restore-only): boot -> restore r47_frontier_a -> "
             "FULL-kind census (air included; burning 0xa264/0xa414 "
             "+ wreck 0xa44c excluded AS TARGETS, RECORDED) -> "
             "zero-input control tap (3f) -> single-bullet taps "
             "(3f Y, nearest targetable ground enemy, soft-st "
             "preferred) with per-tap corpse/score/word tables -> "
             "restore r47_frontier_b if the census thins -> report",
    }
    n = amend_ledger(reasons[stage])
    if n > 3:
        raise SystemExit("BOOT CAP EXCEEDED (3 - incl. the disclosed 2->3 crash amendment)")
    tag = time.strftime(f"r47_{stage}_%H%M%S")
    stem = f"r47_boot{n}_s{stage}"
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
           "r45_frontier_a/b LOST to the sandbox filesystem reset "
           "(never committed - no-game-bytes); issue5_m1_start "
           "survived (Oct 20); the capsule contingency (a rebuild "
           "boot, disclosed) applies verbatim (the R45 precedent)",
       "lineage": ("TAINTED (continue-rescues; never a clean claim)"
                   if stage == "1" else
                   "TAINTED frontier postures (restore-only taps)"),
       "oracle": "walker words + verified score gains + alive "
                 "0x0EE518; never +0x8E (the wide net = disclosed "
                 "exploratory telemetry)",
       "protocol": "TAP_FRAMES=3 single-bullet taps; FULL-kind "
                   "census per tap (the R46 lessons 1-4 encoded)",
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
