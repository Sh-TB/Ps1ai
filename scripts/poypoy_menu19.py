#!/usr/bin/env python3
"""poypoy_menu19.py — the wheel hypothesis: does X act inside the post-field state?

menu17/18 ground truth: X-hold 60f on MODE SELECT = 131K-byte state
transition (menu -> field); the +700f state IGNORES direction keys even
at +3000f. Disc strings say: X = select, team select = a roulette wheel.
Hypothesis: the field-adjacent state is the wheel / match intro, and X
(spins the wheel) is the button that acts there — directions only matter
after the wheel stops.

Arms from a saved +700f field checkpoint: ctrl / X-pulse-3f / X-hold-60f /
START-hold-60f. Per arm at +120f and +360f: RAM byte-delta vs the same-frame
no-input baseline, direction census (does LEFT vs RIGHT differ now?), PNG.
Verdicts: X_ACTS (X arm's delta >> ctrl delta), REAL_MATCH (directions
register after an X arm), or not_yet.
"""
import json
import os
import sys
import time

import numpy as np
from PIL import Image

REPO = "/home/z/my-project/ps1ai"
sys.path.insert(0, REPO)
from ps1play.api import PS1Play                                   # noqa

EVID = "/tmp/my-project/emu/games_psx/evidence/poypoy_menu19"
CUE = "/tmp/my-project/emu/games_psx/poy_poy/Poy Poy (USA).cue"
if not os.path.exists(CUE):
    CUE = "/home/z/my-project/emu/games_psx/poy_poy/Poy Poy (USA).cue"
# reuse the surviving r16 session workspace: its states/ dir holds the
# menu_anchor checkpoint under the /home-z name mapping
WS = "/tmp/my-project/emu/games_psx/ws_poypoy_menu18"
MENU_CKPT = "/home/z/my-project/emu/games_psx/ws_poypoy_menu18/menu_anchor.ckpt"


def snap(p, name):
    img = p.core.frame_rgb()
    if img is not None:
        Image.fromarray(img).save(os.path.join(EVID, name))
    return img


def snap_ram(p):
    return np.frombuffer(bytes(p.mem.snapshot()), dtype=np.uint8).copy()


def run_to(p, anchor, f):
    while p.core.frames_run - anchor < f:
        p.core.run(50, set())


def run_rel(p, rel, target):
    if target > rel:
        p.core.run(target - rel, set())
        return target
    return rel


def arm(p, ckpt, name, btns, hold, base_ram, field_f=700):
    """Rewind to the field checkpoint, apply one arm, measure at +120/+360.
    IMPORTANT: load_state does NOT restore frames_run (verified empirically)
    — all stepping after a rewind is RELATIVE frames via p.core.run."""
    rel = 0
    p.load_state(ckpt)
    if hold:
        p.core.run(hold, btns)
        rel += hold
    else:
        p.core.run(3, set())  # keep frame alignment for the pulse arm
        rel += 3
    out = {}
    for f in (120, 360):
        rel = run_rel(p, rel, f)
        ram = snap_ram(p)
        base = base_ram.get(f)
        out[f"ram_delta_f{f}"] = int((ram != base).sum()) if base is not None else None
        out[f"png_f{f}"] = f"m19_{name}_f{f}.png"
        snap(p, out[f"png_f{f}"])
    # direction census at +330 (240 settle + 90 probe), deterministic core
    cens = {}
    for probe, pbtns in (("none", set()), ("left", {"LEFT"}), ("right", {"RIGHT"})):
        p.load_state(ckpt)
        rel = 0
        if hold:
            p.core.run(hold, btns)
            rel += hold
        else:
            p.core.run(3, set())
            rel += 3
        rel = run_rel(p, rel, 240)
        p.core.run(90, pbtns)
        cens[probe] = snap_ram(p)
    # determinism noise: re-run the none probe from the same checkpoint
    p.load_state(ckpt)
    rel = 0
    if hold:
        p.core.run(hold, btns)
        rel += hold
    else:
        p.core.run(3, set())
        rel += 3
    rel = run_rel(p, rel, 240)
    p.core.run(90, set())
    n2 = snap_ram(p)
    det = int((n2 != cens["none"]).sum())
    del cens["none"]
    out["census"] = {
        "det_none": det,
        "left_vs_right": int((cens["left"] != cens["right"]).sum()),
        "left_vs_none": int((cens["left"] != n2).sum()),
    }
    out["verdict_dir"] = ("DIRS_LIVE" if out["census"]["left_vs_right"] > max(500, 5 * det)
                          else "dirs_dead")
    return out


def main():
    os.makedirs(EVID, exist_ok=True)
    os.makedirs(WS, exist_ok=True)
    out = {"started": time.strftime("%FT%TZ", time.gmtime())}
    p = PS1Play(CUE, workspace=WS)
    p.boot()
    p.wait(480)
    p.load_state(MENU_CKPT)
    anchor = p.core.frames_run
    out["menu_anchor_restored_at"] = anchor
    # enter the field state exactly as menu17/18: X-hold 60f
    p.core.run(60, {"X"})
    run_to(p, anchor, 700)
    FIELD_CKPT = os.path.join(WS, "field700.ckpt")
    p.save_state(FIELD_CKPT)
    snap(p, "m19_field700.png")
    out["field700_frame"] = p.core.frames_run

    # baseline: no-input RAM at +120/+360 past the FIELD checkpoint (relative)
    base_ram = {}
    for f in (120, 360):
        p.load_state(FIELD_CKPT)
        p.core.run(f, set())
        base_ram[f] = snap_ram(p)
    p.load_state(FIELD_CKPT)
    p.core.run(120, set())
    n2 = snap_ram(p)
    out["baseline_det_f120"] = int((n2 != base_ram[120]).sum())

    arms = {
        "ctrl": (set(), 0),
        "xpulse": ({"X"}, 0),
        "xhold": ({"X"}, 60),
        "starthold": ({"START"}, 60),
    }
    results = {}
    for name, (btns, hold) in arms.items():
        results[name] = arm(p, FIELD_CKPT, name, btns, hold, base_ram)
        print(name, json.dumps(results[name]["census"]),
              "deltas", results[name]["ram_delta_f120"], results[name]["ram_delta_f360"],
              results[name]["verdict_dir"])
    out["arms"] = results
    ctrl_d = results["ctrl"]["ram_delta_f120"] or 0
    for name in ("xpulse", "xhold"):
        d = results[name]["ram_delta_f120"]
        if d is not None and d > max(2000, 10 * max(1, ctrl_d)):
            out[f"{name}_verdict"] = "X_ACTS"
        elif results[name]["verdict_dir"] == "DIRS_LIVE":
            out[f"{name}_verdict"] = "REAL_MATCH"
        else:
            out[f"{name}_verdict"] = "no_change"
    out["finished"] = time.strftime("%FT%TZ", time.gmtime())
    with open(os.path.join(EVID, "menu19.json"), "w") as f:
        json.dump(out, f, indent=1, default=str)
    try:
        p.core.close()
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
