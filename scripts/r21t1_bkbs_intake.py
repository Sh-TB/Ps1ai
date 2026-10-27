#!/usr/bin/env python3
"""r21t1_bkbs_intake.py — BKBS (hardrockbluesky/BKBS_PSX) headless intake (r21-t1).

ONE emulator boot (task cap 2 total; boot 1 proved boot+animation, then hit a
script bug at the pulse-logging step — this is the complete boot-2 run).

Phases (all in this single process, JSON dumped incrementally):
  1. boot timeline 0..2600 f, PNG every 200 (shell -> loading -> 3D scene)
  2. pad-buffer signature scan (00 41 ff ff) + per-frame pad-mirror probes
  3. frame-counter hunt: u32 words +60 over a 60 f idle window, then a
     12-frame per-candidate trace (+1 monotone = a real frame counter)
  4. gameplay-motion evidence: whole-RAM delta over a 90 f idle window
  5. input causality — 3-frame pulses: SELECT (cycles effectType 5->0,
     timing-INDEPENDENT visual lever: beams+diamonds disappear),
     CROSS / START / UP (pad-mirror bits + any deltas)
  6. GIF capture window (~f2600..3500, every 10th frame) -> gameplay GIF

Game model (from source, github.com/hardrockbluesky/BKBS_PSX main@):
  LoadingScreen ("Bambi's Knees / Bambi's Shaking") -> loads 11 CD files ->
  PlaySyncedTrack() hard-waits CDDA 0x82 -> gameplay: falling arrow notes,
  cine camera, SELECT cycles effectType (edge), arrows+face buttons hit
  notes (edge, timing-dependent). No title/menu.
Evidence: scratch/r21t1_bkbs/ (PNGs, boot_log.json, GIF, report.json).
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

OUT = os.path.join(REPO, "scratch", "r21t1_bkbs")
SHOTS = os.path.join(OUT, "shots")
GIFDIR = os.path.join(OUT, "gif_frames")
CONTENT = "/home/z/my-project/emu/games_homebrew/patched/bkbs_lic.cue"
CORE = "/home/z/my-project/ps1-test/cores/mednafen_psx_libretro.so"
BIOS = "/home/z/my-project/ps1-test/emu/system/openbios.bin"

TL_END = 2600          # timeline length (~43 s game time)
TL_STEP = 200          # PNG cadence on the timeline
GIF_A, GIF_B, GIF_EVERY = 2650, 3500, 10

R = {"task": "r21-t1", "game": "BKBS (Bambi's Knees / Bambi's Shaking)",
     "content": CONTENT, "boot_no": 2, "boot1_note": "timeline+scan OK, "
     "crashed at pulse log (script bug) -> this complete re-run",
     "started": time.strftime("%FT%TZ", time.gmtime()),
     "events": [], "shots": [], "pulses": {}}
PADS = []


def dump():
    with open(os.path.join(OUT, "boot_log.json"), "w") as f:
        json.dump(R, f, indent=1, default=str)


def log(ev, **kw):
    rec = {"f": core.frames_run, "t": round(time.time() - T0, 1),
           "event": ev, **kw}
    R["events"].append(rec)
    print(f"[r21t1] {json.dumps(rec, default=str)[:240]}", flush=True)
    dump()


def snap(tag):
    arr = core.frame_rgb()
    if arr is not None:
        p = os.path.join(SHOTS, f"{tag}_f{core.frames_run:05d}.png")
        Image.fromarray(arr).save(p)
        R["shots"].append({"tag": tag, "frame": core.frames_run,
                           "png": os.path.relpath(p, OUT),
                           "mean": round(float(arr.mean()), 2)})
    return arr


def pdiff(a, b):
    if a is None or b is None or a.shape != b.shape:
        return -1.0
    return round(float(np.abs(a.astype(int) - b.astype(int)).mean()), 2)


def diff_runs(a, b, min_abs=4, max_runs=30):
    x = a.view(np.uint32)
    y = b.view(np.uint32)
    d = np.flatnonzero(x != y)
    if d.size == 0:
        return []
    groups = np.split(d, np.flatnonzero(np.diff(d) > 4) + 1)
    out = []
    for g in groups:
        i0, i1 = int(g[0]), int(g[-1])
        span = {"off": i0 * 4, "va": f"0x{0x80000000 + i0 * 4:08x}",
                "n": int(i1 - i0 + 1),
                "before": [int(v) for v in x[i0:min(i0 + 3, i1 + 1)]],
                "after": [int(v) for v in y[i0:min(i0 + 3, i1 + 1)]]}
        if span["n"] <= 256 and max(abs(int(v)) for v in y[i0:i1 + 1]) >= min_abs:
            out.append(span)
    out.sort(key=lambda s: -max(abs(int(v)) for v in s["after"]))
    return out[:max_runs]


def mirror_now():
    return [int.from_bytes(bytes(core.ram[o + 2:o + 4]), "little")
            for o in PADS]


def pulse(button, hold=3, settle=45, extra_snaps=()):
    """3-frame press + settle; per-frame pad-mirror + vis delta + PNGs."""
    before = core.frame_rgb()
    mirror = []
    core.set_buttons(button)
    for _ in range(hold):
        core.run_frame()
        mirror.append(mirror_now())
    core.set_buttons(set())
    settled = 0
    while settled < settle:
        core.run_frame()
        settled += 1
        if settled in (10, 25, 45):
            snap(f"t_{button.lower()}_p{settled}")
    after = core.frame_rgb()
    res = {"button": button, "frame": core.frames_run,
           "mirror_press": mirror, "vis_diff": pdiff(before, after),
           "png_after": f"t_{button.lower()}_p45_f{core.frames_run:05d}.png"}
    snap(f"t_{button.lower()}_after")
    return res


T0 = time.time()
for d in (OUT, SHOTS):
    os.makedirs(d, exist_ok=True)
shutil.rmtree(os.path.join(OUT, "ws"), ignore_errors=True)
shutil.rmtree(GIFDIR, ignore_errors=True)
ws = os.path.join(OUT, "ws")
os.makedirs(os.path.join(ws, "system"), exist_ok=True)
os.makedirs(os.path.join(ws, "saves"), exist_ok=True)
shutil.copyfile(BIOS, os.path.join(ws, "system", "openbios.bin"))

core = LibretroCore(CORE, os.path.join(ws, "system"),
                    os.path.join(ws, "saves"),
                    var_overrides={b"beetle_psx_renderer": b"software",
                                   b"beetle_psx_frame_duping": b"disabled"})
av = core.load_game(CONTENT)
log("boot", core=core.core_name, ver=core.core_ver, av=av)

# ---- phase 1: boot timeline -------------------------------------------------
last = None
for i in range(TL_END):
    core.run_frame()
    if i % TL_STEP == 0:
        arr = core.frame_rgb()
        d = pdiff(last, arr)
        snap("boot")
        log("timeline", diff=d, ram_nonzero=int(np.count_nonzero(core.ram)))
        last = arr
log("timeline_done")

# ---- phase 2: pad buffer signature ------------------------------------------
ram = core.ram
sig0 = (ram[:-7] == 0) & (ram[1:-6] == 0x41) & (ram[2:-5] == 0xFF) \
    & (ram[3:-4] == 0xFF)
PADS = [int(i) for i in np.flatnonzero(sig0)[:12]]
R["padbuff"] = {hex(p): bytes(ram[p:p + 8]).hex() for p in PADS}
log("padbuff_scan", found=[hex(p) for p in PADS])

# ---- phase 3: frame counter hunt --------------------------------------------
a = core.ram.copy()
for _ in range(60):
    core.run_frame()
b = core.ram.copy()
xa, xb = a.view(np.int32), b.view(np.int32)
cand = np.flatnonzero(xb - xa == 60)
alive = []
for c in cand[:8]:
    c = int(c)
    series = []
    for _ in range(12):
        core.run_frame()
        series.append(int.from_bytes(bytes(core.ram[c * 4:c * 4 + 4]),
                                     "little", signed=True))
    inc = sum(1 for p, q in zip(series, series[1:]) if q - p == 1)
    if inc >= 10:
        alive.append({"va": f"0x{0x80000000 + c * 4:08x}",
                      "val": series[0], "trace": series, "inc_frames": inc})
log("frame_counter_scan", candidates=int(cand.size),
    alive=[{k: v for k, v in z.items() if k != "trace"} for z in alive])
R["frame_counters"] = alive

# ---- phase 4: gameplay-motion evidence ---------------------------------------
g1 = core.ram.copy()
snap("t_motion_a")
for _ in range(90):
    core.run_frame()
g2 = core.ram.copy()
snap("t_motion_b")
R["motion_runs"] = diff_runs(g1, g2, max_runs=20)
log("motion", changing_runs=len(R["motion_runs"]),
    top=[r["va"] for r in R["motion_runs"][:8]])

# ---- phase 5: input causality (3-frame pulses) -------------------------------
sel = pulse("SELECT")
sel["ram_runs"] = diff_runs(g2, core.ram.copy(), max_runs=20)
R["pulses"]["SELECT"] = sel
log("pulse_SELECT", vis_diff=sel["vis_diff"],
    mirror_press=[m[:2] for m in sel["mirror_press"]],
    ram_runs=len(sel["ram_runs"]),
    top=[(r["va"], r["before"], r["after"]) for r in sel["ram_runs"][:5]])

cr = pulse("X")
R["pulses"]["CROSS"] = cr
log("pulse_CROSS", vis_diff=cr["vis_diff"],
    mirror_press=[m[:2] for m in cr["mirror_press"]])

st = pulse("START")
R["pulses"]["START"] = st
log("pulse_START", vis_diff=st["vis_diff"],
    mirror_press=[m[:2] for m in st["mirror_press"]])

up = pulse("UP")
R["pulses"]["UP"] = up
log("pulse_UP", vis_diff=up["vis_diff"],
    mirror_press=[m[:2] for m in up["mirror_press"]])

# does the frame counter keep ticking after pulses?
if alive:
    va = int(alive[0]["va"], 16) - 0x80000000
    v_before = alive[0]["trace"][-1]
    for _ in range(60):
        core.run_frame()
    v_after = int.from_bytes(bytes(core.ram[va:va + 4]), "little",
                             signed=True)
    R["frame_counter_after_pulses"] = {"va": alive[0]["va"],
                                       "before": v_before, "after": v_after,
                                       "delta": v_after - v_before}
    log("counter_after_pulses", **R["frame_counter_after_pulses"])

# ---- phase 6: GIF capture window ---------------------------------------------
os.makedirs(GIFDIR, exist_ok=True)
n_gif = 0
for i in range(GIF_A, GIF_B):
    core.run_frame()
    if (i - GIF_A) % GIF_EVERY == 0:
        arr = core.frame_rgb()
        if arr is not None:
            Image.fromarray(arr).save(
                os.path.join(GIFDIR, f"g{i:05d}.png"))
            n_gif += 1
log("gif_window", frames=n_gif)

snap("t_final")
tail = [s for s in core.log_history
        if any(k in s.lower() for k in ("exe", "cd", "licens", "cdda"))]
R["core_log_tail"] = tail[-40:]
R["frames_total"] = core.frames_run
R["finished"] = time.strftime("%FT%TZ", time.gmtime())
dump()
print("[r21t1] DONE frames=", core.frames_run,
      "wall=", round(time.time() - T0, 1), flush=True)
