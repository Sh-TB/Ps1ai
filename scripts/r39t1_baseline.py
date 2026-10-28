#!/usr/bin/env python3
"""r39t1_baseline.py — R39 Task 1+2+3 (BOOT 1 of the disclosed cap 2).

Baseline reproduction + per-throw instrumentation + the cheapest
discriminating A/B for the ~1/10 aa connect rate.

Arms (one boot, checkpoint-restored diagnostics — labeled as such):
  BASE        : the SHIPPED policy from r38_ckpt, 300 x 15f chunks.
                Must reproduce R38 trialAA1 stats (aa_kill 56,
                aa_miss 10, aa_connect 1, restart ~c227) — if it does
                not, the R38 result is not reproducible and everything
                else stops until that is explained.
  DIAG-CHUNK  : the shipped policy from the in-run anchor r39_anchor
                (saved at the first aa_kill chunk with the chopper
                inside 160px), 2400f — measures the in-policy delivery
                connect rate with per-throw telemetry.
  DIAG-ATOMIC : the Session-3 chopper_kill.py J1 loop VERBATIM from the
                SAME anchor, 2400f — the proven atomic delivery (3f B,
                8f neutral, 8f UP+A+aim, 25f quiet, 30f rest alternate;
                aim fixed per throw at cycle start). Same-frame-budget
                connect rate vs DIAG-CHUNK isolates the DELIVERY
                MECHANISM (chunked interruptions / per-chunk aim
                recompute / rain-hop phase) from geometry.
  First atomic cycle is run FRAME-BY-FRAME (read-only telemetry: px,
  chopper x/h/st/a4, grenade count, candidate player-Y words) to give
  release-frame geometry and the chopper's motion model.

Success signals (Task 2): a VERIFIED connect = the correctly
identified chopper's hp_a4 drops (identity: st in 0xAA94/0xABDC,
airborne, a4>0). Score events are recorded but never attributed alone.
+0x8E is NEVER in any oracle (R38 rule).

All arms are DIAGNOSTIC (checkpoint-restored inside boot 1). No
fresh-boot gameplay claim is made from this script.
"""
from __future__ import annotations

import json
import os
import sys
import time

from PIL import Image                                     # noqa: E402

_REPO = "/home/z/my-project/ps1ai"
for _p in (_REPO, os.path.join(_REPO, "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from ps1play.telemetry import JsonlTrace                  # noqa: E402
import ps1play.agent.combat as combat                     # noqa: E402
from issue4_controller import boot_to_demo                # noqa: E402

SCRATCH = os.path.join(_REPO, "scratch", "r39")
LEDGER = os.path.join(SCRATCH, "boots_used.json")
CKPT = "r38_ckpt"
ANCHOR = "r39_anchor"
PLAYER_X = 0x0CA2E0
A_SCORE = 0x0EE318
GRENADES = 0x0EDCF4
PLAYER_HP = 0x0CA2F6          # indicator only (R38 contradiction rule)
A_FLAGS = 0x0EE518
CHOPPER_ST = combat.CHOPPER_ST

ARM_FRAMES = 2400             # matched diagnostic budget per arm
BASE_CHUNKS = 300             # x15f; R38 restart was at c227


def log(*a):
    print("[r39]", *a, file=sys.stderr, flush=True)


def make_ledger():
    os.makedirs(SCRATCH, exist_ok=True)
    if not os.path.exists(LEDGER):
        with open(LEDGER, "w") as f:
            json.dump({
                "cap": 2,
                "count": 0,
                "disclosed_before_first_boot": True,
                "budget_plan": {
                    "boot_1": "baseline reproduction + in-policy vs "
                              "atomic delivery diagnostics from one "
                              "in-run anchor (checkpoint-restored, "
                              "labeled diagnostic)",
                    "boot_2": "treatment verification of the "
                              "positioning/delivery sub-rule under the "
                              "same encounter conditions"},
                "amendments": [],
                "log": []}, f, indent=1)


def amend_ledger(reason, script="r39t1_baseline.py"):
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


def px_of(m):
    return int(m.u32(PLAYER_X)) / 65536.0


def alive(m):
    return (int(m.u32(A_FLAGS)) & 0xFF) == 0xFF and px_of(m) != 0.0


def snap(m):
    return {"px": round(px_of(m), 1), "score": int(m.u32(A_SCORE)),
            "gren": int(m.u8(GRENADES)), "php": int(m.u16(PLAYER_HP)),
            "sec": (int(m.u16(combat.SECTION_STATE)),
                    int(m.u16(combat.SECTION_FLAGS))),
            "prog": int.from_bytes(
                m.ram[0xEB5D4:0xEB5D8].tobytes(), "little")}


def census(m, px):
    out = []
    for s in range(1, 40):
        base = combat.TABLE + s * combat.STRIDE
        xw = int(m.u32(base + 0x78))
        if not xw:
            continue
        f8e = int(m.u16(base + 0x8E))
        if not f8e:
            continue
        out.append({"slot": s, "x": round(xw / 65536.0, 1), "f8e": f8e,
                    "a4": int(m.u16(base + 0xA4)),
                    "st": int(m.u16(base)),
                    "h": int(m.u16(base + 0x7E))})
    return out


def chopper_of(cen, px):
    """Closest live chopper row from an unfiltered census."""
    rows = [e for e in cen if e["st"] in CHOPPER_ST and e["h"] > 64
            and e["a4"] > 0]
    if not rows:
        return None
    return min(rows, key=lambda e: abs(e["x"] - px))


class ThrowLog:
    """Per-throw event records (R39 Task 2), shared by all arms."""

    def __init__(self, J, arm):
        self.J, self.arm = J, arm
        self.throws = []
        self.last_a4 = None
        self.hits = 0

    def record_throw(self, m, px, cen, cycle, extra=None):
        ch = chopper_of(cen, px)
        rec = {"ev": "THROW", "arm": self.arm, "cycle": cycle,
               "px": round(px, 1),
               "dx": None if ch is None else round(ch["x"] - px, 1),
               "ch": ch, "gren": int(m.u8(GRENADES)),
               **snap(m), **(extra or {})}
        self.throws.append(rec)
        self.J(rec)

    def check_hit(self, m, px, cen, cycle):
        ch = chopper_of(cen, px)
        a4 = None if ch is None else ch["a4"]
        hit = None
        if self.last_a4 is not None and a4 is not None and a4 < self.last_a4:
            hit = {"from": self.last_a4, "to": a4}
            self.hits += 1
            self.J({"ev": "HP_DROP", "arm": self.arm, "cycle": cycle,
                    "from": self.last_a4, "to": a4, "ch": ch, **snap(m)})
        if a4 is not None:
            self.last_a4 = a4
        return hit, ch


def frames_of(segs):
    out = []
    for s in segs:
        out.extend([frozenset(s["btns"] or set())] * s["frames"])
    return out


def wait_alive(m, p, wait=60):
    for _ in range(wait):
        p.core.run(30, set())
        if alive(m):
            return True
    return False


def run_policy_arm(p, m, J, tag, chunks_cap, tlog, anchor_state=None,
                   settle=2, continues=None):
    """The shipped policy in 15f micro-chunks with per-throw telemetry.
    Returns the arm report dict.

    continues: optional dict to report the count of continue-screen
    recoveries (the recover_v2 START tap - the established issue-4
    mechanism; a legal gameplay input, counted and disclosed, never
    silently merged into 'deaths')."""
    pol = combat.CombatPolicy()
    p.core.run(settle, set())
    s0 = snap(m)
    J({"ev": "arm_start", "arm": tag, "snap": s0})
    deaths = 0
    outcome, end_c = None, None
    last_px, last_segs = None, None
    prev_score = int(m.u32(A_SCORE))
    t0 = time.time()
    # BASE (anchor_state None) saves the anchor once at the first
    # qualifying aa_kill chunk boundary — WITHOUT any extra settle
    # frame, so BASE's own trajectory is not perturbed.
    anchor_saved = anchor_state is not None
    score_events = []
    for c in range(chunks_cap):
        s = snap(m)
        if not alive(m):
            deaths += 1
            J({"ev": "death", "arm": tag, "chunk": c, **s})
            # R38 protocol: wait out the respawn and continue
            if not wait_alive(m, p, wait=20):
                # no auto-respawn: the mission continues via the
                # game's own continue screen (recover_v2 START tap -
                # the established issue-4 mechanism; counted and
                # disclosed, never silently merged into deaths)
                if continues is not None:
                    continues[tag] = continues.get(tag, 0) + 1
                n_cont = (continues or {}).get(tag, 0)
                J({"ev": "CONTINUE_SCREEN", "arm": tag, "chunk": c,
                   "n": n_cont, **snap(m)})
                from run_mission1_legit import recover_v2
                if not recover_v2(p, log=log):
                    outcome, end_c = "death_no_respawn", c
                    break
                if not wait_alive(m, p, wait=20):
                    outcome, end_c = "death_no_respawn", c
                    break
            last_px, last_segs = None, None
            continue
        if px_of(m) > 5000.0:
            p.core.run(60, set())
            continue
        px_early = px_of(m)
        sec = combat.scan_section(m)
        pol.observe_section(sec, px_now=px_early)
        px = px_of(m)
        advanced = 0.0 if last_px is None else px - last_px
        intent = any("RIGHT" in (x.get("btns") or set())
                     for x in (last_segs or []))
        pol.observe(px, advanced, intent)
        cen = census(m, px)
        # scan for the policy (same filter as the shipped sensor)
        scan = combat.scan_entities(m, px=px)
        gren0 = int(m.u8(GRENADES))
        segs = pol.decide(15, px, scan, grenades=gren0,
                          hp=int(m.u16(PLAYER_HP)))
        last_px, last_segs = px, segs
        pre_sec = (int(m.u16(combat.SECTION_STATE)),
                   int(m.u16(combat.SECTION_FLAGS)))
        for x in segs:
            p.core.run(x["frames"], x["btns"] or set())
        post_sec = (int(m.u16(combat.SECTION_STATE)),
                    int(m.u16(combat.SECTION_FLAGS)))
        if pre_sec != post_sec:
            J({"ev": "sec_transition", "arm": tag, "chunk": c,
               "from": pre_sec, "to": post_sec, **snap(m)})
        s2 = snap(m)
        if s2["score"] != prev_score:
            score_events.append({"chunk": c, "from": prev_score,
                                 "to": s2["score"]})
            J({"ev": "SCORE_EVENT", "arm": tag, "chunk": c,
               "mode": pol.mode, "from": prev_score, "to": s2["score"]})
            prev_score = s2["score"]
        # per-chunk telemetry (mode/sec/px/score/gren/php + a periodic
        # chopper fix so the geometry is reconstructable offline)
        cen2 = census(m, px_of(m))
        ch_fix = chopper_of(cen2, px_of(m))
        J({"ev": "chunk", "arm": tag, "c": c, "mode": pol.mode,
           "sec": s2["sec"], "px": s2["px"], "score": s2["score"],
           "gren": s2["gren"], "php": s2["php"],
           "aa_plan": pol.aa_plan, "aa_aim": pol.aa_aim,
           "aa_t": pol._aa_t,
           "ch": None if ch_fix is None else
           {k: ch_fix[k] for k in ("slot", "x", "h", "st", "a4")},
           "dx": None if ch_fix is None or px_of(m) > 5000 else
           round(ch_fix["x"] - px_of(m), 1)})
        # per-throw telemetry: the lob frames happened in this chunk
        fr = frames_of(segs)
        lob_frames = [i for i, b in enumerate(fr)
                      if "A" in b and "UP" in b]
        if pol.mode == "aa_kill" or lob_frames:
            aims = [sorted(b & {"LEFT", "RIGHT"}) for i, b in
                    enumerate(fr) if i in lob_frames]
            tlog.check_hit(m, px_of(m), cen2, c)
            if lob_frames:
                tlog.record_throw(
                    m, px, cen, c,
                    extra={"lob_frames_in_chunk": len(lob_frames),
                           "lob_aims": aims,
                           "aa_t_start": pol._aa_t - len(fr),
                           "aa_t_end": pol._aa_t,
                           "gren_after": int(m.u8(GRENADES)),
                           "gren0": gren0,
                           "mode": pol.mode})
        # anchor: first aa_kill chunk with the chopper inside 160px
        if not anchor_saved and pol.mode == "aa_kill":
            ch = chopper_of(cen2, px_of(m))
            if ch is not None and abs(ch["x"] - px_of(m)) <= 160.0 \
                    and int(m.u8(GRENADES)) > 0:
                p.save_state(ANCHOR)
                anchor_saved = True
                J({"ev": "ANCHOR_SAVED", "arm": tag, "chunk": c,
                   "chopper": ch, **snap(m),
                   "census": cen2})
                log(f"ANCHOR saved at chunk {c}: chopper dx="
                    f"{ch['x'] - px_of(m):.1f} a4={ch['a4']}")
        if s2["sec"][0] == 0xC and s2["px"] < 200.0 and alive(m):
            outcome, end_c = "MISSION_BANNER", c
            break
        # R39 HARNESS FIX: the restart/banner checks require the
        # player to be ALIVE. Boot-4 (and every R38 "restart")
        # misreported a mid-chunk DEATH (px=0, sec [0,0]) as
        # "banner_expired_restart" - the death handler below never
        # ran and the whole trial series measured time-to-first-death
        # instead of the full campaign. A dead player here falls
        # through to the next iteration's alive() check, which waits
        # out the respawn and continues.
        if alive(m) and s2["px"] < 200.0 and c > 4 and \
                s2["sec"][0] in (0xB, 0x0):
            outcome, end_c = "banner_expired_restart", c
            J({"ev": "RESTART_SEEN", "arm": tag, "chunk": c, **s2})
            break
        if alive(m) and s2["sec"][0] == 0xC and pol.mission_end:
            outcome, end_c = "mission_end_latched", c
            break
    else:
        outcome, end_c = "budget", chunks_cap - 1
    res = {"arm": tag, "outcome": outcome, "end_chunk": end_c,
           "deaths": deaths, "wall_s": round(time.time() - t0, 1),
           "throws": len(tlog.throws), "score_events": score_events,
           "score_final": int(m.u32(A_SCORE)),
           "pol_stats": {k: v for k, v in pol.stats.items() if v},
           "final": snap(m)}
    J({"ev": "ARM_DONE", **res})
    log(f"{tag}: {outcome} c={end_c} throws={res['throws']} "
        f"score={res['score_final']}")
    return res


def run_atomic_arm(p, m, J, tlog, budget=ARM_FRAMES, frame_detail=True):
    """The Session-3 J1 delivery VERBATIM (chopper_kill.py arm J1):
    even cycles throw (3f B / 8f neutral / 8f UP+A+aim / 25f quiet),
    odd cycles rest 30f; aim fixed per throw at cycle start. No policy
    object involved."""
    p.core.run(2, set())
    s0 = snap(m)
    cen0 = census(m, px_of(m))
    ch0 = chopper_of(cen0, px_of(m))
    J({"ev": "arm_start", "arm": "DIAG-ATOMIC", "snap": s0,
       "chopper": ch0})
    log(f"DIAG-ATOMIC start: chopper={ch0} px={s0['px']} "
        f"gren={s0['gren']}")
    f = 0
    k = 0
    score0 = int(m.u32(A_SCORE))
    score_events = []
    prev_score = score0
    outcome = "budget"
    while f < budget:
        if not alive(m):
            J({"ev": "death", "arm": "DIAG-ATOMIC", "frame": f,
               **snap(m)})
            outcome = "death"
            break
        px = px_of(m)
        cen = census(m, px)
        ch = chopper_of(cen, px)
        if ch is None:
            J({"ev": "CHOPPER_GONE", "arm": "DIAG-ATOMIC", "frame": f,
               **snap(m), "census": cen})
            outcome = "chopper_gone"
            break
        tlog.check_hit(m, px, cen, k)
        gren0 = int(m.u8(GRENADES))
        if k % 2 == 0:
            d = "RIGHT" if ch["x"] >= px else "LEFT"
            if frame_detail and k == 0:
                # frame-by-frame telemetry across the whole first
                # throw cycle (44f): release-frame geometry + motion
                for btns in ([{"B"}] * 3 + [set()] * 8 +
                             [{"UP", "A", d}] * 8 + [set()] * 25):
                    p.core.run(1, btns)
                    f += 1
                    pxn = px_of(m)
                    cenn = census(m, pxn)
                    chn = chopper_of(cenn, pxn)
                    J({"ev": "FRAME", "arm": "DIAG-ATOMIC", "frame": f,
                       "btns": sorted(btns), "px": round(pxn, 1),
                       "py_u32_ca2e4": int(m.u32(0x0CA2E4)),
                       "py_u16_ca2e6": int(m.u16(0x0CA2E6)),
                       "ch": chn,
                       "dx": None if chn is None else
                       round(chn["x"] - pxn, 1),
                       "gren": int(m.u8(GRENADES))})
            else:
                p.core.run(3, {"B"})
                p.core.run(8, set())
                if gren0 > 0:
                    p.core.run(8, {"UP", "A", d})
                else:
                    p.core.run(8, set())
                p.core.run(25, set())
                f += 44
            tlog.record_throw(m, px, cen, k,
                              extra={"aim": d, "gren0": gren0})
        else:
            p.core.run(30, set())
            f += 30
        # score watch
        sc = int(m.u32(A_SCORE))
        if sc != prev_score:
            score_events.append({"cycle": k, "from": prev_score,
                                 "to": sc})
            J({"ev": "SCORE_EVENT", "arm": "DIAG-ATOMIC", "cycle": k,
               "from": prev_score, "to": sc})
            prev_score = sc
        k += 1
    fin = snap(m)
    cenf = census(m, px_of(m))
    chf = chopper_of(cenf, px_of(m))
    res = {"arm": "DIAG-ATOMIC", "outcome": outcome, "frames": f,
           "cycles": k, "throws": len(tlog.throws),
           "score_delta": int(m.u32(A_SCORE)) - score0,
           "score_events": score_events,
           "chopper_final": chf, "final": fin}
    J({"ev": "ARM_DONE", **res})
    log(f"DIAG-ATOMIC: {outcome} cycles={k} throws={res['throws']} "
        f"dScore={res['score_delta']}")
    return res


def main():
    make_ledger()
    n = amend_ledger("BOOT1: baseline reproduction + delivery A/B "
                     "diagnostics (BASE from r38_ckpt; DIAG-CHUNK and "
                     "DIAG-ATOMIC from in-run anchor r39_anchor)")
    if n > 2:
        raise SystemExit("BOOT CAP EXCEEDED")
    tr_path = os.path.join(SCRATCH, "r39_boot1.jsonl")
    jf = open(tr_path, "w")

    def J(ev):
        jf.write(json.dumps(ev, default=str) + "\n")
        jf.flush()

    J({"ev": "RUN_START", "commit": os.popen(
        "git -C %s rev-parse HEAD" % _REPO).read().strip(),
       "disc_sha256": "45cde149878fe945d0219fd0f61ca09856aee66bdcc9119d"
                      "e21c0583f1d0667d",
       "ts": time.strftime("%FT%TZ", time.gmtime())})

    p = boot_to_demo()
    m = p.mem
    p.load_state(CKPT)
    if not alive(m):
        raise SystemExit("r38_ckpt not alive after restore")
    J({"ev": "CKPT_RESTORED", **snap(m)})

    # ---- Arm 1: BASE (shipped policy, reproduction) ----
    tlog_base = ThrowLog(J, "BASE")
    base = run_policy_arm(p, m, J, "BASE", BASE_CHUNKS, tlog_base)
    if base["pol_stats"].get("aa_connect", 0) != 1 or \
            base["pol_stats"].get("aa_miss", 0) != 10:
        log("WARNING: BASE stats differ from R38 trialAA1 "
            "(aa_kill 56 / aa_miss 10 / aa_connect 1) - reproduction "
            "discrepancy, report before proceeding")

    # ---- Arms 2+3: matched delivery A/B from the anchor ----
    base_stats = base["pol_stats"]
    rep = {"schema": "ps1play.r39-boot1/1",
           "generated": time.strftime("%FT%TZ", time.gmtime()),
           "commit": os.popen("git -C %s rev-parse HEAD"
                              % _REPO).read().strip(),
           "checkpoint": CKPT, "anchor": ANCHOR,
           "base": base, "arms": {}}
    anchor_path = os.path.join("/home/z/my-project/emu/ws/states",
                               ANCHOR + ".state")
    if not os.path.exists(anchor_path):
        raise SystemExit("anchor was never saved - no qualifying "
                         "aa_kill window in BASE; report BLOCKED")

    # DIAG-CHUNK: shipped policy from the anchor
    p.load_state(ANCHOR)
    if not alive(m):
        raise SystemExit("anchor not alive")
    tlog_chunk = ThrowLog(J, "DIAG-CHUNK")
    rep["arms"]["DIAG-CHUNK"] = run_policy_arm(
        p, m, J, "DIAG-CHUNK", ARM_FRAMES // 15, tlog_chunk,
        anchor_state=ANCHOR)

    # DIAG-ATOMIC: the proven script delivery from the SAME anchor
    p.load_state(ANCHOR)
    if not alive(m):
        raise SystemExit("anchor not alive")
    tlog_atom = ThrowLog(J, "DIAG-ATOMIC")
    rep["arms"]["DIAG-ATOMIC"] = run_atomic_arm(p, m, J, tlog_atom)

    # ---- connect-rate comparison (verified hp_a4 drops per arm) ----
    rep["arms"]["DIAG-CHUNK"]["hp_drops"] = tlog_chunk.hits
    rep["arms"]["DIAG-ATOMIC"]["hp_drops"] = tlog_atom.hits
    rep["comparison"] = {
        "base_aa": {k: base_stats.get(k, 0)
                    for k in ("aa_kill", "aa_miss", "aa_connect",
                              "aa_bail")},
        "chunk_throws": rep["arms"]["DIAG-CHUNK"]["throws"],
        "chunk_hp_drops": tlog_chunk.hits,
        "atomic_throws": rep["arms"]["DIAG-ATOMIC"]["throws"],
        "atomic_hp_drops": tlog_atom.hits}
    J({"ev": "COMPARISON", **rep["comparison"]})

    with open(os.path.join(SCRATCH, "r39_boot1_report.json"), "w") as f:
        json.dump(rep, f, indent=1, default=str)
    jf.close()
    log("report -> scratch/r39/r39_boot1_report.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
