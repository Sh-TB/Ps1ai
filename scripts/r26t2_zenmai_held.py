#!/usr/bin/env python3
"""r26t2_zenmai_held.py — Round 26 boot 2: held-button RAM probe.

Boot-1 result (disclosed): menu @f660, but DOWN pulse -> ram_changed=0
across 2 MB and 5 launch tries (START/CROSS x short/long, JP default)
never produced the z3/story signatures. Menu animation baseline is
~7.2 mad, so visual-only cursor probes are meaningless here.

Definitive test for "does the SIO shim deliver buttons at all":
HOLD each button 40f and look for bytes that
  (a) changed idle->hold,
  (b) stayed CONSTANT for 20 consecutive mid-hold frames (a held
      button value plateaus; animation counters churn),
  (c) reverted after release.
A byte matching (a)+(b)+(c) = the game's pad-state byte for that
button -> the exchange WORKS and we can drive the menu with it.
No such byte for any button = the exchange is dead on this build ->
r22's conclusion stands, PCSX-Redux write-side drive becomes the
recorded next lever.

Boot cap 1 -> 2 (disclosed pre-run). If a direction byte is found:
select ENGLISH with it, then try START/CROSS launch (held 30f) with
BSS story-signature verification (z3 sig / West of House > 0xBA800).
"""
import json
import os
import shutil
import sys
import time

import numpy as np
from PIL import Image

REPO = "/home/z/my-project/ps1ai"
sys.path.insert(0, REPO)
from ps1play.core.host import LibretroCore  # noqa: E402

OUT = os.path.join(REPO, "scratch", "r26", "zenmai")
SHOTS = os.path.join(OUT, "shots")
CONTENT = ("/home/z/my-project/emu/games_homebrew/patched/"
           "zenmai_lic_r21b.cue")
CORE = "/home/z/my-project/ps1-test/cores/mednafen_psx_libretro.so"
BIOS = "/home/z/my-project/ps1-test/emu/system/openbios.bin"
BOOTS = os.path.join(OUT, "boots_used.json")

IMAGE_END = 0xBA800
Z3_SIG = bytes.fromhex("00774b5450d5389903e602b02c12")

R = {"task": "r26t2 zenmai held-button probe + launch",
     "boot_amendment": "cap 1->2 disclosed pre-run (boot 1: menu "
                       "reached; DOWN inert; 5 launch tries no story "
                       "signature)",
     "started": time.strftime("%FT%TZ", time.gmtime()),
     "events": [], "shots": []}


def boots_used():
    if os.path.exists(BOOTS):
        return json.load(open(BOOTS)).get("count", 0)
    return 0


def dump():
    json.dump(R, open(os.path.join(OUT, "boot_log.json"), "w"),
              indent=1, default=str)


def log(ev, **kw):
    rec = {"f": core.frames_run, "t": round(time.time() - T0, 1),
           "event": ev, **kw}
    R["events"].append(rec)
    print(f"[r26t2] {json.dumps(rec, default=str)[:230]}", flush=True)
    dump()


def snap(tag):
    arr = core.frame_rgb()
    if arr is not None:
        p = os.path.join(SHOTS, f"{tag}_f{core.frames_run:05d}.png")
        Image.fromarray(arr).save(p)
        R["shots"].append({"tag": tag, "frame": core.frames_run,
                           "png": os.path.relpath(p, OUT)})
    return arr


def ram():
    return np.frombuffer(bytes(core.ram), dtype=np.uint8)


def story():
    s = bytes(core.ram)
    return {"z3_sig": s.find(Z3_SIG, IMAGE_END),
            "west": s.find(b"West of House", IMAGE_END)}


T0 = time.time()
for d in (OUT, SHOTS):
    os.makedirs(d, exist_ok=True)
n0 = boots_used()
assert n0 == 1, f"boot counter {n0} != 1"
json.dump({"count": 2,
           "amendments": [{"from": 1, "to": 2,
                           "reason": "boot 1: menu reached; DOWN inert; "
                                     "5 launch tries dead; held-probe "
                                     "is the definitive test",
                           "disclosed": "pre-run of r26t2"}],
           "log": [{"boot": 1, "script": "r26t1_zenmai_launch.py",
                    "outcome": "MENU_REACHED only (DOWN inert, no story "
                               "signature after 5 launch tries)"},
                   {"boot": 2, "script": "r26t2_zenmai_held.py",
                    "t": time.strftime("%FT%TZ", time.gmtime())}]},
          open(BOOTS, "w"), indent=1)

ws = os.path.join(OUT, "ws")
os.makedirs(os.path.join(ws, "system"), exist_ok=True)
os.makedirs(os.path.join(ws, "saves"), exist_ok=True)
shutil.copyfile(BIOS, os.path.join(ws, "system", "openbios.bin"))
core = LibretroCore(CORE, os.path.join(ws, "system"),
                    os.path.join(ws, "saves"),
                    var_overrides={b"beetle_psx_renderer": b"software",
                                   b"beetle_psx_frame_duping": b"disabled"})
av = core.load_game(CONTENT)
log("boot", core=core.core_name, av=av)

# ---- settle to menu ------------------------------------------------------
menu_f = None
while core.frames_run < 2400:
    core.run_frame()
    if core.frames_run % 60:
        continue
    fr = core.frame_rgb()
    if fr is not None and 25 < float(fr.mean()) < 40:
        menu_f = core.frames_run
        break
core.run(120, set())
snap("menu")
log("menu", menu_f=menu_f)

# ---- held-button probe ----------------------------------------------------
def held_probe(btn, hold=40, mid=20):
    S0 = ram().copy()
    pre = core.frame_rgb()
    core.run(hold, {btn})
    mids = []
    for _ in range(mid):
        core.run_frame()
        mids.append(ram().copy().astype(np.int16))
    S1 = ram().copy()
    core.run(40, set())
    S2 = ram().copy()
    post = core.frame_rgb()
    mids = np.stack(mids)                       # (mid, nbytes)
    changed01 = S0 != S1
    const_mid = (mids.max(axis=0) == mids.min(axis=0))
    reverted12 = S1 != S2
    hits = np.nonzero(changed01 & const_mid & reverted12)[0]
    rec = {"btn": btn, "hits": int(len(hits)),
           "head": [hex(int(i)) for i in hits[:10]],
           "vals": [int(S1[int(i)]) for i in hits[:10]]}
    log("held_probe", **rec)
    snap(f"probe_{btn.lower()}")
    return rec


probes = {b: held_probe(b) for b in ("DOWN", "UP", "START", "B")}
delivered = [b for b, r in probes.items() if r["hits"] > 0]
log("probe_summary", delivered=delivered)

# ---- if a direction works: select + launch --------------------------------
launched = False
sel = None
if any(b in delivered for b in ("DOWN", "UP")):
    sel = "DOWN" if "DOWN" in delivered else "UP"
    core.run(4, {sel})
    core.run(50, set())
    snap("after_select")
    log("selected", sel=sel)
for btn in ("START", "B"):
    if btn not in delivered and btn not in ("START", "B"):
        continue
    core.run(30, {btn})
    core.run(300, set())
    st = story()
    launched = st["z3_sig"] >= 0 or st["west"] >= 0
    log("launch_held", btn=btn, story=st, launched=launched)
    snap(f"launch_{btn.lower()}")
    if launched:
        break

# ---- verdicts --------------------------------------------------------------
R["verdicts"] = {
    "MENU_REACHED": menu_f is not None,
    "PAD_DELIVERED": bool(delivered),
    "LAUNCHED": bool(launched),
}
R["verdict"] = ("LAUNCHED" if launched else
                "PAD_DELIVERED" if delivered else
                "MENU_REACHED" if menu_f is not None else "FAILED")
R["final"] = {"menu_f": menu_f, "delivered": delivered,
              "probes": {k: {kk: vv for kk, vv in v.items()}
                         for k, v in probes.items()}}
R["frames_total"] = core.frames_run
R["finished"] = time.strftime("%FT%TZ", time.gmtime())
dump()
print("[r26t2] DONE frames=", core.frames_run,
      "wall=", round(time.time() - T0, 1), "verdict=", R["verdict"],
      json.dumps(R["verdicts"]), flush=True)
