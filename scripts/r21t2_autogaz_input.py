#!/usr/bin/env python3
"""r21-t2 autogaz: ONE boot -> prove/refute INPUT_RESPONSIVE.

Static-RE groundwork (scripts/r21t2_re_scan.py + upstream source
egemenkus0/autogaz ps1/main.c, cloned read-only):
  game main loop @0x800103d0 checks, per frame:
    padStatus = PadRead(0)                    ; PadRead @0x80017a88
    if (padStatus & 0x40) and state==0: state=1   ; mask 0x40 = bit 6
    elif (padStatus & 0x20) and state==3: state=0 ; mask 0x20 = bit 5
  PadRead returns ~(*(u32*)0x800BE548)  -- INVERTED (active-high) pad word.
  state @0x800BC7EC (_gp+0x18), timerVal @0x800BC7F0 (_gp+0x1C),
  Timer() @0x80010b18: timerVal++ ; if timerVal==476: state=3.
  -> state 0 shows "before" TIM; press(DOWN, bit6) -> state 1->2 ("after"
     image + VAG audio); 476 f later state 3 ("polat"); press(RIGHT, bit5)
     -> state 0.  r20's sweep pressed START/SELECT/TRIANGLE/CIRCLE/SQUARE
     (ps1play X/O/SQ/TR names) but NEVER D-pad DOWN/RIGHT -> no response.

Runtime plan (single boot, single process):
  A: f0..f1200 idle baseline + full-RAM scan of 00 41 ff ff instances.
  B: real port-0 input: DOWN 90f -> expect state 0->2 + screen change;
     idle watch timerVal to 476 -> state 3; RIGHT 90f -> state 0 (reversal);
     DOWN again (2nd causal event); then CROSS/CIRCLE probes (expect none).
  C (fallback, only if B shows no buffer flip): poke raw active-low words
     into the libpad buffer u32 @0x800BE548 every frame.
Logs JSON + labeled PNGs to scratch/r21t2_autogaz/.
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

# RAM offsets (u32)
STATE = 0xBC7EC        # game state 0/1/2/3
TIMERVAL = 0xBC7F0     # state-2 frame timer (fires at 476)
PADBUF = 0xBE548       # game libpad buffer (raw active-low word)
KPAD1 = 0xB008         # kernel pad1 buffer (00 41 ff ff)
FCNT = 0xBCC00         # r20 frame counter (+1/frame)
GP = 0x800BC7D4        # _gp from crt0 (lui 0x800c; addiu -0x382c)

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

R = {"task": "r21-t2 autogaz input causality",
     "core": str(core.core_name), "boot_frames": 0,
     "watch_names": ["state", "timerVal", "padbuf", "kpad1", "fcnt"],
     "trace": [], "pngs": [], "pad_scan": {}, "events": []}
trace = {"f": [], "state": [], "timerVal": [], "padbuf": [], "kpad1": [],
         "fcnt": []}


def watch():
    f = core.frames_run
    trace["f"].append(f)
    trace["state"].append(int(np.frombuffer(core.ram, np.uint32,
                                            count=1, offset=STATE)[0]))
    trace["timerVal"].append(int(np.frombuffer(core.ram, np.uint32,
                                               count=1, offset=TIMERVAL)[0]))
    trace["padbuf"].append(int(np.frombuffer(core.ram, np.uint32,
                                             count=1, offset=PADBUF)[0]))
    trace["kpad1"].append(int(np.frombuffer(core.ram, np.uint32,
                                            count=1, offset=KPAD1)[0]))
    trace["fcnt"].append(int(np.frombuffer(core.ram, np.uint32,
                                           count=1, offset=FCNT)[0]))


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


def pad_scan():
    ram = core.ram
    hits = []
    i = 0
    n = len(ram) - 4
    b = ram
    # vectorized search for 00 41 ff ff
    m = (b[0:n] == 0) & (b[1:n + 1] == 0x41) & (b[2:n + 2] == 0xFF) \
        & (b[3:n + 3] == 0xFF)
    idx = np.flatnonzero(m)
    for i in idx:
        i = int(i)
        ctx = bytes(ram[i - 4:i + 12]).hex()
        hits.append({"va": f"0x{0x80000000 + i:08x}", "ctx": ctx})
    R["pad_scan"] = {"frame": core.frames_run, "hits": hits}
    print(f"pad-pattern scan: {len(hits)} hits", flush=True)
    for h in hits[:12]:
        print("   ", h, flush=True)


def run(n, tag_every=None):
    for i in range(n):
        core.run_frame()
        if trace["f"] and core.frames_run - trace["f"][-1] >= 1 \
                and (i % 5 == 0 or i == n - 1):
            watch()
        if tag_every and (i % tag_every == tag_every - 1):
            pass


def transition_check(tag):
    """Watch for state/padbuf transitions during held input; log events."""
    prev_state = trace["state"][-1] if trace["state"] else -1
    return prev_state


# ================= Phase A: idle boot baseline =================
print("== Phase A: idle f0..f1200 ==", flush=True)
for i in range(1200):
    core.run_frame()
    if i % 10 == 0 or i == 1199:
        watch()
    if i in (300, 600, 900, 1200):
        shot(f"A_idle_f{i:04d}")
a_state = trace["state"][-1]
print(f"after idle: state={a_state} padbuf={trace['padbuf'][-1]:#010x} "
      f"kpad1={trace['kpad1'][-1]:#010x} fcnt={trace['fcnt'][-1]}",
      flush=True)
pad_scan()
pre_png = shot("A_pre_input")

# ================= Phase B: real port-0 input =================
print("== Phase B: real input ==", flush=True)


def press(btn, frames, tag):
    """Hold btn for `frames`, watch every frame, PNG at key moments."""
    core.set_buttons(btn)
    ev = {"btn": btn, "start_f": core.frames_run, "state_before":
          trace["state"][-1], "padbuf_before": trace["padbuf"][-1],
          "states": []}
    st0 = trace["state"][-1]
    for i in range(frames):
        core.run_frame()
        watch()
        st = trace["state"][-1]
        if not ev["states"] or ev["states"][-1][1] != st:
            ev["states"].append([core.frames_run, st])
            print(f"  [{tag}] f={core.frames_run} {btn}: state->{st}",
                  flush=True)
        if i in (0, frames // 2, frames - 1):
            shot(f"B_{tag}_{i:03d}")
    core.set_buttons(set())
    ev["end_f"] = core.frames_run
    ev["padbuf_after"] = trace["padbuf"][-1]
    ev["state_after"] = trace["state"][-1]
    R["events"].append(ev)
    return ev


# B1: DOWN (raw bit6) at state 0 -> expect 0->1->2
press("DOWN", 90, "down1")
post_down = shot("B_after_down1")

# watch timerVal 0->476 (state 2 -> 3) up to 560 frames
saw3 = False
for i in range(560):
    core.run_frame()
    watch()
    if trace["state"][-1] == 3 and not saw3:
        saw3 = True
        print(f"  state 3 reached at f={core.frames_run} "
              f"timerVal={trace['timerVal'][-1]}", flush=True)
        shot("B_state3_polat")
        break
R["events"].append({"btn": None, "kind": "timed_476",
                    "state3_at_f": core.frames_run if saw3 else None,
                    "timerVal_expected_476": True})
if not saw3:
    print("  NO state 3 after 560f idle watch (timerVal=",
          trace["timerVal"][-1], ")", flush=True)
    shot("B_no_state3")

# B2: RIGHT (raw bit5) at state 3 -> expect 3->0
press("RIGHT", 90, "right1")
post_right = shot("B_after_right1")

# B3: DOWN again -> second causal event + reversal
press("DOWN", 60, "down2")
shot("B_after_down2")

# B4: no-op probes (source says these do nothing in states 0..2)
press("B", 60, "cross_probe")
press("A", 60, "circle_probe")
shot("B_after_probes")

# ================= Phase C: pad-buffer poke (fallback) =================
b_state_changes = [e for e in R["events"] if e.get("states")]
R["phase_b_state_changed"] = bool(b_state_changes)
if not b_state_changes:
    print("== Phase C: poke libpad buffer @0x800BE548 ==", flush=True)
    for name, word in (("poke_down", 0xFFFFFFBF),   # raw bit6=0
                       ("poke_right", 0xFFFFFFDF),  # raw bit5=0
                       ("poke_down_hi", 0xFFBFFFFF),
                       ("poke_right_hi", 0xFFDFFFFF)):
        pre = trace["state"][-1]
        for i in range(60):
            core.run_frame()
            core.ram[PADBUF:PADBUF + 4] = np.uint32(word).tobytes()
            watch()
        R["events"].append({"btn": name, "word": hex(word),
                            "state_before": pre,
                            "state_after": trace["state"][-1],
                            "start_f": core.frames_run - 60})
        shot(f"C_{name}")
        if trace["state"][-1] != pre:
            print(f"  {name}: state {pre}->{trace['state'][-1]}", flush=True)
            break

# ================= wrap up =================
final = shot("Z_final")
R["boot_frames"] = core.frames_run
np.save(os.path.join(OUT, "ram_final.npy"), core.ram.copy())
with open(os.path.join(OUT, "watch_trace.json"), "w") as f:
    json.dump(trace, f)
with open(os.path.join(OUT, "boot_log.json"), "w") as f:
    json.dump(R, f, indent=1)
print("DONE frames=", core.frames_run, flush=True)
