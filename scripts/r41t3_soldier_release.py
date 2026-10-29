#!/usr/bin/env python3
"""r41t3_soldier_release.py — R41 Task 3 (BOOT 3 of the disclosed cap 3,
the LAST boot of this round's ledger).

Boot-2 evidence (r41_boot2.jsonl) NAMES the release blocker: after the
deterministic chopper kill (c421 reproduced exactly), the post-resolve
entity table holds LIVE right-side soldiers — slot 13 st 0x4054
x=1309.7 and slot 16 st 0x4054 x=1285.7 (the LIVE state family per
S4-F2; corpse control slot 19 st 0x4BE4) — at screen-x 247-313 but
dx ~264-288 from the player: OUTSIDE the shipped engage window
(near=None 741/779), so the shipped policy never fired at them and
the section script waits for their deaths forever. The cursor word
@0x800EB5F8 is a STATIC base pointer (not a cursor) whose first
handle entry is 0 — the R41 pending-node premise is CONTRADICTED by
the live readout and SUPERSEDED by this soldier-wave blocker.

Boot 3 = the minimal correction test:
  1. the deterministic kill chain again (repro gate),
  2. S2 sweep: AIMED fire (the session-4 soldier_bpp recipe: face 6f,
     settle 4f, Y tap, 90f state watch) at every live row in the
     x-window [1150, 1450] (st not corpse, not the 0xA44C wreck),
  3. S3 advance: hold RIGHT past the clamp when the window is clear,
  4. loop S2/S3; watch the release signatures (flags 0x1->0x8,
     prog -> 0xFFF38B4A, state -> 0xC), pins (0xA, 0x43), spawns.

Oracles: verified soldier state flips + score, RELEASE signature,
walk-past-1300, banner. +0x8E never in any oracle.
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
CHUNKS = 1200
DUMP_EVERY = 10
CLAMP_X = 1150.0
TARGET_LO, TARGET_HI = 1150.0, 1450.0
WRECK_ST = 0xA44C

DEAD_ST = combat.CORPSE_ST
LIVE_ST = combat.SOLDIER_FAMILY_ST


def log(*a):
    print("[r41-t3]", *a, file=sys.stderr, flush=True)


def rows(m):
    out = []
    for s in range(1, 40):
        base = combat.TABLE + s * combat.STRIDE
        xw = int(m.u32(base + 0x78))
        if not xw:
            continue
        out.append({"slot": s,
                    "x": round(xw / 65536.0, 1),
                    "st": int(m.u16(base)),
                    "a4": int(m.u16(base + 0xA4)),
                    "f8e": int(m.u16(base + 0x8E))})
    return out


def targets(m):
    """Live rows in the right-side window (corpse/wreck excluded)."""
    px = t1.px_of(m)
    out = []
    for r in rows(m):
        if r["st"] in DEAD_ST or r["st"] == WRECK_ST:
            continue
        if not (TARGET_LO <= r["x"] <= TARGET_HI):
            continue
        out.append(r)
    return out


def aimed_fire(m, p, J, r, tag):
    """The session-4 kill_one recipe on one row (bounded 10 taps)."""
    slot = r["slot"]
    for tap in range(10):
        if not t1.alive(m):
            return False
        px = t1.px_of(m)
        cur = None
        for row in rows(m):
            if row["slot"] == slot:
                cur = row
                break
        if cur is None or cur["st"] in DEAD_ST:
            return True
        d = "RIGHT" if cur["x"] >= px else "LEFT"
        p.core.run(6, {d})
        p.core.run(4, set())
        pre = t1.snap(m)
        p.core.run(4, {"Y"})
        for k in range(15):
            p.core.run(6, set())
            cur = None
            for row in rows(m):
                if row["slot"] == slot:
                    cur = row
                    break
            if cur is None or cur["st"] in DEAD_ST:
                post = t1.snap(m)
                J({"ev": "SOLDIER_KILL", "arm": tag, "slot": slot,
                   "taps": tap + 1, "pre": pre, "post": post,
                   "vm": t2.read_vm(m)})
                log(f"slot {slot} dead after {tap + 1} taps "
                    f"score {pre['score']}->{post['score']}")
                return True
        J({"ev": "SOLDIER_TAP", "arm": tag, "slot": slot,
           "tap": tap + 1, "st": hex(cur["st"]) if cur else None,
           **t1.snap(m)})
    return False


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
    phase = "kill"
    kills = {}
    released_at = None
    for c in range(CHUNKS):
        s = t1.snap(m)
        if not t1.alive(m):
            deaths += 1
            J({"ev": "death", "phase": phase, "chunk": c, **s})
            if not t1.wait_alive(m, p, wait=20):
                continues["REL"] = continues.get("REL", 0) + 1
                J({"ev": "CONTINUE_SCREEN", "chunk": c, **s})
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

        if phase == "kill":
            segs = pol.decide(15, px, scan, grenades=gren0,
                              hp=int(m.u16(t1.PLAYER_HP)))
            for x in segs:
                p.core.run(x["frames"], x["btns"] or set())
            cen2 = t1.census(m, t1.px_of(m))
            fr = t1.frames_of(segs)
            lob = [i for i, b in enumerate(fr) if "A" in b and "UP" in b]
            if pol.mode == "aa_kill" or lob:
                tlog.check_hit(m, t1.px_of(m), cen2, c)
                if lob:
                    tlog.record_throw(m, px, cen, c, extra={
                        "lob_frames_in_chunk": len(lob),
                        "gren0": gren0})
            if pol.stats.get("aa_resolved", 0) >= 1 and resolved_at is None:
                resolved_at = c
                phase = "sweep"
                J({"ev": "CHOPPER_RESOLVED", "chunk": c,
                   "vm": t2.read_vm(m), "table": t7.full_table(m),
                   "scan": scan, "snap": t1.snap(m)})
                log(f"CHOPPER RESOLVED at c{c} -> SWEEP")
            s2 = t1.snap(m)
        else:
            # ---- S2 sweep / S3 advance ----
            tg = targets(m)
            if tg:
                phase = "sweep"
                r = min(tg, key=lambda q: abs(q["x"] - t1.px_of(m)))
                J({"ev": "SWEEP_TARGET", "chunk": c, "target": r,
                   "all_targets": tg, **t1.snap(m)})
                ok = aimed_fire(m, p, J, r, "REL")
                kills[r["slot"]] = kills.get(r["slot"], 0) + (1 if ok else 0)
            else:
                phase = "advance"
                p.core.run(15, {"RIGHT"})
            s2 = t1.snap(m)
            if resolved_at is not None and c % DUMP_EVERY == 0:
                J({"ev": "VM_DUMP", "chunk": c, "phase": phase,
                   "vm": t2.read_vm(m), "table": t7.full_table(m),
                   "targets": targets(m), "snap": s2})
        if s2["score"] != prev_score:
            J({"ev": "SCORE_EVENT", "chunk": c, "phase": phase,
               "from": prev_score, "to": s2["score"]})
            prev_score = s2["score"]
        # release signature watch
        vmw = (int(m.u16(combat.SECTION_FLAGS)),
               int.from_bytes(m.ram[0xEB5D4:0xEB5D8].tobytes(), "little"),
               int(m.u16(combat.SECTION_STATE)))
        if released_at is None and phase != "kill" and \
                (vmw[0] & 0x8) or (vmw[1] == 0xFFF38B4A):
            released_at = c
            J({"ev": "RELEASE_SIGNATURE", "chunk": c,
               "flags_prog_state": vmw, "vm": t2.read_vm(m),
               "table": t7.full_table(m), "snap": s2})
            log(f"RELEASE SIGNATURE at c{c}: {vmw}")
        if s2["sec"][0] == 0xC and s2["px"] < 200.0 and t1.alive(m):
            outcome, end_c = "MISSION_BANNER", c
            break
        if t1.alive(m) and s2["px"] < 200.0 and c > 4 and \
                s2["sec"][0] in (0xB, 0x0) and phase != "kill":
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
           "score_final": int(m.u32(t1.A_SCORE)),
           "pol_stats": {k: v for k, v in pol.stats.items() if v},
           "final": t1.snap(m), "final_vm": t2.read_vm(m)}
    J({"ev": "ARM_DONE", **res})
    log(f"REL: {outcome} c={end_c} resolved={resolved_at} "
        f"released={released_at} kills={kills} score={res['score_final']}")
    return res


def main():
    n = t2.amend_ledger(
        "BOOT3: soldier-wave release test — aimed fire at the live "
        "0x4054 rows (slots 13/16) then advance; release-signature watch",
        script="r41t3_soldier_release.py")
    if n > 3:
        raise SystemExit("BOOT CAP EXCEEDED")
    tr_path = os.path.join(SCRATCH, "r41_boot3.jsonl")
    jf = open(tr_path, "w")

    def J(ev):
        jf.write(json.dumps(ev, default=str) + "\n")
        jf.flush()

    J({"ev": "RUN_START",
       "commit": os.popen("git -C %s rev-parse HEAD" % _REPO).read().strip(),
       "policy": "kill chain (v3.1) -> SWEEP (aimed, x[1150,1450]) -> "
                 "ADVANCE (hold RIGHT) loop",
       "ts": time.strftime("%FT%TZ", time.gmtime())})
    p = boot_to_demo()
    m = p.mem
    p.load_state(CKPT)
    if not t1.alive(m):
        raise SystemExit("r38_ckpt not alive after restore")
    J({"ev": "CKPT_RESTORED", "vm": t2.read_vm(m), **t1.snap(m)})
    continues = {}
    tlog = t1.ThrowLog(J, "REL")
    res = run_arm(p, m, J, tlog, continues)
    res["hp_drops"] = tlog.hits
    with open(os.path.join(SCRATCH, "r41_boot3_report.json"), "w") as f:
        json.dump({"schema": "ps1play.r41-boot3/1",
                   "generated": time.strftime("%FT%TZ", time.gmtime()),
                   "commit": os.popen("git -C %s rev-parse HEAD"
                                      % _REPO).read().strip(),
                   "checkpoint": CKPT, "run": res}, f, indent=1,
                  default=str)
    jf.close()
    log("report -> scratch/r41/r41_boot3_report.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
