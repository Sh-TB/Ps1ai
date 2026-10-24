#!/usr/bin/env python3
"""psxmc_probe4.py — decisive interaction probes for PSX-Minecraft.

(1) L1 crouch → PhysicsObjectFlags.crouching (flags bit9 @P+0x4C)
(2) R2 dig while standing, pitched ~-30° → BreakingState churn at
    P+0x6C.. (source: playerInputHandlerAttack -> updateBreakingState)
(3) L2 use with the same aim → any world/hotbar writes
(4) whole-RAM diff for the true Camera object (tracks player z each
    frame per playerUpdateCamera: camera.pos = player.pos, rot = physics
    rot) — resolves where the Camera copy lives.

One boot per process (H5). Evidence: emu/games_psx/evidence/psxmc_probe/
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
CUE = "/home/z/my-project/emu/games_homebrew/patched/PSXMC_lic.cue"
A_PLAYER = 0x3C608
ONE_BLOCK = 286720
CAM_OFF = 487424                       # PLAYER_CAMERA_OFFSET


def main():
    out = {"started": time.strftime("%FT%TZ", time.gmtime())}
    p = PS1Play(CUE, workspace="/home/z/my-project/emu/games_psx/ws_psxmc_probe4")
    p.boot()
    P = None
    for _ in range(240):
        v = p.mem.u32(A_PLAYER)
        if (v & 3) == 0 and 0x10000 < (v & 0x1FFFFF) < 0x1F8000:
            y = p.mem.u32((v & 0x1FFFFF) + 4)
            if 0 < y < 10 * ONE_BLOCK * 4:
                P = v & 0x1FFFFF
                break
        p.wait(30)
    if not P:
        out["verdict"] = "NO_PLAYER_POINTER"
        print(json.dumps(out, indent=1))
        return 1
    p.wait(150)                                   # land + settle
    m = p.mem
    out["P"] = P
    flags0 = m.u16(P + 0x4C)
    out["flags0"] = hex(flags0)

    # ---- (1) crouch flag ------------------------------------------------
    p.core.run(40, {"L1"})
    out["crouch_flags"] = hex(m.u16(P + 0x4C))
    out["crouch_bit9"] = bool((m.u16(P + 0x4C) >> 9) & 1)
    p.core.run(20, set())
    # ---- jump flag for reference ----------------------------------------
    p.core.run(20, {"R1"})
    out["jump_flags"] = hex(m.u16(P + 0x4C))
    out["jump_bit8"] = bool((m.u16(P + 0x4C) >> 8) & 1)
    p.wait(90)                                    # land again

    # ---- (4) camera scan: two moves, track z exactly ---------------------
    s0 = np.frombuffer(bytes(m.snapshot()), dtype="<u4")
    z0 = int(m.u32(P + 8))
    p.core.run(60, {"UP"})
    s1 = np.frombuffer(bytes(m.snapshot()), dtype="<u4")
    z1 = int(m.u32(P + 8))
    p.core.run(60, {"UP"})
    s2 = np.frombuffer(bytes(m.snapshot()), dtype="<u4")
    z2 = int(m.u32(P + 8))
    dz1, dz2 = z1 - z0, z2 - z1
    out["z_moves"] = [dz1, dz2]
    if dz1 != 0 and dz2 != 0:
        cand = np.where((s1.astype(np.int64) - s0.astype(np.int64) == dz1)
                        & (s2.astype(np.int64) - s1.astype(np.int64) == dz2)
                        )[0]
        cand = cand[(cand > 0x1000) & (cand < 0x1FF000)]
        out["z_track_addrs"] = [int(c) for c in cand[:40]]
        # camera filter: word at +4 tracks camera y (= -aabb.min.vy-off);
        # during a straight walk aabb.min.vy = ground -> constant y while
        # player y constant -> require +4 word CONSTANT across moves too
        hits = []
        for a in cand[:2000]:
            if int(s0[a - 1]) == int(s1[a - 1]) == int(s2[a - 1]) \
                    and int(s1[a - 2]) == int(s2[a - 2]):
                hits.append(int(a))
        out["cam_candidates"] = [hex(h) for h in hits[:20]]

    # ---- (2) dig: aim down-forward, hold R2, watch breaking -------------
    p.core.run(20, {"X"})                         # pitch down ~30°
    p.wait(30)
    pre = bytes(m.snapshot())
    brk0 = pre[P + 0x6C:P + 0x9C]
    p.core.run(300, {"R2"})                       # 5 s dig attempt
    post = bytes(m.snapshot())
    brk1 = post[P + 0x6C:P + 0x9C]
    out["breaking_before"] = brk0.hex()
    out["breaking_after"] = brk1.hex()
    out["breaking_changed"] = brk0 != brk1
    n_ch = int(np.count_nonzero(np.frombuffer(pre, "<u4")
                                != np.frombuffer(post, "<u4")))
    out["ram_words_changed_dig"] = n_ch
    from PIL import Image
    img = p.core.frame_rgb()
    if img is not None:
        Image.fromarray(img).save(f"{EVID}/probe4_after_dig.png")

    # ---- (3) use/place with same aim -------------------------------------
    p.wait(30)
    pre2 = bytes(m.snapshot())
    p.core.run(120, {"L2"})
    post2 = bytes(m.snapshot())
    n_ch2 = int(np.count_nonzero(np.frombuffer(pre2, "<u4")
                                 != np.frombuffer(post2, "<u4")))
    out["ram_words_changed_use"] = n_ch2
    img = p.core.frame_rgb()
    if img is not None:
        Image.fromarray(img).save(f"{EVID}/probe4_after_use.png")

    out["finished"] = time.strftime("%FT%TZ", time.gmtime())
    with open(f"{EVID}/probe4_report.json", "w") as f:
        json.dump(out, f, indent=1, default=str)
    print(json.dumps({k: v for k, v in out.items()
                      if k not in ("z_track_addrs", "cam_candidates")},
                     indent=1, default=str)[:1600])
    print("cam_candidates:", out.get("cam_candidates"))
    try:
        p.core.close()
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
