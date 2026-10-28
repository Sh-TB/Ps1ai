#!/usr/bin/env python3
"""r26t7_padtest_ab.py — Round 26 boot 4: A/B with the proven artifact.

Boots the r21-PROVEN padtest.hw payload (scripts/make_padtest_hw.py,
rebuilt today) as a disc, and reads its RAM breadcrumbs at 0x80018000
(physical 0x18000):
  +0x00 magic "PAD1"  +0x04 loop counter  +0x08 SW1  +0x0C SW2
  +0x10 polls_ok      +0x14 polls_fail
Then holds RIGHT / START / CROSS and watches SW1/SW2 flip (active-low).

Purpose: re-validate the "padtest works on this exact core build"
premise TODAY. If padtest fails, the r21 premise is stale and the whole
zenmai analysis shifts; if it works, boot 5 grafts zenmai's exact
exchange algorithm into this skeleton for a decisive A/B.

Boot cap: fresh padtest-ab counter, hard cap 1 (disclosed).
"""
import json
import os
import shutil
import sys
import time

import numpy as np
from PIL import Image

REPO = "/home/z/my-project/ps1ai"
sys.path.insert(0, os.path.join(REPO, "scripts"))
sys.path.insert(0, REPO)
from ps1play.core.host import LibretroCore  # noqa: E402

OUT = os.path.join(REPO, "scratch", "r26", "padtest_ab")
SHOTS = os.path.join(OUT, "shots")
CORE = "/home/z/my-project/ps1-test/cores/mednafen_psx_libretro.so"
BIOS = "/home/z/my-project/ps1-test/emu/system/openbios.bin"
BOOTS = os.path.join(OUT, "boots_used.json")
CRUMB = 0x18000                      # physical of 0x80018000

import make_padtest_hw  # noqa: E402
import iso9660_min    # noqa: E402

R = {"task": "r26t7b padtest A/B via the core's RAW EXE load path",
     "boot_amendment": "padtest-ab cap 1->2 disclosed pre-run: boot 1 "
                       "used the DISC route (SYSTEM.CNF shello) but "
                       "magic=0 - the payload never dispatched; "
                       "make_padtest_hw.py's own docstring says it is "
                       "meant for the core's RAW PS-X EXE Load path, no "
                       "disc, no kernel. Boot 2 loads PADTEST.EXE "
                       "directly as content.",
     "boot_cap": 2,
     "started": time.strftime("%FT%TZ", time.gmtime()),
     "events": [], "shots": []}


def dump():
    json.dump(R, open(os.path.join(OUT, "boot_log.json"), "w"),
              indent=1, default=str)


def log(ev, **kw):
    rec = {"f": core.frames_run, "t": round(time.time() - T0, 1),
           "event": ev, **kw}
    R["events"].append(rec)
    print(f"[r26t7] {json.dumps(rec, default=str)[:230]}", flush=True)
    dump()


def snap(tag):
    arr = core.frame_rgb()
    if arr is not None:
        p = os.path.join(SHOTS, f"{tag}_f{core.frames_run:05d}.png")
        Image.fromarray(arr).save(p)
        R["shots"].append({"tag": tag, "frame": core.frames_run,
                           "png": os.path.relpath(p, OUT)})
    return arr


def crumbs():
    r = bytes(core.ram)
    return {"magic": int.from_bytes(r[CRUMB:CRUMB + 4], "little"),
            "loops": int.from_bytes(r[CRUMB + 4:CRUMB + 8], "little"),
            "sw1": r[CRUMB + 8], "sw2": r[CRUMB + 9],
            "ok": int.from_bytes(r[CRUMB + 16:CRUMB + 20], "little"),
            "fail": int.from_bytes(r[CRUMB + 20:CRUMB + 24], "little")}


def boots_used():
    if os.path.exists(BOOTS):
        return json.load(open(BOOTS)).get("count", 0)
    return 0


T0 = time.time()
for d in (OUT, SHOTS):
    os.makedirs(d, exist_ok=True)
assert not os.path.exists(BOOTS) or json.load(open(BOOTS)).get("count", 0) == 1, \
    "padtest-ab counter must be 0 or 1"
_n0 = boots_used()
json.dump({"count": _n0 + 1,
           "amendments": ([{"from": 1, "to": 2,
                           "reason": "boot 1 disc route: payload never "
                                     "dispatched (magic=0); boot 2 uses "
                                     "the raw EXE load path as designed",
                           "disclosed": "pre-run of r26t7b"}] if _n0 == 1
                          else []),
           "log": ([{"boot": 1, "script": "r26t7_padtest_ab.py",
                     "outcome": "FAILED (disc route, magic=0)"}]
                    if _n0 == 1 else []) +
                  [{"boot": _n0 + 1, "script": "r26t7_padtest_ab.py (b)",
                    "t": time.strftime("%FT%TZ", time.gmtime())}]},
          open(BOOTS, "w"), indent=1)

# build the padtest disc (EXE from make_padtest_hw + iso9660_min + license)
work = "/tmp/r26_padtest_hw"
os.makedirs(work, exist_ok=True)
code = make_padtest_hw.build()
make_padtest_hw.write_exe(code, work)
exe = open(os.path.join(work, "PADTEST.EXE"), "rb").read()
cnf = (b"BOOT = cdrom:\\PADTEST.EXE;1\nTCB = 4\nEVENT = 10\n"
       b"STACK = 801FFF00\n")
bin_data, cue = iso9660_min.build_image(
    [("SYSTEM.CNF", cnf), ("PADTEST.EXE", exe)])
msx = "/home/z/my-project/emu/game/Metal Slug X (USA).bin"
lic = open(msx, "rb").read(16 * 2352)
assert b"Sony Computer Entertainment" in lic
bin_data = bytearray(bin_data)
bin_data[:16 * 2352] = lic
bin_path = os.path.join(OUT, "padtest_lic.bin")
open(bin_path, "wb").write(bytes(bin_data))
cue_path = os.path.join(OUT, "padtest_lic.cue")
open(cue_path, "w").write(cue.replace('"image.bin"',
                                      '"padtest_lic.bin"'))
print("[r26t7] disc_built", len(bin_data), "bytes")

ws = os.path.join(OUT, "ws")
os.makedirs(os.path.join(ws, "system"), exist_ok=True)
os.makedirs(os.path.join(ws, "saves"), exist_ok=True)
shutil.copyfile(BIOS, os.path.join(ws, "system", "openbios.bin"))
core = LibretroCore(CORE, os.path.join(ws, "system"),
                    os.path.join(ws, "saves"),
                    var_overrides={b"beetle_psx_renderer": b"software",
                                   b"beetle_psx_frame_duping": b"disabled"})
# boot 2: RAW EXE load path (the payload's designed route - no disc,
# no BIOS kernel involvement)
av = core.load_game(os.path.join(work, "PADTEST.EXE"))
log("boot", core=core.core_name, av=av,
    content="PADTEST.EXE (raw PS-X EXE load)")

# wait for breadcrumbs: magic + loop counter advancing
ok = False
for _ in range(90):
    core.run(60, set())
    c = crumbs()
    if c["magic"] == 0x50414431 and c["loops"] > 3:
        ok = True
        break
snap("padtest")
log("crumbs", ready=ok, **crumbs())

# button watch: idle SW1 vs held
def sw_watch(btn, hold=60):
    base = crumbs()
    core.run(hold, {btn})
    core.run(30, set())
    held = crumbs()
    rec = {"btn": btn, "sw1_idle": base["sw1"], "sw1_held": held["sw1"],
           "sw2_idle": base["sw2"], "sw2_held": held["sw2"],
           "flipped": base["sw1"] != held["sw1"]
           or base["sw2"] != held["sw2"]}
    log("sw_watch", **rec)
    snap(f"sw_{btn.lower()}")
    return rec


watches = [sw_watch(b) for b in ("RIGHT", "START", "B")]
c = crumbs()
snap("final_state")

R["verdicts"] = {
    "PADTEST_RUNNING": bool(ok),
    "BUTTONS_DELIVER": any(w["flipped"] for w in watches),
    "POLLS_HEALTHY": bool(c["ok"] > 0 and c["fail"] == 0),
}
R["verdict"] = ("PADTEST_OK" if ok and any(w["flipped"] for w in watches)
                else "PADTEST_RUNNING_NO_BUTTONS" if ok else "FAILED")
R["final"] = {"crumbs": c, "watches": watches}
R["frames_total"] = core.frames_run
R["finished"] = time.strftime("%FT%TZ", time.gmtime())
dump()
print("[r26t7] DONE frames=", core.frames_run,
      "wall=", round(time.time() - T0, 1), "verdict=", R["verdict"],
      json.dumps(R["verdicts"]), flush=True)
