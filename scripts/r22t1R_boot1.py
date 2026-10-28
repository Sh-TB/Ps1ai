#!/usr/bin/env python3
"""r22t1R_boot1.py — MSPSX boot 1 (license-patched disc, EXE UNPATCHED).

Purpose: falsify/verify the r22t1 decode's root-cause prediction:
  RXEN never set -> ReceiveInProgress never true -> pad_buff[0]=00 00 00 00
  -> held=~0=0xFFFF (phantom) on first Pad_Update -> pressed=0xFFFF ->
  PAD_START auto-fires -> title exits itself within ~1-2 frames of the first
  poll, then board is completely inert (pressed stays 0 forever).

Boot counter: boots_used.json (hard cap 2, asserted here: must be 0 -> 1).

Phases (single process, JSON dumped incrementally to boot1_log.json):
  1. warmup 90 f, PNG every 30 (BIOS shell -> game load)
  2. watch f=90..1500: per-frame pad symbols (pad_buff_len, pad_buff[0],
     held/oldHeld/pressed) + visual diff; transition events get PNG pairs
  3. idle window 120 f: cursor/revealed/board static check (inert board)
  4. final symbol dump + prediction verdicts (recorded, never inflated)
"""
import json
import os
import sys
import time

import numpy as np
from PIL import Image

REPO = "/home/z/my-project/ps1ai"
sys.path.insert(0, REPO)
from ps1play.core.host import LibretroCore  # noqa: E402

OUT = os.path.join(REPO, "scratch", "r22t1_mspsx")
SHOTS = os.path.join(OUT, "shots_b1")
CONTENT = "/home/z/my-project/emu/games_homebrew/patched/mspsx_lic.cue"
CORE = "/home/z/my-project/ps1-test/cores/mednafen_psx_libretro.so"
BIOS = "/home/z/my-project/ps1-test/emu/system/openbios.bin"
BOOTS = os.path.join(OUT, "boots_used.json")

WATCH_END = 1500
IDLE_N = 120

SYM = {"pad_buff0": 0x1AC48, "pad_buff_len0": 0x18D08, "oldHeld": 0x18CF8,
       "pressed": 0x18CFC, "released": 0x18CFA, "held": 0x18CFE,
       "board": 0x199DC, "cursorX": 0x18CD4, "cursorY": 0x18CD0,
       "revealed_total": 0x18CDC, "valid_total": 0x18CD8,
       "mine_count": 0x18CEC, "control_disable": 0x18CE4, "lost": 0x18CE0,
       "FIRST_CLICK": 0x18CCC, "GRID_W": 0x18C9C, "GRID_H": 0x18C98}

R = {"task": "r22t1-R boot1", "content": CONTENT, "exe": "UNPATCHED",
     "started": time.strftime("%FT%TZ", time.gmtime()),
     "events": [], "shots": [], "transitions": []}


def boots_used():
    if os.path.exists(BOOTS):
        with open(BOOTS) as f:
            return json.load(f).get("count", 0)
    return 0


def claim_boot(n_expected):
    n = boots_used()
    assert n == n_expected, f"boot counter {n} != expected {n_expected} " \
                            f"(hard cap 2)"
    with open(BOOTS, "w") as f:
        json.dump({"count": n + 1,
                   "log": [{"boot": n + 1, "script": "r22t1R_boot1.py",
                            "image": "mspsx_lic.bin (license only, EXE "
                                     "unpatched)",
                            "t": time.strftime("%FT%TZ", time.gmtime())}]}, f,
                  indent=1)
    return n + 1


def dump():
    with open(os.path.join(OUT, "boot1_log.json"), "w") as f:
        json.dump(R, f, indent=1, default=str)


def log(ev, **kw):
    rec = {"f": core.frames_run, "t": round(time.time() - T0, 1),
           "event": ev, **kw}
    R["events"].append(rec)
    print(f"[b1] {json.dumps(rec, default=str)[:220]}", flush=True)
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


def sym_all():
    ram = core.ram
    d = {"pad_buff0": bytes(ram[SYM["pad_buff0"]:SYM["pad_buff0"] + 4]).hex(),
         "pad_buff1": bytes(ram[SYM["pad_buff0"] + 34:
                                 SYM["pad_buff0"] + 38]).hex(),
         "pad_buff_len0": int.from_bytes(
             bytes(ram[SYM["pad_buff_len0"]:SYM["pad_buff_len0"] + 4]),
             "little"),
         "oldHeld": int.from_bytes(
             bytes(ram[SYM["oldHeld"]:SYM["oldHeld"] + 2]), "little"),
         "pressed": int.from_bytes(
             bytes(ram[SYM["pressed"]:SYM["pressed"] + 2]), "little"),
         "held": int.from_bytes(
             bytes(ram[SYM["held"]:SYM["held"] + 2]), "little"),
         "cursorX": int.from_bytes(
             bytes(ram[SYM["cursorX"]:SYM["cursorX"] + 4]), "little",
             signed=True),
         "cursorY": int.from_bytes(
             bytes(ram[SYM["cursorY"]:SYM["cursorY"] + 4]), "little",
             signed=True),
         "revealed_total": int.from_bytes(
             bytes(ram[SYM["revealed_total"]:SYM["revealed_total"] + 4]),
             "little", signed=True),
         "valid_total": int.from_bytes(
             bytes(ram[SYM["valid_total"]:SYM["valid_total"] + 4]),
             "little", signed=True),
         "mine_count": int.from_bytes(
             bytes(ram[SYM["mine_count"]:SYM["mine_count"] + 4]), "little",
             signed=True),
         "control_disable": ram[SYM["control_disable"]],
         "lost": ram[SYM["lost"]],
         "board_nonzero": int(np.count_nonzero(
             ram[SYM["board"]:SYM["board"] + 4608]))}
    return d


T0 = time.time()
for d in (OUT, SHOTS):
    os.makedirs(d, exist_ok=True)
assert boots_used() == 0, "boot cap already consumed"
BOOT_NO = claim_boot(0)

shutil_ws = os.path.join(OUT, "ws")
import shutil  # noqa: E402
shutil.rmtree(shutil_ws, ignore_errors=True)
os.makedirs(os.path.join(shutil_ws, "system"), exist_ok=True)
os.makedirs(os.path.join(shutil_ws, "saves"), exist_ok=True)
shutil.copyfile(BIOS, os.path.join(shutil_ws, "system", "openbios.bin"))

core = LibretroCore(CORE, os.path.join(shutil_ws, "system"),
                    os.path.join(shutil_ws, "saves"),
                    var_overrides={b"beetle_psx_renderer": b"software",
                                   b"beetle_psx_frame_duping": b"disabled"})
av = core.load_game(CONTENT)
log("boot", boot_no=BOOT_NO, core=core.core_name, ver=core.core_ver, av=av)

# ---- phase 1: warmup ---------------------------------------------------------
for i in range(90):
    core.run_frame()
    if i % 30 == 0:
        snap("warm")
        log("warmup", sym=sym_all())
log("warmup_done")

# ---- phase 2: watch window ---------------------------------------------------
last = snap("watch_start")
first_poll_f = None
first_nonzero_pad_f = None
held_ffff_f = None
last_tr_f = -99
for f in range(90, WATCH_END):
    core.run_frame()
    ram = core.ram
    plen = int.from_bytes(bytes(ram[SYM["pad_buff_len0"]:
                                    SYM["pad_buff_len0"] + 4]), "little")
    pb = bytes(ram[SYM["pad_buff0"]:SYM["pad_buff0"] + 4])
    if plen >= 4 and first_poll_f is None:
        first_poll_f = core.frames_run
        snap("first_poll")
        log("first_poll_complete", pad_buff_len=plen, pad_buff0=pb.hex(),
            sym=sym_all())
    if pb != b"\x00\x00\x00\x00" and first_nonzero_pad_f is None:
        first_nonzero_pad_f = core.frames_run
        log("pad_buff0_nonzero", pad_buff0=pb.hex())
    held = int.from_bytes(bytes(ram[SYM["held"]:SYM["held"] + 2]), "little")
    if held == 0xFFFF and held_ffff_f is None:
        held_ffff_f = core.frames_run
        log("held_phantom_ffff", held=held, pressed=int.from_bytes(
            bytes(ram[SYM["pressed"]:SYM["pressed"] + 2]), "little"))
    arr = core.frame_rgb()
    d = pdiff(last, arr)
    if d > 8 and core.frames_run - last_tr_f >= 10:
        last_tr_f = core.frames_run
        png = f"tr_f{core.frames_run:05d}.png"
        Image.fromarray(arr).save(os.path.join(SHOTS, png))
        R["transitions"].append({"frame": core.frames_run, "diff": d,
                                 "png": png})
        log("transition", diff=d, sym=sym_all())
    last = arr
    if (f - 90) % 150 == 0:
        snap("watch")
        log("watch_tick", sym=sym_all())
log("watch_done", first_poll_f=first_poll_f,
    first_nonzero_pad_f=first_nonzero_pad_f, held_ffff_f=held_ffff_f,
    transitions=len(R["transitions"]))

# ---- phase 3: idle window (board inert check) --------------------------------
a_sym = sym_all()
a_ram = core.ram.copy()
snap("idle_a")
for _ in range(IDLE_N):
    core.run_frame()
b_sym = sym_all()
b_ram = core.ram.copy()
snap("idle_b")
board_delta = int(np.abs(a_ram[SYM["board"]:SYM["board"] + 4608].astype(int)
                         - b_ram[SYM["board"]:SYM["board"] + 4608]
                         .astype(int)).sum())
R["idle"] = {"n": IDLE_N, "a": a_sym, "b": b_sym, "board_delta": board_delta,
             "cursor_moved": (a_sym["cursorX"], a_sym["cursorY"]) !=
                             (b_sym["cursorX"], b_sym["cursorY"])}
log("idle_done", **R["idle"])

# ---- final -------------------------------------------------------------------
R["final_sym"] = sym_all()
R["predictions"] = {
    "P1_pad_buff0_all_zeros": first_nonzero_pad_f is None,
    "P2_held_phantom_0xFFFF": held_ffff_f is not None,
    "P3_title_auto_exit_no_input": len(R["transitions"]) > 0,
    "P4_board_inert": R["final_sym"]["revealed_total"] == 0
                      and not R["idle"]["cursor_moved"],
}
R["verdict_boot1"] = ("CONFIRMED" if all(R["predictions"].values())
                      else "REFUTED")
R["boot_no"] = BOOT_NO
R["frames_total"] = core.frames_run
R["core_log_tail"] = [s for s in core.log_history
                      if any(k in s.lower() for k in
                             ("exe", "cdrom", "licens", "ps-exe"))][-15:]
R["finished"] = time.strftime("%FT%TZ", time.gmtime())
dump()
print("[b1] DONE frames=", core.frames_run, "wall=", round(time.time() - T0, 1),
      "verdict=", R["verdict_boot1"], "preds=", R["predictions"], flush=True)
