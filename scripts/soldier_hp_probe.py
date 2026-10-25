#!/usr/bin/env python3
"""soldier_hp_probe.py — Issue #5 session 4, experiment S1.

GOAL (F9 next-discriminator, truck_resolution_session3.json):
identify the SOFT-SOLDIER (st word0 0x4054) true HP/liveness word.
The armored HP u16@+0xA4 reads 0 on these soldiers, so the foe filter
cannot separate a live 0x4054 from a corpse — the last-mile blocker.

METHOD (read-only instrumentation; only real gamepad inputs):
  1. boot -> load pin_ckpt (rebuild with chopper_hunt --mode reach).
  2. At the pin the section VM respawns frozen 0x4054 soldiers ahead
     (release_test rel1/2/3: standing-fire kills 2, score +200).
  3. Wait for the respawn wave, pick the nearest live 0x4054, snapshot
     its FULL entity row (166 u16 words) — then fire ONE Y tap, wait
     for the connect window, snapshot again. Repeat shot-by-shot until
     the soldier dies. A word that (a) decrements ONLY on hit frames
     and (b) reaches 0 exactly when st word0 flips to a corpse state
     (0x4BE4/0x5CC8) is the HP word.
  4. Also record the corpse row for N frames (despawn timing + any
     residual liveness word) and the section-walker state around the
     kill (does the queue clear on the kill or on the despawn?).

Controls: one no-input cycle BEFORE the first shot (the soldier row
must be stable without fire — rules out countdown-decay false reads),
and a per-shot diff WITHOUT connecting (a miss) when achievable.

Evidence: JSONL + report JSON in evidence/issue5_soldier_hp/.
Usage: python3 scripts/soldier_hp_probe.py
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
SOLDIER_ST = 0x4054
DEAD_ST = (0x4BE4, 0x5CC8)
EVID = os.path.join(labconfig.resolve_path("evidence_dir"),
                    "issue5_soldier_hp")
NWORDS = STRIDE // 2          # 166 u16 words per row


def log(*a):
    print("[sh]", *a, file=sys.stderr, flush=True)


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
    w = m.ram[base:base + STRIDE].view("<u2").astype(np.int32)
    return [int(v) for v in w]


def row_diff(a, b):
    return {i * 2: {"a": a[i], "b": b[i]}
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


def find_soldier(m, px, max_dx=300):
    """Nearest LIVE 0x4054 soldier (st word0 == 0x4054)."""
    best = None
    for sl in slots_brief(m):
        if sl["st"] != SOLDIER_ST:
            continue
        d = sl["x"] - px
        if abs(d) <= max_dx and (best is None or abs(d) < abs(best[0])):
            best = (d, sl)
    return best[1] if best else None


def alive(m):
    return (int(m.u32(0x0EE518)) & 0xFF) == 0xFF and px_of(m) != 0.0


def png(p, name, tag):
    rgb = p.core.frame_rgb()
    if rgb is not None:
        from PIL import Image
        Image.fromarray(rgb).save(os.path.join(EVID,
                                               f"{tag}_{name}.png"))


def main():
    tag = time.strftime("shp_%H%M%S")
    os.makedirs(EVID, exist_ok=True)
    jf = open(os.path.join(EVID, f"{tag}.jsonl"), "w")

    def J(ev):
        jf.write(json.dumps(ev, default=str) + "\n")
        jf.flush()

    t0 = time.time()
    p, fw = boot()
    m = p.mem
    try:
        p.load_state("pin_ckpt")
    except Exception as e:
        log(f"no pin_ckpt: {e} — run chopper_hunt.py --mode reach first")
        return 1
    J({"ev": "start", **snap(m), "slots": slots_brief(m)})
    log("pin_ckpt loaded", json.dumps(snap(m)))

    # ---- phase W: wait for the respawn wave (frozen 0x4054 soldiers)
    soldier = None
    for k in range(120):
        p.core.run(30, set())
        if not alive(m):
            J({"ev": "death_wait", "k": k, **snap(m)})
            for w in range(60):
                p.core.run(30, set())
                if alive(m):
                    break
            continue
        px = px_of(m)
        s0 = find_soldier(m, px)
        if s0 is not None:
            soldier = s0
            J({"ev": "SOLDIER_SEEN", "k": k, "slot": s0,
               **snap(m), "slots": slots_brief(m)})
            log(f"live soldier slot {s0['s']} x={s0['x']} dx="
                f"{s0['x'] - px:.0f}")
            break
    if soldier is None:
        log("no live 0x4054 seen at the pin in 3600f")
        return 1

    # ---- phase C: no-input stability control (600f) ------------------
    slot = soldier["s"]
    r_before = row(m, slot)
    stable = True
    for k in range(20):
        p.core.run(30, set())
        r_now = row(m, slot)
        if int(m.ram[TABLE + slot * STRIDE:
                          TABLE + slot * STRIDE + 2].view("<u2")[0]) \
                != SOLDIER_ST:
            stable = False
            break
    r_after = row(m, slot)
    ctrl_diff = row_diff(r_before, r_after)
    J({"ev": "CONTROL_NO_INPUT", "slot": slot, "stable": stable,
        "diff": ctrl_diff, "frames": 600, **snap(m)})
    log(f"control: stable={stable} changed_words={len(ctrl_diff)}")
    if stable and ctrl_diff:
        # countdown-decay guard: report which words move WITHOUT fire
        log("  moving without fire:",
            {hex(k * 2): (v['a'], v['b']) for k, v in
             list(ctrl_diff.items())[:8]})

    # ---- phase S: shot-by-shot HP discrimination ---------------------
    shots = []
    death_frame = None
    for shot in range(12):
        if not alive(m):
            J({"ev": "death_shot", "shot": shot, **snap(m)})
            for w in range(60):
                p.core.run(30, set())
                if alive(m):
                    break
            # after respawn the wave re-freezes; re-acquire
            px = px_of(m)
            ns = find_soldier(m, px)
            if ns is None:
                break
            slot, soldier = ns["s"], ns
            J({"ev": "REACQUIRE", "shot": shot, "slot": slot, **snap(m)})
        px = px_of(m)
        cur = find_soldier(m, px)
        if cur is None or cur["s"] != slot:
            # the tracked soldier died on the previous shot
            J({"ev": "TARGET_DEAD_AFTER_SHOT", "shot": shot - 1,
               "slot": slot, **snap(m), "slots": slots_brief(m)})
            log(f"tracked slot {slot} gone after shot {shot - 1}")
            break
        slot = cur["s"]
        pre = snap(m)
        r_pre = row(m, slot)
        # ONE Y tap (4f press + settle) — the release_test kill recipe
        p.core.run(4, {"Y"})
        # connect window: sample every 10f for 110f
        seq = []
        died = False
        for k in range(11):
            p.core.run(10, set())
            r_now = row(m, slot)
            st_now = int(m.ram[TABLE + slot * STRIDE:
                               TABLE + slot * STRIDE + 2]
                         .view("<u2")[0])
            seq.append({"t": (k + 1) * 10,
                        "st": st_now,
                        "diff": row_diff(r_pre, r_now)})
            if st_now in DEAD_ST:
                died = True
                death_frame = pre["px"]
                J({"ev": "CORPSE_FLIP", "shot": shot,
                   "t": (k + 1) * 10, "st": hex(st_now), **snap(m)})
                break
        post = snap(m)
        hit_words = {}
        for samp in seq:
            for off, v in samp["diff"].items():
                hit_words.setdefault(off, []).append(
                    [samp["t"], v["a"], v["b"]])
        rec = {"shot": shot, "slot": slot,
               "pre": {**pre, "row_sel": {off: r_pre[off // 2]
                                          for off in hit_words}},
               "post": post, "died": died,
               "hit_words": hit_words,
               "seq_states": [s["st"] for s in seq]}
        shots.append(rec)
        J({"ev": "SHOT", **rec})
        log(f"shot {shot}: hit_words={list(hit_words)} died={died} "
            f"score {pre['score']}->{post['score']}")
        if died:
            break

    # ---- phase D: corpse watch (2400f) — despawn + walker reaction ---
    corpse = {"slot": slot, "frames": []}
    for k in range(80):
        p.core.run(30, set())
        r_now = row(m, slot)
        st_now = int(m.ram[TABLE + slot * STRIDE:
                           TABLE + slot * STRIDE + 2].view("<u2")[0])
        corpse["frames"].append({"t": (k + 1) * 30, "st": st_now,
                                 "nonzero_words":
                                     sum(1 for v in r_now if v)})
        if not alive(m):
            break
    J({"ev": "CORPSE_WATCH", **corpse, "final": snap(m),
       "slots": slots_brief(m)})
    png(p, "final", tag)

    rep = {"tag": tag, "shots": shots, "control_stable": stable,
           "control_diff": ctrl_diff,
           "corpse_watch": corpse["frames"][-6:],
           "wall_s": round(time.time() - t0, 1),
           "frames": p.core.frames_run}
    with open(os.path.join(EVID, f"report_{tag}.json"), "w") as f:
        json.dump(rep, f, indent=1, default=str)
    log("DONE", json.dumps({"shots": len(shots),
                            "wall_s": rep["wall_s"]}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
