#!/usr/bin/env python3
"""r48t1_frame_exact_taps.py — R48 (the 60% track, Issues #5/#9/#10).

The capsule lever (R47 close-out), executed verbatim: PER-FRAME SCORE
TELEMETRY COMPOSED with the single-bullet tap protocol.  The R47
corrected verdict (PER-KILL, kill-locked: +600 = 6 corpses x +100
while ALL 12 per-tap window deltas read 0 — the 3f tap ends before
the bullet arrives, flight ~8-15f) leaves one unfalsifiable corner:
the per-hit alternative survives only in the "connect pays later,
kill pays nothing extra" reading.  This round closes it FRAME-EXACTLY.

HYPOTHESIS (verbatim, the capsule): per-event score attribution is
DECIDED by composing the r46b per-frame score telemetry with the
single-bullet tap protocol: the exact frame of each +100 event lands
at (a) the bullet-impact frame on a corpse-to-be (per-KILL, locked to
the death moment) or (b) a connect frame with the target surviving
(per-HIT); the identity of each paying entity (the x~1275 cluster:
falling-shell mid-air shoots vs ground soldiers) is read off the
same frames.

Method (the capsule): boot -> restore r47_frontier_a -> per-frame
score reads around each single-bullet tap (TAP_FRAMES 3, then a 20f
readout tail covering the flight window; FULL-kind census per read)
-> the frame-exact event table decides (a) vs (b) per event ->
restore r47_frontier_b if the census thins; the burning-ground states
stay excluded AS TARGETS, RECORDED.

PRE-RUN DISCLOSURE: NO sandbox rollback this round — the R47
frontiers (r47_frontier_a/b) SURVIVED on disk (verified pre-boot in
main()); the session-5 anchor issue5_m1_start (Oct 20) also intact.
Boot plan (cap 1, DISCLOSED PRE-RUN): boot = the core+rom load ONLY;
both frontier passes are restore-only (restores are NOT boots, r35
precedent).  TAINTED lineage carried: the frontier postures were
built with continue-rescues (R45/R47); nothing here is a clean claim.

The R46/R47 lessons encoded (verbatim):  FULL-kind census per read
(a filter that shrinks the TARGET set must not shrink the RECORDING
set); burning 0xa264/0xa414 + wreck 0xa44c excluded AS TARGETS,
RECORDED; class labels use the PRE-DEATH row; churn is not chip (the
zero-input control tap at the SAME timescale is the baseline — the
per-frame telemetry makes the baseline frame-exact too).

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

SCRATCH = os.path.join(_REPO, "scratch", "r48")
LEDGER = os.path.join(SCRATCH, "boots_used.json")
EVID = os.path.join(_REPO, "data", "games", "SLUS-01212",
                    "truck_evidence", "r48")
STATES = "/home/z/my-project/emu/ws/states"

FRONTIER = ("r47_frontier_a", "r47_frontier_b")

WINDOW = (1150.0, 1450.0)

SOFT_ST = 0x4054
CORPSE_ST = combat.CORPSE_ST
TARGET_EXCLUDE_ST = (0xA44C, 0xA264, 0xA414)

TAPS = 24                  # single-bullet taps per frontier pass
TAP_FRAMES = 3             # ONE bullet per tap (the R47 protocol)
TAIL_FRAMES = 20           # the flight-window readout tail (the R48 lever)
RE_RESTORE_MAX = 2
WALL_TAPS_S = 560

SLOT_CAP = combat.SLOTS    # 40: DIRECT per-frame table reads (the
                           # scan_entities corpse-blindness fix: the
                           # scan SKIPS corpse st + hp==0 slots, so
                           # the census can never date a death)

WIDE = tuple(range(0x88, 0xAA, 2))   # the disclosed wide net
T0 = time.time()


def log(*a):
    print("[r48-t1]", *a, file=sys.stderr, flush=True)


def amend_ledger(reason):
    os.makedirs(SCRATCH, exist_ok=True)
    os.makedirs(EVID, exist_ok=True)
    if not os.path.exists(LEDGER):
        with open(LEDGER, "w") as f:
            json.dump({"cap": 1, "count": 0, "log": [], "note":
                       "R48 ledger: cap 1 DISCLOSED PRE-RUN = the "
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
                       "the +100 event frame lands (a) on the "
                       "bullet-impact frame of a corpse-to-be "
                       "(per-KILL) or (b) on a connect frame with "
                       "the target surviving (per-HIT); the paying "
                       "entity identity (x~1275 cluster) is read "
                       "off the same frames"},
                      f, indent=1)
    with open(LEDGER) as f:
        led = json.load(f)
    led["count"] = int(led.get("count", 0)) + 1
    led.setdefault("log", []).append(
        {"n": led["count"], "ts": time.strftime("%FT%TZ", time.gmtime()),
         "script": "r48t1_frame_exact_taps.py", "reason": reason})
    with open(LEDGER, "w") as f:
        json.dump(led, f, indent=1)
    log(f"boot ledger: count={led['count']}/{led['cap']} ({reason})")
    return led["count"]


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
    """FULL-kind census (the R46 lesson verbatim): record ALL kinds,
    act on the filtered subset."""
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


def mini_census(m, px):
    """The per-frame compact table: slot/st/x/kind only (fast enough
    for every frame of the tap+tail window)."""
    rows = []
    for e in combat.scan_entities(m, px=px):
        rows.append({"slot": e["slot"], "st": e["st"],
                     "x": round(e["x_px"], 1), "kind": e.get("kind")})
    return rows


def direct_table(m):
    """The corpse-blindness fix (boot-2, the disclosed cap amendment):
    per-frame DIRECT table reads for slots 1..SLOT_CAP-1 regardless of
    scan filters — st (state handler), x (world px), sx (the +0x8E
    screen-x), h (height), a4.  A slot DROPPED by scan_entities still
    appears here, so every death dates to its exact frame."""
    rows = []
    for s in range(1, SLOT_CAP):
        base = combat.TABLE + s * combat.STRIDE
        st = int(m.u16(base))
        xw = int(m.u32(base + 0x78))
        sx = int(m.u16(base + 0x8E))
        h = int(m.u16(base + 0x7E))
        a4 = int(m.u16(base + 0xA4))
        if st == 0 and xw == 0 and sx == 0:
            continue
        rows.append({"slot": s, "st": st,
                     "x": round(xw / 65536.0, 1) if xw else 0.0,
                     "sx": sx, "h": h, "a4": a4})
    return rows


def full_snapshot(m):
    cen = census_full(m, t1.px_of(m))
    return cen, {str(e["slot"]): entity_state(m, e["slot"])
                 for e in cen}, \
           {str(e["slot"]): read_words(m, e["slot"]) for e in cen}


def union_post(m, post_e, post_w, pre_e):
    for s in pre_e:
        if s not in post_e:
            si = int(s)
            post_e[s] = entity_state(m, si)
            post_w[s] = read_words(m, si)
    return post_e, post_w


def corpse_transitions(pre_ents, post_ents):
    out = []
    for s, pe in pre_ents.items():
        po = post_ents.get(s)
        if po is None:
            continue
        if not (pe["st"] in CORPSE_ST and pe["x"] == 0.0) \
                and po["st"] in CORPSE_ST and po["x"] == 0.0:
            out.append(s)
    return out


def frame_walk(p, m, J, tap, phase, n_frames, btns):
    """The frame-exact telemetry core: per-frame score + mini census
    + DIRECT table reads for n_frames under a fixed button set.
    Returns the frame rows."""
    rows = []
    for k in range(n_frames):
        p.core.run(1, btns)
        sc = int(m.u32(t1.A_SCORE))
        px = t1.px_of(m)
        rows.append({"f_rel": k + 1, "sc": sc, "px": round(px, 1),
                     "ents": mini_census(m, px),
                     "direct": direct_table(m)})
    J({"ev": "FRAME_WALK", "tap": tap, "phase": phase,
       "n": n_frames, "rows": rows})
    return rows


def run_pass(p, m, J, tag, frontier):
    """Restore-only frame-exact tap protocol from one frontier."""
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
    cen = census_full(m, s0["px"])
    out["census_at_restore"] = cen
    n_tgt = len([e for e in cen if e["targetable"]])
    J({"ev": "CENSUS_FULL", "frontier": frontier, "px": s0["px"],
       "n_all": len(cen), "n_targetable": n_tgt, "entities": cen})
    log(f"census {frontier}: {len(cen)} live ({n_tgt} targetable)")
    # ---- the zero-input control walk (3f + 20f tail, same protocol) --
    cen, pre_e, pre_w = full_snapshot(m)
    pre_sc = int(m.u32(t1.A_SCORE))
    ctrl_rows = frame_walk(p, m, J, 0, "CONTROL_ZERO_INPUT",
                           TAP_FRAMES + TAIL_FRAMES, set())
    cen2, post_e, post_w = full_snapshot(m)
    post_e, post_w = union_post(m, post_e, post_w, pre_e)
    post_sc = int(m.u32(t1.A_SCORE))
    ctrl = {"tap": 0, "kind": "CONTROL_ZERO_INPUT",
            "score_delta": post_sc - pre_sc,
            "sc_start": pre_sc, "sc_end": post_sc,
            "frame_rows": ctrl_rows,
            "ents_pre": pre_e, "ents_post": post_e,
            "word_deltas": {s: {k: post_w[s][k] - pre_w[s][k]
                                for k in pre_w[s]} for s in pre_w},
            "corpses": corpse_transitions(pre_e, post_e)}
    out["taps"].append(ctrl)
    J({"ev": "TAP", **ctrl, "frontier": frontier})
    log(f"control walk: dscore={ctrl['score_delta']} "
        f"corpses={ctrl['corpses']}")
    # ---- the single-bullet taps (3f Y + 20f tail) --------------------
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
        if tgt["dx_px"] > 8.0:
            p.core.run(3, {"RIGHT"})
        elif tgt["dx_px"] < -8.0:
            p.core.run(3, {"LEFT"})
        cen, pre_e, pre_w = full_snapshot(m)
        pre_sc = int(m.u32(t1.A_SCORE))
        pre_php = int(m.u16(t1.PLAYER_HP))
        tap_rows = frame_walk(p, m, J, i, "AIMED_Y_SINGLE",
                              TAP_FRAMES, {"Y"})
        tail_rows = frame_walk(p, m, J, i, "FLIGHT_TAIL",
                               TAIL_FRAMES, set())
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
               "sc_start": pre_sc, "sc_end": post_sc,
               "php": (pre_php, post_php),
               "frame_rows": tap_rows + tail_rows,
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
    out["corpse_hist"] = hist
    J({"ev": "PASS_DONE", "frontier": frontier, **fin})
    return out


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


def main():
    # ---- pre-boot on-disk frontier verification (the disclosure) ----
    have = [fr for fr in FRONTIER
            if os.path.exists(os.path.join(STATES, fr + ".state"))]
    if not have:
        raise SystemExit("no r47_frontier_* states on disk - the "
                         "capsule contingency (a rebuild boot) would "
                         "need a fresh disclosed cap; never fabricate")
    log("frontiers on disk (NO rollback this round):", have)
    reasons = ("BOOT (core+rom load ONLY): restore r47_frontier_a "
               "-> frame-exact tap protocol (control walk 3f+20f "
               "tail; taps 3f Y + 20f flight tail; per-frame score "
               "+ FULL-kind mini census + DIRECT per-frame table "
               "reads slots 1..39) -> restore r47_frontier_b if the "
               "census thins -> report.")
    led = json.load(open(LEDGER))
    led["cap"] = 2
    led.setdefault("log", []).append(
        {"n": 0, "ts": time.strftime("%FT%TZ", time.gmtime()),
         "script": "r48t1_frame_exact_taps.py",
         "cap_amendment":
             "cap 1->2 DISCLOSED (the r47 boot-2 defect precedent): "
             "boot 1 completed its WORLD data cleanly but the "
             "RECORDING was corpse-blind - mini_census is built on "
             "scan_entities which SKIPS corpse-st and hp==0 slots "
             "(the union_post lesson), so no corpse transition was "
             "ever dated at frame granularity and the per-event "
             "(a)-vs-(b) decision degraded to target-survival "
             "inference.  boot 2 = the same restore-only protocol + "
             "DIRECT per-frame table reads (slots 1..39, five words, "
             "unconditional).  The boot-1 payment discovery STANDS: "
             "payments DO land inside the 23f window (f_rel 2/3/10), "
             "and the ZERO-INPUT control walk shows 3 natural deaths "
             "paying 0 - the per-event attribution needs the direct "
             "reads."})
    json.dump(led, open(LEDGER, "w"), indent=1)
    print("[r48-t1] cap amended 1->2 (recording-defect disclosure)")
    n = amend_ledger(reasons)
    if n > 2:
        raise SystemExit("BOOT CAP EXCEEDED (2 - the disclosed "
                         "1->2 recording-defect amendment)")
    tag = time.strftime("r48_%H%M%S")
    stem = f"r48_boot{n}"
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
       "protocol": f"TAP_FRAMES={TAP_FRAMES} + TAIL_FRAMES="
                   f"{TAIL_FRAMES} per-frame score/census telemetry "
                   "+ DIRECT per-frame table reads (the corpse-"
                   "blindness fix; the disclosed cap amendment)",
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
            if r.get("note") not in ("no_targetable_at_tap1",
                                     "dead on restore",
                                     "frontier dead after restore") \
                    and r["deaths_seen"] > 0:
                break
        res = {"passes": pas, "final": t1.snap(m)}
        rep = {"schema": "ps1play.r48-frameexact/1",
               "generated": time.strftime("%FT%TZ", time.gmtime()),
               "commit": os.popen("git -C %s rev-parse HEAD"
                                  % _REPO).read().strip(),
               "frontiers_on_disk": have, "run": res}
        with open(os.path.join(EVID, f"{stem}_report.json"), "w") as f:
            json.dump(rep, f, indent=1, default=str)
        log(f"FIN passes={[(r['frontier'], len(r['taps'])) for r in pas]} "
            f"(wall {time.time() - T0:.0f}s)")
    finally:
        jf.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
