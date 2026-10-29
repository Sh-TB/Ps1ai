#!/usr/bin/env python3
"""r41t4_final.py — R41 Task 4 (BOOT 3/3 of the r41 ledger — FINAL).

Boot-3 post-mortem (r41_boot3.jsonl): an early faller-rain death in
the ckpt zone was MISSED by the chunk-boundary alive() check; the run
silently slid through CONTINUE -> auto-restart (px 37.5, score kept
3200) and the c100 "resolve" was a restart artifact. Fixes here:

  (a) death checked after EVERY input burst, not only at chunk start;
  (b) restart detector: in the kill phase px < 700 (a px never reached
      by the policy from the 810 ckpt without a death/restart) or the
      CONTINUE-screen word signature -> honest outcome restart_leak;
  (c) release predicate FIXED: a sticky transition — the flags word
      losing the 0x1 latch while the state word leaves 0xB, OR prog
      == 0xFFF38B4A exactly (0xFFFFFFFF is the pinned saturate, not a
      release), OR state == 0xC;
  (d) POST-KILL SAVESTATE `r41_postkill` (resolve+10 chunks) so the
      next round never re-walks the deterministic chain;
  (e) then the boot-3 sweep: AIMED fire at the live right-side rows
      (0x4054 family, x [1150,1450], corpse/wreck excluded) then hold
      RIGHT — the boot-2-named release blocker test.
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
import r40t7_nodes as t7                          # noqa: E402
import r41t2_nodes_live as t2                     # noqa: E402
from issue4_controller import boot_to_demo        # noqa: E402

SCRATCH = t2.SCRATCH
CKPT = t2.CKPT
POSTKILL = "r41_postkill"
CHUNKS = 1200
DUMP_EVERY = 10
TARGET_LO, TARGET_HI = 1150.0, 1450.0
WRECK_ST = 0xA44C
DEAD_ST = combat.CORPSE_ST
PROG_RELEASE = 0xFFF38B4A


def log(*a):
    print("[r41-t4]", *a, file=sys.stderr, flush=True)


def rows(m):
    out = []
    for s in range(1, 40):
        base = combat.TABLE + s * combat.STRIDE
        xw = int(m.u32(base + 0x78))
        if not xw:
            continue
        out.append({"slot": s, "x": round(xw / 65536.0, 1),
                    "st": int(m.u16(base)),
                    "a4": int(m.u16(base + 0xA4)),
                    "f8e": int(m.u16(base + 0x8E))})
    return out


def targets(m):
    px = t1.px_of(m)
    return [r for r in rows(m)
            if r["st"] not in DEAD_ST and r["st"] != WRECK_ST
            and TARGET_LO <= r["x"] <= TARGET_HI]


def vm_words(m):
    return (int(m.u16(combat.SECTION_FLAGS)),
            int.from_bytes(m.ram[0xEB5D4:0xEB5D8].tobytes(), "little"),
            int(m.u16(combat.SECTION_STATE)))


def release_now(prev_vmw, vmw):
    flags, prog, state = vmw
    pflags, _, pstate = prev_vmw
    if prog == PROG_RELEASE:
        return "prog"
    if state == 0xC:
        return "state_0xC"
    if pstate == 0xB and state != 0xB and not (flags & 0x1):
        return "left_0xB"
    return None


def aimed_fire(m, p, J, r):
    slot = r["slot"]
    for tap in range(10):
        if not t1.alive(m):
            return "dead"
        px = t1.px_of(m)
        cur = next((q for q in rows(m) if q["slot"] == slot), None)
        if cur is None or cur["st"] in DEAD_ST:
            return "gone"
        d = "RIGHT" if cur["x"] >= px else "LEFT"
        p.core.run(6, {d})
        if not t1.alive(m):
            return "dead"
        p.core.run(4, set())
        pre = t1.snap(m)
        p.core.run(4, {"Y"})
        for k in range(15):
            p.core.run(6, set())
            if not t1.alive(m):
                return "dead"
            cur = next((q for q in rows(m) if q["slot"] == slot), None)
            if cur is None or cur["st"] in DEAD_ST:
                post = t1.snap(m)
                J({"ev": "SOLDIER_KILL", "slot": slot, "taps": tap + 1,
                   "pre": pre, "post": post, "vm": t2.read_vm(m)})
                log(f"slot {slot} dead after {tap + 1} taps "
                    f"score {pre['score']}->{post['score']}")
                return "killed"
        J({"ev": "SOLDIER_TAP", "slot": slot, "tap": tap + 1,
           "st": hex(cur["st"]) if cur else None, **t1.snap(m)})
    return "stuck"


def run_arm(p, m, J, tlog, continues):
    pol = combat.CombatPolicy(queue_priority=True)
    p.core.run(2, set())
    J({"ev": "arm_start", "snap": t1.snap(m), "vm": t2.read_vm(m)})
    deaths = 0
    outcome, end_c = None, None
    last_px, last_segs = None, None
    prev_score = int(m.u32(t1.A_SCORE))
    t0 = time.time()
    resolved_at = None
    saved_postkill = False
    phase = "kill"
    kills = {}
    released_at = None
    prev_vmw = vm_words(m)
    for c in range(CHUNKS):
        if not t1.alive(m):
            deaths += 1
            J({"ev": "death", "phase": phase, "chunk": c, **t1.snap(m)})
            if not t1.wait_alive(m, p, wait=20):
                continues["FIN"] = continues.get("FIN", 0) + 1
                J({"ev": "CONTINUE_SCREEN", "chunk": c, **t1.snap(m)})
                from run_mission1_legit import recover_v2
                if not recover_v2(p, log=log) or \
                        not t1.wait_alive(m, p, wait=20):
                    outcome, end_c = "death_no_respawn", c
                    break
            last_px, last_segs = None, None
            continue
        if t1.px_of(m) > 5000.0:
            p.core.run(60, set())
            continue
        # restart-leak detector
        px_now0 = t1.px_of(m)
        if resolved_at is None and px_now0 < 700.0 and c > 2:
            outcome, end_c = "restart_leak", c
            J({"ev": "RESTART_LEAK", "chunk": c, "px": px_now0,
               **t1.snap(m)})
            break
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

        if phase == "kill":
            segs = pol.decide(15, px, scan, grenades=gren0,
                              hp=int(m.u16(t1.PLAYER_HP)))
            for x in segs:
                p.core.run(x["frames"], x["btns"] or set())
                if not t1.alive(m):
                    break
            if pol.stats.get("aa_resolved", 0) >= 1 and \
                    resolved_at is None:
                resolved_at = c
                phase = "sweep"
                J({"ev": "CHOPPER_RESOLVED", "chunk": c,
                   "vm": t2.read_vm(m), "table": t7.full_table(m),
                   "scan": scan, "snap": t1.snap(m)})
                log(f"CHOPPER RESOLVED at c{c} -> SWEEP")
            elif resolved_at is None and c % DUMP_EVERY == 0:
                J({"ev": "VM_DUMP", "chunk": c, "phase": phase,
                   "vm": t2.read_vm(m), "table": t7.full_table(m),
                   "snap": t1.snap(m)})
            s2 = t1.snap(m)
        else:
            if not saved_postkill and resolved_at is not None and \
                    c >= resolved_at + 10:
                p.save_state(POSTKILL)
                saved_postkill = True
                J({"ev": "POSTKILL_SAVED", "chunk": c, "state": POSTKILL,
                   "vm": t2.read_vm(m), **t1.snap(m)})
                log(f"post-kill savestate saved at c{c}")
            tg = targets(m)
            if tg:
                phase = "sweep"
                r = min(tg, key=lambda q: abs(q["x"] - t1.px_of(m)))
                J({"ev": "SWEEP_TARGET", "chunk": c, "target": r,
                   "all": tg, **t1.snap(m)})
                res_f = aimed_fire(m, p, J, r)
                if res_f == "dead":
                    deaths += 1
                    J({"ev": "death", "phase": phase, "chunk": c,
                       "during": "aimed_fire", **t1.snap(m)})
                    if not t1.wait_alive(m, p, wait=20):
                        continues["FIN"] = continues.get("FIN", 0) + 1
                        from run_mission1_legit import recover_v2
                        if not recover_v2(p, log=log) or \
                                not t1.wait_alive(m, p, wait=20):
                            outcome, end_c = "death_no_respawn", c
                            break
                    last_px, last_segs = None, None
                    continue
                if res_f == "killed":
                    kills[r["slot"]] = kills.get(r["slot"], 0) + 1
                phase = "advance" if res_f != "stuck" else "sweep"
            else:
                phase = "advance"
                p.core.run(15, {"RIGHT"})
                if not t1.alive(m):
                    continue
            if c % DUMP_EVERY == 0:
                J({"ev": "VM_DUMP", "chunk": c, "phase": phase,
                   "vm": t2.read_vm(m), "table": t7.full_table(m),
                   "targets": targets(m), "snap": t1.snap(m)})
            s2 = t1.snap(m)
        if s2["score"] != prev_score:
            J({"ev": "SCORE_EVENT", "chunk": c, "phase": phase,
               "from": prev_score, "to": s2["score"]})
            prev_score = s2["score"]
        vmw = vm_words(m)
        rel = release_now(prev_vmw, vmw)
        prev_vmw = vmw
        if rel and released_at is None:
            released_at = c
            J({"ev": "RELEASE_SIGNATURE", "chunk": c, "how": rel,
               "flags_prog_state": vmw, "vm": t2.read_vm(m),
               "table": t7.full_table(m), "snap": s2})
            log(f"RELEASE ({rel}) at c{c}: {vmw}")
        if s2["sec"][0] == 0xC and s2["px"] < 200.0 and t1.alive(m):
            outcome, end_c = "MISSION_BANNER", c
            break
        if t1.alive(m) and s2["px"] < 200.0 and c > 4 and \
                s2["sec"][0] in (0xB, 0x0) and resolved_at is not None:
            outcome, end_c = "banner_expired_restart", c
            J({"ev": "RESTART_SEEN", "chunk": c, **s2})
            break
        if t1.alive(m) and s2["sec"][0] == 0xC and pol.mission_end:
            outcome, end_c = "mission_end_latched", c
            break
    else:
        outcome, end_c = "budget", CHUNKS - 1
    res = {"outcome": outcome, "end_chunk": end_c, "deaths": deaths,
           "wall_s": round(time.time() - t0, 1),
           "throws": len(tlog.throws), "resolved_at": resolved_at,
           "released_at": released_at, "kills": kills,
           "saved_postkill": saved_postkill,
           "score_final": int(m.u32(t1.A_SCORE)),
           "pol_stats": {k: v for k, v in pol.stats.items() if v},
           "final": t1.snap(m), "final_vm": t2.read_vm(m)}
    J({"ev": "ARM_DONE", **res})
    log(f"FIN: {outcome} c={end_c} resolved={resolved_at} "
        f"released={released_at} kills={kills} score={res['score_final']}")
    return res


def main():
    n = t2.amend_ledger(
        "BOOT3-FINAL: hardened sensors (per-burst death, restart-leak, "
        "fixed release predicate) + post-kill savestate + the boot-2 "
        "soldier-wave sweep",
        script="r41t4_final.py")
    if n > 3:
        raise SystemExit("BOOT CAP EXCEEDED")
    tr_path = os.path.join(SCRATCH, "r41_boot4_final.jsonl")
    jf = open(tr_path, "w")

    def J(ev):
        jf.write(json.dumps(ev, default=str) + "\n")
        jf.flush()

    J({"ev": "RUN_START",
       "commit": os.popen("git -C %s rev-parse HEAD" % _REPO).read().strip(),
       "policy": "kill chain -> POSTKILL SAVE -> sweep (aimed, "
                 "x[1150,1450]) -> advance loop",
       "ts": time.strftime("%FT%TZ", time.gmtime())})
    p = boot_to_demo()
    m = p.mem
    p.load_state(CKPT)
    if not t1.alive(m):
        raise SystemExit("r38_ckpt not alive after restore")
    J({"ev": "CKPT_RESTORED", "vm": t2.read_vm(m), **t1.snap(m)})
    continues = {}
    tlog = t1.ThrowLog(J, "FIN")
    res = run_arm(p, m, J, tlog, continues)
    res["hp_drops"] = tlog.hits
    with open(os.path.join(SCRATCH, "r41_boot4_final_report.json"),
              "w") as f:
        json.dump({"schema": "ps1play.r41-boot4/1",
                   "generated": time.strftime("%FT%TZ", time.gmtime()),
                   "commit": os.popen("git -C %s rev-parse HEAD"
                                      % _REPO).read().strip(),
                   "checkpoint": CKPT, "run": res}, f, indent=1,
                  default=str)
    jf.close()
    log("report -> scratch/r41/r41_boot4_final_report.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
