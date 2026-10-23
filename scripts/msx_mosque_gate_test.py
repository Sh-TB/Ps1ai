#!/usr/bin/env python3
"""msx_mosque_gate_test.py — the D6+D7 connection experiment.

Hypothesis (from session-2's mosque causality + the D7 pin state
machine): the mosque roof-cannon kill (+800 signature) is the
village-section completion trigger — killing it lifts the px-1163 pin
AND quiets the mortar rain (D6).

Arms, both starting from the SAME clamp0 savestate (px 1163, pinned,
this boot-session):
  KILL arm    : disclosed hp-freeze reach LEFT to the lob window ->
                grenade volley until the +800&0x20 mosque signature ->
                walk RIGHT -> hold RIGHT 15 chunks -> max px?
  CONTROL arm : fresh boot -> freeze -> load clamp0 -> walk LEFT to
                the window -> NO volley -> walk RIGHT -> max px?
Pin lifted = max px > 1180. All assists DISCLOSED (hp-freeze for reach
safety only; the volley itself is real game input + real grenades).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

from PIL import Image                                 # noqa: E402

_REPO = "/home/z/my-project/ps1ai"
for _p in (_REPO, os.path.join(_REPO, "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from ps1play import labconfig                         # noqa: E402
from issue4_controller import boot                    # noqa: E402
import msx_gate_probe as gp                           # noqa: E402

EVID = os.path.join(
    labconfig.resolve_path("evidence_dir"), "mosque_gate")
GRENADES = 0x0EDCF4
WINDOW_LO, WINDOW_HI = 660.0, 880.0
KILL_LO, KILL_HI = 810.0, 868.0
LOB_SPOT_LO, LOB_SPOT_HI = 700.0, 780.0               # LEFT-facing spot
PIN_LIMIT = 1180.0


def log(*a):
    print("[gatetest]", *a, flush=True)


def px_of(m):
    return int(m.u32(0x0CA2E0)) >> 16


def png(p, tag, name):
    rgb = p.core.frame_rgb()
    if rgb is not None:
        Image.fromarray(rgb).save(os.path.join(EVID, f"{tag}_{name}"))


def step(p, m, frames, btns):
    p.core.run(frames, btns)


def walk_to(p, m, lo, hi, budget=3600, face=None):
    """Walk (frozen) until px in [lo, hi]; hop when stuck."""
    stuck = 0
    for _ in range(budget):
        x = px_of(m)
        if lo <= x <= hi:
            return x
        btns = {face} if face else set()
        if x > hi:
            btns = {"LEFT"}
        elif x < lo:
            btns = {"RIGHT"}
        if stuck > 40:
            btns.add("B")
        step(p, m, 1, btns)
        nx = px_of(m)
        stuck = stuck + 1 if abs(nx - x) < 0.3 else 0
    return px_of(m)


class RainPoll:
    """Falling-faller census via slot height deltas (h @ +0x7E)."""

    def __init__(self, m):
        self.m = m
        self.prev = {s: self._words(s) for s in range(40)}
        self.events = []

    def _words(self, s):
        base = 0x0CA268 + s * 0x14C    # TABLE + STRIDE (gate probe)
        return [int(self.m.u16(base + 2 * k)) for k in range(0x150 // 2)]

    def poll(self, tag):
        evs = 0
        for s in range(1, 40):
            w = self._words(s)
            h, hp = w[63], w[71]
            ph = self.prev[s][63]
            if hp and 0 < ph - h <= 20 and h > 60 and ph > 70:
                evs += 1
                self.events.append({"tag": tag, "slot": s, "h": h,
                                    "f": int(self.m.u32(0x0CA2E0))})
            self.prev[s] = w
        return evs


def lob_campaign(p, m, rain, tag, cycles=60, tracef=None):
    """LEFT-facing grenade volley until the +800&0x20 signature."""
    score0 = int(m.u16(gp.A_SCORE))
    last = score0
    killed = False
    for k in range(cycles * 80):
        gren = int(m.u8(GRENADES))
        if gren == 0:
            log(f"[{tag}] out of grenades at k={k}")
            break
        cyc = k % 80
        btns = ({"A"} if cyc < 8 else ({"LEFT"} if cyc < 24 else set()))
        step(p, m, 1, btns)
        rain.poll(tag)
        now = int(m.u16(gp.A_SCORE))
        delta = (now - last) & 0xFFFF
        if delta and tracef:
            tracef.write(json.dumps(
                {"type": "score_event", "k": k, "delta": delta,
                 "score": now, "f": int(p.core.frames_run)}) + "\n")
        last = now
        total = (now - score0) & 0xFFFF
        if (total >= 800 and (total & 0xFF) == 32) or \
                (total >= 1100 and (total & 0xFF) == 76):
            killed = True
            log(f"[{tag}] MOSQUE KILL signature: total={total} "
                f"score={now} f={p.core.frames_run}")
            png(p, tag, "mosque_kill.png")
            break
        if k % 400 == 0:
            log(f"[{tag}] lob k={k} score={now} gren={gren} "
                f"px={px_of(m):.0f}")
    return killed, int(m.u16(gp.A_SCORE)) - score0


def pin_test(p, m, tag, chunks=15):
    """Hold RIGHT from the window; return max px (pin still at 1163?)."""
    max_px = px_of(m)
    rows = []
    for _c in range(chunks):
        for _k in range(6):
            step(p, m, 10, {"RIGHT"})
        px = px_of(m)
        max_px = max(max_px, px)
        rows.append({"f": int(p.core.frames_run), "px": px})
    log(f"[{tag}] pin test: max_px={max_px}")
    return max_px, rows


def run_arm(p, m, tag, do_kill, tracef):
    rain = RainPoll(m)
    # 1) load clamp0, verify the pin
    p.load_state("clamp0")
    for _ in range(10):
        p.core.run(1, set())
    session = gp.freeze_now(p, f"gatetest_{tag}")
    pin0, _ = pin_test(p, m, tag + "_verify", chunks=4)
    log(f"[{tag}] pre-arm pin check: px={pin0} (expect ~1163)")
    # 2) walk LEFT to the lob spot
    x = walk_to(p, m, LOB_SPOT_LO, LOB_SPOT_HI, face=None)
    log(f"[{tag}] at lob spot px={x} gren={int(m.u8(GRENADES))}")
    # grenade top-up from the ~726 pile if short
    if int(m.u8(GRENADES)) < 4:
        walk_to(p, m, 700.0, 760.0)
        for _ in range(240):
            step(p, m, 1, set())
            if int(m.u8(GRENADES)) >= 4:
                break
        log(f"[{tag}] top-up gren={int(m.u8(GRENADES))}")
    # 3) optional volley
    killed, score_delta = False, 0
    if do_kill:
        killed, score_delta = lob_campaign(p, m, rain, tag,
                                           tracef=tracef)
    rain_after_kill = rain.poll(tag + "_after")
    # 4) walk right and test the pin
    x2 = walk_to(p, m, 900.0, 1000.0)
    max_px, rows = pin_test(p, m, tag)
    gp.unfreeze(session, f"gatetest_{tag}")
    rep = {"tag": tag, "killed": killed, "score_delta": score_delta,
           "pin_at_verify": pin0, "lob_px": x, "back_px": x2,
           "max_px": max_px, "pin_lifted": max_px > PIN_LIMIT,
           "rain_events": len(rain.events),
           "rain_after_kill": rain_after_kill,
           "grenades_end": int(m.u8(GRENADES)),
           "rows": rows}
    with open(os.path.join(EVID, f"report_{tag}.json"), "w") as f:
        json.dump(rep, f, indent=1)
    log(f"[{tag}] RESULT killed={killed} max_px={max_px} "
        f"pin_lifted={rep['pin_lifted']} rain={len(rain.events)}")
    return rep


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--chunks", type=int, default=15)
    args = ap.parse_args()
    os.makedirs(EVID, exist_ok=True)
    p, fwmode = boot()
    m = p.mem
    out = {"schema": "ps1play-mosque-gate/1", "fw": fwmode,
           "pin_limit": PIN_LIMIT, "arms": []}
    for tag, do_kill in (("kill", True), ("control", False)):
        tf = open(os.path.join(EVID, f"trace_{tag}.jsonl"), "w")
        try:
            out["arms"].append(run_arm(p, m, tag, do_kill, tf))
        finally:
            tf.close()
    with open(os.path.join(EVID, "report.json"), "w") as f:
        json.dump(out, f, indent=1)
    for a in out["arms"]:
        log(f"SUMMARY {a['tag']}: killed={a['killed']} "
            f"max_px={a['max_px']} pin_lifted={a['pin_lifted']} "
            f"rain_events={a['rain_events']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
