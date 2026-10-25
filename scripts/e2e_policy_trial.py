#!/usr/bin/env python3
"""e2e_policy_trial.py — Issue #5 session 5: END-TO-END Mission 1 clear
under the SHIPPED plugin policy alone, from a fresh real-play boot.

Session-4 (issuecomment-6396831997 §5) named this the single
highest-value next action: "one paired trial from a fresh boot would
upgrade 'Mission 1 completable' into 'Mission 1 cleared by the policy
end-to-end'".

Arms:
  e2e      boot() -> fresh mission start (px ~26) -> the shipped
           CombatPolicy (session-4 patch) CONTINUOUSLY to the
           MISSION 1 banner.  No savestate loads, no checkpoint saves,
           no scripted inputs inside the claimed run; the real grenade
           count is passed (the proven anti-armor escalation).
  control  the session-4 checkpoint arm re-run on THIS machine:
           pin_ckpt -> the same shipped policy -> banner (was_deep
           from the first chunk, like policy_chain_trial).

Cadence (both arms): 60f chunks on the open walk (the proven reach
cadence, sessions 3/4) switching to 15f micro-chunks inside the D7
zone (the session-4 pre-banner lesson — a 60f segment of inputs can
skip the banner mid-chunk).

PASS = walker state 0xC in the mission-start px window [10, 60]
(observer 26.4; the mid-cycle transient observed at px 3.4 is
excluded) AND the mission_end latch AND a confirm-after-quiet re-read
(60f no input; the banner persists, transients move on).  A PNG is
saved at every PASS and visually verified before any claim.  Deaths
are real and disclosed (in-place respawn waits only); a game-over
screen (flags word 0x1) with no respawn = FAIL death_no_respawn (no
rescue inside the claimed run).

Control arm protocol = session-4 policy_chain_trial EXACTLY: a no-
input pre-wait for the pin-cycle warp to px < 1100 (k<=60) BEFORE the
policy loop; the e2e arm starts at the mission spawn and needs no
pre-wait (was_deep gates every end-sequence predicate).

ONE boot per process (the proven in-process constraint): run one arm
per invocation; loop invocations for repeats.

Evidence: JSONL per run + PNGs + report_<arm>_<ts>.json under
evidence issue5_e2e_trial/ with disc sha256.
"""
import argparse
import hashlib
import json
import os
import sys
import time

_REPO = "/home/z/my-project/ps1ai"
for _p in (_REPO, os.path.join(_REPO, "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _REPO)

from ps1play import labconfig
from issue4_controller import boot
import ps1play.agent.combat as combat

PLAYER_X = combat.PLAYER_X                # 0x0CA2E0
A_SCORE = 0x0EE318
GRENADES = 0x0EDCF4
PLAYER_HP = 0x0CA2F6
FLAGS_WORD = 0x0EE518
DISC = "/home/z/my-project/emu/game/Metal Slug X (USA).bin"
EVID = os.path.join(labconfig.resolve_path("evidence_dir"),
                    "issue5_e2e_trial")
OPEN_CHUNK = 60                           # open-walk cadence (reach walks)
ZONE_CHUNK = 15                           # D7-zone cadence (session-4)
ZONE_ENTER_PX = 1100.0                    # pre-switch margin (latch 1150)
DEEP_PX = 500.0                           # was_deep threshold
RESTART_MIN_C = 20                        # chunks since deep before restart
                                          # predicate may fire
WALL_GUARD_S = 9.5 * 60


def log(*a):
    print("[e2e]", *a, file=sys.stderr, flush=True)


def sha_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def px_of(m):
    return int(m.u32(PLAYER_X)) / 65536.0


def snap(m):
    return {"px": round(px_of(m), 1), "score": int(m.u32(A_SCORE)),
            "gren": int(m.u8(GRENADES)),
            "php": int(m.u16(PLAYER_HP)),
            "flags": int(m.u32(FLAGS_WORD)) & 0xFF,
            "sec": (int(m.u16(combat.SECTION_STATE)),
                    int(m.u16(combat.SECTION_FLAGS))),
            "prog": int(m.u16(combat.SECTION_PROGRESS))}


def alive(m):
    s = snap(m)
    return (s["flags"] == 0xFF and s["px"] != 0.0 and s["php"] > 0)


def png(p, name, tag):
    try:
        rgb = p.core.frame_rgb()
        if rgb is not None:
            from PIL import Image
            Image.fromarray(rgb).save(os.path.join(EVID,
                                                  f"{tag}_{name}.png"))
    except Exception as e:                                  # noqa: BLE001
        log("png failed:", repr(e)[:120])


def warp_prewait(p, m, J):
    """Session-4 protocol: no-input wait for the pin-cycle warp to the
    wave zone (px < 1100, k<=60 x 30f, proven).  Running policy inputs
    during the cycle disturbed it (control1: a transient (0xC,9)@px3.4
    fired the pass predicate with gameplay on screen)."""
    for k in range(60):
        s = snap(m)
        if not alive(m):
            for w in range(60):
                p.core.run(30, set())
                if alive(m):
                    break
            continue
        if s["px"] < 1100.0:
            J({"ev": "WARP", "k": k, **s})
            return True
        p.core.run(30, set())
    J({"ev": "NO_WARP", **snap(m)})
    return False


def banner_confirmed(p, m):
    """Confirm-after-quiet: 60f no input, then the (0xC, px-window)
    signature must persist (the real banner does; transients move on)."""
    p.core.run(60, set())
    s3 = snap(m)
    return (s3["sec"][0] == 0xC and 10.0 <= s3["px"] <= 60.0), s3


def run_once(p, m, J, tag, chunks, control):
    """One continuous policy run.  Returns the run record dict."""
    pol = combat.CombatPolicy()
    last_px, last_segs = None, None
    outcome, end_c, deaths = None, None, 0
    was_deep = bool(control)          # control starts at the pin (deep)
    deep_c = 0                        # chunks since was_deep went True
    t0 = time.time()
    if control:
        if not warp_prewait(p, m, J):
            return {"outcome": "no_warp", "end_chunk": None,
                    "deaths": 0, "was_deep": was_deep,
                    "pol_stats": {}, "final": snap(m),
                    "wall_s": round(time.time() - t0, 1)}
        last_px = None                # fresh observation baseline
    for c in range(chunks):
        if time.time() - t0 > WALL_GUARD_S:
            outcome = outcome or "wall_guard"
            log("wall guard hit at chunk", c)
            break
        s = snap(m)
        if not alive(m):
            deaths += 1
            J({"ev": "death", "chunk": c, **s})
            log(f"death #{deaths} c{c} px={s['px']} php={s['php']}")
            got = False
            for w in range(100):        # ~3000f respawn budget
                p.core.run(30, set())
                if alive(m):
                    got = True
                    break
            if not got:
                png(p, "gameover", tag)
                outcome = "death_no_respawn"
                J({"ev": "DEAD_END", "chunk": c, **snap(m)})
                break
            last_px, last_segs = None, None
            continue
        px_early = px_of(m)
        if px_early > 5000.0:
            # mission-transition garbage (u32 reads 0xFFFF_xxxx while
            # the world rebuilds — session-4 trial c=14): skip chunk
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
           "n": len(scan), "deaths": deaths,
           "pinned": pol.section_pinned, "d7": pol.d7_zone,
           "me": pol.mission_end})
        if c % 250 == 0:
            png(p, f"c{c:05d}", tag)
            log(f"c{c} px={s2['px']} mode={pol.mode} sec={s2['sec']} "
                f"score={s2['score']} gren={s2['gren']} "
                f"deaths={deaths}")
        # ---- PASS: the MISSION 1 banner (hardened) ----
        # state 0xC + the mission-start px window [10,60] (observer
        # 26.4; the mid-cycle transient sat at px 3.4) + the mission_end
        # latch + was_deep, then confirm-after-quiet.
        if (s2["sec"][0] == 0xC and 10.0 <= s2["px"] <= 60.0
                and was_deep and pol.mission_end):
            ok, s3 = banner_confirmed(p, m)
            if ok:
                outcome = "MISSION_BANNER"
                end_c = c
                png(p, "mission_banner", tag)
                J({"ev": "MISSION_BANNER", "chunk": c, **s3})
                log(f"MISSION BANNER c={c} px={s3['px']} "
                    f"score={s3['score']} deaths={deaths}")
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
    return {"outcome": outcome or "budget", "end_chunk": end_c,
            "deaths": deaths, "was_deep": was_deep,
            "pol_stats": {k: v for k, v in pol.stats.items() if v},
            "final": snap(m),
            "wall_s": round(time.time() - t0, 1)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", default="e2e",
                    choices=["e2e", "control"])
    ap.add_argument("--run", type=int, default=1)
    ap.add_argument("--chunks", type=int, default=2600)
    args = ap.parse_args()
    os.makedirs(EVID, exist_ok=True)
    tag = (f"{args.arm}{args.run}_{time.strftime('%H%M%S')}")
    jf = open(os.path.join(EVID, f"{tag}.jsonl"), "w")

    def J(ev):
        jf.write(json.dumps(ev, default=str) + "\n")
        jf.flush()

    t0 = time.time()
    p, fw = boot()
    m = p.mem
    J({"ev": "boot", "arm": args.arm, "run": args.run,
       "firmware": fw, **snap(m)})
    log(f"=== arm {args.arm} run {args.run}: booted ({fw}) "
        f"px={snap(m)['px']} ===")
    if args.arm == "control":
        p.load_state("pin_ckpt")
        J({"ev": "control_ckpt_loaded", **snap(m)})
        log(f"checkpoint loaded px={snap(m)['px']}")
    rec = run_once(p, m, J, tag, args.chunks,
                   control=(args.arm == "control"))
    rec.update({"arm": args.arm, "run": args.run, "firmware": fw,
                "wall_total_s": round(time.time() - t0, 1),
                "frames": p.core.frames_run,
                "game_sha256": sha_file(DISC)})
    J({"ev": "RUN_DONE", **rec})
    jf.close()
    with open(os.path.join(EVID, f"report_{tag}.json"), "w") as f:
        json.dump(rec, f, indent=1, default=str)
    log(f"RUN {args.arm}{args.run}: {rec['outcome']} "
        f"c={rec['end_chunk']} deaths={rec['deaths']} "
        f"wall={rec['wall_s']}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
