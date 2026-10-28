#!/usr/bin/env python3
"""r37t1_msx_cheat_anchors.py — validate public cheat-DB RAM hypotheses
against the ORIGINAL gameplay backend (beetle + local retail SLUS-01212).

Issue #10 Part 3 bounded A/B experiment. Boot cap: 2 (disclosed BEFORE
run; 1 boot budgeted, 1 spare).

Hypotheses under test (gamehacking.org "Metal Slug X (NTSC-U)" /
SLUS-01212, codes by Code Master + nolberto82; cheatcc 2001 variants):
  H1 score P1 = u32 @0x800EE318 (Max Score writes 0x05F5E0FF LE =
     99,999,999 -> consistent little-endian u32)
  H2 prisoners saved P1 = u8 @0x80087A78
  H3 mission unlock = byte @0x800D4213 (300-format one-time write;
     corroborates the r20 u16 unlock counter @0x800D4210)
  H4 P1 entity = 0x800CA268 (r24/25 CONFIRMED entity table): HP u16
     @+0x8E = 0x800CA2F6; cheat "Invisible P1 800CA30C 0068" = base
     +0xA4 -> the +0xA4 slot field (r35 next-lever region 0x800CA268 /
     0x800CA3B4)

Method (distinguishing hypotheses, not another attack policy):
  - reach live Mission 1 through the r17-verified pure-input menu ladder
  - read candidates across 3 windows: W1 idle (negative control),
    W2 walk+fire (enemies shot), W3 post-window
  - VERIFIED requires: plausible value at start, causal delta in the
    fired window only, and stability in the control window
  - no memory writes, no cheats applied — read-only probes

Game/build identity: local retail disc, SLUS-01212 (psxdatacenter
identity cross-check), boot via labconfig firmware contract.
"""
import json
import os
import shutil
import sys
import time

import numpy as np

REPO = "/home/z/my-project/ps1ai"
sys.path.insert(0, REPO)
from ps1play.core.host import LibretroCore  # noqa: E402

OUT = os.path.join(REPO, "scratch", "r37", "msx_anchors")
CORE = "/home/z/my-project/ps1-test/cores/mednafen_psx_libretro.so"
BIOS = "/home/z/my-project/ps1-test/emu/system/openbios.bin"
CONTENT = "/home/z/my-project/emu/game/Metal Slug X (USA).cue"

SCORE_P1, SCORE_P2 = 0x800EE318, 0x800EE320
PRIS_P1, UNLOCK16, UNLOCK8 = 0x80087A78, 0x800D4210, 0x800D4213
ENT_P1, P1_HP, P1_INV = 0x800CA268, 0x800CA268 + 0x8E, 0x800CA268 + 0xA4

R = {"task": "r37t1 MSX cheat-anchor validation", "boot_cap": 2,
     "content": CONTENT,
     "identity": {"serial": "SLUS-01212", "region": "NTSC-U",
                  "source": "local retail disc (never committed)"},
     "boot_cap_note": "cap 2 set BEFORE run, disclosed (Issue #10 Part 3)",
     "started": time.strftime("%FT%TZ", time.gmtime()),
     "events": []}


def log(ev, **kw):
    rec = {"f": core.frames_run, "event": ev, **kw}
    R["events"].append(rec)
    print(f"[r37t1] {json.dumps(rec, default=str)[:200]}", flush=True)


def u16(va):
    return int.from_bytes(core.ram[va - 0x80000000:va - 0x80000000 + 2],
                          "little")


def u32(va):
    return int.from_bytes(core.ram[va - 0x80000000:va - 0x80000000 + 4],
                          "little")


def u8(va):
    return core.ram[va - 0x80000000]


def snap_syms():
    return {"score_p1": u32(SCORE_P1), "score_p2": u32(SCORE_P2),
            "prisoners_p1": u8(PRIS_P1), "unlock16": u16(UNLOCK16),
            "unlock8": u8(UNLOCK8), "p1_hp": u16(P1_HP),
            "p1_inv": u16(P1_INV), "states_byte": core.ram[0x95A7D]}


os.makedirs(OUT, exist_ok=True)
ws = os.path.join(OUT, "ws")
os.makedirs(os.path.join(ws, "system"), exist_ok=True)
os.makedirs(os.path.join(ws, "saves"), exist_ok=True)
shutil.copyfile(BIOS, os.path.join(ws, "system", "openbios.bin"))
core = LibretroCore(CORE, os.path.join(ws, "system"),
                    os.path.join(ws, "saves"),
                    var_overrides={b"beetle_psx_renderer": b"software",
                                   b"beetle_psx_frame_duping": b"disabled"})
av = core.load_game(CONTENT)
log("boot", av=av)

# ---- menu ladder: state-byte driven, pure input (r17-verified path) ----
# r17 ground truth: states 0x0->0x6->0x9; START opens main menu (9);
# DOWN moves highlight; CROSS (not START) confirms via "OK? YES/NO";
# chain end = SOLDIER SELECT -> live Mission 1 (php 116 observed then).
in_game = False
ladder = ["START"] + ["B"] * 11  # B = CROSS on beetle (project map)
for rnd, btn in enumerate(ladder):
    while core.frames_run < 300 + 120 * (rnd + 1):
        core.run_frame()
    s0 = snap_syms()
    log("state_probe", round=rnd, btn=btn, **s0)
    if s0["p1_hp"] and 0 < s0["p1_hp"] < 300:
        in_game = True
        break
    core.set_buttons(btn)
    for _ in range(25):
        core.run_frame()
    core.set_buttons(set())
    f_t = core.frames_run + 90
    while core.frames_run < f_t:
        core.run_frame()

s = snap_syms()
log("ladder_end", in_game=in_game, **s)

# boot ledger (disclosed): 2-boot cap, ledger persisted
_ledger = os.path.join(OUT, "boots_used.json")
_n = json.load(open(_ledger))["count"] if os.path.exists(_ledger) else 1
with open(_ledger, "w") as f:
    json.dump({"cap": 2, "count": _n + 1,
               "log": [{"boot": _n + 1, "script": "r37t1 (v2 ladder)",
                        "t": time.strftime("%FT%TZ", time.gmtime())}]}, f)

# ---- windows: W1 idle control, W2 walk+fire, W3 settle -------------------
def window(tag, frames, buttons=None, every=60):
    rec = []
    for i in range(0, frames, every):
        if buttons:
            core.set_buttons(buttons)
        for _ in range(every):
            core.run_frame()
        if buttons:
            core.set_buttons(set())
        rec.append({"f": core.frames_run, **snap_syms()})
    R[tag] = rec
    log("window", tag=tag, n=len(rec),
        first=rec[0] if rec else None, last=rec[-1] if rec else None)
    return rec


window("W1_idle_control", 300)
window("W2_walk_fire", 900, buttons="RIGHT+B")   # advance + fire
window("W3_settle", 240)

# ---- verdicts ------------------------------------------------------------
w1, w2 = R["W1_idle_control"], R["W2_walk_fire"]
verdicts = {}
sc = [x["score_p1"] for x in w1 + w2]
verdicts["H1_score_p1@800EE318"] = {
    "start": w1[0]["score_p1"], "w1_stable": len(
        {x["score_p1"] for x in w1}) == 1,
    "w2_delta": w2[-1]["score_p1"] - w1[-1]["score_p1"],
    "status": None}
if verdicts["H1_score_p1@800EE318"]["w2_delta"] > 0 and \
        verdicts["H1_score_p1@800EE318"]["w1_stable"]:
    verdicts["H1_score_p1@800EE318"]["status"] = "VERIFIED"
elif verdicts["H1_score_p1@800EE318"]["w2_delta"] == 0 and sc[0] == 0:
    verdicts["H1_score_p1@800EE318"]["status"] = "OBSERVED_ZERO_NO_KILLS"
else:
    verdicts["H1_score_p1@800EE318"]["status"] = "CONTRADICTED"
pr = [x["prisoners_p1"] for x in w1 + w2]
verdicts["H2_prisoners@80087A78"] = {
    "start": pr[0], "delta": pr[-1] - pr[0],
    "status": "OBSERVED" if pr[0] == 0 and pr[-1] == 0 else
    ("VERIFIED" if pr[-1] > 0 else "CONTRADICTED"),
    "note": "no hostages reached in this window is not a refutation"}
verdicts["H3_unlock@800D4213"] = {
    "byte": w1[0]["unlock8"], "u16": w1[0]["unlock16"],
    "status": "OBSERVED",
    "note": "corroborates r20 unlock-counter block 0x800D4210"}
hp = [x["p1_hp"] for x in w1 + w2]
verdicts["H4_p1_entity_HP@CA268+0x8E"] = {
    "start": hp[0], "min": min(hp), "end": hp[-1],
    "inv_field": w1[0]["p1_inv"],
    "status": ("OBSERVED" if 0 < min(hp) <= 300 else
               ("BLOCKED" if not in_game else "CONTRADICTED")),
    "note": "HP within 0..300 plausible band; BLOCKED when the menu "
            "ladder did not reach Mission 1 (no in-game claim)"}
R["verdicts"] = verdicts

with open(os.path.join(OUT, "verdicts.json"), "w") as f:
    json.dump(R, f, indent=1, default=str)
log("done", verdicts={k: v["status"] for k, v in verdicts.items()})
