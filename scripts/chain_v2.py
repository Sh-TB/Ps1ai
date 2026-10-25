#!/usr/bin/env python3
"""chain_v2.py — Issue #5 session 4, experiment S2: the FULL chain with
the facing fix, run >=3x (paired vs session-3 chopper_chain).

Session-3 F9 (BLOCKED): chopper dead (19 throws) + soldiers dead +
truck dead still left the walker cycling (0xA/0xB,0x43) with one
residual 0x4054 at 1072 "that Y-bursts did not kill".

Session-4 evidence so far (issue5_soldier_hp/):
  shp2  : 2 aimed bullets kill the wave soldier (facing FIXED — the
          session-3 bursts fired 24f of Y after a 6f turn tap, but the
          tracked soldier was often BEHIND the player at dx -92..-120:
          tap direction was computed from a stale/anim-cycled row).
  bpp x3: deterministic 2-tap kills; walker releases to (0xB,0x1),
          px 992, prog 0xFFFFFFFF 3/3 from the fresh pin_ckpt.

v2 chain (one run = one paired trial):
  pin_ckpt -> J1 hop+apex UP-lobs until the chopper dies (proven
  recipe) -> AIMED soldier clear (face-corrected, single Y taps with
  corpse-flip verification, grenade escalation) -> walker watch to
  sec 0xC / mission screen (px < 200) -> PNG.

PASS = mission screen within the budget. BLOCKED = walker still
cycles after all reachable foes are dead (the difference matrix is
real; next probe: the queue-walker node list 0x800EB5F8).

Usage: python3 scripts/chain_v2.py [--runs 3]
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
                    "issue5_chain_v2")
DEAD_ST = (0x4BE4, 0x5CC8)
CHOPPER_ST = (0xAA94, 0xABDC)
WAVE_LO, WAVE_HI = 1030.0, 1130.0


def log(*a):
    print("[c2]", *a, file=sys.stderr, flush=True)


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


def chopper(m, px):
    best = None
    for sl in raw_slots(m):
        if sl["st"] in CHOPPER_ST and sl["hpA4"] > 0:
            d = abs(sl["x"] - px)
            if best is None or d < best[0]:
                best = (d, sl)
    return best[1] if best else None


def wave_soldiers(m, px):
    return [sl for sl in raw_slots(m)
            if WAVE_LO <= sl["x"] <= WAVE_HI and sl["h"] == 64
            and sl["st"] not in DEAD_ST]


def alive(m):
    return (int(m.u32(0x0EE518)) & 0xFF) == 0xFF and px_of(m) != 0.0


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


def kill_chopper(p, m, J, tag):
    """J1 recipe from chopper_chain phase K. Returns throws used."""
    throws = 0
    for k in range(150):
        if not alive(m):
            J({"ev": "death_kill", "k": k, **snap(m)})
            if not wait_respawn(p, m, J, "respawn_kill", k):
                return throws, False
            continue
        px = px_of(m)
        ch = chopper(m, px)
        if ch is None:
            J({"ev": "CHOPPER_DEAD", "k": k, "throws": throws,
               **snap(m), "slots": raw_slots(m)})
            log(f"CHOPPER DEAD k={k} throws={throws} "
                f"score={snap(m)['score']}")
            return throws, True
        dx = ch["x"] - px
        if int(m.u8(GRENADES)) == 0:
            p.core.run(30, set())
            continue
        if abs(dx) > 34:
            target = ch["x"] - (15 if ch["x"] >= px else -15)
            d = "RIGHT" if target > px else "LEFT"
            p.core.run(8, {d})
            p.core.run(6, set())
            continue
        d = "RIGHT" if dx >= 0 else "LEFT"
        p.core.run(3, {"B"})
        p.core.run(8, set())
        p.core.run(8, {"UP", "A", d})
        p.core.run(25, set())
        throws += 1
        J({"ev": "throw", "k": k, "dx": round(dx, 1), "ch": ch,
           **snap(m)})
    return throws, False


def st_of(m, slot):
    return int(m.ram[TABLE + slot * STRIDE:
                     TABLE + slot * STRIDE + 2].view("<u2")[0])


def x_of(m, slot):
    base = TABLE + slot * STRIDE + 0x78
    return int(m.ram[base:base + 4].view("<u4")[0]) / 65536.0


def wait_wave(p, m, J, budget_polls=120):
    """Poll until a wave-zone soldier spawns (they appear 1-4s after
    the pin/respawn). Returns the soldier list or []."""
    for k in range(budget_polls):
        ws = wave_soldiers(m, px_of(m))
        if ws:
            J({"ev": "WAVE_SEEN", "k": k, "soldiers": ws})
            return ws
        p.core.run(30, set())
        if not alive(m):
            for w in range(60):
                p.core.run(30, set())
                if alive(m):
                    break
    return wave_soldiers(m, px_of(m))


def clear_soldiers(p, m, J, tag):
    """Face-corrected aimed clear. Returns kills list."""
    kills = []
    if not wait_wave(p, m, J):
        J({"ev": "NO_WAVE", **snap(m)})
        return kills
    for rnd in range(8):
        if not alive(m):
            if not wait_respawn(p, m, J, "respawn_clear", rnd):
                break
            continue
        ws = wave_soldiers(m, px_of(m))
        if not ws:
            J({"ev": "ZONE_CLEAR", "rnd": rnd, **snap(m),
               "slots": raw_slots(m)})
            break
        ws.sort(key=lambda s: abs(s["x"] - px_of(m)))
        slot = ws[0]["s"]
        taps = 0
        dead = False
        for t in range(4):
            if not alive(m):
                break
            px = px_of(m)
            tx = x_of(m, slot)
            d = "RIGHT" if tx >= px else "LEFT"
            p.core.run(6, {d})
            p.core.run(4, set())
            pre = snap(m)
            p.core.run(4, {"Y"})
            for k in range(15):
                p.core.run(6, set())
                if st_of(m, slot) in DEAD_ST:
                    taps += 1
                    dead = True
                    break
            if dead:
                break
            taps += 1
            J({"ev": "tap", "slot": slot, "taps": taps, "pre": pre,
               "st": st_of(m, slot)})
        post = snap(m)
        kills.append({"slot": slot, "taps": taps, "dead": dead,
                      "score": post["score"]})
        J({"ev": "SOLDIER_RESULT", "slot": slot, "taps": taps,
           "dead": dead, **post})
        log(f"slot {slot}: taps={taps} dead={dead} "
            f"score={post['score']}")
        if not dead and int(m.u8(GRENADES)) > 0:
            # grenade escalation (the proven 100-dmg delivery)
            px = px_of(m)
            tx = x_of(m, slot)
            d = "RIGHT" if tx >= px else "LEFT"
            p.core.run(6, {d})
            p.core.run(3, {"UP", "A"})
            p.core.run(60, set())
            dead = st_of(m, slot) in DEAD_ST
            J({"ev": "GRENADE_ESCALATION", "slot": slot,
               "dead": dead, **snap(m)})
    return kills


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--arm", default="B", choices=["A", "B"])
    args = ap.parse_args()
    os.makedirs(EVID, exist_ok=True)
    t0 = time.time()
    results = []
    p, fw = boot()
    m = p.mem
    for r in range(args.runs):
        tag = time.strftime(f"r{r + 1}_%H%M%S")
        jf = open(os.path.join(EVID, f"{tag}.jsonl"), "w")

        def J(ev):
            jf.write(json.dumps(ev, default=str) + "\n")
            jf.flush()

        p.load_state("pin_ckpt")
        J({"ev": "start", "run": r + 1, "arm": args.arm, **snap(m)})
        log(f"=== run {r + 1}/{args.runs} arm {args.arm} "
            f"pin_ckpt loaded ===")

        if args.arm == "A":
            # inactive-chopper boot phase: the wave + soldier kill IS
            # the whole release chain (bpp 3/3) — no chopper phase.
            throws, ch_dead = 0, None
        else:
            # -- phase E: make the chopper ENGAGE (policy act; the
            # parked chopper only fights when the player acts) ------
            pol = combat.CombatPolicy()
            last_px, last_segs = None, None
            engaged = False
            for c in range(80):
                if not alive(m):
                    if not wait_respawn(p, m, J, "respawn_engage", c):
                        break
                    continue
                px = px_of(m)
                advanced = 0.0 if last_px is None else px - last_px
                intent = any("RIGHT" in (x.get("btns") or set())
                             for x in (last_segs or []))
                pol.observe(px, advanced, intent)
                pol.observe_section(combat.scan_section(m))
                scan = combat.scan_entities(m, px=px)
                segs = pol.decide(60, px, scan,
                                  grenades=int(m.u8(GRENADES)),
                                  hp=int(m.u16(0x0CA2F6)))
                last_px, last_segs = px, segs
                for x in segs:
                    p.core.run(x["frames"], x["btns"] or set())
                ch = chopper(m, px_of(m))
                if ch is not None:
                    engaged = True
                    J({"ev": "CHOPPER_ENGAGED", "c": c, "ch": ch,
                       **snap(m)})
                    log(f"chopper engaged c{c} dx="
                        f"{ch['x'] - px:.0f}")
                    break
            if not engaged:
                J({"ev": "CHOPPER_NEVER_ENGAGED", **snap(m)})
                log("chopper never engaged — treating as arm A")
            # -- phase K: chopper -------------------------------------
            throws, ch_dead = kill_chopper(p, m, J, tag)
        # -- phase S: aimed soldier clear ------------------------------
        kills = clear_soldiers(p, m, J, tag)
        # -- phase R: walker watch (up to 7200f) ------------------------
        released = False
        mission = False
        seen = []
        for k in range(240):
            p.core.run(30, set())
            s = snap(m)
            if s["sec"] not in seen:
                seen.append(s["sec"])
                J({"ev": "SEC", "k": k, **s, "slots": raw_slots(m)})
                log(f"sec k={k}: {s['sec']} px={s['px']}")
            if s["sec"][0] == 0xC:
                released = True
                if s["px"] < 200.0:
                    mission = True
                    J({"ev": "MISSION_SCREEN", "k": k, **s})
                    png(p, "mission_screen", tag)
                    log(f"MISSION SCREEN k={k} px={s['px']} "
                        f"score={s['score']}")
                    break
            if not alive(m):
                J({"ev": "death_watch", "k": k, **s})
                if not wait_respawn(p, m, J, "respawn_watch", k):
                    break
                continue
            # keep walking RIGHT through the clamp zone (the release
            # test released while the player WALKED the section)
            p.core.run(24, {"RIGHT"})
            p.core.run(6, set())
        png(p, "final", tag)
        res = {"run": r + 1, "throws": throws, "chopper_dead": ch_dead,
               "kills": kills, "released": released,
               "mission_screen": mission,
               "seen_states": [list(x) for x in seen],
               "final": snap(m)}
        results.append(res)
        J({"ev": "RUN_DONE", **res})
        jf.close()
        log(f"RUN {r + 1}: chopper_dead={ch_dead} kills={len(kills)} "
            f"released={released} mission={mission}")
        if mission:
            break

    rep = {"schema": "issue5/chain-v2/1", "runs": results,
           "wall_s": round(time.time() - t0, 1),
           "firmware": fw, "game_sha256":
               "45cde149878fe945d0219fd0f61ca09856aee66bdcc9119de21c0583f1d0667d"}
    with open(os.path.join(EVID, f"report_{int(t0)}.json"), "w") as f:
        json.dump(rep, f, indent=1, default=str)
    log("ALL DONE", json.dumps([{k: r[k] for k in
                                 ("run", "chopper_dead", "released",
                                  "mission_screen")}
                                for r in results]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
