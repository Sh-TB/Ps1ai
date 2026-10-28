#!/usr/bin/env python3
"""r26t6_zenmai_boot.py — Round 26 boot 3 (beetle, delay-loop-free disc).

Patch #3 (r26t5, disclosed): the 60-iteration inter-byte delay loop in
pad_exchange NOPed — the read->TX sequence is now back-to-back, making
zenmai's SIO flow byte-equivalent to the core-verified padtest protocol
(scripts/make_padtest_hw.py). Root cause analysis in r26t4 (static RE,
no boot cost).

Boot cap 2 -> 3 (disclosed pre-run). Program: settle -> menu ->
alternating probe x4 (DOWN/UP/START/B) -> if direction delivered:
select ENGLISH -> START launch -> z3/West-of-House story scans.
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
           "zenmai_lic_r26.cue")
CORE = "/home/z/my-project/ps1-test/cores/mednafen_psx_libretro.so"
BIOS = "/home/z/my-project/ps1-test/emu/system/openbios.bin"
BOOTS = os.path.join(OUT, "boots_used.json")
Z3 = bytes.fromhex("00774b5450d5389903e602b02c12")

R = {"task": "r26t6 zenmai beetle boot with patch #3 (delay loop NOPed)",
     "boot_amendment": "cap 2->3 disclosed pre-run: patch #3 = NOP the "
                       "60-iter delay loop (r26t4 static RE: read->TX "
                       "gap corrupts pad byte alignment via receive-"
                       "only double-clocking)",
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
    print(f"[r26t6] {json.dumps(rec, default=str)[:230]}", flush=True)
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
    return {"z3": s.find(Z3, 0xBA800),
            "west": s.find(b"West of House", 0xBA800),
            "banner": s.find(b"ZORK I", 0xBA800)}


T0 = time.time()
for d in (OUT, SHOTS):
    os.makedirs(d, exist_ok=True)
n0 = boots_used()
assert n0 == 2, f"boot counter {n0} != 2"
json.dump({"count": 3,
           "amendments": [
               {"from": 1, "to": 2, "reason": "boot 1 DOWN inert; 5 "
                                             "launch tries dead"},
               {"from": 2, "to": 3,
                "reason": "patch #3: NOP the 60-iter delay loop "
                          "(r26t4 static RE root cause)",
                "disclosed": "pre-run of r26t6"}],
           "log": [
               {"boot": 1, "script": "r26t1", "outcome": "MENU_REACHED "
                                                         "only"},
               {"boot": 2, "script": "r26t2", "outcome": "PAD_DELIVERED="
                                                         "false"},
               {"boot": 3, "script": "r26t6_zenmai_boot.py",
                    "disc": "zenmai_lic_r26 (patches 1+2+3)",
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


# ---- alternating probe ---------------------------------------------------
def alt_probe(btn, rounds=3):
    deltas = None
    consistent = None
    for _ in range(rounds):
        A0 = ram().copy()
        core.run(8, set())
        A1 = ram().copy()
        core.run(8, {btn})
        A2 = ram().copy()
        core.run(8, set())
        d = A2.astype(np.int16) - A1.astype(np.int16)
        hit = (d != 0) & (A1 == A0)
        if deltas is None:
            deltas, consistent = d, hit.copy()
        else:
            consistent &= hit & (np.sign(deltas) == np.sign(d))
    hits = np.nonzero(consistent)[0]
    rec = {"btn": btn, "hits": int(len(hits)),
           "head": [hex(int(i)) for i in hits[:10]],
           "deltas": [int(deltas[int(i)]) for i in hits[:10]]}
    log("alt_probe", **rec)
    snap(f"probe_{btn.lower()}")
    return rec


probes = {b: alt_probe(b) for b in ("DOWN", "UP", "START", "B")}
delivered = [b for b, r in probes.items() if r["hits"] > 0]
log("probe_summary", delivered=delivered)

# ---- select + launch -----------------------------------------------------
launched = False
if "DOWN" in delivered or "UP" in delivered:
    sel = "DOWN" if "DOWN" in delivered else "UP"
    core.run(4, {sel})
    core.run(50, set())
    snap("after_select")
    log("selected", sel=sel)
for btn in ("START", "B"):
    core.run(4, {btn})
    core.run(400, set())
    st = story()
    launched = st["z3"] >= 0 or st["west"] >= 0 or st["banner"] >= 0
    log("launch", btn=btn, story=st, launched=launched)
    snap(f"launch_{btn.lower()}")
    if launched:
        break
snap("final_state")

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
print("[r26t6] DONE frames=", core.frames_run,
      "wall=", round(time.time() - T0, 1), "verdict=", R["verdict"],
      json.dumps(R["verdicts"]), flush=True)
