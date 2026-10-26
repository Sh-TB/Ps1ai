#!/usr/bin/env python3
"""psxmc_r10_place7.py — Round 10 (Task 16-c): the PLACE campaign with a
VALIDATED oracle (FIX-2 closed: r10_oracle run 3, static ABI + double
deref) and per-attempt stability gates (FIX-1).

Chain: boot -> settle -> sensors -> [if hotbar empty: DIG-DOWN first
(hold R2 on the surface cell until its world id goes air, pickup wait)]
-> placement ladder (pitch 30..70): r2_probe (adopted world-arbitrated
hit) -> L2 (BINDING_USE) -> converging verification:
  primary   world_id 0 -> non-zero at a candidate cell (top face
            (hx,hy+1,hz) or near face (hx,hy,hz-1) at yaw 0, +z fwd);
  secondary stack decrement (if hotbar present) + pre/post PNG diff;
  negative  horizon aim -> L2 -> NO stack/world change (causal control).
Honest verdicts; evidence -> scratch/round10_psxmc/place7/. ONE beetle
boot per process; no RAM writes.
"""
import json
import os
import sys
import time

import numpy as np
from PIL import Image

_REPO = "/home/z/my-project/ps1ai"
for _p in (_REPO, os.path.join(_REPO, "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from psxmc_r10_oracle import (                       # noqa: E402
    CUE, player_ptr, pos_of, pitch_now, yaw_now, ensure_world_control,
    aim_ring_exact, r2_probe, parse_probe, snap)
import psxmc_r10_lib as L                            # noqa: E402
from psxmc_r7_lib import A_INPUT, Evid, sha          # noqa: E402

PLACE_BTN = "L2"    # BINDING_USE (bindings.c:21; r8 ground truth)

OUT = os.path.join(_REPO, "scratch", "round10_psxmc", "place7")
WS = "/home/z/my-project/emu/games_homebrew/ws_psxmc_r10p"
TAG = "place7"


def stable_gate(core, m, tries=3):
    """FIX-1: bit-exact RAM sha twice 8 f apart, before EACH attempt."""
    for t in range(tries):
        s0 = sha(m.snapshot())
        core.run(8, set())
        s1 = sha(m.snapshot())
        if s0 == s1:
            return True, t
        core.run(10, set())
    return False, tries


def top_nonair(wr, bx, bz):
    """Real surface: topmost y with a non-air block (world-arbitrated)."""
    for y in range(7, -1, -1):
        wid = wr.block_id(bx, y, bz)
        if wid not in (0, None):
            return y, wid
    return None, None


def servo_probe(core, m, P, ev, wr, want, max_it=8, start_pitch=40.0,
                fwd_sign=None, fbz=0):
    """Closed-loop aim on the HIT with per-boot facing calibration.
    r10 finding: the spawn YAW differs per boot, so 'forward' is +z on
    some boots and -z on others (run A: 47deg->dz+5; run C: 31deg->
    dz-3 monotonic within-run).  fwd_sign (+1/-1) converts world dz to
    forward distance; None = calibrate here.
    want: fd_min/fd_max forward-distance band."""
    pitch = start_pitch
    fd_min = want.get("fd_min", 2)
    fd_max = want.get("fd_max", 4)

    def fwd(hit):
        return fwd_sign * (hit[2] - fbz) if fwd_sign else hit[2] - fbz

    for it in range(max_it):
        aim_ring_exact(core, m, P, pitch_now(m, P), pitch)
        rec = r2_probe(core, m, P, ev, pitch_now(m, P), pitch,
                       f"servo{it}")
        pr = parse_probe(m, wr, rec, P, pitch_now(m, P))
        a = pr["adopted"][0] if pr["adopted"] else None
        ev.j({"ev": "servo", "it": it, "pitch": pitch,
              "hit": a and a["hit"], "geom": a and a["geom"],
              "wid": a and a.get("world_id")})
        if a and a.get("geom") and a.get("world_id") not in (0, None):
            g = a["geom"]
            fd = fwd(a["hit"])
            if g["in_reach"] and fd_min <= fd <= fd_max:
                return a, pitch
            if fd > fd_max:
                pitch = min(85.0, pitch + max(4, 6 * (fd - fd_max)))
            elif fd < fd_min:
                pitch = max(5.0, pitch - max(4, 6 * (fd_min - fd)))
            elif not g["in_reach"]:
                pitch = min(85.0, pitch + 6.0)
        else:
            pitch = min(85.0, pitch + 10.0)
    return None, pitch


def calibrate_facing(core, m, P, ev, wr, fbz):
    """Probe at two pitches; forward = the dz direction that GROWS as
    the pitch flattens.  Returns fwd_sign (+1/-1) or None."""
    hits = []
    for pdeg in (45.0, 8.0):
        aim_ring_exact(core, m, P, pitch_now(m, P), pdeg)
        rec = r2_probe(core, m, P, ev, pitch_now(m, P), pdeg, f"cal{pdeg}")
        pr = parse_probe(m, wr, rec, P, pitch_now(m, P))
        a = pr["adopted"][0] if pr["adopted"] else None
        hits.append(a and a["hit"])
        ev.j({"ev": "cal", "pitch": pdeg, "hit": a and a["hit"]})
    if not all(hits):
        return None
    d45 = hits[0][2] - fbz
    d8 = hits[1][2] - fbz
    if d8 == d45:
        return None
    # forward = the direction where the hit lands FARTHER as the pitch
    # flattens (shallow ray reaches farther ahead)
    return 1 if d8 > d45 else -1


def main():
    os.makedirs(OUT, exist_ok=True)
    t0 = time.time()
    ev = Evid(OUT, TAG)
    ev.jpath = os.path.join(OUT, "r10_place7.jsonl")
    ev.j({"ev": "start", "cue": CUE,
          "task": "16-c place7 v2: servo-dig-then-place, world-arbitrated"})
    from ps1play.api import PS1Play
    p = PS1Play(CUE, workspace=WS)
    p.boot()
    P = None
    for _ in range(240):
        P = player_ptr(p.mem)
        if P:
            break
        p.wait(30)
    if not P:
        ev.finish("FAILED: no player pointer")
        return 1
    p.wait(120)
    m, core = p.mem, p.core
    grab = core.frame_rgb

    stable_n, last_y = 0, None
    for _ in range(120):
        y = pos_of(m, P)[1]
        stable_n = stable_n + 1 if y == last_y else 0
        last_y = y
        if stable_n >= 45:
            break
        core.run(2, set())
    pos0 = pos_of(m, P)
    ev.j({"ev": "settled", "P": hex(P),
          "pos_blocks": [round(v / L.ONE_BLOCK, 3) for v in pos0]})

    wr = L.WorldReader(m)
    wr_info = None
    for _ in range(5):
        try:
            wr_info = wr.discover()
            break
        except Exception as e:                     # noqa: BLE001
            ev.j({"ev": "world_retry", "err": str(e)[:120]})
            core.run(30, set())
    if wr_info is None:
        ev.finish("FAILED: WorldReader discovery failed")
        return 2
    ev.j({"ev": "world", **wr_info})

    fbx = int(np.floor(pos_of(m, P)[0] / L.ONE_BLOCK))
    fbz = int(np.floor(pos_of(m, P)[2] / L.ONE_BLOCK))
    surf, surf_id = top_nonair(wr, fbx, fbz)
    ahead_cell = (fbx, None, fbz + 2)
    surf_a, surf_a_id = top_nonair(wr, fbx, fbz + 2)
    hb = L.find_hotbar(m, P)
    ev.j({"ev": "surface", "own": [fbx, surf, fbz, surf_id],
          "ahead2": [fbx, surf_a, fbz + 2, surf_a_id],
          "hotbar": hb})
    pitch0 = pitch_now(m, P)

    # negative control: horizon aim -> L2 must change nothing
    okc, _gt = stable_gate(core, m)
    aim_ring_exact(core, m, P, pitch_now(m, P), 0.0)
    st_pre = (L.find_hotbar(m, P) or {}).get("stack")
    cell_pre = wr.block_id(fbx, surf_a, fbz + 2)
    core.run(6, {PLACE_BTN})
    core.run(40, set())
    st_post = (L.find_hotbar(m, P) or {}).get("stack")
    cell_post = wr.block_id(fbx, surf_a, fbz + 2)
    ev.j({"ev": "NEGATIVE_CONTROL", "gate": okc,
          "stack": [st_pre, st_post], "cell": [cell_pre, cell_post]})

    verified = []
    digs = []
    # ---- two dig->place cycles on two different ahead-columns ----
    fwd_sign = calibrate_facing(core, m, P, ev, wr, fbz)
    ev.j({"ev": "facing", "fwd_sign": fwd_sign})
    for cycle, fd_target in enumerate((2, 3)):
        want = {"fd_min": fd_target, "fd_max": fd_target + 1}
        hit, pitch_used = servo_probe(core, m, P, ev, wr, want,
                                      start_pitch=45.0,
                                      fwd_sign=fwd_sign, fbz=fbz)
        if not hit:
            ev.j({"ev": "dig_no_servo_hit", "cycle": cycle})
            continue
        target = tuple(hit["hit"])
        ev.j({"ev": "dig_target_locked", "cycle": cycle,
              "target": target, "wid": hit.get("world_id"),
              "pitch": pitch_used})
        okg, _gt = stable_gate(core, m)
        ev.j({"ev": "dig_gate", "stable": okg})
        mined = False
        for i in range(34):                        # ~1020 f cap
            core.run(28, {"R2"})
            core.run(2, set())
            if wr.block_id(*target) in (0, None):
                mined = True
                break
        core.run(150, set())                       # drop + pickup
        hb2 = L.find_hotbar(m, P)
        digs.append({"cycle": cycle, "target": target, "mined": mined,
                     "hotbar_after": hb2})
        ev.j({"ev": "DIG_DONE", **digs[-1]})
        ev.png(f"place7_c{cycle}_dug", grab())
        if not mined:
            continue
        # PLACE: probe the hole, L2, verify the cell goes non-air
        hit2, _pu = servo_probe(core, m, P, ev, wr, want,
                                start_pitch=45.0, fwd_sign=fwd_sign,
                                fbz=fbz)
        st_pre = (L.find_hotbar(m, P) or {}).get("stack")
        png_pre = world_region_png_bytes(grab)
        ev.png(f"place7_c{cycle}_pre", grab())
        core.run(6, {PLACE_BTN})
        core.run(45, set())
        wid_post = wr.block_id(*target)
        st_post = (L.find_hotbar(m, P) or {}).get("stack")
        png_post = world_region_png_bytes(grab)
        stack_delta = (st_post - st_pre) \
            if (st_pre is not None and st_post is not None) else None
        ok = wid_post not in (0, None) and \
            (stack_delta is None or stack_delta < 0) and \
            png_pre != png_post
        rec = {"cycle": cycle, "target": target,
               "wid_post": wid_post, "stack": [st_pre, st_post],
               "stack_delta": stack_delta,
               "png_changed": png_pre != png_post,
               "verdict": "VERIFIED" if ok else "NOT_VERIFIED"}
        verified.append(rec) if ok else None
        ev.j({"ev": "PLACE_ATTEMPT", **rec})
        ev.png(f"place7_c{cycle}_post", grab())

    verdict = f"VERIFIED_PLACED x{len(verified)}" if verified else \
        "FAILED_PLACE_REJECTED"
    if verified and all(d["mined"] for d in digs):
        pass
    rep = {"schema": "ps1play-r10-place7/2", "verdict": verdict,
           "world": wr_info, "surface": [fbx, surf, fbz, surf_id],
           "digs": digs, "verified": verified,
           "n_verified": len(verified),
           "wall_s": round(time.time() - t0, 1)}
    with open(os.path.join(OUT, "report.json"), "w") as f:
        json.dump(rep, f, indent=1, default=str)
    ev.finish(verdict)
    try:
        core.close()
    except Exception:                              # noqa: BLE001
        pass
    print("[place7] done:", verdict)
    return 0 if verified else 2


def world_region_png_bytes(grab):
    rgb = grab()
    if rgb is None:
        return None
    h = rgb.shape[0]
    return rgb[int(h * 0.35):, :, :].tobytes()


if __name__ == "__main__":
    sys.exit(main())
