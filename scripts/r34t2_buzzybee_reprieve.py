#!/usr/bin/env python3
"""r34t2_buzzybee_reprieve.py — Round 34: buzzybee input re-probe with
CORRECT KUSEG addressing (the r30 observation-bug correction probe).

FINDINGS SO FAR (r34t1, instrumented core f2383b2f, source [PSXBUS]):
  - Boot 1 buzzybee: START press -> L0fe btn=0008, L1dev p0=0800,
    L2bus nz=0800 served 50x on the pad bus, kernel ISR alive
    (dtr/c42 counters climbing). Core delivery layer 100% healthy.
  - Boot 2 tetrade: CROSS -> L0fe 4000 -> L1dev 0040 -> L2bus nz=0040.
    Same binary serves both games identically.
  - AUDIT: r30t2/t5/t6 read the game words with core.ram[va:va+4]
    where va = 0x8005xxxx RAW -> numpy out-of-bounds slice -> empty ->
    0. The r23 scripts (r23t2_buzzybee_boot4.py) used
    core.ram[va - 0x80000000:...] - correct. Therefore the r30
    "input regression" / "class split" on buzzybee was an OBSERVATION
    ARTIFACT, not an environment change. r30t6's padbuf POKE also
    wrote via the broken path (empty-slice assignment = no-op), void
    on both read and write sides.

This boot re-measures buzzybee with r23-correct addressing:
  expectation chain (r23 ground truth, image buzbee_ntsc_lic sha
  042b94bb): settle -> gs==0 -> START 40f -> gs==1 -> CROSS taps ->
  score increases (r23: 143->205 class) -> kernel padbuf candidates
  (r30t6 scan 0x80058850/0x80058872, re-read correctly) show the
  active-low button bytes landing.

Cap amendment 2->3 DISCLOSED PRE-RUN (fresh r34 ledger): boot 3 =
this correction probe. Class correction only - no rung inflation
from this boot alone; if gs moves, the deep-systems pass follows in
a separately disclosed boot.
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

OUT = os.path.join(REPO, "scratch", "r34")
SHOTS = os.path.join(OUT, "shots")
BIOS = "/home/z/my-project/ps1-test/emu/system/openbios.bin"
CORE = "/home/z/my-project/ps1-test/cores/mednafen_psx_libretro_psxbus_r34.so"
BUZZ = "/home/z/my-project/emu/games_homebrew/patched/buzzybee_ntsc_lic.cue"
BOOTS = os.path.join(OUT, "boots_used.json")

GS, BEST, SCORE = 0x80058830, 0x80058838, 0x8005883C
IPAD, ITRIG, IHELD = 0x8005881C, 0x80058820, 0x80058824
PB1, PB2 = 0x80058850, 0x80058872   # r30t6 candidates, re-read correctly

R = {"task": "r34t2 buzzybee reprieve: correct-addressing input re-probe",
     "cap_policy": "amendment 2->3 DISCLOSED PRE-RUN: boot 3 = "
                   "correction probe; no rung inflation from this boot",
     "started": time.strftime("%FT%TZ", time.gmtime()),
     "events": [], "shots": []}


def dump():
    json.dump(R, open(os.path.join(OUT, "boot_log_r34t2.json"), "w"),
              indent=1, default=str)


def log(ev, **kw):
    rec = {"f": core.frames_run, "t": round(time.time() - T0, 1),
           "event": ev, **kw}
    R["events"].append(rec)
    print(f"[r34t2] {json.dumps(rec, default=str)[:240]}", flush=True)
    dump()


def snap(tag):
    arr = core.frame_rgb()
    if arr is not None:
        p = os.path.join(SHOTS, f"{tag}_f{core.frames_run:05d}.png")
        Image.fromarray(arr).save(p)
        R["shots"].append({"tag": tag, "frame": core.frames_run,
                           "png": os.path.relpath(p, OUT)})
    return arr


def i32(va):
    off = va - 0x80000000
    return int.from_bytes(bytes(core.ram[off:off + 4]), "little",
                          signed=True)


def u16(va):
    off = va - 0x80000000
    return int.from_bytes(bytes(core.ram[off:off + 2]), "little")


def pb(va):
    off = va - 0x80000000
    return bytes(core.ram[off:off + 4]).hex()


def buz_inp():
    return {"pad": u16(IPAD), "trig": u16(ITRIG), "held": u16(IHELD),
            "gs": i32(GS)}


T0 = time.time()
os.makedirs(SHOTS, exist_ok=True)

led = json.load(open(BOOTS))
assert led["count"] == 2, "expected r34t1 to have consumed 2"
led["amendments"] = [{"from": 2, "to": 3,
                      "reason": "r34t2 correction probe (addressing "
                                "artifact), disclosed pre-run"}]
led["count"] = 3
led["log"].append({"boot": 3, "script": "r34t2_buzzybee_reprieve.py",
                   "t": time.strftime("%FT%TZ", time.gmtime())})
json.dump(led, open(BOOTS, "w"), indent=1)

ws = os.path.join(OUT, "ws_reprieve")
os.makedirs(os.path.join(ws, "system"), exist_ok=True)
os.makedirs(os.path.join(ws, "saves"), exist_ok=True)
shutil.copyfile(BIOS, os.path.join(ws, "system", "openbios.bin"))
core = LibretroCore(CORE, os.path.join(ws, "system"),
                    os.path.join(ws, "saves"),
                    var_overrides={b"beetle_psx_renderer": b"software",
                                   b"beetle_psx_frame_duping": b"disabled"})
av = core.load_game(BUZZ)
log("boot", core=core.core_name, av=av)

# P1: settle -> idle
for _ in range(900):
    core.run(1, set())
idle = [buz_inp() for _ in range(30)]
pb_idle = {hex(PB1): pb(PB1), hex(PB2): pb(PB2)}
log("idle_sample", head=idle[:5],
    gs0=bool(all(x["gs"] == 0 for x in idle)), padbuf_idle=pb_idle)
snap("idle")

# P2: START hold 40f (correct reads + padbuf bytes)
core.set_buttons("START")
series, pbs = [], []
for _ in range(40):
    core.run_frame()
    series.append(buz_inp())
    pbs.append({"pb1": pb(PB1), "pb2": pb(PB2)})
core.set_buttons(set())
for _ in range(90):
    core.run_frame()
gs1 = i32(GS)
R["start_hold"] = series
R["start_hold_padbuf"] = pbs
nz = [s for s in series if s["pad"] or s["held"] or s["trig"]]
n1 = [p for p in pbs if not p["pb1"].startswith("0041ffff")]
log("start_hold_40f", nonzero_input_frames=len(nz),
    input_first=nz[:3] if nz else None,
    gs_after=gs1, GS_MOVED=bool(gs1 == 1),
    padbuf_nonidle_frames=len(n1), padbuf_first=n1[:2] if n1 else None)
snap("after_start")

# P3: gameplay CROSS taps -> score delta (r23 class: score rises)
sc0 = i32(SCORE)
core.set_buttons("B")
for _ in range(6):
    core.run_frame()
core.set_buttons(set())
for _ in range(40):
    core.run_frame()
sc1 = i32(SCORE)
core.set_buttons("B")
for _ in range(6):
    core.run_frame()
core.set_buttons(set())
for _ in range(60):
    core.run_frame()
sc2 = i32(SCORE)
inp_after = buz_inp()
log("cross_taps", score_0=sc0, score_1=sc1, score_2=sc2,
    score_rose=bool(sc2 > sc0), last_inp=inp_after)
snap("after_cross")

verdict = {
    "input_alive": bool(nz and i32(GS) == 1),
    "gs_moved_on_start": bool(gs1 == 1),
    "score_rose": bool(sc2 > sc0),
    "padbuf_buttons_landed": bool(n1),
}
R["verdict"] = verdict
log("verdict", **verdict,
    interpretation=("input_alive=true REFUTES the r30 environment-"
                    "regression premise for buzzybee (observation "
                    "artifact); deep systems pass follows"))

json.dump(R, open(os.path.join(OUT, "boot_log_r34t2.json"), "w"),
          indent=1, default=str)
print("[r34t2] DONE", flush=True)
