#!/usr/bin/env python3
"""psxmc_probe.py — live verification of the PSX-Minecraft player/world
state, source-first (MIT EngineersBox/PSX-Minecraft, release infdev
2025-04-18 map symbols) + input-causality confirmed (Tetrade method).

Map anchors (PSXMC.map, RAM offset = VA & 0x1FFFFF):
  player      0x3C608 (Player*)     world      0x3C61C (World*)
  minecraft   0x3C62C               time_ms    0x3C5A0
Struct candidate (source-derived, gcc MIPS layout):
  P+0x00 position VECTOR (i32 x3)   P+0x0C velocity
  P+0x18 rot.pitch P+0x1C yaw       P+0x20 fwd P+0x22 strafe (i16)
  P+0x2C aabb.min P+0x38 aabb.max   P+0x4C flags u16
  P+0x50 alive u8  P+0x51..53 health/armour/air bitfield bytes
  P+0x54 on_fire u16                P+0x58 camera*
  P+0x5C inventory IUI (8B)  P+0x64 hotbar IUI (8B)  P+0x6C breaking
Camera C=*camera: C+0x04 pos, C+0x10 rot, C+0x1C dir, C+0x28 mode

Bindings (bindings.c): move=dpad, jump=R1, crouch=L1,
look=TRI(up)/X(down)/SQ(left)/O(right), attack=R2, use/place=L2,
inventory=START, hotbar prev/next=L3/R3, pause=SELECT.

Evidence: /home/z/my-project/emu/games_psx/evidence/psxmc_probe/
Local only. One boot per process (H5).
"""
import json
import os
import sys
import time

import numpy as np

REPO = "/home/z/my-project/ps1ai"
sys.path.insert(0, REPO)

from ps1play.api import PS1Play                                   # noqa

EVID = "/home/z/my-project/emu/games_psx/evidence/psxmc_probe"
os.makedirs(EVID, exist_ok=True)

CUE = "/home/z/my-project/emu/games_homebrew/patched/PSXMC_lic.cue"
A_PLAYER = 0x3C608
A_WORLD = 0x3C61C
A_MC = 0x3C62C
A_TIME = 0x3C5A0


def s32(v):
    v &= 0xFFFFFFFF
    return v - 0x100000000 if v >= 0x80000000 else v


def s16(v):
    v &= 0xFFFF
    return v - 0x10000 if v >= 0x8000 else v


def player_ptr(m):
    return m.u32(A_PLAYER)


def read_player(m):
    P = player_ptr(m)
    if not P or P < 0x100000:
        return None
    P &= 0x1FFFFF
    b = m.u8
    return {
        "P": P,
        "pos": [m.u32(P), m.u32(P + 4), m.u32(P + 8)],
        "vel": [m.u32(P + 0xC), m.u32(P + 0x10), m.u32(P + 0x14)],
        "pitch": s32(m.u32(P + 0x18)),
        "yaw": s32(m.u32(P + 0x1C)),
        "fwd": s16(m.u16(P + 0x20)),
        "strafe": s16(m.u16(P + 0x22)),
        "flags_u16": m.u16(P + 0x4C),
        "alive": b(P + 0x50) & 1,
        "bf_bytes": [b(P + 0x51), b(P + 0x52), b(P + 0x53)],
        "on_fire": m.u16(P + 0x54),
        "camera": m.u32(P + 0x58),
        "hotbar_self": m.u32(P + 0x68),
        "breaking_hash": bytes(m.snapshot()[P + 0x6C:P + 0x8C]).hex()[:32],
    }


def read_camera(m, cam):
    if not cam or cam < 0x100000:
        return None
    C = cam & 0x1FFFFF
    return {"C": C,
            "pos": [m.u32(C + 4), m.u32(C + 8), m.u32(C + 0xC)],
            "rot": [s32(m.u32(C + 0x10)), s32(m.u32(C + 0x14)),
                    s32(m.u32(C + 0x18))],
            "dir": [s32(m.u32(C + 0x1C)), s32(m.u32(C + 0x20)),
                    s32(m.u32(C + 0x24))],
            "mode": m.u32(C + 0x28)}


def frame_diff(a, b):
    if a is None or b is None:
        return None
    return float(np.abs(a.astype(np.int16) - b.astype(np.int16)).mean())


def main():
    out = {"started": time.strftime("%FT%TZ", time.gmtime())}
    p = PS1Play(CUE, workspace="/home/z/my-project/emu/games_psx/ws_psxmc_probe")
    p.boot()
    out["boot_serial"] = p.core.serial if hasattr(p.core, "serial") else None

    # ---- wait for world: player pointer live + non-zero position ------
    st = None
    for _ in range(240):                     # up to ~240x30f
        st = read_player(p.mem)
        if st and st["pos"][0] | st["pos"][1] | st["pos"][2]:
            break
        p.wait(30)
    if not st:
        out["verdict"] = "NO_PLAYER_POINTER"
        print(json.dumps(out, indent=1))
        return 1
    out["world_ready_after_f"] = p.core.frames_run
    out["state0"] = st
    out["camera0"] = read_camera(p.mem, st["camera"])
    out["world_ptr"] = hex(p.mem.u32(A_WORLD) & 0x1FFFFF)
    out["time_ms"] = p.mem.u32(A_TIME)
    p.core.frame_rgb() if False else None
    from PIL import Image
    img0 = p.core.frame_rgb()
    if img0 is not None:
        Image.fromarray(img0).save(f"{EVID}/world_ready.png")

    def probe(label, btns, frames, watch="pos"):
        """Run input, capture state before/after, return deltas."""
        s0 = read_player(p.mem)
        c0 = read_camera(p.mem, s0["camera"]) if s0 else None
        f0 = p.core.frame_rgb()
        p.core.run(frames, btns)
        s1 = read_player(p.mem)
        c1 = read_camera(p.mem, s1["camera"]) if s1 else None
        f1 = p.core.frame_rgb()
        d = {"label": label, "btns": sorted(btns), "frames": frames}
        if s0 and s1:
            d["d_pos"] = [s1["pos"][i] - s0["pos"][i] for i in range(3)]
            d["d_fwd"] = s1["fwd"] - s0["fwd"]
            d["d_strafe"] = s1["strafe"] - s0["strafe"]
            d["d_yaw"] = s1["yaw"] - s0["yaw"]
            d["flags1"] = s1["flags_u16"]
            d["flags0"] = s0["flags_u16"]
            d["breaking_changed"] = s1["breaking_hash"] != s0["breaking_hash"]
        if c0 and c1:
            d["d_cam_rot"] = [c1["rot"][i] - c0["rot"][i] for i in range(3)]
            d["d_cam_pos"] = [c1["pos"][i] - c0["pos"][i] for i in range(3)]
        d["diff_frame"] = frame_diff(f0, f1)
        if f1 is not None:
            Image.fromarray(f1).save(f"{EVID}/after_{label}.png")
        out.setdefault("probes", []).append(d)
        print(label, "->", {k: v for k, v in d.items()
                            if k.startswith(("d_", "breaking"))})
        return d

    # settle tail after world-ready (initial spawn physics)
    p.wait(120)

    # ---- movement causality (dpad = move) -----------------------------
    probe("fwd", {"UP"}, 90)
    probe("fwd2", {"UP"}, 90)
    probe("back", {"DOWN"}, 60)
    probe("left", {"LEFT"}, 60)
    probe("right", {"RIGHT"}, 60)
    # ---- look causality (SQ left / O right / TRI up / X down) ---------
    probe("look_left", {"SQ"}, 45)
    probe("look_right", {"O"}, 45)
    probe("look_up", {"TR"}, 30)
    probe("look_down", {"X"}, 30)
    # ---- jump causality (R1) ------------------------------------------
    probe("jump", {"R1"}, 45)
    # ---- attack/break causality (R2) — hold on whatever is ahead ------
    probe("attack", {"R2"}, 90)
    probe("attack2", {"R2"}, 90)
    # ---- use/place causality (L2) --------------------------------------
    probe("use", {"L2"}, 90)
    # ---- hotbar cycling (L3/R3) ----------------------------------------
    probe("hotbar_next", {"R3"}, 30)
    # ---- pause (SELECT) --------------------------------------------------
    probe("pause", {"SELECT"}, 30)
    probe("unpause", {"SELECT"}, 30)

    final = read_player(p.mem)
    out["state_final"] = final
    out["camera_final"] = read_camera(p.mem, final["camera"])
    out["verdict"] = "PROBED"
    out["finished"] = time.strftime("%FT%TZ", time.gmtime())
    with open(f"{EVID}/probe_report.json", "w") as f:
        json.dump(out, f, indent=1, default=str)
    print("VERDICT:", out["verdict"])
    try:
        p.core.close()
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
