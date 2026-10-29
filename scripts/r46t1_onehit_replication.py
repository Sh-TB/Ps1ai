#!/usr/bin/env python3
"""r46t1_onehit_replication.py — R46 (the 60% track, Issues #5/#9/#10).

The capsule lever (R45 close-out): the soft-soldier ONE-HIT kill
finding replication.

HYPOTHESIS (verbatim from the capsule): the soft-soldier ONE-HIT kill
finding replicates: >= 3 ground (kind=='enemy') 0x4054-class kills
from the frontier postures, each dying to a single aimed tap with the
flat +100 and NO candidate-word decrement before death - converting
the soldier class to "one-hit, no tracked HP word" with the unchanged
oracle (walker words + verified score gains + alive 0x0EE518; never
+0x8E).  Any multi-tap kill or any decrementing word REFUTES the
one-hit reading and reopens the HP-word hunt at the non-candidate
offsets.

R45 protocol note applied: the tap fallback hit AIRBORNE projectiles
after the ground entities died (dscore 0) - THIS round filters
kind=='enemy' (ground only; corpse/wreck excluded; projectile_air
slots are never targeted).

Boot plan (cap 1, DISCLOSED PRE-RUN - restore-only; the boot is the
core+rom load only):
  boot -> restore r45_frontier_b (px 1254.8, census 13 expected) ->
  census (ground-only) -> ONE zero-input control tap -> up to 16
  aimed taps (nearest ground enemy, soft-st preferred; face + Y
  burst) -> per-tap wide-net word deltas + score deltas -> the kill
  table; restore r45_frontier_a for a second pass in the SAME boot if
  kills < 3; early exit once kills >= 3.

Kill-row verdict rules (recorded per ground slot that dies):
  one_hit = (death tap carries the flat +100) AND (every prior tap
  aimed at the slot shows NO wide-net decrement AND NO non-zero score
  delta attributable while it was alive).  A prior tap with all-zero
  deltas is a MISS (bullets may not connect) - it does not refute.
  REFUTATION evidence = a prior tap with a non-zero word delta on the
  slot (HP chipping) or a non-+100 death-tap score.

Comparative rows: ground slots with st != 0x4054 (e.g. 0x42bc) are
recorded with the same table but do NOT count toward the >= 3
replication (the R45 finding is about the 0x4054 class; the R45
0x42bc slot died 2 taps after its +100 - the contrast is data).
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

SCRATCH = os.path.join(_REPO, "scratch", "r46")
PNGDIR = os.path.join(SCRATCH, "pngs")
LEDGER = os.path.join(SCRATCH, "boots_used.json")
EVID = os.path.join(_REPO, "data", "games", "SLUS-01212",
                    "truck_evidence", "r46")
STATES = "/home/z/my-project/emu/ws/states"

FRONTIER_B = "r45_frontier_b"      # px 1254.8, census 13 expected
FRONTIER_A = "r45_frontier_a"      # px 1224.9, the R45 readout pass

WINDOW = (1150.0, 1450.0)
SOFT_ST = 0x4054
WRECK_ST = (0xA44C,)
CORPSE_ST = combat.CORPSE_ST

TAPS = 16                  # aimed taps per frontier pass
TAP_FRAMES = 24            # the Y burst
WIDE = tuple(range(0x88, 0xAA, 2))   # the disclosed wide net
KILLS_NEEDED = 3
RE_RESTORE_MAX = 2         # per frontier pass (the R45 budget)
WALL_ALL_S = 560


def log(*a):
    print("[r46-t1]", *a, file=sys.stderr, flush=True)


def amend_ledger(reason):
    os.makedirs(SCRATCH, exist_ok=True)
    os.makedirs(EVID, exist_ok=True)
    if not os.path.exists(LEDGER):
        with open(LEDGER, "w") as f:
            json.dump({"cap": 1, "count": 0, "log": [], "note":
                       "R46 cap 1 DISCLOSED PRE-RUN (the capsule "
                       "budget: restore-only from the SAVED "
                       "r45_frontier_a/b - they survive on disk; the "
                       "boot is the core+rom load only).  Restores "
                       "are NOT boots (r35 precedent).",
                       "hypothesis":
                       "the soft-soldier ONE-HIT kill finding "
                       "replicates: >= 3 ground kind=='enemy' "
                       "0x4054-class kills, each dying to a single "
                       "aimed tap with the flat +100 and NO "
                       "candidate-word decrement before death"},
                      f, indent=1)
    with open(LEDGER) as f:
        led = json.load(f)
    led["count"] = int(led.get("count", 0)) + 1
    led.setdefault("log", []).append(
        {"n": led["count"], "ts": time.strftime("%FT%TZ", time.gmtime()),
         "script": "r46t1_onehit_replication.py", "reason": reason})
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


def census_ground(m, px):
    """GROUND-ONLY live entities in the window (the R46 filter):
    kind=='enemy', corpse/wreck excluded.  Soft soldiers (st 0x4054)
    listed first, then nearest."""
    ents = combat.scan_entities(m, px=px)
    out = []
    for e in ents:
        if e.get("kind") != "enemy":          # the R46 ground filter
            continue
        if not (WINDOW[0] <= e["x_px"] <= WINDOW[1]):
            continue
        if e["st"] in WRECK_ST:
            continue
        out.append(e)
    out.sort(key=lambda e: (e["st"] != SOFT_ST, abs(e["dx_px"])))
    return out


def aimed_tap(p, m, J, tag, tgt, tap_i, hist, pass_out):
    """One aimed tap at the nearest ground enemy + full per-slot
    delta table (the wide net + score + entity states)."""
    if tgt["dx_px"] > 8.0:
        p.core.run(3, {"RIGHT"})
    elif tgt["dx_px"] < -8.0:
        p.core.run(3, {"LEFT"})
    cen = census_ground(m, t1.px_of(m))
    slots = [e["slot"] for e in cen]
    if tgt["slot"] not in slots:
        J({"ev": "TARGET_LOST_PRE_TAP", "tap": tap_i,
           "target": tgt, "census": cen})
    pre = {"score": int(m.u32(t1.A_SCORE)),
           "words": {s: read_words(m, s) for s in slots},
           "ents": {s: entity_state(m, s) for s in slots},
           "php": int(m.u16(t1.PLAYER_HP))}
    p.core.run(TAP_FRAMES, {"Y"})
    post = {"score": int(m.u32(t1.A_SCORE)),
            "words": {s: read_words(m, s) for s in slots},
            "ents": {s: entity_state(m, s) for s in slots},
            "php": int(m.u16(t1.PLAYER_HP))}
    gone = [s for s in slots
            if post["ents"][s]["st"] in CORPSE_ST
            or post["ents"][s]["f8e"] == 0]
    wd = {s: {k: post["words"][s][k] - pre["words"][s][k]
              for k in pre["words"][s]} for s in slots}
    dscore = post["score"] - pre["score"]
    tap = {"tap": tap_i, "kind": "AIMED_Y_GROUND",
           "target": tgt, "score_delta": dscore,
           "php": (pre["php"], post["php"]),
           "word_deltas": wd,
           "ent_after": {s: post["ents"][s] for s in slots},
           "slots_gone": gone}
    pass_out["taps"].append(tap)
    J({"ev": "TAP", **tap})
    # history per slot (for the kill table)
    for s in slots:
        hist.setdefault(s, []).append(
            {"tap": tap_i, "score_delta": dscore, "wd": wd[s],
             "was_target": tgt["slot"] == s})
    log(f"tap {tap_i}: tgt slot{tgt['slot']} st{hex(tgt['st'])} "
        f"dx{tgt['dx_px']:+.0f} dscore={dscore} gone={gone}")
    return tap, gone


def kill_table(pass_out, hist, frontier):
    """Build the kill rows for every ground slot that died this pass
    + the one-hit verdict per the capsule rules."""
    rows = []
    for t in pass_out["taps"]:
        for s in (t.get("slots_gone") or []):
            if any(r["slot"] == s for r in rows):
                continue
            ent = t["ent_after"].get(s) or {}
            prior = [h for h in hist.get(s, [])
                     if h["tap"] != t["tap"]]
            # evidence of prior damage on THIS slot: any wide-net word
            # delta != 0, or a non-zero score delta on a tap where the
            # slot was the TARGET (attribution-safe rule).
            prior_chip = [
                h for h in prior
                if any(v != 0 for v in h["wd"].values())
                or (h["was_target"] and h["score_delta"] != 0)]
            st = ent.get("st")
            rows.append({
                "frontier": frontier, "slot": s, "st": st,
                "class": ("soft_0x4054" if st == SOFT_ST
                          else f"other_{hex(st)}" if st else "unknown"),
                "death_tap": t["tap"],
                "death_score_delta": t["score_delta"],
                "prior_taps": len(prior),
                "prior_chip_events": prior_chip,
                "flat_100_at_death": t["score_delta"] == 100,
                "one_hit_verdict":
                    "ONE_HIT" if (t["score_delta"] == 100
                                  and not prior_chip) else "REFUTES",
                "is_0x4054_class": st == SOFT_ST})
    return rows


def run_pass(p, m, J, tag, frontier, kills_so_far):
    """Restore-only readout pass from one frontier posture,
    ground-only targets."""
    out = {"frontier": frontier, "taps": [], "census_at_restore": [],
           "re_restores": 0, "kills": 0}
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
    cen = census_ground(m, s0["px"])
    out["census_at_restore"] = cen
    J({"ev": "CENSUS_GROUND", "frontier": frontier, "px": s0["px"],
       "window": WINDOW, "entities": cen})
    log(f"census {frontier}: {len(cen)} ground live in-window")
    if not cen:
        out["note"] = "census_empty_ground"
        return out
    # ---- the zero-input control tap --------------------------------
    slots = [e["slot"] for e in cen]
    pre = {"score": int(m.u32(t1.A_SCORE)),
           "words": {s: read_words(m, s) for s in slots}}
    p.core.run(TAP_FRAMES, set())
    post = {"score": int(m.u32(t1.A_SCORE)),
            "words": {s: read_words(m, s) for s in slots}}
    ctrl = {"tap": 0, "kind": "CONTROL_ZERO_INPUT",
            "score_delta": post["score"] - pre["score"],
            "word_deltas": {s: {k: post["words"][s][k] -
                                pre["words"][s][k]
                                for k in pre["words"][s]}
                            for s in slots}}
    out["taps"].append(ctrl)
    J({"ev": "TAP", **ctrl, "frontier": frontier})
    # ---- the aimed ground taps -------------------------------------
    for i in range(1, TAPS + 1):
        if time.time() - T0 > WALL_ALL_S:
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
        cen = census_ground(m, t1.px_of(m))
        if not cen:
            J({"ev": "CENSUS_EMPTY_GROUND", "frontier": frontier,
               "tap": i})
            out["note"] = f"census_empty_ground_at_tap{i}"
            break
        tgt = cen[0]
        tap, gone = aimed_tap(p, m, J, tag, tgt, i, hist, out)
        if gone:
            png(p, f"kill_tap{i}", tag)
            kt = kill_table({"taps": [tap]}, hist, frontier)
            for r in kt:
                r["frontier"] = frontier
                J({"ev": "KILL_ROW", **r})
            new4054 = [r for r in kt
                       if r["is_0x4054_class"]
                       and r["one_hit_verdict"] == "ONE_HIT"]
            refutes = [r for r in kt if r["one_hit_verdict"] == "REFUTES"]
            out["kills"] += len([r for r in kt
                                 if r["is_0x4054_class"]])
            if refutes:
                out.setdefault("refutations", []).extend(refutes)
            if new4054:
                log(f"KILL slot{tgt['slot']} st0x4054 one-hit "
                    f"confirmed ({len(new4054)} this tap)")
    rows = kill_table(out, hist, frontier)
    out["kill_table"] = rows
    out["kills_0x4054"] = len([r for r in rows
                               if r["is_0x4054_class"]])
    out["one_hit_0x4054"] = len([r for r in rows
                                 if r["is_0x4054_class"]
                                 and r["one_hit_verdict"] == "ONE_HIT"])
    out["refute_rows"] = [r for r in rows
                          if r["one_hit_verdict"] == "REFUTES"]
    log(f"pass {frontier} done: kills_0x4054={out['kills_0x4054']} "
        f"one_hit={out['one_hit_0x4054']} "
        f"refutes={len(out['refute_rows'])}")
    fin = t1.snap(m)
    out["final"] = fin
    J({"ev": "PASS_DONE", "frontier": frontier, **fin})
    return out


def main():
    global T0
    t_start = time.time()
    T0 = t_start
    reason = ("BOOT (the ONE-HIT replication, restore-only; cap 1 "
              "DISCLOSED PRE-RUN): boot -> restore r45_frontier_b "
              "(px 1254.8, census 13 expected) -> ground-only census "
              "(kind=='enemy', corpse/wreck excluded) -> zero-input "
              "control tap -> aimed ground taps (per-tap wide-net "
              "deltas + score deltas -> kill table) -> restore "
              "r45_frontier_a in the SAME boot if kills < 3; early "
              "exit at kills >= 3")
    n = amend_ledger(reason)
    if n > 1:
        raise SystemExit("BOOT CAP EXCEEDED (1)")
    tag = time.strftime("r46_%H%M%S")
    stem = "r46_boot1"
    os.makedirs(SCRATCH, exist_ok=True)
    os.makedirs(EVID, exist_ok=True)
    order = []
    for fr in (FRONTIER_B, FRONTIER_A):
        if os.path.exists(os.path.join(STATES, fr + ".state")):
            order.append(fr)
        else:
            log("FRONTIER ABSENT:", fr)
    if not order:
        raise SystemExit("no r45_frontier_* states on disk - never "
                         "fabricate a frontier")
    tr_path = os.path.join(EVID, f"{stem}.jsonl")
    jf = open(tr_path, "w")

    def J(ev):
        jf.write(json.dumps(ev, default=str) + "\n")
        jf.flush()

    J({"ev": "RUN_START",
       "commit": os.popen("git -C %s rev-parse HEAD"
                          % _REPO).read().strip(),
       "rollback_watch":
           "pre-flight: r45_frontier_a/b verified on disk before the "
           "boot (the R45 rollback lesson)",
       "oracle": "walker words + verified score gains + alive "
                 "0x0EE518; never +0x8E (the wide net = disclosed "
                 "exploratory telemetry)",
       "protocol_note": "ground-only targets (kind=='enemy'); the R45 "
                        "projectile-tap waste is filtered out",
       "ts": time.strftime("%FT%TZ", time.gmtime())})
    try:
        p = boot_to_demo()
        m = p.mem
        passes = []
        kills = 0
        refutes = []
        verdict = "INCOMPLETE"
        for fr in order:
            pr = run_pass(p, m, J, tag, fr, kills)
            passes.append(pr)
            kills += pr.get("one_hit_0x4054", 0)
            refutes.extend(pr.get("refute_rows", []))
            if kills >= KILLS_NEEDED:
                verdict = ("ONE_HIT_REPLICATED"
                           if not refutes else "MIXED")
                break
            if pr.get("note") in ("dead on restore",
                                  "frontier dead after restore"):
                continue
        else:
            if kills >= KILLS_NEEDED:
                verdict = "ONE_HIT_REPLICATED" if not refutes \
                    else "MIXED"
            elif refutes:
                verdict = "REFUTED"
            elif kills > 0:
                verdict = f"PARTIAL (kills={kills} < 3, cap spent)"
            else:
                verdict = "NO_KILLS_OBSERVED (cap spent)"
        res = {"passes": passes, "kills_total": kills,
               "verdict": verdict}
        rep = {"schema": "ps1play.r46-onehit/1",
               "generated": time.strftime("%FT%TZ", time.gmtime()),
               "commit": os.popen("git -C %s rev-parse HEAD"
                                  % _REPO).read().strip(),
               "run": res}
        with open(os.path.join(EVID, f"{stem}_report.json"), "w") as f:
            json.dump(rep, f, indent=1, default=str)
        J({"ev": "RUN_DONE", "verdict": verdict,
           "kills_total": kills})
        log(f"RUN DONE verdict={verdict} kills={kills} "
            f"(wall {time.time() - t_start:.0f}s)")
        rc = 0
    finally:
        jf.close()
    log(f"report -> {EVID}/{stem}_report.json")
    return rc


if __name__ == "__main__":
    sys.exit(main())
