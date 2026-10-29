#!/usr/bin/env python3
"""r42t1_hold.py — R42 BOOT 1/2 (the 60% track, Issue #5): the HARD
no-input hold through prebanner -> banner -> banner+2s (the c28 recipe).

The capsule premise said "restore the post-kill savestate from boot-4".
REALITY (disclosed): r41_postkill DOES NOT EXIST — the boot-4 report
records saved_postkill=false (the restart leak at c78 pre-empted the
save) and emu/ws/states/ holds no r41_postkill.*.  So boot 1 REBUILDS
the resolved posture from r38_ckpt exactly like r41t4 did, SAVES
r42_postkill at the resolve gate, and then runs the HARD hold in the
same boot:

  HARD = the harness itself emits p.core.run(n, set()) and NEVER
  consults the policy during the hold.  R41 boot-4's leak is
  hypothesized to be exactly the policy's own unlatch/resume during
  the banner window (mission_end_hold only 2 of c74..c77); a hard hold
  removes that channel entirely.

  Success oracle (capsule, unchanged): the banner predicate (0xC +
  px in [10,60] persisting after the quiet confirm) + NO
  RESTART_SEEN/RESTART_LEAK through the hold, then either the
  mission-2 load or a clean mission-select.
  Contradiction shape: with ZERO inputs the countdown still expires
  into the M1 restart (px ~37, sec[0] in (0xB,0), score kept) -> the
  restart is the countdown's natural expiry, NOT a harness leak, and
  the known-good accept (session-6: ONE START tap) becomes the lever.

Walker words at 1-chunk granularity (15f chunks) throughout the hold.
Oracle never uses +0x8E.  Legal inputs only (the hold IS zero-input);
the rebuild uses the shipped policy only.
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

SCRATCH = os.path.join(_REPO, "scratch", "r42")
PNGDIR = os.path.join(SCRATCH, "pngs")
LEDGER = os.path.join(SCRATCH, "boots_used.json")
EVID = os.path.join(_REPO, "data", "games", "SLUS-01212",
                    "truck_evidence", "r42")
POSTKILL = "r42_postkill"
CKPT = t2.CKPT

REBUILD_CHUNKS = 1200
HOLD_CHUNKS = 1600           # 15f each -> 24000f ~ 6.7 min sim
WALL_GUARD_S = 9.0 * 60
BANNER_QUIET_F = 60          # banner_confirmed quiet (session-5 recipe)
BANNER_2S_F = 120            # banner + 2s (60fps)
POST_WORLD_CHUNKS = 40       # observe a post-banner world before closing
RESTART_PX_LO, RESTART_PX_HI = 20.0, 60.0


def log(*a):
    print("[r42-t1]", *a, file=sys.stderr, flush=True)


def amend_ledger(reason, script="r42t1_hold.py"):
    os.makedirs(SCRATCH, exist_ok=True)
    if not os.path.exists(LEDGER):
        with open(LEDGER, "w") as f:
            json.dump({"cap": 2, "count": 0, "log": [], "note":
                       "r41_postkill ABSENT (boot-4 saved_postkill=false; "
                       "states/ has no r41_postkill.*) -> boot 1 rebuilds "
                       "r42_postkill from r38_ckpt, then holds; boot 2 "
                       "reserved (accept-variant or the 0x4054 HP word)"},
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
    """The walker words at 1-chunk granularity (compact tuple)."""
    return {"flags": t2.rd_u16(m, t2.O_FLAGS),
            "prog": hex(t2.rd_u32(m, t2.O_PROG) or 0),
            "state": t2.rd_u16(m, t2.O_STATE),
            "cursor": hex(t2.rd_u32(m, t2.O_CURSOR) or 0),
            "gate_b": (t2.rd_u8(m, t2.O_GB1), t2.rd_u8(m, t2.O_GB2))}


def scene_teardown(m):
    s = t1.snap(m)
    return s["px"] == 0.0 and s["php"] == 0, s


def rebuild_phase(p, m, J, tag):
    """The kill chain from r38_ckpt until the resolve gate; then save."""
    pol = combat.CombatPolicy(queue_priority=True)
    p.core.run(2, set())
    J({"ev": "REBUILD_START", "snap": t1.snap(m), "vm": t2.read_vm(m)})
    t0 = time.time()
    last_px, last_segs = None, None
    prev_score = int(m.u32(t1.A_SCORE))
    deaths = 0
    for c in range(REBUILD_CHUNKS):
        if time.time() - t0 > WALL_GUARD_S:
            return {"outcome": "wall_guard", "pol": pol, "c": c}
        if not t1.alive(m):
            deaths += 1
            J({"ev": "death", "phase": "rebuild", "chunk": c,
               **t1.snap(m)})
            if not t1.wait_alive(m, p, wait=20):
                from run_mission1_legit import recover_v2
                if not recover_v2(p, log=log) or \
                        not t1.wait_alive(m, p, wait=20):
                    return {"outcome": "death_no_respawn", "pol": pol,
                            "c": c, "deaths": deaths}
            last_px, last_segs = None, None
            continue
        if t1.px_of(m) > 5000.0:
            p.core.run(60, set())
            continue
        # the R41 restart-leak detector (honest abort, no re-run)
        px0 = t1.px_of(m)
        if px0 < 700.0 and c > 2:
            J({"ev": "RESTART_LEAK", "phase": "rebuild", "chunk": c,
               "px": px0, **t1.snap(m)})
            return {"outcome": "restart_leak", "pol": pol, "c": c,
                    "deaths": deaths}
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
            J({"ev": "SCORE_EVENT", "phase": "rebuild", "chunk": c,
               "from": prev_score, "to": s2["score"]})
            prev_score = s2["score"]
        # ---- the resolve gate: the policy's mission_end latch -------
        # (prebanner (0,8)+d7_zone or the 0xC x2 confirm — both latched
        # 3/3 in sessions 4-6 and in r41 boot-3/boot-4).
        if pol.mission_end or \
                pol.stats.get("aa_resolved", 0) >= 1:
            p.save_state(POSTKILL)
            how = ("aa_resolved" if pol.stats.get("aa_resolved", 0) >= 1
                   else "mission_end_latch")
            J({"ev": "RESOLVED", "chunk": c, "how": how,
               "postkill_state": POSTKILL, "vm": t2.read_vm(m), **s2})
            log(f"RESOLVED ({how}) c{c} -> r42_postkill saved")
            return {"outcome": "resolved", "pol": pol, "c": c,
                    "deaths": deaths, "how": how}
        if c % 60 == 0:
            J({"ev": "REBUILD_DUMP", "chunk": c, "vm": vm_compact(m),
               **s2, "mode": pol.mode})
    return {"outcome": "budget_gate", "pol": pol,
            "c": REBUILD_CHUNKS - 1, "deaths": deaths}


def hold_phase(p, m, J, tag, gate_c):
    """The HARD hold: zero inputs, 1-chunk granularity, transition
    classifiers only."""
    t0 = time.time()
    banner_c = None
    banner_confirmed_c = None
    quiet_since = None
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
           "tear_streak": tear_streak,
           "banner": banner_c is not None})
        prev_vm = vm
        hold_c = c
        tear, _s = scene_teardown(m)
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
                png(p, "post_banner_world", tag)
                J({"ev": "POST_BANNER_WORLD", "chunk": c, **s,
                   "vm": t2.read_vm(m)})
                # hold through POST_WORLD_CHUNKS to see it stabilize
        alive = t1.alive(m)
        if not alive:
            J({"ev": "HOLD_NOT_ALIVE", "chunk": c, **s})
            p.core.run(15, set())
            continue
        # ---- banner candidate + quiet confirm (session-5 recipe,
        # satisfied WITHOUT input: the quiet IS the hold) ------------
        if banner_c is None:
            if s["sec"][0] == 0xC and 10.0 <= s["px"] <= 60.0:
                if quiet_since is None:
                    quiet_since = c
                elif c - quiet_since >= BANNER_QUIET_F // 15:
                    banner_c = c
                    png(p, "mission_banner", tag)
                    J({"ev": "BANNER", "chunk": c, **s,
                       "vm": t2.read_vm(m),
                       "latency_chunks": c})
                    log(f"BANNER c{c} px={s['px']} score={s['score']}")
            else:
                if quiet_since is not None:
                    J({"ev": "BANNER_CANDIDATE_LOST", "chunk": c, **s})
                quiet_since = None
        elif banner_confirmed_c is None and \
                c - banner_c >= BANNER_2S_F // 15:
            banner_confirmed_c = c
            J({"ev": "BANNER_2S", "chunk": c, **s, "vm": vm})
        # ---- restart classifier: independent of the banner state,
        # 2-chunk persistence (the M1-restart shape px~37, sec[0] 0xB/0;
        # the banner itself is 0xC so it never matches; the M2 spawn
        # px 74.6/76.4 sits OUTSIDE the window) ----------------------
        if 20.0 <= s["px"] <= 60.0 and s["sec"][0] in (0xB, 0x0):
            restart_streak += 1
            if restart_streak == 1:
                J({"ev": "RESTART_CANDIDATE", "chunk": c, **s})
            elif restart_streak >= 2:
                ev = ("BANNER_EXPIRED_RESTART" if banner_c is not None
                      else "RESTART_NO_BANNER")
                png(p, "restart", tag)
                J({"ev": ev, "chunk": c, **s, "vm": t2.read_vm(m),
                   "banner_c": banner_c})
                log(f"{ev} c{c} px={s['px']} sec={s['sec']}")
                return {"outcome": "restart_expired",
                        "end_c": c, "banner_c": banner_c,
                        "banner_2s_c": banner_confirmed_c,
                        "chunks": hold_c, "final": s}
        else:
            restart_streak = 0
        # ---- the m2-load accept: a fresh world after the teardown ---
        if post_world_c is not None and \
                c - post_world_c >= POST_WORLD_CHUNKS:
            png(p, "m2_world_stable", tag)
            J({"ev": "M2_WORLD_STABLE", "chunk": c, **s,
               "vm": t2.read_vm(m), "post_world_c": post_world_c})
            return {"outcome": "m2_load", "end_c": c,
                    "banner_c": banner_c,
                    "banner_2s_c": banner_confirmed_c,
                    "post_world_c": post_world_c, "chunks": hold_c,
                    "final": s}
        p.core.run(15, set())
    s = t1.snap(m)
    return {"outcome": "hold_budget", "end_c": hold_c,
            "banner_c": banner_c, "chunks": hold_c, "final": s}


def main():
    n = amend_ledger(
        "BOOT1: rebuild r42_postkill from r38_ckpt (premise staleness "
        "disclosed) + the HARD zero-input hold prebanner->banner+2s+")
    if n > 2:
        raise SystemExit("BOOT CAP EXCEEDED")
    os.makedirs(SCRATCH, exist_ok=True)
    os.makedirs(EVID, exist_ok=True)
    tag = time.strftime("r42b1_%H%M%S")
    tr_path = os.path.join(SCRATCH, "r42_boot1.jsonl")
    jf = open(tr_path, "w")

    def J(ev):
        jf.write(json.dumps(ev, default=str) + "\n")
        jf.flush()

    J({"ev": "RUN_START",
       "commit": os.popen("git -C %s rev-parse HEAD" % _REPO).read().strip(),
       "policy": "rebuild (shipped policy) -> r42_postkill -> HARD "
                 "zero-input hold through prebanner/banner/banner+2s+",
       "premise_note": "r41_postkill absent (boot-4 saved_postkill="
                       "false); rebuild disclosed in the ledger",
       "ts": time.strftime("%FT%TZ", time.gmtime())})
    p = boot_to_demo()
    m = p.mem
    p.load_state(CKPT)
    if not t1.alive(m):
        raise SystemExit("r38_ckpt not alive after restore")
    J({"ev": "CKPT_RESTORED", "vm": t2.read_vm(m), **t1.snap(m)})
    rb = rebuild_phase(p, m, J, tag)
    res = {"rebuild": {k: v for k, v in rb.items() if k != "pol"}}
    if rb["outcome"] != "resolved":
        res["outcome"] = f"rebuild_{rb['outcome']}"
    else:
        hd = hold_phase(p, m, J, tag, rb["c"])
        res.update(hd)
        res["rebuild"]["gate_chunk"] = rb["c"]
        res["rebuild"]["how"] = rb.get("how")
    res["final"] = t1.snap(m)
    res["final_vm"] = t2.read_vm(m)
    with open(os.path.join(SCRATCH, "r42_boot1_report.json"), "w") as f:
        json.dump({"schema": "ps1play.r42-boot1/1",
                   "generated": time.strftime("%FT%TZ", time.gmtime()),
                   "commit": os.popen("git -C %s rev-parse HEAD"
                                      % _REPO).read().strip(),
                   "checkpoint": CKPT, "postkill": POSTKILL,
                   "run": res}, f, indent=1, default=str)
    jf.close()
    log(f"FIN: {res.get('outcome')} banner_c={res.get('banner_c')} "
        f"final={res.get('final')}")
    log("report -> scratch/r42/r42_boot1_report.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
