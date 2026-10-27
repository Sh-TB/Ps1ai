#!/usr/bin/env python3
"""r20-t2 autogaz: ONE boot -> timeline PNGs + padbuff + idle-vs-input RAM
diff sensor mining (+stretch policy). Run once, in its own process."""
import json
import os
import sys
import numpy as np

REPO = "/home/z/my-project/ps1ai"
sys.path.insert(0, REPO)
from ps1play.core.host import LibretroCore  # noqa: E402

OUT = os.path.join(REPO, "scratch", "r20t2_autogaz")
SHOTS = os.path.join(OUT, "shots")
os.makedirs(SHOTS, exist_ok=True)
CONTENT = "/home/z/my-project/emu/games_homebrew/patched/autogaz_lic.cue"
CORE = "/home/z/my-project/ps1-test/cores/mednafen_psx_libretro.so"
BIOS = "/home/z/my-project/ps1-test/emu/system/openbios.bin"

import shutil  # noqa: E402
from PIL import Image  # noqa: E402

ws = os.path.join(OUT, "ws")
shutil.rmtree(ws, ignore_errors=True)
os.makedirs(os.path.join(ws, "system"), exist_ok=True)
os.makedirs(os.path.join(ws, "saves"), exist_ok=True)
shutil.copyfile(BIOS, os.path.join(ws, "system", "openbios.bin"))

core = LibretroCore(CORE, os.path.join(ws, "system"),
                    os.path.join(ws, "saves"),
                    var_overrides={b"beetle_psx_renderer": b"software",
                                   b"beetle_psx_frame_duping": b"disabled"})
av = core.load_game(CONTENT)
print("core:", core.core_name, core.core_ver, "av:", av, flush=True)

log = {"av": av, "events": [], "shots": []}


def snap(tag, f):
    arr = core.frame_rgb()
    if arr is not None:
        p = os.path.join(SHOTS, f"{tag}_f{f:05d}.png")
        Image.fromarray(arr).save(p)
        log["shots"].append({"tag": tag, "frame": f, "png": os.path.relpath(p, OUT),
                             "mean": float(arr.mean())})
        print(f"  [{tag}] f={f} mean={arr.mean():.1f} shape={arr.shape}", flush=True)
    m = {"f": f, "ram_nonzero": int(np.count_nonzero(core.ram))}
    log["events"].append(m)
    return arr


def view(off=0, n=2 * 1024 * 1024):
    return core.ram[off:off + n]


def diff_runs(a, b, min_abs=8, max_runs=40):
    """u32-view differing runs, grouped, sorted by |delta| desc."""
    x = a.view(np.uint32)
    y = b.view(np.uint32)
    d = np.flatnonzero(x != y)
    if d.size == 0:
        return []
    groups = np.split(d, np.flatnonzero(np.diff(d) > 4) + 1)
    out = []
    for g in groups:
        i0, i1 = int(g[0]), int(g[-1])
        delta = int(y[i1]) - int(x[i1]) if i0 == i1 else None
        span = {"off": i0 * 4, "end": i1 * 4 + 3, "n": int(i1 - i0 + 1),
                "va": f"0x{0x80000000 + i0 * 4:08x}",
                "before": [int(v) for v in x[i0:min(i0 + 4, i1 + 1)]],
                "after": [int(v) for v in y[i0:min(i0 + 4, i1 + 1)]]}
        if i0 == i1:
            span["delta"] = delta
        if span["n"] <= 512 and max(abs(int(y[i])) for i in g) >= min_abs:
            out.append(span)
    out.sort(key=lambda s: -max(abs(int(v)) for v in s["after"]))
    return out[:max_runs]


# ---- boot timeline: 4200 frames, PNG every 600 ----
last = None
for i in range(4200):
    core.run_frame()
    if i % 600 == 0:
        arr = core.frame_rgb()
        if arr is not None:
            d = float(np.abs(arr.astype(int) - last.astype(int)).mean()) \
                if last is not None and arr.shape == last.shape else -1.0
            p = os.path.join(SHOTS, f"boot_f{i:05d}.png")
            Image.fromarray(arr).save(p)
            log["shots"].append({"tag": "boot", "frame": i, "diff": d,
                                 "png": os.path.relpath(p, OUT),
                                 "mean": float(arr.mean())})
            print(f"boot f{i} diff={d:.2f} mean={arr.mean():.1f}", flush=True)
            last = arr
        if i == 100:
            print("RAM nonzero @f100:", int(np.count_nonzero(core.ram)), flush=True)

snap("t_title", 4200)

# padbuff check (kernel pad buffers observed at 0xBB120/0xBB142 in prior rounds)
ram = core.ram
pb1 = bytes(ram[0xBB120:0xBB128])
pb2 = bytes(ram[0xBB142:0xBB14A])
log["padbuff"] = {"0xBB120": pb1.hex(), "0xBB142": pb2.hex()}
print("padbuff:", log["padbuff"], flush=True)

# ---- sensors: idle vs input diffing ----
s1 = view().copy()
for _ in range(300):
    core.run_frame()
s2 = view().copy()
idle_runs = diff_runs(s1, s2)
print("idle-changing u32 runs:", len(idle_runs), flush=True)

for _ in range(120):
    core.run_frame()

# START press (12f) -> title advance?
core.set_buttons("START")
for _ in range(12):
    core.run_frame()
core.set_buttons(set())
snap("t_after_start", core.frames_run)
for _ in range(30):
    core.run_frame()
s3 = view().copy()
for _ in range(240):
    core.run_frame()
s4 = view().copy()
snap("t_after_start_240", core.frames_run)
start_runs = diff_runs(s1, s4)
print("start-correlated u32 runs:", len(start_runs), flush=True)

# CROSS press
core.set_buttons("X")
for _ in range(12):
    core.run_frame()
core.set_buttons(set())
snap("t_after_x", core.frames_run)
for _ in range(30):
    core.run_frame()
s5 = view().copy()
for _ in range(240):
    core.run_frame()
s6 = view().copy()
snap("t_after_x_240", core.frames_run)
x_runs = diff_runs(s1, s6)
print("x-correlated u32 runs:", len(x_runs), flush=True)

# SECOND idle window for score-in-attract candidates (compare s6 vs s2)
late_idle = diff_runs(s2, s6, max_runs=25)
print("late idle-changing runs:", len(late_idle), flush=True)

log["sensors"] = {"idle": idle_runs, "start": start_runs, "x": x_runs,
                  "late_idle": late_idle}
log["padbuff_after"] = {"0xBB120": bytes(ram[0xBB120:0xBB128]).hex(),
                        "0xBB142": bytes(ram[0xBB142:0xBB14A]).hex()}
with open(os.path.join(OUT, "boot_log.json"), "w") as f:
    json.dump(log, f, indent=1)
print("DONE frames=", core.frames_run, flush=True)
