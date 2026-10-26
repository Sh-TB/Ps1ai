#!/usr/bin/env python3
"""r13_doukutsu_long.py — Cave Story PSX (doukutsupsx v0.7) long boot.

ONE beetle boot. Poll up to ~75 s of emulated time through the
LOADING phase into the title screen; save the timeline; then a START
causality probe (idle control vs hold+release) with before/after PNGs.

Verdicts: BOOTED_TITLE(+INPUT_PROBE_CAUSAL) / BOOTED_LOADING_STABLE /
FAILED(stage)."""
import os
import shutil
import sys
import time

REPO = "/home/z/my-project/ps1ai"
for _p in (REPO, os.path.join(REPO, "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import numpy as np                                          # noqa: E402
from ps1play import labconfig                               # noqa: E402
from ps1play.api import PS1Play                             # noqa: E402

EMU = "/home/z/my-project/emu/games_homebrew"
CUE = os.path.join(EMU, "patched", "doukutsu_lic.cue")
WS = os.path.join(EMU, "ws_doukutsu_r13long")
OUT = os.path.join(REPO, "scratch", "round13_newgames", "doukutsu_long")
PADBUFF_SIG = b"\x00\x41\xff\xff"


def jrn(ev):
    ev = {"t": round(time.time(), 3), **ev}
    with open(os.path.join(OUT, "events.jsonl"), "a") as f:
        f.write(str(ev).replace("'", '"') + "\n")
    print("[dk]", str(ev)[:200], flush=True)


def madiff(a, b):
    if a is None or b is None or a.shape != b.shape:
        return None
    return float(np.abs(a.astype(np.int16) - b.astype(np.int16)).mean())


def save(arr, name):
    from PIL import Image
    Image.fromarray(arr).save(os.path.join(OUT, name))


def snap_addrs(p):
    s = bytes(p.mem.snapshot())
    hits, i = [], 0
    while True:
        i = s.find(PADBUFF_SIG, i)
        if i < 0:
            break
        hits.append(i)
        i += 1
    return len(hits)


def main():
    os.makedirs(OUT, exist_ok=True)
    os.makedirs(os.path.join(WS, "system"), exist_ok=True)
    shutil.copyfile(os.path.join(REPO, "third_party", "openbios",
                                 "openbios.bin"),
                    os.path.join(WS, "system", "openbios.bin"))
    fw = labconfig.resolve_firmware("openbios", workspace=WS)
    p = PS1Play(CUE, workspace=WS, var_overrides=fw["override_vars"])
    boot = p.boot()
    jrn({"ev": "boot", "core": boot.get("core", "")[:40]})

    # ---- long settle: 70 polls x 60 frames ----
    timeline, pngs = [], []
    prev = None
    title_seen_at = None
    for k in range(70):
        fr = p.core.frame_rgb()
        if fr is None:
            p.wait(60)
            continue
        a = madiff(prev, fr)
        prev = fr
        g = fr.mean(axis=2)
        ent = {"k": k, "f": p.core.frames_run,
               "mean": round(float(g.mean()), 2),
               "madiff": None if a is None else round(a, 4)}
        # LOADING phase marker: dark blue bg (mean ~11), title brighter
        if k % 4 == 0:
            nm = f"long_{k:02d}.png"
            save(fr, nm)
            pngs.append({"f": ent["f"], "png": nm,
                         "mean": ent["mean"]})
        timeline.append(ent)
        # title heuristic: stable bright screen (mean > 20) after the
        # loading phase OR any sustained animation (madiff > 1) late
        if k > 12 and ent["mean"] > 20 and a is not None and a > 0.3:
            title_seen_at = ent
            jrn({"ev": "candidate_title", **ent})
            break
        if k > 12 and ent["mean"] > 45:
            title_seen_at = ent
            jrn({"ev": "candidate_title_bright", **ent})
            break
        p.wait(60)
    jrn({"ev": "settle_done", "tail": timeline[-4:], "pngs": len(pngs)})

    # ---- START probe ----
    fr0 = p.core.frame_rgb()
    save(fr0, "probe_before.png")
    ctrl = []
    for _ in range(4):
        a0 = p.core.frame_rgb()
        p.wait(30, set())
        f1 = p.core.frame_rgb()
        ctrl.append(round(madiff(a0, f1) or 0.0, 4))
    p.core.run(12, {"START"})
    p.core.run(4, set())
    seq = []
    for _ in range(10):
        a1 = p.core.frame_rgb()
        p.wait(4, set())
        f1 = p.core.frame_rgb()
        seq.append(round(madiff(a1, f1) or 0.0, 4)
                   if f1 is not None else 0.0)
    p.wait(90, set())
    save(p.core.frame_rgb(), "probe_after.png")

    verdict = "BOOTED_TITLE" if title_seen_at else "BOOTED_LOADING_STABLE"
    if max(seq) > 0.05 and max(seq) > 2 * max(ctrl or [0.0]):
        verdict += "_INPUT_PROBE_CAUSAL"
    rep = {"verdict": verdict, "boot": boot,
           "title_seen": title_seen_at, "timeline_tail": timeline[-10:],
           "control": ctrl, "probe_seq": seq, "pngs": pngs,
           "pad_id41_final": snap_addrs(p)}
    import json
    json.dump(rep, open(os.path.join(OUT, "report.json"), "w"),
              indent=2)
    jrn({"ev": "verdict", "verdict": verdict,
         "probe_max": max(seq), "ctrl_max": max(ctrl)})
    print("VERDICT", verdict, flush=True)


if __name__ == "__main__":
    main()
