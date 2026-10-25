#!/usr/bin/env python3
"""lives_banner_variant.py — Issue #5 session 6: the lives-remaining
banner variant (the session-5 declared next action, commit 21d92db:
"Mission 2 entry NOT claimed, needs the lives-remaining variant
(pre-window chopper kill = declared next action)").

Session-5 evidence (S5-F2): the e2e fresh-boot run is deterministic 3/3
but spends the LAST life at c43 — the standing player dies to the
chopper's faller rain during the mission_end_hold (php 155->0), so the
banner lands with 0 lives and the post-banner flow is the CONTINUE?
branch (S5-F3).  The declared fix: kill the chopper with the PROVEN
session-3 jump-lob recipe (chopper_kill.py arm J1: hop -> UP+A lob at
the apex, connect band |dx| 7-29, 3 connects = dead, hp_a4 300->0)
BEFORE the trigger-B signature — the pre-banner (0,8) walker reset
inside the D7 zone — because after that latch ANY input skips the
banner into a restart (chain_a v3/v4).

Arms:
  variant  boot() -> fresh mission start -> the SHIPPED CombatPolicy
           continuously, with ONE disclosed scripted interlude: while
           (a) the mission_end latch is NOT set, (b) the player is in
           the D7 zone (px >= 1100 / d7_zone / section_pinned), and
           (c) the chopper (st 0xAA94/0xABDC, hp_a4 > 0) is close
           (|dx| <= 60) with grenades > 0, run the J1 throw cycle until
           CHOPPER_GONE.  Every cycle is JSONL-logged (dx/h/hpA4/gren).
           Guards: any (0,*) or 0xC walker reading or px < 900 aborts
           the interlude immediately (the fragile end-sequence window);
           a global 80-throw cap; deaths are real and disclosed.
           After the banner PASS: post-banner observation phases
           W (no-input watch), S (START taps + RIGHT ownership probe),
           Q (quiet watch) — the 0-lives run showed CONTINUE? here
           (S5-F3); with lives remaining the M2-entry question is
           answered by flags 0xFF + px advancing under RIGHT ONLY.

NOT claimed: policy-alone status for the chopper kill (it is a
disclosed scripted interlude; a policy-layer integration is the
follow-up if the variant proves out).  Mission 2 gameplay is claimed
only through the proven predicate.

ONE boot per process (the proven in-process constraint): one run per
invocation; loop invocations for repeats.

Evidence: JSONL + report_*.json + PNGs under evidence/issue5_lives_variant/.
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

from ps1play import labconfig
from issue4_controller import boot
import ps1play.agent.combat as combat
from e2e_policy_trial import (snap, alive, px_of, banner_confirmed,
                              sha_file, DISC, GRENADES, PLAYER_HP,
                              OPEN_CHUNK, ZONE_CHUNK, ZONE_ENTER_PX,
                              DEEP_PX, RESTART_MIN_C, WALL_GUARD_S)

EVID = os.path.join(labconfig.resolve_path("evidence_dir"),
                    "issue5_lives_variant")
LIVES_A = 0x0475A8         # gsmap "Extra Lives -> P1 life count" —
                           # liveness RE-tested this session (task-13
                           # said not-live; verify against the HUD)
CHOPPER_ST = (0xAA94, 0xABDC)
CK_THROW_CAP = 80          # global throws per run (runaway guard)
CK_CLOSE_DX = 160.0        # interlude engage band (the session-3
                           # anchor protocol; J1 CONNECTS at |dx| 7-29)
CK_THROW_DX = 45.0         # throw only inside this band (the connect
                           # band 7-29 + a small hedge); farther = wait
CK_WAIT_MAX = 20           # 15f quiet waits per invocation while the
                           # chopper closes in (it tracks the player)
CK_MAX_CYCLES = 40         # throw cycles per interlude invocation


def log(*a):
    print("[lbv]", *a, file=sys.stderr, flush=True)


def lives(m):
    return int(m.u16(LIVES_A))


def png(p, name, tag):
    try:
        rgb = p.core.frame_rgb()
        if rgb is not None:
            from PIL import Image
            Image.fromarray(rgb).save(os.path.join(
                EVID, f"{tag}_{name}.png"))
    except Exception as e:                                  # noqa: BLE001
        log("png failed:", repr(e)[:120])


def raw_slots(m, n=36):
    """36-slot entity scan (session-3 F5: the truck lived at slot 33,
    OUTSIDE the historical 24-slot window)."""
    tv = m.ram[combat.TABLE:combat.TABLE + n * combat.STRIDE].view(
        "<u2").astype(np.int32).reshape(n, combat.STRIDE // 2)
    return [{"s": s, "st": int(tv[s, 0]),
             "x": round(((int(tv[s, 61]) << 16) | int(tv[s, 60]))
                        / 65536.0, 1), "h": int(tv[s, 63]),
             "hpA4": int(tv[s, 82])}
            for s in range(1, n)
            if int(tv[s, 0]) or ((int(tv[s, 61]) << 16)
                                 | int(tv[s, 60]))]


def chopper(m, px):
    best = None
    for sl in raw_slots(m):
        if sl["st"] in CHOPPER_ST and sl["hpA4"] > 0:
            d = abs(sl["x"] - px)
            if best is None or d < best[0]:
                best = (d, sl)
    return best[1] if best else None


def chopper_interleave(p, m, J, pol, tag, throw_state):
    """The proven session-3 J1 recipe (hop -> UP+A lob at the apex,
    facing the chopper), executed ONLY before the mission_end latch.
    Returns (status, cycles): gone | end_window | no_ammo | dead |
    exhausted | never_close | throw_cap."""
    hp_prev = None
    waits = 0
    for k in range(CK_MAX_CYCLES + CK_WAIT_MAX):
        if throw_state["throws"] >= CK_THROW_CAP:
            J({"ev": "CK_THROW_CAP", **snap(m)})
            return "throw_cap", k
        if not alive(m):
            J({"ev": "CK_DEATH", "cycle": k})
            return "dead", k
        s = snap(m)
        if s["px"] < 900.0 or s["sec"][0] in (0, 0xC):
            # the fragile end-sequence window opened (the walker reset
            # (0,8) / the 0xC banner): NO inputs — abort at once
            J({"ev": "CK_ABORT_END_WINDOW", "cycle": k, **s})
            return "end_window", k
        px = px_of(m)
        ch = chopper(m, px)
        if ch is None or ch["hpA4"] <= 0:
            J({"ev": "CHOPPER_GONE", "cycle": k, "throws":
               throw_state["throws"], **s, "slots": raw_slots(m)})
            log(f"CHOPPER GONE cycle {k} score={s['score']}")
            return "gone", k
        if int(m.u8(GRENADES)) <= 0:
            J({"ev": "CK_NO_AMMO", "cycle": k, **s})
            return "no_ammo", k
        if abs(ch["x"] - px) > CK_THROW_DX:
            # close-in wait: the chopper tracks an ACTING player; a
            # brief quiet window lets it drift into the connect band
            # (waits are bounded; the abort guards re-run next loop)
            waits = waits + 1 if waits < CK_WAIT_MAX else waits
            if waits >= CK_WAIT_MAX:
                J({"ev": "CK_NEVER_CLOSE", "cycle": k,
                   "dx": round(ch["x"] - px, 1), **s})
                return "never_close", k
            p.core.run(15, set())
            J({"ev": "CK_WAIT", "cycle": k, "waits": waits,
               "dx": round(ch["x"] - px, 1), "h": ch["h"],
               "hpA4": ch["hpA4"], **snap(m)})
            continue
        d = "RIGHT" if ch["x"] >= px else "LEFT"
        p.core.run(3, {"B"})                # hop
        p.core.run(8, set())
        p.core.run(8, {"UP", "A", d})       # UP-lob at the apex
        p.core.run(25, set())
        throw_state["throws"] += 1
        s2 = snap(m)
        chn = chopper(m, px_of(m))
        ev = {"ev": "CK_CYCLE", "cycle": k, "dx": round(ch["x"] - px, 1),
              "h_before": ch["h"], "hpA4_before": ch["hpA4"],
              "hpA4_after": chn["hpA4"] if chn else 0,
              "dir": d, "score": s2["score"], "gren": s2["gren"],
              "px": s2["px"], "sec": s2["sec"]}
        J(ev)
        if chn is None or chn["hpA4"] <= 0:
            J({"ev": "CHOPPER_KILLED", "cycles": k + 1,
               "throws": throw_state["throws"], **s2,
               "slots": raw_slots(m)})
            log(f"CHOPPER KILLED cycles={k + 1} "
                f"throws={throw_state['throws']} score={s2['score']}")
            return "gone", k + 1
        if hp_prev is not None and chn["hpA4"] < hp_prev:
            J({"ev": "CHOPPER_HP_DROP", "from": hp_prev,
               "to": chn["hpA4"], "cycle": k})
            log(f"CHOPPER HP DROP {hp_prev}->{chn['hpA4']}")
        hp_prev = chn["hpA4"]
    J({"ev": "CK_EXHAUSTED", "max_cycles": CK_MAX_CYCLES, **snap(m)})
    return "exhausted", CK_MAX_CYCLES


def gameplay_probe(p, m, J, tag, label):
    """The ONLY admissible M2-gameplay predicate: flags 0xFF, px in a
    valid window, and the player ADVANCES under RIGHT (ownership)."""
    if not (snap(m)["flags"] == 0xFF):
        return False
    px0 = px_of(m)
    if not 60.0 < px0 < 4096.0:
        return False
    p.core.run(90, {"RIGHT"})
    s2 = snap(m)
    moved = round(px_of(m) - px0, 1)
    J({"ev": "RIGHT_PROBE", "label": label, "from_px": px0,
       "moved_px": moved, **s2})
    png(p, f"{label}_right", tag)
    if moved > 8.0 and s2["flags"] == 0xFF:
        # RAW observation only — interpretation (mission-1 continue
        # resume vs mission-2 gameplay) happens in the report: the
        # 0-lives branch resumes at px 992 (the mission-1 wave zone,
        # session-5 S5-F3) and ALSO advances under RIGHT.
        J({"ev": "GAMEPLAY_AFTER_BANNER", "label": label, **s2})
        log(f"GAMEPLAY AFTER BANNER ({label}) moved {moved}px "
            f"px={s2['px']} sec={s2['sec']}")
        return True
    return False


def walk_forward(p, m, J, tag, chunks=120):
    """Phase M — the mission-2 entry question, answered by WALKING:
    after the continue-accept resumes gameplay, hold RIGHT (real
    inputs, disclosed scripted probe) and watch for a mission
    transition (scene/flags change, px reset, NOW LOADING)."""
    trans = []
    for i in range(chunks):
        p.core.run(30, {"RIGHT"})
        s = snap(m)
        ev = {"ev": "M", "i": i, "px": s["px"], "sec": s["sec"],
              "flags": s["flags"], "score": s["score"],
              "lives": lives(m), "php": s["php"], "gren": s["gren"]}
        if s["flags"] != 0xFF or s["px"] < 100.0 or s["px"] > 5000.0:
            trans.append(ev)
            J({**ev, "note": "anomaly_paused"})
            png(p, f"M{i:03d}", tag)
            p.core.run(60, set())      # let a transition play out
        elif i % 10 == 0:
            J(ev)
        if i % 15 == 0:
            png(p, f"M{i:03d}", tag)
        if not alive(m):
            J({"ev": "M_DEATH", "i": i, "lives": lives(m), **snap(m)})
            png(p, "M_death", tag)
            for w in range(60):
                p.core.run(30, set())
                if alive(m):
                    break
    fin = snap(m)
    rec = {"chunks": chunks, "transitions": trans, "final": fin,
           "final_lives": lives(m)}
    J({"ev": "M_done", **{k: rec[k] for k in
                          ("chunks", "final", "final_lives")},
       "n_transitions": len(trans)})
    png(p, "M_final", tag)
    return rec


def post_banner_watch(p, m, J, tag, deaths):
    """Post-banner flow with the lives proxy = in-run deaths (0 deaths
    here vs the 0-lives CONTINUE? branch of session-5 S5-F3).
    Phases: W no-input watch (auto-advance?), S START taps, Q quiet."""
    for w in range(6):
        p.core.run(150, set())
        s = snap(m)
        J({"ev": "W", "step": w, "deaths": deaths, "lives": lives(m),
           **s})
        png(p, f"W{w}", tag)
        log(f"W{w}: px={s['px']} sec={s['sec']} flags={s['flags']} "
            f"score={s['score']}")
        if s["flags"] == 0xFF and 60.0 < s["px"] < 4096.0:
            if gameplay_probe(p, m, J, tag, f"W{w}"):
                walk = walk_forward(p, m, J, tag)
                return {"result": "gameplay_seen", "walk": walk}
    for k in range(4):
        p.core.run(12, {"START"})
        p.core.run(300, set())
        s = snap(m)
        J({"ev": "S", "tap": k + 1, "deaths": deaths, **s})
        png(p, f"S{k + 1}", tag)
        log(f"S{k + 1}: px={s['px']} sec={s['sec']} "
            f"flags={s['flags']} score={s['score']}")
        if s["flags"] == 0xFF and 60.0 < s["px"] < 4096.0:
            if gameplay_probe(p, m, J, tag, f"S{k + 1}"):
                walk = walk_forward(p, m, J, tag)
                return {"result": "gameplay_seen", "walk": walk}
    for q in range(4):
        p.core.run(300, set())
        s = snap(m)
        J({"ev": "Q", "step": q, **s})
        png(p, f"Q{q}", tag)
        if s["flags"] == 0xFF and 60.0 < s["px"] < 4096.0:
            if gameplay_probe(p, m, J, tag, f"Q{q}"):
                walk = walk_forward(p, m, J, tag)
                return {"result": "gameplay_seen", "walk": walk}
    return {"result": "no_gameplay_seen", "walk": None}


def run_variant(p, m, J, tag, chunks, diag=False):
    """One continuous policy run with the disclosed chopper interlude.
    Mirrors e2e_policy_trial.run_once (the proven loop) + the gate."""
    pol = combat.CombatPolicy()
    last_px, last_segs = None, None
    outcome, end_c, deaths = None, None, 0
    was_deep, deep_c = False, 0
    throw_state = {"throws": 0}
    ck = {"status": None, "kills": 0, "throws": 0, "cycles": 0}
    t0 = time.time()
    for c in range(chunks):
        if time.time() - t0 > WALL_GUARD_S:
            outcome = outcome or "wall_guard"
            log("wall guard hit at chunk", c)
            break
        s = snap(m)
        if not alive(m):
            # death-frame forensics: PNG burst + full slot dump + the
            # lives word (the c42 event identity question)
            J({"ev": "death", "chunk": c, "lives_before": 
               getattr(run_variant, "_last_lives", None), **s,
               "slots": raw_slots(m)})
            log(f"death #{deaths} c{c} px={s['px']} php={s['php']} "
                f"lives={lives(m)}")
            for i, f in enumerate((0, 10, 10, 20, 40)):
                if f:
                    p.core.run(f, set())
                png(p, f"death_f{i}", tag)
                J({"ev": "death_frame", "i": i, "lives": lives(m),
                   **snap(m)})
            deaths += 1
            got = False
            for w in range(100):            # ~3000f respawn budget
                p.core.run(30, set())
                if alive(m):
                    got = True
                    break
            if not got:
                png(p, "gameover", tag)
                outcome = "death_no_respawn"
                J({"ev": "DEAD_END", "chunk": c, "lives": lives(m),
                   **snap(m)})
                break
            if diag:
                outcome = "diag_death_reached"
                J({"ev": "DIAG_STOP", "chunk": c, "lives": lives(m)})
                break
            last_px, last_segs = None, None
            continue
        px_early = px_of(m)
        if px_early > 5000.0:
            # mission-transition garbage (u32 reads 0xFFFF_xxxx while
            # the world rebuilds): skip chunk
            p.core.run(60, set())
            continue
        sec = combat.scan_section(m)
        pol.observe_section(sec, px_now=px_early)
        px = px_of(m)
        if px > DEEP_PX:
            was_deep = True
            deep_c = 0
        else:
            deep_c += 1
        advanced = 0.0 if last_px is None else px - last_px
        intent = any("RIGHT" in (x.get("btns") or set())
                     for x in (last_segs or []))
        pol.observe(px, advanced, intent)
        scan = combat.scan_entities(m, px=px)
        # ---- session-6 interlude gate (disclosed, pre-trigger-B) ----
        if (not pol.mission_end and
                (pol.d7_zone or pol.section_pinned or
                 px >= ZONE_ENTER_PX)):
            ch = chopper(m, px)
            if ch is not None:
                # census: the chopper dynamics inside the D7 zone are
                # the session-6 unknown (why run 1 never engaged)
                J({"ev": "ck_scan", "chunk": c,
                   "dx": round(ch["x"] - px, 1), "h": ch["h"],
                   "hpA4": ch["hpA4"], "st": ch["st"], **snap(m),
                   "slots": raw_slots(m)})
            else:
                # full-slot census in the zone: identify the ACTUAL
                # faller-rain source (run 1/2: ZERO chopper-st rows —
                # the session-5 attribution needs re-derivation)
                J({"ev": "zone_census", "chunk": c, **snap(m),
                   "slots": raw_slots(m)})
            if ch is not None and ch["hpA4"] > 0 and \
                    abs(ch["x"] - px) <= CK_CLOSE_DX and \
                    int(m.u8(GRENADES)) > 0:
                J({"ev": "CK_ENGAGE", "chunk": c, "chopper": ch,
                   **snap(m)})
                st, cyc = chopper_interleave(p, m, J, pol, tag,
                                             throw_state)
                ck["status"], ck["cycles"] = st, ck["cycles"] + cyc
                if st == "gone":
                    ck["kills"] += 1
                    png(p, "chopper_down", tag)
                ck["throws"] = throw_state["throws"]
                last_px, last_segs = None, None
                if st == "dead":
                    continue
                if st == "end_window":
                    # feed the observed walker reading so the policy
                    # latches mission_end (trigger-B / 0xC) this chunk
                    sec2 = combat.scan_section(m)
                    pol.observe_section(sec2, px_now=px_of(m))
                continue
        cf = ZONE_CHUNK if (pol.d7_zone or pol.section_pinned or
                            px >= ZONE_ENTER_PX) else OPEN_CHUNK
        segs = pol.decide(cf, px, scan,
                          grenades=int(m.u8(GRENADES)),
                          hp=int(m.u16(PLAYER_HP)))
        last_px, last_segs = px, segs
        for x in segs:
            p.core.run(x["frames"], x["btns"] or set())
        s2 = snap(m)
        J({"ev": "chunk", "c": c, "cf": cf, "mode": pol.mode, **s2,
           "n": len(scan), "deaths": deaths, "lives": lives(m),
           "pinned": pol.section_pinned, "d7": pol.d7_zone,
           "me": pol.mission_end})
        if pol.mission_end and c % 2 == 0:
            # hold census: who is actually raining death on the
            # standing player (the c43 killer identity question)
            J({"ev": "hold_census", "c": c, **s2,
               "slots": raw_slots(m)})
        if c % 250 == 0:
            png(p, f"c{c:05d}", tag)
            log(f"c{c} px={s2['px']} mode={pol.mode} sec={s2['sec']} "
                f"score={s2['score']} gren={s2['gren']} "
                f"deaths={deaths}")
        # ---- PASS: the MISSION 1 banner (the hardened predicate) ----
        if (s2["sec"][0] == 0xC and 10.0 <= s2["px"] <= 60.0
                and was_deep and pol.mission_end):
            ok, s3 = banner_confirmed(p, m)
            if ok:
                outcome = "MISSION_BANNER"
                end_c = c
                png(p, "mission_banner", tag)
                J({"ev": "MISSION_BANNER", "chunk": c, "deaths": deaths,
                   **s3})
                log(f"MISSION BANNER c={c} px={s3['px']} "
                    f"score={s3['score']} deaths={deaths} "
                    f"(lives remaining = {deaths == 0})")
                break
            J({"ev": "TRANSIENT_REJECTED", "chunk": c, **s2,
               "after_quiet": s3})
        # ---- banner expired into a mission restart (FAIL) ----
        if (was_deep and deep_c > RESTART_MIN_C and
                s2["px"] < 200.0 and s2["sec"][0] in (0xB, 0) and
                not pol.mission_end):
            outcome = "banner_expired_restart"
            end_c = c
            png(p, "restart", tag)
            J({"ev": "RESTART_SEEN", "chunk": c, **s2})
            log(f"RESTART c={c} px={s2['px']} sec={s2['sec']}")
            break
    rec = {"outcome": outcome or "budget", "end_chunk": end_c,
           "deaths": deaths, "was_deep": was_deep,
           "chopper_interlude": ck,
           "pol_stats": {k: v for k, v in pol.stats.items() if v},
           "final": snap(m), "wall_s": round(time.time() - t0, 1)}
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", type=int, default=1)
    ap.add_argument("--chunks", type=int, default=2600)
    ap.add_argument("--skip_post", action="store_true",
                    help="stop at the banner (no W/S/Q phases)")
    ap.add_argument("--diag", action="store_true",
                    help="diagnostic: census only, abort at the death")
    args = ap.parse_args()
    os.makedirs(EVID, exist_ok=True)
    tag = f"lives{args.run}_{time.strftime('%H%M%S')}"
    jf = open(os.path.join(EVID, f"{tag}.jsonl"), "w")

    def J(ev):
        jf.write(json.dumps(ev, default=str) + "\n")
        jf.flush()

    t0 = time.time()
    p, fw = boot()
    m = p.mem
    J({"ev": "boot", "arm": "variant", "run": args.run,
       "firmware": fw, "lives": lives(m), **snap(m)})
    log(f"=== variant run {args.run}: booted ({fw}) ===")
    rec = run_variant(p, m, J, tag, args.chunks,
                      diag=args.diag)
    J({"ev": "e2e_result", **{k: rec[k] for k in
                              ("outcome", "end_chunk", "deaths",
                               "chopper_interlude")}})
    post = None
    if rec["outcome"] == "MISSION_BANNER" and not args.skip_post:
        post = post_banner_watch(p, m, J, tag, rec["deaths"])
        J({"ev": "post_banner", "result": post})
        log("post-banner:", post)
    rec.update({"arm": "variant", "run": args.run, "firmware": fw,
                "post_banner": post,
                "wall_total_s": round(time.time() - t0, 1),
                "frames": p.core.frames_run,
                "game_sha256": sha_file(DISC)})
    with open(os.path.join(EVID, f"report_{tag}.json"), "w") as f:
        json.dump(rec, f, indent=1, default=str)
    J({"ev": "RUN_DONE", **rec})
    jf.close()
    log(f"RUN lives{args.run}: {rec['outcome']} c={rec['end_chunk']} "
        f"deaths={rec['deaths']} ck={rec['chopper_interlude']} "
        f"post={post} wall={rec['wall_total_s']}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
