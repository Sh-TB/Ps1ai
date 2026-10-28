#!/usr/bin/env python3
"""r40t5_watch.py — R40 Task 5 (BOOT 5 of the disclosed cap 5, ledger
amended 4->5 BEFORE the run).

The post-kill full-table watch. Boot-4 killed the chopper in-policy
(3 verified hp_a4 connects) yet the D7 section did not release: 745
post-kill chunks of clamp_clear with NOTHING in the engage window
(near=None 741/779), no 0xC, rain ongoing, px drifting past the clamp
(1238), the progress word moving 0x80000000 -> 0xFFFFFFFF. The
boot-1..4 census recorded only the near-SELECTION — the remaining
queue blocker(s) (candidates: the wall mortarman st 0xE17C/0xE19C, an
off-window entity, a non-entity trigger) are unidentified.

Boot 5 = the patient kill again (same protocol; also re-tests the
boot-4 kill's reproducibility) + AFTER the chopper resolves:
  - every 10 chunks: the FULL entity table (slots 1-39: slot/x/f8e/
    a4/st/h) + the policy-visible scan_entities list + the section
    words + px/score/prog/php;
  - per-chunk census events gain the snap fields (px/php/sec/score)
    — the harness gap boot-4 exposed.

Success oracles unchanged: verified hp_a4 drops; CHOPPER_DEAD; the
section release; the banner predicate. +0x8E never in any oracle.
Checkpoint-restored diagnostics inside boot 5.
"""
from __future__ import annotations

import json
import os
import sys
import time

_REPO = "/home/z/my-project/ps1ai"
for _p in (_REPO, os.path.join(_REPO, "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _REPO + "/scripts")
        sys.path.insert(0, _REPO)

import r39t1_baseline as t1                       # noqa: E402
import ps1play.agent.combat as combat             # noqa: E402
import r40t1_census as c1                         # noqa: E402
from issue4_controller import boot_to_demo        # noqa: E402

SCRATCH = c1.SCRATCH
CKPT = c1.CKPT
CHUNKS = 1200                                     # the patient window
DUMP_EVERY = 10


def log(*a):
    print("[r40-t5]", *a, file=sys.stderr, flush=True)


def full_table(m, px):
    """Every live row of the entity table (the t1.census filter
    loosened: keep rows with a valid x even when f8e reads 0, marked
    f8e=0) — the release blocker must be visible HERE."""
    rows = []
    for s in range(1, 40):
        base = combat.TABLE + s * combat.STRIDE
        xw = int(m.u32(base + 0x78))
        if not xw:
            continue
        rows.append({"slot": s,
                     "x": round(xw / 65536.0, 1),
                     "f8e": int(m.u16(base + 0x8E)),
                     "a4": int(m.u16(base + 0xA4)),
                     "st": int(m.u16(base)),
                     "h": int(m.u16(base + 0x7E))})
    return rows


def run_watch_arm(p, m, J, tag, chunks_cap, tlog, continues=None,
                  settle=2):
    """The boot-1..4 census harness + the watch additions:
    (a) snap fields in every census event, (b) after the chopper
    resolves, a full-table dump every DUMP_EVERY chunks."""
    pol = combat.CombatPolicy(queue_priority=True)
    p.core.run(settle, set())
    s0 = t1.snap(m)
    J({"ev": "arm_start", "arm": tag, "snap": s0})
    deaths = 0
    outcome, end_c = None, None
    last_px, last_segs = None, None
    prev_score = int(m.u32(t1.A_SCORE))
    t0 = time.time()
    resolved_at = None
    dumps = 0
    for c in range(chunks_cap):
        s = t1.snap(m)
        if not t1.alive(m):
            deaths += 1
            J({"ev": "death", "arm": tag, "chunk": c, **s})
            if not t1.wait_alive(m, p, wait=20):
                if continues is not None:
                    continues[tag] = continues.get(tag, 0) + 1
                J({"ev": "CONTINUE_SCREEN", "arm": tag, "chunk": c,
                   "n": continues.get(tag, 0), **s})
                from run_mission1_legit import recover_v2
                if not recover_v2(p, log=log):
                    outcome, end_c = "death_no_respawn", c
                    break
                if not t1.wait_alive(m, p, wait=20):
                    outcome, end_c = "death_no_respawn", c
                    break
            last_px, last_segs = None, None
            continue
        if t1.px_of(m) > 5000.0:
            p.core.run(60, set())
            continue
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
        pre_sec = (int(m.u16(combat.SECTION_STATE)),
                   int(m.u16(combat.SECTION_FLAGS)))
        for x in segs:
            p.core.run(x["frames"], x["btns"] or set())
        post_sec = (int(m.u16(combat.SECTION_STATE)),
                    int(m.u16(combat.SECTION_FLAGS)))
        if pre_sec != post_sec:
            J({"ev": "sec_transition", "arm": tag, "chunk": c,
               "from": pre_sec, "to": post_sec, **t1.snap(m)})
        s2 = t1.snap(m)
        if s2["score"] != prev_score:
            J({"ev": "SCORE_EVENT", "arm": tag, "chunk": c,
               "mode": pol.mode, "from": prev_score, "to": s2["score"]})
            prev_score = s2["score"]
        cen2 = t1.census(m, t1.px_of(m))
        ch_fix = t1.chopper_of(cen2, t1.px_of(m))
        # census + snap (the boot-4 gap fixed)
        J({"ev": "census", "arm": tag, "c": c, "mode": pol.mode,
           "px": s2["px"], "php": s2["php"], "sec": s2["sec"],
           "score": s2["score"], "gren": s2["gren"],
           "prog": s2["prog"],
           **(pol.last_scan or {})})
        if resolved_at is not None and c % DUMP_EVERY == 0:
            # the post-kill watch: the FULL table + the policy scan
            J({"ev": "FULL_TABLE", "arm": tag, "chunk": c,
               "table": full_table(m, t1.px_of(m)),
               "scan": scan,
               "section_words": (int(m.u16(combat.SECTION_STATE)),
                                 int(m.u16(combat.SECTION_FLAGS))),
               "snap": s2})
            dumps += 1
        fr = t1.frames_of(segs)
        lob_frames = [i for i, b in enumerate(fr)
                      if "A" in b and "UP" in b]
        if pol.mode == "aa_kill" or lob_frames:
            tlog.check_hit(m, t1.px_of(m), cen2, c)
            if lob_frames:
                tlog.record_throw(
                    m, px, cen, c,
                    extra={"lob_frames_in_chunk": len(lob_frames),
                           "aa_t_start": pol._aa_t - len(fr),
                           "aa_t_end": pol._aa_t,
                           "gren_after": int(m.u8(t1.GRENADES)),
                           "gren0": gren0,
                           "mode": pol.mode})
        if pol.stats.get("aa_resolved", 0) >= 1 and resolved_at is None:
            resolved_at = c
            J({"ev": "CHOPPER_RESOLVED", "arm": tag, "chunk": c,
               "kill_connects": pol.stats.get("aa_kill_connect", 0),
               "connects": pol.stats.get("aa_connect", 0),
               "table": full_table(m, t1.px_of(m)),
               "scan": scan, "snap": s2})
            log(f"CHOPPER RESOLVED at c{c}: "
                f"connects={pol.stats.get('aa_connect', 0)} "
                f"kill={pol.stats.get('aa_kill_connect', 0)}")
        if s2["sec"][0] == 0xC and s2["px"] < 200.0 and t1.alive(m):
            outcome, end_c = "MISSION_BANNER", c
            break
        if t1.alive(m) and s2["px"] < 200.0 and c > 4 and \
                s2["sec"][0] in (0xB, 0x0):
            outcome, end_c = "banner_expired_restart", c
            J({"ev": "RESTART_SEEN", "arm": tag, "chunk": c, **s2})
            break
        if t1.alive(m) and s2["sec"][0] == 0xC and pol.mission_end:
            outcome, end_c = "mission_end_latched", c
            break
    else:
        outcome, end_c = "budget", chunks_cap - 1
    res = {"arm": tag, "outcome": outcome, "end_chunk": end_c,
           "deaths": deaths, "wall_s": round(time.time() - t0, 1),
           "throws": len(tlog.throws), "resolved_at": resolved_at,
           "full_table_dumps": dumps,
           "score_final": int(m.u32(t1.A_SCORE)),
           "pol_stats": {k: v for k, v in pol.stats.items() if v},
           "final": t1.snap(m)}
    J({"ev": "ARM_DONE", **res})
    log(f"{tag}: {outcome} c={end_c} throws={res['throws']} "
        f"resolved_at={resolved_at} score={res['score_final']}")
    return res


def main():
    n = c1.amend_ledger(
        "BOOT5: the patient kill + the post-resolve full-table watch "
        "(identify the remaining release blocker)",
        script="r40t5_watch.py")
    if n > 5:
        raise SystemExit("BOOT CAP EXCEEDED")
    tr_path = os.path.join(SCRATCH, "r40_boot5.jsonl")
    jf = open(tr_path, "w")

    def J(ev):
        jf.write(json.dumps(ev, default=str) + "\n")
        jf.flush()

    J({"ev": "RUN_START",
       "commit": os.popen("git -C %s rev-parse HEAD"
                          % _REPO).read().strip(),
       "policy": "R40 v3.1 (queue priority + arrival-band lead gate)",
       "protocol": "1 run x 1200 chunks + the post-resolve full-table "
                   "watch (every 10 chunks) + snap fields in census",
       "ts": time.strftime("%FT%TZ", time.gmtime())})

    p = boot_to_demo()
    m = p.mem
    p.load_state(CKPT)
    if not t1.alive(m):
        raise SystemExit("r38_ckpt not alive after restore")

    continues = {}
    tlog = t1.ThrowLog(J, "WATCH")
    res = run_watch_arm(p, m, J, "WATCH", CHUNKS, tlog,
                        continues=continues)
    res["hp_drops"] = tlog.hits
    res["throws"] = len(tlog.throws)

    with open(os.path.join(SCRATCH, "r40_boot5_report.json"),
              "w") as f:
        json.dump({"schema": "ps1play.r40-boot5/1",
                   "generated": time.strftime("%FT%TZ", time.gmtime()),
                   "commit": os.popen("git -C %s rev-parse HEAD"
                                      % _REPO).read().strip(),
                   "checkpoint": CKPT, "run": res}, f, indent=1,
                  default=str)
    jf.close()
    log("report -> scratch/r40/r40_boot5_report.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
