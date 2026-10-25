#!/usr/bin/env python3
"""soldier_bpp.py — Issue #5 session 4, experiment S1-b: bullets-per-kill.

Question: how many AIMED bullets does one wave-zone 0x4054 soldier
take? (The soft-soldier HP word is drowned by anim noise in the row
diff — the behavioural count is the evidence the policy needs for its
fire budget. Session-4 probe2 shp2: shot 0 no-death, shot 1 death ->
consistent with hp_soft = 2.)

Protocol x3 (fresh pin_ckpt each attempt):
  wait wave -> nearest wave-zone soldier -> loop:
    face (6f tap + 4f settle) -> ONE 4f Y tap -> 90f settle ->
    check st flip to corpse (0x4BE4/0x5CC8) AND score delta
  count taps until the flip. Record every tap's score/st.

Also kills any SECOND wave soldier the same way (the wave spawns 2),
then watches the walker 1800f (release timing after a FULL clear).

Usage: python3 scripts/soldier_bpp.py
"""
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

TABLE, STRIDE = combat.TABLE, combat.STRIDE
PLAYER_X = 0x0CA2E0
A_SCORE = 0x0EE318
DEAD_ST = (0x4BE4, 0x5CC8)
EVID = os.path.join(labconfig.resolve_path("evidence_dir"),
                    "issue5_soldier_hp")
WAVE_LO, WAVE_HI = 1040.0, 1120.0


def log(*a):
    print("[bp]", *a, file=sys.stderr, flush=True)


def px_of(m):
    return int(m.u32(PLAYER_X)) / 65536.0


def snap(m):
    return {"px": round(px_of(m), 1), "score": int(m.u32(A_SCORE)),
            "sec": (int(m.u16(combat.SECTION_STATE)),
                    int(m.u16(combat.SECTION_FLAGS))),
            "prog": int.from_bytes(
                m.ram[0xEB5D4:0xEB5D8].tobytes(), "little")}


def st_of(m, slot):
    return int(m.ram[TABLE + slot * STRIDE:
                     TABLE + slot * STRIDE + 2].view("<u2")[0])


def x_of(m, slot):
    base = TABLE + slot * STRIDE + 0x78
    return int(m.ram[base:base + 4].view("<u4")[0]) / 65536.0


def h_of(m, slot):
    return int(m.u16(TABLE + slot * STRIDE + 0x7E))


def slots_brief(m, n=36):
    import numpy as np
    tv = m.ram[TABLE:TABLE + n * STRIDE].view("<u2").astype(
        np.int32).reshape(n, STRIDE // 2)
    out = []
    for s in range(1, n):
        st = int(tv[s, 0])
        xw = (int(tv[s, 61]) << 16) | int(tv[s, 60])
        if st or xw:
            out.append({"s": s, "st": st,
                        "x": round(xw / 65536.0, 1), "h": int(tv[s, 63])})
    return out


def wave_soldiers(m, px):
    return [sl for sl in slots_brief(m)
            if WAVE_LO <= sl["x"] <= WAVE_HI and sl["h"] == 64
            and sl["st"] not in DEAD_ST]


def alive(m):
    return (int(m.u32(0x0EE518)) & 0xFF) == 0xFF and px_of(m) != 0.0


def kill_one(m, slot, p, J):
    """Aimed single-bullet loop on one slot; returns taps used."""
    taps = 0
    for t in range(10):
        if not alive(m):
            return taps
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
                post = snap(m)
                J({"ev": "KILL", "slot": slot, "taps": taps,
                   "pre": pre, "post": post})
                log(f"slot {slot} dead after {taps} taps "
                    f"score {pre['score']}->{post['score']}")
                return taps
        taps += 1
        J({"ev": "tap", "slot": slot, "taps": taps, "pre": pre,
           "st": st_of(m, slot)})
    return taps


def main():
    tag = time.strftime("bpp_%H%M%S")
    os.makedirs(EVID, exist_ok=True)
    jf = open(os.path.join(EVID, f"{tag}.jsonl"), "w")

    def J(ev):
        jf.write(json.dumps(ev, default=str) + "\n")
        jf.flush()

    t0 = time.time()
    p, fw = boot()
    m = p.mem
    attempts = []
    for att in range(3):
        try:
            p.load_state("pin_ckpt")
        except Exception as e:
            log(f"no pin_ckpt: {e}")
            return 1
        J({"ev": "attempt", "n": att, **snap(m)})
        # wait for the wave
        got = None
        for k in range(90):
            p.core.run(30, set())
            if not alive(m):
                for w in range(60):
                    p.core.run(30, set())
                    if alive(m):
                        break
                continue
            ws = wave_soldiers(m, px_of(m))
            if ws:
                got = ws
                break
        if not got:
            J({"ev": "NO_WAVE", "n": att, **snap(m)})
            attempts.append({"n": att, "wave": False})
            continue
        kills = []
        # kill every wave soldier, one at a time, re-scanning slots
        for rnd in range(4):
            ws = wave_soldiers(m, px_of(m))
            if not ws:
                break
            ws.sort(key=lambda s: abs(s["x"] - px_of(m)))
            slot = ws[0]["s"]
            J({"ev": "engage", "n": att, "slot": slot, "soldier": ws[0]})
            taps = kill_one(m, slot, p, J)
            kills.append({"slot": slot, "taps": taps})
            if not alive(m):
                break
        # walker watch 1800f
        rel = None
        for k in range(60):
            p.core.run(30, set())
            s = snap(m)
            if s["sec"][0] == 0xC or (s["sec"] == (0xB, 0x1)):
                rel = {"k": k, **s}
                J({"ev": "WALKER_RELEASE", "n": att, **s})
                break
            if not alive(m):
                break
        attempts.append({"n": att, "wave": True, "kills": kills,
                         "walker": rel, "final": snap(m)})
        log(f"attempt {att}: kills={kills} walker={rel}")
    rep = {"tag": tag, "attempts": attempts,
           "wall_s": round(time.time() - t0, 1)}
    with open(os.path.join(EVID, f"report_{tag}.json"), "w") as f:
        json.dump(rep, f, indent=1, default=str)
    log("DONE", json.dumps(rep["attempts"])[:400])
    return 0


if __name__ == "__main__":
    sys.exit(main())
