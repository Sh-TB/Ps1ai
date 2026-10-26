#!/usr/bin/env python3
"""msx_anchor_regen.py — round 7 (task 17-a, COMPLETED by 17-a-r2):
regenerate the durable m2_train anchor (the workspace reset wiped it;
the 17-a attempt died with anchor_saved false).

R2 FIX (the rg1_045648 failure diagnosis, see
scratch/issue6_round7_msx/discrepancy_rg1_vs_session9.md): the 17-a
zero-input quiet ladder can NEVER reach M2 — the M1->M2 gate needs ONE
START accept at the CONTINUE? countdown (px 0.0, sec (11,1), flags 255,
score>0); without it the countdown self-expires into NOW LOADING ->
score reset -> input-contended ATTRACT DEMO (rg1's "rejected" worlds).
Secondary trap (m2t1/m2t8): a START tap can re-enter the input-live
endzone world (px ~992) — that world must be RIDDEN to the next
teardown and re-tapped, not mistaken for gameplay-success.

So THIS r2 resolver is signature-driven with bounded budgets:
  boot -> input sanity -> policy_ride (CombatPolicy traversal only,
  stop at FIRST S6-F1 teardown) -> resolve_to_m2():
    countdown signature -> START taps (<=3 per instance, 12f tap,
    600f accept poll, <=12 total);
    endzone (px>800, input-live) -> RIGHT-hold ride to the next
    teardown (<=4 rides);
    0xC banner (px 10-60) -> quiet wait;
    M2 spawn signature (score 0, px [60,90], php [70,80], gren 10)
    -> 90f stability proof -> save_state("m2_train") + RAM npz.
Spawn expectation px 76.4 php 76 gren 10 score 0 (m2t7/16-a; session-6
recorded 74.6/74 — the window tolerates both).  Overall deadline 400 s
(hard rule <=420 s).

One boot per process.  Evidence: scratch/issue6_round7_msx/.
"""
import argparse
import json
import os
import sys
import time

import numpy as np

_REPO = "/home/z/my-project/ps1ai"
for _p in (_REPO, os.path.join(_REPO, "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _REPO)

from ps1play import labconfig                       # noqa: E402,F401
from issue4_controller import boot                  # noqa: E402
from e2e_policy_trial import (snap, px_of, sha_file, DISC,   # noqa: E402
                              run_once)
from e2e_policy_trial import GRENADES, PLAYER_HP    # noqa: E402
import ps1play.agent.combat as combat               # noqa: E402
from msx_ramhunt_util import png, jlog              # noqa: E402
from lives_banner_variant import raw_slots          # noqa: E402

EVID = "/home/z/my-project/ps1ai/scratch/issue6_round7_msx"
RIDE_CHUNKS = 200
RIDE_WALL_S = 240.0
OPEN_CHUNK = 60
ZONE_CHUNK = 15
ZONE_ENTER_PX = 1100.0
EXPECT_SPAWN = {"px": 76.4, "php": 76, "gren": 10, "score": 0}
M2_PX_WINDOW = (60.0, 90.0)         # recorded M2 spawns: 74.6 / 76.4
M2_PHP_WINDOW = (70, 80)            # recorded: 74 / 76
RESOLVE_WALL_S = 300.0
MAX_TAPS_PER_CD = 4
MAX_OUTER = 4
DEADLINE_S = 400.0                  # hard run deadline (rule <=420 s)


def log(*a):
    print("[rg]", *a, file=sys.stderr, flush=True)


def input_sanity(p, m, J, tag):
    px0 = px_of(m)
    p.core.run(90, set())
    drift = round(px_of(m) - px0, 1)
    p.core.run(90, {"RIGHT"})
    moved = round(px_of(m) - px0 - drift, 1)
    ok = abs(drift) < 2.0 and moved > 8.0
    J({"ev": "INPUT_SANITY", "drift": drift, "moved_net": moved,
       "ok": ok, **snap(m)})
    png(p, "sanity_right", tag)
    return ok


def policy_ride(p, m, J, tag, deadline=None):
    """Shipped-policy traversal (run_once body, banner logic removed)
    up to the FIRST scene teardown.  Deaths: quiet respawn, resume."""
    pol = combat.CombatPolicy()
    last_px, last_segs = None, None
    deaths = 0
    max_px = 0.0
    t0 = time.time()
    ride_start_snap = m.ram.copy()
    for c in range(RIDE_CHUNKS):
        if time.time() - t0 > RIDE_WALL_S or (
                deadline and time.time() > deadline):
            J({"ev": "RIDE_WALL", "c": c})
            return "wall_guard", ride_start_snap, deaths, max_px
        s = snap(m)
        if s["px"] == 0.0 and s["php"] == 0:
            J({"ev": "RIDE_TEARDOWN", "c": c, **s, "slots": raw_slots(m)})
            png(p, "ride_td", tag)
            return "teardown", ride_start_snap, deaths, max_px
        if s["php"] == 0 and s["px"] != 0.0:
            deaths += 1
            J({"ev": "death", "c": c, **s})
            got = False
            for w in range(100):
                p.core.run(30, set())
                if snap(m)["flags"] == 0xFF and px_of(m) != 0.0 \
                        and int(m.u16(PLAYER_HP)) > 0:
                    got = True
                    break
            if not got:
                J({"ev": "DEAD_END", **snap(m)})
                return "dead_end", ride_start_snap, deaths, max_px
            last_px, last_segs = None, None
            continue
        px_early = px_of(m)
        if px_early > 5000.0:
            p.core.run(60, set())
            continue
        sec = combat.scan_section(m)
        pol.observe_section(sec, px_now=px_early)
        px = px_of(m)
        max_px = max(max_px, px)
        advanced = 0.0 if last_px is None else px - last_px
        intent = any("RIGHT" in (x.get("btns") or set())
                     for x in (last_segs or []))
        pol.observe(px, advanced, intent)
        scan = combat.scan_entities(m, px=px)
        cf = (ZONE_CHUNK if (pol.d7_zone or pol.section_pinned or
                             px >= ZONE_ENTER_PX) else OPEN_CHUNK)
        segs = pol.decide(cf, px, scan,
                          grenades=int(m.u8(GRENADES)),
                          hp=int(m.u16(PLAYER_HP)))
        last_px, last_segs = px, segs
        for x in segs:
            p.core.run(x["frames"], x["btns"] or set())
        if c % 5 == 0:
            J({"ev": "R", "c": c, **snap(m), "deaths": deaths})
            log(f"R{c} px={px} score={snap(m)['score']} "
                f"gren={int(m.u8(GRENADES))} deaths={deaths}")
    return "budget", ride_start_snap, deaths, max_px


def world_class(m):
    """Signature classification from VERIFIED telemetry only.
    Returns (kind, snap).  Kinds: countdown | scene_dark | banner |
    m2_spawn_cand | endzone | other_world."""
    s = snap(m)
    if s["px"] == 0.0 and s["php"] == 0:
        if s["sec"] == (11, 1) and s["flags"] == 255 and s["score"] > 0:
            return "countdown", s       # CONTINUE? accept window
        return "scene_dark", s          # tally/loading/score-reset family
    if s["flags"] != 0xFF:
        return "scene_dark", s
    if s["sec"][0] == 0xC and 10.0 <= s["px"] <= 60.0:
        return "banner", s              # mission-clear banner (px 26.4)
    if (s["score"] == 0 and M2_PX_WINDOW[0] <= s["px"] <= M2_PX_WINDOW[1]
            and M2_PHP_WINDOW[0] <= s["php"] <= M2_PHP_WINDOW[1]
            and s["gren"] == 10):
        return "m2_spawn_cand", s
    if s["px"] > 800.0:
        return "endzone", s             # input-live M1 endzone world
    return "other_world", s


def try_save_m2(p, m, J, tag):
    """If the world is a stable M2 spawn -> save the anchor + RAM npz,
    then prove input ownership with a RIGHT probe (post-save).
    Returns the spawn snap or None."""
    kind, s = world_class(m)
    if kind != "m2_spawn_cand":
        return None
    p.core.run(90, set())              # stability proof (world_stable)
    s2 = snap(m)
    if not (s2["flags"] == 0xFF and s2["score"] == 0
            and M2_PX_WINDOW[0] <= s2["px"] <= M2_PX_WINDOW[1]
            and s2["php"] > 0 and abs(s2["px"] - s["px"]) < 250.0):
        J({"ev": "SPAWN_UNSTABLE", "first": s, "after": s2})
        return None
    J({"ev": "M2_SPAWN_VERIFIED", **s2, "slots": raw_slots(m)})
    png(p, "m2_spawn", tag)
    try:
        p.save_state("m2_train")
        np.savez_compressed(
            os.path.join(EVID, f"{tag}_m2spawn_ram.npz"), ram=m.ram.copy())
        J({"ev": "M2_ANCHOR_SAVED", "state": "m2_train", **s2})
        log(f"ANCHOR SAVED px={s2['px']} php={s2['php']} "
            f"gren={s2['gren']} score={s2['score']}")
    except Exception as e:                              # noqa: BLE001
        J({"ev": "M2_ANCHOR_FAIL", "err": repr(e)[:120]})
        return None
    px0 = px_of(m)                     # input-ownership probe (post-save)
    p.core.run(90, {"RIGHT"})
    moved = round(px_of(m) - px0, 1)
    J({"ev": "ANCHOR_RIGHT_PROBE", "moved": moved, **snap(m)})
    png(p, "anchor_right", tag)
    return s2


def post_banner_m2(p, m, J, tag, deadline):
    """The proven session-6 post-banner choreography (W/S/Q, adapted
    from m2_train_advance.post_banner) with the M2-SPAWN-SIGNATURE
    handoff (NOT right_probe — m2t8 proved the endzone world also
    answers RIGHT, so gameplay_seen alone is a misfire).
    Returns the spawn snap or None."""
    spawn = try_save_m2(p, m, J, tag)
    if spawn:
        return spawn
    for w in range(6):                 # W: quiet watch
        p.core.run(150, set())
        s = snap(m)
        J({"ev": "W", "step": w, **s})
        if time.time() > deadline:
            break
        spawn = try_save_m2(p, m, J, tag)
        if spawn:
            return spawn
    for k in range(4):                 # S: bounded START taps
        p.core.run(12, {"START"})
        J({"ev": "S_TAP", "n": k + 1})
        for w in range(50):            # ~1500f accept/walk poll
            p.core.run(30, set())
            kind, s = world_class(m)
            if kind == "endzone":      # m2t1/m2t8 trap: stop tapping
                J({"ev": "S_ENDZONE_TRAP", "tap": k + 1, **s})
                return None
            if time.time() > deadline:
                break
            spawn = try_save_m2(p, m, J, tag)
            if spawn:
                return spawn
        s = snap(m)
        J({"ev": "S", "tap": k + 1, **s})
        png(p, f"S{k + 1}", tag)
        if time.time() > deadline:
            break
    for q in range(4):                 # Q: quiet
        p.core.run(300, set())
        s = snap(m)
        J({"ev": "Q", "step": q, **s})
        if time.time() > deadline:
            break
        spawn = try_save_m2(p, m, J, tag)
        if spawn:
            return spawn
    return None


def standing_clear(p, m, J, tag, max_bursts=30):
    """The release_test 3/3 standing-fire instrument: face the nearest
    live foe within 220px, 6f face + 24f Y-fire + 10f quiet; stop when
    the zone is clear or the budget is spent.  NEVER walks RIGHT."""
    from lives_banner_variant import raw_slots as _rs
    killed = 0
    for k in range(max_bursts):
        s = snap(m)
        if s["flags"] != 0xFF or s["px"] == 0.0 or s["php"] == 0:
            break
        foes = [sl for sl in _rs(m)
                if sl["st"] not in (0x4BE4, 0x5CC8, 19428)
                and sl["h"] == 64 and abs(sl["x"] - s["px"]) < 220.0]
        if not foes:
            return killed
        near = min(foes, key=lambda e: abs(e["x"] - s["px"]))
        d = "RIGHT" if near["x"] >= s["px"] else "LEFT"
        p.core.run(6, {d})
        p.core.run(24, {"Y"})
        p.core.run(10, set())
        if int(m.u32(0x0EE318)) > s["score"]:
            killed += 1
        if k % 10 == 0:
            J({"ev": "STANDING_FIRE", "k": k, "foes": len(foes), **s})
    return killed


def drive_m1_endgame(p, m, J, tag, deadline):
    """The recorded mission-end discipline (combat.py mission-end notes
    + release_test 3/3 + chain_a v2/v6 + the rg2/rg3 negatives):
      R: RIGHT-hold to the clamp trigger (px >= 1160) / teardown.
      H: STAND — never re-touch the clamp; standing-clear pending
         entities; the end sequence comes to a STANDING player.
      Watch: 0xC banner @ px 26.4 -> mark; countdown (px 0, sec (11,1),
         flags 255) -> ONE START tap re-forms the wave zone (rg2) or
         accepts into M2 post-banner (m2t7) -> M2-spawn handoff.
    Returns (saved, spawn, stats)."""
    t0 = time.time()
    taps = 0
    banner_seen = False
    stats = {"taps": 0, "clears": 0, "banners": 0}
    # ---- phase R: ride to the clamp trigger / teardown ----
    for i in range(120):
        if time.time() > deadline:
            return False, None, stats
        s = snap(m)
        if s["px"] == 0.0 and s["php"] == 0:
            J({"ev": "R_TEARDOWN", "i": i, **s})
            break
        if s["php"] == 0 and s["px"] != 0.0:
            for w in range(100):
                p.core.run(30, set())
                if snap(m)["flags"] == 0xFF and px_of(m) != 0.0 \
                        and int(m.u16(PLAYER_HP)) > 0:
                    break
            continue
        if s["px"] >= 1160.0 and s["flags"] == 0xFF:
            J({"ev": "R_CLAMP_TOUCH", "i": i, **s})
            break
        if s["sec"][0] == 0xC and 10.0 <= s["px"] <= 60.0:
            J({"ev": "R_BANNER_EARLY", "i": i, **s})
            banner_seen = True
            break
        if s["flags"] != 0xFF or s["px"] > 5000.0:
            p.core.run(60, set())
            continue
        p.core.run(30, {"RIGHT"})
    p.core.run(30, set())
    # ---- phase H: stand + clear + watch (the endgame machine) ----
    f = 0
    last_tap_f = -10**9
    while f < 11000 and time.time() < deadline:
        p.core.run(15, set())
        f += 15
        s = snap(m)
        if s["px"] == 0.0 and s["php"] == 0:
            if s["sec"] == (11, 1) and s["flags"] == 255:
                # countdown instance (pre- or post-banner)
                if f - last_tap_f > 600 and taps < 5:
                    p.core.run(12, {"START"})
                    taps += 1
                    last_tap_f = f
                    stats["taps"] = taps
                    J({"ev": "H_TAP", "n": taps, "banner_seen":
                       banner_seen, "before": s})
                    png(p, f"Htap{taps}", tag)
                    p.core.run(288, set())
                    f += 300
                continue
            # tally/loading/dark: quiet (rg1: input here re-arms the
            # machinery) — but a long dark stretch gets ONE blind tap
            if (s["flags"] in (0, 1) and f - last_tap_f > 1800
                    and taps < 5):
                p.core.run(12, {"START"})
                taps += 1
                last_tap_f = f
                stats["taps"] = taps
                J({"ev": "H_BLIND_TAP", "n": taps, **s})
                p.core.run(288, set())
                f += 300
            continue
        if s["flags"] != 0xFF:
            continue
        if s["sec"][0] == 0xC and 10.0 <= s["px"] <= 60.0:
            if not banner_seen:
                banner_seen = True
                stats["banners"] += 1
                J({"ev": "H_BANNER", "f": f, **s})
                png(p, "H_banner", tag)
            continue
        if (s["score"] == 0 and M2_PX_WINDOW[0] <= s["px"] <= M2_PX_WINDOW[1]
                and M2_PHP_WINDOW[0] <= s["php"] <= M2_PHP_WINDOW[1]
                and s["gren"] == 10):
            sp = try_save_m2(p, m, J, tag)
            if sp:
                return True, sp, stats
            continue
        # alive world: STANDING discipline — clear foes, never walk
        killed = standing_clear(p, m, J, tag, max_bursts=12)
        if killed:
            stats["clears"] += killed
            J({"ev": "H_CLEARED", "killed": killed, **snap(m)})
        f += 12 * 40          # accounting for the burst frames
    return False, None, stats


def resolve_to_m2(p, m, J, tag, deadline):
    """r2 v5 resolver: one proven ride (run_once) then the disciplined
    endgame driver; bounded retries within the run deadline.
    Returns (saved, spawn, stats)."""
    t0 = time.time()
    spawn = None
    history = []
    for outer in range(MAX_OUTER):
        if time.time() > deadline:
            break
        rec = run_once(p, m, J, tag, 200, control=False)
        history.append({"outer": outer, "outcome": rec["outcome"],
                        "end_chunk": rec["end_chunk"],
                        "deaths": rec["deaths"]})
        J({"ev": "E2E_RESULT", "outer": outer,
           "outcome": rec["outcome"], "end_chunk": rec["end_chunk"],
           "deaths": rec["deaths"]})
        log(f"outer{outer}: e2e={rec['outcome']} c={rec['end_chunk']} "
            f"deaths={rec['deaths']}")
        if rec["outcome"] == "MISSION_BANNER":
            png(p, f"outer{outer}_banner", tag)
            spawn = post_banner_m2(p, m, J, tag, deadline)
            if spawn:
                break
            J({"ev": "POST_BANNER_NO_M2", "outer": outer})
        if time.time() > deadline:
            break
        saved, spawn, dstats = drive_m1_endgame(p, m, J, tag, deadline)
        history.append({"outer": outer, "driver": dstats})
        if saved or spawn:
            break
        J({"ev": "DRIVER_NO_M2", "outer": outer, "stats": dstats})
    return spawn is not None, spawn, {
        "outer_history": history,
        "resolve_wall_s": round(time.time() - t0, 1)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", type=int, default=1)
    args = ap.parse_args()
    os.makedirs(EVID, exist_ok=True)
    tag = f"rg{args.run}_{time.strftime('%H%M%S')}"
    jf = open(os.path.join(EVID, f"{tag}.jsonl"), "w")

    def J(ev):
        jlog(jf, ev)

    t0 = time.time()
    deadline = t0 + DEADLINE_S
    p, fw = boot()
    m = p.mem
    s0 = snap(m)
    J({"ev": "boot", "run": args.run, "firmware": fw, **s0})
    log(f"booted ({fw}) px={s0['px']} php={s0['php']} sec={s0['sec']}")
    if not input_sanity(p, m, J, tag):
        out = {"verdict": "FAILED", "why": "gate world failed RAM "
               "input-causality sanity", "boot": s0}
        with open(os.path.join(EVID, f"report_{tag}.json"), "w") as fh:
            json.dump(out, fh, indent=1, default=str)
        J({"ev": "RUN_DONE", **out})
        jf.close()
        log("ABORT: gate world failed input sanity")
        return 0
    np.savez_compressed(os.path.join(EVID, f"{tag}_gatestart.npz"),
                        ram=m.ram.copy())
    saved, spawn, resolve = resolve_to_m2(p, m, J, tag, deadline)
    match = None
    if spawn:
        match = {k: (abs(spawn[k] - v) < 2.1 if k == "px"
                     else abs(spawn[k] - v) <= 2 if k == "php"
                     else spawn[k] == v)
                 for k, v in EXPECT_SPAWN.items()}
    out = {"run": args.run, "firmware": fw, "boot": s0,
           "resolver": resolve, "spawn": spawn,
           "expect_match": match,
           "anchor_saved": saved,
           "wall_total_s": round(time.time() - t0, 1),
           "frames": p.core.frames_run, "game_sha256": sha_file(DISC)}
    with open(os.path.join(EVID, f"report_{tag}.json"), "w") as fh:
        json.dump(out, fh, indent=1, default=str)
    J({"ev": "RUN_DONE", **{k: out[k] for k in
                            ("run", "spawn", "expect_match",
                             "anchor_saved", "wall_total_s")}})
    jf.close()
    log(f"RUN {tag}: saved={saved} "
        f"spawn={spawn} match={match} wall={out['wall_total_s']}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
