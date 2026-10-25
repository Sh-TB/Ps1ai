#!/usr/bin/env python3
"""chain_a_full.py — Issue #5 session 4: the COMPLETE release chain in
one run (arm A: fresh-boot pin, chopper inactive), run >=3x.

Reproduces + connects the session-3 proven segments end to end:
  1. pin_ckpt (px 1164, the D7 pin)
  2. the pin cycle warps the player to ~992 and spawns the wave
     (F9's "(0xA/0xB,0x43) cycle at px ~984" IS this warp+spawn)
  3. AIMED soldier clear — session-4 protocol (shp2/bpp): face 6f+4f,
     single 4f Y taps, corpse-flip verification, rescan; the wave
     soldier dies in 2 taps 3/3 (bpp).  ALSO answers session-3's
     "Y-bursts did not kill": those bursts fired from a stale facing
     (dx -92 = BEHIND the player).
  4. release wait (sec leaves the pin set / prog moves)  [F1]
  5. post-release policy walk with death handling until the
     MISSION 1 screen (sec 0xC + px < 200)               [F2] -> PNG

PASS = MISSION_SCREEN within the budget.  READ-ONLY instrumentation;
deaths are real; grenades untouched (bullets only).

Usage: python3 scripts/chain_a_full.py [--runs 3]
"""
import argparse
import json
import os
import sys
import time
import numpy as np
from PIL import Image

_REPO = "/home/z/my-project/ps1ai"
for _p in (_REPO, os.path.join(_REPO, "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _REPO)

from ps1play import labconfig
from issue4_controller import boot
import ps1play.agent.combat as combat

TABLE, STRIDE = combat.TABLE, combat.STRIDE
PLAYER_X = 0x0CA2E0
A_SCORE = 0x0EE318
GRENADES = 0x0EDCF4
PLAYER_HP = 0x0CA2F6
EVID = os.path.join(labconfig.resolve_path("evidence_dir"),
                    "issue5_chain_a")
DEAD_ST = (0x4BE4, 0x5CC8)
SOLDIER_FAMILY = (0x4054, 0x41FC)   # live wave-soldier states (v1:
                                    # slot12 cycled 0x4054<->0x41FC
                                    # with no input at all)
WAVE_LO, WAVE_HI = 1020.0, 1140.0


def log(*a):
    print("[ca]", *a, file=sys.stderr, flush=True)


def px_of(m):
    return int(m.u32(PLAYER_X)) / 65536.0


def snap(m):
    return {"px": round(px_of(m), 1), "score": int(m.u32(A_SCORE)),
            "flags": int(m.u32(0x0EE518)) & 0xFF,
            "gren": int(m.u8(GRENADES)),
            "php": int(m.u16(PLAYER_HP)),
            "sec": (int(m.u16(combat.SECTION_STATE)),
                    int(m.u16(combat.SECTION_FLAGS))),
            "prog": int.from_bytes(
                m.ram[0xEB5D4:0xEB5D8].tobytes(), "little")}


def raw_slots(m, n=36):
    tv = m.ram[TABLE:TABLE + n * STRIDE].view("<u2").astype(
        np.int32).reshape(n, STRIDE // 2)
    return [{"s": s, "st": int(tv[s, 0]),
             "x": round(((int(tv[s, 61]) << 16) | int(tv[s, 60]))
                        / 65536.0, 1), "h": int(tv[s, 63]),
             "hpA4": int(tv[s, 82])}
            for s in range(1, n)
            if int(tv[s, 0]) or ((int(tv[s, 61]) << 16)
                                 | int(tv[s, 60]))]


def wave_soldiers(m, px):
    """Live soldier-family slots in the wave window (state-agnostic
    within the observed family; corpses excluded)."""
    return [sl for sl in raw_slots(m)
            if WAVE_LO <= sl["x"] <= WAVE_HI and sl["h"] == 64
            and sl["st"] in SOLDIER_FAMILY]


def alive(m):
    return (int(m.u32(0x0EE518)) & 0xFF) == 0xFF and px_of(m) != 0.0


def st_of(m, slot):
    return int(m.ram[TABLE + slot * STRIDE:
                     TABLE + slot * STRIDE + 2].view("<u2")[0])


def x_of(m, slot):
    base = TABLE + slot * STRIDE + 0x78
    return int(m.ram[base:base + 4].view("<u4")[0]) / 65536.0


def png(p, name, tag):
    rgb = p.core.frame_rgb()
    if rgb is not None:
        Image.fromarray(rgb).save(os.path.join(EVID,
                                               f"{tag}_{name}.png"))


def wait_respawn(p, m, J, ev, k):
    for w in range(60):
        p.core.run(30, set())
        if alive(m):
            J({"ev": ev, "k": k, **snap(m)})
            return True
    return False


def phase_warp_to_992(p, m, J):
    """The pin cycle warps the player to ~992 and spawns the wave
    (release_advance phase 1, proven k=18)."""
    for k in range(60):
        s = snap(m)
        if not alive(m):
            if not wait_respawn(p, m, J, "respawn_warp", k):
                return False
            continue
        if s["px"] < 1100.0:
            J({"ev": "WARPED_TO_WAVE_ZONE", "k": k, **s})
            return True
        p.core.run(30, set())
    return False


def phase_finish(p, m, J, tag, rounds=240):
    """UNIFIED finish loop (v6 — latency fix).

    v5 lesson: the end sequence starts DURING the clear (the (0,8)
    reset appeared at the ZONE_CLEAR snap) and the (0xC,9) banner
    lives < 180f — the 3-empty-scan waits missed it every time.

    One tight loop, 10f granularity:
      * soldier-family slot visible  -> aimed tap (2 bullets kill;
        3 taps max, then re-acquire)
      * sec[0]==0xC and px<200       -> MISSION_BANNER (PASS)
      * else                         -> 10f idle
    Deaths handled inline.
    """
    kills = []
    seen_wave = False
    for rnd in range(rounds):
        if not alive(m):
            J({"ev": "death_finish", "rnd": rnd, **snap(m)})
            if not wait_respawn(p, m, J, "respawn_finish", rnd):
                return kills, False
            continue
        s = snap(m)
        if s["sec"][0] == 0xC and s["px"] < 200.0:
            J({"ev": "MISSION_BANNER", "rnd": rnd, **s})
            png(p, "mission_banner", tag)
            log(f"MISSION BANNER rnd={rnd} px={s['px']} "
                f"sec={s['sec']} score={s['score']}")
            return kills, True
        ws = wave_soldiers(m, px_of(m))
        if ws:
            seen_wave = True
            ws.sort(key=lambda e: abs(e["x"] - px_of(m)))
            slot = ws[0]["s"]
            dead = False
            for t in range(3):
                if not alive(m):
                    break
                px = px_of(m)
                tx = x_of(m, slot)
                d = "RIGHT" if tx >= px else "LEFT"
                p.core.run(6, {d})
                p.core.run(4, set())
                p.core.run(4, {"Y"})
                for w in range(6):          # 36f settle
                    p.core.run(6, set())
                    if st_of(m, slot) in DEAD_ST:
                        dead = True
                        break
                if dead:
                    break
            kills.append({"slot": slot, "taps": t + 1,
                          "dead": dead})
            J({"ev": "SOLDIER_RESULT", "slot": slot, "taps": t + 1,
               "dead": dead, **snap(m)})
            log(f"slot {slot}: taps={t + 1} dead={dead} "
                f"score={snap(m)['score']}")
            continue
        if seen_wave:
            # wave zone empty: 10f idle, watch for the sequence
            p.core.run(10, set())
        else:
            p.core.run(30, set())   # waiting for the wave to spawn
    return kills, False


PIN_STATES = ((0xA, 0x43), (0xB, 0x43), (0xB, 0x1), (0, 0),
              (0xA, 0x1), (0xB, 0x0))


def phase_release_wait(p, m, J):
    """Wait for the walker to leave the pin signature set."""
    for k in range(90):
        s = snap(m)
        if not alive(m):
            if not wait_respawn(p, m, J, "respawn_rel", k):
                return False
            continue
        if s["sec"] not in PIN_STATES and s["sec"] != (0xA, 0x0):
            J({"ev": "RELEASE", "k": k, **s, "slots": raw_slots(m)})
            log(f"RELEASE k={k} sec={s['sec']} prog={s['prog']:#x}")
            return True
        p.core.run(30, set())
    return False


def phase_banner_wait(p, m, J, tag, polls=90):
    """Mission-end sequence watch (v5 — the session-4 decode).

    v2 evidence (issue5_chain_a a1_102112 tally): after the wave
    clear the game runs the end sequence BY ITSELF —
      (0xB,0x1) @992 -> (0,8) reset -> (0xC,0x9) @ px 26.4
    and (0xC,8/9) with px < 200 is the MISSION 1 banner + PRESS
    START (release_confirm's own detector; my v2 tally watch FIRED
    SEC_0xC_SEEN + RESTART at k=8 without recognising it).  Walking
    during the countdown (v3/v4) expired it into a restart.

    NO INPUT.  PASS = (sec[0]==0xC and px<200) — the banner.  PNG
    every 30f for the visual record.
    """
    seq = []
    for k in range(polls):
        p.core.run(30, set())
        s = snap(m)
        seq.append({"k": k, **s})
        if k % 2 == 0:
            png(p, f"b{k:03d}", tag)
        J({"ev": "banner_wait", **{**s, "k": k}})
        if s["sec"][0] == 0xC and s["px"] < 200.0:
            J({"ev": "MISSION_BANNER", "k": k, **s})
            png(p, "mission_banner", tag)
            log(f"MISSION BANNER k={k} px={s['px']} sec={s['sec']} "
                f"score={s['score']}")
            return seq, True
        if not alive(m):
            J({"ev": "death_banner_wait", "k": k, **s})
    return seq, False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=3)
    args = ap.parse_args()
    os.makedirs(EVID, exist_ok=True)
    t0 = time.time()
    results = []
    p, fw = boot()
    m = p.mem
    for r in range(args.runs):
        tag = time.strftime(f"a{r + 1}_%H%M%S")
        jf = open(os.path.join(EVID, f"{tag}.jsonl"), "w")

        def J(ev):
            jf.write(json.dumps(ev, default=str) + "\n")
            jf.flush()

        p.load_state("pin_ckpt")
        J({"ev": "start", "run": r + 1, **snap(m)})
        log(f"=== run {r + 1}/{args.runs} ===")
        ok = phase_warp_to_992(p, m, J)
        kills, mission = ([], False)
        if ok:
            kills, mission = phase_finish(p, m, J, tag)
        png(p, "final", tag)
        res = {"run": r + 1, "warp": ok, "kills": kills,
               "mission_banner": mission, "final": snap(m)}
        results.append(res)
        J({"ev": "RUN_DONE", **res})
        jf.close()
        log(f"RUN {r + 1}: warp={ok} kills={len(kills)} "
            f"banner={mission}")
        if mission and r + 1 >= 3:
            break

    rep = {"schema": "issue5/chain-a-full/1", "runs": results,
           "wall_s": round(time.time() - t0, 1), "firmware": fw,
           "game_sha256":
               "45cde149878fe945d0219fd0f61ca09856aee66bdcc9119de21c0583f1d0667d"}
    with open(os.path.join(EVID, f"report_{int(t0)}.json"), "w") as f:
        json.dump(rep, f, indent=1, default=str)
    log("ALL DONE", json.dumps([{k: r[k] for k in
                                 ("run", "warp", "mission_banner")}
                                for r in results]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
