#!/usr/bin/env python3
"""input_causality.py — INPUT_CAUSALITY gate on the lawful BIOS UI.

Proves that controller input causes verifiable state changes in the
running game/BIOS, using only lawful content (SCPH BIOS CD-player menu
driven against a self-generated silent audio disc).

A/B/counter-test design (Phase 4 of the mission):

  baseline run   : boot, settle, no input at all, screenshots over time
  treatment run  : identical boot, CROSS pressed during a fixed window
                   (starts CD playback -> the on-screen time counter
                   appears and advances), screenshots over time
  classification : CAUSAL if the treatment observation (counter area
                   activity) distinguishes itself from the baseline in
                   the measured region AND the effect repeats; the
                   screenshots are saved for independent inspection.

All runs are contentless-of-copyright: the disc is generated silence.
Nothing here writes to RAM; input goes only through the real
retro_input_state callback path.

Exit codes: 0 CAUSAL | 2 NOT_CAUSAL / INCONCLUSIVE | 3 setup error.

Usage:
    python3 scripts/input_causality.py --bios /path/scph1001.bin \
        --content /path/audio_fixture.cue [--out /tmp/causality] [--json]
"""
import argparse
import json
import os
import shutil
import sys
import time

import numpy as np

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)

from ps1play.core.host import LibretroCore  # noqa: E402

DEF_CORE = os.environ.get(
    "M1_CORE", "/home/z/my-project/ps1-test/cores/mednafen_psx_libretro.so")

OVERRIDES = {b"beetle_psx_renderer": b"software",
             b"beetle_psx_frame_duping": b"disabled"}


def _shot(core, path):
    from PIL import Image
    arr = core.frame_rgb()
    if arr is None:
        return None
    Image.fromarray(arr).save(path)
    return arr


def _region_diff(a, b, y0=0.70):
    """Mean abs pixel difference on the bottom (1-y0) band of the frame.

    The BIOS CD-player UI (focus highlight / time counter) lives in the
    lower part of the screen; the rotating cube occupies the center.
    A static UI under no input yields ~0 diff; starting playback yields
    a large, monotonic diff (counter appears and advances).
    """
    if a is None or b is None:
        return None
    h = a.shape[0]
    band = a[int(h * y0):], b[int(h * y0):]
    return float(np.abs(band[0].astype(int) - band[1].astype(int)).mean())


def _boot(core_path, bios, content, work):
    sysdir = os.path.join(work, "system")
    savedir = os.path.join(work, "saves")
    shutil.rmtree(work, ignore_errors=True)
    os.makedirs(sysdir, exist_ok=True)
    os.makedirs(savedir, exist_ok=True)
    shutil.copyfile(bios, os.path.join(sysdir, os.path.basename(bios)))
    core = LibretroCore(core_path, sysdir, savedir,
                        var_overrides=dict(OVERRIDES))
    core.load_game(content)
    return core


def run_arm(core_path, bios, content, work, shots_dir, prefix,
            settle=420, hold=(330, 342), tail=180, shot_every=60):
    """Run one arm; returns frame array snapshots + schedule metadata.

    `hold` is the (start, end) frame window during which CROSS is held;
    pass hold=None for the no-input baseline arm.
    """
    core = _boot(core_path, bios, content, work)
    sched = {"settle": settle, "hold": list(hold) if hold else None,
             "tail": tail}
    frames = {}
    total = settle + tail
    for i in range(total):
        if hold and hold[0] <= i < hold[1]:
            core.set_buttons({"X"})
        else:
            core.set_buttons(set())
        core.run_frame()
        if i >= settle and (i - settle) % shot_every == 0:
            arr = _shot(core, os.path.join(
                shots_dir, f"{prefix}_f{i - settle:04d}.png"))
            if arr is not None:
                frames[i - settle] = arr
    core.shutdown()
    return frames, sched


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bios", required=True)
    ap.add_argument("--content", required=True,
                    help="lawful cue fixture (self-generated audio disc)")
    ap.add_argument("--core", default=DEF_CORE)
    ap.add_argument("--out", default="/tmp/ps1play_causality")
    ap.add_argument("--settle", type=int, default=420)
    ap.add_argument("--hold", type=int, nargs=2, default=(330, 342),
                    help="frame window (relative) holding CROSS")
    ap.add_argument("--tail", type=int, default=180)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    shots = os.path.join(a.out, "shots")
    os.makedirs(shots, exist_ok=True)
    res = {"tool": "input_causality", "bios": os.path.abspath(a.bios),
           "content": os.path.abspath(a.content), "core": a.core,
           "button": "X (cross) via retro_input_state", "arms": {}}

    t0 = time.time()
    try:
        base, sched = run_arm(a.core, a.bios, a.content,
                              os.path.join(a.out, "ws_base"), shots,
                              "base", settle=a.settle, hold=None,
                              tail=a.tail)
        treat, sched2 = run_arm(a.core, a.bios, a.content,
                                os.path.join(a.out, "ws_treat"), shots,
                                "treat", settle=a.settle, hold=a.hold,
                                tail=a.tail)
    except Exception as e:                                      # noqa: BLE001
        res.update(verdict="SETUP_ERROR", detail=str(e))
        print(json.dumps(res, indent=1))
        sys.exit(3)

    keys = sorted(set(base) & set(treat))
    res["arms"]["baseline"] = {"shots": sorted(os.listdir(shots)) if False
                               else [f"base_f{k:04d}.png" for k in keys],
                               "schedule": sched}
    res["arms"]["treatment"] = {"shots": [f"treat_f{k:04d}.png"
                                          for k in keys],
                                "schedule": sched2}

    # ---- measurement: baseline self-diff vs treatment-vs-baseline ----
    self_diffs = [_region_diff(base[k], base[keys[max(0, idx - 1)]])
                  for idx, k in enumerate(keys)]
    cross_diffs = [_region_diff(treat[k], base[k]) for k in keys]
    res["baseline_self_diff"] = [round(d, 3) for d in self_diffs]
    res["treatment_vs_baseline_diff"] = [round(d, 3) for d in cross_diffs]

    # CAUSAL: the treatment diverges from baseline well above the
    # baseline's own self-noise, and stays diverged (persistent effect).
    noise = max(self_diffs) if self_diffs else 0.0
    diverged = [d > max(2.0, noise * 3) for d in cross_diffs]
    res["baseline_max_self_diff"] = round(noise, 3)
    res["divergence_flags"] = diverged
    res["verdict"] = ("CAUSAL" if diverged and sum(diverged) >= 2
                      else "NOT_CAUSAL")
    res["elapsed_s"] = round(time.time() - t0, 1)

    with open(os.path.join(a.out, "input_causality_result.json"), "w") as f:
        json.dump(res, f, indent=1)
    if a.json:
        print(json.dumps(res, indent=1))
    else:
        print(f"verdict  : {res['verdict']} ({res['elapsed_s']}s)")
        print(f"baseline self-diff : {res['baseline_self_diff']}")
        print(f"treat vs baseline  : {res['treatment_vs_baseline_diff']}")
        print(f"screenshots        : {shots}")
    sys.exit(0 if res["verdict"] == "CAUSAL" else 2)


if __name__ == "__main__":
    main()
