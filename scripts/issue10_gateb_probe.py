#!/usr/bin/env python3
"""issue10_gateb_probe.py - ISSUE 10 Gate B runtime validation (READ-ONLY).

Static hypothesis (from Ghidra corpus, exe_decompiled.json):
  FUN_80021898 (VA 0x80021898) is the camera/scroll updater:
    - copies param_2 into scroll state words 0x800EB598 (x) / 0x800EB59C (y),
      applies a follow-offset from a pointer table (ptr+0x14/+0x18),
      stores results into 0x800EB590/0x800EB594;
    - then calls FUN_8001e340; on its failure branch the function RESTORES
      the previous scroll values from 0x800EB598 (rollback), gated by a
      mode check `uVar6>>16 == 9`.

Runtime predictions to validate on the real disc (issue5_m1_start anchor):
  P1  scroll word 0x0EB598 advances while the player walks RIGHT.
  P2  at the known D7 clamp the scroll word freezes (or rolls back)
      while gameplay remains active (flags u32@0x0EE518 == 0xFF).
  P3  flags word stays 0xFF during gameplay, flips on menu/death.

Everything here is observe-only: reads + ordinary RIGHT input.
Output: work/msx_recomp/evidence/issue10_gateB/gateb_report.json
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

# physical offsets = VA - 0x80000000
SCROLL_X_SAVED = 0x0EB598   # FUN_80021898: *param_2 backup / restore source
SCROLL_Y_SAVED = 0x0EB59C
SCROLL_X_OUT = 0x0EB590     # updated camera position
SCROLL_Y_OUT = 0x0EB594
CAM_FOLLOW_PTR = 0x0EB5A0
FLAGS_WORD = 0x0EE518       # u32: 0xFF play, 0x1 menu/gameover (CONFIRMED #5)
SCORE = 0x0EE318
PROGRESS_X = 0x0EB85A       # forward candidate found in issue4 scroll_dump
ENTITY_TABLE = 0x0CA268     # stride 0x14C, HP +0x8E (CONFIRMED #3/#5)
STRIDE = 0x14C
HP_OFF = 0x8E

EVID = "/home/z/my-project/work/msx_recomp/evidence/issue10_gateB"


def _log(*a):
    print("[gateb]", *a, file=sys.stderr, flush=True)


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


def sample(p):
    m = p.mem
    row = {
        "scroll_x_saved": m.u32(SCROLL_X_SAVED),
        "scroll_y_saved": m.u32(SCROLL_Y_SAVED),
        "scroll_x_out": m.u32(SCROLL_X_OUT),
        "scroll_y_out": m.u32(SCROLL_Y_OUT),
        "cam_follow_ptr": m.u32(CAM_FOLLOW_PTR),
        "flags": m.u32(FLAGS_WORD),
        "score": m.u32(SCORE),
        "progress_x": m.u16(PROGRESS_X),
        "hp": [m.u16(ENTITY_TABLE + i * STRIDE + HP_OFF) for i in range(4)],
    }
    return row


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--steps", type=int, default=80)
    ap.add_argument("--step-frames", type=int, default=20)
    ap.add_argument("--fine-frames", type=int, default=60)
    args = ap.parse_args()

    t0 = time.time()
    p = boot()
    p.load_state("issue5_m1_start")
    p.core.run(60, set())            # settle at anchor
    p._advance()

    series = []
    frozen_streak = 0
    first_clamp_step = None
    rollback_events = []

    prev = sample(p)
    series.append({"step": 0, "frame": 0, **prev})

    for step in range(1, args.steps + 1):
        p.core.run(args.step_frames, {"RIGHT"})
        p._advance()
        row = sample(p)
        row["step"] = step
        row["frame"] = step * args.step_frames
        d = row["scroll_x_out"] - prev["scroll_x_out"]
        row["scroll_x_delta"] = d
        series.append(row)
        if row["flags"] != 0xFF:
            _log(f"step {step}: flags=0x{row['flags']:X} (left gameplay) - stop")
            break
        if d < 0:
            rollback_events.append(
                {"step": step, "from": prev["scroll_x_out"],
                 "to": row["scroll_x_out"]})
        if d == 0 and row["progress_x"] != prev["progress_x"]:
            frozen_streak += 1
            if frozen_streak >= 5 and first_clamp_step is None:
                first_clamp_step = step - 4
                _log(f"CLAMP signature: scroll frozen while progress moves "
                     f"at step {step} (scroll_x={row['scroll_x_out']})")
        else:
            frozen_streak = 0
        prev = row

    # fine-grained 1-frame window to catch write->rollback pairs
    fine = []
    if first_clamp_step is not None:
        fine_frames = args.fine_frames
    else:
        fine_frames = min(args.fine_frames, 40)
    for i in range(fine_frames):
        p.core.run(1, {"RIGHT"})
        p._advance()
        fine.append({"i": i, **sample(p)})

    ok, _ = labconfig.validate_cue(labconfig.resolve_path("game"))
    rep = {
        "schema": "ps1play-issue10-gateb/1",
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "wall_s": round(time.time() - t0, 1),
        "anchor": "issue5_m1_start",
        "inputs": "RIGHT held during stepped run (ordinary gameplay input)",
        "write_mode": "NONE (observe-only)",
        "cue_valid": ok,
        "predictions": {
            "P1_scroll_advances_while_RIGHT": None,
            "P2_scroll_freezes_or_rolls_back_at_clamp": None,
            "P3_flags_0xFF_during_play": None,
        },
        "first_clamp_step": first_clamp_step,
        "rollback_events": rollback_events,
        "series": series,
        "fine_window": fine,
    }

    # classify predictions from the data
    moved = [r for r in series if r.get("scroll_x_delta", 0)]
    pos = [r for r in moved if r["scroll_x_delta"] > 0]
    rep["predictions"]["P1_scroll_advances_while_RIGHT"] = bool(pos)
    rep["predictions"]["P2_scroll_freezes_or_rolls_back_at_clamp"] = bool(
        first_clamp_step is not None or rollback_events)
    flags_ff = [r for r in series if r["flags"] == 0xFF]
    rep["predictions"]["P3_flags_0xFF_during_play"] = (
        len(flags_ff) >= max(1, len(series) - 1))

    os.makedirs(EVID, exist_ok=True)
    out = os.path.join(EVID, "gateb_report.json")
    with open(out, "w") as fh:
        json.dump(rep, fh, indent=1)
    _log("report ->", out)
    print(json.dumps({k: rep[k] for k in
                      ("predictions", "first_clamp_step",
                       "rollback_events", "wall_s")}, indent=1))


if __name__ == "__main__":
    main()
