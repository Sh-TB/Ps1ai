#!/usr/bin/env python3
"""r43t1_accept.py — R43 BOOT 1 (the 60% track, Issues #5/#9/#10).

The capsule lever (R42 close-out): the INTERACTIVE M2 entry is claimable
from the mission_end latch — at the teardown/tally accept with the
session-6 recipe (ONE disclosed START tap, then the endzone RIGHT walk
through the MSX-logo transition); the demo discriminator is the
input-delta, not the score alone.

PREMISE STALENESS (disclosed, same class as the R42 boot-1 lesson and
the documented mspsx_lic rollback): the R42 savestates r38_ckpt and
r42_postkill are ABSENT from emu/ws/states/ (only Oct-20 states
survived).  Boot 1 therefore rebuilds the posture from the surviving
session-5-era anchor `issue5_m1_start` (M1 gameplay start, px ~26) with
the SHIPPED policy — the session-6-proven full-mission chain — saves
r43_postkill at the resolve gate, and continues the policy to the
mission_end latch in the same boot.

Phases after the latch (the accept chain):
  W  zero-input watch windows (150f x6) — record prebanner/teardown
  S  the session-6 accept ladder: 12f START taps + 300f quiet x8
  P  the RIGHT ownership probe (60f; moved > 8 px = a live world)
  M  walk_forward: 120 x 30f RIGHT with anomaly pauses (session-6)
  D  the discriminator at the M2 spawn fingerprint: signed input-delta
     legs ZERO 60f / RIGHT 90f / LEFT 60f — the M2 entry is
     INTERACTIVE_M2_ENTRY only if the legs show a signed runner
     response (dR >= 30 px and dR - dL >= 60 px); unresponsive legs
     against the recorded R42 attract trajectory = ATTRACT_TAKEOVER.

Oracle unchanged: walker words + verified score gains + the alive word
0x0EE518; never +0x8E in any oracle.  Every input after the latch is a
DISCLOSED scripted probe (the S taps / the P+M walk / the D legs);
restart and death sensors are the hardened R42 classifiers; deaths and
continue-rescues are counted separately.
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

SCRATCH = os.path.join(_REPO, "scratch", "r43")
PNGDIR = os.path.join(SCRATCH, "pngs")
LEDGER = os.path.join(SCRATCH, "boots_used.json")
EVID = os.path.join(_REPO, "data", "games", "SLUS-01212",
                    "truck_evidence", "r43")

ANCHOR = "issue5_m1_start"      # session-5-era M1 start (px ~26)
POSTKILL = "r43_postkill"       # saved at the resolve gate this boot

REBUILD_CHUNKS = 1200           # r42t1 bound
LATCH_CHUNKS = 900              # covers a restart-posture full replay
WALL_GUARD_S = 9.0 * 60

W_WATCH = 6                     # 150f zero-input windows
S_ROUNDS = 8                    # 12f START + 300f quiet each
M_CHUNKS = 120                  # 30f RIGHT each (session-6 walk)

# the M2 spawn fingerprint (train_vocab_17d: px 74.6/php 74/gren 10/
# score 0; R42 attract chain showed px 74.0/php 74 — fingerprint alone
# is NOT the claim, the input-delta legs are)
M2_PX = (70.0, 80.0)
M2_PHP = (70.0, 80.0)
M2_GREN_MIN = 9
M2_SCORE_MAX = 200

# discriminator thresholds (free-walk 1.17-1.31 px/f, train net 0.785)
D_RIGHT_MIN = 30.0
D_CONTRAST_MIN = 60.0

RESTART_PX_LO, RESTART_PX_HI = 20.0, 60.0


def log(*a):
    print("[r43-t1]", *a, file=sys.stderr, flush=True)


def amend_ledger(reason, script="r43t1_accept.py"):
    os.makedirs(SCRATCH, exist_ok=True)
    if not os.path.exists(LEDGER):
        with open(LEDGER, "w") as f:
            json.dump({"cap": 2, "count": 0, "log": [], "note":
                       "premise staleness DISCLOSED: r38_ckpt and "
                       "r42_postkill absent (filesystem rollback; only "
                       "Oct-20 states survived) -> boot 1 rebuilds from "
                       "the session-5 anchor issue5_m1_start with the "
                       "shipped policy, saves r43_postkill at the gate, "
                       "then the accept chain; boot 2 = conditional "
                       "retry or the 0x4054 HP-word secondary"},
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


def policy_phase(p, m, J, tag, cap, phase, until_latch):
    """The shipped policy until the resolve gate (until_latch=False) or
    the mission_end latch (until_latch=True).  Returns (outcome, c,
    deaths).

    The px<700 restart-leak detector is DEPTH-CONDITIONAL: it is only
    meaningful from a deep posture (the r38_ckpt-era anchors sat at
    px 992+).  From a mission-START anchor (px ~26) px<700 is the
    NORMAL walk to the wave zone - the absolute guard misfires there
    (the double-filing lesson: entries 1+2 both died at c3 from the
    verbatim-copied r42t1 guard).  The guard arms only when the phase
    opens deep (px > 700)."""
    pol = combat.CombatPolicy(queue_priority=True)
    p.core.run(2, set())
    deep = t1.px_of(m) > 700.0
    J({"ev": "PHASE_START", "phase": phase, "deep_anchor": deep,
       "snap": t1.snap(m), "vm": t2.read_vm(m)})
    t0 = time.time()
    last_px, last_segs = None, None
    prev_score = int(m.u32(t1.A_SCORE))
    deaths = 0
    for c in range(cap):
        if time.time() - t0 > WALL_GUARD_S:
            return "wall_guard", c, deaths, pol
        if not t1.alive(m):
            deaths += 1
            J({"ev": "death", "phase": phase, "chunk": c, **t1.snap(m)})
            if not t1.wait_alive(m, p, wait=20):
                from run_mission1_legit import recover_v2
                if not recover_v2(p, log=log) or \
                        not t1.wait_alive(m, p, wait=20):
                    return "death_no_respawn", c, deaths, pol
            last_px, last_segs = None, None
            continue
        if t1.px_of(m) > 5000.0:
            p.core.run(60, set())
            continue
        px0 = t1.px_of(m)
        if deep and px0 < 700.0 and c > 2:
            J({"ev": "RESTART_LEAK", "phase": phase, "chunk": c,
               "px": px0, **t1.snap(m)})
            return "restart_leak", c, deaths, pol
        px_early = t1.px_of(m)
        sec = combat.scan_section(m)
        pol.observe_section(sec, px_now=px_early)
        px = t1.px_of(m)
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
        # per-chunk stderr trail (the boot-4 village stall hunt): the
        # last line before any hang names the chunk + mode + segments
        print(f"[r43-trace] {phase} c={c} px={px:.0f} mode={pol.mode} "
              f"segs={[(x['frames'], sorted(x['btns'] or set())) for x in segs]}",
              file=sys.stderr, flush=True)
        for x in segs:
            p.core.run(x["frames"], x["btns"] or set())
            if not t1.alive(m):
                break
        s2 = t1.snap(m)
        if s2["score"] != prev_score:
            J({"ev": "SCORE_EVENT", "phase": phase, "chunk": c,
               "from": prev_score, "to": s2["score"]})
            prev_score = s2["score"]
        if c % 20 == 0:
            J({"ev": "PHASE_DUMP", "phase": phase, "chunk": c,
               "mode": pol.mode, "vm": vm_compact(m), **s2})
        if until_latch and pol.mission_end:
            J({"ev": "MISSION_END_LATCH", "phase": phase, "chunk": c,
               "stats": {k: v for k, v in pol.stats.items() if v},
               "vm": t2.read_vm(m), **s2})
            log(f"MISSION_END LATCHED c{c} px={s2['px']} "
                f"score={s2['score']}")
            return "latched", c, deaths, pol
        if not until_latch and (pol.mission_end or
                                (pol.stats.get("aa_resolved", 0) >= 1
                                 and t1.px_of(m) > 700.0)):
            # the depth condition is the boot-5 lesson: aa_resolved is
            # a POLICY stat that survives deaths/restarts - after a
            # mission restart (px back to ~24) the stale stat fired the
            # r42t1 gate verbatim and saved a RESTART posture as the
            # postkill.  The gate is only honest when the world is
            # actually deep (the aa zone px 912-1164).
            how = ("aa_resolved" if pol.stats.get("aa_resolved", 0) >= 1
                   else "mission_end_latch")
            p.save_state(POSTKILL)
            J({"ev": "RESOLVED", "phase": phase, "chunk": c, "how": how,
               "postkill_state": POSTKILL, "vm": t2.read_vm(m), **s2})
            log(f"RESOLVED ({how}) c{c} -> {POSTKILL} saved")
            return "resolved", c, deaths, pol
    return "budget", cap - 1, deaths, pol


def right_probe(p, m, J, tag, label, frames=60):
    """The session-6 ownership probe: hold RIGHT, require moved > 8."""
    s0 = t1.snap(m)
    p.core.run(frames, {"RIGHT"})
    s1 = t1.snap(m)
    moved = s1["px"] - s0["px"]
    J({"ev": "RIGHT_PROBE", "label": label, "from_px": s0["px"],
       "moved_px": round(moved, 1), **s1})
    png(p, f"{label}_right", tag)
    return moved > 8.0 and t1.alive(m), moved, s1


def walk_forward(p, m, J, tag):
    """Phase M — the session-6 walk: 120 x 30f RIGHT with anomaly
    pauses; fingerprint-watch the M2 spawn; stop at the spawn."""
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
    """The signed input-delta legs at the M2 spawn: ZERO 60f / RIGHT
    90f / LEFT 60f.  INTERACTIVE iff dR >= 30 and dR - dL >= 60."""
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
    """W watch -> S ladder -> P probe -> M walk -> D discriminator."""
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
        # the hardened restart classifier
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
    assert stage in ("1", "2"), "usage: r43t1_accept.py [1|2]"
    n = amend_ledger(
        f"BOOT stage-{stage} (two-stage split: each stage fits one "
        f"foreground window; the cross-process savestate restore is "
        f"the R42-proven pattern): "
        + ("boot -> premise-staleness rebuild from issue5_m1_start "
           "(depth-conditional gate: aa_resolved>=1 AND px>700 - the "
           "boot-5 stale-stat-restart lesson) -> save r43_postkill "
           "-> exit"
           if stage == "1" else
           "boot -> restore r43_postkill -> policy to the mission_end "
           "latch (900-chunk bound) -> the session-6 accept chain -> "
           "the M2 input-delta discriminator -> report"))
    if n > 7:
        raise SystemExit("BOOT CAP EXCEEDED")
    os.makedirs(SCRATCH, exist_ok=True)
    os.makedirs(EVID, exist_ok=True)
    tag = time.strftime(f"r43b{n}_%H%M%S")
    stem = f"r43_boot{n}_s{stage}"
    tr_path = os.path.join(SCRATCH, f"{stem}.jsonl")
    jf = open(tr_path, "w")

    def J(ev):
        jf.write(json.dumps(ev, default=str) + "\n")
        jf.flush()

    J({"ev": "RUN_START",
       "commit": os.popen("git -C %s rev-parse HEAD" % _REPO).read().strip(),
       "stage": stage,
       "policy": ("stage1: premise-staleness rebuild from "
                  "issue5_m1_start, depth-conditional resolve gate, "
                  "save r43_postkill"
                  if stage == "1" else
                  "stage2: restore r43_postkill -> policy to the "
                  "mission_end latch -> W/S accept ladder -> RIGHT "
                  "walk -> M2 input-delta discriminator"),
       "premise_note": "r38_ckpt and r42_postkill ABSENT (filesystem "
                       "rollback, only Oct-20 states survived); anchor "
                       "issue5_m1_start = session-5-era M1 start px~26; "
                       "entries 1+2 double-filing disclosed in the "
                       "ledger (deep-posture guard misfire at c3)",
       "oracle": "walker words + verified score gains + alive 0x0EE518; "
                 "never +0x8E",
       "ts": time.strftime("%FT%TZ", time.gmtime())})
    p = boot_to_demo()
    m = p.mem
    p.load_state(ANCHOR if stage == "1" else POSTKILL)
    s0 = t1.snap(m)
    if not t1.alive(m):
        raise SystemExit(f"restore not alive: {s0}")
    J({"ev": "ANCHOR_RESTORED", "state": ANCHOR if stage == "1"
       else POSTKILL, "vm": t2.read_vm(m), **s0})
    log(f"anchor restored px={s0['px']} score={s0['score']}")
    res = {}
    if stage == "1":
        g_out, g_c, g_deaths, _pol = policy_phase(p, m, J, tag,
                                                  REBUILD_CHUNKS,
                                                  "rebuild",
                                                  until_latch=False)
        res["rebuild"] = {"outcome": g_out, "c": g_c,
                          "deaths": g_deaths}
        if g_out != "resolved":
            res["outcome"] = f"rebuild_{g_out}"
        else:
            res["outcome"] = "postkill_saved"
    else:
        l_out, l_c, l_deaths, _pol = policy_phase(p, m, J, tag,
                                                  LATCH_CHUNKS, "latch",
                                                  until_latch=True)
        res["latch"] = {"outcome": l_out, "c": l_c, "deaths": l_deaths}
        if l_out == "latched":
            acc = accept_phase(p, m, J, tag)
            res["accept"] = acc
        else:
            res["outcome"] = f"latch_{l_out}"
    res["final"] = t1.snap(m)
    res["final_vm"] = t2.read_vm(m)
    with open(os.path.join(SCRATCH, f"{stem}_report.json"), "w") as f:
        json.dump({"schema": "ps1play.r43-boot/1",
                   "generated": time.strftime("%FT%TZ", time.gmtime()),
                   "commit": os.popen("git -C %s rev-parse HEAD"
                                      % _REPO).read().strip(),
                   "anchor": ANCHOR, "postkill": POSTKILL,
                   "run": res}, f, indent=1, default=str)
    jf.close()
    log(f"FIN: {res.get('outcome', res.get('accept', {}).get('result'))} "
        f"verdict={res.get('accept', {}).get('verdict')}")
    log(f"report -> scratch/r43/{stem}_report.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
