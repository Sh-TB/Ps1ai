#!/usr/bin/env python3
"""r35a_reach.py — R35-A phase REACH (boot #1 of 3).

Rebuild the pre-encounter checkpoint lost in the filesystem rollback:
boot() (issue4_controller real-play boot) -> gif_story_run.phase_b
(live-play gate -> DISCLOSED hp_pair_freeze EXPLORATION walk to the
lob window + grenade top-up) -> nudge into px [810, 868] -> save
savestate `r35a_ckpt` -> unfreeze.

Identical recipe to scripts/msx_helicopter_ladder.py phase_reach, with
a UNIQUE checkpoint name and evidence under scratch/r35a/.

Boot ledger: increments scratch/r35a/boots_used.json BEFORE load_game.
"""
from __future__ import annotations

import json
import os
import sys
import time

from PIL import Image                                     # noqa: E402

_REPO = "/home/z/my-project/ps1ai"
for _p in (_REPO, os.path.join(_REPO, "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from ps1play.telemetry import JsonlTrace                 # noqa: E402
import msx_gate_probe as gp                              # noqa: E402
import gif_story_run as story                            # noqa: E402
from issue4_controller import boot                       # noqa: E402

EVID = os.path.join(_REPO, "scratch", "r35a")
LEDGER = os.path.join(EVID, "boots_used.json")
CKPT = "r35a_ckpt"
PLAYER_X = 0x0CA2E0
A_FLAGS = 0x0EE518
A_SCORE = 0x0EE318
A_PAIR0, A_PAIR1 = 0x0CA2F6, 0x0CA2FE
GRENADES = 0x0EDCF4
KILL_LO, KILL_HI = 810.0, 868.0


def log(*a):
    print("[r35a-reach]", *a, file=sys.stderr, flush=True)


def amend_ledger(reason):
    with open(LEDGER) as f:
        led = json.load(f)
    led["count"] = int(led.get("count", 0)) + 1
    led.setdefault("log", []).append(
        {"n": led["count"], "ts": time.strftime("%FT%TZ", time.gmtime()),
         "script": "r35a_reach.py", "reason": reason})
    with open(LEDGER, "w") as f:
        json.dump(led, f, indent=1)
    log(f"boot ledger: count={led['count']} ({reason})")
    return led["count"]


def px_of(m):
    return int(m.u32(PLAYER_X)) / 65536.0


def png(p, name):
    rgb = p.core.frame_rgb()
    if rgb is not None:
        Image.fromarray(rgb).save(os.path.join(EVID, "png", name))


def nudge_into_window(p, session, m):
    """After phase_b: position inside [810, 868] (lob window)."""
    for k in range(900):
        x = px_of(m)
        if KILL_LO <= x <= KILL_HI:
            return x
        btns = {"RIGHT"} if x < KILL_LO else {"LEFT"}
        p.core.set_buttons(btns)
        p.core.run_frame()
        session.gs.tick()
    return px_of(m)


def main():
    os.makedirs(os.path.join(EVID, "png"), exist_ok=True)
    trace = JsonlTrace(os.path.join(EVID, "reach_trace.jsonl"))
    evlog = JsonlTrace(os.path.join(EVID, "reach_highlights.jsonl"))
    cap = {"count": 0}
    t0 = time.time()
    trace.write({"type": "reach_start",
                 "assist": "hp_pair_freeze EXPLORATION (disclosed) "
                           "for REACH ONLY; trace/attack phases run "
                           "UNFROZEN",
                 "core": os.environ.get(
                     "M1_CORE",
                     "labconfig default (see boots_used.json)")})

    n = amend_ledger("REACH: boot() -> phase_b walk -> save r35a_ckpt")
    if n > 3:
        raise SystemExit("BOOT CAP EXCEEDED")
    p, fwmode = boot()
    log("boot complete, firmware:", fwmode,
        "core:", os.path.basename(p.core_path))

    rb, sess = story.phase_b(p, 0, trace, evlog, EVID, 0, cap, EVID)
    x = nudge_into_window(p, sess, p.mem)
    px = px_of(p.mem)
    gren = int(p.mem.u8(GRENADES))
    hp = int(p.mem.u16(A_PAIR0))
    p.save_state(CKPT)
    gp.unfreeze(sess, "r35a_reach")
    png(p, "r35a_checkpoint.png")
    rec = {"type": "checkpoint_saved", "state": CKPT,
           "px": round(px, 1), "window_x": round(x, 1),
           "grenades": gren, "hp0": hp, "hp1": int(p.mem.u16(A_PAIR1)),
           "flags_active": (int(p.mem.u32(A_FLAGS)) & 0xFF) == 0xFF,
           "score": int(p.mem.u32(A_SCORE)),
           "frame": p.core.frames_run,
           "wall_s": round(time.time() - t0, 1),
           "phase_b_report": rb,
           "frozen_at_save_note":
               "savestate captured BEFORE unfreeze; freeze codes are "
               "not persisted in savestates (gs.tick per frame), so "
               "loads of r35a_ckpt are UNFROZEN"}
    trace.write(rec)
    trace.close()
    evlog.close()
    with open(os.path.join(EVID, "reach_report.json"), "w") as f:
        json.dump({"checkpoint": CKPT, "firmware_mode": fwmode,
                   **{k: rec[k] for k in ("px", "window_x", "grenades",
                                          "hp0", "flags_active",
                                          "wall_s", "phase_b_report")}},
                  f, indent=1)
    log("checkpoint saved:", json.dumps(
        {k: rec[k] for k in ("state", "px", "grenades", "hp0",
                             "flags_active", "wall_s")}))
    ok = rec["flags_active"] and KILL_LO <= px <= KILL_HI
    log("REACH", "OK" if ok else "MARGINAL")
    return 0 if ok else 2


if __name__ == "__main__":
    sys.exit(main())
