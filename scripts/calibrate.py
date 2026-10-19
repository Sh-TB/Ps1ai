#!/usr/bin/env python3
"""calibrate.py v2 — per-boot semantic recalibration (READ-ONLY).

Order matters: motion scans FIRST (the player must be alive!), value
scans after. Candidates in the game's counter zone (~0xEE000-0xF0000,
seen stable across boots) get priority when several survive."""
import sys

sys.path.insert(0, "/home/z/my-project")
import numpy as np

from ps1play.agent.memscan import MemScan, DT

COUNTER_LO, COUNTER_HI = 0xEC000, 0xF0000


def addr_set(scan, name):
    sz = DT[name][0]
    return {int(i) * sz for i in np.flatnonzero(scan.masks[name])}


def _zone_pref(cands):
    """counter-zone addresses first, then by address."""
    return (sorted(a for a in cands if COUNTER_LO <= a < COUNTER_HI)
            + sorted(a for a in cands if not (COUNTER_LO <= a < COUNTER_HI)))


def calibrate(p, dbg=True):
    out = {}
    p.save_state("cal_base")

    # ============ 1) player x/y (motion, player must be alive) ===========
    p.load_state("cal_base")
    p.core.run(240, {"RIGHT"})          # distance from the left clamp
    p._advance()
    p.save_state("cal_x")
    scan = MemScan(p.mem)
    scan.reset()
    p.core.run(35, {"RIGHT"})
    scan.inc("u16"); scan.inc("u32")
    p.core.run(35, {"RIGHT"})
    scan.inc("u16"); scan.inc("u32")
    p.core.run(25, set())
    scan.unchanged("u16"); scan.unchanged("u32")
    p._advance()
    right = {"u16": addr_set(scan, "u16"), "u32": addr_set(scan, "u32")}
    p.load_state("cal_x")
    scan = MemScan(p.mem)
    scan.reset()
    p.core.run(35, {"LEFT"})
    scan.dec("u16"); scan.dec("u32")
    p.core.run(35, {"LEFT"})
    scan.dec("u16"); scan.dec("u32")
    p.core.run(25, set())
    scan.unchanged("u16"); scan.unchanged("u32")
    p._advance()
    left = {"u16": addr_set(scan, "u16"), "u32": addr_set(scan, "u32")}
    best = None
    for dt in ("u16", "u32"):
        both = sorted(right[dt] & left[dt])
        if dbg:
            print(f"x cands {dt}:", len(both),
                  [hex(a) for a in both[:8]], file=sys.stderr)
        for a in _zone_pref(both)[:8]:
            ver = p.disc.verify_series(p.states, "cal_x", a, dt,
                                       "RIGHT", frames=90, step=15)
            if ver and (best is None or ver["quality"] > best["quality"]):
                best = ver
    if best and best["quality"] >= 5:
        out["player_x"] = {"addr": best["addr"], "dtype": best["dtype"],
                           "quality": best["quality"],
                           "m_act": best["m_act"], "m_idle": best["m_idle"]}
        if dbg:
            print("x:", out["player_x"], file=sys.stderr)

    # y: jump swing
    p.load_state("cal_x")
    scan = MemScan(p.mem)
    scan.reset()
    p.core.run(40, set())
    scan.unchanged("u16"); scan.unchanged("u32")
    p.core.run(16, {"B"})
    scan.changed("u16"); scan.changed("u32")
    p.core.run(30, {"B"})
    scan.changed("u16"); scan.changed("u32")
    p.core.run(40, set())
    scan.changed("u16"); scan.changed("u32")
    p.core.run(40, set())
    scan.unchanged("u16"); scan.unchanged("u32")
    p._advance()
    yc = addr_set(scan, "u16") | addr_set(scan, "u32")
    x_addr = out.get("player_x", {}).get("addr")
    read = {"u16": p.mem.u16, "u32": p.mem.u32}
    besty = None
    for a in _zone_pref(yc)[:20]:
        if x_addr is not None and abs(a - x_addr) <= 4:
            continue
        dt = "u32" if a % 4 == 0 else "u16"
        p.load_state("cal_x")
        idle = [read[dt](a)]
        for _ in range(6):
            p.core.run(10, set())
            idle.append(read[dt](a))
        p._advance()
        p.load_state("cal_x")
        jump = [read[dt](a)]
        for _ in range(5):
            p.core.run(10, {"B"})
            jump.append(read[dt](a))
        p.core.run(40, set())
        for _ in range(4):
            p.core.run(10, set())
            jump.append(read[dt](a))
        p._advance()
        i_sw, j_sw = max(idle) - min(idle), max(jump) - min(jump)
        if j_sw >= 3 * max(i_sw, 8) and j_sw >= 48:
            besty = (a, j_sw, i_sw, dt)
            break
    if besty:
        out["player_y"] = {"addr": besty[0], "dtype": besty[3],
                           "jump_swing": besty[1], "idle_swing": besty[2]}
        if dbg:
            print("y:", out["player_y"], file=sys.stderr)

    # ============ 2) bombs: 8..15 -> -1 exactly per grenade ==============
    # TWO grenades, each decrementing by EXACTLY 1, then a no-input
    # control window: natural countdowns (timers, bonus bars) fail the
    # exact-1 or the unchanged test -> only the true count survives.
    p.load_state("cal_base")
    scan = MemScan(p.mem)
    scan.reset()
    scan.between("u16", 8, 15)
    p.core.run(15, {"A"})
    p.core.run(75, set())
    p._advance()
    scan.dec_by("u16", 1, tol=0)
    p.core.run(60, {"Y"})
    p.core.run(15, {"A"})
    p.core.run(75, set())
    p._advance()
    scan.dec_by("u16", 1, tol=0)
    p.core.run(180, set())
    p._advance()
    scan.unchanged("u16")
    bc = _zone_pref(addr_set(scan, "u16"))
    if dbg:
        print("bombs cands:", [hex(a) for a in bc[:6]], file=sys.stderr)
    if bc:
        out["bombs"] = {"addr": bc[0], "dtype": "u16"}

    # ============ 3) hp: full=200 or 100 -> dec on a melee stab ==========
    for lo, hi in ((190, 215), (90, 112)):
        p.load_state("cal_base")
        scan = MemScan(p.mem)
        scan.reset()
        scan.between("u16", lo, hi)
        p.core.run(420, set())          # stand -> soldier reaches us
        p._advance()
        scan.dec("u16")
        hc = _zone_pref(addr_set(scan, "u16"))
        if dbg:
            print(f"hp cands [{lo},{hi}]:", [hex(a) for a in hc[:6]],
                  file=sys.stderr)
        if hc:
            out["hp"] = {"addr": hc[0], "dtype": "u16", "full": hi - 15}
            break

    # ============ 4) timer: 1 Hz countdown, two passes ===================
    def _tset():
        p.load_state("cal_base")
        s = MemScan(p.mem)
        s.reset()
        p.core.run(300, set())
        s.dec_by("u16", 5, tol=1)
        p._advance()
        return addr_set(s, "u16")

    ts = _tset() & _tset()
    tc = [a for a in _zone_pref(ts) if 0 < p.mem.u16(a) <= 300]
    if dbg:
        print("timer cands:", [hex(a) for a in tc[:6]], file=sys.stderr)
    if tc:
        out["timer"] = {"addr": tc[0], "dtype": "u16"}

    # ============ 5) write into the live profile =========================
    gs = p.profile.setdefault("gsmap", {})
    for role, spec in out.items():
        if role in ("player_x", "player_y"):
            d = p.profile.setdefault("discovered", {})
            d[role] = {"addr": spec["addr"], "dtype": spec["dtype"],
                       "score": int(spec.get("quality")
                                    or spec.get("jump_swing", 0)),
                       "dir": "+", "verified": "calibration"}
        else:
            gs.setdefault(role, {}).update(
                {"addr": spec["addr"], "dtype": spec["dtype"],
                 "verified": True, "last_value": None,
                 "evidence": "boot-time calibration"})
    p.save_profile()
    return out


if __name__ == "__main__":
    from ps1play.api import PS1Play
    GAME = "/home/z/my-project/ps1-test/emu/games/Metal Slug X (USA).cue"
    p = PS1Play(GAME, verbose=False)
    p.boot()
    r = p.enter_gameplay3()
    print("enter:", r.get("in_game"), flush=True)
    import json
    print(json.dumps(calibrate(p), indent=1))
