#!/usr/bin/env python3
"""issue5_invuln.py — find the REAL invincibility mechanism (Issue #5).

Evidence so far (issue5_recon_recon1): the freeze-verified "hp" word
0xCA2FE is NOT the player's lethal-damage gate — the player died 4x in
one cheat-assisted run with it frozen (Metal Slug is a one-hit-death
game; the prior hp_freeze VERIFIED status is SUPERSEDED here).

Primary target: the post-respawn INVULNERABILITY (blink) timer that
counts down right after Marco reappears. Freezing it positive should
make the player unhittable — the game's own invulnerability mechanism,
just held open.

Protocol (one variable per experiment, smallest state diff):
  1. boot, arm only the strictly-verified bombs freeze.
  2. drive right until game-over (flags_word leaves 0xFF).
  3. accept the continue with FAST polling; the moment flags returns
     to 0xFF, sample RAM every 5 frames x 24 (the blink window).
  4. candidates = words non-increasing to 0, starting 8..600,
     reproduced in BOTH cycles.
  5. freeze-test each candidate from the cycle-0 spawn savestate:
     walk into live enemies; VERIFIED iff no death for 900 frames
     while the same walk without the freeze dies (baseline).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

import numpy as np
from PIL import Image                                     # noqa: E402

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (_REPO, os.path.join(_REPO, "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from ps1play import labconfig                             # noqa: E402
from ps1play.telemetry import TelemetryAdapter, JsonlTrace  # noqa: E402
from ps1play.agent.cheatprof import (                      # noqa: E402
    CheatSession, CHEAT_ASSISTED, derive_freeze_code)
from ps1play.agent.perception import PerceptionGuard        # noqa: E402
from ps1play.agent.route import RoutePolicy, StallDetector   # noqa: E402
from mission import ensure_mission, responsive               # noqa: E402
from issue4_controller import boot                           # noqa: E402
from issue5_controller import ContinueLedger                 # noqa: E402


def _log(*a):
    print("[invuln]", *a, file=sys.stderr, flush=True)


def png(p, evid, name):
    rgb = p.core.frame_rgb()
    if rgb is not None:
        Image.fromarray(rgb).save(os.path.join(evid, name))


def in_play(p, tel):
    cur = tel.snapshot(buttons=[], frame=p.core.frames_run)
    return cur["flags_word"] == 0xFF, cur


def find_countdowns(snaps):
    """u16/u8 words: start 8..600, non-increasing to 0 by the end,
    with >=3 strict drops and not 0 in the first two samples."""
    a = [s[:0x1FC000] for s in snaps]
    out = []
    for width in (2, 1):
        if width == 2:
            views = [x.view("<u2").astype(np.int32) for x in a]
            lo, hi = 8, 600
        else:
            views = [x.astype(np.int32) for x in a]
            lo, hi = 4, 255
        v0 = views[0]
        start_ok = (v0 >= lo) & (v0 <= hi)
        noninc = np.ones(v0.shape, bool)
        strict = np.zeros(v0.shape, np.int32)
        for i in range(1, len(views)):
            noninc &= views[i] <= views[i - 1]
            strict += (views[i] < views[i - 1]).astype(np.int32)
        end_zero = views[-1] == 0
        early_pos = np.minimum(views[0], views[1]) > 0
        cand = np.flatnonzero(start_ok & noninc & end_zero &
                              early_pos & (strict >= 3))
        for idx in cand.tolist()[:40]:
            out.append({"addr": int(idx) * width, "width": width,
                        "series": [int(v[idx]) for v in views]})
    return out


def drive_to_gameover(p, tel, policy, det, session, evid, trace,
                      max_chunks=60):
    """Drive right; return the chunk where the GAME OVER state (flags
    == 1) has settled. flags 255->0 is a <60-frame loading transition,
    NOT the death screen (recon1 trace evidence) — wait through it."""
    prev = tel.snapshot(buttons=[], frame=p.core.frames_run)
    out_run = 0
    for c in range(max_chunks):
        segs = policy.decide(60, det)
        for s in segs:
            session.run_frames(s["frames"], set(s["btns"] or set()))
        cur = tel.snapshot(buttons=[], frame=p.core.frames_run)
        evs = tel.events(prev, cur)
        trace.write({"type": "chunk", "chunk": c, "flags":
                     cur["flags_word"], "score": cur["score"],
                     "grenades": cur["grenades"],
                     "deaths_sig": [e["type"] for e in evs
                                    if "death" in e["type"]]})
        prev = cur
        det.update(None, 1000, max(0, cur["score"]))
        if cur["flags_word"] == 0x1:
            out_run += 60
            if out_run >= 120:               # settled on GAME OVER
                png(p, evid, f"gameover_c{c:03d}.png")
                return c
        else:
            out_run = 0
            if cur["flags_word"] != 0xFF:
                out_run = -1                 # loading: hold inputs off
                session.run_frames(60, set())
    return None


def accept_and_sample(p, tel, evid, trace, chunk, max_rounds=14):
    """Accept the continue with the PROVEN cadence (issue5_controller:
    130f settle, 8f tap, ~100f settle) but with 10-frame polling inside
    the settle so the blink window is sampled the instant play resumes."""
    for i in range(max_rounds):
        p.core.run(130, set())
        for btn in ({"START"}, {"Y"}):
            p.core.run(8, btn)
            resumed = False
            for k in range(10):            # poll up to 100 frames
                p.core.run(10, set())
                ok, _cur = in_play(p, tel)
                if ok:
                    resumed = True
                    break
            if resumed:
                png(p, evid, f"respawn_c{chunk:03d}_r{i:02d}.png")
                snaps = [p.mem.snapshot()]
                for j in range(23):
                    p.core.run(5, set())
                    snaps.append(p.mem.snapshot())
                cands = find_countdowns(snaps)
                png(p, evid, f"postblink_c{chunk:03d}_r{i:02d}.png")
                trace.write({"type": "respawn", "chunk": chunk,
                             "round": i, "btn": sorted(btn)[0],
                             "cands": cands[:24]})
                return True, cands
    return False, []


def freeze_test(p, session, addr, width, base_state, evid,
                frames=900):
    """Walk into live enemies from base_state with the freeze ON."""
    p.load_state(base_state)
    dtype = "u8" if width == 1 else "u16"
    code, val = derive_freeze_code(p, addr, dtype=dtype)
    session.enable("_blink", [code])
    tel = TelemetryAdapter(p)
    policy = RoutePolicy(allow_grenades=False, jump_enabled=False)
    det = StallDetector()
    died = False
    for _ in range(frames // 60):
        segs = policy.decide(60, det)
        for s in segs:
            session.run_frames(s["frames"], set(s["btns"] or set()))
        ok, _cur = in_play(p, tel)
        if not ok:
            died = True
            break
    session.disable("_blink")
    ok_final, _ = in_play(p, tel)
    p.load_state(base_state)
    return {"addr": hex(addr), "width": width, "frozen_val": val,
            "code": code.raw,
            "died": bool(died),
            "verdict": ("INVULN_VERIFIED" if not died and ok_final
                        else "REJECTED")}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default="inv1")
    ap.add_argument("--cycles", type=int, default=2)
    ap.add_argument("--evidence-dir",
                    default=labconfig.resolve_path("evidence_dir"))
    args = ap.parse_args()
    outdir = os.path.join(args.evidence_dir, f"issue5_invuln_{args.tag}")
    os.makedirs(outdir, exist_ok=True)
    trace = JsonlTrace(os.path.join(outdir, "trace.jsonl"))
    t0 = time.time()

    _log("=== boot ===")
    p, fwmode = boot()
    session = CheatSession(p, CHEAT_ASSISTED, opt_in=True)
    tel = TelemetryAdapter(p)

    guard = PerceptionGuard(p)
    anch = guard.anchor(log=_log)
    if anch.get("ok"):
        code, _v = derive_freeze_code(p, int(guard.addrs["bombs"]),
                                      dtype=guard.dtypes.get("bombs", "u8"))
        session.enable("bombs_freeze", [code])
        trace.write({"type": "bombs_armed", "addr":
                     hex(int(guard.addrs["bombs"]))})

    policy = RoutePolicy(allow_grenades=True, jump_enabled=True)
    det = StallDetector()
    led = ContinueLedger()
    pool = {}
    cycles = []
    for d in range(args.cycles):
        _log(f"--- cycle {d + 1}: drive to game-over ---")
        c = drive_to_gameover(p, tel, policy, det, session, outdir, trace)
        if c is None:
            _log("no game-over within budget; cycle ends")
            break
        led.on_continue_restart()
        resumed, cands = accept_and_sample(p, tel, outdir, trace, c)
        if not resumed:
            _log("continue accept failed; stopping")
            break
        g = ensure_mission(p, tries=3, log=_log, want_hp_cands=False)
        p.save_state("spawn_c0" if d == 0 else f"spawn_c{d}")
        _log(f"cycle {d + 1}: {len(cands)} countdown candidates")
        for cd in cands:
            key = (cd["addr"], cd["width"])
            pool[key] = pool.get(key, 0) + 1
        cycles.append({"cycle": d, "death_chunk": c, "resumed": resumed,
                       "candidates": len(cands),
                       "top": cands[:10]})

    tested = []
    ranked = sorted(pool.items(), key=lambda kv: -kv[1])
    _log("reproducible blink candidates:", [(hex(a), w, n)
                                            for (a, w), n in ranked[:8]])
    for (addr, width), n in ranked[:6]:
        if n < args.cycles:              # must reproduce in every cycle
            continue
        r = freeze_test(p, session, addr, width, "spawn_c0", outdir)
        r["reproduced"] = n
        tested.append(r)
        trace.write({"type": "blink_freeze_test", **r})
        _log("blink freeze test:", r)
        if r["verdict"] == "INVULN_VERIFIED":
            break

    results = {"cycles": cycles, "blink_tests": tested,
               "pool_top": [[hex(a), w, n] for (a, w), n in ranked[:16]],
               "boot": {"firmware": fwmode},
               "wall_s": round(time.time() - t0, 1)}
    with open(os.path.join(outdir, "invuln_report.json"), "w") as f:
        json.dump(results, f, indent=1, default=str)
    _log("report:", os.path.join(outdir, "invuln_report.json"))
    trace.close()
    del p
    return 0


if __name__ == "__main__":
    sys.exit(main())
