#!/usr/bin/env python3
"""psxmc_probe2.py — resolve the remaining PSX-Minecraft struct facts
live: (1) the REAL Camera object (diff-hunt through Player-held
pointers while looking), (2) BreakingState during a dig, (3) hotbar
impl bytes during use/place. Source-first offsets from
MIT EngineersBox/PSX-Minecraft; everything else measured.

One boot per process (H5). Evidence: emu/games_psx/evidence/psxmc_probe/
"""
import json
import os
import sys
import time

REPO = "/home/z/my-project/ps1ai"
sys.path.insert(0, REPO)

from ps1play.api import PS1Play                                   # noqa

EVID = "/home/z/my-project/emu/games_psx/evidence/psxmc_probe"
os.makedirs(EVID, exist_ok=True)
CUE = "/home/z/my-project/emu/games_homebrew/patched/PSXMC_lic.cue"
A_PLAYER = 0x3C608
ONE_BLOCK = 286720                                 # source: ONE*BLOCK_SIZE


def u(m, a):
    return m.u32(a & 0x1FFFFF)


def dump(m, a, n):
    return bytes(m.snapshot()[(a & 0x1FFFFF):(a & 0x1FFFFF) + n])


def diff_regs(a0, b0, a1, b1):
    """Changed 4-byte words between two dumps."""
    out = []
    for i in range(0, min(len(b0), len(b1)) - 3, 4):
        if b0[i:i + 4] != b1[i:i + 4]:
            out.append((a0 + i, b0[i:i + 4].hex(), b1[i:i + 4].hex()))
    return out


def main():
    out = {"started": time.strftime("%FT%TZ", time.gmtime())}
    p = PS1Play(CUE, workspace="/home/z/my-project/emu/games_psx/ws_psxmc_probe2")
    p.boot()
    P = None
    for _ in range(240):
        v = u(p.mem, A_PLAYER)
        y = p.mem.u32((v & 0x1FFFFF) + 4) if (v & 0x1FFFFF) > 0x10000 else 0
        # world-ready gate: heap-aligned pointer + spawn height ~10 blocks
        if (v & 3) == 0 and 0x10000 < (v & 0x1FFFFF) < 0x1F8000 \
                and 0 < y < 10 * ONE_BLOCK * 4:
            P = v & 0x1FFFFF
            break
        p.wait(30)
    if not P:
        out["verdict"] = "NO_PLAYER_POINTER"
        print(json.dumps(out, indent=1))
        return 1
    p.wait(120)                                   # land after spawn
    m = p.mem
    out["P"] = P

    # ---- (1) camera hunt: all pointers inside the Player struct -------
    ptrs = {}
    for off in range(0, 0x80, 4):
        v = u(m, P + off)
        if 0x100000 < (v & 0x1FFFFF) < 0x200000:
            ptrs[off] = v & 0x1FFFFF
    out["player_ptrs"] = {hex(k): hex(v) for k, v in ptrs.items()}

    snap0 = dump(m, P, 0x80)
    tgt0 = {off: dump(m, t, 0x40) for off, t in ptrs.items()}

    # look down hard (X held) — camera pitch must change somewhere
    p.core.run(90, {"X"})
    snap1 = dump(m, P, 0x80)
    tgt1 = {off: dump(m, t, 0x40) for off, t in ptrs.items()}
    p.wait(30)

    out["player_struct_changes_look"] = diff_regs(P, snap0, P, snap1)
    cam_hits = {}
    for off, t in ptrs.items():
        ch = diff_regs(t, tgt0[off], t, tgt1[off])
        if ch:
            cam_hits[hex(off)] = {"target": hex(t), "changed": ch[:8]}
    out["pointer_target_changes_on_look"] = cam_hits

    # movement: which target tracks the player?
    z0 = u(m, P + 8)
    p.core.run(90, {"UP"})
    z1 = u(m, P + 8)
    out["z_delta_fwd"] = z1 - z0
    mv_hits = {}
    for off, t in ptrs.items():
        # re-dump now (post-move) and compare against pre-move dump
        b1 = dump(m, t, 0x40)
        ch = diff_regs(t, tgt0[off], t, b1)
        if ch:
            mv_hits[hex(off)] = ch[:6]
    out["pointer_target_changes_on_move"] = mv_hits

    # ---- (2) dig: aim down, hold R2, watch BreakingState --------------
    p.core.run(45, {"X"})                        # pitch down at ground
    p.wait(10)
    pre = dump(m, P, 0xC0)
    p.core.run(150, {"R2"})                      # ~2.5 s of breaking
    post = dump(m, P, 0xC0)
    out["dig_changes"] = diff_regs(P, pre, P, post)[:20]
    from PIL import Image
    img = p.core.frame_rgb()
    if img is not None:
        Image.fromarray(img).save(f"{EVID}/after_dig.png")

    # ---- (3) place: hold L2, watch hotbar impl + player tail ----------
    hb = u(m, P + 0x68) & 0x1FFFFF
    out["hotbar_impl"] = hex(hb)
    hb0 = dump(m, hb, 0x80)
    pre2 = dump(m, P, 0xC0)
    p.core.run(90, {"L2"})
    post2 = dump(m, P, 0xC0)
    hb1 = dump(m, hb, 0x80)
    out["place_player_changes"] = diff_regs(P, pre2, P, post2)[:20]
    out["place_hotbar_changes"] = diff_regs(hb, hb0, hb, hb1)[:20]

    # inventory impl too (START opens it — not opened here; static bytes)
    inv = u(m, P + 0x5C) & 0x1FFFFF
    out["inventory_impl"] = hex(inv)
    out["hotbar_dump0"] = hb0[:64].hex()
    out["finished"] = time.strftime("%FT%TZ", time.gmtime())
    with open(f"{EVID}/probe2_report.json", "w") as f:
        json.dump(out, f, indent=1, default=str)
    print(json.dumps({k: v for k, v in out.items()
                      if k not in ("hotbar_dump0",)}, indent=1,
                     default=str)[:3000])
    try:
        p.core.close()
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
