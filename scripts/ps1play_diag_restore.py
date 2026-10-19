#!/usr/bin/env python3
"""Diagnose: restore stage1_start, screenshot, probe watch addresses."""
import sys, os, json
sys.path.insert(0, "/home/z/my-project")
from PIL import Image
from ps1play.api import PS1Play
from ps1play.agent.gsmap import GS_SEEDS, phys

GAME = "/home/z/my-project/ps1-test/extracted/metal_slug_x/Metal Slug X (USA).cue"
OUT = "/home/z/my-project/download/ps1play_v2"

p = PS1Play(GAME)
print("boot:", p.boot())
for cand in ("stage1_start", "progress_A", "auto_0010k"):
    if not p.states.exists(cand):
        print(cand, "missing"); continue
    try:
        p.states.load(p.core, cand)
    except Exception as e:
        print(cand, "restore FAILED:", e); continue
    p.core.run(30, set())
    m = p.mem
    rows = {}
    for role, spec in GS_SEEDS.items():
        a = phys(spec["addr"])
        rows[role] = (m.u8(a) if spec["dtype"] == "u8" else
                      m.u32(a) if spec["dtype"] == "u32" else m.u16(a))
    dx = (p.profile.get("discovered") or {}).get("player_x") or {}
    if dx.get("addr") is not None:
        rows["x"] = m.u32(dx["addr"])
    print(f"--- {cand}: {rows}")
    rgb = p.core.frame_rgb()
    if rgb is not None:
        Image.fromarray(rgb).save(os.path.join(OUT, f"diag_{cand}.png"))
    # hexdump around key addrs
    for name in ("hp", "bombs", "lives", "pad_mirror", "ammo"):
        a = phys(GS_SEEDS[name]["addr"])
        print(f"  {name} @{a:#x}: {m.hexdump(a-8, 24)}")
p.shutdown()
