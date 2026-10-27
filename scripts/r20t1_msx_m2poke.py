#!/usr/bin/env python3
"""r20t1_msx_m2poke.py — Mission-2 entry via u16 poke (task r20-t1).

R19 context: r19-t2 expC poked mission_var=1 -> game entered Mission 1
(banner "1-1") falsifying 0-based indexing. r20-t1 tests mission=2
(1-based hypothesis) with the same mechanism: hardware-cadence GameShark
freeze re-poke active across the whole menu->loading->spawn window.

Targets (whole mission/unlock block, all bytes = VAL):
  800D4210 00VV   u16 "missions unlocked" (menu readers @0x80016270/378/64C:
                  slti v0,<2 skip; clamp-loop item<count)
  800D4212 VVVV   u16 covering GS "Unlock Another Mission" byte 0x0D4213;
                  game itself writes 0xFFFF there at 0x8002DD8C (unlock-all)

Static RE (this session, SLUS_012.12 @0x80010000): u16@0x800D4210 has ONLY
4 readers (0x80016270, 0x80016378, 0x8001664C lh; 0x80016500 lbu), all in
the menu cluster; u16@0x800D4212 one writer (sh 0xFFFF @0x8002DD8C).

Ladder (r17 choreography, psx_headless-derived): START taps 1000..5300
every 300f + confirm 5150; codes ticked EVERY frame from boot (hardware GS
cadence). Gameplay gate: flags_word u32@0xEE518==0xFF AND score
u32@0x0EE318==0 (attract demo shows score 1600, real spawn is 0).
"""
import json
import os
import struct
import sys
import time

import numpy as np

_REPO = "/home/z/my-project/ps1ai"
for _p in (_REPO, os.path.join(_REPO, "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from ps1play import labconfig                              # noqa: E402
from ps1play.api import PS1Play                            # noqa: E402
from ps1play.agent.gameshark import GameShark, GSCode      # noqa: E402

OUT = "/home/z/my-project/scratch/r20t1_msx"
VAL = int(os.environ.get("M2_VALUE", "2"))       # run1: 2; fallback run2: 3
MAX_EXTRA = 9000                                 # frames after tap ladder

LOG = []


def log(ev, **kw):
    rec = {"t": round(time.time() - T0, 1), "event": ev, **kw}
    LOG.append(rec)
    print(f"[r20t1] {json.dumps(rec, default=str)[:300]}", flush=True)


def png(p, name):
    try:
        os.makedirs(OUT, exist_ok=True)
        from PIL import Image
        rgb = p.core.frame_rgb()
        if rgb is not None:
            Image.fromarray(rgb).save(os.path.join(OUT, name))
            return name
    except Exception as e:
        log("png_fail", name=name, err=str(e))
    return None


def ticked_run(p, gs, frames, buttons):
    """core.run with a per-frame GS tick (hardware cadence)."""
    p.core.set_buttons(set(buttons))
    for _ in range(frames):
        p.core.run_frame()
        gs.tick()
    p._advance()


def patch_core_run(p, gs):
    """Route EVERY core.run through the per-frame GS tick so the poke
    keeps hardware cadence inside enter_gameplay3's adaptive nav."""
    core = p.core

    def run(frames, buttons=(), _orig=core.run):
        ticked_run(p, gs, frames, set(buttons))
    core.run = run


def metrics(p):
    m = p.mem
    raw = bytes(m.ram[0xCA268:0xCA268 + 0x150])     # entity[0] struct
    fl = []
    for off in range(0, 0x150 - 3, 4):
        f = struct.unpack("<f", raw[off:off + 4])[0]
        if 0.5 < abs(f) < 5000.0:
            fl.append([hex(0xCA268 + off), round(f, 3)])
    return {
        "flags_word_0xEE518": int(m.u32(0xEE518)),
        "score_u32_0x0EE318": int(m.u32(0x0EE318)),
        "hp_u16_0x032764": int(m.u16(0x032764)),
        "e0_hp_u16_0xCA2F6": int(m.u16(0xCA2F6)),
        "mission_block_0x0D4210":
            bytes(m.ram[0x0D4210:0x0D4218]).hex(),
        "pad_mirror_u16_0x0D4948": int(m.u16(0x0D4948)),
        "entity0_floats": fl[:24],
    }


T0 = time.time()


def main():
    game = labconfig.resolve_path("game")
    ws = labconfig.resolve_path("workspace")
    fw = labconfig.resolve_firmware(
        os.environ.get("M1_FIRMWARE", "openbios"), ws)
    kw = {}
    core = labconfig.resolve_path("core")
    if core:
        kw["core"] = core
    if ws:
        kw["workspace"] = ws
    if fw["override_vars"]:
        kw["var_overrides"] = fw["override_vars"]

    p = PS1Play(game, states_dir=os.path.join(OUT, "states"), **kw)
    info = p.boot()
    log("boot", **{k: info.get(k) for k in
                   ("core", "serial", "plugin", "ram_bytes")})
    fw_ev = labconfig.firmware_log_evidence(
        getattr(p.core, "log_history", []))
    ok, detail = labconfig.check_firmware_trust(fw, fw_ev)
    log("firmware", ok=ok, detail=str(detail)[:120])
    if not ok:
        json.dump({"verdict": "BLOCKED", "why": f"firmware: {detail}"},
                  open(os.path.join(OUT, "report.json"), "w"), indent=1)
        return

    gs = GameShark(p.mem)
    codes = [GSCode(f"800D4210 {VAL:04X}"),
             GSCode(f"800D4212 {(VAL << 8) | VAL:04X}")]
    gs.enable("m2poke", codes)
    log("codes_on", val=VAL, codes=[c.raw for c in codes])
    patch_core_run(p, gs)

    # adaptive nav (r17/r19 ladder) with codes ticked every frame
    nav = p.enter_gameplay3()
    log("enter_gameplay3", **{k: nav.get(k) for k in
                              ("in_game", "steps", "screen")})
    f = int(p.core.frames_run)

    # wait for real gameplay: flags 0xFF AND score==0 (demo shows 1600)
    live = False
    first_ff = None
    deadline = f + MAX_EXTRA
    while f < deadline:
        ticked_run(p, gs, 30, set())
        f += 30
        flags = int(p.mem.u32(0xEE518))
        score = int(p.mem.u32(0x0EE318))
        if flags == 0xFF and first_ff is None:
            first_ff = f
            log("first_flags_ff", frame=f, score=score)
        if flags == 0xFF and first_ff is not None and f - first_ff >= 180:
            if score == 0:
                live = True
                log("LIVE", frame=f, wall=round(time.time() - T0, 1))
                break
            if f - first_ff > 1800:
                log("ff_but_score_nonzero_giveup", score=score)
                break
        if flags != 0xFF and first_ff is not None:
            first_ff = None                      # transient; re-arm
    png(p, f"spawn_a_f{f}.png")
    ticked_run(p, gs, 180, set())
    f += 180
    png(p, f"spawn_b_f{f}.png")
    m_live = metrics(p)
    log("metrics_codes_on", **m_live)

    gs.disable("m2poke")
    ticked_run(p, gs, 300, set())
    f += 300
    m_after = metrics(p)
    png(p, f"final_f{f}.png")
    log("metrics_codes_off", **m_after)

    report = {
        "task": "r20-t1", "game": "Metal Slug X (USA) SLUS-01212",
        "poke_value": VAL,
        "codes": ["800D4210 0002" if VAL == 2 else f"800D4210 {VAL:04X}",
                  f"800D4212 {VAL:02X}{VAL:02X}"],
        "mechanism": "GS freeze re-poke every frame from boot through spawn",
        "firmware": fw["mode"] if isinstance(fw, dict) else str(fw),
        "live_gameplay": live, "first_flags_ff_frame": first_ff,
        "frames_total": f, "wall_seconds": round(time.time() - T0, 1),
        "metrics_codes_on": m_live, "metrics_codes_off": m_after,
        "log": LOG,
    }
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "run.json"), "w") as fh:
        json.dump(report, fh, indent=1, default=str)
    print("[r20t1] live=", live, "wall=", round(time.time() - T0, 1))


if __name__ == "__main__":
    main()
