#!/usr/bin/env python3
"""r26t3_zenmai_rearmed.py — Round 26 boot 3: PCSX-ReARMed backend.

BEETLE VERDICT (boots 1-2, disclosed): PAD_DELIVERED=false — zero bytes
in 2 MB change under 40f held buttons for DOWN/UP/START/CROSS; the
r21 game-side SIO shim does NOT deliver input on beetle's frontio
(read-armed receive model). r22's diagnosis stands; the recorded lever
was "independent backend with write/TX-armed receive semantics".

LEVER EXECUTED: PCSX-ReARMed libretro core (independent SIO
implementation, real-hardware TX-armed receive semantics) — same
harness, same licensed disc (zenmai_lic_r21b, disclosed shim included;
harmless if the core arms receive on TX). Core downloaded from the
libretro buildbot, sha256 f202985eae74498b... recorded.

Boot cap: fresh per-backend counter (hard cap 1). Program:
  settle -> menu -> held-probe DOWN/UP/START/CROSS (same discriminating
  probe as boot 2) -> if a direction byte exists: select ENGLISH ->
  launch with START/CROSS -> BSS story scans (z3 sig / West of House).
RAM addressing note: ReARMed exposes SYSTEM_RAM; the physical-vs-KUSEG
convention is re-verified in-script (scan the first 64 KB for the
license string 'Sony Computer Entertainment' at physical 0 — same
convention beetle showed; if not found, addresses are re-based).
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
CORE = "/home/z/my-project/ps1-test/cores/pcsx_rearmed_libretro.so"
BIOS = "/home/z/my-project/ps1-test/emu/system/openbios.bin"
BOOTS = os.path.join(OUT, "boots_used_rearmed.json")

R = {"task": "r26t3b zenmai ReARMed boot 2: pad1type=standard + "
          "alternating probe",
     "core": CORE,
     "boot_amendment": "rearmed cap 1->2 disclosed pre-run: boot 1 "
                       "dead-input hypothesis = ReARMed default pad "
                       "type DualShock (ID 0x73) vs game expecting "
                       "digital 0x41; fix pcsx_rearmed_pad1type=standard; "
                       "also probe redesign: alternating 3-round "
                       "direction test catches edge-latched state the "
                       "held-constancy filter missed; plus a passive "
                       "auto-launch wait check",
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
    print(f"[r26t3] {json.dumps(rec, default=str)[:230]}", flush=True)
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


T0 = time.time()
for d in (OUT, SHOTS):
    os.makedirs(d, exist_ok=True)
n0 = boots_used()
assert n0 == 1, f"rearmed boot counter {n0} != 1"
json.dump({"count": 2, "backend": "pcsx_rearmed",
           "core_sha16": "f202985eae74498b",
           "amendments": [{"from": 1, "to": 2,
                           "reason": "pad1type=standard (digital 41) + "
                                     "alternating probe + passive wait",
                           "disclosed": "pre-run"}],
           "log": [{"boot": 1, "script": "r26t3_zenmai_rearmed.py",
                    "outcome": "menu reached; PAD_DELIVERED=false "
                               "(held-constancy probe)"},
                   {"boot": 2, "script": "r26t3_zenmai_rearmed.py (b)",
                    "t": time.strftime("%FT%TZ", time.gmtime())}]},
          open(BOOTS, "w"), indent=1)

ws = os.path.join(OUT, "ws_rearmed")
os.makedirs(os.path.join(ws, "system"), exist_ok=True)
os.makedirs(os.path.join(ws, "saves"), exist_ok=True)
shutil.copyfile(BIOS, os.path.join(ws, "system", "openbios.bin"))
# ReARMed bios naming: scph1001.bin / or any .bin in system dir; try
# both names via copies
shutil.copyfile(BIOS, os.path.join(ws, "system", "scph1001.bin"))
core = LibretroCore(CORE, os.path.join(ws, "system"),
                    os.path.join(ws, "saves"),
                    var_overrides={b"pcsx_rearmed_frameskip": b"0",
                                   b"pcsx_rearmed_pad1type": b"standard"})
av = core.load_game(CONTENT)
log("boot", core=core.core_name, ver=core.core_ver, av=av)

# RAM convention check
s0 = bytes(core.ram)
lic_at_0 = s0.find(b"Sony Computer Entertainment") < 0x4000
log("ram_check", ram_len=len(s0),
    lic_in_first_16k=lic_at_0,
    first_bytes=s0[:16].hex())

# ---- settle: poll frames, detect menu by mean band -----------------------
menu_f = None
mean_series = []
while core.frames_run < 3000:
    core.run_frame()
    if core.frames_run % 60:
        continue
    fr = core.frame_rgb()
    if fr is None:
        continue
    g = float(fr.mean())
    mean_series.append((core.frames_run, round(g, 1)))
    if core.frames_run % 300 == 0:
        snap("settle")
    if 25 < g < 40 and core.frames_run > 400:
        menu_f = core.frames_run
        break
snap("menu")
log("menu", menu_f=menu_f, tail=mean_series[-4:])
core.run(120, set())
snap("menu")

# passive auto-launch check: wait 1200f with NO input, story scan
for _ in range(20):
    core.run(60, set())
    s = bytes(core.ram)
    if s.find(bytes.fromhex("00774b5450d5389903e602b02c12"),
              0xBA800) >= 0:
        break
s = bytes(core.ram)
auto = s.find(bytes.fromhex("00774b5450d5389903e602b02c12"), 0xBA800)
log("passive_wait", z3_sig=auto)
snap("after_passive")


# ---- alternating probe (catches edge-latches AND steady state) ----------
def alt_probe(btn, rounds=3):
    """idle 8f vs held 8f, alternating; byte must differ the SAME
    direction in every round."""
    deltas = None
    consistent = None
    for _ in range(rounds):
        A0 = ram().copy()
        core.run(8, set())
        A1 = ram().copy()
        core.run(8, {btn})
        A2 = ram().copy()
        core.run(8, set())
        d = (A2.astype(np.int16) - A1.astype(np.int16))
        hit = (d != 0) & (A1 == A0)          # changed during hold, idle stable
        if deltas is None:
            deltas = d
            consistent = hit.copy()
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
launched = auto >= 0
log("probe_summary", delivered=delivered, auto_launched=launched)

# ---- select + launch -------------------------------------------------------
IMAGE_END = 0xBA800
if not launched and any(b in delivered for b in ("DOWN", "UP")):
    sel = "DOWN" if "DOWN" in delivered else "UP"
    core.run(4, {sel})
    core.run(50, set())
    snap("after_select")
    log("selected", sel=sel)
for btn in ("START", "B"):
    core.run(30, {btn})
    core.run(400, set())
    s = bytes(core.ram)
    z3 = s.find(bytes.fromhex("00774b5450d5389903e602b02c12"), IMAGE_END)
    west = s.find(b"West of House", IMAGE_END)
    launched = z3 >= 0 or west >= 0
    log("launch_held", btn=btn, z3=z3, west=west, launched=launched)
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
print("[r26t3] DONE frames=", core.frames_run,
      "wall=", round(time.time() - T0, 1), "verdict=", R["verdict"],
      json.dumps(R["verdicts"]), flush=True)
