#!/usr/bin/env python3
"""r40t7_nodes.py — R40 Task 7 (BOOT 7 of the disclosed cap 7, ledger
amended 6->7 BEFORE the run).

Boot-6 = the boot-5 watch + the post-kill wave-zone stand, and it
FALSIFIED the stand as the release path: the walk LEFT hit a hard
barrier at px 1021.8 (5.8 px short of the verified 992-1016 zone) with
the walker at [0xB, 0x1] and the progress word accumulating pending
bits. Session-3 finding F6 gives the section-VM queue RAM map (runner
id @0x800EB588, gate @0x800EB5C6, node table @0x800EB5E8, node list
@0x800EB5F8); F1 gives the release signatures (walker flags 0x1->0x8,
progress 0xFFFFFFFF->0xFFF38B4A).

Boot 7 = the boot-6 run + QUEUE-RAM dumps: every FULL_TABLE dump and
the CHOPPER_RESOLVED event also read 0x800EB580..0x800EB66F (the
walker/queue words + the node list) so the pending release blocker is
NAMED, not guessed. No behavior change beyond boot-6's posture.
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
CHUNKS = 1200
DUMP_EVERY = 10
WAVE_ZONE = 1016.0                                # stand at <= this
WAVE_FLOOR = 992.0                                # the verified release band


def log(*a):
    print("[r40-t7]", *a, file=sys.stderr, flush=True)


def full_table(m):
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


QUEUE_LO = 0x800EB580
QUEUE_HI = 0x800EB670          # covers runner id s16, gate, table, nodes


def read_queue_ram(m):
    """The session-3 F6 section-VM queue words (raw little-endian
    u16/u32 sweep + the node list), for the post-kill pending-node
    identification. Read-only."""
    out = {}
    try:
        raw = bytes(m.ram[QUEUE_LO - 0x80000000:QUEUE_HI - 0x80000000]
                    .tobytes()) if hasattr(m.ram, "tobytes") else None
    except Exception:
        raw = None
    if raw is None:
        # fall back to per-word reads through the memory interface
        words = []
        for a in range(QUEUE_LO, QUEUE_HI, 4):
            try:
                words.append(int(m.u32(a)))
            except Exception:
                words.append(None)
        out["u32_sweep"] = words
        out["sweep_base"] = QUEUE_LO
        return out
    out["u32_sweep"] = [int.from_bytes(raw[i:i + 4], "little")
                        for i in range(0, len(raw), 4)]
    out["sweep_base"] = QUEUE_LO
    return out


def run_nodes_arm(p, m, J, tag, chunks_cap, tlog, continues=None,
                  settle=2):
    """The boot-5 watch harness + the post-resolve posture change
    (the policy's segments are OVERRIDDEN after the chopper resolves:
    LEFT-walk to the wave zone, then stand — the session-3/4 release
    geometry)."""
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
    stands = 0
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
        # ---- the post-resolve posture change (boot-6) ----
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
            J({"ev": "sec_transition", "arm": tag, "chunk": c,
               "from": pre_sec, "to": post_sec, "posture": posture,
               **t1.snap(m)})
        s2 = t1.snap(m)
        if s2["score"] != prev_score:
            J({"ev": "SCORE_EVENT", "arm": tag, "chunk": c,
               "mode": pol.mode, "posture": posture,
               "from": prev_score, "to": s2["score"]})
            prev_score = s2["score"]
        cen2 = t1.census(m, t1.px_of(m))
        ch_fix = t1.chopper_of(cen2, t1.px_of(m))
        J({"ev": "census", "arm": tag, "c": c, "mode": pol.mode,
           "posture": posture,
           "px": s2["px"], "php": s2["php"], "sec": s2["sec"],
           "score": s2["score"], "gren": s2["gren"],
           "prog": s2["prog"],
           **(pol.last_scan or {})})
        if resolved_at is not None and c % DUMP_EVERY == 0:
            J({"ev": "FULL_TABLE", "arm": tag, "chunk": c,
               "table": full_table(m),
               "scan": combat.scan_entities(m, px=t1.px_of(m)),
               "section_words": (int(m.u16(combat.SECTION_STATE)),
                                 int(m.u16(combat.SECTION_FLAGS))),
               "queue_ram": read_queue_ram(m),
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
                           "gren0": gren0,
                           "mode": pol.mode})
        if pol.stats.get("aa_resolved", 0) >= 1 and resolved_at is None:
            resolved_at = c
            J({"ev": "CHOPPER_RESOLVED", "arm": tag, "chunk": c,
               "kill_connects": pol.stats.get("aa_kill_connect", 0),
               "connects": pol.stats.get("aa_connect", 0),
               "table": full_table(m),
               "scan": combat.scan_entities(m, px=t1.px_of(m)),
               "queue_ram": read_queue_ram(m),
               "snap": s2})
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
           "stand_chunks": stands,
           "score_final": int(m.u32(t1.A_SCORE)),
           "pol_stats": {k: v for k, v in pol.stats.items() if v},
           "final": t1.snap(m)}
    J({"ev": "ARM_DONE", **res})
    log(f"{tag}: {outcome} c={end_c} throws={res['throws']} "
        f"resolved_at={resolved_at} stands={stands} "
        f"score={res['score_final']}")
    return res


def main():
    # idempotent filing: the three pre-boot aborts already filed
    # boot-7 slots (disclosed in the ledger cap 7->9 amendment); reuse
    # the filing when the last entry is this script's corrected BOOT7
    # line, so the ACTUAL run does not consume another slot.
    import json as _json
    with open(c1.LEDGER) as _f:
        _led = _json.load(_f)
    _last = (_led.get("log") or [{}])[-1]
    if _last.get("script") == "r40t7_nodes.py" and \
            "BOOT7" in _last.get("reason", "") and \
            "PRE-BOOT ABORT" not in _last.get("reason", ""):
        n = int(_led["count"])
        c1.log(f"boot filing reused: n={n}/{_led['cap']}")
    else:
        n = c1.amend_ledger(
            "BOOT7 (the actual run): the boot-6 posture + the queue-RAM "
            "dumps naming the pending release node",
            script="r40t7_nodes.py")
    if n > int(_led["cap"]):
        raise SystemExit("BOOT CAP EXCEEDED")
    tr_path = os.path.join(SCRATCH, "r40_boot7.jsonl")
    jf = open(tr_path, "w")

    def J(ev):
        jf.write(json.dumps(ev, default=str) + "\n")
        jf.flush()

    J({"ev": "RUN_START",
       "commit": os.popen("git -C %s rev-parse HEAD"
                          % _REPO).read().strip(),
       "policy": "R40 v3.1 until resolve; then the posture change "
                 "(LEFT-walk to the wave zone, stand)",
       "ts": time.strftime("%FT%TZ", time.gmtime())})

    p = boot_to_demo()
    m = p.mem
    p.load_state(CKPT)
    if not t1.alive(m):
        raise SystemExit("r38_ckpt not alive after restore")

    continues = {}
    tlog = t1.ThrowLog(J, "NODES")
    res = run_nodes_arm(p, m, J, "NODES", CHUNKS, tlog,
                        continues=continues)
    res["hp_drops"] = tlog.hits
    res["throws"] = len(tlog.throws)

    with open(os.path.join(SCRATCH, "r40_boot7_report.json"),
              "w") as f:
        json.dump({"schema": "ps1play.r40-boot7/1",
                   "generated": time.strftime("%FT%TZ", time.gmtime()),
                   "commit": os.popen("git -C %s rev-parse HEAD"
                                      % _REPO).read().strip(),
                   "checkpoint": CKPT, "run": res}, f, indent=1,
                  default=str)
    jf.close()
    log("report -> scratch/r40/r40_boot7_report.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
