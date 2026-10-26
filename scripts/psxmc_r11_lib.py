#!/usr/bin/env python3
"""psxmc_r11_lib.py — Round 11 (Task 17-b): canonical-latch disambiguation.

The round-10 recorded lever: the player struct retains SEVERAL
breaking-like i32 triples (BreakingState latches the raycast hit per
upstream player.c:134); the r10 diff-based parse could adopt a STALE
mirror, decoupling the hit from the ring pitch => place7 v2-v5
FAILED_PLACE_REJECTED.

This module closes the lever with the STATIC ground truth of the fixed
infdev_2025_04_18 binary (capstone, see scripts/psxmc_r11_latch_offset.py):

  Player.breaking @ +0x6C          (updateBreakingState 0x80013CD4:
                                    addiu $s3, $a0, 0x6C)
  breaking.ticks_precise  @ +0x6C  (sw $zero, 0x6C($s0) @0x80013F40)
  breaking.ticks_per_stage@ +0x70
  breaking.ticks_so_far   @ +0x74  (+= ONE per held tick @0x80013D44)
  breaking.position       @ +0x78  (VECTOR vx,vy,vz = raycast hit cell,
                                    re-stored from result->pos
                                    @0x80013F60..68)
  breaking.flags u8       @ +0x84  (visible_sides:6 | remesh_trig:1 |
                                    reset_trigger:1)
  breaking.block (IBlock*)@ +0x88  (result->block @0x80013F6C)

breaking_current() reads THE CURRENT latch triple at the fixed offset
(no candidate ambiguity).  RepeatLatchTracker implements the second half
of the recorded lever: sample the window on N consecutive r2_probes —
the live latch updates on every probe (re-latch zeroes ticks_so_far and
re-stores the position; chunk.c:772 breaksStateReset zeroes the window
within a frame or two of release), stale mirrors stay frozen.

Everything else reuses psxmc_r10_lib / psxmc_r10_oracle unchanged
(WorldReader static ABI, validate_known_hit, stability, r2_probe).
"""
import numpy as np

import psxmc_r10_lib as L  # noqa: E402

# ---- static latch ground truth (player.c:134, fixed binary) ----------------
BREAKING_OFF = 0x6C            # Player.breaking (addiu $s3, $a0, 0x6C)
BREAKING_LAYOUT = {            # offsets relative to P (player base)
    "ticks_precise": 0x6C,     # fixedi32
    "ticks_per_stage": 0x70,   # fixedi32
    "ticks_so_far": 0x74,      # fixedi32 (+ONE per held tick)
    "position": 0x78,          # VECTOR vx,vy,vz (i32 hit cell coords)
    "flags": 0x84,             # u8 bitfield (sides:6|remesh:1|reset:1)
    "block": 0x88,             # IBlock* (NULL == not breaking)
}
BREAKING_SIZE = 0x20

# provenance addresses (map + capstone, psxmc_r11_latch_offset.py)
UBS_VA = 0x80013C9C            # updateBreakingState (player.c:134, size 0x530)
STORE_SITE_VA = 0x80013F40     # sw $zero, 0x6C($s0) .. sw $a1, 0x88($s0)
PIH_VA = 0x800141CC            # playerInputHandler
LATCH_CALL_VA = 0x800144A4     # jal updateBreakingState (raycast 0x8001445C)
USE_RAYCAST_VA = 0x80014570    # playerInputHandlerUse raycast
PLAYER_INIT_VA = 0x80013954    # playerInit (breakingStateReset inlined)


def _words4(snap, off):
    """off = address of BreakingState.position; block ptr sits 0x10 past
    it (position +0x78, block +0x88 => +0x10)."""
    i = off >> 2
    a = np.frombuffer(bytes(snap), "<i4")
    u = np.frombuffer(bytes(snap), "<u4")
    return [int(a[i]), int(a[i + 1]), int(a[i + 2])], int(u[(off + 0x10) >> 2])


def breaking_current(m, P, snap=None):
    """Read the CURRENT BreakingState window at the STATIC offset.

    m: memory view (live read) OR ignored when snap is given.
    snap: optional full-RAM snapshot bytes (parse offline, e.g. the
    while-holding-R2 snapshot from r2_probe — FIX-2 protocol).

    Returns dict: hit (i32 triple), block_ptr (u32), ticks (3x i32),
    flags (u8), live (block_ptr is a heap pointer AND hit non-zero).
    """
    if snap is not None:
        hit, blk = _words4(snap, P + BREAKING_LAYOUT["position"])
        w = np.frombuffer(bytes(snap), "<u4")
        b = np.frombuffer(bytes(snap), "<u1")
        tp = int(np.frombuffer(bytes(snap[P + 0x6C:P + 0x70]), "<i4")[0])
        tps = int(np.frombuffer(bytes(snap[P + 0x70:P + 0x74]), "<i4")[0])
        tsf = int(np.frombuffer(bytes(snap[P + 0x74:P + 0x78]), "<i4")[0])
        fl = int(b[P + 0x84])
    else:
        hit = [L.s32(m.u32(P + BREAKING_LAYOUT["position"])),
               L.s32(m.u32(P + BREAKING_LAYOUT["position"] + 4)),
               L.s32(m.u32(P + BREAKING_LAYOUT["position"] + 8))]
        blk = int(m.u32(P + BREAKING_LAYOUT["block"]))
        tp = L.s32(m.u32(P + 0x6C))
        tps = L.s32(m.u32(P + 0x70))
        tsf = L.s32(m.u32(P + 0x74))
        fl = int(m.u8(P + 0x84))
        w = None
    return {"hit": hit, "block_ptr": blk,
            "ticks": {"precise": tp, "per_stage": tps, "so_far": tsf},
            "flags": fl,
            "live": bool(L.is_heap(blk)) and hit != [0, 0, 0]}


def zero_current(m, P):
    """breakingStateReset state: the window is fully zeroed."""
    return breaking_current(m, P) == {
        "hit": [0, 0, 0], "block_ptr": 0,
        "ticks": {"precise": 0, "per_stage": 0, "so_far": 0},
        "flags": 0, "live": False}


class RepeatLatchTracker:
    """The live latch UPDATES on every new r2_probe; stale mirrors freeze.

    observe() once per probe with the parse_probe_current record.  The
    live-consistency evidence collected across probes:
      * every live observation reset on release (chunk.c:772 — stale
        mirrors never reset),
      * ticks_so_far GREW within a hold (mid -> mid2) at least once,
      * the hit position FOLLOWED THE AIM across different-aim probes.
    Frozen windows show none of these.
    """

    def __init__(self, min_live=2):
        self.obs = []
        self.min_live = min_live

    def observe(self, parse):
        self.obs.append(parse)
        return self.verdict()

    def verdict(self):
        live = [o for o in self.obs if o.get("live")]
        n = len(self.obs)
        resets_ok = all(o.get("reset_by_late") for o in live)
        grew = any(o.get("ticks_grew") for o in live)
        aims = set()
        hits = set()
        for o in live:
            if o.get("aim_deg") is not None:
                aims.add(round(o["aim_deg"], 1))
                hits.add(tuple(o.get("hit") or ()))
        follows = len(aims) >= 2 and len(hits) >= 2
        ok = (len(live) >= self.min_live and resets_ok
              and (grew or follows))
        why = "" if ok else (
            f"n_live={len(live)}<min" if len(live) < self.min_live else
            "a live observation never reset (stale mirror?)"
            if not resets_ok else
            "no tick growth and hit does not follow aim (frozen?)")
        return {"n": n, "n_live": len(live), "resets_ok": resets_ok,
                "ticks_grew": grew, "pos_follows_aim": follows,
                "n_aims": len(aims), "n_hits": len(hits),
                "live": bool(ok), "why": why}


def agree_with_diff_candidates(snap_mid, snap_base, P, cam_y, pos,
                               search=0x800):
    """Cross-check: the static window must also appear among the r10
    diff-based candidates (same block-ptr slot, overlapping triple)."""
    cands = L.breaking_candidates(snap_mid, snap_base, P, cam_y, pos,
                                  search=search)
    hits = [c for c in cands
            if c["ptr_off"] == BREAKING_LAYOUT["block"]
            and BREAKING_LAYOUT["position"] - 0x10 <= c["off"]
            <= BREAKING_LAYOUT["position"]]
    return cands, hits


def parse_probe_current(wr, rec, P, pitch0=None):
    """Disambiguated r2_probe parse (place8): read ONLY the static
    CURRENT window from the while-holding snapshots; arbitrate with the
    world; require the release-reset (chunk.c:772) for 'current' proof.

    rec: probe record with pos/base(pre)/mid(hold)/rel/late snapshots
    (mid2 optional: end-of-hold snapshot for tick-growth telemetry).
    Returns a flat adoption record (dict) — live=False when dead.
    """
    cam_y, feet = L.camera_world_y(rec["pos"][1])
    cur = breaking_current(None, P, snap=rec["mid"])
    late = breaking_current(None, P, snap=rec["late"])
    rel = breaking_current(None, P, snap=rec["rel"])
    cur["reset_by_late"] = (late["hit"] == [0, 0, 0]
                            and late["block_ptr"] == 0)
    cur["rel_hit"] = rel["hit"]
    cur["cam_y"] = round(cam_y, 2)
    cur["feet"] = round(feet, 2)
    cur["pos_blocks"] = [round(v / L.ONE_BLOCK, 2) for v in rec["pos"]]
    cur["pitch_deg"] = rec.get("pitch_deg")
    cur["aim_deg"] = rec.get("aim_deg")
    if "mid2" in rec and rec["mid2"] is not None:
        mid2 = breaking_current(None, P, snap=rec["mid2"])
        cur["ticks_so_far_end"] = mid2["ticks"]["so_far"]
        cur["ticks_grew"] = (cur["live"]
                             and mid2["ticks"]["so_far"]
                             > cur["ticks"]["so_far"])
    if not cur["live"]:
        cur["ok"] = False
        cur["why"] = "no live latch at static window"
        return cur
    g = L.hit_geometry(cur["hit"], rec["pos"], cam_y)
    cur["geom"] = g
    wid = wr.block_id(*cur["hit"]) if wr is not None else None
    cur["world_id"] = wid
    cur["world_arbitrated"] = wid not in (None, 0)
    cur["ok"] = bool(cur["reset_by_late"] and cur["world_arbitrated"])
    cur["why"] = "" if cur["ok"] else (
        "latch not reset after release (stale window?)"
        if not cur["reset_by_late"] else
        f"world says air at hit {cur['hit']} (wid={wid})")
    return cur


# ---------------- place8 helpers (dig-down + servo on current latch) --------
def top_nonair(wr, bx, bz):
    for y in range(L.WORLD_HEIGHT - 1, -1, -1):
        wid = wr.block_id(bx, y, bz)
        if wid not in (0, None):
            return y, wid
    return None, None


def stable_gate(core, m, tries=3):
    """FIX-1: bit-exact RAM sha twice 8 f apart, before EACH attempt."""
    for t in range(tries):
        s0 = L.sha(m.snapshot())
        core.run(8, set())
        s1 = L.sha(m.snapshot())
        if s0 == s1:
            return True, t
        core.run(10, set())
    return False, tries


def calibrate_facing(core, m, P, ev, wr, fbz, probe_fn):
    """place7 method, parse via parse_probe_current: forward = the dz
    direction where the hit lands FARTHER as the pitch flattens."""
    hits = []
    for pdeg in (45.0, 8.0):
        a = probe_fn(core, m, P, ev, wr, pdeg, f"cal{int(pdeg)}")
        hits.append(a["hit"] if a.get("ok") else None)
        ev.j({"ev": "cal", "pitch": pdeg, "ok": a.get("ok"),
              "hit": a.get("hit")})
    if not all(hits):
        return None
    d45 = hits[0][2] - fbz
    d8 = hits[1][2] - fbz
    if d8 == d45:
        return None
    return 1 if d8 > d45 else -1


def servo_probe_current(core, m, P, ev, wr, probe_fn, want,
                        max_it=8, start_pitch=45.0, fwd_sign=None, fbz=0):
    """Closed-loop aim on the CURRENT latch (static window).  want:
    fd_min/fd_max forward-distance band.  Returns (adoption, pitch)."""
    pitch = start_pitch
    fd_min = want.get("fd_min", 2)
    fd_max = want.get("fd_max", 4)

    def fwd(hit):
        return fwd_sign * (hit[2] - fbz) if fwd_sign else hit[2] - fbz

    for it in range(max_it):
        rec = probe_fn(core, m, P, ev, wr, pitch, f"servo{it}",
                       want_probe_rec=True)
        a = rec["parse"]
        ev.j({"ev": "servo", "it": it, "pitch": pitch,
              "ok": a.get("ok"), "hit": a.get("hit"),
              "geom": a.get("geom"), "wid": a.get("world_id")})
        if a.get("ok") and a.get("geom"):
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


PLACED_CANDIDATES = ("top", "near", "far", "left", "right")


def placement_candidates(hit, fwd_sign):
    """Candidate cells for vec3_add(result.pos, result.face): the raycast
    entry face is the top (hy+1) or the facing-normal cell; we probe the
    full 5-neighbourhood and let the world walk arbitrate which went
    non-air (place7 battery, now with a signed near/far pair)."""
    hx, hy, hz = hit
    f = 1 if fwd_sign in (1, None) else -1
    return {"top": (hx, hy + 1, hz),
            "near": (hx, hy, hz - f),
            "far": (hx, hy, hz + f),
            "left": (hx - 1, hy, hz),
            "right": (hx + 1, hy, hz)}


# ---------------- exact ring aim (player.c movement handler) -----------------
# player.c playerInputHandlerMovement:
#   rotation.pitch = positiveModulo(pitch +/- ONE*ROTATION_SPEED, 2^24)
# per handler call (~60 Hz): the ring moves EXACTLY 15 GTE-degrees per
# frame while LOOK_DOWN/LOOK_UP is held.  Reachable rings are therefore
# spawn_ring + k*step — aim by DEAD RECKONING (frame-exact), not by the
# r10 feedback loop (whose 1-frame fine step IS 15 deg, so its 0.35 deg
# tolerance was unreachable and it stalled up to ~7.5 deg off).
def measure_ring_step(core, pitch_now_fn, probe_btns=("B", "X")):
    """Measure the per-frame ring step with 2 LOOK_DOWN frames."""
    r0 = pitch_now_fn()
    core.run(1, {probe_btns[0]})
    r1 = pitch_now_fn()
    core.run(1, {probe_btns[0]})
    r2 = pitch_now_fn()
    step = L.ring_diff(r1, r2)
    if abs(step) < int(1.0 * L.DEG):          # no/insane response
        step = int(round(15.0 * L.DEG))       # source: ONE*ROTATION_SPEED
    return step, r2


def nearest_reachable_ring(ref_raw, target_deg, step_raw):
    """Ring = ref + k*step nearest to target_deg (mod 360).  Returns
    (ring_raw, achieved_deg).

    The ring is a RAW-integer actuator (the measured LOOK step is an
    integer, 15 GTE-degrees approximated), so the reachable grid is
    ref_raw + k*step_raw in INTEGER space — never round(k*step_deg*DEG)
    (that re-derives the step from the ideal float and drifts up to a
    few raw units per k, which made the r11-latch_offset v1 aims miss
    by 4+ raw and the tick-growth telemetry disagree)."""
    step_deg = step_raw / L.DEG
    ref_deg = (ref_raw % L.PITCH_MOD) / L.DEG
    k = round(((target_deg - ref_deg) % 360.0) / step_deg)
    ring = int(int(ref_raw) + k * int(step_raw)) % L.PITCH_MOD
    return ring, round((ref_deg + k * step_deg) % 360.0, 2)


def aim_ring_dead_reckon(core, pitch_now_fn, target_ring, step_raw,
                         down_btn="B", up_btn="X"):
    """Frame-exact aim to target_ring using LOOK step quantization."""
    cur = pitch_now_fn()
    d = L.ring_diff(cur, target_ring)
    n = int(round(d / step_raw))
    if n:
        core.run(abs(n), {down_btn if d > 0 else up_btn})
    err = L.ring_diff(pitch_now_fn(), target_ring)
    n2 = 0
    if abs(err) > abs(step_raw) // 2:
        n2 = int(round(err / step_raw))
        if n2:
            core.run(abs(n2), {down_btn if err > 0 else up_btn})
        err = L.ring_diff(pitch_now_fn(), target_ring)
    return {"err_deg": round(err / L.DEG, 3),
            "frames": abs(n) + abs(n2),
            "step_deg": round(step_raw / L.DEG, 2)}


# ---------------- shared probe factory (current-window parse) ----------------
def make_probe_fn(core, m, P, ev, wr, tracker=None,
                  hold_frames=8, mid_after=3, attack_btn="R2"):
    """probe(target_ring, pdeg_nominal, tag, want_probe_rec=False)
    -> {"parse", "rec"}.

    r11 probe: DEAD-RECKON absolute ring targeting (measure the LOOK
    step once, then land on the nearest reachable ring to the requested
    ray angle).  FIX-2 kept: base pre-R2, mid WHILE HOLDING (frame
    mid_after), mid2 end-of-hold (tick-growth telemetry), late 24 f
    after release.  Records the pad held-word parsed from the mid
    snapshot.  Optional RepeatLatchTracker observation per probe.
    """
    import psxmc_r10_oracle as O
    from psxmc_r7_lib import A_INPUT

    step, _ = measure_ring_step(core, lambda: O.pitch_now(m, P))
    ref = O.pitch_now(m, P)          # spawn-horizon ring reference
    ref_deg = (ref % L.PITCH_MOD) / L.DEG
    ev.j({"ev": "ring_cal", "step_deg": round(step / L.DEG, 3),
          "ref_deg": round(ref_deg, 2)})

    def probe(pdeg=0.0, tag="p", target_ring=None, want_probe_rec=False):
        if target_ring is None:
            target_ring, _ = nearest_reachable_ring(ref, pdeg, step)
        aim = aim_ring_dead_reckon(
            core, lambda: O.pitch_now(m, P), target_ring, step)
        aim_deg = round(((target_ring % L.PITCH_MOD) / L.DEG - ref_deg)
                        % 360.0, 2)
        if aim_deg > 180.0:
            aim_deg -= 360.0
        core.run(2, set())
        pos = O.pos_of(m, P)
        base = bytes(m.snapshot())
        pre = breaking_current(None, P, snap=base)
        core.run(2, {attack_btn})
        core.run(max(1, mid_after - 2), {attack_btn})
        mid = bytes(m.snapshot())                    # WHILE HOLDING
        core.run(max(1, hold_frames - mid_after), {attack_btn})
        mid2 = bytes(m.snapshot())                   # end of hold
        core.run(1, set())                           # release
        rel = bytes(m.snapshot())
        core.run(24, set())                          # remesh/reset settles
        late = bytes(m.snapshot())
        held = (~int.from_bytes(mid[A_INPUT + 2:A_INPUT + 4],
                                "little")) & 0xFFFF
        rec = {"tag": tag, "aim": aim, "pos": pos, "aim_deg": aim_deg,
               "pitch_deg": round(((O.pitch_now(m, P) % L.PITCH_MOD)
                                   / L.DEG - ref_deg) % 360.0, 2),
               "held_mid": hex(held),
               "base": base, "mid": mid, "mid2": mid2,
               "rel": rel, "late": late}
        parse = parse_probe_current(wr, rec, P)
        parse["held_mid"] = rec["held_mid"]
        parse["pre_live"] = pre["live"]
        if tracker is not None:
            parse["tracker"] = tracker.observe(parse)
        ev.j({"ev": f"probe_{tag}", "aim": aim, "aim_deg": aim_deg,
              "held": rec["held_mid"], "pos": parse["pos_blocks"],
              "live": parse["live"], "ok": parse["ok"],
              "hit": parse.get("hit"), "wid": parse.get("world_id")})
        return {"parse": parse, "rec": rec if want_probe_rec else None}

    return probe
