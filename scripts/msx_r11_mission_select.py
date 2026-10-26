#!/usr/bin/env python3
"""msx_r11_mission_select.py — Round 11 / Segment 3 (MSX mission index).

Three arms, EACH in its OWN process (one beetle boot per process):

  attract   boot_to_demo (no start taps) -> attract/demo world; idle
            ~3,000 f sampling full RAM every 60 f; records which u16
            words are STABLE across the whole window (npz + summary).
  gameplay  issue4 boot() -> ensure_mission -> stable M1 gameplay;
            sample 3,000 f the same way.
  diff      OFFLINE (no emulator): intersect stable words, keep the
            ones that DIFFER attract vs M1; cross-check the known
            globals (FLAGS_WORD, world-alive latch, SECTION_*); write
            candidates.json.
  m3probe   boot() -> M1 gameplay -> ONE DISCLOSED WRITE PROBE per
            candidate value: hold the mission word at 2 then 3
            (u8/u16/u32 as instructed) via GS constant codes for 600 f
            with PNGs, then DISABLE (the engine restores the original
            bytes captured at enable) and VERIFY the restore.  A
            no-write control window runs first for the churn baseline.

All writes are CHEAT_ASSISTED_EXPLORATION (opt_in=True, logged).  No
savestate tricks.  Verdict (m3probe): M3_SELECT_CAUSAL (persistent
world/scene state change absent from the control window) / NEGATIVE /
INCONCLUSIVE.  Evidence: scratch/round11_msx/mission_select/.
"""
from __future__ import annotations

import argparse
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

from ps1play.telemetry import JsonlTrace                # noqa: E402
from ps1play.agent.cheatprof import (                   # noqa: E402
    CheatSession, CHEAT_ASSISTED)
from ps1play.agent.gameshark import GSCode              # noqa: E402
from issue4_controller import boot                      # noqa: E402
from issue4_real_start import boot_to_demo              # noqa: E402
from mission import ensure_mission                      # noqa: E402
from e2e_policy_trial import snap                       # noqa: E402

SCRATCH = "/home/z/my-project/ps1ai/scratch/round11_msx/mission_select"
PLAYER_X = 0x0CA2E0
A_SCORE = 0x0EE318
FLAGS_WORD = 0x0EE518
LATCH = 0x0EB5FC
KNOWN = {"FLAGS_WORD": FLAGS_WORD, "world_alive_latch": LATCH,
         "SECTION_STATE": 0x0EB5F4, "SECTION_FLAGS": 0x0EB5D0,
         "SECTION_PROGRESS": 0x0EB5D4, "A_SCORE": A_SCORE,
         "PLAYER_X": PLAYER_X}


def log(*a):
    print("[r11-mselect]", *a, file=sys.stderr, flush=True)


def px_of(m):
    v = int(m.u32(PLAYER_X))
    if v >= 0x80000000:
        v -= 0x100000000
    return v / 65536.0


def sample_loop(p, m, J, frames, sample=60):
    """Idle sampling; returns (stable16_vals, stable16_mask, rows)."""
    n_u16 = 0x200000 // 2
    first = None
    stable = None
    rows = []
    f0 = p.core.frames_run
    while p.core.frames_run - f0 < frames:
        p.core.run(sample, set())
        f = p.core.frames_run
        cur = m.ram[:n_u16 * 2].copy()
        if first is None:
            first = cur
            stable = np.ones(n_u16 * 2, dtype=bool)
        else:
            stable &= (cur == first)
        s = snap(m)
        s["frame"] = f
        rows.append(s)
        J({"ev": "sample", "frame": f, **s})
    first16 = first.view("<u2").astype(np.uint32)
    stable16 = stable.view(np.bool_)
    # a u16 word is stable iff BOTH its bytes never changed
    stable_w = stable16[0::2] & stable16[1::2]
    return first16, stable_w, rows


def save_npz(tag, first16, stable_w, rows):
    idx = np.flatnonzero(stable_w)
    np.savez_compressed(
        os.path.join(SCRATCH, f"{tag}_stable.npz"),
        offsets=idx.astype(np.int64),
        values=first16[idx].astype(np.uint32),
        rows=json.dumps(rows, default=str))
    return len(idx)


def arm_attract(args, J):
    p = boot_to_demo()
    m = p.mem
    J({"ev": "boot", "mode": "attract"})
    # let the boot logo / title settle into the attract world
    p.core.run(600, set())
    first16, stable_w, rows = sample_loop(p, m, J, args.frames)
    n = save_npz("attract", first16, stable_w, rows)
    J({"ev": "attract_done", "stable_u16": n})
    log("attract stable u16 words:", n)
    return 0


def arm_gameplay(args, J):
    p, fw = boot()
    m = p.mem
    J({"ev": "boot", "mode": "gameplay", "fw": fw})
    first16, stable_w, rows = sample_loop(p, m, J, args.frames)
    n = save_npz("gameplay", first16, stable_w, rows)
    J({"ev": "gameplay_done", "stable_u16": n})
    log("gameplay stable u16 words:", n)
    return 0


def arm_diff(args, J):
    a = np.load(os.path.join(SCRATCH, "attract_stable.npz"))
    g = np.load(os.path.join(SCRATCH, "gameplay_stable.npz"))
    A = dict(zip(a["offsets"].tolist(), a["values"].tolist()))
    G = dict(zip(g["offsets"].tolist(), g["values"].tolist()))
    common = sorted(set(A) & set(G))
    cands = [{"addr": int(o), "addr_hex": f"0x0{o:06X}",
              "attract": A[o], "gameplay": G[o]}
             for o in common if A[o] != G[o]]
    for c in cands:
        c["known"] = next((k for k, v in KNOWN.items()
                           if v == c["addr"]), None)
    # restrict to the globals band for the mission-word shortlist
    band = [c for c in cands if 0x0E0000 <= c["addr"] < 0x100000]
    J({"ev": "diff_done", "candidates": len(cands), "band": len(band)})
    json.dump({"schema": "ps1play-r11-mission-candidates/1",
               "n_candidates": len(cands), "n_band": len(band),
               "band": band, "all": cands[:4000]},
              open(os.path.join(SCRATCH, "candidates.json"), "w"),
              indent=1)
    log("diff: candidates", len(cands), "in 0x0E-0x0F band:", len(band))
    for c in band[:60]:
        log("  ", c["addr_hex"], "attract", c["attract"], "m1",
            c["gameplay"], c["known"] or "")
    return 0


def gs_codes(addr, value, enc):
    """Constant-write GS codes for one value at a physical RAM addr."""
    if enc == "u8":
        return [GSCode(f"30{addr & 0xFFFFFF:06X} {value & 0xFF:02X}")]
    if enc == "u16":
        return [GSCode(f"8{addr & 0x7FFFFFF:07X} {value & 0xFFFF:04X}")]
    if enc == "u32":
        return [GSCode(f"8{addr & 0x7FFFFFF:07X} {value & 0xFFFF:04X}"),
                GSCode(f"8{(addr + 2) & 0x7FFFFFF:07X} "
                       f"{(value >> 16) & 0xFFFF:04X}")]
    raise ValueError(enc)


def read_word(m, addr, enc):
    if enc == "u8":
        return int(m.u8(addr))
    if enc == "u16":
        return int(m.u16(addr))
    return int(m.u32(addr))


def arm_m3probe(args, J):
    p, fw = boot()
    m = p.mem
    J({"ev": "boot", "mode": "m3probe", "fw": fw})
    addr = int(args.addr, 0)
    enc = args.enc
    orig = read_word(m, addr, enc)
    J({"ev": "probe_target", "addr": hex(addr), "enc": enc,
       "orig": orig, "values": args.values})
    # ---- no-write control window ----
    ctrl0 = snap(m)
    pngs = []
    f0 = p.core.frames_run
    for i in range(10):
        p.core.run(60, set())
        s = snap(m)
        s["frame"] = p.core.frames_run
        J({"ev": "control", **s})
        if i % 2 == 0:
            rgb = p.core.frame_rgb()
            if rgb is not None:
                n = f"m3_control_{i:02d}.png"
                Image.fromarray(rgb).save(os.path.join(SCRATCH, n))
                pngs.append(n)
    ctrl1 = snap(m)
    J({"ev": "control_summary", "px0": ctrl0["px"], "px1": ctrl1["px"],
       "score0": ctrl0["score"], "score1": ctrl1["score"]})

    results = []
    session = CheatSession(p, CHEAT_ASSISTED, opt_in=True)
    try:
        for vs in args.values.split(","):
            v = int(vs, 0)
            name = f"m3_write_{enc}_{v}"
            codes = gs_codes(addr, v, enc)
            pre = read_word(m, addr, enc)
            pre_snap = snap(m)
            session.enable(name, codes)
            J({"ev": "WRITE_ARMED", "disclosed": True,
               "mode": "CHEAT_ASSISTED_EXPLORATION",
               "codes": [c.raw for c in codes], "pre": pre})
            for i in range(10):
                session.run_frames(60, set())
                s = snap(m)
                s["frame"] = p.core.frames_run
                s["word"] = read_word(m, addr, enc)
                J({"ev": "write_window", "value": v, **s})
                if i % 2 == 0:
                    rgb = p.core.frame_rgb()
                    if rgb is not None:
                        n = f"m3_write{v}_{i:02d}.png"
                        Image.fromarray(rgb).save(os.path.join(
                            SCRATCH, n))
                        pngs.append(n)
            post = read_word(m, addr, enc)
            post_snap = snap(m)
            session.disable(name)
            after = read_word(m, addr, enc)
            restore_ok = after == pre
            J({"ev": "WRITE_RESTORED", "disclosed": True,
               "value": v, "post": post, "after_disable": after,
               "restore_ok": restore_ok})
            results.append({
                "value": v, "codes": [c.raw for c in codes],
                "pre": pre, "post_held": post,
                "held": post == v,
                "restore_ok": restore_ok,
                "pre_snap": pre_snap, "post_snap": post_snap})
            p.core.run(120, set())
    finally:
        session.disable_all()
        fin = read_word(m, addr, enc)
        J({"ev": "session_end", "word_final": fin,
           "orig": orig, "restored_to_orig": fin == orig})
    # ---- verdict ----
    flags_left = [r["post_snap"]["flags"] for r in results]
    scene_change = any(
        (r["post_snap"]["flags"] != 0xFF
         or r["post_snap"]["px"] != r["pre_snap"]["px"]
         and abs(r["post_snap"]["px"]) < 100.0)
        for r in results if r["held"])
    all_restored = all(r["restore_ok"] for r in results)
    held_any = any(r["held"] for r in results)
    if held_any and scene_change:
        verdict = "M3_SELECT_CAUSAL"
    elif held_any and all_restored and not scene_change:
        verdict = "NEGATIVE"
    else:
        verdict = "INCONCLUSIVE"
    rep = {"schema": "ps1play-r11-m3probe/1", "verdict": verdict,
           "addr": hex(addr), "enc": enc, "orig": orig,
           "results": results, "control": {"px0": ctrl0["px"],
                                           "px1": ctrl1["px"]},
           "pngs": pngs,
           "disclosed": {"writes": "GS constant holds ("
                         "CHEAT_ASSISTED_EXPLORATION), engine restores "
                         "orig bytes on disable; verified per arm"},
           "frames": p.core.frames_run,
           "wall_s": round(time.time() - t0, 1)}
    json.dump(rep, open(os.path.join(SCRATCH, "m3probe_report.json"),
                        "w"), indent=1)
    J({"ev": "run_end", "verdict": verdict})
    log("done:", verdict)
    return 0


def main():
    global t0
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", required=True,
                    choices=("attract", "gameplay", "diff", "m3probe"))
    ap.add_argument("--frames", type=int, default=3000)
    ap.add_argument("--addr", default="0x0EB5F4")
    ap.add_argument("--enc", default="u16", choices=("u8", "u16", "u32"))
    ap.add_argument("--values", default="2,3")
    args = ap.parse_args()
    os.makedirs(SCRATCH, exist_ok=True)
    t0 = time.time()
    trace = JsonlTrace(os.path.join(SCRATCH, f"trace_{args.arm}.jsonl"))

    def J(ev):
        ev["t"] = round(time.time() - t0, 1)
        trace.write(ev)

    return {"attract": arm_attract, "gameplay": arm_gameplay,
            "diff": arm_diff, "m3probe": arm_m3probe}[args.arm](args, J)


if __name__ == "__main__":
    sys.exit(main())
