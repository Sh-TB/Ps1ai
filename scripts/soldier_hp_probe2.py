#!/usr/bin/env python3
"""soldier_hp_probe2.py — Issue #5 session 4, experiment S1-v2.

v1 finding (shp_100033): the frozen 0x4054 soldiers at the D7 pin are
NOT static — without any input the tracked soldier (slot 12 @1072)
transitioned 0x4054 -> 0x41FC within ~600f, while slot 10 @1064 stayed
0x4054. v1 also fired WITHOUT facing the soldier (dx -92 = behind the
player) — the same facing bug that likely explains the session-3
"Y-bursts did not kill" observation.

v2 protocol (read-only + real inputs only):
  1. boot -> pin_ckpt -> wait for the respawn wave.
  2. track the nearest wave-zone soldier BY SLOT (ground h==64,
     x 1040..1120, st not in corpse states) regardless of the exact
     live state word (the state cycles).
  3. MISS CONTROL first: face AWAY from the soldier, one Y tap, full
     row diff -> words that change are fire-independent (anim/decay).
  4. HIT series: face the soldier (6f directional tap), snapshot,
     ONE Y tap, sample every 6f x 25 (150f) with FULL row diffs.
     The HP word must (a) be stable in the miss control, (b) decrement
     only on connect shots, (c) reach 0 exactly at the corpse flip.
  5. On survival after 6 hit shots: one UP+A grenade lob (the proven
     100-dmg anti-armor delivery) with the same diff protocol.
  6. Corpse watch 2400f: st transitions, despawn timing, walker
     (sec,flags,prog) around the kill — does the queue clear on the
     kill or on the despawn?

Evidence: evidence/issue5_soldier_hp/ (JSONL + report + PNGs).
Usage: python3 scripts/soldier_hp_probe2.py
"""
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

TABLE, STRIDE = combat.TABLE, combat.STRIDE
PLAYER_X = 0x0CA2E0
A_SCORE = 0x0EE318
GRENADES = 0x0EDCF4
PLAYER_HP = 0x0CA2F6
DEAD_ST = (0x4BE4, 0x5CC8)
EVID = os.path.join(labconfig.resolve_path("evidence_dir"),
                    "issue5_soldier_hp")
NWORDS = STRIDE // 2
WAVE_LO, WAVE_HI = 1040.0, 1120.0


def log(*a):
    print("[s2]", *a, file=sys.stderr, flush=True)


def px_of(m):
    return int(m.u32(PLAYER_X)) / 65536.0


def snap(m):
    return {"px": round(px_of(m), 1),
            "score": int(m.u32(A_SCORE)),
            "flags": int(m.u32(0x0EE518)) & 0xFF,
            "gren": int(m.u8(GRENADES)),
            "php": int(m.u16(PLAYER_HP)),
            "sec": (int(m.u16(combat.SECTION_STATE)),
                    int(m.u16(combat.SECTION_FLAGS))),
            "prog": int.from_bytes(
                m.ram[0xEB5D4:0xEB5D8].tobytes(), "little")}


def row(m, slot):
    base = TABLE + slot * STRIDE
    return [int(v) for v in
            m.ram[base:base + STRIDE].view("<u2").astype(np.int32)]


def st_of(m, slot):
    return int(m.ram[TABLE + slot * STRIDE:
                     TABLE + slot * STRIDE + 2].view("<u2")[0])


def x_of(m, slot):
    base = TABLE + slot * STRIDE + 0x78
    return int(m.ram[base:base + 4].view("<u4")[0]) / 65536.0


def row_diff(a, b):
    return {i * 2: [a[i], b[i]]
            for i in range(NWORDS) if a[i] != b[i]}


def slots_brief(m, n=36):
    tv = m.ram[TABLE:TABLE + n * STRIDE].view("<u2").astype(
        np.int32).reshape(n, STRIDE // 2)
    out = []
    for s in range(1, n):
        st = int(tv[s, 0])
        xw = (int(tv[s, 61]) << 16) | int(tv[s, 60])
        if st or xw:
            out.append({"s": s, "st": st,
                        "x": round(xw / 65536.0, 1),
                        "h": int(tv[s, 63]),
                        "hpA4": int(tv[s, 82])})
    return out


def find_wave_soldier(m, px):
    """Nearest wave-zone ground soldier by slot (state-agnostic)."""
    best = None
    for sl in slots_brief(m):
        if not (WAVE_LO <= sl["x"] <= WAVE_HI) or sl["h"] != 64:
            continue
        if sl["st"] in DEAD_ST or sl["st"] == 0:
            continue
        d = sl["x"] - px
        if best is None or abs(d) < abs(best[0]):
            best = (d, sl)
    return best


def alive(m):
    return (int(m.u32(0x0EE518)) & 0xFF) == 0xFF and px_of(m) != 0.0


def png(p, name, tag):
    rgb = p.core.frame_rgb()
    if rgb is not None:
        from PIL import Image
        Image.fromarray(rgb).save(os.path.join(
            EVID, f"{tag}_{name}.png"))


def face(m, px, tx, run):
    """Tap the direction that turns the player toward tx."""
    d = "RIGHT" if tx >= px else "LEFT"
    run(6, {d})
    run(4, set())
    return d


def main():
    tag = time.strftime("shp2_%H%M%S")
    os.makedirs(EVID, exist_ok=True)
    jf = open(os.path.join(EVID, f"{tag}.jsonl"), "w")

    def J(ev):
        jf.write(json.dumps(ev, default=str) + "\n")
        jf.flush()

    def run(n, btns):
        p.core.run(n, set(btns))

    t0 = time.time()
    p, fw = boot()
    m = p.mem
    try:
        p.load_state("pin_ckpt")
    except Exception as e:
        log(f"no pin_ckpt: {e}")
        return 1
    J({"ev": "start", **snap(m), "slots": slots_brief(m)})

    # ---- wait for the wave ------------------------------------------
    target = None
    for k in range(120):
        run(30, set())
        if not alive(m):
            J({"ev": "death_wait", "k": k, **snap(m)})
            for w in range(60):
                run(30, set())
                if alive(m):
                    break
            continue
        fnd = find_wave_soldier(m, px_of(m))
        if fnd is not None:
            target = fnd[1]
            J({"ev": "TARGET_ACQUIRED", "k": k, "slot": target,
               **snap(m), "slots": slots_brief(m)})
            log(f"wave soldier slot {target['s']} x={target['x']}")
            break
    if target is None:
        log("no wave soldier in 3600f")
        return 1
    slot = target["s"]

    # ---- MISS CONTROL: face AWAY, one Y tap --------------------------
    px = px_of(m)
    away = "LEFT" if target["x"] >= px else "RIGHT"
    run(6, {away})
    run(4, set())
    r_pre = row(m, slot)
    pre = snap(m)
    run(4, {"Y"})
    seq = []
    for k in range(25):
        run(6, set())
        seq.append({"t": (k + 1) * 6, "st": st_of(m, slot),
                    "diff": row_diff(r_pre, row(m, slot))})
    post = snap(m)
    miss_words = {}
    for smp in seq:
        for off, v in smp["diff"].items():
            miss_words.setdefault(off, []).append([smp["t"], v[0], v[1]])
    J({"ev": "MISS_CONTROL", "slot": slot, "away": away,
       "score": [pre["score"], post["score"]],
       "final_st": seq[-1]["st"], "changed_words": miss_words,
       "seq_states": [s["st"] for s in seq]})
    log(f"miss control: {len(miss_words)} words changed, "
        f"score {pre['score']}->{post['score']}")

    # ---- HIT series ---------------------------------------------------
    shots = []
    grenade_used = False
    for shot in range(8):
        if not alive(m):
            J({"ev": "death_shot", "shot": shot, **snap(m)})
            for w in range(60):
                run(30, set())
                if alive(m):
                    break
            fnd = find_wave_soldier(m, px_of(m))
            if fnd is None:
                break
            slot = fnd[1]["s"]
            J({"ev": "REACQUIRE", "shot": shot, "slot": slot, **snap(m)})
        px = px_of(m)
        tx = x_of(m, slot)
        if not (WAVE_LO <= tx <= WAVE_HI) or st_of(m, slot) in DEAD_ST:
            J({"ev": "TARGET_GONE", "shot": shot, "slot": slot,
               "st": st_of(m, slot), "x": tx, **snap(m)})
            break
        face(m, px, tx, run)                 # turn toward the soldier
        r_pre = row(m, slot)
        pre = snap(m)
        run(4, {"Y"})                        # ONE bullet
        seq = []
        died = False
        for k in range(25):
            run(6, set())
            st_now = st_of(m, slot)
            seq.append({"t": (k + 1) * 6, "st": st_now,
                        "diff": row_diff(r_pre, row(m, slot))})
            if st_now in DEAD_ST:
                died = True
                break
        post = snap(m)
        hit_words = {}
        for smp in seq:
            for off, v in smp["diff"].items():
                hit_words.setdefault(off, []).append(
                    [smp["t"], v[0], v[1]])
        rec = {"shot": shot, "slot": slot, "died": died,
               "score": [pre["score"], post["score"]],
               "final_st": seq[-1]["st"],
               "hit_words": hit_words,
               "seq_states": [s["st"] for s in seq]}
        shots.append(rec)
        J({"ev": "SHOT", **rec})
        log(f"shot {shot}: words={len(hit_words)} died={died} "
            f"st_final={hex(seq[-1]['st'])} "
            f"score {pre['score']}->{post['score']}")
        if died:
            break
        # after 6 surviving bullet shots escalate to ONE grenade
        if shot == 5 and not grenade_used and int(m.u8(GRENADES)) > 0:
            grenade_used = True
            px = px_of(m)
            tx = x_of(m, slot)
            face(m, px, tx, run)
            r_pre = row(m, slot)
            pre = snap(m)
            run(3, {"UP", "A"})
            seq = []
            for k in range(40):
                run(10, set())
                st_now = st_of(m, slot)
                seq.append({"t": (k + 1) * 10, "st": st_now,
                            "diff": row_diff(r_pre, row(m, slot))})
                if st_now in DEAD_ST:
                    break
            post = snap(m)
            gw = {}
            for smp in seq:
                for off, v in smp["diff"].items():
                    gw.setdefault(off, []).append(
                        [smp["t"], v[0], v[1]])
            shots.append({"shot": "grenade", "slot": slot,
                          "gren": [pre["gren"], post["gren"]],
                          "died": seq[-1]["st"] in DEAD_ST,
                          "score": [pre["score"], post["score"]],
                          "hit_words": gw,
                          "seq_states": [s["st"] for s in seq]})
            J({"ev": "GRENADE_SHOT", "slot": slot, "hit_words": gw,
               "seq_states": [s["st"] for s in seq]})
            log(f"grenade: words={len(gw)} died="
                f"{seq[-1]['st'] in DEAD_ST}")

    # ---- corpse watch -------------------------------------------------
    watch = []
    released = False
    for k in range(80):
        run(30, set())
        s = snap(m)
        ent = {"t": (k + 1) * 30, "st": st_of(m, slot), **s}
        watch.append(ent)
        if s["sec"] != (0xA, 0x43) and s["sec"] != (0xB, 0x43):
            released = True
            J({"ev": "WALKER_LEFT_PIN", "k": k, **s,
               "slots": slots_brief(m)})
            break
        if not alive(m):
            break
    J({"ev": "CORPSE_WATCH", "frames": watch[-10:],
       "released": released, **snap(m), "slots": slots_brief(m)})
    png(p, "final", tag)

    rep = {"tag": tag, "miss_control_words":
           {hex(int(k)): v[:3] for k, v in miss_words.items()},
           "shots": shots, "released": released,
           "corpse_watch_tail": watch[-10:],
           "wall_s": round(time.time() - t0, 1),
           "frames": p.core.frames_run}
    with open(os.path.join(EVID, f"report_{tag}.json"), "w") as f:
        json.dump(rep, f, indent=1, default=str)
    log("DONE", json.dumps({"shots": len(shots),
                            "released": released,
                            "wall_s": rep["wall_s"]}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
