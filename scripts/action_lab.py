#!/usr/bin/env python3
"""action_lab.py — Phase D: verify every action the active policy uses.

Controlled A/B experiments from the REAL game's Mission-1 start
savestate (calibration tier — savestate branches, NOT live-run
evidence). For each action the lab measures the FULL chain
`set_buttons() -> libretro input_state -> core pad mapping -> game pad
mirror (0x0D4948) -> independent in-game outcome`:

  FIRE    (Y / PSX SQUARE)  — world frame difference + RAM churn vs
                              control (muzzle flash / projectile); the
                              live-run score events (kills) are the
                              independent cross-check
  JUMP    (B / PSX CROSS)   — visible jump: frame difference vs
                              control + screenshots
  GRENADE (A / PSX CIRCLE)  — bombs counter anchored
                              FRESH IN THIS BOOT (PerceptionGuard: A
                              press => exactly -1, idle-stable) then
                              each treatment rep consumes exactly 1
  NEGCTRL (X / PSX TRIANGLE)— reaches the game but NO world-visible
                              effect (maps, does nothing here)
  CONTROL (idle)            — baseline churn + frame

v0.12 lesson encoded here:
  * profile-derived per-boot RAM addresses are NOT valid across boots
    (player_x 0xE8084 read a frozen 255 in a new boot) — every per-boot
    sensor is re-anchored in THIS boot or dropped.
  * the pad-mirror word 0x0D4948 reflects DIRECTIONAL input only
    (RIGHT held => bit 0x20; Y/B/A never appear there). Action buttons
    are therefore verified through in-game OUTCOMES, not this word.

Each action: 3 repetitions from byte-identical initial conditions.
Outputs JSON + PNGs under <evidence-dir>/action_lab/.
"""
import argparse
import json
import os
import sys

import numpy as np

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (_REPO, os.path.join(_REPO, "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from ps1play import labconfig                                  # noqa: E402
from ps1play.api import PS1Play                                # noqa: E402
from ps1play.agent.perception import PerceptionGuard           # noqa: E402

PAD_MIRROR = 0x0D4948
SCORE_ADDR = 0x0EE318

MIRROR_EXPECT = {"RIGHT": 0x20, "Y": 0x8000, "B": 0x4000, "A": 0x2000,
                "X": 0x1000}

OBS = 90            # observation frames per rep
PREROLL = 210       # idle frames after restore: the mission-start
                    # drop-in animation must finish before gameplay
                    # consumes input (verified: intro churns ~1k RAM
                    # bytes and ignores Y/B/A until it ends)
HOLDS = {"CONTROL": 0, "Y": 60, "B": 24, "A": 8, "X": 60,
         "RIGHT": 45}
REPS = 3


def frame_mean_diff(a, b):
    if a is None or b is None:
        return 0.0
    if a.shape != b.shape:
        return 999.0
    return float(np.mean(np.abs(a.astype(np.int16) - b.astype(np.int16))))


def block_diff_max(a, b, block=32):
    """Max mean-abs-diff over 32x32 blocks — a LOCALIZED change metric
    (a small bullet / jump pose produces a bright block while the
    whole-frame mean stays tiny)."""
    if a is None or b is None or a.shape != b.shape:
        return 0.0
    d = np.abs(a.astype(np.int16) - b.astype(np.int16)).mean(axis=2)
    h, w = d.shape
    best = 0.0
    for y in range(0, h - block + 1, block):
        for x in range(0, w - block + 1, block):
            m = float(d[y:y + block, x:x + block].mean())
            if m > best:
                best = m
    return best


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Phase D action-verification lab (savestate tier)")
    ap.add_argument("--game", default=labconfig.resolve_path("game"))
    ap.add_argument("--core", default=labconfig.resolve_path("core"))
    ap.add_argument("--workspace",
                    default=labconfig.resolve_path("workspace"))
    ap.add_argument("--evidence-dir",
                    default=labconfig.resolve_path("evidence_dir"))
    ap.add_argument("--state", default="m1_start",
                    help="named savestate to branch from (workspace "
                         "states dir)")
    ap.add_argument("--firmware", default="openbios",
                    choices=list(labconfig.FIRMWARE_MODES))
    a = ap.parse_args(argv)

    out = os.path.join(a.evidence_dir, "action_lab")
    os.makedirs(out, exist_ok=True)

    fw = labconfig.resolve_firmware(a.firmware, a.workspace)
    kw = {"core": a.core, "workspace": a.workspace}
    if fw["override_vars"]:
        kw["var_overrides"] = fw["override_vars"]
    p = PS1Play(a.game, **kw)
    info = p.boot()
    fw_ev = labconfig.firmware_log_evidence(
        getattr(p.core, "log_history", []))
    fw_ok, fw_detail = labconfig.check_firmware_trust(fw, fw_ev)
    print("boot:", json.dumps(info, default=str), flush=True)
    print(f"firmware: mode={fw['mode']} trust_ok={fw_ok} ({fw_detail})",
          flush=True)
    if not fw_ok:
        sys.exit(f"!! firmware trust failed: {fw_detail}")

    state_path = os.path.join(p.states_dir, f"{a.state}.state")
    if not os.path.exists(state_path):
        sys.exit(f"!! savestate not found: {state_path} — run "
                 "scripts/run_mission1_legit.py once to create it")
    with open(state_path, "rb") as f:
        base_state = f.read()
    p.core.unserialize(base_state)
    p.core.run_frame()          # materialize a frame after restore

    # ---- fresh per-boot anchor for the bombs counter -----------------
    guard = PerceptionGuard(p)
    anch = guard.anchor(log=print)
    print("anchor:", anch, flush=True)
    bombs_addr = guard.addrs.get("bombs")
    bombs_status = guard.verification.get("bombs", {}).get("status")
    if not bombs_addr or bombs_status != "VERIFIED":
        sys.exit(f"!! bombs anchor not VERIFIED in this boot: {anch}")
    bombs_addr = int(bombs_addr)

    def read_state():
        return (int(p.mem.u16(bombs_addr)), int(p.mem.u32(SCORE_ADDR)))

    p.core.unserialize(base_state)
    p.core.run_frame()
    bombs0, score0 = read_state()
    if not (0 <= bombs0 <= 40):
        sys.exit(f"!! bombs anchor implausible after reload: {bombs0}")
    print(f"branch state: bombs0={bombs0} score0={score0}", flush=True)

    # ---- controlled branches ----------------------------------------
    results = {}
    control_frames = []

    for action in ("CONTROL", "RIGHT", "Y", "B", "A", "X"):
        hold = HOLDS[action]
        reps = []
        for rep in range(REPS):
            p.core.unserialize(base_state)
            p.core.set_buttons("")
            for _ in range(PREROLL):
                p.core.run_frame()      # let the drop-in intro finish
            mirror_bits = []
            churn_history = []
            bombs_before, score_before = read_state()
            s_start = p.mem.snapshot()
            for f in range(OBS):
                if f < hold:
                    p.core.set_buttons(action if action != "CONTROL"
                                       else "")
                elif f == hold:
                    p.core.set_buttons("")
                p.core.run_frame()
                mirror_bits.append(int(p.mem.u16(PAD_MIRROR)))
                if f in (30, 60, 89):
                    churn_history.append(
                        int(np.count_nonzero(s_start != p.mem.snapshot())))
            final = np.asarray(p.core.frame_rgb()).copy()
            png_name = f"{action}_rep{rep}.png"
            try:
                from PIL import Image
                Image.fromarray(final).save(os.path.join(out, png_name))
            except Exception as e:                          # noqa: BLE001
                png_name = None
                print("png fail:", e, flush=True)
            bombs_after, score_after = read_state()
            reps.append({
                "rep": rep,
                "mirror_bits": mirror_bits,
                "churn_history": churn_history,
                "bombs_before": bombs_before, "bombs_after": bombs_after,
                "score_before": score_before, "score_after": score_after,
                "png": png_name,
            })
            if action == "CONTROL":
                control_frames.append(final)
        results[action] = reps

    # ---- analysis ----------------------------------------------------
    def held_ratio(bits, bit, seg_len):
        seg = bits[:seg_len]
        if not seg:
            return 0.0
        return sum(1 for b in seg if b & bit) / len(seg)

    def churn_delta(reps):
        ctrl = results["CONTROL"]
        out = []
        for r, c in zip(reps, ctrl):
            d = [r["churn_history"][i] - c["churn_history"][i]
                 for i in range(len(r["churn_history"]))]
            out.append(d)
        return out

    analysis = {}
    for action, reps in results.items():
        d = {}
        if action in MIRROR_EXPECT:
            d["mirror"] = {
                "expected_bit": MIRROR_EXPECT[action],
                "held_ratios": [round(held_ratio(r["mirror_bits"],
                                                 MIRROR_EXPECT[action],
                                                 hold), 3)
                                for r, hold in
                                zip(reps, [HOLDS[action]] * len(reps))]}
        if action in ("RIGHT", "Y", "B", "A", "X"):
            from PIL import Image as _Img
            d["frame_diff_vs_control"] = [
                round(frame_mean_diff(
                    np.asarray(_Img.open(os.path.join(out, r["png"]))),
                    control_frames[i]), 2)
                for i, r in enumerate(reps)]
            d["block_diff_max"] = [
                round(block_diff_max(
                    np.asarray(_Img.open(os.path.join(out, r["png"]))),
                    control_frames[i]), 2)
                for i, r in enumerate(reps)]
            d["churn_delta_vs_control"] = churn_delta(reps)
        if action == "A":
            d["bombs_delta"] = [r["bombs_after"] - r["bombs_before"]
                                for r in reps]
            d["bombs_minus1_each"] = all(x == -1 for x in d["bombs_delta"])
        if action in ("X", "RIGHT"):
            d["bombs_delta"] = [r["bombs_after"] - r["bombs_before"]
                                for r in reps]
        if action == "CONTROL":
            d["churn_history"] = [r["churn_history"] for r in reps]
        analysis[action] = d

    summary = {
        "tier": "savestate-calibration (NOT live-run evidence)",
        "branch_state": a.state,
        "bombs0": bombs0, "score0": score0,
        "bombs_anchor_this_boot": {"addr": hex(bombs_addr),
                                   "status": bombs_status,
                                   "method": guard.verification.get(
                                       "bombs", {}).get("method")},
        "firmware": {"mode": fw["mode"], "bios_md5": fw["bios_md5"],
                     "trust_ok": fw_ok},
        "core": a.core, "game": a.game, "boot": info,
        "verdicts": {},
    }
    vm = {k: analysis[k]["mirror"]["held_ratios"] for k in
          ("RIGHT", "Y", "B", "A", "X") if "mirror" in analysis.get(k, {})}
    summary["mirror_held_ratios"] = vm
    summary["pad_mirror_semantics"] = (
        "0x0D4948 carries DIRECTIONAL bits only (RIGHT=0x20 observed); "
        "Y/B/A never appear there — action verification uses in-game "
        "outcomes")
    summary["verdicts"]["direction_mirror_responds"] = bool(
        vm.get("RIGHT")) and min(vm["RIGHT"]) > 0.9
    # World-effect verdicts: RAM churn delta (full-bank snapshot diff)
    # plus a LOCALIZED visual block diff. Thresholds are anchored by
    # the negative control measured in THIS lab (X: churn ~7, block
    # diff ~0): a treatment is an effect only when it clears the
    # control by a wide margin.
    nx = analysis["X"]
    ctrl_churn_peak = max(max(r) for r in analysis["CONTROL"]["churn_history"])
    fire_churn = [r[0] for r in analysis["Y"]["churn_delta_vs_control"]]
    jump_churn = [r[0] for r in analysis["B"]["churn_delta_vs_control"]]
    summary["verdicts"]["fire_world_effect"] = (
        min(fire_churn) > max(100, 10 * max(nx["churn_delta_vs_control"][0]
                                            or [0])) and
        max(analysis["Y"]["block_diff_max"]) > 8.0)
    summary["verdicts"]["jump_world_effect"] = (
        min(jump_churn) > 50 and
        max(analysis["B"]["block_diff_max"]) > 6.0)
    summary["verdicts"]["grenade_bombs_minus1_each_rep"] = \
        analysis["A"].get("bombs_minus1_each", False)
    summary["verdicts"]["negative_control_inert"] = (
        max(analysis["X"]["frame_diff_vs_control"] or [0]) < 5.0 and
        all(x == 0 for x in analysis["X"]["bombs_delta"]))

    with open(os.path.join(out, "action_lab_result.json"), "w") as f:
        json.dump({"summary": summary, "raw": results,
                   "analysis": analysis}, f, indent=1, default=str)
    print(json.dumps(summary, indent=1, default=str))
    print("result ->", os.path.join(out, "action_lab_result.json"))


if __name__ == "__main__":
    main()
