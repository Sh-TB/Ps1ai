#!/usr/bin/env python3
"""truck_wreck_release.py — the wreck-clearance release experiment.

Model so far (this session, all live-evidenced):
  * truck parked AHEAD at 1126.5 (revived anchor) -> 3-lobe kill works
    (230->130->30->0, +800 score)
  * the WRECK physically blocks the road: post-kill walks freeze at
    ~1058 = the wreck's left edge; hop-advance + hop-dodges are no-ops
    against it (kr_rep9)
  * the historical anchor had the truck parked BEHIND (937.5) -> no
    block -> the real D7 pin (0xA,0x43 @1164)

THIS test: kill -> retreat to the survivable hold band [950,1000]
(the CLAMP-ROOT band, 200f hop cadence) -> poll the corpse slot until
it clears (states 0xa304/0xa44c -> gone/0x4BE4?) -> walk right ->
release test (px > 1170).

READ-ONLY. Usage: python3 scripts/truck_wreck_release.py
"""
import json, os, sys, time
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
EVID = os.path.join(labconfig.resolve_path("evidence_dir"),
                    "issue5_truck_release")
HOLD_LO, HOLD_HI = 950.0, 985.0
WAIT_BUDGET = 7200
DEAD_ST = (0x4BE4, 0x5CC8)


def log(*a):
    print("[wr]", *a, file=sys.stderr, flush=True)


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
                    "h": int(tv[s, 63]), "hpA4": int(tv[s, 82])})
    return out


def find_truck_slot(m):
    """Parked truck OR wreck (0x9E88 alive / 0xa304/0xa44c wreck)."""
    for sl in raw_slots(m):
        if sl["st"] in (0x9E88, 0xA304, 0xA44C) and sl["h"] == 64:
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


def png(p, name):
    rgb = p.core.frame_rgb()
    if rgb is not None:
        Image.fromarray(rgb).save(
            os.path.join(EVID, f"wreck_{name}.png"))


def main():
    os.makedirs(EVID, exist_ok=True)
    jf = open(os.path.join(EVID, "wreck_trace.jsonl"), "w")

    def J(ev):
        jf.write(json.dumps(ev, default=str) + "\n"); jf.flush()

    p, fw = boot()
    m = p.mem
    p.load_state("truck_engage")
    for _ in range(3):
        p.core.run_frame()
    ok, s0 = alive(m)
    J({"ev": "start", **s0})
    if not ok:
        log("anchor dead on load"); jf.close(); return 1

    # ---- 1) KILL (lob immediately from the load position; the debug
    # PNG shows soldiers ON the truck whose contact-push defeats
    # reposition walks — kr_rep2 proved blind alternating lobs connect
    # within ~8 throws) ----------------------------------------------
    hp_track, killed = [], False
    for lobs in range(14):
        ok, s = alive(m)
        if not ok:
            J({"ev": "death_kill", "hp_track": hp_track, **s})
            log(f"DIED killing track={hp_track}")
            jf.close(); return 1
        trk = find_truck_slot(m)
        if trk is None or trk["st"] != 0x9E88 or trk["hpA4"] <= 0:
            killed = trk is None or trk["st"] != 0x9E88
            J({"ev": "truck_down", "slot": trk, "hp_track": hp_track})
            log(f"truck down: slot={trk} track={hp_track}")
            break
        if int(m.u8(GRENADES)) <= 0:
            log("OUT OF GRENADES mid-kill"); break
        dx = trk["x"] - px_of(m)
        face = {"RIGHT"} if dx > 0 else {"LEFT"}
        if lobs % 2 == 0:
            p.core.run(2, face); p.core.run(8, face | {"A"})
        else:
            p.core.run(3, face | {"UP"})
            p.core.run(6, face | {"UP", "A"})
        p.core.run(2, set()); p.core.run(35, set())
        nt = find_truck_slot(m)
        hp_track.append(nt["hpA4"] if nt and nt["st"] == 0x9E88
                        else (0 if nt is None else nt["hpA4"]))
        J({"ev": "lob", "n": lobs, "dx": round(dx, 1),
           "hp": hp_track[-1], "px": round(px_of(m), 1)})
    if not killed:
        log(f"kill incomplete: track={hp_track}")
        jf.close(); return 1
    png(p, "truck_dead")
    wreck0 = find_truck_slot(m)
    J({"ev": "KILLED", "hp_track": hp_track, "wreck": wreck0,
       **snap(m)})
    log(f"KILLED track={hp_track} wreck={wreck0}")

    # ---- 2) RETREAT to the hold band -------------------------------
    for k in range(300):
        ok, s = alive(m)
        if not ok:
            J({"ev": "death_retreat", **s}); log("DIED retreating")
            jf.close(); return 1
        px = px_of(m)
        if px <= HOLD_HI:
            break
        fall = faller_near(m, px)
        if fall is not None:
            away = {"LEFT"} if fall["x"] > px else {"RIGHT"}
            p.core.run(3, {"B"}); p.core.run(10, {"B"} | away)
            p.core.run(4, set())
            continue
        p.core.run(8, {"LEFT"})
    J({"ev": "retreated", **snap(m)})

    # ---- 3) WAIT for the wreck to clear ----------------------------
    cleared = False
    corpse_log = []
    w0 = p.core.frames_run
    last_hop = w0
    while p.core.frames_run - w0 < WAIT_BUDGET:
        ok, s = alive(m)
        if not ok:
            J({"ev": "death_wait", **s, "corpse_log": corpse_log[-6:]})
            log("DIED waiting"); png(p, "wait_death")
            jf.close(); return 1
        px = px_of(m)
        wrk = find_truck_slot(m)
        corpse_log.append({"f": p.core.frames_run - w0,
                           "wreck": wrk, "px": round(px, 1)})
        if wrk is None or wrk["st"] in DEAD_ST:
            cleared = True
            J({"ev": "WRECK_CLEARED", "at_f": p.core.frames_run - w0,
               **snap(m)})
            log(f"WRECK CLEARED at f={p.core.frames_run - w0}")
            png(p, "wreck_cleared")
            break
        now = p.core.frames_run
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
        elif px > HOLD_HI:
            p.core.run(12, {"LEFT"})
        elif px < HOLD_LO:
            p.core.run(8, {"RIGHT"})
        else:
            p.core.run(10, set())
        if (now - w0) % 300 < 12:
            J({"ev": "wait", **snap(m), "wreck": wrk,
               "slots": raw_slots(m)})
    if not cleared:
        J({"ev": "WRECK_NEVER_CLEARED", "corpse_log": corpse_log[-8:],
           **snap(m)})
        log(f"wreck never cleared in {WAIT_BUDGET}f: "
            f"{corpse_log[-3:]}")
        jf.close(); return 1

    # ---- 4) RELEASE WALK -------------------------------------------
    max_px, passed = px_of(m), False
    f0 = p.core.frames_run
    while p.core.frames_run - f0 < 2400:
        ok, s = alive(m)
        if not ok:
            J({"ev": "death_walk", "max_px": round(max_px, 1), **s})
            log(f"DIED walking max={max_px:.1f}"); png(p, "walk_death")
            break
        px0 = px_of(m)
        fall = faller_near(m, px0)
        if fall is not None:
            away = {"LEFT"} if fall["x"] > px0 else {"RIGHT"}
            p.core.run(3, {"B"}); p.core.run(10, {"B"} | away)
            p.core.run(4, set())
            continue
        p.core.run(30, {"RIGHT"})
        s = snap(m)
        max_px = max(max_px, s["px"])
        J({"ev": "walk", **s})
        if s["px"] > 1170.0:
            passed = True
            J({"ev": "PASSED_1170", **s})
            png(p, "RELEASED")
            p.core.run(300, {"RIGHT"})
            break

    res = {"killed": killed, "hp_track": hp_track, "cleared": cleared,
           "released": passed, "max_px": round(max_px, 1),
           "final": snap(m), "wait_frames": WAIT_BUDGET if cleared
           else p.core.frames_run - w0}
    with open(os.path.join(EVID, "wreck_report.json"), "w") as f:
        json.dump(res, f, indent=1)
    jf.close()
    log("DONE", json.dumps({k: res[k] for k in
        ("killed", "cleared", "released", "max_px")}))
    return 0


if __name__ == "__main__":
    main()
