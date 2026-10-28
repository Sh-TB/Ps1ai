#!/usr/bin/env python3
"""r34t1_bus_probe.py — Round 34 boot-1/2: instrumented-beetle pad-bus probe.

The recorded lever from R32 (instrumented beetle build) executed.

Instrumentation (source edits, grep [PSXBUS], this tree df2b53b):
  core binary mednafen_psx_libretro_psxbus_r34.so md5 f2383b2f...
  (canonical 447b7ebf untouched; rollback 79f8fac0 retained)
  L0fe  input.c        : frontend callback view, port-0 button u16,
                         logged on change (btn=%04x)
  L1dev frontio.c      : Gamepad device struct buttons[2], on change
                         (p0=%02x%02x, active-high 1=pressed)
  L2bus frontio.c      : every 0x42 response served on the pad bus;
                         nonzero-buttons occurrences logged
                         (nz=%02x%02x); HB heartbeat every 120 FIO
                         updates with aggregate counters
                         (dtr=kernel ISR access attempts,
                          c42=0x42 responses served,
                          c42nz=nonzero-button responses)
  dtr   frontio.c      : Gamepad SetDTR rising edges counted

Question of the day (r30-r32 open): the same core binary, image,
BIOS and harness delivered buttons for minecraft+tetrade but not
doukutsu+buzzybee, mechanism unknown. The bus trace localizes the
death layer:
  - if L0fe shows the press but L1dev does not  -> device-selection
    layer (controller type resolution)
  - if L1dev shows it but L2bus never serves nz -> serialization
    layer (bus transfer)
  - if L2bus serves nz while the kernel padbuf stays idle -> BIOS
    kernel ISR discards (interrupt/clearing layer)
  - if L0fe itself never fires -> harness->core callback layer

Cap 2, DISCLOSED PRE-RUN: boot 1 = buzzybee (dead class), boot 2 =
tetrade (alive control, r30t4 protocol). Class probe only - no rung
attempt, no verdict inflation. Attribution is self-identifying in
the stderr bus log: buzzybee presses START (bit 0x0008, d8[0]=0x08),
tetrade presses CROSS (bit 0x4000, d8[1]=0x40).
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
CORE_MD5 = "f2383b2f6ea08c0509b08540963e49b2"
CANON_MD5 = "447b7ebf9e0805d0ebb222256ed62958"
BUZZ = "/home/z/my-project/emu/games_homebrew/patched/buzzybee_ntsc_lic.cue"
TET = "/home/z/my-project/emu/games_homebrew/patched/TETRADE_lic.cue"
BOOTS = os.path.join(OUT, "boots_used.json")
STDERR_PATH = os.path.join(OUT, "bus_stderr.log")

GS, IPAD, ITRIG, IHELD = 0x80058830, 0x8005881C, 0x80058820, 0x80058824
PB1, PB2 = 0x80058850, 0x80058872   # r30t6 engine padbuf candidates
TET_PAD0 = 0xBB120                   # kernel padbuff port 0 (r6/r7)

R = {"task": "r34t1 instrumented-beetle pad-bus probe (buzzybee vs tetrade)",
     "core": {"path": CORE, "md5": CORE_MD5,
              "canonical_md5": CANON_MD5,
              "source": "beetle-psx-libretro df2b53b + [PSXBUS] edits "
                        "(grep [PSXBUS]: input.c L0fe; frontio.c "
                        "L1dev/L2bus/dtr/HB)"},
     "cap_policy": "cap 2 disclosed pre-run: boot 1 buzzybee (dead "
                   "class), boot 2 tetrade (alive control); class "
                   "probe, no rung attempt",
     "started": time.strftime("%FT%TZ", time.gmtime()),
     "events": [], "shots": []}


def dump():
    json.dump(R, open(os.path.join(OUT, "boot_log.json"), "w"),
              indent=1, default=str)


def log(ev, **kw):
    rec = {"f": core.frames_run, "t": round(time.time() - T0, 1),
           "event": ev, **kw}
    R["events"].append(rec)
    print(f"[r34t1] {json.dumps(rec, default=str)[:240]}", flush=True)
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
    return int.from_bytes(bytes(core.ram[va:va + 4]), "little", signed=True)


def u16(va):
    return int.from_bytes(bytes(core.ram[va:va + 2]), "little")


def buz_inp():
    return {"pad": u16(IPAD), "trig": u16(ITRIG), "held": u16(IHELD),
            "gs": i32(GS)}


def pb_bytes(va):
    return bytes(core.ram[va:va + 4]).hex()


T0 = time.time()
os.makedirs(SHOTS, exist_ok=True)

# ---- boots ledger (fresh for r34, cap 2 disclosed) --------------------
if not os.path.exists(BOOTS):
    json.dump({"cap": 2, "count": 0, "log": [],
               "disclosure": "r34t1 cap 2 set pre-run; class probe "
                             "only, no rung attempt",
               "core_md5": CORE_MD5}, open(BOOTS, "w"), indent=1)
led = json.load(open(BOOTS))
assert led["cap"] == 2 and led["count"] == 0, "boot cap consumed"
led["count"] = 1
led["log"].append({"boot": 1, "script": "r34t1_bus_probe.py",
                   "content": "buzzybee_ntsc_lic",
                   "t": time.strftime("%FT%TZ", time.gmtime())})
json.dump(led, open(BOOTS, "w"), indent=1)

# ======================================================================
# BOOT 1: buzzybee (dead class) on the instrumented core
# ======================================================================
print("[PSXBUS] ---- BOOT 1 buzzybee (dead class) ----", file=sys.stderr,
      flush=True)
ws = os.path.join(OUT, "ws_buzz")
os.makedirs(os.path.join(ws, "system"), exist_ok=True)
os.makedirs(os.path.join(ws, "saves"), exist_ok=True)
shutil.copyfile(BIOS, os.path.join(ws, "system", "openbios.bin"))
core = LibretroCore(CORE, os.path.join(ws, "system"),
                    os.path.join(ws, "saves"),
                    var_overrides={b"beetle_psx_renderer": b"software",
                                   b"beetle_psx_frame_duping": b"disabled"})
av = core.load_game(BUZZ)
log("boot1_buzzybee", core=core.core_name, av=av)

for _ in range(900):
    core.run(1, set())
idle = [buz_inp() for _ in range(30)]
pb_idle = {hex(PB1): pb_bytes(PB1), hex(PB2): pb_bytes(PB2)}
log("idle_sample", head=idle[:5],
    all_zero=bool(all(x["pad"] == 0 and x["held"] == 0 for x in idle)),
    padbuf_idle=pb_idle)
snap("buzz_idle")

# START hold 40f, sample game words + both padbuf candidates per frame
core.set_buttons("START")
series = []
pb_series = []
for _ in range(40):
    core.run_frame()
    series.append({"f": core.frames_run, **buz_inp()})
    pb_series.append({"f": core.frames_run,
                      "pb1": pb_bytes(PB1), "pb2": pb_bytes(PB2)})
core.set_buttons(set())
rel = []
for _ in range(90):
    core.run_frame()
    rel.append(buz_inp())
R["start_hold"] = series
R["start_hold_padbuf"] = pb_series
nz = [s for s in series if s["pad"] or s["held"] or s["trig"]]
nzpb = [p for p in pb_series
        if not p["pb1"].startswith("0041ffff")
        and not p["pb2"].startswith("0041ffff")]
log("start_hold_40f", nonzero_frames=len(nz), first=nz[:3] if nz else None,
    last=series[-1], gs_after=i32(GS),
    padbuf_any_nonidle=len(nzpb),
    padbuf_first_nonidle=nzpb[:2] if nzpb else None)
snap("buzz_after_start")

# extended 2nd press window: START double-tap (r30t2 protocol)
core.set_buttons("START")
tap2 = []
for _ in range(5):
    core.run_frame()
    tap2.append(buz_inp())
core.set_buttons(set())
for _ in range(120):
    core.run_frame()
    tap2.append(buz_inp())
core.set_buttons("START")
for _ in range(5):
    core.run_frame()
    tap2.append(buz_inp())
core.set_buttons(set())
for _ in range(120):
    core.run_frame()
    tap2.append(buz_inp())
nz2 = [s for s in tap2 if s["pad"] or s["held"] or s["trig"]]
log("double_tap", nonzero=len(nz2), head=nz2[:4] if nz2 else None,
    gs_after=i32(GS))
snap("buzz_after_tap2")

# ======================================================================
# BOOT 2: tetrade (alive control) on the SAME instrumented core
# ======================================================================
print("[PSXBUS] ---- BOOT 2 tetrade (alive control) ----", file=sys.stderr,
      flush=True)
led["count"] = 2
led["log"].append({"boot": 2, "script": "r34t1_bus_probe.py",
                   "content": "TETRADE_lic",
                   "t": time.strftime("%FT%TZ", time.gmtime())})
json.dump(led, open(BOOTS, "w"), indent=1)

ws2 = os.path.join(OUT, "ws_tet")
os.makedirs(os.path.join(ws2, "system"), exist_ok=True)
os.makedirs(os.path.join(ws2, "saves"), exist_ok=True)
shutil.copyfile(BIOS, os.path.join(ws2, "system", "openbios.bin"))
core2 = LibretroCore(CORE, os.path.join(ws2, "system"),
                     os.path.join(ws2, "saves"),
                     var_overrides={b"beetle_psx_renderer": b"software",
                                    b"beetle_psx_frame_duping": b"disabled"})
av2 = core2.load_game(TET)
core = core2   # log() uses global core for frames_run
log("boot2_tetrade", core=core.core_name, av=av2)

for _ in range(900):
    core.run(1, set())


def tet_pad():
    return bytes(core.ram[TET_PAD0:TET_PAD0 + 4]).hex()


idle2 = [tet_pad() for _ in range(30)]
log("idle_padbuff", head=idle2[:5],
    id_ok=bool(all(x.startswith("0041") for x in idle2)))
snap("tet_idle")

# CROSS hold 5f (r30t4 protocol): button u16 at 0xBB122 active-low
before = idle2[-1]
core.set_buttons("B")
hold = []
for _ in range(5):
    core.run_frame()
    hold.append(tet_pad())
core.set_buttons(set())
rel2 = []
for _ in range(30):
    core.run_frame()
    rel2.append(tet_pad())
R["tet_cross_hold"] = hold
btn_before = before[4:8]
btn_during = sorted({h[4:8] for h in hold})
btn_after = rel2[-1][4:8]
log("cross_hold_5f", before=before, during=btn_during, after=btn_after,
    changed=bool(btn_during - {btn_before} or btn_during != {btn_before}))
snap("tet_after_cross")

# START tap for the menu transition leg (extra causal signal)
core.set_buttons("START")
for _ in range(5):
    core.run_frame()
core.set_buttons(set())
for _ in range(60):
    core.run_frame()
log("start_tap_done", padbuff=tet_pad())
snap("tet_after_start")

# ======================================================================
# verdict: parse the stderr bus log
# ======================================================================
try:
    raw = open(STDERR_PATH, "r", errors="replace").read()
except OSError:
    raw = ""
lines = [l for l in raw.splitlines() if "[PSXBUS]" in l]
b1 = [l for l in lines if "BOOT 1" in l]
i_b1 = raw.splitlines().index(b1[0]) if b1 else -1
seg1 = [l for l in lines if lines.index(l) < 10**9 and False]  # noop
# segment by boundary markers
bound = [i for i, l in enumerate(lines) if "BOOT 2" in l]
if bound:
    seg1 = lines[:bound[0]]
    seg2 = lines[bound[0]:]
else:
    seg1, seg2 = lines, []


def summarize(seg):
    return {
        "L0fe": [l.split("L0fe ", 1)[1] for l in seg if "L0fe" in l][:12],
        "L1dev": [l.split("L1dev ", 1)[1] for l in seg if "L1dev" in l][:12],
        "L2bus_nz": [l.split("L2bus ", 1)[1] for l in seg if "L2bus" in l]
                    [:12],
        "L2bus_nz_count": sum(1 for l in seg if "L2bus" in l),
        "HB_last": ([l for l in seg if " HB " in l] or [None])[-1],
        "HB_count": sum(1 for l in seg if " HB " in l),
    }


s1, s2 = summarize(seg1), summarize(seg2)
R["bus_log"] = {"boot1_buzzybee": s1, "boot2_tetrade": s2,
                "stderr_path": STDERR_PATH, "total_lines": len(lines)}
log("bus_verdict", boot1=s1, boot2=s2,
    interpretation=(
        "see L0fe/L1dev/L2bus layers; START=0800 (boot1), "
        "CROSS=0040 (boot2)"))

json.dump(R, open(os.path.join(OUT, "boot_log.json"), "w"), indent=1,
          default=str)
print("[r34t1] DONE", flush=True)
