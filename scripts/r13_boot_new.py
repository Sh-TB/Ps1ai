#!/usr/bin/env python3
"""r13_boot_new.py — Round 13 boot gate for the TWO new games.

Usage: python3 scripts/r13_boot_new.py <tag> <cue_path>

  tag cs50x    -> psxBreakout (locally built ISO9660 + PS-EXE)
  tag doukutsu -> Cave Story PSX (doukutsupsx v0.7)

ONE beetle boot PER PROCESS. Evidence: boot timeline (frame_mean,
madiff, pad-buffer mirrors), screen PNGs, then an INPUT causality probe
(idle control vs START / directional hold) with clean separation.

Verdicts: BOOTED(+INPUT_PROBE_CAUSAL) / BOOTED_NO_INPUT / FAILED(stage).
"""
from __future__ import annotations

import json
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
OPENBIOS_SRC = os.path.join(REPO, "third_party", "openbios",
                            "openbios.bin")
PADBUFF_SIG = b"\x00\x41\xff\xff"
TAG = sys.argv[1]
CUE = sys.argv[2]
OUT = os.path.join(REPO, "scratch", "round13_newgames", TAG)
WS = os.path.join(EMU, f"ws_{TAG}_r13")


def jrn(ev, cur=None):
    ev = {"t": round(time.time(), 3), **ev}
    with open(os.path.join(OUT, "events.jsonl"), "a") as f:
        f.write(json.dumps(ev, default=str) + "\n")
    print(f"[{TAG}]", json.dumps(ev, default=str)[:220], flush=True)


def madiff(a, b):
    if a is None or b is None or a.shape != b.shape:
        return None
    return float(np.abs(a.astype(np.int16) - b.astype(np.int16)).mean())


def save_png(arr, name):
    from PIL import Image
    Image.fromarray(arr).save(os.path.join(OUT, name))


def padbuff_addrs(snap):
    hits, i = [], 0
    while True:
        i = snap.find(PADBUFF_SIG, i)
        if i < 0:
            break
        hits.append(i)
        i += 1
    return hits


def main():
    os.makedirs(OUT, exist_ok=True)
    os.makedirs(os.path.join(WS, "system"), exist_ok=True)
    shutil.copyfile(OPENBIOS_SRC, os.path.join(WS, "system",
                                               "openbios.bin"))
    fw = labconfig.resolve_firmware("openbios", workspace=WS)
    p = PS1Play(CUE, workspace=WS, var_overrides=fw["override_vars"])
    boot_info = p.boot()
    fw_ev = labconfig.firmware_log_evidence(
        getattr(p.core, "log_history", []))
    ok, detail = labconfig.check_firmware_trust(fw, fw_ev)
    jrn({"ev": "boot", "core": boot_info, "fw_trust": ok,
         "fw_detail": detail, "fw_mode": fw["mode"]})
    if not ok:
        ff = p.core.frame_rgb()
        if ff is not None:
            save_png(ff, "fail_fw.png")
        json.dump({"verdict": "FAILED_FW_TRUST", "detail": detail},
                  open(os.path.join(OUT, "report.json"), "w"), indent=2)
        return 2

    # ---- boot timeline: 36 polls x 30 frames, PNG every 3rd poll ----
    timeline, addrs = [], []
    prev = None
    pngs = []
    for k in range(36):
        fr = p.core.frame_rgb()
        if fr is None:                       # pre-render frames
            p.wait(30)
            continue
        a = madiff(prev, fr)
        prev = fr
        g = fr.mean(axis=2)
        ent = {"f": p.core.frames_run, "frame_mean": round(float(
            g.mean()), 2), "madiff": None if a is None
            else round(a, 4)}
        if k % 3 == 0:
            nm = f"boot_{k:02d}.png"
            save_png(fr, nm)
            pngs.append({"f": ent["f"], "png": nm,
                         "frame_mean": ent["frame_mean"]})
        snap = bytes(p.mem.snapshot())
        addrs = padbuff_addrs(snap) or addrs
        ent["pad_id41"] = len(addrs)
        timeline.append(ent)
        if k % 6 == 0:
            jrn({"ev": "poll", **ent})
        p.wait(30)
    jrn({"ev": "timeline_done", "last_f": p.core.frames_run,
         "pad_id41": len(addrs), "pngs": len(pngs)})

    # ---- INPUT causality probe ----
    probe_btn = "START" if TAG == "doukutsu" else "LEFT"
    ctrl = []
    for _ in range(4):
        a0 = p.core.frame_rgb()
        p.wait(30, set())
        f1 = p.core.frame_rgb()
        ctrl.append(round(madiff(a0, f1) or 0.0, 4)
                    if f1 is not None else 0.0)
    fb = p.core.frame_rgb()
    if fb is not None:
        save_png(fb, "probe_before.png")
    p.core.run(10, {probe_btn})
    mir = {hex(a): p.mem.u16(a + 2) for a in addrs}
    p.core.run(4, set())
    seq = []
    for _ in range(8):
        a1 = p.core.frame_rgb()
        p.wait(4, set())
        f1 = p.core.frame_rgb()
        seq.append(round(madiff(a1, f1) or 0.0, 4)
                   if f1 is not None else 0.0)
    p.wait(60, set())
    fa = p.core.frame_rgb()
    if fa is not None:
        save_png(fa, "probe_after.png")

    # second probe with the other direction (visual movement proof)
    probe2 = "RIGHT" if TAG == "cs50x" else None
    seq2 = []
    if probe2:
        p.core.run(10, {probe2})
        p.core.run(4, set())
        for _ in range(8):
            a2 = p.core.frame_rgb()
            p.wait(4, set())
            f2 = p.core.frame_rgb()
            seq2.append(round(madiff(a2, f2) or 0.0, 4)
                        if f2 is not None else 0.0)

    stable = sum(1 for e in timeline[-8:] if e["frame_mean"] > 2.0)
    verdict = {
        "tag": TAG, "cue": CUE, "core": boot_info,
        "fw": {"mode": fw["mode"], "trust_ok": ok},
        "timeline_tail": timeline[-8:], "padbuff_addrs": len(addrs),
        "pad_mirror_held": mir,
        "control_max_madiff": max(ctrl), "control": ctrl,
        f"probe_{probe_btn}_max_madiff": max(seq), "probe_seq": seq,
        "probe2": {"btn": probe2, "max": max(seq2) if seq2 else None,
                   "seq": seq2},
        "stable_frames": stable,
        "pngs": pngs,
    }
    if stable >= 6 and len(addrs) >= 1:
        if max(seq) > 0.05 and max(seq) > 2 * max(ctrl):
            verdict["verdict"] = "BOOTED_INPUT_PROBE_CAUSAL"
        else:
            verdict["verdict"] = "BOOTED_NO_INPUT_RESPONSE"
    else:
        verdict["verdict"] = "BOOT_UNCONFIRMED"
    json.dump(verdict, open(os.path.join(OUT, "report.json"), "w"),
              indent=2)
    jrn({"ev": "verdict", **{k: verdict[k] for k in
                             ("verdict", "control_max_madiff")}})
    print("VERDICT", verdict["verdict"], flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
