#!/usr/bin/env python3
"""r45t1_hp_readout.py — R45 (the 60% track, Issues #5/#9/#10).

The capsule lever (R44 close-out) = fallback (a): the DEFERRED
0x4054 soft-soldier HP-word readout from the saved frontier
postures (restore-only, cap 2).

PRE-RUN DISCLOSURE (the sandbox rollback): the R43/R44 sandbox was
rolled back to the Oct-22 snapshot — r43_postkill, r44_postkill and
the r44_frontier_a/b states are GONE (their bytes were never
committed: no-game-bytes rule).  The session-5 anchor
issue5_m1_start.state (Oct 20) SURVIVED on disk.  The capsule
budget anticipated exactly this: "a rebuild boot only if a frontier
is lost, disclosed".

Boot plan (cap 2, disclosed pre-run):
  boot 1 = frontier REBUILD + the readout, one process:
    A) restore issue5_m1_start -> the shipped policy in 15f chunks
       with continue-rescues (deaths allowed, counted, disclosed -
       the tainted-lineage rule; a rebuilt frontier is NEVER a clean
       claim) -> EAGER frontier saves past px 1200 (rolling
       r45_frontier_a/b, every >= 25 px gain - combat-live postures
       wanted) -> early exit when both slots are saved and the
       latest px >= 1260 (past the 1272-clamp fighting zone entry).
    B) restore r45_frontier_a -> census the live entities in
       x 1150-1450 (corpse/wreck excluded) -> ONE zero-input control
       tap -> up to 14 aimed-fire taps (nearest preferred-st target,
       face, Y burst) -> per-tap candidate-word deltas (+0x8E/+0x9E/
       +0xA4 + a disclosed wide net 0x88..0xA8) vs verified score
       deltas -> the readout table.
    C) if the census is empty at a -> restore r45_frontier_b (same
       boot, restore-only) -> the same readout.
  boot 2 = the spare (only if boot 1 died before any readout table
    exists; disclosed).

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
import r44t1_clean_resolve as r44                 # noqa: E402
from issue4_controller import boot_to_demo        # noqa: E402
from run_mission1_legit import recover_v2         # noqa: E402

SCRATCH = os.path.join(_REPO, "scratch", "r45")
PNGDIR = os.path.join(SCRATCH, "pngs")
LEDGER = os.path.join(SCRATCH, "boots_used.json")
EVID = os.path.join(_REPO, "data", "games", "SLUS-01212",
                    "truck_evidence", "r45")
STATES = "/home/z/my-project/emu/ws/states"

ANCHOR = "issue5_m1_start"
FRONTIER = ("r45_frontier_a", "r45_frontier_b")

PUSH_CAP = 900             # 15f chunks for the rebuild push
WALL_PUSH_S = 330
WALL_ALL_S = 560

WINDOW = (1150.0, 1450.0)  # the capsule readout window
FRONTIER_PX = 1200.0
FRONTIER_STEP = 25.0
EARLY_EXIT_PX = 1240.0     # both slots saved AND latest >= this

SOFT_ST = 0x4054           # the soft-soldier kind word (docs/truck_*
WRECK_ST = (0xA44C,)       # the truck wreck (corpse-equivalent)
CORPSE_ST = combat.CORPSE_ST

TAPS = 14                  # aimed taps per frontier
TAP_FRAMES = 24            # the Y burst
WIDE = tuple(range(0x88, 0xAA, 2))   # the disclosed wide net

FRONTIER_EVID = ["r45_frontier_a px>=1240", "r45_frontier_b px>=1200"]


def log(*a):
    print("[r45-t1]", *a, file=sys.stderr, flush=True)


def amend_ledger(reason):
    os.makedirs(SCRATCH, exist_ok=True)
    os.makedirs(EVID, exist_ok=True)
    if not os.path.exists(LEDGER):
        with open(LEDGER, "w") as f:
            json.dump({"cap": 2, "count": 0, "log": [], "note":
                       "R45 cap 2 DISCLOSED PRE-RUN (the capsule "
                       "budget: restore-only from the saved frontier "
                       "postures; a rebuild boot only if a frontier "
                       "is lost, disclosed).  SANDBOX ROLLBACK "
                       "DISCLOSURE: the R43/R44 states (r43_postkill, "
                       "r44_postkill, r44_frontier_a/b) are LOST to "
                       "the filesystem rollback; issue5_m1_start "
                       "(Oct 20) survived.  boot1 = frontier rebuild "
                       "(tainted lineage, continue-rescues counted) "
                       "+ the 0x4054 readout in ONE process; boot2 = "
                       "the spare.  Restores are NOT boots (r35 "
                       "precedent).",
                       "hypothesis":
                       "the aimed-fire readout at soft-soldier slots "
                       "(x 1150-1450, corpse/wreck excluded) reads "
                       "the soft-soldier HP word per tap "
                       "(+0x8E/+0xA4/+0x9E candidates) against "
                       "verified score gains"},
                      f, indent=1)
    with open(LEDGER) as f:
        led = json.load(f)
    led["count"] = int(led.get("count", 0)) + 1
    led.setdefault("log", []).append(
        {"n": led["count"], "ts": time.strftime("%FT%TZ", time.gmtime()),
         "script": "r45t1_hp_readout.py", "reason": reason})
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


def census_window(m, px):
    """Live entities in the readout window; corpse/wreck excluded
    (scan_entities already drops CORPSE_ST; the wreck st is dropped
    here).  Soft soldiers (st 0x4054) listed first."""
    ents = combat.scan_entities(m, px=px)
    out = []
    for e in ents:
        if not (WINDOW[0] <= e["x_px"] <= WINDOW[1]):
            continue
        if e["st"] in WRECK_ST:
            continue
        out.append(e)
    out.sort(key=lambda e: (e["st"] != SOFT_ST, abs(e["dx_px"])))
    return out


def save_frontier(p, m, J, px, state):
    try:
        p.save_state(state)
        J({"ev": "FRONTIER_SAVED", "state": state, "px": px,
           "census_n": len(census_window(m, px))})
        log(f"frontier saved px={px:.1f} -> {state} "
            f"(census {len(census_window(m, px))})")
        return True
    except Exception as e:                                  # noqa: BLE001
        J({"ev": "FRONTIER_SAVE_FAILED", "state": state,
           "err": repr(e)[:160]})
        return False


def push_phase(p, m, J, tag):
    """Phase A: the tainted rebuild push (deaths allowed, counted,
    disclosed) with EAGER frontier saves.  Sensor order + sane clamp
    + wrap fast-forward = the R44 lessons verbatim.  Early exit when
    both slots are saved and the latest px >= EARLY_EXIT_PX."""
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
        # SENSOR ORDER (chunk start, the R44 lesson): alive FIRST.
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
        # EAGER frontier saves (combat-live postures wanted): every
        # >= FRONTIER_STEP px gain past FRONTIER_PX, rolling a/b.
        if sane0 and px0 > FRONTIER_PX and \
                px0 > saved["px"] + FRONTIER_STEP:
            if save_frontier(p, m, J, px0,
                             FRONTIER[saved["i"] % 2]):
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
        print(f"[r45-trace] push c={c} px={px:.0f} mode={pol.mode} "
              f"segs={[(x['frames'], sorted(x['btns'] or set())) for x in segs]}",
              file=sys.stderr, flush=True)
        for x in segs:
            p.core.run(x["frames"], x["btns"] or set())
            if not t1.alive(m):
                break
        s2 = t1.snap(m)
        sane2 = 0.0 <= s2["px"] < 5000.0
        if sane2:
            max_px = max(max_px, s2["px"])
        # SENSOR ORDER (chunk end, the R44 lesson): alive FIRST.
        if not t1.alive(m):
            J({"ev": "CHUNK_END_DEATH", "chunk": c,
               "deaths_at_start": deaths, "px_end": s2["px"], **s2})
            png(p, f"chunkend_death_c{c}", tag)
            continue                   # recovery at the next chunk
        elif sane2 and max_px > 700.0 and s2["px"] < 700.0:
            J({"ev": "RESTART_LEAK_DYNAMIC", "chunk": c,
               "max_px": round(max_px, 1), "px_end": s2["px"], **s2})
            log(f"restart leak c{c} (deaths kept, push continues)")
            last_px, last_segs = None, None
            continue
        if sane2 and s2["px"] > FRONTIER_PX and \
                s2["px"] > saved["px"] + FRONTIER_STEP:
            if save_frontier(p, m, J, s2["px"],
                             FRONTIER[saved["i"] % 2]):
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


def readout_pass(p, m, J, tag, frontier, max_taps=TAPS):
    """Phase B/C: restore-only readout from one frontier posture."""
    out = {"frontier": frontier, "taps": [], "census_at_restore": [],
           "re_restores": 0}
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
    cen = census_window(m, s0["px"])
    out["census_at_restore"] = cen
    J({"ev": "CENSUS", "frontier": frontier, "px": s0["px"],
       "window": WINDOW, "entities": cen})
    log(f"census {frontier}: {len(cen)} live in-window")
    if not cen:
        out["note"] = "census_empty"
        return out
    slots = [e["slot"] for e in cen]
    # ---- the zero-input control tap --------------------------------
    pre = {"score": int(m.u32(t1.A_SCORE)),
           "words": {s: read_words(m, s) for s in slots},
           "ents": {s: entity_state(m, s) for s in slots}}
    p.core.run(TAP_FRAMES, set())
    post = {"score": int(m.u32(t1.A_SCORE)),
            "words": {s: read_words(m, s) for s in slots},
            "ents": {s: entity_state(m, s) for s in slots}}
    ctrl = {"tap": 0, "kind": "CONTROL_ZERO_INPUT",
            "score_delta": post["score"] - pre["score"],
            "word_deltas": {s: {k: post["words"][s][k] -
                                pre["words"][s][k]
                                for k in pre["words"][s]}
                            for s in slots},
            "ent_after": {s: post["ents"][s] for s in slots}}
    out["taps"].append(ctrl)
    J({"ev": "TAP", **ctrl, "frontier": frontier})
    # ---- the aimed taps --------------------------------------------
    for i in range(1, max_taps + 1):
        if not t1.alive(m):
            out["re_restores"] += 1
            J({"ev": "READOUT_DEATH", "frontier": frontier,
               "tap": i, "re_restores": out["re_restores"]})
            if out["re_restores"] > 2:
                out["note"] = "player died, re-restore budget gone"
                break
            p.load_state(frontier)
            if not t1.wait_alive(m, p, wait=10):
                out["note"] = "frontier dead after restore"
                break
            J({"ev": "RE_RESTORED", "frontier": frontier,
               "tap": i, **t1.snap(m)})
        cen = census_window(m, t1.px_of(m))
        if not cen:
            J({"ev": "CENSUS_EMPTY", "frontier": frontier, "tap": i})
            out["note"] = f"census_empty_at_tap{i}"
            break
        tgt = cen[0]
        # face the target (a brief hold; disclosed scripted input)
        if tgt["dx_px"] > 8.0:
            p.core.run(3, {"RIGHT"})
        elif tgt["dx_px"] < -8.0:
            p.core.run(3, {"LEFT"})
        slots = [e["slot"] for e in cen]
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
        tap = {"tap": i, "kind": "AIMED_Y",
               "target": tgt, "score_delta": post["score"] -
               pre["score"], "php": (pre["php"], post["php"]),
               "word_deltas": {s: {k: post["words"][s][k] -
                                   pre["words"][s][k]
                                   for k in pre["words"][s]}
                               for s in slots},
               "ent_after": {s: post["ents"][s] for s in slots},
               "slots_gone": gone}
        out["taps"].append(tap)
        J({"ev": "TAP", **tap, "frontier": frontier})
        log(f"tap {i}: tgt slot{tgt['slot']} st{hex(tgt['st'])} "
            f"dx{tgt['dx_px']:+.0f} dscore={tap['score_delta']} "
            f"gone={gone}")
        if gone:
            png(p, f"kill_tap{i}", tag)
    fin = t1.snap(m)
    out["final"] = fin
    J({"ev": "READOUT_DONE", "frontier": frontier, **fin})
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
    rep = {"schema": "ps1play.r45-readout/1", "stage": 1,
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
        raise SystemExit("no r45_frontier_* states on disk - run "
                         "stage 1 first (never fabricate a frontier)")
    # prefer the FURTHER frontier first (more depth), then the other
    # if its census is empty (the capsule method)
    p = boot_to_demo()
    m = p.mem
    pas = []
    for fr in order:
        r = readout_pass(p, m, J, tag, fr)
        pas.append(r)
        if r.get("note") not in ("census_empty", "dead on restore",
                                 "frontier dead after restore"):
            break
    res = {"readouts": pas, "final": t1.snap(m)}
    rep = {"schema": "ps1play.r45-readout/1", "stage": 2,
           "generated": time.strftime("%FT%TZ", time.gmtime()),
           "commit": os.popen("git -C %s rev-parse HEAD"
                              % _REPO).read().strip(),
           "anchor": ANCHOR, "run": res}
    with open(os.path.join(EVID, f"{stem}_report.json"), "w") as f:
        json.dump(rep, f, indent=1, default=str)
    log(f"STAGE2 FIN readouts="
        f"{[(r['frontier'], len(r['taps'])) for r in pas]}")
    return 0


def main():
    stage = (sys.argv[1] if len(sys.argv) > 1 else "1").strip()
    assert stage in ("1", "2"), "usage: r45t1_hp_readout.py [1|2]"
    t_start = time.time()
    reasons = {
        "1": "BOOT stage-1 (the frontier REBUILD; DISCLOSED: the R44 "
             "frontiers + r43_postkill are LOST to the sandbox "
             "rollback - the capsule contingency; the rebuilt "
             "frontier lineage is TAINTED, continue-rescues counted, "
             "never a clean claim): boot -> restore issue5_m1_start "
             "(survived) -> tainted push (deaths counted, eager "
             "frontier saves r45_frontier_a/b px>1200 every >=25px, "
             "early exit both saved & latest >=1240) -> exit",
        "2": "BOOT stage-2 (the READOUT, restore-only): boot -> "
             "restore r45_frontier_a -> census x 1150-1450 "
             "(corpse/wreck excluded) -> zero-input control tap -> "
             "aimed-fire taps (per-tap candidate-word deltas vs "
             "score deltas) -> restore b if census empty -> report",
    }
    n = amend_ledger(reasons[stage])
    if n > 2:
        raise SystemExit("BOOT CAP EXCEEDED (2)")
    tag = time.strftime(f"r45b{n}_%H%M%S")
    stem = f"r45_boot{n}_s{stage}"
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
           "r43_postkill/r44_postkill/r44_frontier_a/b LOST to the "
           "sandbox filesystem rollback; issue5_m1_start survived "
           "(Oct 20); the capsule contingency (rebuild boot, "
           "disclosed) applies; boot ledger entries 1 from the "
           "aborted same-round background attempts were REFUNDED "
           "per the corrected-filings precedent (process died in "
           "boot_to_demo, no jsonl event beyond RUN_START)",
       "lineage": "TAINTED (continue-rescues; never a clean claim)",
       "oracle": "walker words + verified score gains + alive "
                 "0x0EE518; never +0x8E (the wide net = disclosed "
                 "exploratory telemetry)",
       "ts": time.strftime("%FT%TZ", time.gmtime())})
    try:
        if stage == "1":
            rc = do_stage1(J, tag, stem)
        else:
            rc = do_stage2(J, tag, stem)
    finally:
        jf.close()
    log(f"report -> {EVID}/{stem}_report.json "
        f"(wall {time.time() - t_start:.0f}s)")
    return rc


if __name__ == "__main__":
    sys.exit(main())
