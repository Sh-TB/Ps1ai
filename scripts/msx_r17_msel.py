#!/usr/bin/env python3
"""msx_r17_msel.py — Round 17 Track C: LIVE mission-select navigation (first probe).

Round-12 static finding: the real M3 gate is a MENU — 17-entry descriptor
table 0x80095ef4, state machine 0x8007exxx, states byte 0x80095a7d, handler
tables 0x80095a70/5a84/5b24, per-mission sequencer files MISS01..MISS16.BIN.
This probe drives the real menus from a fresh boot and records the states
byte + table words at every rung, with PNGs:

  1. boot -> idle strip (PNG every 600 f up to ~4,800 f): what screens pass.
  2. START-hold60 -> settle 900 -> PNG + RAM (repeat up to 4 rungs or until
     a screen where UP/DOWN changes RAM — the selector).
  3. At the first selector-like screen: UP/DOWN census (which words move),
     PNG per rung, checkpoint saved.
  4. Cursor rung = select the mission-2 slot, confirm with START then CROSS
     (both probed once, PNG after each), observe 2,400 f for the M2 spawn
     signature (px 76.4 / php 120 / banner) — the honest verdict comes from
     the PNGs + px telemetry, never from the intent.

One beetle boot per process. No RAM writes. Evidence: scratch/round17_msx/mselect/.
"""
from __future__ import annotations

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

from ps1play.api import PS1Play                                   # noqa: E402

EVID = "/home/z/my-project/ps1ai/scratch/round17_msx/mselect"
CUE = "/tmp/my-project/emu/game/Metal Slug X (USA).cue"
if not os.path.exists(CUE):
    CUE = "/home/z/my-project/emu/game/Metal Slug X (USA).cue"
WS = "/tmp/my-project/emu/ws_r17_msel"

STATES_BYTE = 0x80095A7D
TABLE = 0x80095EF4
PLAYER_X = 0x0CA2E0
PLAYER_HP = 0x0CA2F6
A_SCORE = 0x0EE318

TABLE_WORDS = [0x00095EF4 + 4 * i for i in range(18)]   # RAM offsets (0x80000000-based minus base)
RAM_BASE = 0x80000000


def off(a):
    return a - RAM_BASE


def log(*a):
    print("[r17-msel]", *a, file=sys.stderr, flush=True)


def snap(p, name):
    img = p.core.frame_rgb()
    if img is not None:
        Image.fromarray(img).save(os.path.join(EVID, name))
    return img


def ram_words(p):
    m = p.mem
    out = {"states_byte": int(m.u8(off(STATES_BYTE)))}
    out["table"] = [int(m.u32(a)) for a in TABLE_WORDS[:18]]
    px = int(m.u32(PLAYER_X))
    if px >= 0x80000000:
        px -= 0x100000000
    out["px"] = px / 65536.0
    out["php"] = int(m.u16(PLAYER_HP))
    out["score"] = int(m.u32(A_SCORE))
    return out


def main():
    os.makedirs(EVID, exist_ok=True)
    out = {"started": time.strftime("%FT%TZ", time.gmtime())}
    p = PS1Play(CUE, workspace=WS)
    p.boot()
    p.wait(120)

    # ---- phase 1: idle strip ----
    for i in range(8):
        p.core.run(600, set())
        snap(p, f"idle_{(i + 1) * 600}.png")
        out[f"idle_{(i + 1) * 600}"] = ram_words(p)
        log(f"idle {(i + 1) * 600} states={out[f'idle_{(i + 1) * 600}']['states_byte']:#x} px={out[f'idle_{(i + 1) * 600}']['px']}")

    # ---- phase 2: START rungs ----
    for r in range(4):
        p.core.run(60, {"START"})
        p.core.run(900, set())
        snap(p, f"start_rung{r}.png")
        out[f"start_rung{r}"] = ram_words(p)
        w = out[f"start_rung{r}"]
        log(f"start rung {r}: states={w['states_byte']:#x} px={w['px']} score={w['score']}")

    # ---- phase 3: selector census at the last rung state ----
    ck = "msel_r17_base"
    p.save_state(ck)
    base_words = ram_words(p)
    probes = {}
    for name, btns in (("none", set()), ("up", {"UP"}), ("down", {"DOWN"}),
                       ("up2", {"UP", "UP"})):
        p.load_state(ck)
        p.core.run(120, set())
        p.core.run(30, btns)
        p.core.run(240, set())
        snap(p, f"census_{name}.png")
        probes[name] = ram_words(p)
    # which table words / bytes differ across up/down
    diffs = {}
    for name in ("up", "down", "up2"):
        d = [i for i, (a, b) in enumerate(zip(base_words["table"],
                                              probes[name]["table"])) if a != b]
        diffs[name] = {
            "table_idx_changed": d,
            "states_byte": (base_words["states_byte"], probes[name]["states_byte"]),
            "differs_from_base": (probes[name]["table"] != base_words["table"]),
        }
    out["census"] = diffs
    out["base_words"] = base_words
    log("census:", json.dumps(diffs))

    # ---- phase 4: pick a selector rung (up2) and confirm with START/CROSS ----
    p.load_state(ck)
    p.core.run(120, set())
    p.core.run(30, {"UP", "UP"})
    p.core.run(240, set())
    snap(p, "sel_cursor.png")
    p.save_state("msel_r17_cursor")

    for lbl, btn in (("confirm_start", {"START"}), ("confirm_cross", {"B"})):
        p.load_state("msel_r17_cursor")
        p.core.run(30, btn)
        p.core.run(2400, set())
        snap(p, f"{lbl}.png")
        out[lbl] = ram_words(p)
        log(f"{lbl}: states={out[lbl]['states_byte']:#x} px={out[lbl]['px']} php={out[lbl]['php']} score={out[lbl]['score']}")

    out["finished"] = time.strftime("%FT%TZ", time.gmtime())
    with open(os.path.join(EVID, "msel_report.json"), "w") as f:
        json.dump(out, f, indent=1, default=str)
    return 0


if __name__ == "__main__":
    sys.exit(main())
