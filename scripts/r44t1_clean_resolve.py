#!/usr/bin/env python3
"""r44t1_clean_resolve.py — R44 BOOT (the 60% track, Issues #5/#9/#10).

The capsule lever (R43 close-out): the end-of-mission chain fires ONLY
from a CLEAN (deaths=0, no-restart) resolve posture.

Stage 1: boot -> restore the surviving session-5 anchor
issue5_m1_start (M1 start px ~26) -> rebuild with the SHIPPED policy
under the R43 harness lessons:
  - DYNAMIC restart guard: max_px is tracked from chunk 0; once the
    world has been DEEP (max_px > 700), any px < 700 is a silent
    restart leak (the c164->c165 timer-expiry path reads as
    alive-at-25) = HONEST ABORT.  (The R43 phase-open-state guard was
    permanently off for shallow anchors; the dynamic guard cannot be
    fooled by the anchor's start depth.)
  - deaths=0 VALIDITY: any death taints the posture (a continue-rescue
    is still a death) -> honest abort of the clean-claim (the spare
    boot retries; the capsule fallbacks follow if deaths=0 proves
    unreachable in budget).
  - frontier saves: whenever px > 1200 (the boot-7 px-1378 posture was
    lost to exit without a save), a rolling r44_frontier_a/_b state is
    saved (checks at chunk start AND chunk end).
  - gate unchanged (the boot-5 lesson): aa_resolved >= 1 AND px > 700
    (the aa zone px 912-1164 is the only honest depth for the stat) ->
    save r44_postkill.

Stage 2: boot -> restore r44_postkill -> policy to the mission_end
latch (900-chunk bound, frontier saves live here too) -> the
session-6 accept chain (W watch / S ladder / P probe / M walk) -> the
M2 input-delta discriminator (INTERACTIVE iff dR >= 30 and
dR - dL >= 60 at the spawn fingerprint px 70-80/php 70-80/gren>=9/
score<=200).

Fallback levers if stage 1 cannot produce a clean posture in budget
(NOT auto-run; each needs its own disclosure): (a) the deferred
0x4054 soft-soldier HP-word readout, (b) the px-1272 clamp push.

Oracle unchanged: walker words + verified score gains + alive
0x0EE518; never +0x8E in any oracle.  Every input after the latch is a
DISCLOSED scripted probe; restart and death sensors are the hardened
R42 classifiers.
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

SCRATCH = os.path.join(_REPO, "scratch", "r44")
PNGDIR = os.path.join(SCRATCH, "pngs")
LEDGER = os.path.join(SCRATCH, "boots_used.json")
EVID = os.path.join(_REPO, "data", "games", "SLUS-01212",
                    "truck_evidence", "r44")

ANCHOR = "issue5_m1_start"      # session-5-era M1 start (px ~26)
POSTKILL = "r44_postkill"       # CLEAN resolve posture (deaths=0)
POSTKILL43 = "r43_postkill"     # the on-disk TAINTED posture (post-
                                # restart checkpoint-respawn px 992,
                                # flags 0x4B, score 4501) - fallback-b
                                # lineage, NEVER a clean claim
FRONTIER = ("r44_frontier_a", "r44_frontier_b")

REBUILD_CHUNKS = 1200
LATCH_CHUNKS = 900
WALL_GUARD_S = 8.5 * 60

W_WATCH = 6
S_ROUNDS = 8
M_CHUNKS = 120

M2_PX = (70.0, 80.0)
M2_PHP = (70.0, 80.0)
M2_GREN_MIN = 9
M2_SCORE_MAX = 200

D_RIGHT_MIN = 30.0
D_CONTRAST_MIN = 60.0

RESTART_PX_LO, RESTART_PX_HI = 20.0, 60.0
DEEP_PX = 700.0
FRONTIER_PX = 1200.0


def log(*a):
    print("[r44-t1]", *a, file=sys.stderr, flush=True)


def amend_ledger(reason, script="r44t1_clean_resolve.py"):
    os.makedirs(SCRATCH, exist_ok=True)
    if not os.path.exists(LEDGER):
        with open(LEDGER, "w") as f:
            json.dump({"cap": 4, "count": 0, "log": [], "note":
                       "R44 cap 4 DISCLOSED PRE-RUN (the capsule budget: "
                       "stage-1 rebuilds are death-sensitive; one "
                       "spare): boot1 = stage-1 clean rebuild (dynamic "
                       "restart guard + deaths=0 + frontier saves) -> "
                       "r44_postkill; boot2 = stage-2 latch -> accept "
                       "chain -> discriminator; boot3 = spare stage-1; "
                       "boot4 = spare stage-2. Restores are NOT boots "
                       "(r35 precedent). Fallbacks (a) 0x4054 HP-word "
                       "readout / (b) px-1272 clamp push need their "
                       "own disclosure beyond this cap.",
                       "hypothesis":
                       "the end-of-mission chain fires ONLY from a "
                       "clean (deaths=0, no-restart) resolve posture"},
                      f, indent=1)
    with open(LEDGER) as f:
        led = json.load(f)
    led["count"] = int(led.get("count", 0)) + 1
    led.setdefault("log", []).append(
        {"n": led["count"], "ts": time.strftime("%FT%TZ", time.gmtime()),
         "script": script, "reason": reason})
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


def vm_compact(m):
    return {"flags": t2.rd_u16(m, t2.O_FLAGS),
            "prog": hex(t2.rd_u32(m, t2.O_PROG) or 0),
            "state": t2.rd_u16(m, t2.O_STATE),
            "cursor": hex(t2.rd_u32(m, t2.O_CURSOR) or 0),
            "gate_b": (t2.rd_u8(m, t2.O_GB1), t2.rd_u8(m, t2.O_GB2))}


def teardown(m):
    s = t1.snap(m)
    return s["px"] == 0.0 and s["php"] == 0, s


def m2_fingerprint(s):
    return (M2_PX[0] <= s["px"] <= M2_PX[1]
            and M2_PHP[0] <= s["php"] <= M2_PHP[1]
            and s["gren"] >= M2_GREN_MIN
            and s["score"] <= M2_SCORE_MAX)


def save_frontier(p, m, J, px, state):
    """The boot-7 lesson: frontier postures must be SAVED.  Rolling
    pair a/b so one save can never clobber the previous frontier."""
    try:
        p.save_state(state)
        J({"ev": "FRONTIER_SAVED", "state": state, "px": px})
        log(f"frontier saved px={px:.0f} -> {state}")
        return True
    except Exception as e:                                  # noqa: BLE001
        J({"ev": "FRONTIER_SAVE_FAILED", "state": state,
           "err": repr(e)[:160]})
        return False


def policy_phase(p, m, J, tag, cap, phase, until_latch):
    """The shipped policy: until the resolve gate (until_latch=False,
    stage 1) or the mission_end latch (until_latch=True, stage 2).

    R44 harness upgrades vs r43t1:
      - DYNAMIC restart guard: max_px from chunk 0; deep-then-shallow
        (max_px > 700 then px < 700) = RESTART_LEAK honest abort.  The
        c>2 warmup only suppresses the chunk-0 restore transient.
      - deaths=0 validity (stage 1): first death = 'death_taints' honest
        abort (wait_alive + recover first, so the world is left sane).
      - frontier saves whenever px > 1200 (chunk start AND end).
    Returns (outcome, c, deaths, pol)."""
    pol = combat.CombatPolicy(queue_priority=True)
    p.core.run(2, set())
    J({"ev": "PHASE_START", "phase": phase, "snap": t1.snap(m),
       "vm": t2.read_vm(m)})
    t0 = time.time()
    last_px, last_segs = None, None
    prev_score = int(m.u32(t1.A_SCORE))
    deaths = 0
    max_px = -1.0
    saved_front = {"i": 0, "px": -1.0}
    for c in range(cap):
        if time.time() - t0 > WALL_GUARD_S:
            return "wall_guard", c, deaths, pol
        px0 = t1.px_of(m)
        # SANE-WORLD clamp (the boot-3 lesson): the scene-transition
        # wrap (px 65494-65535 seen alive in R43 boot-5 c160 and here)
        # is NOT a position - it must never feed max_px, the leak
        # guard, or a frontier save.
        sane0 = 0.0 <= px0 < 5000.0
        if sane0:
            max_px = max(max_px, px0)
        # SENSOR ORDER (chunk start, the boot-3 lesson mirrored from
        # the chunk-end fix): alive FIRST - a dead world takes the
        # death path (count + recover + continue, the boot-7
        # continue-rescue pattern), never a restart classification.
        if not t1.alive(m):
            deaths += 1
            J({"ev": "death", "phase": phase, "chunk": c,
               "deaths": deaths, **t1.snap(m)})
            png(p, f"death_{phase}_c{c}", tag)
            if not t1.wait_alive(m, p, wait=20):
                from run_mission1_legit import recover_v2
                if not recover_v2(p, log=log) or \
                        not t1.wait_alive(m, p, wait=20):
                    return "death_no_respawn", c, deaths, pol
            if not until_latch:
                # stage 1: deaths=0 is a HARD validity requirement -
                # the world is recovered/sane, the claim is not.
                J({"ev": "CLEAN_REQUIREMENT_TAINTED", "phase": phase,
                   "chunk": c, "deaths": deaths})
                log(f"death taints the clean requirement c{c} "
                    f"(deaths={deaths}) - honest abort")
                return "death_taints", c, deaths, pol
            last_px, last_segs = None, None
            continue
        if px0 > 5000.0:
            # the wrap/transition world (fast-forward through it,
            # the r43t1 pattern)
            p.core.run(60, set())
            continue
        if max_px > DEEP_PX and px0 < DEEP_PX and c > 2:
            J({"ev": "RESTART_LEAK_DYNAMIC", "phase": phase, "chunk": c,
               "max_px": round(max_px, 1), "px": px0, **t1.snap(m)})
            log(f"RESTART_LEAK (dynamic) c{c} max_px={max_px:.0f} "
                f"px={px0:.0f}")
            return "restart_leak", c, deaths, pol
        if sane0 and px0 > FRONTIER_PX and px0 > saved_front["px"] + 50:
            if save_frontier(p, m, J, px0,
                             FRONTIER[saved_front["i"] % 2]):
                saved_front["i"] += 1
                saved_front["px"] = px0
        px_early = t1.px_of(m)
        sec = combat.scan_section(m)
        pol.observe_section(sec, px_now=px_early)
        px = t1.px_of(m)
        max_px = max(max_px, px)
        advanced = 0.0 if last_px is None else px - last_px
        intent = any("RIGHT" in (x.get("btns") or set())
                     for x in (last_segs or []))
        pol.observe(px, advanced, intent)
        cen = t1.census(m, px)
        scan = combat.scan_entities(m, px=px)
        gren0 = int(m.u8(t1.GRENADES))
        segs = pol.decide(15, px, scan, grenades=gren0,
                          hp=int(m.u16(t1.PLAYER_HP)))
        last_px, last_segs = px, segs
        # per-chunk stderr trail (the boot-4/5 hang-hunt pattern): the
        # last line before any hang names the chunk + mode + segments
        print(f"[r44-trace] {phase} c={c} px={px:.0f} mode={pol.mode} "
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
        # SENSOR ORDER (the boot-1 lesson): a mid-chunk death surfaces
        # HERE (chunk end) as px_end=0/php=0 - the boot-1 c86 death was
        # mislabeled restart_leak because the leak guard ran before the
        # death sensor.  Alive-check FIRST; a dead world is never a
        # restart classification.
        if not t1.alive(m):
            J({"ev": "CHUNK_END_DEATH", "phase": phase, "chunk": c,
               "deaths_at_start": deaths, "px_end": s2["px"], **s2})
            png(p, f"chunkend_death_{phase}_c{c}", tag)
            if not until_latch:
                from run_mission1_legit import recover_v2
                recover_v2(p, log=log)
                J({"ev": "CLEAN_REQUIREMENT_TAINTED", "phase": phase,
                   "chunk": c, "deaths": deaths + 1,
                   "why": "mid-chunk death (chunk-end sensor)"})
                log(f"mid-chunk death taints the clean requirement c{c}")
                return "death_taints", c, deaths + 1, pol
            log(f"chunk-end death c{c} (stage 2: recovery at next "
                f"chunk start)")
        elif sane2 and max_px > DEEP_PX and s2["px"] < DEEP_PX:
            J({"ev": "RESTART_LEAK_DYNAMIC_END", "phase": phase,
               "chunk": c, "max_px": round(max_px, 1),
               "px_end": s2["px"], **s2})
            log(f"RESTART_LEAK (dynamic, chunk-end) c{c} "
                f"max_px={max_px:.0f} px_end={s2['px']:.0f}")
            return "restart_leak", c, deaths, pol
        if sane2 and s2["px"] > FRONTIER_PX and \
                s2["px"] > saved_front["px"] + 50:
            if save_frontier(p, m, J, s2["px"],
                             FRONTIER[saved_front["i"] % 2]):
                saved_front["i"] += 1
                saved_front["px"] = s2["px"]
        if s2["score"] != prev_score:
            J({"ev": "SCORE_EVENT", "phase": phase, "chunk": c,
               "from": prev_score, "to": s2["score"]})
            prev_score = s2["score"]
        if c % 20 == 0:
            J({"ev": "PHASE_DUMP", "phase": phase, "chunk": c,
               "mode": pol.mode, "vm": vm_compact(m), "max_px":
               round(max_px, 1), **s2})
        if until_latch and pol.mission_end:
            J({"ev": "MISSION_END_LATCH", "phase": phase, "chunk": c,
               "deaths": deaths, "max_px": round(max_px, 1),
               "stats": {k: v for k, v in pol.stats.items() if v},
               "vm": t2.read_vm(m), **s2})
            log(f"MISSION_END LATCHED c{c} px={s2['px']} "
                f"score={s2['score']} deaths={deaths}")
            return "latched", c, deaths, pol
        if not until_latch and (pol.mission_end or
                                (pol.stats.get("aa_resolved", 0) >= 1
                                 and t1.px_of(m) > 700.0)):
            how = ("aa_resolved" if pol.stats.get("aa_resolved", 0) >= 1
                   else "mission_end_latch")
            state = POSTKILL if deaths == 0 else POSTKILL + "_tainted"
            p.save_state(state)
            J({"ev": "RESOLVED", "phase": phase, "chunk": c, "how": how,
               "deaths": deaths, "clean": deaths == 0,
               "max_px": round(max_px, 1), "postkill_state": state,
               "vm": t2.read_vm(m), **s2})
            log(f"RESOLVED ({how}) c{c} deaths={deaths} -> {state} "
                f"saved")
            return ("resolved_clean" if deaths == 0
                    else "resolved_tainted"), c, deaths, pol
    return "budget", cap - 1, deaths, pol


def right_probe(p, m, J, tag, label, frames=60):
    s0 = t1.snap(m)
    p.core.run(frames, {"RIGHT"})
    s1 = t1.snap(m)
    moved = s1["px"] - s0["px"]
    J({"ev": "RIGHT_PROBE", "label": label, "from_px": s0["px"],
       "moved_px": round(moved, 1), **s1})
    png(p, f"{label}_right", tag)
    return moved > 8.0 and t1.alive(m), moved, s1


def walk_forward(p, m, J, tag):
    trans = []
    spawn_seen = None
    for i in range(M_CHUNKS):
        p.core.run(30, {"RIGHT"})
        s = t1.snap(m)
        ev = {"ev": "M", "i": i, **s}
        if m2_fingerprint(s):
            spawn_seen = i
            J({**ev, "vm": t2.read_vm(m), "note": "M2_SPAWN_FINGERPRINT"})
            png(p, f"M{i:03d}_spawn", tag)
            log(f"M2 SPAWN FINGERPRINT i={i} px={s['px']} php={s['php']} "
                f"gren={s['gren']} score={s['score']}")
            return {"chunks": i, "transitions": trans, "spawn_i": i,
                    "spawn": s}
        if not t1.alive(m):
            trans.append(ev)
            J({**ev, "vm": t2.read_vm(m), "note": "anomaly_paused"})
            png(p, f"M{i:03d}", tag)
            p.core.run(60, set())
        elif i % 10 == 0:
            J(ev)
        if i % 15 == 0:
            png(p, f"M{i:03d}", tag)
        if not t1.alive(m):
            J({"ev": "M_DEATH", "i": i, **t1.snap(m)})
            png(p, "M_death", tag)
            if not t1.wait_alive(m, p, wait=60):
                from run_mission1_legit import recover_v2
                recover_v2(p, log=log)
                t1.wait_alive(m, p, wait=20)
    fin = t1.snap(m)
    J({"ev": "M_done", "chunks": M_CHUNKS, "final": fin,
       "n_transitions": len(trans)})
    png(p, "M_final", tag)
    return {"chunks": M_CHUNKS, "transitions": trans, "spawn_i": None,
            "final": fin}


def discriminator(p, m, J, tag):
    legs = {}
    for name, frames, btns in (("zero", 60, set()),
                               ("right", 90, {"RIGHT"}),
                               ("left", 60, {"LEFT"})):
        s0 = t1.snap(m)
        p.core.run(frames, btns)
        s1 = t1.snap(m)
        d = round(s1["px"] - s0["px"], 1)
        legs[name] = {"d_px": d, "score": (s0["score"], s1["score"]),
                      "php": (s0["php"], s1["php"]), "final": s1}
        J({"ev": "DISCRIMINATOR_LEG", "leg": name, "frames": frames,
           "d_px": d, **s1})
        png(p, f"disc_{name}", tag)
    dR = legs["right"]["d_px"]
    dL = legs["left"]["d_px"]
    verdict = ("INTERACTIVE_M2_ENTRY"
               if dR >= D_RIGHT_MIN and (dR - dL) >= D_CONTRAST_MIN
               else "ATTRACT_TAKEOVER")
    J({"ev": "DISCRIMINATOR_VERDICT", "verdict": verdict,
       "d_right": dR, "d_left": dL,
       "thresholds": {"d_right_min": D_RIGHT_MIN,
                      "contrast_min": D_CONTRAST_MIN}})
    log(f"DISCRIMINATOR: {verdict} dR={dR} dL={dL}")
    return verdict, legs


def accept_phase(p, m, J, tag):
    outcome = {"result": "no_gameplay_seen", "walk": None,
               "verdict": None}
    restart_streak = 0
    # ---- W: zero-input watch ---------------------------------------
    for w in range(W_WATCH):
        p.core.run(150, set())
        s = t1.snap(m)
        tear, _ = teardown(m)
        J({"ev": "W", "step": w, "teardown": tear, "vm": vm_compact(m),
           **s})
        png(p, f"W{w}", tag)
        log(f"W{w}: px={s['px']} sec={s['sec']} score={s['score']} "
            f"tear={tear}")
        if t1.alive(m) and 60.0 < s["px"] < 4096.0:
            ok, moved, _ = right_probe(p, m, J, tag, f"W{w}")
            if ok:
                outcome["result"] = "gameplay_seen_W"
                break
        if (RESTART_PX_LO <= s["px"] <= RESTART_PX_HI
                and s["sec"][0] in (0xB, 0x0)):
            restart_streak += 1
            if restart_streak >= 2:
                J({"ev": "RESTART_NO_BANNER", "step": w, **s,
                   "vm": t2.read_vm(m)})
                outcome["result"] = "restart_expired"
                return outcome
        else:
            restart_streak = 0
    if outcome["result"].startswith("gameplay_seen"):
        wk = walk_forward(p, m, J, tag)
        outcome["walk"] = wk
        if wk.get("spawn") is not None:
            verdict, legs = discriminator(p, m, J, tag)
            outcome["verdict"] = verdict
            outcome["legs"] = legs
        return outcome
    # ---- S: the session-6 accept ladder ----------------------------
    for k in range(S_ROUNDS):
        p.core.run(12, {"START"})
        p.core.run(300, set())
        s = t1.snap(m)
        J({"ev": "S", "tap": k + 1, "vm": vm_compact(m), **s})
        png(p, f"S{k + 1}", tag)
        log(f"S{k + 1}: px={s['px']} sec={s['sec']} score={s['score']}")
        if t1.alive(m) and 60.0 < s["px"] < 4096.0:
            ok, moved, _ = right_probe(p, m, J, tag, f"S{k + 1}")
            if ok:
                outcome["result"] = f"gameplay_seen_S{k + 1}"
                wk = walk_forward(p, m, J, tag)
                outcome["walk"] = wk
                if wk.get("spawn") is not None:
                    verdict, legs = discriminator(p, m, J, tag)
                    outcome["verdict"] = verdict
                    outcome["legs"] = legs
                return outcome
        if (RESTART_PX_LO <= s["px"] <= RESTART_PX_HI
                and s["sec"][0] in (0xB, 0x0)):
            restart_streak += 1
            if restart_streak >= 2:
                J({"ev": "RESTART_NO_BANNER", "tap": k + 1, **s,
                   "vm": t2.read_vm(m)})
                outcome["result"] = "restart_expired"
                return outcome
        else:
            restart_streak = 0
    # ---- Q: quiet watch through the attract chain ------------------
    for q in range(8):
        p.core.run(300, set())
        s = t1.snap(m)
        J({"ev": "Q", "step": q, "vm": vm_compact(m), **s})
        png(p, f"Q{q}", tag)
        if m2_fingerprint(s):
            J({"ev": "M2_SPAWN_FINGERPRINT_ATTRACT", "step": q, **s,
               "vm": t2.read_vm(m),
               "note": "spawn-shaped world under the zero-input chain "
                       "(the R42 attract label expected)"})
            verdict, legs = discriminator(p, m, J, tag)
            outcome["result"] = "spawn_shaped_attract_chain"
            outcome["verdict"] = verdict
            outcome["legs"] = legs
            return outcome
        if t1.alive(m) and 60.0 < s["px"] < 4096.0:
            ok, moved, _ = right_probe(p, m, J, tag, f"Q{q}")
            if ok:
                outcome["result"] = f"gameplay_seen_Q{q}"
                wk = walk_forward(p, m, J, tag)
                outcome["walk"] = wk
                if wk.get("spawn") is not None:
                    verdict, legs = discriminator(p, m, J, tag)
                    outcome["verdict"] = verdict
                    outcome["legs"] = legs
                return outcome
    return outcome


def main():
    stage = (sys.argv[1] if len(sys.argv) > 1 else "1").strip()
    assert stage in ("1", "2", "3"), \
        "usage: r44t1_clean_resolve.py [1|2|3]"
    n = amend_ledger(
        f"BOOT stage-{stage}: "
        + ("boot -> restore issue5_m1_start -> CLEAN rebuild (DYNAMIC "
           "restart guard max_px>700-then-px<700 = honest abort; "
           "deaths=0 validity; frontier saves px>1200) -> gate "
           "aa_resolved>=1 AND px>700 -> r44_postkill -> exit"
           if stage == "1" else
           "boot -> restore r44_postkill (CLEAN, deaths=0) -> policy "
           "to the mission_end latch (900 bound, frontier saves) -> "
           "the session-6 accept chain -> the M2 input-delta "
           "discriminator -> report"
           if stage == "2" else
           "FALLBACK (b) PIVOT (disclosed: the deaths=0 premise was "
           "falsified by the deterministic 3/3 c86/87 armor-zone "
           "death; boots 3+4 reallocated per the corrected-filings "
           "precedent): boot -> restore r43_postkill (the on-disk "
           "TAINTED post-restart checkpoint-respawn posture - NOT a "
           "clean claim) -> policy to the mission_end latch (900 "
           "bound) with FRONTIER SAVES px>1200 (the boot-7 loss) -> "
           "accept chain + discriminator ONLY if latched (any verdict "
           "is post-restart-lineage evidence, not an interactive "
           "claim)"))
    if n > 4:
        raise SystemExit("BOOT CAP EXCEEDED (4)")
    os.makedirs(SCRATCH, exist_ok=True)
    os.makedirs(EVID, exist_ok=True)
    tag = time.strftime(f"r44b{n}_%H%M%S")
    stem = f"r44_boot{n}_s{stage}"
    tr_path = os.path.join(SCRATCH, f"{stem}.jsonl")
    jf = open(tr_path, "w")

    def J(ev):
        jf.write(json.dumps(ev, default=str) + "\n")
        jf.flush()

    J({"ev": "RUN_START",
       "commit": os.popen("git -C %s rev-parse HEAD" % _REPO).read().strip(),
       "stage": stage,
       "policy": ("stage1: clean rebuild from issue5_m1_start with the "
                  "dynamic restart guard + deaths=0 + frontier saves, "
                  "save r44_postkill"
                  if stage == "1" else
                  "stage2: restore r44_postkill -> policy to the "
                  "mission_end latch -> W/S accept ladder -> RIGHT "
                  "walk -> M2 input-delta discriminator"),
       "premise_note": "R43 negative: the INTERACTIVE M2 entry is NOT "
                       "claimable from a post-restart posture; the "
                       "clean deaths=0 resolve posture is the "
                       "requirement (the capsule hypothesis).  The "
                       "r43_postkill on disk IS the known tainted "
                       "(post-restart) posture - R44 never restores it.",
       "oracle": "walker words + verified score gains + alive 0x0EE518; "
                 "never +0x8E",
       "ts": time.strftime("%FT%TZ", time.gmtime())})
    restore_name = (ANCHOR if stage == "1"
                    else POSTKILL if stage == "2" else POSTKILL43)
    if stage == "2" and not os.path.exists(
            os.path.join("/home/z/my-project/emu/ws/states",
                         POSTKILL + ".state")):
        jf.close()
        raise SystemExit("r44_postkill MISSING - run stage 1 first "
                         "(never substitute a tainted posture)")
    if stage == "3" and not os.path.exists(
            os.path.join("/home/z/my-project/emu/ws/states",
                         POSTKILL43 + ".state")):
        jf.close()
        raise SystemExit("r43_postkill MISSING - fallback (b) needs "
                         "the on-disk tainted posture")
    p = boot_to_demo()
    m = p.mem
    p.load_state(restore_name)
    s0 = t1.snap(m)
    if not t1.alive(m):
        raise SystemExit(f"restore not alive: {s0}")
    J({"ev": "ANCHOR_RESTORED", "state": restore_name,
       "lineage": ("clean-anchor" if stage == "1" else
                   "clean-required" if stage == "2" else
                   "TAINTED (post-restart checkpoint-respawn; the R43 "
                   "negative applies to any claim)"),
       "vm": t2.read_vm(m), **s0})
    log(f"anchor restored px={s0['px']} score={s0['score']}")
    res = {}
    if stage == "1":
        g_out, g_c, g_deaths, _pol = policy_phase(p, m, J, tag,
                                                  REBUILD_CHUNKS,
                                                  "rebuild",
                                                  until_latch=False)
        res["rebuild"] = {"outcome": g_out, "c": g_c,
                          "deaths": g_deaths}
        res["outcome"] = ("postkill_saved_clean" if g_out ==
                          "resolved_clean"
                          else "rebuild_" + g_out)
    elif stage == "2":
        l_out, l_c, l_deaths, _pol = policy_phase(p, m, J, tag,
                                                  LATCH_CHUNKS, "latch",
                                                  until_latch=True)
        res["latch"] = {"outcome": l_out, "c": l_c, "deaths": l_deaths}
        if l_out == "latched":
            acc = accept_phase(p, m, J, tag)
            res["accept"] = acc
        else:
            res["outcome"] = f"latch_{l_out}"
    else:
        l_out, l_c, l_deaths, _pol = policy_phase(p, m, J, tag,
                                                  LATCH_CHUNKS, "latch",
                                                  until_latch=True)
        res["latch"] = {"outcome": l_out, "c": l_c, "deaths": l_deaths,
                        "lineage": "tainted (r43_postkill)"}
        if l_out == "latched":
            acc = accept_phase(p, m, J, tag)
            res["accept"] = acc
            res["accept"]["claim_label"] = (
                "POST_RESTART_LINEAGE - NOT an interactive claim "
                "(the R43 negative)")
        else:
            res["outcome"] = f"latch_{l_out}_frontiers_saved"
    res["final"] = t1.snap(m)
    res["final_vm"] = t2.read_vm(m)
    with open(os.path.join(SCRATCH, f"{stem}_report.json"), "w") as f:
        json.dump({"schema": "ps1play.r44-boot/1",
                   "generated": time.strftime("%FT%TZ", time.gmtime()),
                   "commit": os.popen("git -C %s rev-parse HEAD"
                                      % _REPO).read().strip(),
                   "anchor": ANCHOR, "postkill": POSTKILL,
                   "run": res}, f, indent=1, default=str)
    jf.close()
    log(f"FIN: {res.get('outcome', res.get('accept', {}).get('result'))} "
        f"verdict={res.get('accept', {}).get('verdict')}")
    log(f"report -> scratch/r44/{stem}_report.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
