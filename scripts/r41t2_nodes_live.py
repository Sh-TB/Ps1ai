#!/usr/bin/env python3
"""r41t2_nodes_live.py — R41 Task 2 (BOOT 2 of the disclosed cap 3;
boot 1 = scripts/r38t1_reach.py rebuilding r38_ckpt, its own ledger).

The R40-recorded lever, executed: the section-VM queue walker decode
(static, r41t0/r41t1, zero boots) says

  @0x800EB5F8 = the walker CURSOR (u32 address, monotonic, stored back)
  loop: handle = *cursor; if 0 -> done-path (0x800205fc, $a1=1 ->
        jal 0x800216bc(0)); else node=handle; cursor+=4 (stored);
        sub = node->0x5C; if 0 -> next entry; else s8 = sub->0x8;
        if s8 != 0 -> return node to the caller (dispatch elsewhere);
  plus byte gates @0x800EB5DE / @0x800EB5F2 and handle->0x8
  (0x80020654 path), walker flags u16 @0x800EB5D0 (bit0 latch),
  progress u32 @0x800EB5D4 (release signature -> 0xFFF38B4A),
  section state u16 @0x800EB5F4, runner s16 @0x800EB588,
  gate u16 @0x800EB5C6, node table @0x800EB5E8.

R40 boot-7 saw cursor = 0x80084dcc post-kill with the body unread.
This boot NAMES the pending node: at CHOPPER_RESOLVED and every dump
we read the cursor, the handle word AT the cursor, the node chain
(node->0x5C, sub->0x8, node->0x8), the surrounding handle array
(backward 64 + forward 8 entries, KUSEG-pointer classified), and the
full section-VM word set — plus the entity table so the pending node
correlates with an entity identity or a trigger.

Posture after the kill = the session-3/4 release geometry (walk LEFT
to the verified 992-1016 zone, stand) — the boot-6 falsification is
re-tested WITH the node readout, so a re-latch is now EXPLAINABLE.

Success oracles unchanged (verified hp_a4 drops; CHOPPER_RESOLVED;
flags 0x1->0x8; prog -> 0xFFF38B4A; the 0xC state). +0x8E never in
any oracle.
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
import r40t1_census as c1                         # noqa: E402
import r40t7_nodes as t7                          # noqa: E402
from issue4_controller import boot_to_demo        # noqa: E402

SCRATCH = os.path.join(_REPO, "scratch", "r41")
LEDGER = os.path.join(SCRATCH, "boots_used.json")
CKPT = c1.CKPT
CHUNKS = 1200
DUMP_EVERY = 10
PRE_DUMP_EVERY = 60
WAVE_ZONE = 1016.0
WAVE_FLOOR = 992.0

# section-VM offsets (RAM offsets = VA - 0x80000000)
O_RUNNER = 0xEB588
O_GATE = 0xEB5C6
O_FLAGS = 0xEB5D0                 # u16 (bit0 advanced latch)
O_PROG = 0xEB5D4                  # u32
O_TABLE = 0xEB5E8                 # 2 words
O_STATE = 0xEB5F4                 # u16
O_CURSOR = 0xEB5F8                # u32
O_GB1, O_GB2 = 0xEB5DE, 0xEB5F2   # u8 gates (0x80020628 / 0x8002063c)

LO_VA, HI_VA = 0x80010000, 0x80200000


def log(*a):
    print("[r41-t2]", *a, file=sys.stderr, flush=True)


def amend_ledger(reason, script="r41t2_nodes_live.py"):
    os.makedirs(SCRATCH, exist_ok=True)
    if not os.path.exists(LEDGER):
        with open(LEDGER, "w") as f:
            json.dump({"cap": 3, "count": 0, "log": [], "note":
                       "boot 1 = r38t1_reach.py (own ledger, scratch/r38)"},
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


def rd_u32(m, off):
    try:
        return int(m.u32(off))
    except Exception:
        return None


def rd_u16(m, off):
    try:
        return int(m.u16(off))
    except Exception:
        return None


def rd_u8(m, off):
    try:
        return int(m.u8(off))
    except Exception:
        return None


def decode_handle(m, h, depth=2):
    """node->0x5C, sub->0x8, node->0x8 — the decoded static contract."""
    if h is None or not (LO_VA <= h < HI_VA):
        return {"handle": h, "valid": False}
    o = h - 0x80000000
    n5c = rd_u32(m, o + 0x5C)
    n8 = rd_u32(m, o + 0x8)
    out = {"handle": hex(h), "valid": True,
           "node_0x5C": hex(n5c) if n5c is not None else None,
           "node_0x8": hex(n8) if n8 is not None else None}
    if n5c is not None and LO_VA <= n5c < HI_VA:
        o2 = n5c - 0x80000000
        s8 = rd_u32(m, o2 + 0x8)
        s0 = rd_u32(m, o2)
        out["sub_0x8"] = hex(s8) if s8 is not None else None
        out["sub_0x0"] = hex(s0) if s0 is not None else None
    return out


def read_vm(m):
    """The full section-VM readout incl. the pending node identity."""
    cur = rd_u32(m, O_CURSOR)
    vm = {
        "runner_s16": rd_u16(m, O_RUNNER),
        "gate_u16": rd_u16(m, O_GATE),
        "flags_u16": rd_u16(m, O_FLAGS),
        "prog_u32": hex(rd_u32(m, O_PROG) or 0),
        "table": [hex(x) if x is not None else None
                  for x in (rd_u32(m, O_TABLE), rd_u32(m, O_TABLE + 4))],
        "state_u16": hex(rd_u16(m, O_STATE) or 0),
        "gate_bytes": (rd_u8(m, O_GB1), rd_u8(m, O_GB2)),
        "cursor": hex(cur) if cur is not None else None,
    }
    if cur is not None and LO_VA <= cur < HI_VA:
        co = cur - 0x80000000
        vm["handle_at_cursor"] = hex(rd_u32(m, co) or 0)
        h = rd_u32(m, co)
        vm["pending"] = decode_handle(m, h)
        # backward array scan (processed entries): KUSEG ptr or 0
        back = []
        for k in range(1, 65):
            w = rd_u32(m, co - 4 * k)
            if w is None:
                break
            back.append({"d": k, "w": hex(w),
                         **(decode_handle(m, w)
                            if LO_VA <= w < HI_VA else {})})
            if len(back) >= 3 and all(
                    (b["w"] == "0x0") for b in back[-3:]):
                break
        vm["array_backward"] = back[:24]
        fwd = []
        for k in range(1, 9):
            w = rd_u32(m, co + 4 * k)
            if w is None:
                break
            fwd.append({"d": k, "w": hex(w),
                        **(decode_handle(m, w)
                           if LO_VA <= w < HI_VA else {})})
        vm["array_forward"] = fwd
    return vm


def run_arm(p, m, J, tlog, continues):
    pol = combat.CombatPolicy(queue_priority=True)
    p.core.run(2, set())
    J({"ev": "arm_start", "snap": t1.snap(m), "vm": read_vm(m)})
    deaths = 0
    outcome, end_c = None, None
    last_px, last_segs = None, None
    prev_score = int(m.u32(t1.A_SCORE))
    t0 = time.time()
    resolved_at = None
    stands = 0
    for c in range(CHUNKS):
        s = t1.snap(m)
        if not t1.alive(m):
            deaths += 1
            J({"ev": "death", "chunk": c, **s})
            if not t1.wait_alive(m, p, wait=20):
                continues["NODES"] = continues.get("NODES", 0) + 1
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
        segs = pol.decide(15, px, scan, grenades=gren0,
                          hp=int(m.u16(t1.PLAYER_HP)))
        posture = "policy"
        if resolved_at is not None:
            px_now = t1.px_of(m)
            if px_now > WAVE_ZONE:
                segs = [{"frames": 15, "btns": {"LEFT"}}]
                posture = "walk_left"
            else:
                segs = [{"frames": 15, "btns": set()}]
                posture = "stand"
                stands += 1
        last_px, last_segs = px, segs
        pre_sec = (int(m.u16(combat.SECTION_STATE)),
                   int(m.u16(combat.SECTION_FLAGS)))
        for x in segs:
            p.core.run(x["frames"], x["btns"] or set())
        post_sec = (int(m.u16(combat.SECTION_STATE)),
                    int(m.u16(combat.SECTION_FLAGS)))
        if pre_sec != post_sec:
            J({"ev": "sec_transition", "chunk": c, "from": pre_sec,
               "to": post_sec, "posture": posture, "vm": read_vm(m),
               **t1.snap(m)})
        s2 = t1.snap(m)
        if s2["score"] != prev_score:
            J({"ev": "SCORE_EVENT", "chunk": c, "mode": pol.mode,
               "posture": posture, "from": prev_score, "to": s2["score"]})
            prev_score = s2["score"]
        cen2 = t1.census(m, t1.px_of(m))
        J({"ev": "census", "c": c, "mode": pol.mode, "posture": posture,
           **s2, **(pol.last_scan or {})})
        dump_due = ((resolved_at is None and c % PRE_DUMP_EVERY == 0)
                    or (resolved_at is not None and c % DUMP_EVERY == 0))
        if dump_due:
            J({"ev": "VM_DUMP", "chunk": c, "posture": posture,
               "resolved": resolved_at is not None,
               "vm": read_vm(m),
               "table": t7.full_table(m),
               "scan": combat.scan_entities(m, px=t1.px_of(m)),
               "snap": s2})
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
                           "gren0": gren0, "mode": pol.mode})
        if pol.stats.get("aa_resolved", 0) >= 1 and resolved_at is None:
            resolved_at = c
            J({"ev": "CHOPPER_RESOLVED", "chunk": c,
               "kill_connects": pol.stats.get("aa_kill_connect", 0),
               "connects": pol.stats.get("aa_connect", 0),
               "vm": read_vm(m),
               "table": t7.full_table(m),
               "scan": combat.scan_entities(m, px=t1.px_of(m)),
               "snap": s2})
            log(f"CHOPPER RESOLVED at c{c}")
        if s2["sec"][0] == 0xC and s2["px"] < 200.0 and t1.alive(m):
            outcome, end_c = "MISSION_BANNER", c
            J({"ev": "VM_DUMP", "chunk": c, "why": "banner",
               "vm": read_vm(m), "table": t7.full_table(m), "snap": s2})
            break
        if t1.alive(m) and s2["px"] < 200.0 and c > 4 and \
                s2["sec"][0] in (0xB, 0x0):
            outcome, end_c = "banner_expired_restart", c
            J({"ev": "RESTART_SEEN", "chunk": c, **s2})
            break
        if t1.alive(m) and s2["sec"][0] == 0xC and pol.mission_end:
            outcome, end_c = "mission_end_latched", c
            break
        if resolved_at is not None and c - resolved_at > 400 and \
                s2["prog"] in (0xFFF38B4A,):
            outcome, end_c = "RELEASED_PROG_SIGNATURE", c
            J({"ev": "RELEASE", "chunk": c, "vm": read_vm(m), **s2})
            break
    else:
        outcome, end_c = "budget", CHUNKS - 1
    res = {"outcome": outcome, "end_chunk": end_c, "deaths": deaths,
           "wall_s": round(time.time() - t0, 1),
           "throws": len(tlog.throws), "resolved_at": resolved_at,
           "stand_chunks": stands,
           "score_final": int(m.u32(t1.A_SCORE)),
           "pol_stats": {k: v for k, v in pol.stats.items() if v},
           "final": t1.snap(m), "final_vm": read_vm(m)}
    J({"ev": "ARM_DONE", **res})
    log(f"NODES: {outcome} c={end_c} resolved_at={resolved_at} "
        f"score={res['score_final']}")
    return res


def main():
    n = amend_ledger(
        "BOOT2: kill chain (v3.1) + the section-VM node readout naming "
        "the pending node (cursor/handle/node-chain/array)")
    if n > 3:
        raise SystemExit("BOOT CAP EXCEEDED")
    os.makedirs(SCRATCH, exist_ok=True)
    tr_path = os.path.join(SCRATCH, "r41_boot2.jsonl")
    jf = open(tr_path, "w")

    def J(ev):
        jf.write(json.dumps(ev, default=str) + "\n")
        jf.flush()

    J({"ev": "RUN_START",
       "commit": os.popen("git -C %s rev-parse HEAD" % _REPO).read().strip(),
       "policy": "R40 v3.1 until resolve; then the release geometry "
                 "(walk-left to 992-1016, stand)",
       "ts": time.strftime("%FT%TZ", time.gmtime())})
    p = boot_to_demo()
    m = p.mem
    p.load_state(CKPT)
    if not t1.alive(m):
        raise SystemExit("r38_ckpt not alive after restore")
    J({"ev": "CKPT_RESTORED", "vm": read_vm(m), **t1.snap(m)})
    continues = {}
    tlog = t1.ThrowLog(J, "NODES")
    res = run_arm(p, m, J, tlog, continues)
    res["hp_drops"] = tlog.hits
    with open(os.path.join(SCRATCH, "r41_boot2_report.json"), "w") as f:
        json.dump({"schema": "ps1play.r41-boot2/1",
                   "generated": time.strftime("%FT%TZ", time.gmtime()),
                   "commit": os.popen("git -C %s rev-parse HEAD"
                                      % _REPO).read().strip(),
                   "checkpoint": CKPT, "run": res}, f, indent=1,
                  default=str)
    jf.close()
    log("report -> scratch/r41/r41_boot2_report.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
