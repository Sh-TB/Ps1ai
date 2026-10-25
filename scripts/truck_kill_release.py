#!/usr/bin/env python3
"""truck_kill_release.py — THE documented smallest next experiment
(Issue #5 D7 release, truck_resolution.json d7_release_status):

  1. load the revived `truck_engage` (truck parked 1126.5, hp_a4 230,
     player 1064.9, 10 grenades)
  2. KILL the truck with lobs at the proven 50..62px engagement
     distance (mirrored: the truck is AHEAD here — face-RIGHT flat
     lob), alternate UP/flat on no-connect, poll +0xA4 every throw
  3. SWEEP remaining zone entities — priority: the wall mortarman
     (st 0xE17C, h 74..100) with UP-lobs from below (dx -45..-15)
  4. RELEASE TEST: walk RIGHT up to 2400f; PASSED iff px > 1170
     (the D7 clamp pins at ~1164)

READ-ONLY instrumentation; deaths are real; grenades are the game's
own counter. Usage: python3 scripts/truck_kill_release.py --rep 1
"""
import argparse, json, os, sys, time
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
ENGAGE = "truck_engage"
EVID = os.path.join(labconfig.resolve_path("evidence_dir"),
                    "issue5_truck_release")
DEAD_ST = (0x4BE4, 0x5CC8)


def log(*a):
    print("[kr]", *a, file=sys.stderr, flush=True)


def px_of(m):
    return int(m.u32(PLAYER_X)) / 65536.0


def snap(m):
    return {"px": round(px_of(m), 1), "score": int(m.u32(A_SCORE)),
            "flags": int(m.u32(0x0EE518)) & 0xFF,
            "gren": int(m.u8(GRENADES)),
            "sec_state": int(m.u16(combat.SECTION_STATE)),
            "sec_flags": int(m.u16(combat.SECTION_FLAGS)),
            "sec_prog": int(m.u16(combat.SECTION_PROGRESS))}


def raw_slots(m):
    tv = m.ram[TABLE:TABLE + 24 * STRIDE].view("<u2").astype(
        np.int32).reshape(24, STRIDE // 2)
    out = []
    for s in range(1, 24):
        st = int(tv[s, 0])
        xw = ((int(tv[s, 61]) << 16) | int(tv[s, 60])) / 65536.0
        if not st and not xw:
            continue
        out.append({"s": s, "st": st, "x": round(xw, 1),
                    "h": int(tv[s, 63]), "hp8E": int(tv[s, 71]),
                    "hpA4": int(tv[s, 82])})
    return out


def find_truck(m, px):
    for sl in raw_slots(m):
        if sl["st"] == 0x9E88 and sl["h"] == 64 \
                and abs(sl["x"] - px) < 400:
            return sl
    return None


def find_mortarman(m, px):
    for sl in raw_slots(m):
        if sl["st"] == 0xE17C and 55 <= sl["h"] <= 110 \
                and abs(sl["x"] - px) < 400:
            return sl
    return None


def faller_near(m, px):
    for sl in raw_slots(m):
        if sl["st"] == 0xB4E4 and 60 < sl["h"] < 260 \
                and abs(sl["x"] - px) < 150:
            return sl
    return None


def alive(m):
    s = snap(m)
    return s["flags"] == 0xFF and s["px"] != 0.0, s


def png(p, name, tag):
    rgb = p.core.frame_rgb()
    if rgb is not None:
        Image.fromarray(rgb).save(
            os.path.join(EVID, f"{tag}_{name}.png"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rep", type=int, default=1)
    args = ap.parse_args()
    tag = f"kr_rep{args.rep}"
    os.makedirs(EVID, exist_ok=True)
    jf = open(os.path.join(EVID, f"{tag}_trace.jsonl"), "w")

    def J(ev):
        jf.write(json.dumps(ev, default=str) + "\n"); jf.flush()

    t0 = time.time()
    p, fw = boot()
    m = p.mem
    p.load_state(ENGAGE)
    for _ in range(3):
        p.core.run_frame()
    ok, s0 = alive(m)
    J({"ev": "start", "snap": s0, "slots": raw_slots(m)})
    log(f"start {s0}")
    if not ok:
        log("anchor not alive on load"); jf.close(); return 1

    # ---------------- 1) KILL THE TRUCK ------------------------------
    trk = find_truck(m, px_of(m))
    hp0 = trk["hpA4"] if trk else None
    hp_track, lobs, killed = [], 0, False
    while True:
        ok, s = alive(m)
        if not ok:
            J({"ev": "death_kill", **s, "hp_track": hp_track})
            log(f"DIED during kill hp_track={hp_track}")
            png(p, "kill_death", tag)
            jf.close(); return 1
        trk = find_truck(m, px_of(m))
        if trk is None:
            J({"ev": "truck_gone", "hp_track": hp_track, **s})
            log(f"truck record gone hp_track={hp_track}")
            killed = any(h <= 0 for h in hp_track) if hp_track else False
            break
        hp = trk["hpA4"]
        if hp <= 0 or trk["st"] != 0x9E88:
            J({"ev": "truck_dead", "final": trk, "hp_track": hp_track,
               **s})
            log(f"TRUCK DEAD st={trk['st']:#06x} hp_track={hp_track}")
            killed = True
            break
        if int(m.u8(GRENADES)) <= 0:
            J({"ev": "out_of_grenades", "hp_track": hp_track, **s})
            log(f"out of grenades hp={hp} track={hp_track}")
            break
        if lobs >= 14:
            J({"ev": "lob_safety_end", "hp_track": hp_track, **s})
            log(f"lob safety end hp={hp} track={hp_track}")
            break
        # hold the PROVEN connect band: |dx| in [50, 62] (hit1
        # geometry, mirrored — truck is AHEAD here; reach4 rep1 showed
        # dx 64.8 connects only by grenade-bounce luck)
        dx = trk["x"] - px_of(m)
        miss_streak = len([h for h in hp_track[-2:]
                           if h == hp_track[-1]]) if len(
            hp_track) >= 2 and hp_track[-1] == hp_track[-2] else 0
        if miss_streak == 2:
            # two identical readings = two misses at this distance:
            # nudge 12px toward the band centre (56)
            want_dx = 56.0 if dx > 0 else -56.0
            step = {"RIGHT"} if (abs(dx) > abs(want_dx)) else {"LEFT"}
            if abs(abs(dx) - 56.0) > 4:
                p.core.run(6, step)
                p.core.run(2, set())
                continue
        adx = abs(dx)
        if adx > 62:
            p.core.run(6, {"RIGHT"} if dx > 0 else {"LEFT"})
            p.core.run(2, set())
            continue
        if adx < 50:
            p.core.run(6, {"LEFT"} if dx > 0 else {"RIGHT"})
            p.core.run(2, set())
            continue
        face = {"RIGHT"} if dx > 0 else {"LEFT"}
        up = (lobs % 2 == 1)          # first throw = proven flat lob
        J({"ev": "lob", "n": lobs, "dx": round(dx, 1), "hp": hp,
           "up": up, **s})
        if up:
            p.core.run(3, face | {"UP"})
            p.core.run(6, face | {"UP", "A"})
        else:
            p.core.run(2, face)
            p.core.run(8, face | {"A"})
        p.core.run(2, set())
        p.core.run(35, set())
        nt = find_truck(m, px_of(m))
        hp_track.append(nt["hpA4"] if nt else 0)
        lobs += 1
    if killed:
        png(p, "truck_dead", tag)
        s = snap(m)
        J({"ev": "KILLED", **s})
        log(f"KILLED score={s['score']} gren={s['gren']}")
    else:
        log("truck not killed — aborting to report")
        with open(os.path.join(EVID, f"{tag}_report.json"), "w") as f:
            json.dump({"rep": args.rep, "killed": False,
                       "hp_track": hp_track, "final": snap(m)},
                      f, indent=1)
        jf.close(); return 1

    # ---------------- 2) SWEEP: soldiers by bullet, wall by UP-lob ---
    # rep2 lesson: the wall bomb sources here are 0x270c (h 102..135) +
    # 0xb378 (h 95), NOT 0xE17C; ground soldiers die to FREE Y bullets
    # (grenades are scarce), and walking toward the clamp with live
    # shooters killed rep2 mid-approach.
    sweeps = []
    for rnd in range(12):
        ok, s = alive(m)
        if not ok:
            J({"ev": "death_sweep", "rnd": rnd, **s})
            log(f"DIED sweep{rnd}"); png(p, "sweep_death", tag)
            jf.close(); return 1
        px = px_of(m)
        ground = [sl for sl in raw_slots(m)
                  if sl["h"] == 64 and sl["hpA4"] == 0
                  and sl["st"] not in DEAD_ST + (0xB4E4, 0xA304,
                                                 0xA44C)
                  and 830 <= sl["x"] <= 1230]
        wall = [sl for sl in raw_slots(m)
                if 90 <= sl["h"] <= 160 and sl["st"] not in DEAD_ST
                and 830 <= sl["x"] <= 1230
                and sl["st"] not in (0xB570, 0x74C8)]
        tgt = ground[0] if ground else (wall[0] if wall else None)
        J({"ev": "sweep_scan", "rnd": rnd, "ground": ground,
           "wall": wall, **s})
        if tgt is None:
            J({"ev": "sweep_clean", "rnd": rnd, **s})
            log(f"sweep{rnd}: zone clean")
            break
        if tgt in ground:
            # ---- ground soldier: stand off ~120px, Y-bursts --------
            side = 120 if tgt["x"] > px else -120
            want = tgt["x"] - side
            for k in range(160):
                ok2, s2 = alive(m)
                if not ok2:
                    J({"ev": "death_approach", "rnd": rnd, **s2})
                    log(f"DIED bullet-approach rnd{rnd}")
                    png(p, "approach_death", tag)
                    jf.close(); return 1
                px2 = px_of(m)
                if abs(want - px2) <= 8:
                    break
                fall = faller_near(m, px2)
                if fall is not None:
                    away = {"LEFT"} if fall["x"] > px2 else {"RIGHT"}
                    p.core.run(3, {"B"})
                    p.core.run(10, {"B"} | away)
                    p.core.run(6, set())
                    continue
                p.core.run(6, {"RIGHT"} if want > px2 else {"LEFT"})
            face = {"RIGHT"} if tgt["x"] > px_of(m) else {"LEFT"}
            before = tgt["st"]
            for burst in range(10):
                ok2, s2 = alive(m)
                if not ok2:
                    J({"ev": "death_fire", "rnd": rnd, **s2})
                    log(f"DIED firing rnd{rnd}")
                    png(p, "fire_death", tag)
                    jf.close(); return 1
                p.core.run(2, face)
                p.core.run(8, face | {"Y"})
                p.core.run(6, set())
                cur = [sl for sl in raw_slots(m)
                       if sl["s"] == tgt["s"]]
                if not cur or cur[0]["st"] in DEAD_ST or \
                        cur[0]["st"] != before and cur[0]["hpA4"] == 0 \
                        and cur[0]["st"] not in (0x4054, 0x6730,
                                                 0x1BE0, 0x3F48,
                                                 0x270C, 0xB378):
                    break
            sweeps.append({"rnd": rnd, "mode": "bullet",
                           "target": tgt})
            J({"ev": "sweep_bullet", "rnd": rnd, "target": tgt,
               **snap(m)})
        else:
            # ---- wall entity: UP-lob from below at dx 15..45 -------
            want = tgt["x"] - 30
            for k in range(160):
                ok2, s2 = alive(m)
                if not ok2:
                    J({"ev": "death_approach", "rnd": rnd, **s2})
                    log(f"DIED wall-approach rnd{rnd}")
                    png(p, "approach_death", tag)
                    jf.close(); return 1
                px2 = px_of(m)
                if abs(want - px2) <= 6:
                    break
                fall = faller_near(m, px2)
                if fall is not None:
                    away = {"LEFT"} if fall["x"] > px2 else {"RIGHT"}
                    p.core.run(3, {"B"})
                    p.core.run(10, {"B"} | away)
                    p.core.run(6, set())
                    continue
                p.core.run(6, {"RIGHT"} if want > px2 else {"LEFT"})
            face = {"RIGHT"} if tgt["x"] > px_of(m) else {"LEFT"}
            if int(m.u8(GRENADES)) <= 0:
                J({"ev": "out_of_grenades", "rnd": rnd, **s})
                log("out of grenades at wall entity")
                break
            p.core.run(3, face | {"UP"})
            p.core.run(6, face | {"UP", "A"})
            p.core.run(2, set())
            p.core.run(60, set())
            sweeps.append({"rnd": rnd, "mode": "uplob",
                           "target": tgt})
            J({"ev": "sweep_throw", "rnd": rnd, "target": tgt,
               **snap(m)})
        png(p, f"sweep{rnd}", tag)

    # ---------------- 3) RELEASE TEST --------------------------------
    s = snap(m)
    J({"ev": "pre_walk", "slots": raw_slots(m), **s})
    log(f"pre-walk {s}")
    walk, max_px, passed = [], px_of(m), False
    f0 = p.core.frames_run
    frozen = 0
    while p.core.frames_run - f0 < 2400:
        ok, s = alive(m)
        if not ok:
            J({"ev": "death_walk", **s, "max_px": round(max_px, 1)})
            log(f"DIED walking max_px={max_px:.1f}")
            png(p, "walk_death", tag)
            break
        px0 = px_of(m)
        fall = faller_near(m, px0)
        if fall is not None:
            away = {"LEFT"} if fall["x"] > px0 else {"RIGHT"}
            p.core.run(3, {"B"}); p.core.run(10, {"B"} | away)
            p.core.run(4, set())
            J({"ev": "walk_dodge", "faller_x": fall["x"],
               "px": round(px0, 1)})
            continue
        # hop-advance: RIGHT + periodic B (rep3-7 held plain RIGHT and
        # froze at 1059.7 — discriminate physical obstacle (jump
        # clears) vs walker clamp (jump no-op))
        p.core.run(30, {"RIGHT", "B"})
        s = snap(m)
        max_px = max(max_px, s["px"])
        if s["px"] > 1170.0:
            passed = True
            J({"ev": "PASSED_1170", **s})
            png(p, "RELEASED", tag)
            p.core.run(300, {"RIGHT"})
            break
        frozen = frozen + 1 if abs(s["px"] - px0) < 0.5 else 0
        walk.append({"px": s["px"], "frozen": frozen, **{
            k: s[k] for k in ("sec_state", "sec_flags", "score")}})
        J({"ev": "walk", "frozen": frozen, **s})
        if frozen >= 12:
            J({"ev": "WALK_FROZEN_DESPITE_HOPS", "px": s["px"],
               "max_px": round(max_px, 1)})
            log(f"frozen at {s['px']} despite hops")
            break

    # ---------------- 2.5) CHOPPER HUNT ------------------------------
    # rep3 lesson: after the truck died and the zone swept clean, the
    # chopper (0xaa94/0xabdc class, hp_a4 300, h ~206..228) flew back
    # in (0xabdc @1010.8 h212) and bombed the frozen player at the
    # (0xB,0x43) clamp — px froze at 1059.7 (NOT 1164). Test whether
    # killing the chopper is the missing release condition.
    chopper_log = []
    ch0 = p.core.frames_run
    last_hop = ch0
    no_connect = 0
    while p.core.frames_run - ch0 < 3600:
        ok, s = alive(m)
        if not ok:
            J({"ev": "death_chopper_wait", **s,
               "log": chopper_log[-8:]})
            log("DIED waiting for chopper"); png(p, "ch_death", tag)
            jf.close(); return 1
        px = px_of(m)
        # NEVER advance past 1005: the walker clamp engages ~1047 and
        # rep5/6 showed the clamped player cannot retreat (hops no-op)
        # and dies to chopper bombs. Hunt from mobile ground.
        chop = [sl for sl in raw_slots(m)
                if 170 <= sl["h"] <= 260 and sl["hpA4"] > 0
                and sl["st"] not in DEAD_ST
                and abs(sl["x"] - px) < 420]
        now = p.core.frames_run
        if chop:
            c = chop[0]
            dx = c["x"] - px
            if abs(dx) <= 25:
                # directly (near-)overhead: UP-lob (MSX anti-flyer)
                if int(m.u8(GRENADES)) > 0:
                    face = {"RIGHT"} if dx > 0 else {"LEFT"}
                    hp_before = c["hpA4"]
                    p.core.run(3, {"UP"})
                    p.core.run(6, {"UP", "A"})
                    p.core.run(2, set())
                    p.core.run(24, set())
                    cur = [sl for sl in raw_slots(m)
                           if sl["s"] == c["s"]]
                    hp_now = cur[0]["hpA4"] if cur else 0
                    chopper_log.append({"f": now - ch0,
                                        "st": c["st"], "x": c["x"],
                                        "h": c["h"],
                                        "hp_before": hp_before,
                                        "hp_after": hp_now,
                                        "mode": "uplob",
                                        "dx": round(dx, 1),
                                        "px": round(px, 1)})
                    if hp_now <= 0 or not cur:
                        J({"ev": "CHOPPER_DEAD",
                           "log": chopper_log[-4:]})
                        log(f"CHOPPER DEAD hp {hp_before}->{hp_now}")
                        png(p, "chopper_dead", tag)
                        break
                    last_hop = now
                    continue
            else:
                # reposition under its hover line (mobile, pre-clamp)
                want = max(950.0, min(1005.0, c["x"]))
                step = {"RIGHT"} if want > px else {"LEFT"}
                p.core.run(6, step)
                p.core.run(2, set())
                continue
        # no engage: bomb-aware hold with the PROVEN 200f hop cadence
        fall = faller_near(m, px)
        if fall is not None:
            away = {"LEFT"} if fall["x"] > px else {"RIGHT"}
            p.core.run(3, {"B"}); p.core.run(10, {"B"} | away)
            p.core.run(8, set())
            last_hop = now
        elif now - last_hop >= 200:
            p.core.run(3, {"B"}); p.core.run(10, {"B"})
            p.core.run(8, set())
            last_hop = now
        elif px > 1005:
            p.core.run(8, {"LEFT"})
        elif px < 950:
            p.core.run(8, {"RIGHT"})
        else:
            p.core.run(10, set())
    else:
        J({"ev": "chopper_budget_end", "log": chopper_log[-6:]})
        log("chopper hunt budget end")

    res = {"rep": args.rep, "killed": killed, "hp_track": hp_track,
           "lobs": lobs, "sweeps": sweeps,
           "released": passed, "max_px": round(max_px, 1),
           "walk_tail": walk[-8:], "final": snap(m),
           "wall_s": round(time.time() - t0, 1)}
    with open(os.path.join(EVID, f"{tag}_report.json"), "w") as f:
        json.dump(res, f, indent=1)
    jf.close()
    log("DONE", json.dumps({k: res[k] for k in
        ("killed", "released", "max_px", "lobs")}))
    return 0


if __name__ == "__main__":
    main()
