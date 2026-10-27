#!/usr/bin/env python3
"""r21-t2 autogaz boot #2 (final): close the full input loop.

Boot #1 (r21t2_autogaz_input.py) proved: real port-0 CROSS (ps1play "B")
press at f2001 -> libpad buffer 0x800BE548 flips to 0xFFFFFFBF the SAME
frame, PadRead(0)=~word has bit6 set, game state @0x800BC7EC 0->1->2,
screen "before"(mean 121.3) -> "after"(mean 133.7). Layout decoded:
buffer bytes = [pad1 buttons byteB, byteA, pad2?, pad2?] (byte-swapped);
PadRead returns ~u32, so bit6==CROSS, bit5==CIRCLE (PSY-Q PADRdown/
PADRright are the face buttons in active-high convention).

Boot #2 closes the source-predicted cycle (main.c):
  CROSS at state0 -> state1/2 ("after" + VAG audio)
  476 frames later Timer() -> state3 ("polat")
  CIRCLE at state3 -> state0 ("before")        <- reversal test
  CROSS again -> state1/2 ("after")            <- second causal event
Per-frame trace during presses; PNG at every stage.
"""
import json
import os
import shutil
import sys

import numpy as np
from PIL import Image

REPO = "/home/z/my-project/ps1ai"
sys.path.insert(0, REPO)
from ps1play.core.host import LibretroCore  # noqa: E402

OUT = os.path.join(REPO, "scratch", "r21t2_autogaz")
SHOTS = os.path.join(OUT, "shots")
os.makedirs(SHOTS, exist_ok=True)
CONTENT = "/home/z/my-project/emu/games_homebrew/patched/autogaz_lic.cue"
CORE = "/home/z/my-project/ps1-test/cores/mednafen_psx_libretro.so"
BIOS = "/home/z/my-project/ps1-test/emu/system/openbios.bin"

STATE, TIMERVAL, PADBUF, KPAD1, FCNT = 0xBC7EC, 0xBC7F0, 0xBE548, 0xB008, 0xBCC00

ws = os.path.join(OUT, "ws2")
shutil.rmtree(ws, ignore_errors=True)
os.makedirs(os.path.join(ws, "system"), exist_ok=True)
os.makedirs(os.path.join(ws, "saves"), exist_ok=True)
shutil.copyfile(BIOS, os.path.join(ws, "system", "openbios.bin"))

core = LibretroCore(CORE, os.path.join(ws, "system"),
                    os.path.join(ws, "saves"),
                    var_overrides={b"beetle_psx_renderer": b"software",
                                   b"beetle_psx_frame_duping": b"disabled"})
core.load_game(CONTENT)
print("core:", core.core_name, flush=True)

R = {"task": "r21-t2 boot2 full input cycle", "events": [], "pngs": [],
     "per_frame": []}


def u32(off):
    return int(np.frombuffer(core.ram, np.uint32, count=1, offset=off)[0])


def shot(tag):
    arr = core.frame_rgb()
    if arr is not None:
        p = os.path.join(SHOTS, f"{tag}.png")
        Image.fromarray(arr).save(p)
        R["pngs"].append({"tag": tag, "frame": core.frames_run,
                          "mean": round(float(arr.mean()), 2),
                          "png": os.path.relpath(p, OUT)})
        print(f"  [{tag}] f={core.frames_run} mean={arr.mean():.1f}",
              flush=True)
    return arr


def idle(frames, png_every=0):
    for i in range(frames):
        core.run_frame()
        if png_every and (i + 1) % png_every == 0:
            shot(f"idle_f{core.frames_run:05d}")


def press_trace(btn, frames, tag):
    """Hold btn, record state/padbuf EVERY frame (trigger-frame capture)."""
    core.set_buttons(btn)
    ev = {"btn": btn, "tag": tag, "start_f": core.frames_run,
          "seq": []}
    st_prev = u32(STATE)
    for i in range(frames):
        core.run_frame()
        st = u32(STATE)
        rec = {"f": core.frames_run, "padbuf": f"{u32(PADBUF):#010x}",
               "state": st}
        if st != st_prev or i < 3 or i == frames - 1:
            ev["seq"].append(rec)
            R["per_frame"].append(rec)
            if st != st_prev:
                print(f"  [{tag}] f={core.frames_run} state {st_prev}->{st}"
                      f" padbuf={u32(PADBUF):#010x}", flush=True)
            st_prev = st
    core.set_buttons(set())
    ev["end_f"] = core.frames_run
    R["events"].append(ev)
    return ev


def wait_state(target, max_frames, tag):
    for _ in range(max_frames):
        core.run_frame()
        if u32(STATE) == target:
            print(f"  state {target} at f={core.frames_run} "
                  f"timerVal={u32(TIMERVAL)}", flush=True)
            shot(tag)
            return core.frames_run
    print(f"  TIMEOUT waiting state {target} (state={u32(STATE)} "
          f"timerVal={u32(TIMERVAL)})", flush=True)
    return None


# ---------- idle baseline ----------
idle(1300)
print(f"baseline: state={u32(STATE)} padbuf={u32(PADBUF):#010x} "
      f"mean={core.frame_rgb().mean():.1f}", flush=True)
shot("b2_before_state0")
R["baseline"] = {"f": core.frames_run, "state": u32(STATE),
                 "padbuf": f"{u32(PADBUF):#010x}"}

# ---------- 1. CROSS: state0 -> 1/2 ----------
press_trace("B", 45, "cross1")
f_state2 = core.frames_run
shot("b2_after_cross_state2")

# ---------- 2. timed 476: state2 -> 3 ----------
f3 = wait_state(3, 700, "b2_state3_polat")
R["timed_transition"] = {"state2_at": f_state2, "state3_at": f3,
                         "delta": (f3 - f_state2) if f3 else None,
                         "timerVal_expected": 476}

# ---------- 3. CIRCLE at state3 -> 0 (reversal) ----------
press_trace("O", 45, "circle_state3")
shot("b2_after_circle_state0")

# ---------- 4. CROSS again -> 1/2 ----------
press_trace("B", 45, "cross2")
shot("b2_after_cross2_state2")

# ---------- 5. negative probe: SQUARE at state2 (no-op) ----------
press_trace("Y", 45, "square_probe")
shot("b2_after_square_state2")

R["final_state"] = u32(STATE)
R["boot_frames"] = core.frames_run
np.save(os.path.join(OUT, "ram_b2.npy"), core.ram.copy())
with open(os.path.join(OUT, "boot2_log.json"), "w") as f:
    json.dump(R, f, indent=1)
print("DONE frames=", core.frames_run, flush=True)
