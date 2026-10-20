#!/usr/bin/env python3
"""issue4_progress_probe.py — ISSUE 4 Phase 2: player-progress variable,
real mission timer, and death event, via bounded event-driven RAM diff.

Previous attempts (route_timed_run find_progress_addr) rejected every
camera candidate because the monotonicity test treated the EXPECTED
wall plateau as a dip.  v2 protocol fixes that and adds:

  * two-origin validation — a candidate must pass the idle/RIGHT/LEFT
    3-way test from caus0 AND from caus0+30f (independent origin);
  * plateau-tolerant monotonicity — reversals <=2 and plateaus are
    allowed (walking into a wall stops the camera; that is physics,
    not a failed test);
  * timer discovery — bytes decrementing exactly 1 per 60-frame window
    during active play, value 30..250, for 10 windows, repeated on the
    second origin (the 0xD47D4 'sensor' is known NOT to be the timer:
    it freezes under input);
  * death event — from caus0, idle 480f (the opening kills idlers),
    snapshot every 40f; bytes that flip within one window of the score
    collapse are death-event candidates.

Output: evidence/issue4_progress/progress_report.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

import numpy as np

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (_REPO, os.path.join(_REPO, "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from ps1play import labconfig                             # noqa: E402
from ps1play.api import PS1Play                           # noqa: E402
from mission import ensure_mission                        # noqa: E402

SCORE_OFF = 0x0EE318
ZONE = 0x1FC000


def _log(*a):
    print("[progress]", *a, file=sys.stderr, flush=True)


def boot():
    ws = labconfig.resolve_path("workspace")
    fw = labconfig.resolve_firmware(
        os.environ.get("M1_FIRMWARE", "openbios"), ws)
    kw = {}
    core_path = labconfig.resolve_path("core")
    if core_path:
        kw["core"] = core_path
    if ws:
        kw["workspace"] = ws
    if fw["override_vars"]:
        kw["var_overrides"] = fw["override_vars"]
    p = PS1Play(labconfig.resolve_path("game"), **kw)
    p.boot()
    fw_ev = labconfig.firmware_log_evidence(
        getattr(p.core, "log_history", []))
    ok, detail = labconfig.check_firmware_trust(fw, fw_ev)
    if not ok:
        raise SystemExit(f"firmware trust failed: {detail}")
    nav = p.enter_gameplay3()
    if not nav.get("in_game"):
        raise SystemExit("enter_gameplay3 failed")
    gate = ensure_mission(p, log=_log, want_hp_cands=False)
    if not gate.get("in_mission"):
        raise SystemExit("gate failed")
    return p


def three_way(p, origin_frames):
    """idle/RIGHT/LEFT 120f from the given origin offset on caus0."""
    legs = {}
    for name, btns, frames in (("idle", set(), 240),
                               ("right", {"RIGHT"}, 240),
                               ("left", {"LEFT"}, 240)):
        p.load_state("caus0")
        p.core.run(origin_frames, set())
        s0 = p.mem.snapshot()[:ZONE]
        p.core.run(10, set())          # settle after origin shift
        sA = p.mem.snapshot()[:ZONE]
        p.core.run(frames, btns)
        p._advance()
        s1 = p.mem.snapshot()[:ZONE]
        legs[name] = (s0, sA, s1)
    idle = legs["idle"]
    cands = set()
    detail = {}
    for width in (1, 2, 4):
        view = {1: "<u1", 2: "<u2", 4: "<u4"}[width]
        dr = legs["right"][2].view(view).astype(np.int64) - \
            legs["right"][0].view(view).astype(np.int64)
        dl = legs["left"][2].view(view).astype(np.int64) - \
            legs["left"][0].view(view).astype(np.int64)
        di = idle[2].view(view).astype(np.int64) - \
            idle[0].view(view).astype(np.int64)
        diA = idle[1].view(view).astype(np.int64) - \
            idle[0].view(view).astype(np.int64)
        lo, hi = ((60, 4000) if width > 1 else (60, 255))
        cand = np.flatnonzero(
            (dr >= lo) & (dr <= hi) &
            (dl <= -lo) & (dl >= -hi) &
            (np.abs(di) <= 6) & (np.abs(diA) <= 2) &
            (np.abs(dr + dl) <= np.maximum(60, 0.15 * np.abs(dr))))
        addrs = sorted(int(c) * width for c in cand)
        detail[f"u{width * 8}"] = len(addrs)
        cands.update(addrs)
    _log(f"origin+{origin_frames}: candidates by view {detail}")
    return sorted(cands), legs


def plateau_test(p, addrs, frames=600, step=20):
    """RIGHT run; return per-addr series + plateau classification."""
    out = []
    p.load_state("caus0")
    series = {a: [] for a in addrs}
    for i in range(0, frames, step):
        p.core.run(step, {"RIGHT"})
        for a in addrs:
            series[a].append(int(p.mem.u32(a) if a % 4 == 0
                                 else p.mem.u16(a)))
    p._advance()
    for a in addrs:
        s = series[a]
        revs = sum(1 for k in range(1, len(s)) if s[k] < s[k - 1] - 2)
        big_revs = sum(1 for k in range(1, len(s)) if s[k] < s[k - 1] - 64)
        plateaus = sum(1 for k in range(1, len(s)) if s[k] == s[k - 1])
        out.append({"addr": hex(a), "series": s, "net_gain": s[-1] - s[0],
                    "small_revs": revs, "big_revs": big_revs,
                    "plateau_steps": plateaus,
                    "class": ("MONOTONE_WITH_PLATEAUS" if big_revs == 0 and
                              s[-1] > s[0] else "REJECTED")})
    return out


def camera_focus(p):
    """Focused validation of the 0xeb85a/0xeb862 scroll candidates.

    Series sampled every 40f for idle / RIGHT / LEFT / blocked-LEFT /
    RIGHT-with-jumps.  A camera/scroll variable must: freeze idle,
    advance at constant rate RIGHT, freeze at the left boundary (the
    mission cannot scroll left past its start), ignore jumps, and
    never reverse except under LEFT."""
    WATCH = [0xEB85A, 0xEB862, 0xEB858, 0xEB85C, 0xEB860, 0xEB864]
    legs = (("idle", set(), 240), ("right", {"RIGHT"}, 240),
            ("left", {"LEFT"}, 240), ("jump_mix", {"RIGHT"}, 240))
    out = {}
    for name, btns, frames in legs:
        p.load_state("caus0")
        series = {hex(a): [] for a in WATCH}
        for i in range(0, frames, 40):
            if name == "jump_mix" and i in (80, 160):
                p.core.run(10, {"B"})          # jump mid-run
            p.core.run(40, btns)
            for a in WATCH:
                series[hex(a)].append(int(p.mem.u16(a)))
        p._advance()
        out[name] = series
        _log(f"[cam] {name}: " + " ".join(
            f"{h}={v[:6]}" for h, v in series.items()))
    return out


def camera_verdict(cam):
    """Apply the camera rules to the two candidate addrs."""
    verdicts = {}
    for addr in ("0xeb85a", "0xeb862"):
        idle = cam["idle"][addr]
        right = cam["right"][addr]
        left = cam["left"][addr]
        mix = cam["jump_mix"][addr]
        idle_frozen = max(idle) - min(idle) <= 2
        right_rate = (right[-1] - right[0]) / max(1, len(right) - 1)
        right_monotone = all(b >= a for a, b in zip(right, right[1:]))
        left_monotone = all(b <= a for a, b in zip(left, left[1:]))
        left_frozen_or_back = (max(left) - min(left)) <= 8 or left_monotone
        mix_ok = (mix[-1] - mix[0]) >= (right[-1] - right[0]) * 0.8
        verdicts[addr] = {
            "idle_frozen": idle_frozen,
            "right_gain": right[-1] - right[0],
            "right_monotone": right_monotone,
            "left_gain": left[-1] - left[0],
            "left_monotone": left_monotone,
            "left_frozen_or_back": left_frozen_or_back,
            "jump_mix_gain": mix[-1] - mix[0],
            "jump_does_not_regress": mix_ok,
        }
        v = verdicts[addr]
        v["class"] = ("VERIFIED_CAMERA" if idle_frozen and right_monotone
                      and v["right_gain"] >= 60 and left_monotone and
                      mix_ok else "UNVERIFIED")
    return verdicts


def bcd16(v):
    lo, hi = v & 0xFF, (v >> 8) & 0xFF
    if (lo >> 4) > 9 or (lo & 0xF) > 9 or (hi >> 4) > 9 or (hi & 0xF) > 9:
        return None
    return hi * 100 + (lo >> 4) * 10 + (lo & 0xF)


def timer_scan(p, windows=10, step=60):
    """Timer candidates: u8 plain, u16 plain (carry-safe), u16 BCD.
    Two origins; bytes must decrement exactly one unit per window
    throughout, start value 30..250."""
    results = []
    for origin in (0, 24):
        p.load_state("caus0")
        p.core.run(60 + origin, {"RIGHT"})   # active play, alive
        snaps = []
        for _ in range(windows):
            p.core.run(step, {"RIGHT"})
            snaps.append(p.mem.snapshot())
        p._advance()
        Z = ZONE
        u8 = np.stack([s[:Z].astype(np.int16) for s in snaps])
        u16 = np.stack([s[:ZONE].view("<u2").astype(np.int32)
                        for s in snaps])
        cands = []
        # u8 plain (no borrow crossing this window set)
        dec = u8[:-1] - u8[1:]
        ok = np.all(dec == 1, axis=0) & (u8[0] >= 30) & (u8[0] <= 250)
        cands += [(int(i), "u8", int(u8[0][i])) for i in
                  np.flatnonzero(ok)]
        # u16 plain
        dec16 = u16[:-1] - u16[1:]
        ok16 = np.all(dec16 == 1, axis=0) & (u16[0] >= 30) & (u16[0] <= 250)
        cands += [(int(i) * 2, "u16", int(u16[0][i])) for i in
                  np.flatnonzero(ok16)]
        # u16 BCD
        bd = [(k, bcd16(int(v))) for k, v in enumerate(u16[0])]
        bd = [(k, d) for k, d in bd if d is not None and 30 <= d <= 250]
        for k, d0 in bd[:20000]:
            seq_ok = True
            prev = d0
            for s in snaps[1:]:
                v = int(s[k * 2] | (s[k * 2 + 1] << 8))
                d = bcd16(v)
                if d is None or prev - d != 1:
                    seq_ok = False
                    break
                prev = d
            if seq_ok:
                cands.append((k * 2, "u16bcd", d0))
        # 3-byte BCD (MSX HUD timers are often 3 BCD digits: 200 ->
        # bytes 00 02): value = b2*10000 + b1*100 + lo-nibbles of b0.
        # Fully vectorized: (windows, ZONE) u8 matrices.
        m = np.stack([np.frombuffer(s[:ZONE], dtype=np.uint8)
                      for s in snaps]).astype(np.int32)
        b0, b1, b2 = m[:, :-2], m[:, 1:-1], m[:, 2:]
        nib_ok = np.all(((b0 >> 4) <= 9) & ((b0 & 15) <= 9) &
                        ((b1 >> 4) <= 9) & ((b1 & 15) <= 9) &
                        ((b2 >> 4) <= 9) & ((b2 & 15) <= 9), axis=0)
        val = b2 * 10000 + b1 * 100 + (b0 >> 4) * 10 + (b0 & 15)
        dec = val[:-1] - val[1:]
        seq_ok = np.all(dec == 1, axis=0)
        rng = (val[0] >= 30) & (val[0] <= 300)
        for i in np.flatnonzero(nib_ok & seq_ok & rng):
            cands.append((int(i), "bcd24", int(val[0][i])))
        results.append({"origin": origin, "strict": [
            {"addr": hex(a), "kind": k, "start": v}
            for a, k, v in cands[:64]], "n": len(cands)})
        _log(f"timer origin+{origin}: strict candidates = {len(cands)} "
             f"{[(hex(a), k, v) for a, k, v in cands[:8]]}")
    return results


def death_event(p, windows=30, step=40):
    """Walk DEEPER into the level, then idle until death; capture flips
    around the score collapse."""
    p.load_state("caus0")
    p.core.run(400, {"RIGHT"})          # into the next enemy group
    p.core.run(10, set())
    snaps = [p.mem.snapshot()]
    scores = [int(p.mem.u32(SCORE_OFF))]
    for _ in range(windows):
        p.core.run(step, set())
        snaps.append(p.mem.snapshot())
        scores.append(int(p.mem.u32(SCORE_OFF)))
    p._advance()
    death_idx = next((k for k in range(1, len(scores))
                      if scores[k - 1] >= 200 and scores[k] < 100), None)
    if death_idx is None:
        _log(f"death event not observed; scores={scores}")
        return {"observed": False, "scores": scores}
    before = np.stack([s[:ZONE].astype(np.int16) for s in
                       snaps[death_idx - 1:death_idx + 1]])
    d = before[1] - before[0]
    flipped = np.flatnonzero(d != 0)
    _log(f"death at window {death_idx}: scores={scores} "
         f"flipped={flipped.size}")
    after = np.stack([s[:ZONE].astype(np.int16) for s in
                      snaps[death_idx:death_idx + 2]])
    d2 = after[1] - after[0]
    persist = np.flatnonzero((d != 0) & (d2 == 0))
    return {"observed": True, "death_window": death_idx,
            "scores": scores,
            "flip_count": int(flipped.size),
            "flip_then_stable_addrs":
                [hex(int(x)) for x in persist[:48]],
            "flip_then_stable_count": int(persist.size)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--evidence-dir",
                    default=labconfig.resolve_path("evidence_dir"))
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    outdir = os.path.join(args.evidence_dir, "issue4_progress")
    os.makedirs(outdir, exist_ok=True)
    out = {"schema": "ps1play-progress-probe/2",
           "generated_utc": time.strftime("%FT%TZ", time.gmtime())}

    p = boot()
    # build caus0 in a CLEAN corridor: walk right, kill the opening
    # soldier (FIRE 244 pts, v5-verified), settle — no enemy interference
    # during the movement legs; score>200 also enables death detection.
    p.core.run(90, {"RIGHT"})
    p.core.run(45, {"Y"})
    p.core.run(15, set())
    p._advance()
    p.save_state("caus0")
    _log(f"caus0 score={int(p.mem.u32(SCORE_OFF))} "
         f"grenades={int(p.mem.u8(0xEDCF4))}")

    c0, _ = three_way(p, 0)
    c1, _ = three_way(p, 30)
    common = sorted(set(c0) & set(c1))
    out["candidates_origin0"] = len(c0)
    out["candidates_origin30"] = len(c1)
    out["candidates_common"] = [hex(a) for a in common[:64]]
    _log(f"common across origins: {len(common)}")
    if common:
        out["plateau"] = plateau_test(p, common[:12])
    out["camera_focus"] = camera_focus(p)
    out["camera_verdicts"] = camera_verdict(out["camera_focus"])
    _log(f"camera verdicts: " + " ".join(
        f"{a}={v['class']}" for a, v in out["camera_verdicts"].items()))
    out["timer_scan"] = timer_scan(p)
    out["death_event"] = death_event(p)

    outpath = args.out or os.path.join(outdir, "progress_report.json")
    with open(outpath, "w") as f:
        json.dump(out, f, indent=1)
    _log("report:", outpath)
    return 0


if __name__ == "__main__":
    sys.exit(main())
