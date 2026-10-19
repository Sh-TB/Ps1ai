#!/usr/bin/env python3
"""verify_map.py — discover the REAL RAM map live, read-only (v2).

The published GameShark seeds (gamehacking.org #89284) turned out to be
for a different disc version (hp/bombs/lives read 0xFF garbage on
SLUS-01212 while the pad word matched) — so this run DISCOVERS the map
with the classic cheat-finder workflow instead, then cross-checks the
seeds as hints:

  A enter      : vision nav + activity ratio + pad-echo gate
  B bombs      : MemScan 1..99 -> grenade -> dec_by(1) x2 -> intersect
  C hp         : MemScan 50..200 -> combat (hits happen) -> dec filter
  D score      : monotonic() during combat (u32 winners)
  E pad echo   : input_echo(RIGHT+Y) -> controller mirror word
  F player_y   : jump-arc sweep near the known x counter
  G entities   : 90-frame watch -> live actor blocks (zero-token enemies)

Everything is observation: we NEVER write RAM. Results go to the profile.
"""
import json
import os
import sys
import time

sys.path.insert(0, "/home/z/my-project")
import numpy as np
from PIL import Image

from ps1play.api import PS1Play
from ps1play.agent.gsmap import GS_SEEDS, phys
from ps1play.agent import memscan, entities

GAME = "/home/z/my-project/ps1-test/extracted/metal_slug_x/Metal Slug X (USA).cue"
OUT = "/home/z/my-project/download/ps1play_v2"
os.makedirs(OUT, exist_ok=True)

SCAN_REGIONS = [
    (0x085200, 0x085A00, "hit-anywhere 0x85xxx"),
    (0x03F000, 0x042000, "hit fields 0x040xxx"),
    (0x0E7000, 0x0E9000, "player-x zone"),
    (0x0D0000, 0x0D6000, "pad/mission zone"),
]

rep = {"phases": {}, "started": time.strftime("%H:%M:%S")}


def log(msg):
    print(f"[verify] {msg}", file=sys.stderr, flush=True)


def snap_png(p, name):
    try:
        rgb = p.core.frame_rgb()
        if rgb is not None:
            Image.fromarray(rgb).save(os.path.join(OUT, name))
    except Exception as e:
        log(f"png {name}: {e}")


def watch_once(p):
    """Raw GS seed values + discovered roles (reporting only)."""
    m = p.mem
    row = {}
    for role, spec in GS_SEEDS.items():
        a = phys(spec["addr"])
        row[role] = (m.u8(a) if spec["dtype"] == "u8" else
                     m.u32(a) if spec["dtype"] == "u32" else m.u16(a))
    dx = (p.profile.get("discovered") or {}).get("player_x") or {}
    if dx.get("addr") is not None:
        row["x"] = m.u32(dx["addr"]) if dx.get("dtype") == "u32" else m.u16(dx["addr"])
    return row


# ---------------------------------------------------------------- boot ----
log("boot...")
p = PS1Play(GAME, verbose=False)
info = p.boot()
log(f"core={info['core']} serial={info['serial']}")
rep["boot"] = info

log("fresh boot -> vision-guided enter_gameplay3 (activity + pad-echo gate)")
r = p.enter_gameplay3()
log(f"enter_gameplay3: {json.dumps(r)[:220]}")
rep["enter"] = {k: r.get(k) for k in ("in_game", "steps", "detector", "echo")}
if not r["in_game"]:
    print(json.dumps(rep, indent=1))
    sys.exit(2)

snap_png(p, "verify_gameplay_start.png")
row0 = watch_once(p)
log(f"start state: {row0}")
rep["state_start"] = row0
m = p.mem

# ------------------------------------------------ B: bombs via MemScan ----
scan = memscan.MemScan(m)
scan.between("u16", 1, 99)
scan.between("u8", 1, 99)
p.core.run(10, {"A"})                       # throw grenade #1
p.core.run(70, {"RIGHT", "Y"})
scan.dec_by("u16", 1, tol=0)
scan.dec_by("u8", 1, tol=0)
p.core.run(10, {"A"})                       # throw grenade #2
p.core.run(70, {"RIGHT", "Y"})
scan.dec_by("u16", 1, tol=0)
scan.dec_by("u8", 1, tol=0)
cands_bombs = scan.results("u16", top=12) + scan.results("u8", top=12)
rep["phases"]["bombs"] = {"candidates": cands_bombs}
log(f"B bombs candidates: {cands_bombs[:6]}")

# ------------------------------------------------ C: hp via MemScan -------
scan2 = memscan.MemScan(m)
scan2.between("u16", 50, 200)
for _ in range(6):                          # combat: take hits naturally
    p.core.run(40, {"RIGHT", "Y"})
    p.core.run(20, {"RIGHT"})
hp_cands = []
if scan2.counts()["u16"] < 400000:          # narrow only if sane
    scan2.lt_prev = None
    scan2.dec("u16")                        # hp dropped during combat
    hp_cands = scan2.results("u16", top=16)
rep["phases"]["hp"] = {"candidates": hp_cands,
                       "remaining": scan2.counts()["u16"]}
log(f"C hp candidates: {hp_cands[:6]}")

# ------------------------------------------------ D: score monotonic ------
mono = p.disc.monotonic(frames=240, step=30, buttons={"RIGHT", "Y"}, top=12)
u32m = [x for x in mono if x["dtype"] == "u32"]
rep["phases"]["score"] = {"monotonic": mono[:8]}
log(f"D monotonic top: {mono[:5]}")

# ------------------------------------------------ E: pad echo -------------
echo = p.disc.input_echo("RIGHT+Y", window=40, reps=2)
rep["phases"]["pad_echo"] = echo[:5]
log(f"E pad echo: {echo[:3]}")

# ------------------------------------------------ F: player_y jump arc ----
px_spec = (p.profile.get("discovered") or {}).get("player_x") or {}
px_addr = px_spec.get("addr")
y_found = None
if px_addr:
    base_addrs = list(range(px_addr - 0x40, px_addr + 0x64, 4))
    frames = []
    p.core.run(15, set())
    for i in range(95):
        p.core.set_buttons({"B"} if 15 <= i < 60 else set())
        p.core.run_frame()
        if i % 2 == 0:
            frames.append({a: m.u32(a) for a in base_addrs})
    p.core.set_buttons(set())
    best = None
    for a in base_addrs:
        if a == px_addr:
            continue
        vals = [f[a] for f in frames]
        b0v = float(np.mean(vals[:6]))
        mn, mx = min(vals), max(vals)
        returned = abs(vals[-1] - b0v) < 0x80
        dip = (b0v - mn) if mn < b0v else (mx - b0v)
        if returned and 0x100 <= dip <= 0x8000 and (mx - mn) >= 0x100:
            if best is None or dip > best[1]:
                best = (a, dip)
    if best:
        y_found = {"addr": best[0], "dtype": "u32", "dip": int(best[1]),
                   "verified": "jump_arc"}
rep["phases"]["player_y"] = y_found
log(f"F player_y: {y_found}")

# ------------------------------------------------ G: entity blocks -------
log("G entity watch: 90 frames of running combat...")
snaps = []
p.core.set_buttons({"RIGHT", "Y"})
for i in range(90):
    p.core.run_frame()
    p.core.set_buttons({"RIGHT"} if i % 3 == 0 else {"RIGHT", "Y"})
    snaps.append(m.snapshot())
p.core.set_buttons(set())

blocks_all = []
for lo, hi, tag in SCAN_REGIONS:
    for dt, max_step in (("<u4", 0x8000), ("<u2", 0x2000)):
        flds = entities.find_live_fields(snaps, lo, hi, dtype=dt,
                                         max_step=max_step)
        for b in entities.group_blocks(flds):
            b["zone"] = tag
            blocks_all.append(b)
blocks_all.sort(key=lambda b: -b["n_live"])
rep["phases"]["entities"] = {"n_blocks": len(blocks_all),
                             "top": blocks_all[:6]}
log(f"G blocks: {len(blocks_all)}; top: "
    f"{[(hex(b['start']), hex(b['end']), b['n_live'], b['zone']) for b in blocks_all[:4]]}")

# ------------------------------------------------ verdict + profile ------
# GS seed cross-check: which seeds hold sane values in-mission?
gs_check = {}
for role, spec in GS_SEEDS.items():
    v = row0.get(role)
    sane = (v is not None and v != 255 and v != 0xFF)
    gs_check[role] = {"addr": phys(spec["addr"]), "value": v, "sane": sane}
rep["gs_check"] = gs_check

p.profile.setdefault("history", []).append({
    "op": "verify_map_v2",
    "bombs_cands": [c["addr"] for c in cands_bombs[:4]],
    "hp_cands": [c["addr"] for c in hp_cands[:4]],
    "score_cands": [c["addr"] for c in u32m[:4]],
    "pad_echo": (echo[0]["addr"] if echo else None),
    "player_y": bool(y_found),
    "blocks": len(blocks_all)})
if u32m:
    p.profile.setdefault("discovered", {})["score"] = {
        "addr": u32m[0]["addr"], "dtype": "u32",
        "score": u32m[0]["gain"], "dir": "+", "verified": "monotonic"}
if y_found:
    p.profile.setdefault("discovered", {})["player_y"] = y_found
if blocks_all:
    main = blocks_all[0]
    p.profile["entities"] = {"main_block": {
        "start": main["start"], "end": main["end"], "step": 4,
        "n_live": main["n_live"], "zone": main["zone"]}}
if echo:
    p.profile.setdefault("discovered", {})["controller_echo"] = echo[0]
p.save_profile()
rep["state_end"] = watch_once(p)
snap_png(p, "verify_gameplay_end.png")
rep["saved_profile"] = p.profile_path

with open(os.path.join(OUT, "verify_map_report.json"), "w") as f:
    json.dump(rep, f, indent=1, default=str)
print(json.dumps(rep["phases"], indent=1, default=str)[:2000])
log("DONE")
