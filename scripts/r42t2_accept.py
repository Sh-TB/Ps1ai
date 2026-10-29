#!/usr/bin/env python3
"""r42t2_accept.py — R42 BOOT 2/2 (the 60% track, Issue #5).

Boot-1 lesson (recorded): the resolve gate `aa_resolved` was PREMATURE —
from that posture 24000f of zero input produced NO banner and NO restart
(the end sequence is not an idle timer; the section-entity queue still
held the 0x4054 soft soldiers at x 1150-1450).  The resolved posture the
capsule means is the mission_end LATCH posture.

Boot 2 therefore: restore r42_postkill (saved at boot-1's aa-resolve,
px 1025, score 13630) -> run the SHIPPED policy (bounded 400 chunks,
hardened sensors) UNTIL pol.mission_end latches (the prebanner (0,8)+
d7_zone signature or the 0xC x2 confirm) -> then the HARD hold (the
harness emits p.core.run(n, set()) and never consults the policy again)
with the persist-confirm banner classifier (4 consecutive chunks of
0xC — the session-4 transient dies inside one chunk; the px window is
dropped in favour of persistence) and the 2-chunk-persistent restart
classifier.  The R42 question is answered at the banner boundary:
  hold survives the banner -> mission-2 load / clean select = the D7
  blocker CLOSED as bypassed-by-mission-end;
  countdown expires into the M1 restart with ZERO inputs = the restart
  is the countdown's natural expiry (hypothesis CONTRADICTED) and the
  known-good accept (session-6: ONE START tap) becomes the lever.

Oracle unchanged (banner predicate + walker words; never +0x8E).
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
import r42t1_hold as t1h                          # noqa: E402
from issue4_controller import boot_to_demo        # noqa: E402

SCRATCH = t1h.SCRATCH
LEDGER = t1h.LEDGER
EVID = t1h.EVID
POSTKILL = t1h.POSTKILL

LATCH_CHUNKS = 400            # bounded policy phase (15f chunks)
BANNER_CONFIRM_CHUNKS = 4     # 60f of 0xC = banner (transient-safe)
HOLD_CHUNKS = t1h.HOLD_CHUNKS
WALL_GUARD_S = t1h.WALL_GUARD_S


def log(*a):
    print("[r42-t2]", *a, file=sys.stderr, flush=True)


def vm_compact(m):
    return t1h.vm_compact(m)


def latch_phase(p, m, J, tag):
    """Shipped policy from r42_postkill until the mission_end latch."""
    pol = combat.CombatPolicy(queue_priority=True)
    p.core.run(2, set())
    J({"ev": "LATCH_PHASE_START", "snap": t1.snap(m), "vm": t2.read_vm(m)})
    t0 = time.time()
    last_px, last_segs = None, None
    prev_score = int(m.u32(t1.A_SCORE))
    deaths = 0
    for c in range(LATCH_CHUNKS):
        if time.time() - t0 > WALL_GUARD_S:
            return {"outcome": "wall_guard", "c": c}
        if not t1.alive(m):
            deaths += 1
            J({"ev": "death", "phase": "latch", "chunk": c, **t1.snap(m)})
            if not t1.wait_alive(m, p, wait=20):
                from run_mission1_legit import recover_v2
                if not recover_v2(p, log=log) or \
                        not t1.wait_alive(m, p, wait=20):
                    return {"outcome": "death_no_respawn", "c": c,
                            "deaths": deaths}
            last_px, last_segs = None, None
            continue
        if t1.px_of(m) > 5000.0:
            p.core.run(60, set())
            continue
        px0 = t1.px_of(m)
        if px0 < 700.0 and c > 2:
            J({"ev": "RESTART_LEAK", "phase": "latch", "chunk": c,
               "px": px0, **t1.snap(m)})
            return {"outcome": "restart_leak", "c": c, "deaths": deaths}
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
        for x in segs:
            p.core.run(x["frames"], x["btns"] or set())
            if not t1.alive(m):
                break
        s2 = t1.snap(m)
        if s2["score"] != prev_score:
            J({"ev": "SCORE_EVENT", "phase": "latch", "chunk": c,
               "from": prev_score, "to": s2["score"]})
            prev_score = s2["score"]
        if c % 20 == 0:
            J({"ev": "LATCH_DUMP", "chunk": c, "mode": pol.mode,
               "vm": vm_compact(m), **s2})
        if pol.mission_end:
            J({"ev": "MISSION_END_LATCH", "chunk": c,
               "stats": {k: v for k, v in pol.stats.items() if v},
               "vm": t2.read_vm(m), **s2})
            log(f"MISSION_END LATCHED c{c} px={s2['px']} "
                f"sec={s2['sec']} score={s2['score']}")
            return {"outcome": "latched", "c": c, "deaths": deaths,
                    "stats": {k: v for k, v in pol.stats.items() if v}}
    return {"outcome": "budget_latch", "c": LATCH_CHUNKS - 1,
            "deaths": deaths}


def hold_phase(p, m, J, tag, latch_c):
    """The HARD hold from the latch — persist-confirm banner classifier,
    2-chunk restart classifier, teardown chain tracking."""
    t0 = time.time()
    banner_c = None
    c_streak = 0
    tear_streak = 0
    post_world_c = None
    last_teardown = False
    restart_streak = 0
    hold_c = 0
    prev_vm = None
    for c in range(HOLD_CHUNKS):
        if time.time() - t0 > WALL_GUARD_S:
            return {"outcome": "hold_wall_guard", "end_c": c,
                    "banner_c": banner_c, "chunks": hold_c}
        s = t1.snap(m)
        vm = vm_compact(m)
        full_vm = (c % 10 == 0) or (vm != prev_vm)
        J({"ev": "HOLD", "chunk": c, **s, "vm": vm,
           **({"vm_full": t2.read_vm(m)} if full_vm else {}),
           "tear_streak": tear_streak, "banner": banner_c is not None})
        prev_vm = vm
        hold_c = c
        tear = s["px"] == 0.0 and s["php"] == 0
        if tear:
            tear_streak += 1
            if not last_teardown:
                J({"ev": "TEARDOWN_BEGIN", "chunk": c, **s,
                   "vm": t2.read_vm(m)})
            last_teardown = tear
            p.core.run(15, set())
            continue
        if last_teardown:
            J({"ev": "TEARDOWN_END", "chunk": c, "streak": tear_streak,
               **s, "vm": t2.read_vm(m)})
            last_teardown = False
            if banner_c is not None and post_world_c is None:
                post_world_c = c
                t1h.png(p, "post_banner_world", tag)
                J({"ev": "POST_BANNER_WORLD", "chunk": c, **s,
                   "vm": t2.read_vm(m)})
        if not t1.alive(m):
            J({"ev": "HOLD_NOT_ALIVE", "chunk": c, **s})
            p.core.run(15, set())
            continue
        # ---- banner: 0xC persisting BANNER_CONFIRM_CHUNKS chunks ----
        if s["sec"][0] == 0xC:
            c_streak += 1
            if banner_c is None and c_streak >= BANNER_CONFIRM_CHUNKS:
                banner_c = c
                t1h.png(p, "mission_banner", tag)
                J({"ev": "BANNER", "chunk": c, **s, "vm": t2.read_vm(m),
                   "latch_chunk": latch_c})
                log(f"BANNER c{c} px={s['px']} score={s['score']}")
        else:
            if c_streak and banner_c is None:
                J({"ev": "BANNER_CANDIDATE_LOST", "chunk": c, **s,
                   "streak": c_streak})
            c_streak = 0
        # ---- restart classifier (2-chunk persistence) ---------------
        if 20.0 <= s["px"] <= 60.0 and s["sec"][0] in (0xB, 0x0):
            restart_streak += 1
            if restart_streak == 1:
                J({"ev": "RESTART_CANDIDATE", "chunk": c, **s})
            elif restart_streak >= 2:
                ev = ("BANNER_EXPIRED_RESTART" if banner_c is not None
                      else "RESTART_NO_BANNER")
                t1h.png(p, "restart", tag)
                J({"ev": ev, "chunk": c, **s, "vm": t2.read_vm(m),
                   "banner_c": banner_c})
                log(f"{ev} c{c} px={s['px']} sec={s['sec']}")
                return {"outcome": "restart_expired", "end_c": c,
                        "banner_c": banner_c, "chunks": hold_c,
                        "final": s}
        else:
            restart_streak = 0
        # ---- the m2-load accept --------------------------------------
        if post_world_c is not None and \
                c - post_world_c >= t1h.POST_WORLD_CHUNKS:
            t1h.png(p, "m2_world_stable", tag)
            J({"ev": "M2_WORLD_STABLE", "chunk": c, **s,
               "vm": t2.read_vm(m), "post_world_c": post_world_c})
            return {"outcome": "m2_load", "end_c": c,
                    "banner_c": banner_c, "post_world_c": post_world_c,
                    "chunks": hold_c, "final": s}
        p.core.run(15, set())
    return {"outcome": "hold_budget", "end_c": hold_c,
            "banner_c": banner_c, "chunks": hold_c, "final": t1.snap(m)}


def main():
    n = t1h.amend_ledger(
        "BOOT2: from r42_postkill -> shipped policy to the mission_end "
        "latch -> HARD hold through prebanner/banner+2s+ (boot-1's "
        "aa_resolved gate was premature — recorded)")
    if n > 2:
        raise SystemExit("BOOT CAP EXCEEDED")
    os.makedirs(SCRATCH, exist_ok=True)
    os.makedirs(EVID, exist_ok=True)
    tag = time.strftime("r42b2_%H%M%S")
    tr_path = os.path.join(SCRATCH, "r42_boot2.jsonl")
    jf = open(tr_path, "w")

    def J(ev):
        jf.write(json.dumps(ev, default=str) + "\n")
        jf.flush()

    J({"ev": "RUN_START",
       "commit": os.popen("git -C %s rev-parse HEAD" % _REPO).read().strip(),
       "policy": "restore r42_postkill -> shipped policy -> mission_end "
                 "latch -> HARD zero-input hold",
       "boot1_lesson": "aa_resolved gate premature: 24000f zero input "
                       "from that posture = no banner/no restart",
       "ts": time.strftime("%FT%TZ", time.gmtime())})
    p = boot_to_demo()
    m = p.mem
    p.load_state(POSTKILL)
    if not t1.alive(m):
        raise SystemExit("r42_postkill not alive after restore")
    J({"ev": "POSTKILL_RESTORED", "vm": t2.read_vm(m), **t1.snap(m)})
    lp = latch_phase(p, m, J, tag)
    res = {"latch": {k: v for k, v in lp.items()}}
    if lp["outcome"] != "latched":
        res["outcome"] = f"latch_{lp['outcome']}"
    else:
        hd = hold_phase(p, m, J, tag, lp["c"])
        res.update(hd)
        res["latch_chunk"] = lp["c"]
    res["final"] = t1.snap(m)
    res["final_vm"] = t2.read_vm(m)
    with open(os.path.join(SCRATCH, "r42_boot2_report.json"), "w") as f:
        json.dump({"schema": "ps1play.r42-boot2/1",
                   "generated": time.strftime("%FT%TZ", time.gmtime()),
                   "commit": os.popen("git -C %s rev-parse HEAD"
                                      % _REPO).read().strip(),
                   "postkill": POSTKILL, "run": res}, f, indent=1,
                  default=str)
    jf.close()
    log(f"FIN: {res.get('outcome')} banner_c={res.get('banner_c')} "
        f"final={res.get('final')}")
    log("report -> scratch/r42/r42_boot2_report.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
